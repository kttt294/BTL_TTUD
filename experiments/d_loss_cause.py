"""Tách nguyên nhân mất D (nhánh ml_experiments), sau `d_loss.py`.

Chơi lại đội hình do bộ chọn vai trò chọn (1 giây/ngày); mỗi ngày mất D đo số loại đi được khi:
- B: giữ vị trí đầu ngày, nhiên liệu vô hạn (đủ loại = nghẽn do nhiên liệu);
- C: đặt xe tuần tra tự do ở các điểm udon, nhiên liệu vô hạn, leo đồi 4 giây (đủ loại mà B thiếu =
  nghẽn do vị trí cuối ngày hôm trước; C cũng thiếu = gần như không tránh được với số xe này).
Dựng chỉ nhắm loại (`tour.types_coverage`) nên B, C là cận dưới của khả năng thật.

python -X utf8 experiments/d_loss_cause.py
"""

from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon import tour
from hexudon.generator import generate_config
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day

FULL = 10 ** 6


def relaxed(board, state, positions=None):
    big = deepcopy(board)
    big.fuel_limit = FULL
    new = deepcopy(state)
    for i, agent in enumerate(new.agents):
        agent.fuel = FULL if agent.kind == 0 else 0
        if positions and i in positions:
            agent.pos = positions[i]
    return big, new


def coverage(board, state, steps, positions=None):
    big, new = relaxed(board, state, positions)
    return tour.types_coverage(big, new, steps, [])


def free_placement(board, state, steps, seconds, seed):
    rng = random.Random(seed)
    patrols = [i for i, a in enumerate(state.agents) if a.kind == 0]
    spots = [s["pos"] for s in board.spots]
    brands = len({s["brand"] for s in board.spots})
    current = {i: state.agents[i].pos for i in patrols}
    best = coverage(board, state, steps, current)
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline and best < brands:
        trial = dict(current)
        for i in rng.sample(patrols, rng.randint(1, min(2, len(patrols)))):
            trial[i] = rng.choice(spots)
        value = coverage(board, state, steps, trial)
        if value >= best:
            best, current = value, trial
    return best


def play(row):
    board = Board.from_dict(generate_config(row["seed"], row["profile"]))
    brands = row["brands"]
    state = State.initial(board, row["kinds"])
    days = []
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, "tour", 1.0, seed=row["seed"])
        after = simulate_day(board, state, plan.actions, steps).state
        types = after.daily_sum - state.daily_sum
        if types < brands:
            fuel = [a.fuel for a in state.agents if a.kind == 0]
            days.append({"day": state.day + 1, "steps": steps, "types": types, "fuel": fuel,
                         "B": coverage(board, state, steps), "C": free_placement(board, state, steps, 4.0, row["seed"])})
        state = after
    return {"profile": row["profile"], "seed": row["seed"], "kinds": row["kinds"], "brands": brands,
            "fuel_limit": board.fuel_limit, "score": list(state.score()), "lost": days}


def main():
    rows = [r for r in json.loads((ROOT / "results/suite/d_loss.json").read_text(encoding="utf-8"))
            if r["mode"] == "select"]
    with ProcessPoolExecutor(14) as pool:
        results = list(pool.map(play, rows))
    (ROOT / "results/suite/d_loss_cause.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    for r in results:
        print(f"{r['profile']} {r['seed']} {r['kinds']} {r['brands']} loại, nhiên liệu tối đa {r['fuel_limit']}, "
              f"D {r['score'][1]}/{r['brands'] * len(generate_config(r['seed'], r['profile'])['daySteps'])}")
        for d in r["lost"]:
            print(f"   ngày {d['day']} ({d['steps']} step): đạt {d['types']}, B (đầy xăng) {d['B']}, "
                  f"C (đặt tự do) {d['C']}, xăng xe tuần tra {d['fuel']}")


if __name__ == "__main__":
    main()
