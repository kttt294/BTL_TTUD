"""Planner có đúng và tốt với mọi trạng thái đường 0/1/2 không: ép mặt đường cố định suốt trận.

Kịch bản (mặt đường được ghi đè trước mỗi ngày):
- clear: mọi ô đường 0 (1 step/bước);  busy: mọi ô 1 (2 step);  jam: mọi ô 2 (4 step);
- mixed: mỗi ngày mỗi ô ngẫu nhiên 0/1/2 với tỷ lệ 50/30/20;
- hotspot: ô đường trong bán kính 2 quanh điểm udon là 2, còn lại 0 (tắc đúng chỗ cần đi).
Mỗi kế hoạch đều qua simulator (thời gian di chuyển theo đúng trạng thái đường). So tour với Greedy
cũ trên cùng mặt đường; báo U, D so với cận, Q và số ngày mất D.

python -X utf8 experiments/traffic_robustness.py --seconds 3
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day

CONFIGS = {"Q01": "output/team_selection/Q01/config.json", "Q03": "output/team_selection/Q03/config.json",
           "Q07": "output/team_selection/Q07/config.json", "Q10": "output/team_selection/Q10/config.json",
           "M11": "results/mock_contest/configs/Q11.json", "M18": "results/mock_contest/configs/Q18.json"}
SCENARIOS = ["clear", "busy", "jam", "mixed", "hotspot"]


def traffic_for(board, scenario, day, seed):
    roads = [p for p in range(board.width * board.height) if board.terrain(p) == 1]
    if scenario in ("clear", "busy", "jam"):
        level = {"clear": 0, "busy": 1, "jam": 2}[scenario]
        return {p: level for p in roads}
    if scenario == "mixed":
        rng = random.Random(seed * 1000 + day)
        return {p: rng.choices([0, 1, 2], [5, 3, 2])[0] for p in roads}
    spots = [s["pos"] for s in board.spots]
    return {p: 2 if min(board.distance(p, q) for q in spots) <= 2 else 0 for p in roads}


def play(job):
    name, scenario, strategy, seconds, seed = job
    board = Board.from_dict(json.loads((ROOT / CONFIGS[name]).read_text(encoding="utf-8")))
    kinds = [0] * (len(board.starts) - 1) + [1]
    state = State.initial(board, kinds)
    brands = len({s["brand"] for s in board.spots})
    lost, invalid = [], 0
    for day, steps in enumerate(board.day_steps):
        state.traffic = traffic_for(board, scenario, day, seed)
        plan = plan_day(board, state, steps, strategy, seconds if strategy == "tour" else 0.5, seed=seed)
        checked = simulate_day(board, state, plan.actions, steps)
        if not checked.valid:
            invalid += 1
            break
        before = state.daily_sum
        state = checked.state
        if state.daily_sum - before < brands:
            lost.append(day + 1)
    return {"case": name, "scenario": scenario, "strategy": strategy, "score": list(state.score()),
            "max_u": brands, "max_d": brands * len(board.day_steps), "lost": lost, "invalid": invalid}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--workers", type=int, default=14)
    args = parser.parse_args()
    jobs = [(c, s, p, args.seconds, 0) for c in CONFIGS for s in SCENARIOS for p in ("tour", "greedy")]
    with ProcessPoolExecutor(args.workers) as pool:
        results = list(pool.map(play, jobs))
    Path(ROOT / "results/traffic_robustness.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    table = {(r["case"], r["scenario"], r["strategy"]): r for r in results}
    print(f"{'bài':5}{'kịch bản':10}{'tour (U, D, Q)':24}{'mất D':10}{'Greedy (U, D, Q)':24}{'tour hơn':>9}")
    for case in CONFIGS:
        for scenario in SCENARIOS:
            t, g = table[case, scenario, "tour"], table[case, scenario, "greedy"]
            bad = " LỖI" if t["invalid"] or g["invalid"] else ""
            print(f"{case:5}{scenario:10}{str(tuple(t['score'])):24}{str(t['lost']):10}{str(tuple(g['score'])):24}"
                  f"{t['score'][2] - g['score'][2]:>+9}{bad}  (cận U {t['max_u']}, D {t['max_d']})")
    invalid = sum(r["invalid"] for r in results)
    full = sum(r["score"][:2] == [r["max_u"], r["max_d"]] for r in results if r["strategy"] == "tour")
    print(f"\nKế hoạch không hợp lệ: {invalid}; tour đạt U, D tối đa {full}/{len(CONFIGS) * len(SCENARIOS)} trận")


if __name__ == "__main__":
    main()
