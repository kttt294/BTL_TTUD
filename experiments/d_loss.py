"""Chẩn đoán các trận mất D trên bộ dev (nhánh ml_experiments).

Với mỗi bản đồ mà cấu hình base (1 xe tiếp tế trung tâm, 1 giây/ngày) chưa đạt D tối đa:
- cận ngày 1: số loại tới kịp từ vị trí xuất phát nếu mọi xe là tuần tra (bỏ qua nhiên liệu); nhỏ
  hơn số loại nghĩa là không đội nào đạt D tối đa;
- base: chơi lại, mỗi ngày mất D ghi cận tới kịp (`tour.day_bound`) và số loại tốt nhất khi lập lại
  ngày đó với 5 giây × 3 seed (đạt đủ = lỗi tìm kiếm; cận thiếu = lỗi vị trí/đội hình);
- long: cùng đội hình, 4 giây/ngày; select: đội hình do bộ chọn vai trò thật chọn (20 giây);
  allpatrol: mọi xe tuần tra.

python -X utf8 experiments/d_loss.py
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
from hexudon import tour
from hexudon.generator import generate_config
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day
from hexudon.team_selection import select_types
from suite import central_supply


def board_of(profile, seed):
    return Board.from_dict(generate_config(seed, profile))


def play(job):
    profile, seed, mode, kinds = job
    board = board_of(profile, seed)
    brands = len({s["brand"] for s in board.spots})
    seconds = 4.0 if mode == "long" else 1.0
    state = State.initial(board, kinds)
    days = []
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, "tour", seconds, seed=seed)
        after = simulate_day(board, state, plan.actions, steps).state
        types = after.daily_sum - state.daily_sum
        if types < brands and mode == "base":
            bound = tour.day_bound(board, state)[0]
            retry = 0
            for s in range(3):
                actions = tour.plan_tour(board, state, steps, 5.0, seed=s)
                checked = simulate_day(board, state, actions, steps)
                if checked.valid:
                    retry = max(retry, checked.state.daily_sum - state.daily_sum)
            days.append({"day": state.day + 1, "steps": steps, "types": types, "bound": bound, "retry": retry})
        elif types < brands:
            days.append({"day": state.day + 1, "steps": steps, "types": types})
        state = after
    return {"profile": profile, "seed": seed, "mode": mode, "kinds": kinds, "score": list(state.score()),
            "max_d": brands * len(board.day_steps), "lost": days}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="results/suite/dev_1s.json")
    parser.add_argument("--selection-seconds", type=float, default=20.0)
    parser.add_argument("--workers", type=int, default=14)
    args = parser.parse_args()
    rows = json.loads((ROOT / args.source).read_text(encoding="utf-8"))
    maps = [(r["profile"], r["seed"]) for r in rows if r["variant"] == "base" and r["score"][1] < r["max_d"]]
    jobs, info = [], {}
    for profile, seed in maps:
        board = board_of(profile, seed)
        brands = len({s["brand"] for s in board.spots})
        day1 = tour.day_bound(board, State.initial(board, [0] * len(board.starts)))[0]
        chosen = select_types(board, args.selection_seconds, "tour")
        chosen = chosen[0] if isinstance(chosen, tuple) else chosen
        info[profile, seed] = {"brands": brands, "day1_all_patrol": day1, "selected": chosen}
        print(f"{profile} {seed}: {brands} loại, cận ngày 1 (mọi xe tuần tra) {day1}, bộ chọn: {chosen}", flush=True)
        for mode, kinds in (("base", central_supply(board)), ("long", central_supply(board)),
                            ("select", list(chosen)), ("allpatrol", [0] * len(board.starts))):
            jobs.append((profile, seed, mode, kinds))
    with ProcessPoolExecutor(args.workers) as pool:
        results = list(pool.map(play, jobs))
    for r in results:
        r.update(info[r["profile"], r["seed"]])
    out = ROOT / "results/suite/d_loss.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    for r in results:
        lost = "; ".join(f"ngày {d['day']} ({d['steps']} step) {d['types']}" +
                         (f", cận {d['bound']}, lập lại 5 giây {d['retry']}" if "bound" in d else "")
                         for d in r["lost"])
        print(f"{r['profile']} {r['seed']} {r['mode']:9} {r['kinds']} D {r['score'][1]}/{r['max_d']} "
              f"Q {r['score'][2]} | {lost or 'đủ D'}")


if __name__ == "__main__":
    main()
