"""So planner cũ và planner tuyến cả đội trên config BTC đã tải, mô phỏng một đội.

Mỗi trường hợp chạy với cùng danh sách đội hình (toàn tuần tra, từng xe tiếp tế, hai xe
tiếp tế gần trung tâm) cho cả hai planner; điểm tốt nhất của mỗi planner được báo riêng.
Đây là điểm offline, giao thông tương lai chỉ do đội mình tạo ra.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day

CASES = ["Q01", "Q03", "Q04", "Q06", "Q07", "Q08", "Q09", "Q10",
         "generated_8_2026", "generated_16_2026", "generated_32_2026"]


def run_match(job):
    case, kinds, strategy, seconds, alpha = job[:5]
    beta = job[5] if len(job) > 5 else 0.0
    config = json.loads((ROOT / "output/team_selection" / case / "config.json").read_text(encoding="utf-8"))
    board = Board.from_dict(config)
    state = State.initial(board, kinds)
    started, fallbacks = time.perf_counter(), 0
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, strategy, seconds, alpha, beta)
        fallbacks += plan.fallback
        checked = simulate_day(board, state, plan.actions, steps)
        if not checked.valid:
            raise ValueError(f"{case} {kinds} {strategy}: {checked.errors}")
        state = checked.state
    return {"case": case, "types": kinds, "strategy": strategy, "alpha": alpha, "beta": beta,
            "seconds": seconds, "score": list(state.score()), "fallbacks": fallbacks,
            "elapsed": time.perf_counter() - started}


def type_options(board):
    count = len(board.starts)
    options = [[0] * count]
    for i in range(count):
        options.append([int(j == i) for j in range(count)])
    if count >= 4:
        spots = [s["pos"] for s in board.spots]
        order = sorted(range(count), key=lambda i: sum(board.distance(board.starts[i], p) for p in spots))
        options.append([int(j in order[:2]) for j in range(count)])
    return options


def upper_bounds(board, kinds):
    brands = len({s["brand"] for s in board.spots})
    patrols = kinds.count(0)
    per_day = sum(min(s["stocks"], patrols) for s in board.spots)
    return brands, brands * len(board.day_steps), per_day * len(board.day_steps)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", default=CASES)
    parser.add_argument("--strategies", nargs="+", default=["greedy", "tour"])
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--workers", type=int, default=14)
    parser.add_argument("--output", default=str(ROOT / "results/benchmark_tour.json"))
    args = parser.parse_args()
    jobs = []
    for case in args.cases:
        config = json.loads((ROOT / "output/team_selection" / case / "config.json").read_text(encoding="utf-8"))
        board = Board.from_dict(config)
        for kinds in type_options(board):
            for strategy in args.strategies:
                jobs.append((case, kinds, strategy, args.seconds, args.alpha))
    with ProcessPoolExecutor(args.workers) as pool:
        results = list(pool.map(run_match, jobs))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"{'case':20} " + " ".join(f"{s:>30}" for s in args.strategies))
    for case in args.cases:
        row = []
        for strategy in args.strategies:
            mine = [r for r in results if r["case"] == case and r["strategy"] == strategy]
            best = max(mine, key=lambda r: tuple(r["score"]))
            allp = next(r for r in mine if 1 not in r["types"])
            row.append(f"{str(tuple(best['score'])):>16}{str(best['types']):>14}")
            row[-1] += f" allP{tuple(allp['score'])}"
        print(f"{case:20} " + " | ".join(row))


if __name__ == "__main__":
    main()
