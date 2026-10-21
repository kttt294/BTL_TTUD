"""Bộ đo mức ngày cho planner tour: cùng trạng thái đầu ngày, cùng ngân sách, cùng seed.

Bước `collect`: chơi các trận bằng tour (2 giây/ngày) và lưu trạng thái đầu mỗi ngày.
Bước `run`: lập kế hoạch lại cho từng trạng thái với từng biến thể và so (loại, suất) của ngày.
Đo trên từng ngày nên không có hiệu ứng dây chuyền giữa các ngày; nhiễu thấp hơn đo cả trận.

python -X utf8 experiments/benchmark_day.py collect
python -X utf8 experiments/benchmark_day.py run --variants base --seconds 1 --seeds 0 1
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import pickle
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon import tour
from hexudon.generator import generate_config
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day

STATES = ROOT / "results/day_states.pkl"
BTC = {"Q01": [1, 0, 0, 0], "Q03": [0, 0, 0, 0, 1], "Q04": [0, 0, 1, 0], "Q06": [0, 0, 0, 1, 0, 0],
       "Q07": [0, 1, 0, 0, 0], "Q08": [0, 1, 0, 0, 0], "Q09": [0, 1, 0, 0, 0], "Q10": [0, 0, 1, 0, 0]}


def load_config(name):
    if name.startswith("Q"):
        return json.loads((ROOT / "output/team_selection" / name / "config.json").read_text(encoding="utf-8"))
    return generate_config(int(name.split("_")[1]), "btc")


def collect_one(job):
    name, kinds = job
    board = Board.from_dict(load_config(name))
    state = State.initial(board, kinds)
    states = []
    for steps in board.day_steps:
        states.append(state)
        plan = plan_day(board, state, steps, "tour", 2.0)
        state = simulate_day(board, state, plan.actions, steps).state
    return name, states


def run_one(job):
    name, day, state, variant, seconds, seed = job
    # Biến thể: đặt thuộc tính module tương ứng ở đây khi cần so A/B (mặc định: cấu hình hiện tại).
    board = Board.from_dict(load_config(name))
    steps = board.day_steps[day]
    actions = tour.plan_tour(board, state, steps, seconds, seed=seed)
    after = simulate_day(board, state, actions, steps).state
    return name, day, variant, seed, after.daily_sum - state.daily_sum, after.portions - state.portions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["collect", "run"])
    parser.add_argument("--variants", nargs="+", default=["base"])
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1])
    parser.add_argument("--workers", type=int, default=14)
    args = parser.parse_args()
    if args.step == "collect":
        jobs = list(BTC.items())
        for seed in range(1000, 1008):
            board = Board.from_dict(generate_config(seed, "btc"))
            jobs.append((f"btc_{seed}", [0] * (len(board.starts) - 1) + [1]))
        with ProcessPoolExecutor(args.workers) as pool:
            states = dict(pool.map(collect_one, jobs))
        STATES.write_bytes(pickle.dumps(states))
        print("Đã lưu", sum(len(v) for v in states.values()), "trạng thái vào", STATES)
        return
    states = pickle.loads(STATES.read_bytes())
    jobs = [(name, day, state, variant, args.seconds, seed)
            for name, items in states.items() for day, state in enumerate(items)
            for variant in args.variants for seed in args.seeds]
    with ProcessPoolExecutor(args.workers) as pool:
        results = list(pool.map(run_one, jobs))
    table = {}
    for name, day, variant, seed, types, portions in results:
        table.setdefault((name, day, seed), {})[variant] = (types, portions)
    base = args.variants[0]
    for (name, day, seed), v in sorted(table.items()):
        for variant in args.variants[1:]:
            if v[variant][0] != v[base][0]:
                print(f"khác số loại: {name} ngày {day + 1} seed {seed}: {base} {v[base]} | {variant} {v[variant]}")
    for variant in args.variants:
        types = sum(v[variant][0] for v in table.values())
        portions = sum(v[variant][1] for v in table.values())
        line = f"{variant:10} loại {types} suất {portions}"
        if variant != base:
            better = sum(v[variant] > v[base] for v in table.values())
            worse = sum(v[variant] < v[base] for v in table.values())
            gain = statistics.mean(v[variant][1] - v[base][1] for v in table.values())
            line += f" | so với {base}: tốt hơn {better}, kém hơn {worse}, Δsuất TB/ngày {gain:+.2f}"
        print(line)


if __name__ == "__main__":
    main()
