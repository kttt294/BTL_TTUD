"""So bộ chọn đội hình cũ (điều phối Python) và mới (C++ cả trận, loại dần, cùng seed) (nhánh test).

Mỗi bản đồ: mỗi bộ chọn chạy 2 lần với ngân sách như ngày thi (độ ổn định); mỗi đội hình được chọn
được chấm bằng trận đầy đủ (nhiều luồng, vài seed, lấy trung bình) để biết lựa chọn nào tốt hơn.

python -X utf8 experiments/selection_compare.py --seconds 26
"""

import argparse
import glob
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon import native, tour
from hexudon.generator import generate_config
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day
from hexudon.team_selection import candidate_types, select_types_parallel


def match(board, kinds, seconds, threads, seed):
    state = State.initial(board, list(kinds))
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, "tour", seconds, seed=seed, workers=threads)
        state = simulate_day(board, state, plan.actions, steps).state
    return state.score()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=26.0, help="Ngân sách chọn đội hình")
    parser.add_argument("--day-seconds", type=float, default=2.0, help="Ngân sách mỗi ngày khi chấm đội hình")
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--threads", type=int, default=14)
    args = parser.parse_args()
    boards = [(Path(p).stem, Board.from_dict(json.loads(Path(p).read_text(encoding="utf8"))))
              for p in sorted(glob.glob(str(ROOT / "results/mock_contest/configs/*.json")))]
    boards += [(f"{profile}{seed}", Board.from_dict(generate_config(seed, profile)))
               for profile, seed in [("btc", 2000 + i) for i in range(6)] + [("wide", 3000 + i) for i in range(6)]]
    rows = []
    for name, board in boards:
        picks = {"old": [], "new": []}
        for _ in range(2):
            picks["old"].append(tuple(select_types_parallel(board, args.seconds, "tour")[0]))
            chosen = native.select_types(board, args.seconds, candidate_types(board), args.threads)
            picks["new"].append(tuple(chosen[0]) if chosen else picks["old"][-1])
        scores = {}
        for kinds in {k for ks in picks.values() for k in ks}:
            runs = [match(board, kinds, args.day_seconds, args.threads, seed) for seed in range(args.seeds)]
            scores[kinds] = (min(r[0] for r in runs), min(r[1] for r in runs), statistics.mean(r[2] for r in runs))
        value = {k: statistics.mean(scores[p][2] for p in ps) for k, ps in picks.items()}
        rows.append({"map": name, "picks": {k: [list(p) for p in v] for k, v in picks.items()},
                     "scores": {str(list(k)): v for k, v in scores.items()}, "mean_q": value})
        print(f"{name}: cũ {picks['old']} | mới {picks['new']} | "
              + " | ".join(f"{list(k)} {v}" for k, v in scores.items()), flush=True)
    (ROOT / "results/selection_compare.json").write_text(json.dumps(rows, indent=1), encoding="utf8")
    for key in ("old", "new"):
        stable = sum(r["picks"][key][0] == r["picks"][key][1] for r in rows)
        print(f"{key}: chọn giống nhau ở 2 lần {stable}/{len(rows)}")
    diff = [r["mean_q"]["new"] - r["mean_q"]["old"] for r in rows]
    print(f"Q trung bình của đội hình được chọn, mới - cũ: {statistics.mean(diff):+.1f} "
          f"(hơn {sum(d > 0 for d in diff)}, bằng {sum(d == 0 for d in diff)}, kém {sum(d < 0 for d in diff)})")


if __name__ == "__main__":
    main()
