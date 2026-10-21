"""So planner tour một tiến trình với nhiều seed song song, cùng ngân sách giây/ngày.

Các trận chạy lần lượt để mỗi cấu hình dùng trọn CPU; đội hình lấy từ lượt nộp gần nhất của ta.
python -X utf8 experiments/benchmark_parallel.py --workers 1 8 14 --seconds 5
"""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day

TYPES = {"Q01": [1, 0, 0, 0], "Q03": [0, 0, 0, 0, 1], "Q04": [0, 0, 1, 0], "Q06": [0, 0, 0, 1, 0, 0],
         "Q07": [0, 1, 0, 0, 0], "Q08": [0, 1, 0, 0, 0], "Q09": [0, 1, 0, 0, 0], "Q10": [0, 0, 1, 0, 0]}


def play(case, kinds, seconds, workers):
    config = json.loads((ROOT / "output/team_selection" / case / "config.json").read_text(encoding="utf-8"))
    board = Board.from_dict(config)
    state = State.initial(board, kinds)
    longest, fallbacks = 0.0, 0
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, "tour", seconds, workers=workers)
        longest, fallbacks = max(longest, plan.elapsed), fallbacks + plan.fallback
        state = simulate_day(board, state, plan.actions, steps).state
    return {"case": case, "workers": workers, "seconds": seconds, "score": list(state.score()),
            "longest_day": round(longest, 2), "fallbacks": fallbacks}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", default=list(TYPES))
    parser.add_argument("--workers", nargs="+", type=int, default=[1, 8, 14])
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--output", default=str(ROOT / "results/benchmark_parallel.json"))
    args = parser.parse_args()
    results = []
    for case in args.cases:
        for workers in args.workers:
            started = time.perf_counter()
            result = play(case, TYPES[case], args.seconds, workers)
            results.append(result)
            print(case, "workers", workers, tuple(result["score"]),
                  "ngày lâu nhất", result["longest_day"], "dự phòng", result["fallbacks"],
                  f"{time.perf_counter() - started:.0f}s", flush=True)
            Path(args.output).write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
