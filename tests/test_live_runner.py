"""Kiểm tra tự chạy trận, đường thực tế, hạn giờ và khôi phục sau mất phản hồi."""

from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from hexudon.generator import to_dict
from hexudon.live import MatchRunner, APIError, detect_mode, predict, cleanup_run
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day

TEMP_ROOT=Path(__file__).resolve().parents[1]/'scratch'
TEMP_ROOT.mkdir(exist_ok=True)


class Clock:
    def __init__(self):self.now=0.
    def monotonic(self):return self.now
    def sleep(self,seconds):self.now+=seconds


class FakeAPI:
    team_id='62'
    timeout=5.
    def __init__(self,clock,mode='practice',failure=None):
        self.clock,self.mode,self.failure=clock,mode,failure
        self.board=Board([[0,1,0],[0,0,0],[0,0,0]],
                         [dict(pos=4,brand=0,stocks=3),dict(pos=6,brand=1,stocks=3)],
                         [0,2,8],[6,6],12)
        self.state=State.initial(self.board,[0]*3)
        self.selected=False
        self.pending={}
        self.calls=[]
        self.failed=False

    def advance(self):
        while self.state.day<2 and self.clock.now >= 30*(self.state.day+1):
            actions=self.pending.get(self.state.day,[[-6]]*3)
            checked=simulate_day(self.board,self.state,actions,6)
            assert checked.valid,checked.errors
            self.state=checked.state

    def request(self,method,endpoint,game_id=None,body=None,timeout=None):
        self.calls.append((method,endpoint,deepcopy(body)))
        if self.mode=='timed':self.advance()
        day=self.state.day
        if method=='GET' and endpoint=='/api/game/state':
            return dict(status='finished' if day==2 else ('running' if self.selected else 'selection'),day=day,
                day_deadline_in=30*(day+1)-self.clock.now if self.mode=='timed' and day<2 and self.selected else None,
                selection_deadline_in=20. if self.mode=='timed' and not self.selected else None,
                selection_opens_in=0,
                teams={'62':dict(types_selected=self.selected,distinct_types=sorted(self.state.brands),
                    cumulative_daily_types=self.state.daily_sum,total_servings=self.state.portions,
                    submit_count=int(day in self.pending))})
        if endpoint=='/api/game/config':return to_dict(self.board)
        if endpoint=='/api/game/result':
            return {'detail':{'62':{'score':self.state.score()}}}
        if endpoint=='/api/game/agent-types':
            self.selected=True
            self.state=State.initial(self.board,body['types'])
            return {'ok':True}
        if endpoint=='/api/game/day':
            # Xe đối thủ có thể làm đường ngày 2 tắc; không lấy giao thông dự đoán một đội.
            self.state.traffic={1:2 if day==1 else 0}
            return dict(day=day,agents=[dict(kind=a.kind,pos=a.pos,fuel=a.fuel) for a in self.state.agents],
                        traffics=[dict(pos=1,status=self.state.traffic[1])])
        expected='/api/game/practice/actions' if self.mode=='practice' else '/api/game/actions'
        if method=='POST' and endpoint==expected:
            assert body['day']==day
            if self.failure=='before' and not self.failed:
                self.failed=True
                raise TimeoutError('Mạng mất trước khi máy chủ nhận bài.')
            self.pending[day]=body['actions']
            checked=simulate_day(self.board,self.state,body['actions'],6)
            assert checked.valid,checked.errors
            if self.mode=='practice':self.state=checked.state
            if self.failure=='after' and not self.failed:
                self.failed=True
                raise TimeoutError('Máy chủ nhận bài nhưng phản hồi bị mất.')
            return {'ok':True}
        raise AssertionError((method,endpoint))


class LiveRunnerTests(unittest.TestCase):
    def test_server_in_progress_status_submits_until_finished(self):
        clock = Clock()
        api = FakeAPI(clock)
        original = api.request
        def request(method, endpoint, **kwargs):
            response = original(method, endpoint, **kwargs)
            if endpoint == '/api/game/state' and response['status'] == 'running':
                response['status'] = 'in_progress'
            return response
        api.request = request
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory, contextlib.redirect_stdout(io.StringIO()):
            runner = MatchRunner(api, 'test', directory, clock=clock,
                                 roles='all-patrol', seconds=.01)
            self.assertTrue(runner.run())
        self.assertEqual(api.state.day, 2)
        self.assertEqual(len(api.pending), 2)

    def test_fresh_selection_day_minus_one_completes_match(self):
        clock = Clock()
        api = FakeAPI(clock)
        original = api.request
        def request(method, endpoint, **kwargs):
            response = original(method, endpoint, **kwargs)
            if endpoint == '/api/game/state' and not api.selected:
                response.update(status='selecting_agents', day=-1)
            return response
        api.request = request
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory, contextlib.redirect_stdout(io.StringIO()):
            runner = MatchRunner(api, 'test', directory, clock=clock,
                                 roles='all-patrol', seconds=.01)
            self.assertTrue(runner.run())
        self.assertTrue(api.selected)
        self.assertEqual(api.state.day, 2)

    def test_existing_checkpoint_still_rejects_reset(self):
        clock = Clock()
        api = FakeAPI(clock)
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory, contextlib.redirect_stdout(io.StringIO()):
            runner = MatchRunner(api, 'test', directory, clock=clock)
            runner.journal['last_seen_day'] = 2
            with self.assertRaisesRegex(ValueError, 'lùi ngày'):
                runner.run()

    def run_case(self,mode='practice',failure=None,**options):
        clock=Clock()
        api=FakeAPI(clock,mode,failure)
        seen=[]
        def planner(board,state,algorithm,seconds):
            seen.append((state.day,dict(state.traffic),[a.fuel for a in state.agents],seconds))
            return plan_day(board,state,6,'greedy',.01).actions,{'algorithm':algorithm}
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory,contextlib.redirect_stdout(io.StringIO()):
            runner=MatchRunner(api,'test-game',directory,roles='all-patrol',clock=clock,
                               predictor=planner,**options)
            runner.run()
            journal=json.loads((Path(directory)/'checkpoint.json').read_text(encoding='utf8')) if (Path(directory)/'checkpoint.json').exists() else {}
            return api,seen,journal

    def test_practice_fetches_real_roads_and_fuel_each_day(self):
        api,seen,journal=self.run_case()
        self.assertEqual(api.state.day,2)
        self.assertEqual([s[1][1] for s in seen],[0,2])
        self.assertNotEqual(seen[1][2],[12]*3)
        self.assertEqual(set(api.pending),{0,1})
        self.assertTrue(all('reset' not in path for method,path,body in api.calls))
        self.assertEqual(journal['submitted']['1']['status'],'accepted')

    def test_timed_uses_normal_endpoint_once_per_day(self):
        api,seen,_=self.run_case(mode='timed')
        posts=[c for c in api.calls if c[0]=='POST' and c[1]=='/api/game/actions']
        self.assertEqual([c[2]['day'] for c in posts],[0,1])
        self.assertEqual(len(seen),2)
        self.assertTrue(all(s[3]<=20 for s in seen))

    def test_practice_lost_response_does_not_resubmit_previous_day(self):
        api,seen,journal=self.run_case(failure='after')
        posts=[c for c in api.calls if c[1]=='/api/game/practice/actions']
        self.assertEqual([c[2]['day'] for c in posts],[0,1])
        self.assertEqual(len(seen),2)
        self.assertEqual(journal['submitted']['0']['status'],'advanced')

    def test_timed_lost_response_uses_server_submission_counter(self):
        api,seen,journal=self.run_case(mode='timed',failure='after')
        self.assertEqual(len([c for c in api.calls if c[1]=='/api/game/actions']),2)
        self.assertEqual(journal['submitted']['0']['acknowledgement'],'server_submit_count')

    def test_retry_preserves_exact_output(self):
        api,seen,_=self.run_case(failure='before')
        posts=[c[2] for c in api.calls if c[1]=='/api/game/practice/actions']
        self.assertEqual(posts[0],posts[1])
        self.assertEqual(len(seen),2)

    def test_dry_run_never_submits_or_changes_roles(self):
        api,_,_=self.run_case(dry_run=True)
        self.assertFalse(any(method=='POST' for method,path,body in api.calls))

    def test_dry_run_active_day_generates_output_without_submission(self):
        clock=Clock()
        api=FakeAPI(clock,'timed')
        api.selected=True
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory,contextlib.redirect_stdout(io.StringIO()):
            MatchRunner(api,'test',directory,dry_run=True,clock=clock,seconds=.01).run()
            self.assertTrue((Path(directory)/'day_01_output.txt').exists())
            self.assertFalse((Path(directory)/'checkpoint.json').exists())
        self.assertFalse(any(c[0]=='POST' for c in api.calls))

    def test_invalid_plan_is_stopped_before_post(self):
        clock=Clock()
        api=FakeAPI(clock)
        api.selected=True
        def invalid(*args):return [[0],[0],[0]],{}
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'Output không hợp lệ'):
                MatchRunner(api,'test',directory,clock=clock,predictor=invalid).run()
        self.assertFalse(any(c[0]=='POST' for c in api.calls))

    def test_planner_overrun_never_posts_an_expired_day(self):
        clock=Clock()
        api=FakeAPI(clock,'timed')
        api.selected=True
        def slow(*args):
            clock.now+=31
            return [[-6]]*3,{}
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory,contextlib.redirect_stdout(io.StringIO()):
            MatchRunner(api,'test',directory,clock=clock,predictor=slow).run()
        self.assertFalse(any(c[0]=='POST' for c in api.calls))

    def test_day_transition_conflict_refreshes_state(self):
        clock=Clock()
        class TransitionAPI(FakeAPI):
            def request(self,method,endpoint,game_id=None,body=None,timeout=None):
                if method=='POST' and endpoint=='/api/game/actions' and body['day']==0:
                    self.clock.now=31
                    self.advance()
                    raise APIError(409,'Ngày đã chuyển.')
                return super().request(method,endpoint,game_id,body,timeout)
        api=TransitionAPI(clock,'timed')
        api.selected=True
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory,contextlib.redirect_stdout(io.StringIO()):
            MatchRunner(api,'test',directory,clock=clock,seconds=.01).run()
        self.assertEqual(set(api.pending),{1})

    def test_resume_does_not_replace_accepted_plan(self):
        clock=Clock()
        api=FakeAPI(clock,'timed')
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory,contextlib.redirect_stdout(io.StringIO()):
            first=MatchRunner(api,'test',directory,mode='timed',roles='all-patrol',clock=clock,max_days=1,seconds=.01)
            first.run()
            second=MatchRunner(api,'test',directory,mode='timed',clock=clock,seconds=.01)
            second.run()
        self.assertEqual([c[2]['day'] for c in api.calls if c[1]=='/api/game/actions'],[0,1])

    def test_algorithm_switch_generates_valid_plans(self):
        clock=Clock()
        api=FakeAPI(clock)
        for algorithm in ('greedy','lookahead','rollout'):
            actions,metrics=predict(api.board,api.state,algorithm,.1)
            checked=simulate_day(api.board,api.state,actions,6)
            self.assertTrue(checked.valid,checked.errors)
            self.assertEqual(metrics['algorithm'],algorithm)

    def test_ambiguous_mode_requires_override(self):
        with self.assertRaises(ValueError):detect_mode('auto','test',{'status':'unknown'})
        self.assertEqual(detect_mode('practice','test',{}),'practice')

    def test_practice_zero_clock_requires_day_confirmation(self):
        remote = {'status': 'in_progress', 'day_deadline_in': 0.0}
        self.assertEqual(detect_mode('auto', 'test', remote, {'endsAt': None}), 'practice')
        with self.assertRaisesRegex(ValueError, '--mode practice'):
            detect_mode('auto', 'test', remote, {'endsAt': 123})
        self.assertEqual(detect_mode('timed', 'test', remote, {'endsAt': 123}), 'timed')


class CleanupTests(unittest.TestCase):
    def test_cleanup_removes_empty_run_folder(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            folder = Path(temporary)/'run'
            folder.mkdir()
            for name in ('checkpoint.json', 'runner.lock', 'day_01_output.txt', 'day_01_state.json'):
                (folder/name).write_text('{}')
            cleanup_run(folder)
            self.assertFalse(folder.exists())

    def test_cleanup_keeps_unrelated_data(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temporary:
            folder = Path(temporary)
            (folder/'notes.txt').write_text('keep')
            (folder/'checkpoint.json').write_text('{}')
            cleanup_run(folder)
            self.assertEqual((folder/'notes.txt').read_text(), 'keep')
            self.assertFalse((folder/'checkpoint.json').exists())


if __name__=='__main__':unittest.main()
