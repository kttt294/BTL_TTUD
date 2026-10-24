"""So các cấu hình planner ở ngân sách giống ngày thi trên đề BTC (nhánh test).

Mỗi trận dùng hết số luồng (như runner), các cấu hình chạy xen kẽ theo bài và seed.

python -X utf8 experiments/budget_check.py --seconds 10 --threads 14
"""

import argparse
from copy import deepcopy
import glob
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
from hexudon import tour
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day
from suite import DEFAULTS, VARIANTS, central_supply


def play(path, variant, seconds, threads, seed):
    settings = deepcopy(VARIANTS[variant])
    objective = settings.pop("objective", "lookahead")
    tour.PARAMS.clear()
    tour.PARAMS.update(deepcopy(DEFAULTS))
    tour.PARAMS.update(settings)
    board = Board.from_dict(json.loads(Path(path).read_text(encoding="utf8")))
    state = State.initial(board, central_supply(board))
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, "tour", seconds, seed=seed, workers=threads, parallel_objective=objective)
        state = simulate_day(board, state, plan.actions, steps).state
    return list(state.score())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", nargs="+", default=["native", "native_sa"])
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--threads", type=int, default=14)
    parser.add_argument("--seeds", type=int, nargs="+", default=[0])
    args = parser.parse_args()
    paths = sorted(glob.glob(str(ROOT / "results/mock_contest/configs/*.json")))
    rows = []
    for path in paths:
        for seed in args.seeds:
            scores = {v: play(path, v, args.seconds, args.threads, seed) for v in args.variants}
            rows.append({"case": Path(path).stem, "seed": seed, "scores": scores})
            print(Path(path).stem, seed, " | ".join(f"{v} {tuple(s)}" for v, s in scores.items()), flush=True)
    (ROOT / f"results/budget_check_{args.seconds:g}s.json").write_text(json.dumps(rows, indent=1), encoding="utf8")
    base = args.variants[0]
    for v in args.variants[1:]:
        dq = [r["scores"][v][2] - r["scores"][base][2] for r in rows]
        dd = [r["scores"][v][1] - r["scores"][base][1] for r in rows]
        print(f"{v} so với {base}: ΔQ TB {statistics.mean(dq):+.1f}, ΔD tổng {sum(dd):+d}, "
              f"thắng {sum(r['scores'][v] > r['scores'][base] for r in rows)}/{len(rows)}")


if __name__ == "__main__":
    main()
