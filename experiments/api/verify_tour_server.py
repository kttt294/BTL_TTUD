"""Nộp tour vào Practice riêng, lưu lịch sử trước reset và đối chiếu replay BTC."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from hexudon.live import MatchRunner, predict
from hexudon.live_api import LiveAPI, APIError
from hexudon.live_storage import cleanup_run, run_lock, write_json
from compare_api import compare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', nargs='+', default=['Q01','Q03','Q04','Q06','Q07','Q08','Q09','Q10'])
    parser.add_argument('--seconds', type=float, default=5.)
    args = parser.parse_args()
    api = LiveAPI(ROOT/'.env')
    if api.team_id != '62':
        raise ValueError('Phép đo này chỉ được phép reset Practice của đội 62.')
    registry = json.loads((ROOT/'docs/api/sample_games.json').read_text(encoding='utf8'))
    pipeline = json.loads((ROOT/'experiments/data/tour_results/pipeline.json').read_text(encoding='utf8'))
    folder = ROOT/'experiments/data/tour_api_evidence'
    folder.mkdir(exist_ok=True)
    summaries = json.loads((folder/'summary.json').read_text(encoding='utf8')) if (folder/'summary.json').exists() else []

    def request(method, endpoint, **kwargs):
        for attempt in range(3):
            try:
                value = api.request(method, endpoint, **kwargs)
                time.sleep(.4)
                return value
            except APIError as error:
                if method != 'GET' or error.status != 429 or attempt == 2:
                    raise
                time.sleep(1.5)

    for case in args.cases:
        if any(r['case'] == case for r in summaries):
            print(case, 'đã có kết quả, không reset lại.', flush=True)
            continue
        game = registry[case]+':62'
        config = request('GET','/api/game/config',game_id=game)
        if config['players'] != 1:
            raise ValueError('Chỉ hỗ trợ reset Practice riêng một đội.')
        before = folder/(case+'_before.json')
        if not before.exists():
            backup = {'config': config}
            for endpoint in ('result','state','actions','replay'):
                backup[endpoint] = request('GET','/api/game/'+endpoint,game_id=game)
            write_json(before, backup)
            request('POST','/api/game/practice/reset',body={'game_id':game})
        metrics = []
        def planner(board, state, algorithm, seconds):
            started = time.perf_counter()
            actions, detail = predict(board, state, algorithm, seconds)
            metrics.append({'day': state.day, 'seconds': time.perf_counter()-started, **detail})
            return actions, detail
        kinds = pipeline[case]['new']['types']
        run_folder = ROOT/'results/tour_verification'/case
        runner = MatchRunner(api, game, run_folder, algorithm='tour', mode='practice',
                             seconds=args.seconds, kinds=kinds, predictor=planner)
        print('Bắt đầu', case, 'đội hình', kinds, flush=True)
        with run_lock(run_folder):
            finished = runner.run()
        if not finished:
            raise ValueError('Trận chưa kết thúc, giữ checkpoint để tiếp tục.')
        result = request('GET','/api/game/result',game_id=game)['detail']['62']
        replay = request('GET','/api/game/replay',game_id=game)
        history = request('GET','/api/game/actions',game_id=game)
        for name, value in [('config',config),('replay',replay),('actions',history),('metrics',metrics)]:
            write_json(folder/(case+'_'+name+'.json'), value)
        comparison = compare(config,replay,history)
        write_json(folder/(case+'_comparison.json'),comparison)
        score = [result[k] for k in ('distinct_types','cumulative_daily_types','total_servings')]
        plans = {r['day']:r['plan'] for r in history['actions'] if str(r['team_id'])=='62'}
        brands = len({s['brand'] for s in config['spots']})
        row = {'case':case,'server_score':score,'types':kinds,'seconds_per_day':args.seconds,
               'accepted_days':len(plans),'daily_types':[r['types'] for r in comparison['days']],
               'daily_servings':[r['servings'] for r in comparison['days']],
               'checked_frames':comparison['checked_frames'],'checked_values':comparison['checked_values'],
               'mismatch_count':comparison['mismatch_count'],'replayed_score':comparison['final_score'],
               'fallback_days':sum(bool(r.get('fallback')) for r in metrics),
               'max_planning_seconds':max((r['seconds'] for r in metrics),default=0),
               'ud_bound':[brands, brands*len(config['daySteps'])],
               'time_utc':datetime.now(timezone.utc).isoformat(),
               'roles_source':'đội hình từ pipeline offline; không chọn lại trong lần nộp này'}
        summaries.append(row)
        write_json(folder/'summary.json',summaries)
        cleanup_run(run_folder)
        print(case, 'BTC',score,'sai khác',row['mismatch_count'],flush=True)
        if row['mismatch_count'] or score!=row['replayed_score']:
            raise ValueError('Replay không khớp, cần điều tra trước khi báo cáo.')


if __name__ == '__main__':
    main()
