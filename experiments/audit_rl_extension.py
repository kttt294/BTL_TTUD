"""Chấm lại 36 hành trình đã lưu và kiểm tra tính chất giữ kế hoạch của bộ chọn."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hexudon.model import Board, State
from hexudon.simulator import simulate_day


def main():
    folder = ROOT / 'experiments/rl_extension_results'
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    assert len(summary) == 36
    checked_days = 0
    for item in summary:
        question, variant = item['question'], item['variant']
        row = json.loads((folder / f'{question}_{variant}.json').read_text(encoding='utf-8'))
        source = ROOT / f'experiments/rl_branch_evidence/{question}_config.json'
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row['config_sha256']
        board = Board.from_dict(json.loads(source.read_text(encoding='utf-8'))['response'])
        state = State.initial(board, [0] * len(board.starts))
        assert len(row['actions']) == len(board.day_steps) == 10
        prediction = tuple(row['initial_greedy_score'])
        for actions, day in zip(row['actions'], row['days']):
            result = simulate_day(board, state, actions, board.day_steps[state.day])
            assert result.valid, result.errors
            state = result.state
            assert list(state.score()) == day['score_after_day']
            if variant != 'rl_daily':
                assert tuple(day['predicted_score']) >= prediction
                prediction = tuple(day['predicted_score'])
            checked_days += 1
        assert list(state.score()) == row['score'] == item['score']
        if variant != 'rl_daily':
            assert state.score() == prediction >= tuple(row['initial_greedy_score'])
    counts = {}
    for baseline in ('greedy', 'rollout_no_rl', 'rl_daily'):
        by_key = {(r['question'], r['variant']): r for r in summary}
        pairs = [(tuple(by_key[q, 'rl_rollout']['score']), tuple(by_key[q, baseline]['score']))
                 for q in sorted({r['question'] for r in summary})]
        counts[baseline] = {'wins': sum(a > b for a, b in pairs), 'ties': sum(a == b for a, b in pairs),
                            'losses': sum(a < b for a, b in pairs)}
    audit = {'matches': len(summary), 'verified_days': checked_days, 'invalid_plans': 0,
             'replay_score_mismatches': 0, 'incumbent_monotonicity_violations': 0,
             'max_decision_seconds': max(r['max_decision_seconds'] for r in summary),
             'rl_rollout_selected_days': sum(r['selected_rl_days'] for r in summary if r['variant'] == 'rl_rollout'),
             'comparison_rl_rollout': counts}
    (folder / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
