"""Đo nghiệm tối ưu bài nhỏ và độ nhạy Greedy/Lookahead theo thời gian."""

import argparse
import csv
import json
import platform
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hexudon.exact import solve_small
from hexudon.generator import generate_board, to_dict
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day


def tiny_board(seed, size):
    rng = random.Random(seed)
    board = Board([[0 if rng.random() < .75 else 2 for _ in range(size)]
                   for _ in range(size)], [], [], [6, 6], 5 + seed % 3)
    # Vị trí đầu và điểm bán luôn được đặt trên đồng bằng, không trùng nhau.
    positions = rng.sample(range(size * size), min(5, size * size))
    for pos in positions:
        board.cells[pos // size][pos % size] = 0
    board.starts = positions[:1]
    board.spots = [{'pos': p, 'brand': i % 3, 'stocks': 1}
                   for i, p in enumerate(positions[1:])]
    return board


def play(board, strategy, budget, kinds):
    state = State.initial(board, kinds)
    plans, searches, elapsed, fallbacks = [], 0, 0, 0
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, strategy, budget)
        checked = simulate_day(board, state, plan.actions, steps)
        assert checked.valid, checked.errors
        state = checked.state
        plans.append(plan.actions)
        searches += plan.searches
        elapsed += plan.elapsed
        fallbacks += plan.fallback
    return state.score(), plans, searches, elapsed, fallbacks


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['exact', 'budgets'], required=True)
    parser.add_argument('--cases', type=int, default=10)
    args = parser.parse_args()
    folder = ROOT / 'experiments/quality_results'
    folder.mkdir(exist_ok=True)
    rows = []
    if args.mode == 'exact':
        for size in (2, 3):
            for case in range(args.cases):
                seed = 3100 + case
                board = tiny_board(seed, size)
                exact = solve_small(board)
                state = State.initial(board, [0])
                for steps, commands in zip(board.day_steps, exact.actions):
                    replay = simulate_day(board, state, commands, steps)
                    assert replay.valid, replay.errors
                    state = replay.state
                assert state.score() == exact.score
                entry = {'config': to_dict(board), 'optimal_score': exact.score,
                         'optimal_actions': exact.actions, 'states': exact.states,
                         'seconds': exact.seconds, 'heuristics': {}}
                for strategy in ('greedy', 'lookahead'):
                    score, plans, searches, elapsed, fallback = play(board, strategy, .25, [0])
                    assert score <= exact.score
                    entry['heuristics'][strategy] = {'score': score, 'actions': plans}
                    rows.append(dict(size=size, seed=seed, strategy=strategy,
                                     optimal_u=exact.score[0], optimal_d=exact.score[1], optimal_q=exact.score[2],
                                     u=score[0], d=score[1], q=score[2], optimal=int(score == exact.score),
                                     dp_states=exact.states, dp_seconds=exact.seconds))
                (folder / f'tiny_{size}_{seed}.json').write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding='utf-8')
                print(f'Bài nhỏ {size}, seed {seed}: tối ưu {exact.score}', flush=True)
    else:
        for size in (8, 16, 32):
            for case in range(args.cases):
                seed = 2026 + case
                board = generate_board(size, seed, steps=80, fuel=40)
                for budget in (.05, .25, 1., 3.):
                    # Đảo thứ tự chạy giữa các input để giảm thiên lệch thứ tự cố định.
                    strategies = ('greedy', 'lookahead') if case % 2 == 0 else ('lookahead', 'greedy')
                    for strategy in strategies:
                        score, plans, searches, elapsed, fallback = play(board, strategy, budget, [0, 0, 0, 1])
                        rows.append(dict(size=size, seed=seed, budget=budget, strategy=strategy,
                                         u=score[0], d=score[1], q=score[2], searches=searches,
                                         seconds=elapsed, fallback=fallback))
                        # Lưu ngay sau mỗi trận để không mất số liệu nếu tiến trình bị gián đoạn.
                        write_csv(folder / 'budgets.csv', rows)
                print(f'Ngân sách: xong {size}×{size}, seed {seed}', flush=True)
    write_csv(folder / f'{args.mode}.csv', rows)
    (folder / f'{args.mode}_metadata.json').write_text(json.dumps({
        'python': platform.python_version(), 'platform': platform.platform(),
        'processor': platform.processor(), 'cases_per_size': args.cases,
        'created_local': time.strftime('%Y-%m-%d %H:%M:%S'),
        'note': 'Một đội; ngày sau kế thừa nhiên liệu và giao thông của chính chiến lược.'},
        ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
