"""So toàn bộ quy trình thi offline: chọn vai trò rồi lập kế hoạch từng ngày, mô phỏng một đội.

Bản cũ: chọn vai trò bằng Greedy (8 giây) và lập kế hoạch Greedy.
Bản mới: chọn vai trò song song bằng planner tuyến (20 giây) và lập kế hoạch tuyến.
Điểm là điểm simulator, giao thông tương lai chỉ do đội mình tạo ra.
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
from hexudon.team_selection import select_types

CASES = ["Q01", "Q03", "Q04", "Q06", "Q07", "Q08", "Q09", "Q10",
         "generated_8_2026", "generated_16_2026", "generated_32_2026",
         "generated_8_2027", "generated_16_2027", "generated_32_2027"]
PIPELINES = {"old": ("greedy", 8.0, 2.0), "new": ("tour", 20.0, 5.0)}


def upper_bound(board, kinds):
    brands = len({s["brand"] for s in board.spots})
    patrols = kinds.count(0)
    portions = sum(min(s["stocks"], patrols) for s in board.spots) * len(board.day_steps)
    return brands, brands * len(board.day_steps), portions


def play(board, name):
    strategy, selection_seconds, day_seconds = PIPELINES[name]
    started = time.perf_counter()
    kinds, _, selection_elapsed = select_types(board, selection_seconds, strategy)
    state = State.initial(board, kinds)
    days, fallbacks, longest = [], 0, 0.0
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, strategy, day_seconds)
        checked = simulate_day(board, state, plan.actions, steps)
        if not checked.valid:
            raise ValueError(f"{name}: kế hoạch không hợp lệ {checked.errors}")
        before = state.daily_sum, state.portions
        state = checked.state
        fallbacks += plan.fallback
        longest = max(longest, plan.elapsed)
        days.append([state.daily_sum - before[0], state.portions - before[1]])
    return {"pipeline": name, "types": kinds, "score": list(state.score()),
            "bound_for_types": list(upper_bound(board, kinds)), "days": days,
            "fallbacks": fallbacks, "selection_seconds": round(selection_elapsed, 2),
            "longest_day_seconds": round(longest, 2), "elapsed": round(time.perf_counter() - started, 1)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", default=CASES)
    parser.add_argument("--output", default=str(ROOT / "experiments/tour_results/pipeline.json"))
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    for case in args.cases:
        config = json.loads((ROOT / "output/team_selection" / case / "config.json").read_text(encoding="utf-8"))
        board = Board.from_dict(config)
        results[case] = {name: play(board, name) for name in PIPELINES}
        old, new = results[case]["old"], results[case]["new"]
        verdict = "new" if tuple(new["score"]) > tuple(old["score"]) else (
            "tie" if new["score"] == old["score"] else "old")
        results[case]["winner"] = verdict
        print(f"{case:18} old {tuple(old['score'])} {old['types']}  new {tuple(new['score'])} "
              f"{new['types']}  -> {verdict}", flush=True)
        output.write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
