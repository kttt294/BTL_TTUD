"""Chạy các phép đo độc lập cho tìm đường, toàn trận và bộ kiểm tra."""

import argparse
import csv
import json
import platform
from pathlib import Path
import random
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hexudon.generator import generate_board
from hexudon.model import State
from hexudon.planner import plan_day
from hexudon.search import ALGORITHMS, find_path
from hexudon.simulator import simulate_day


def save_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=10)
    parser.add_argument("--sizes", nargs="+", type=int, default=[8, 16, 32])
    parser.add_argument("--seconds", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", default="experiments/results")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    path_rows, match_rows, validation_rows = [], [], []
    for size in args.sizes:
        for case in range(args.games):
            seed = args.seed + case
            board = generate_board(size, seed, steps=80, fuel=40)
            rng = random.Random(seed + 10000)
            walkable = [p for p in range(size * size) if board.terrain(p) != 3]
            traffic = {p: rng.randrange(3) for p in walkable if board.terrain(p) == 1}
            for query in range(3):
                start, goal = rng.sample(walkable, 2)
                for algorithm in ALGORITHMS:
                    begin = time.perf_counter()
                    route = find_path(board, start, goal, traffic, 80, 40, algorithm, begin + args.seconds)
                    path_rows.append({"size": size, "seed": seed, "query": query,
                                      "algorithm": algorithm, "found": int(route.found),
                                      "cutoff": int(route.cutoff), "steps": route.steps if route.found else "",
                                      "fuel": route.fuel if route.found else "",
                                      "hops": len(route.actions) if route.found else "",
                                      "expanded": route.expanded, "seconds": time.perf_counter() - begin})
            for strategy in ("greedy", "lookahead"):
                state = State.initial(board, [0, 0, 0, 1])
                planning_seconds, fallbacks = 0.0, 0
                valid = True
                for day, steps in enumerate(board.day_steps, 1):
                    plan = plan_day(board, state, steps, strategy, args.seconds)
                    planning_seconds += plan.elapsed
                    fallbacks += int(plan.fallback)
                    begin = time.perf_counter()
                    checked = simulate_day(board, state, plan.actions, steps)
                    elapsed = time.perf_counter() - begin
                    validation_rows.append({"size": size, "seed": seed, "strategy": strategy,
                                            "day": day, "agents": 4, "steps": steps,
                                            "valid": int(checked.valid), "seconds": elapsed})
                    if not checked.valid:
                        valid = False
                        break
                    state = checked.state
                match_rows.append({"size": size, "seed": seed, "strategy": strategy,
                                   "unique": len(state.brands), "daily": state.daily_sum,
                                   "portions": state.portions, "planning_seconds": planning_seconds,
                                   "valid": int(valid), "fallbacks": fallbacks})
            print(f"Đã đo bản đồ {size}×{size}, seed {seed}.", flush=True)
    save_csv(output / "pathfinding.csv", path_rows)
    save_csv(output / "matches.csv", match_rows)
    save_csv(output / "validation.csv", validation_rows)
    stress_rows = []
    for agents in (4, 8):
        board = generate_board(32, args.seed)
        board.starts = [board.starts[i % 4] for i in range(agents)]
        state = State.initial(board, [0] * (agents - 1) + [1])
        for steps in (80, 255, 1000):
            timings = []
            for _ in range(30):
                begin = time.perf_counter()
                checked = simulate_day(board, state, [[-steps] for _ in range(agents)], steps)
                timings.append(time.perf_counter() - begin)
                if not checked.valid:
                    raise ValueError("Phép đo bộ kiểm tra phát hiện kế hoạch sai.")
            stress_rows.append({"agents": agents, "steps": steps,
                                "median_ms": statistics.median(timings) * 1000,
                                "max_ms": max(timings) * 1000})
    save_csv(output / "validation_stress.csv", stress_rows)
    metadata = {"python": platform.python_version(), "platform": platform.platform(),
                "processor": platform.processor(), "games_per_size": args.games,
                "sizes": args.sizes, "budget_seconds": args.seconds, "seed": args.seed,
                "days": 4, "steps_per_day": 80, "fuel_limit": 40,
                "path_queries_per_map": 3, "types": [0, 0, 0, 1],
                "note": "Toàn trận offline một đội; mỗi chiến lược có lịch sử giao thông riêng."}
    (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
