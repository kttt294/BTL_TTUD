"""Khoảng cách giữa tour và lời giải tối ưu của một ngày trên bản đồ nhỏ.

Bộ giải chính xác (Held-Karp): với mỗi xe tính thời gian ít nhất để ghé một tập điểm bất kỳ, dùng
khoảng cách ngắn nhất theo step giữa các điểm với giao thông của ngày; tập nào ghé kịp trong số
step của ngày là khả thi. Một xe: chọn tập khả thi có (số loại, số điểm) lớn nhất. Hai xe: xét mọi
cặp tập khả thi tối đa. Nhiên liệu dư (không ràng buộc) và kho ≥ số xe, nên số suất = tổng số
điểm các xe ghé. Đây là tối ưu thật của ngày vì đi ngang một điểm tương đương chọn nó làm đích.

python -X utf8 experiments/optimality_gap.py --instances 40
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.generator import generate_config
from hexudon.model import Board, State
from hexudon.simulator import simulate_day
from hexudon.tour import Legs, plan_tour


def instance(seed):
    """Bản đồ nhỏ 12–16 ô, 10–13 điểm, 1–2 xe tuần tra, nhiên liệu dư, một ngày."""
    rng = random.Random(seed)
    source = seed
    config = generate_config(source, "wide")
    while not (12 <= config["map"]["width"] <= 16 and 12 <= config["map"]["height"] <= 16
               and len(config["spots"]) >= 10):
        source += 100003
        config = generate_config(source, "wide")
    spots = config["spots"][:rng.randint(10, 13)]
    agents = config["agents"][:rng.randint(1, 2)]
    for spot in spots:
        spot["stocks"] = len(agents)  # kho = số xe: không tranh kho, mỗi xe lấy được ở mọi điểm
    config.update(spots=spots, agents=agents, fuelLimits=10 ** 6, daySteps=[1])
    return config


def distances(board, legs, nodes):
    return {(a, b): legs.leg(a, b, 0)[0] for a in nodes for b in nodes if a != b}


def feasible_sets(board, start, spots, dist, limit):
    """Mọi tập điểm (bitmask) một xe ghé kịp trong `limit` step, xuất phát tại start."""
    n = len(spots)
    inf = 10 ** 9
    dp = [[inf] * n for _ in range(1 << n)]
    base = 0
    for j, p in enumerate(spots):
        if p == start:
            base |= 1 << j
    for j, p in enumerate(spots):
        cost = 0 if p == start else dist[start, p]
        dp[base | (1 << j)][j] = min(dp[base | (1 << j)][j], cost)
    feasible = {base}
    for mask in range(1 << n):
        row = dp[mask]
        best = min(row)
        if best > limit:
            continue
        feasible.add(mask)
        for j in range(n):
            if row[j] > limit:
                continue
            for k in range(n):
                if mask & (1 << k):
                    continue
                value = row[j] + dist[spots[j], spots[k]]
                if value <= limit and value < dp[mask | (1 << k)][k]:
                    dp[mask | (1 << k)][k] = value
    return feasible, dp


def maximal(sets):
    result = []
    for mask in sorted(sets, key=lambda m: -bin(m).count("1")):
        if not any(mask | other == other for other in result):
            result.append(mask)
    return result


def optimum(board, steps):
    legs = Legs(board, {}, {s["pos"] for s in board.spots})
    spots = [s["pos"] for s in board.spots]
    brand_of = [s["brand"] for s in board.spots]
    dist = distances(board, legs, set(spots) | set(board.starts))
    per_car = [maximal(feasible_sets(board, start, spots, dist, steps)[0]) for start in board.starts]

    def brands(mask):
        return len({brand_of[i] for i in range(len(spots)) if mask >> i & 1})

    if len(per_car) == 1:
        return max((brands(m), bin(m).count("1")) for m in per_car[0])
    return max((brands(a | b), bin(a).count("1") + bin(b).count("1")) for a in per_car[0] for b in per_car[1])


def full_time(board):
    """Số step ít nhất để một xe (xe đầu) ghé hết mọi điểm; dùng để đặt ngày bị ràng buộc."""
    legs = Legs(board, {}, {s["pos"] for s in board.spots})
    spots = [s["pos"] for s in board.spots]
    dist = distances(board, legs, set(spots) | set(board.starts))
    _, dp = feasible_sets(board, board.starts[0], spots, dist, 10 ** 8)
    return min(dp[(1 << len(spots)) - 1])


def run(seed):
    config = instance(seed)
    board = Board.from_dict(config)
    steps = max(20, int(full_time(board) * random.Random(seed).uniform(0.35, 0.6)))
    board.day_steps = [steps]
    best = optimum(board, steps)
    state = State.initial(board, [0] * len(board.starts))
    found = {}
    for label, seconds, seeds in (("1 seed 1 giây", 1.0, [0]), ("tốt nhất 3 seed 3 giây", 3.0, [0, 1, 2])):
        results = []
        for s in seeds:
            actions = plan_tour(board, state, steps, seconds, seed=s)
            after = simulate_day(board, state, actions, steps).state
            results.append((after.daily_sum, after.portions))
        found[label] = max(results)
    return seed, len(board.starts), len(board.spots), steps, best, found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instances", type=int, default=40)
    parser.add_argument("--workers", type=int, default=14)
    args = parser.parse_args()
    with ProcessPoolExecutor(args.workers) as pool:
        rows = list(pool.map(run, range(args.instances)))
    for label in ("1 seed 1 giây", "tốt nhất 3 seed 3 giây"):
        optimal = sum(found[label] == best for *_, best, found in rows)
        types_short = sum(found[label][0] < best[0] for *_, best, found in rows)
        gaps = [(best[1] - found[label][1]) / best[1] for *_, best, found in rows if found[label][0] == best[0]]
        print(f"{label}: đạt tối ưu {optimal}/{len(rows)}, thiếu loại {types_short}, "
              f"khoảng cách suất TB {100 * statistics.mean(gaps):.1f}% (tối đa {100 * max(gaps):.1f}%)")
    for seed, patrols, spots, steps, best, found in rows:
        if found["tốt nhất 3 seed 3 giây"] != best:
            print(f"  seed {seed}: {patrols} xe, {spots} điểm, {steps} step | tối ưu {best} | tour {found}")


if __name__ == "__main__":
    main()
