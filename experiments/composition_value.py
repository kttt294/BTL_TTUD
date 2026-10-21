"""Bộ chọn vai trò chọn tốt đến đâu so với đội hình tốt nhất (nhánh ml_experiments).

Mỗi bản đồ: chơi trọn trận (1 giây/ngày) với mọi đội hình ứng viên (`candidate_types`, tối đa 16)
để có bảng điểm; chạy bộ chọn thật với ngân sách như khi thi; đo khoảng cách (U, D, Q) giữa đội
hình tốt nhất trong bảng và đội hình được chọn. Max trên nhiều trận nhiễu nên khoảng cách Q hơi
bị phóng đại; D ít nhiễu hơn.

python -X utf8 experiments/composition_value.py --btc 20 --wide 40
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.generator import generate_config
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day
from hexudon.team_selection import candidate_types, select_types


def play(job):
    profile, seed, kinds = job
    board = Board.from_dict(generate_config(seed, profile))
    state = State.initial(board, kinds)
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, "tour", 1.0, seed=seed)
        state = simulate_day(board, state, plan.actions, steps).state
    return profile, seed, tuple(kinds), state.score()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--btc", type=int, default=20)
    parser.add_argument("--wide", type=int, default=40)
    parser.add_argument("--selection-seconds", type=float, default=26.0)
    args = parser.parse_args()
    maps = [("btc", 2000 + i) for i in range(args.btc)] + [("wide", 3000 + i) for i in range(args.wide)]
    selected = {}
    for profile, seed in maps:
        board = Board.from_dict(generate_config(seed, profile))
        selected[profile, seed] = tuple(select_types(board, args.selection_seconds, "tour")[0])
    jobs = [(p, s, kinds) for p, s in maps
            for kinds in candidate_types(Board.from_dict(generate_config(s, p)))]
    table = {}
    with ProcessPoolExecutor(14) as pool:
        for profile, seed, kinds, score in pool.map(play, jobs):
            table.setdefault((profile, seed), {})[kinds] = score
    rows = []
    for (profile, seed), scores in table.items():
        best = max(scores, key=scores.get)
        chosen = selected[profile, seed]
        mine = scores.get(chosen)
        rows.append({"profile": profile, "seed": seed, "best": list(best), "best_score": list(scores[best]),
                     "chosen": list(chosen), "chosen_score": list(mine) if mine else None,
                     "all": {str(k): list(v) for k, v in scores.items()}})
    (ROOT / "results/suite/composition_value.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for profile in ("btc", "wide"):
        part = [r for r in rows if r["profile"] == profile and r["chosen_score"]]
        d_gap = [r["best_score"][1] - r["chosen_score"][1] for r in part]
        q_gap = [r["best_score"][2] - r["chosen_score"][2] for r in part if r["best_score"][:2] == r["chosen_score"][:2]]
        print(f"{profile}: {len(part)} bản đồ, chọn đúng đội hình tốt nhất {sum(r['best'] == r['chosen'] for r in part)}, "
              f"thiếu D so với tốt nhất ở {sum(g > 0 for g in d_gap)} bản đồ (tổng {sum(d_gap)} D), "
              f"cùng U/D thì thiếu Q TB {statistics.mean(q_gap) if q_gap else 0:.1f}")
        for r in part:
            if r["best_score"][:2] > r["chosen_score"][:2]:
                print(f"   {r['seed']}: chọn {r['chosen']} {tuple(r['chosen_score'])} | tốt nhất {r['best']} {tuple(r['best_score'])}")


if __name__ == "__main__":
    main()
