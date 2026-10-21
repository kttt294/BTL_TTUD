"""Bộ test vài trăm bản đồ sinh để so các biến thể planner (nhánh ml_experiments).

Bản đồ: dev = 100 `btc` (seed 2000+) + 100 `wide` (seed 3000+); test = 50 `btc` (seed 8000+) +
50 `wide` (seed 8500+), chỉ dùng để chốt. Mỗi trận: một tiến trình, đội hình cố định (1 xe tiếp tế
ở vị trí xuất phát gần trung tâm các điểm nhất), tour với ngân sách cố định mỗi ngày. Biến thể =
các khóa ghi đè `tour.PARAMS` (xem VARIANTS).

python -X utf8 experiments/suite.py --split dev --variants base alns --seconds 1
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon import tour
from hexudon.generator import generate_config
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day

SPLITS = {"dev": [("btc", 2000, 100), ("wide", 3000, 100)], "test": [("btc", 8000, 50), ("wide", 8500, 50)]}
VARIANTS = {
    "base": {},
    "base2": {},
    "alns": {"alns": 0.2},
    "alns_fast": {"alns": 0.5},
    "positions5": {"positions": 5},
    "noise1": {"noise": 1.0},
    "remove6": {"max_remove": 6, "segment": 6},
    "escort": {"escort": True},
    "extended_heavy": {"weights": {"variant_segment": 0.08, "segment": 0.1, "random": 0.27,
                                   "reverse": 0.25, "swap": 0.15, "worst": 0.15}},
}


# Tiến trình con được dùng lại giữa các job: mỗi job đặt lại PARAMS về mặc định trước khi ghi đè.
DEFAULTS = deepcopy(tour.PARAMS)


def maps(split):
    return [(profile, start + i) for profile, start, count in SPLITS[split] for i in range(count)]


def central_supply(board):
    spots = [s["pos"] for s in board.spots]
    centre = min(range(len(board.starts)), key=lambda i: sum(board.distance(board.starts[i], p) for p in spots))
    return [int(i == centre) for i in range(len(board.starts))]


def play(job):
    profile, seed, variant, seconds = job
    tour.PARAMS.clear()
    tour.PARAMS.update(deepcopy(DEFAULTS))
    tour.PARAMS.update(deepcopy(VARIANTS[variant]))
    board = Board.from_dict(generate_config(seed, profile))
    kinds = central_supply(board)
    state = State.initial(board, kinds)
    brands = len({s["brand"] for s in board.spots})
    started, fallbacks = time.perf_counter(), 0
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, "tour", seconds, seed=seed)
        fallbacks += plan.fallback
        state = simulate_day(board, state, plan.actions, steps).state
    return {"profile": profile, "seed": seed, "variant": variant, "score": list(state.score()),
            "max_u": brands, "max_d": brands * len(board.day_steps), "fallbacks": fallbacks,
            "seconds": round(time.perf_counter() - started, 1)}


def summarize(results, variants):
    lines = []
    base = {(r["profile"], r["seed"]): tuple(r["score"]) for r in results if r["variant"] == variants[0]}
    for profile in ("btc", "wide"):
        for variant in variants:
            rows = [r for r in results if r["variant"] == variant and r["profile"] == profile]
            if not rows:
                continue
            full_u = sum(r["score"][0] == r["max_u"] for r in rows)
            full_d = sum(r["score"][1] == r["max_d"] for r in rows)
            mean_q = statistics.mean(r["score"][2] for r in rows)
            line = f"{profile:5} {variant:15} U tối đa {full_u}/{len(rows)}  D tối đa {full_d}/{len(rows)}  Q TB {mean_q:7.1f}"
            if variant != variants[0]:
                pairs = [(tuple(r["score"]), base[r["profile"], r["seed"]]) for r in rows if (r["profile"], r["seed"]) in base]
                win = sum(a > b for a, b in pairs)
                loss = sum(a < b for a, b in pairs)
                gain = statistics.mean((a[2] - b[2]) / max(1, b[2]) for a, b in pairs)
                line += f"  | so với {variants[0]}: thắng {win} hòa {len(pairs) - win - loss} thua {loss}, ΔQ TB {100 * gain:+.2f}%"
            lines.append(line)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=list(SPLITS), default="dev")
    parser.add_argument("--variants", nargs="+", default=["base"])
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--workers", type=int, default=14)
    args = parser.parse_args()
    output = ROOT / f"results/suite/{args.split}_{args.seconds:g}s.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    results = json.loads(output.read_text(encoding="utf-8")) if output.exists() else []
    done = {(r["profile"], r["seed"], r["variant"]) for r in results}
    # Xen kẽ biến thể theo từng bản đồ để các biến thể chạy cùng điều kiện tải máy.
    jobs = [(p, s, v, args.seconds) for p, s in maps(args.split) for v in args.variants if (p, s, v) not in done]
    with ProcessPoolExecutor(args.workers) as pool:
        for result in pool.map(play, jobs):
            results.append(result)
            if len(results) % 25 == 0:
                output.write_text(json.dumps(results), encoding="utf-8")
    output.write_text(json.dumps(results), encoding="utf-8")
    print(summarize(results, args.variants))


if __name__ == "__main__":
    main()
