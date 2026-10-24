"""Ensemble ILP + heuristic trên bản đồ nhỏ (8x8, 16x16): CP-SAT có thắng tour C++ không (nhánh test).

Hai đường chạy cả trận trên cùng bản đồ, đội hình 1 xe tiếp tế trung tâm:
- A: chỉ tour C++ (K nhiệt độ, nhiều luồng);
- B: mỗi ngày chạy tour và CP-SAT (warm start từ tour) rồi chọn theo plan_key như runner
  (U, loại hôm nay, loại ngày mai ước lượng, suất).
Ghi số ngày CP-SAT chứng minh tối ưu (bỏ qua nhiên liệu) và số ngày kế hoạch CP-SAT thắng tour.

python -X utf8 experiments/ilp_small.py --maps 10 --seconds 5
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
from hexudon import tour
from hexudon.generator import generate_board
from hexudon.model import State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day
from ilp_day import plan_from_routes, solve_day, visited_spots
from suite import central_supply


def tour_plan(board, state, steps, seconds, threads):
    return plan_day(board, state, steps, "tour", seconds, seed=0, workers=threads).actions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--maps", type=int, default=10, help="Số bản đồ mỗi kích thước")
    parser.add_argument("--sizes", type=int, nargs="+", default=[8, 16])
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--cpsat-workers", type=int, default=8)
    args = parser.parse_args()
    tour.PARAMS.update(native=True, temperature=2.0)
    rows = []
    for size in args.sizes:
        for seed in range(args.maps):
            board = generate_board(size, seed)
            kinds = central_supply(board)
            only, mixed = State.initial(board, kinds), State.initial(board, kinds)
            days = []
            for steps in board.day_steps:
                only = simulate_day(board, only, tour_plan(board, only, steps, args.seconds, args.threads), steps).state
                actions = tour_plan(board, mixed, steps, args.seconds, args.threads)
                result = solve_day(board, mixed, steps, args.seconds, args.cpsat_workers,
                                   hint=visited_spots(board, mixed, actions))
                tour_key = tour.plan_key(board, mixed, actions)
                info = {"tour": tour_key, "status": None, "bound": None, "cpsat": None, "chosen": "tour"}
                if result:
                    bound, _, routes, status = result
                    info.update(status=status, bound=bound)
                    plan = plan_from_routes(board, mixed, steps, routes)
                    key = tour.plan_key(board, mixed, plan) if plan else None
                    info["cpsat"] = key
                    if key is not None and key > tour_key:
                        actions, info["chosen"] = plan, "cpsat"
                days.append(info)
                mixed = simulate_day(board, mixed, actions, steps).state
            row = {"size": size, "seed": seed, "tour_only": list(only.score()), "ensemble": list(mixed.score()),
                   "days": days}
            rows.append(row)
            print(f"{size}x{size} seed {seed}: chỉ tour {only.score()} | ensemble {mixed.score()} | ngày chọn CP-SAT "
                  f"{sum(d['chosen'] == 'cpsat' for d in days)}/{len(days)} | CP-SAT tối ưu "
                  f"{sum(d['status'] == 'OPTIMAL' for d in days)}/{len(days)}", flush=True)
    (ROOT / "results/ilp_small.json").write_text(json.dumps(rows, indent=1, default=list), encoding="utf8")
    for size in args.sizes:
        part = [r for r in rows if r["size"] == size]
        days = [d for r in part for d in r["days"]]
        print(f"{size}x{size}: ensemble hơn/bằng/kém chỉ tour "
              f"{sum(r['ensemble'] > r['tour_only'] for r in part)}/{sum(r['ensemble'] == r['tour_only'] for r in part)}/"
              f"{sum(r['ensemble'] < r['tour_only'] for r in part)}; ngày CP-SAT thắng tour "
              f"{sum(d['chosen'] == 'cpsat' for d in days)}/{len(days)}; CP-SAT chứng minh tối ưu "
              f"{sum(d['status'] == 'OPTIMAL' for d in days)}/{len(days)}")


if __name__ == "__main__":
    main()
