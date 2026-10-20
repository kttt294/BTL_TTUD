"""Nộp lại kế hoạch đã lưu vào Practice riêng và đối chiếu replay với simulator TTUD."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hexudon.api import CompetitionAPI
from hexudon.model import Board, State
from hexudon.simulator import simulate_day
from compare_api import compare


def main():
    parser = argparse.ArgumentParser(description='Có đặt lại và nộp Practice riêng; không dùng để chỉ xem số liệu.')
    parser.add_argument('--questions', nargs='+', default=['Q04', 'Q06'])
    args = parser.parse_args()
    registry = json.loads((ROOT / 'docs/api/sample_games.json').read_text(encoding='utf-8'))
    folder = ROOT / 'experiments/rl_extension_api_evidence'
    api = CompetitionAPI(evidence_dir=folder)
    summaries = []
    for question in args.questions:
        result = json.loads((ROOT / f'experiments/rl_extension_results/{question}_rl_rollout.json').read_text(encoding='utf-8'))
        game = registry[question] + ':62'
        config = api.get('/api/game/config', game, question + '_config')
        assert config['players'] == 1
        original = json.loads((ROOT / f'experiments/rl_branch_evidence/{question}_config.json').read_text(encoding='utf-8'))['response']
        assert config == original, 'Cấu hình máy chủ đã thay đổi; không dùng kế hoạch cũ.'
        for endpoint in ('actions', 'replay', 'state', 'result'):
            api.get('/api/game/' + endpoint, game, question + '_before_' + endpoint)
        api.request('POST', '/api/game/practice/reset', body={'game_id': game}, label=question + '_reset')
        kinds = [0] * len(config['agents'])
        api.request('POST', '/api/game/agent-types', body={'game_id': game, 'types': kinds}, label=question + '_types')
        board = Board.from_dict(config)
        state = State.initial(board, kinds)
        for day, actions in enumerate(result['actions']):
            raw = api.get('/api/game/day', game, f'{question}_day_{day:02d}')
            assert raw['day'] == day
            assert [(a['pos'], a['fuel'], a['kind']) for a in raw['agents']] == [(a.pos, a.fuel, a.kind) for a in state.agents]
            assert all(t['status'] == state.traffic.get(t['pos'], 0) for t in raw['traffics'])
            checked = simulate_day(board, state, actions, board.day_steps[day])
            assert checked.valid, checked.errors
            api.practice_actions(game, day, actions, f'{question}_submit_{day:02d}')
            state = checked.state
        replay = api.get('/api/game/replay', game, question + '_replay')
        history = api.get('/api/game/actions', game, question + '_actions')
        server = api.get('/api/game/result', game, question + '_result')['detail']['62']
        score = [server['distinct_types'], server['cumulative_daily_types'], server['total_servings']]
        assert score == result['score'] == list(state.score())
        actual = {a['day']: a['plan'] for a in history['actions'] if str(a['team_id']) == '62'}
        assert len(actual) == len(result['actions'])
        assert all(actual[day] == actions for day, actions in enumerate(result['actions']))
        comparison = compare(config, replay, history)
        assert comparison['mismatch_count'] == 0
        row = {'question': question, 'variant': 'rl_rollout', 'game_id': game,
               'server_score': score, 'accepted_days': len(actual),
               'checked_frames': comparison['checked_frames'], 'checked_values': comparison['checked_values'],
               'mismatches': comparison['mismatch_count'],
               'selected_rl_days': result['selected_rl_days']}
        summaries.append(row)
        (folder / 'summary.json').write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding='utf-8')
        print(question, score, 'accepted days', len(actual), 'mismatches', comparison['mismatch_count'], flush=True)


if __name__ == '__main__':
    main()
