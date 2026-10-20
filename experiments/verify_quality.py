"""Kiểm tra lại toàn bộ input, nghiệm tối ưu và hành động của các bài nhỏ."""

import json
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hexudon.exact import solve_small
from hexudon.model import Board, State
from hexudon.simulator import simulate_day


def main():
    paths = sorted((ROOT / 'experiments/quality_results').glob('tiny_*.json'))
    assert len(paths) == 24, 'Bộ dữ liệu báo cáo cần đủ 24 bài nhỏ.'
    csv_rows = list(csv.DictReader((ROOT / 'experiments/quality_results/exact.csv').open(encoding='utf-8-sig')))
    assert len(csv_rows) == 48
    checked = 0
    for path in paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        board = Board.from_dict(data['config'])
        optimal = tuple(data['optimal_score'])
        assert solve_small(board).score == optimal, path.name
        candidates = [{'score': optimal, 'actions': data['optimal_actions']},
                      *data['heuristics'].values()]
        for candidate in candidates:
            state = State.initial(board, [0])
            assert len(candidate['actions']) == len(board.day_steps)
            for steps, actions in zip(board.day_steps, candidate['actions']):
                result = simulate_day(board, state, actions, steps)
                assert result.valid, (path.name, result.errors)
                state = result.state
            assert state.score() == tuple(candidate['score']) <= optimal
            checked += 1
        _, size, seed = path.stem.split('_')
        for strategy, candidate in data['heuristics'].items():
            row = next(r for r in csv_rows if r['size'] == size and r['seed'] == seed and r['strategy'] == strategy)
            assert tuple(int(row[c]) for c in ('u', 'd', 'q')) == tuple(candidate['score'])
            assert tuple(int(row[c]) for c in ('optimal_u', 'optimal_d', 'optimal_q')) == optimal
    print(f'Đã kiểm tra {len(paths)} nghiệm tối ưu và {checked} hành trình toàn trận; không có sai khác.')


if __name__ == '__main__':
    main()
