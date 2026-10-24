"""Chạy tự động một trận trên API website Việt Nam, không đặt lại trận."""

import argparse
from copy import deepcopy
from functools import partial
import os
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.error import URLError

from .live_api import APIError, LiveAPI
from .live_storage import cleanup_run, run_lock, write_json
from .model import Agent, Board, State
from .planner import plan_day
from .simulator import simulate_day
from .team_selection import select_types
from . import native
from .tour import PARAMS, make_session, plan_key, reaches_bound, warm_up


ROOT = Path(__file__).resolve().parents[2]
ENDPOINTS = {'practice': '/api/game/practice/actions', 'timed': '/api/game/actions'}
# Trận tính giờ: kiểm tra bài tốt nhất mỗi CHECK_EVERY giây; nộp lại giữa ngày cách nhau ít nhất
# MIN_GAP giây, tối đa MID_SUBMITS lần (cùng bài nhanh và bài cuối: tối đa 5 lần nộp/ngày).
CHECK_EVERY, MIN_GAP, MID_SUBMITS = 2.0, 5.0, 3


def detect_mode(requested, game_id, remote, day_info=None):
    if requested != 'auto':
        return requested
    if ':' in game_id:
        return 'practice'
    # Practice có thể trả đồng hồ bằng 0 do cấu hình thời gian gốc đã cũ.
    # Chỉ xác nhận khi API ngày ghi rõ không có hạn, không suy từ số 0 đơn lẻ.
    if (day_info is not None and 'endsAt' in day_info
            and day_info['endsAt'] is None
            and remote.get('day_deadline_in') in (None, 0)):
        return 'practice'
    if remote.get('day_deadline_in') == 0:
        raise ValueError('Máy chủ trả đồng hồ bằng 0, chưa xác định được Practice hay trận đã hết hạn. '
                         'Nếu đây là Practice tự luyện, chạy lại cùng lệnh và thêm --mode practice; '
                         'nếu là trận tính giờ, thêm --mode timed. Không cần reset.')
    if remote.get('day_deadline_in') is not None or remote.get('selection_deadline_in') is not None:
        return 'timed'
    if remote.get('status') in ('running', 'playing', 'in_progress') and 'day_deadline_in' in remote:
        return 'practice'
    raise ValueError('Chưa phân biệt được loại trận; dùng --mode timed hoặc --mode practice.')


def authoritative_state(board, raw, own, journal):
    day = raw['day']
    if not 0 <= day < len(board.day_steps):
        raise ValueError('Ngày hiện tại nằm ngoài cấu hình trận.')
    if len(raw['agents']) != len(board.starts) or 'traffics' not in raw:
        raise ValueError('Máy chủ thiếu danh sách xe hoặc trạng thái đường.')
    agents = []
    for a in raw['agents']:
        if (a['kind'] not in (0, 1) or not 0 <= a['pos'] < board.width * board.height
                or board.terrain(a['pos']) == 3 or not 0 <= a['fuel'] <= board.fuel_limit):
            raise ValueError('Máy chủ trả trạng thái xe không hợp lệ.')
        agents.append(Agent(a['kind'], a['pos'], a['fuel']))
    traffic = {}
    for road in raw['traffics']:
        p, status = road['pos'], road['status']
        if (not 0 <= p < board.width * board.height or board.terrain(p) != 1
                or status not in (0, 1, 2) or p in traffic):
            raise ValueError('Máy chủ trả trạng thái đường không hợp lệ.')
        traffic[p] = status
    known = own.get('distinct_types')
    if known is None:
        known = journal.get('brands')
        if day > 0 and known is None:
            raise ValueError('Thiếu lịch sử loại udon; không tự giả định chưa thu loại nào.')
    state = State(agents, traffic, set(known or []),
                  own.get('cumulative_daily_types', journal.get('daily_sum', 0)),
                  own.get('total_servings', 0), journal.get('road_history', []), day)
    return state


def predict(board, state, algorithm, seconds, workers=1, seed=0, parallel_objective="lookahead"):
    if algorithm != 'rollout':
        plan = plan_day(board, state, board.day_steps[state.day], algorithm, seconds, workers=workers,
                        seed=seed, parallel_objective=parallel_objective)
        return plan.actions, {'algorithm': algorithm, 'fallback': plan.fallback,
                              'searches': plan.searches, 'parallel': plan.details}
    deadline = time.monotonic() + seconds
    # Luôn tạo một kế hoạch khả thi trước; không dùng giả định tương lai để kiểm tra ngày hiện tại.
    candidates = []
    for strategy in ('greedy', 'lookahead'):
        remaining = deadline - time.monotonic()
        if remaining <= .02:
            break
        plan = plan_day(board, state, board.day_steps[state.day], strategy, min(2., remaining * .25))
        candidates.append((strategy, plan.actions))
    best_actions = candidates[0][1] if candidates else [[-board.day_steps[state.day]] for a in state.agents]
    best_score, source = None, 'greedy'
    for name, actions in candidates:
        current = deepcopy(state)
        first = True
        while current.day < len(board.day_steps) and time.monotonic() < deadline:
            steps = board.day_steps[current.day]
            commands = actions if first else plan_day(board, current, steps, 'greedy',
                                                       min(.1, max(0, deadline-time.monotonic()))).actions
            checked = simulate_day(board, current, commands, steps)
            if not checked.valid:
                break
            current, first = checked.state, False
        if current.day == len(board.day_steps) and (best_score is None or current.score() > best_score):
            best_score, best_actions, source = current.score(), actions, name
    return best_actions, {'algorithm': 'rollout', 'selected': source,
                          'predicted_score': best_score, 'future_assumption': 'one_team'}


class MatchRunner:
    def __init__(self, api, game_id, folder, algorithm='greedy', mode='auto',
                 seconds=20., reserve=4., selection_seconds=8., roles='auto', kinds=None,
                 poll=1., dry_run=False, inspect=False, max_days=None, clock=time,
                 predictor=predict, team_id=None, resubmit=True, workers=1, seed=0,
                 parallel_objective="lookahead"):
        self.api, self.game_id, self.folder = api, game_id, Path(folder)
        self.team_id = str(team_id or api.team_id or '')
        if not self.team_id:
            raise ValueError('Không đọc được ID đội từ token; cần --team.')
        self.algorithm, self.mode, self.seconds, self.reserve = algorithm, mode, seconds, reserve
        self.selection_seconds, self.roles, self.kinds = selection_seconds, roles, kinds
        self.poll, self.dry_run, self.inspect = poll, dry_run, inspect
        self.max_days, self.clock, self.predictor = max_days, clock, predictor
        # seconds/selection_seconds = None: lấy theo daySeconds/agent_selection_time_limit của config.
        self.resubmit, self.config = resubmit, {}
        # workers > 1 với tour: một phiên tìm kiếm cho cả ngày, nộp nhanh rồi lấy bài cuối.
        self.workers, self.session = workers, None
        self.seed, self.parallel_objective = seed, parallel_objective
        self.folder.mkdir(parents=True, exist_ok=True)
        self.checkpoint = self.folder/('preview_checkpoint.json' if dry_run else 'checkpoint.json')
        self.journal = json.loads(self.checkpoint.read_text(encoding='utf-8')) if self.checkpoint.exists() else {'submitted': {}}
        identity = [game_id.split(':')[0], self.team_id]
        if self.journal.get('identity', identity) != identity:
            raise ValueError('Thư mục checkpoint thuộc trận hoặc đội khác.')
        self.journal['identity'] = identity

    def save(self):
        write_json(self.checkpoint, self.journal)

    def request(self, method, endpoint, body=None, deadline=None):
        for attempt in range(3 if method=='GET' else 1):
            timeout = self.api.timeout
            if deadline is not None:
                timeout = min(timeout, deadline-self.clock.monotonic())
                if timeout <= .05:
                    raise TimeoutError('Đã hết thời gian gửi request của ngày này.')
            try:
                return self.api.request(method, endpoint, game_id=self.game_id if method=='GET' else None,
                                        body=body, timeout=timeout)
            except APIError as error:
                if method!='GET' or error.status not in (429,500,502,503,504) or attempt==2:
                    raise
            except (URLError,TimeoutError,OSError):
                if method!='GET' or attempt==2:
                    raise
            self.clock.sleep(self.poll)

    def submit_if_better(self, board, state, day, entry, candidate, deadline, mode, label):
        """Nộp `candidate` nếu simulator xác nhận tốt hơn bài đã nộp; True khi máy chủ đã nhận."""
        old_key = plan_key(board, state, entry['actions'], objective=self.parallel_objective)
        new_key = plan_key(board, state, candidate, objective=self.parallel_objective)
        if new_key is None or old_key is not None and new_key <= old_key:
            return False
        if deadline is not None and deadline-self.clock.monotonic() <= .5:
            return False
        try:
            response = self.request('POST', ENDPOINTS[mode],
                                    {'game_id': self.game_id, 'day': day, 'actions': candidate}, deadline)
        except (APIError, URLError, TimeoutError, OSError) as error:
            print(f'Ngày {day+1}: nộp lại ({label}) lỗi ({error}); máy chủ giữ bài trước.', flush=True)
            return False
        checked = simulate_day(board, state, candidate, board.day_steps[day])
        entry.update(actions=candidate, response=response)
        entry.setdefault('resubmits', []).append({'label': label, 'key': new_key})
        self.journal.update(brands=sorted(checked.state.brands), daily_sum=checked.state.daily_sum,
                            road_history=checked.state.road_history)
        write_json(self.folder/f'day_{day+1:02d}_output.txt', candidate)
        self.save()
        print(f'Ngày {day+1}: nộp lại ({label}) bài tốt hơn {old_key} → {new_key}.', flush=True)
        return True

    def check_token(self, config):
        """Dừng trước khi chọn vai trò nếu token sẽ hết hạn trước khi trận kết thúc."""
        expires = getattr(self.api, 'expires_at', None)
        if expires is None:
            return
        left = expires-time.time()
        need = sum(config.get('daySeconds') or [30.]*len(config.get('daySteps', [])))
        need += (config.get('agent_selection_time_limit') or 30.)+300
        if left <= 0:
            raise ValueError('Token đã hết hạn; lấy token mới vào HEXUDON_TOKEN trong .env.')
        if left < need:
            raise ValueError(f'Token còn {left/60:.0f} phút, trận cần khoảng {need/60:.0f} phút; '
                             'lấy token mới trước khi chạy.')
        print(f'Token còn hạn {left/3600:.1f} giờ.', flush=True)

    def safe_predict(self, board, state, budget, deadline):
        """Planner lỗi bất ngờ thì dùng Greedy với phần thời gian còn lại, không bỏ trống ngày."""
        try:
            return self.predictor(board, state, self.algorithm, budget)
        except Exception as error:
            print(f'Planner lỗi ({type(error).__name__}: {error}); dùng Greedy.', flush=True)
            left = budget if deadline is None else max(.05, deadline-self.clock.monotonic()-self.reserve)
            plan = plan_day(board, state, board.day_steps[state.day], 'greedy', min(left, 2.))
            return plan.actions, {'algorithm': 'greedy', 'fallback_from': self.algorithm,
                                  'error': f'{type(error).__name__}: {error}'[:200]}

    def wait_next_day(self, remaining, started):
        """Ngủ tới khoảng 0,3 giây trước khi hết ngày rồi hỏi mỗi 0,1 giây; không rõ hạn thì chờ poll."""
        if remaining is None:
            self.clock.sleep(self.poll)
            return
        left = started+remaining-self.clock.monotonic()
        self.clock.sleep(min(max(left-.3, .1), 5.) if left > .4 else .1)

    def day_budget(self, day, deadline):
        """Giây lập kế hoạch: thời hạn ngày theo config trừ dự phòng, không vượt hạn máy chủ."""
        budget = self.seconds
        if budget is None:
            limits = self.config.get('daySeconds') or []
            base = limits[day] if day < len(limits) and limits[day] else 30.
            budget = max(.5, base-self.reserve)
        if deadline is not None:
            budget = min(budget, max(0, deadline-self.clock.monotonic()-self.reserve))
        return budget

    def select(self, board, remote, started):
        limit = remote.get('selection_deadline_in')
        deadline = started+limit if limit is not None else None
        budget = self.selection_seconds
        if budget is None:
            budget = max(1., (self.config.get('agent_selection_time_limit') or 30.)-self.reserve)
        if deadline is not None:
            budget = min(budget, max(0, deadline-self.clock.monotonic()-self.reserve))
        if self.kinds is not None:
            kinds = self.kinds
        elif self.roles == 'all-patrol':
            kinds = [0]*len(board.starts)
        elif self.roles == 'last-supply':
            kinds = [0]*(len(board.starts)-1)+[1]
        else:
            strategy = self.algorithm if self.algorithm in ('lookahead', 'tour') else 'greedy'
            kinds, _, _ = select_types(board, budget, strategy)
        State.initial(board, kinds)
        if 0 not in kinds:
            raise ValueError('Đội hình cần ít nhất một xe tuần tra.')
        write_json(self.folder/'types.json', kinds)
        print('Vai trò đã chọn (0 tuần tra, 1 tiếp tế):', kinds, flush=True)
        if self.dry_run:
            return
        self.request('POST', '/api/game/agent-types', {'game_id': self.game_id, 'types': kinds}, deadline)
        self.journal['types'] = kinds
        self.save()

    def run(self):
        config, board, completed, last_notice = None, None, 0, None
        while True:
            started = self.clock.monotonic()
            remote = self.request('GET', '/api/game/state')
            own = remote.get('teams', {}).get(self.team_id)
            if own is None:
                raise ValueError('Đội trong token chưa tham gia trận này hoặc --team không khớp.')
            # Chỉ lưu thông tin đội mình, không lưu bài nộp hay trạng thái riêng của đội khác.
            write_json(self.folder/'server_state.json', {k:v for k,v in remote.items() if k!='teams'} | {'team': own})
            status, day = remote['status'], remote.get('day', 0)
            notice = status, day
            if notice != last_notice:
                print(f'Trạng thái: {status}; ngày API: {day}.', flush=True)
                last_notice = notice
            if 'last_seen_day' in self.journal and day < self.journal['last_seen_day']:
                raise ValueError('Trận đã lùi ngày hoặc được reset. Hãy dùng --run-dir mới; script không tự reset.')
            self.journal['last_seen_day'] = day
            for previous_day, previous in self.journal['submitted'].items():
                if int(previous_day)<day and previous['status']=='pending':
                    previous['status'] = 'advanced'
                    previous['acknowledgement'] = 'server_day_advanced_after_uncertain_response'
            if status in ('finished','ended','completed') and not self.inspect:
                result = self.request('GET', '/api/game/result')
                detail = result.get('detail', {}).get(self.team_id)
                write_json(self.folder/'result.json', detail if detail is not None else {'status': status})
                print('Trận đã kết thúc. Kết quả đội mình:', detail, flush=True)
                self.save()
                return True
            if config is None:
                try:
                    config = self.request('GET', '/api/game/config')
                except APIError as error:
                    if error.status != 409:
                        raise
                    self.clock.sleep(self.poll)
                    continue
                board = Board.from_dict(config)
                self.config = config
                digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
                if self.journal.get('config_sha256', digest) != digest:
                    raise ValueError('Cấu hình trận đã đổi; cần dùng --run-dir mới.')
                self.journal['config_sha256'] = digest
                write_json(self.folder/'config.json', config)
                self.check_token(config)
                if self.algorithm=='tour' and self.workers>1 and not self.inspect:
                    warm_up(self.workers)
            if self.inspect:
                print(f'Đã đọc cấu hình {board.width}×{board.height}, {len(board.day_steps)} ngày; không gửi bài.', flush=True)
                return
            if not own.get('types_selected') and not own.get('missed_selection'):
                if self.journal['submitted']:
                    raise ValueError('Trận đã trở lại bước chọn vai trò; dùng --run-dir mới sau khi reset thủ công.')
                if (remote.get('selection_opens_in') or 0) > 0:
                    self.clock.sleep(self.poll)
                    continue
                try:
                    self.select(board, remote, started)
                except APIError as error:
                    if error.status != 409:
                        raise
                    self.clock.sleep(self.poll)
                if self.dry_run:
                    return
                continue
            if status not in ('running','playing','in_progress'):
                self.clock.sleep(self.poll)
                continue
            remaining = remote.get('day_deadline_in')
            done = self.journal['submitted'].get(str(day))
            if done and done['status']=='accepted' and done.get('stage')!='quick':
                # Đã nộp xong ngày này: ngủ tới sát giờ chuyển ngày rồi hỏi dày (thời gian phản hồi
                # tính từ lúc ngày mới mở), không lấy lại /day và không hỏi máy chủ liên tục.
                self.wait_next_day(remaining, started)
                continue
            fetch_deadline = started+remaining if remaining is not None and remaining > 0 else None
            try:
                raw = self.request('GET', '/api/game/day', deadline=fetch_deadline)
            except (TimeoutError, URLError, OSError):
                # Sát hạn ngày hoặc mạng chập chờn: chờ rồi hỏi lại, không dừng runner giữa trận.
                self.clock.sleep(self.poll)
                continue
            if raw['day'] != day:
                # Máy chủ có thể cập nhật /day chậm hơn /state một chút.
                self.clock.sleep(.1)
                continue
            mode = detect_mode(self.mode, self.game_id, remote, raw)
            if mode=='timed' and remaining is None:
                raise ValueError('Trận tính giờ thiếu thời gian còn lại; dừng trước khi nộp.')
            deadline = started+remaining if mode=='timed' else None
            if deadline is not None and deadline-self.clock.monotonic() <= self.reserve+.05:
                if notice != getattr(self, '_deadline_notice', None):
                    print('Ngày hiện tại đã hết hoặc gần hết hạn; đang chờ máy chủ chuyển ngày. '
                          'Nếu đây là Practice tự luyện, dừng và chạy lại với --mode practice.', flush=True)
                    self._deadline_notice = notice
                self.clock.sleep(self.poll)
                continue
            key = str(day)
            entry = self.journal['submitted'].get(key)
            if entry and entry['status']=='accepted':
                self.clock.sleep(self.poll)
                continue
            if not self.dry_run and mode=='timed' and own.get('submit_count', 0)>0:
                # Có thể là bài của lần chạy trước đã được nhận nhưng mất phản hồi.
                if entry and own['submit_count'] > entry.get('before_submit_count',0):
                    entry['status'] = 'accepted'
                    entry['acknowledgement'] = 'server_submit_count'
                    self.save()
                self.clock.sleep(self.poll)
                continue
            state = authoritative_state(board, raw, own, self.journal)
            snapshot = {'day': day, 'agents': raw['agents'], 'traffics': raw['traffics'], 'brands': sorted(state.brands)}
            fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
            write_json(self.folder/f'day_{day+1:02d}_state.json', snapshot)
            if entry:
                if entry['fingerprint'] != fingerprint:
                    raise ValueError('Trạng thái đã đổi sau lần nộp chưa rõ kết quả; không gửi lại kế hoạch cũ.')
                actions = entry['actions']
            else:
                budget = self.day_budget(day, deadline)
                staged = mode=='timed' and self.resubmit and not self.dry_run and budget > 8
                actions = None
                if staged and self.algorithm=='tour' and self.workers>1:
                    # Nộp nhanh sau 2-5 giây; các tiến trình tối ưu tiếp tới hết ngân sách.
                    quick = min(5., max(2., .12*budget))
                    # Các tiến trình gửi kế hoạch mỗi 2 giây để nộp lại ngay khi có bài tốt hơn.
                    self.session = make_session(board, state, board.day_steps[day], budget, quick,
                                                self.workers, every=CHECK_EVERY, seed=self.seed,
                                                objective=self.parallel_objective)
                    actions, metrics, budget = self.session.quick(), {'algorithm': 'tour', 'anytime': True}, quick
                if actions is None:
                    # Phiên song song chưa kịp có bài nhanh: lập nhanh một bài riêng, giữ phiên để lấy bài cuối.
                    if staged:
                        # Nộp sớm một bài an toàn, phần thời gian còn lại dùng để tìm bài tốt hơn.
                        budget = min(budget, max(3., .15*budget))
                    actions, metrics = self.safe_predict(board, state, budget, deadline)
                if staged and reaches_bound(board, state, actions):
                    # Đã đạt cận trên của ngày: không thể tốt hơn, nộp một lần để thời gian phản hồi thấp.
                    staged, self.session = False, None
                checked = simulate_day(board, state, actions, board.day_steps[day])
                if not checked.valid:
                    raise ValueError(f'Output không hợp lệ; chưa nộp: {checked.errors}')
                entry = {'status': 'pending', 'actions': actions, 'fingerprint': fingerprint,
                         'algorithm': self.algorithm, 'metrics': metrics, 'attempts': 0,
                         'before_submit_count': own.get('submit_count',0),
                         'stage': 'quick' if staged else 'final'}
                self.journal['submitted'][key] = entry
                write_json(self.folder/f'day_{day+1:02d}_output.txt', actions)
                print(f'Ngày {day+1}: tạo output bằng {self.algorithm}, ngân sách {budget:.2f}s.',flush=True)
                if self.dry_run:
                    # Bản chạy thử không được đánh dấu như một lần nộp thật khi chạy lại.
                    del self.journal['submitted'][key]
                    self.save()
                    print('Dry run: đã kiểm tra output, không gửi lên máy chủ.',flush=True)
                    return
            if entry['attempts'] >= 3:
                raise RuntimeError('Ba lần gửi chưa xác nhận được. Checkpoint vẫn giữ nguyên kế hoạch; cần kiểm tra kết nối.')
            if deadline is not None and deadline-self.clock.monotonic()<=.05:
                entry['status'] = 'expired'
                self.save()
                print(f'Ngày {day+1}: đã quá hạn; không gửi output của ngày cũ.',flush=True)
                self.clock.sleep(self.poll)
                continue
            entry['attempts'] += 1
            self.save()
            try:
                response = self.request('POST', ENDPOINTS[mode],
                                        {'game_id':self.game_id,'day':day,'actions':actions},deadline)
            except APIError as error:
                if error.status==409:
                    current = self.request('GET','/api/game/state')
                    if current.get('day')!=day or current.get('status')=='finished':
                        entry['status'] = 'expired'
                        self.save()
                        continue
                if error.status not in (429,500,502,503,504):
                    raise
                print('Máy chủ tạm thời chưa xác nhận bài; sẽ kiểm tra lại trước khi gửi cùng output.',flush=True)
                self.clock.sleep(self.poll)
                continue
            except (URLError,TimeoutError,OSError):
                print('Mất phản hồi nộp bài; giữ nguyên output và kiểm tra ngày/trạng thái máy chủ.',flush=True)
                self.clock.sleep(self.poll)
                continue
            entry['status'], entry['response'] = 'accepted', response
            checked = simulate_day(board,state,actions,board.day_steps[day])
            self.journal.update(brands=sorted(checked.state.brands), daily_sum=checked.state.daily_sum,
                                road_history=checked.state.road_history)
            if mode=='practice':
                self.journal['last_seen_day'] = day+1
            self.save()
            completed += 1
            print(f'Ngày {day+1}: máy chủ đã nhận kế hoạch ({mode}).',flush=True)
            if entry.get('stage')=='quick':
                self.improve(board, state, day, entry, deadline, mode)
            if self.max_days is not None and completed >= self.max_days:
                return
            self.clock.sleep(self.poll)


    def improve(self, board, state, day, entry, deadline, mode):
        """Máy chủ giữ bài hợp lệ cuối cùng: chỉ nộp lại khi simulator xác nhận bài mới tốt hơn."""
        entry['stage'] = 'final'
        budget = self.day_budget(day, deadline)
        if budget < 2:
            self.save()
            return
        try:
            session, self.session = self.session, None
            if session is not None:
                # Nộp lại khi có bài tốt hơn: thời gian phản hồi là lúc tìm ra bài tốt nhất chứ không
                # phải cuối ngân sách. Giới hạn tần suất vì đề cảnh báo gửi quá nhiều có thể bị loại:
                # cách lần trước ít nhất MIN_GAP giây, tối đa MID_SUBMITS lần giữa ngày; bài cuối luôn
                # được nộp nếu tốt hơn. Chạm cận trên của ngày thì dừng.
                last, sent = time.time(), 0
                for mark in session.marks:
                    candidate = session.best_until(mark)
                    if candidate is None or sent >= MID_SUBMITS or time.time()-last < MIN_GAP:
                        continue
                    if self.submit_if_better(board, state, day, entry, candidate, deadline, mode, 'giữa ngày'):
                        last, sent = time.time(), sent+1
                        if reaches_bound(board, state, candidate):
                            self.save()
                            return
                better, metrics = session.final(), {'algorithm': 'tour', 'anytime': True}
                if better is None:
                    better, metrics = self.predictor(board, state, self.algorithm, max(.5, budget-2))
            else:
                better, metrics = self.predictor(board, state, self.algorithm, budget)
            old_key = plan_key(board, state, entry['actions'], objective=self.parallel_objective)
            new_key = plan_key(board, state, better, objective=self.parallel_objective)
        except Exception as error:
            entry['improve'] = {'error': f'{type(error).__name__}: {error}'[:200]}
            self.save()
            print(f'Ngày {day+1}: tối ưu thêm lỗi ({error}); giữ bài đã nộp.', flush=True)
            return
        entry['improve'] = {'old_key': old_key, 'new_key': new_key, 'budget': round(budget, 2)}
        if new_key is None or old_key is not None and new_key <= old_key:
            self.save()
            print(f'Ngày {day+1}: bài tối ưu thêm không tốt hơn; giữ bài đã nộp.', flush=True)
            return
        if deadline is not None and deadline-self.clock.monotonic() <= .5:
            self.save()
            print(f'Ngày {day+1}: hết giờ trước khi nộp lại; giữ bài đã nộp.', flush=True)
            return
        try:
            response = self.request('POST', ENDPOINTS[mode],
                                    {'game_id': self.game_id, 'day': day, 'actions': better}, deadline)
        except (APIError, URLError, TimeoutError, OSError) as error:
            entry['improve']['error'] = str(error)[:200]
            self.save()
            print(f'Ngày {day+1}: nộp lại lỗi ({error}); máy chủ vẫn giữ bài đầu.', flush=True)
            return
        checked = simulate_day(board, state, better, board.day_steps[day])
        entry.update(actions=better, metrics=metrics, response=response)
        entry['improve']['accepted'] = True
        self.journal.update(brands=sorted(checked.state.brands), daily_sum=checked.state.daily_sum,
                            road_history=checked.state.road_history)
        write_json(self.folder/f'day_{day+1:02d}_output.txt', better)
        self.save()
        print(f'Ngày {day+1}: đã nộp lại bài tốt hơn {old_key} → {new_key}.', flush=True)


def preflight(api, game_id, folder, workers, reserve):
    """Kiểm tra trước trận, chỉ gửi GET: token, kết nối, config, máy, planner. Trả về số cảnh báo."""
    warnings = 0

    def report(ok, message):
        nonlocal warnings
        warnings += not ok
        print(('OK        ' if ok else 'CẢNH BÁO  ') + message, flush=True)

    expires = getattr(api, 'expires_at', None)
    if expires is None:
        report(False, 'Không đọc được hạn token; vẫn có thể dùng nếu máy chủ chấp nhận.')
    else:
        hours = (expires-time.time())/3600
        report(hours > 3, f'Token đội {api.team_id} còn hạn {hours:.1f} giờ.')
    latencies, config = [], None
    for _ in range(3):
        started = time.perf_counter()
        try:
            remote = api.request('GET', '/api/game/state', game_id=game_id, timeout=10)
            latencies.append(time.perf_counter()-started)
        except (APIError, URLError, TimeoutError, OSError) as error:
            report(False, f'Không đọc được trạng thái trận: {error}')
            return warnings + 1
    worst = max(latencies)
    report(worst < 1.0, f'Độ trễ /state: {", ".join(f"{x:.2f}" for x in latencies)} giây.')
    own = remote.get('teams', {}).get(str(api.team_id))
    report(own is not None, f'Trạng thái trận: {remote.get("status")}, ngày API {remote.get("day")}, '
                            f'đội mình {"có" if own is not None else "KHÔNG có"} trong trận.')
    try:
        config = api.request('GET', '/api/game/config', game_id=game_id, timeout=10)
    except APIError as error:
        report(False, f'Chưa đọc được config ({error}); có thể BTC chưa mở trận.')
    if config is not None:
        board = Board.from_dict(config)
        seconds = config.get('daySeconds') or []
        report(bool(seconds), f'Bản đồ {board.width}x{board.height}, {len(board.starts)} xe, {len(board.spots)} điểm, '
                              f'{len(board.day_steps)} ngày; daySeconds {sorted(set(seconds))}, '
                              f'chọn vai trò {config.get("agent_selection_time_limit")} giây, '
                              f'{config.get("players", "?")} đội.')
        if seconds:
            report(min(seconds)-reserve >= 5, f'Ngân sách lập kế hoạch nhỏ nhất {min(seconds)-reserve:.0f} giây/ngày.')
    cores = os.cpu_count() or 1
    report(cores >= workers+2, f'{cores} nhân CPU, dùng {workers} tiến trình song song.')
    if PARAMS['native']:
        report(native.available(), f'Planner C++ {"sẵn sàng" if native.available() else "KHÔNG chạy được, dùng bản Python"} '
                                   f'({native.EXE.name}).')
    if workers > 1:
        from .tour import warm_up
        started = time.perf_counter()
        ok = warm_up(workers)
        report(ok and time.perf_counter()-started < 10,
               f'Khởi động {workers} tiến trình mất {time.perf_counter()-started:.1f} giây.')
    try:
        Path(folder).mkdir(parents=True, exist_ok=True)
        write_json(Path(folder)/'preflight.json', {'checked_at': time.time()})
        report(True, f'Ghi được thư mục checkpoint {folder}.')
    except OSError as error:
        report(False, f'Không ghi được thư mục checkpoint: {error}')
    if config is not None:
        board = Board.from_dict(config)
        state = State.initial(board, [0]*(len(board.starts)-1)+[1])
        started = time.perf_counter()
        plan = plan_day(board, state, board.day_steps[0], 'tour', 3., workers=workers)
        valid = simulate_day(board, state, plan.actions, board.day_steps[0]).valid
        report(valid and not plan.fallback and time.perf_counter()-started < 4.5,
               f'Thử lập kế hoạch ngày 1 (3 giây): {time.perf_counter()-started:.1f} giây, '
               f'hợp lệ={valid}, dự phòng={plan.fallback}.')
    print('Nhắc: cắm sạc, tắt chế độ ngủ/cập nhật Windows, không chạy việc khác trên máy trong trận.')
    print(f'Kết quả: {warnings} cảnh báo.' if warnings else 'Kết quả: sẵn sàng.')
    return warnings


def main():
    parser = argparse.ArgumentParser(description='Tự lấy trạng thái và nộp kế hoạch HEXUDON trên website BTC Việt Nam.')
    parser.add_argument('game_id',nargs='?',help='ID trận hoặc ID Practice, có thể nhập khi được hỏi')
    parser.add_argument('--game-id',dest='id_option')
    parser.add_argument('--algorithm','--predict',choices=['greedy','lookahead','rollout','tour'],default='greedy')
    parser.add_argument('--mode',choices=['auto','timed','practice'],default='auto')
    parser.add_argument('--seconds',type=float,
                        help='Trần giây lập kế hoạch mỗi ngày; mặc định daySeconds của config trừ --reserve')
    parser.add_argument('--reserve',type=float,default=4.,
                        help='Giây chừa trong mỗi thời hạn để lấy /day, kiểm tra và nộp bài')
    parser.add_argument('--no-resubmit',action='store_true',
                        help='Trận tính giờ: không nộp sớm rồi nộp lại bài tốt hơn')
    parser.add_argument('--selection-seconds',type=float,
                        help='Giây chọn vai trò; mặc định agent_selection_time_limit của config trừ --reserve')
    parser.add_argument('--roles',choices=['auto','all-patrol','last-supply'],default='auto')
    parser.add_argument('--types',nargs='+',type=int,help='Vai trò cụ thể, ưu tiên hơn --roles')
    parser.add_argument('--team',help='Mặc định lấy ID đội từ token')
    parser.add_argument('--env',default=str(ROOT/'.env'))
    parser.add_argument('--base-url',default='https://hexudon.hairbui76.id.vn')
    parser.add_argument('--run-dir',help='Thư mục mới nếu đã reset trận trên website')
    parser.add_argument('--poll',type=float,default=1.)
    parser.add_argument('--workers',type=int,
                        help='Số tiến trình chạy seed song song cho tour; mặc định số nhân CPU trừ 2')
    parser.add_argument('--seed', type=int, default=0, help='Seed đầu tiên; mỗi tiến trình dùng một seed kế tiếp')
    parser.add_argument('--parallel-objective', choices=['score', 'lookahead'], default='lookahead',
                        help='score: chọn theo U,D,Q cuối ngày; lookahead: xét thêm dự báo loại ngày mai')
    parser.add_argument('--no-native',action='store_true',help='Không dùng planner C++, chạy bản Python')
    parser.add_argument('--max-days',type=int)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--inspect',action='store_true',help='Chỉ đọc cấu hình/trạng thái, không chọn vai trò hay nộp bài')
    parser.add_argument('--preflight',action='store_true',
                        help='Kiểm tra trước trận (token, kết nối, config, CPU, planner); chỉ gửi GET, không nộp bài')
    args=parser.parse_args()
    game_id=args.game_id or args.id_option or input('ID trận đấu: ').strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]+(?::[0-9]+)?',game_id):
        parser.error('ID trận không hợp lệ; chỉ nhập ID, không nhập toàn bộ URL.')
    workers=args.workers if args.workers is not None else (
        max(1,min(14,(os.cpu_count() or 2)-2)) if args.algorithm=='tour' else 1)
    if workers < 1:
        parser.error('--workers phải ít nhất là 1.')
    if (args.seconds is not None and args.seconds<=0) or args.reserve<1 or args.poll<=0 or (
            args.selection_seconds is not None and args.selection_seconds<0):
        parser.error('Ngân sách và poll phải dương; reserve ít nhất một giây.')
    if args.max_days is not None and args.max_days<1:
        parser.error('--max-days phải ít nhất là 1.')
    api=LiveAPI(args.env,args.base_url)
    team=str(args.team or api.team_id or '')
    if ':' in game_id and game_id.rsplit(':',1)[1]!=team:
        parser.error('Hậu tố ID Practice không khớp ID đội trong token/--team.')
    folder=Path(args.run_dir) if args.run_dir else ROOT/'results/live'/f"{game_id.split(':')[0]}_{team}"
    if args.no_native:
        PARAMS['native']=False
    elif PARAMS['native'] and args.algorithm=='tour' and not native.build():
        # Thiếu g++ hoặc biên dịch lỗi: vẫn thi được bằng planner Python.
        print('CẢNH BÁO: không biên dịch được planner C++; dùng bản Python.',flush=True)
        PARAMS['native']=False
    if args.preflight:
        parser.exit(1 if preflight(api,game_id,folder,workers,args.reserve) else 0)
    runner=MatchRunner(api,game_id,folder,algorithm=args.algorithm,mode=args.mode,seconds=args.seconds,
        reserve=args.reserve,selection_seconds=args.selection_seconds,roles=args.roles,kinds=args.types,
        poll=args.poll,dry_run=args.dry_run,inspect=args.inspect,max_days=args.max_days,team_id=team,
        predictor=partial(predict,workers=workers,seed=args.seed,parallel_objective=args.parallel_objective),
        resubmit=not args.no_resubmit,workers=workers,seed=args.seed,parallel_objective=args.parallel_objective)
    try:
        with run_lock(folder):
            finished = runner.run()
        # Chỉ dọn sau khi máy chủ xác nhận hết trận và đã nhả khóa tệp trên Windows.
        if finished:
            cleanup_run(folder)
            print('Đã dọn dữ liệu chạy tạm của trận.', flush=True)
    except KeyboardInterrupt:
        print('\nĐã dừng. Chạy lại cùng lệnh để tiếp tục từ trạng thái máy chủ.')
    except (ValueError,RuntimeError,URLError,TimeoutError,OSError) as error:
        parser.exit(1,f'Lỗi: {error}\nCheckpoint: {runner.checkpoint}\n')


if __name__=='__main__':
    main()
