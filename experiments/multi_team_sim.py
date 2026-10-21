"""Mô phỏng trận nhiều đội vòng kín: mọi đội cùng lập kế hoạch trên một mặt đường chung.

Mặt đường ngày sau = ngưỡng(tổng lưu lượng hai ngày trước của mọi đội / số đội), như đề.
Đối thủ là planner thật (tour ngân sách nhỏ, Greedy cũ) và có thể thêm "đội bóng ma" phát lại
lưu lượng thật từ replay Practice đầy đủ của các đội khác (không phản ứng).

Kịch bản:
- solo:   chỉ đội mình (như Practice).
- replay: đội mình + lưu lượng thật của các đội có replay đầy đủ (results/peer_comparison).
- mixed:  đội mình + tour 1 giây (1 tiếp tế) + Greedy toàn tuần tra + Greedy 1 tiếp tế.
- crowd:  đội mình + 5 đội tour 1 giây cùng đội hình với mình (cùng săn các điểm như mình).

python -X utf8 experiments/multi_team_sim.py --seconds 3
"""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
from fetch_peer_traffic import load_board
from hexudon.model import State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_match_day

# Đội hình đội mình theo lượt nộp gần nhất trên máy chủ (cố định để tách tác dụng nhìn trước).
OUR_TYPES = {"Q01": [0, 1, 0, 0], "Q02": [1, 0, 0, 0], "Q03": [0, 0, 1, 0, 0], "Q04": [0, 1, 0, 0],
             "Q06": [0, 1, 0, 0, 0, 0], "Q07": [0, 1, 0, 0, 0], "Q08": [0, 1, 0, 0, 0],
             "Q09": [0, 1, 0, 0, 0], "Q10": [0, 0, 1, 0, 0]}
FULL = ROOT / "results/peer_comparison"
OWN_NAME = "Phenikaa_2"


def roads(board):
    return [p for p in range(board.width * board.height) if board.terrain(p) == 1]


def status_of(board, value):
    return 2 if value >= board.jammed_threshold else 1 if value >= board.busy_threshold else 0


def ghost_windows(case, board):
    """Tổng lưu lượng hai ngày trước (cho ngày 1..n-1) của từng đội có replay Practice đầy đủ."""
    sys.path.insert(0, str(ROOT / "experiments"))
    from peer_traffic_demo import windows
    ghosts = {}
    for path in sorted(FULL.glob(f"*_{case}.json")):
        team = path.stem.rsplit("_", 1)[0]
        replay = json.loads(path.read_text(encoding="utf-8")).get("replay", {})
        days = replay.get("days", [])
        if team != OWN_NAME and len(days) == len(board.day_steps) and len(days[0]["teams"][0]["frames"]) > 1:
            ghosts[team] = windows(board, replay)
    return ghosts


def last_supply(count):
    return [0] * (count - 1) + [1]


def opponents(scenario, board, ours):
    count = len(board.starts)
    if scenario == "mixed":
        return [("tour", 1.0, last_supply(count)), ("greedy", 0.3, [0] * count),
                ("greedy", 0.3, last_supply(count))]
    if scenario == "crowd":
        return [("tour", 1.0, list(ours)) for _ in range(5)]
    return []


def play(job):
    case, scenario, seconds = job
    board = load_board(case)
    ours = OUR_TYPES[case]
    rivals = opponents(scenario, board, ours)
    ghosts = ghost_windows(case, board) if scenario == "replay" else {}
    teams = 1 + len(rivals) + len(ghosts)
    states = {"us": State.initial(board, ours)}
    planners = {"us": ("tour", seconds)}
    for index, (kind, budget, kinds) in enumerate(rivals):
        states[f"r{index}"] = State.initial(board, kinds)
        planners[f"r{index}"] = (kind, budget)
    brands = len({s["brand"] for s in board.spots})
    daily, congested, fallbacks = [], [], 0
    started = time.perf_counter()
    for day, steps in enumerate(board.day_steps):
        congested.append(sum(1 for s in states["us"].traffic.values() if s))
        orders = {}
        for name, state in states.items():
            kind, budget = planners[name]
            plan = plan_day(board, state, steps, kind, budget)
            orders[name] = plan.actions
            fallbacks += name == "us" and plan.fallback
        before = states["us"].daily_sum
        result = simulate_match_day(board, states, orders, steps)
        if not result.valid:
            raise ValueError(f"{case} {scenario}: {result.errors[:2]}")
        states = result.states
        daily.append(states["us"].daily_sum - before)
        if ghosts and day + 1 < len(board.day_steps):
            total = Counter()
            for state in states.values():
                for history in state.road_history:
                    total.update(history)
            for window in ghosts.values():
                total.update(window[day])
            traffic = {p: status_of(board, total.get(p, 0) / teams) for p in roads(board)}
            for state in states.values():
                state.traffic = dict(traffic)
    return {"case": case, "scenario": scenario, "seconds": seconds,
            "teams": teams, "score": list(states["us"].score()),
            "rivals": {n: list(s.score()) for n, s in states.items() if n != "us"},
            "d_lost_days": [d + 1 for d, v in enumerate(daily) if v < brands],
            "congested_per_day": congested, "fallbacks": fallbacks,
            "minutes": round((time.perf_counter() - started) / 60, 1)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", default=["Q01", "Q03", "Q04", "Q06", "Q07", "Q08", "Q09", "Q10"])
    parser.add_argument("--scenarios", nargs="+", default=["solo", "replay", "mixed", "crowd"])
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--workers", type=int, default=14)
    parser.add_argument("--output", default=str(ROOT / "results/multi_team/sim.json"))
    args = parser.parse_args()
    jobs = [(c, s, args.seconds) for _ in range(args.repeats) for c in args.cases
            for s in args.scenarios]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with ProcessPoolExecutor(args.workers) as pool:
        for result in pool.map(play, jobs):
            results.append(result)
            print(result["case"], result["scenario"].ljust(7),
                  f"{result['teams']} đội", tuple(result["score"]), "mất D ngày", result["d_lost_days"],
                  f"đông/tắc TB {sum(result['congested_per_day']) / len(result['congested_per_day']):.0f}",
                  flush=True)
            output.write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
