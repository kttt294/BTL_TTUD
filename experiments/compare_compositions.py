"""Các đội hình một xe tiếp tế có thật sự khác nhau không: chơi trọn trận nhiều seed cho mỗi đội hình.

Mỗi trận chạy một tiến trình, tour với ngân sách cố định; báo U, D thấp nhất và Q trung bình ± độ
lệch chuẩn theo vị trí xe tiếp tế. Nếu chênh Q trung bình giữa các vị trí nhỏ so với độ lệch chuẩn
thì bộ chọn chọn vị trí nào cũng như nhau; nếu lớn thì bộ chọn cần ổn định hơn.

python -X utf8 experiments/compare_compositions.py --seconds 3 --seeds 0 1 2
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day

CASES = ["Q01", "Q03", "Q04", "Q06", "Q07", "Q08", "Q09", "Q10"]


def play(job):
    case, kinds, seconds, seed = job
    config = json.loads((ROOT / "output/team_selection" / case / "config.json").read_text(encoding="utf-8"))
    board = Board.from_dict(config)
    state = State.initial(board, kinds)
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, "tour", seconds, seed=seed)
        state = simulate_day(board, state, plan.actions, steps).state
    return case, tuple(kinds), seed, state.score()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", default=CASES)
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--workers", type=int, default=14)
    parser.add_argument("--output", default=str(ROOT / "results/compare_compositions.json"))
    args = parser.parse_args()
    jobs = []
    for case in args.cases:
        config = json.loads((ROOT / "output/team_selection" / case / "config.json").read_text(encoding="utf-8"))
        count = len(config["agents"])
        for supply in range(count):
            kinds = [int(i == supply) for i in range(count)]
            jobs += [(case, kinds, args.seconds, seed) for seed in args.seeds]
    with ProcessPoolExecutor(args.workers) as pool:
        results = list(pool.map(play, jobs))
    Path(args.output).write_text(json.dumps([[c, list(k), s, list(sc)] for c, k, s, sc in results]), encoding="utf-8")
    for case in args.cases:
        rows = {}
        for c, kinds, seed, score in results:
            if c == case:
                rows.setdefault(kinds, []).append(score)
        print(case)
        ranked = sorted(rows.items(), key=lambda item: statistics.mean(s[2] for s in item[1]), reverse=True)
        for kinds, scores in ranked:
            q = [s[2] for s in scores]
            print(f"  xe tiếp tế ở vị trí {kinds.index(1)}: U {min(s[0] for s in scores)} D {min(s[1] for s in scores)} "
                  f"Q TB {statistics.mean(q):.0f} ± {statistics.stdev(q) if len(q) > 1 else 0:.0f} ({q})")


if __name__ == "__main__":
    main()
