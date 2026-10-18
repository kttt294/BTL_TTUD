"""Cận trên từ các điều kiện cần về tiếp cận, không giả định ghé được mọi điểm."""

import heapq
import time

from .model import State


def shortest_costs(board, start, fuel=False):
    distances = {start: 0}
    pending = [(0, start)]
    while pending:
        cost, pos = heapq.heappop(pending)
        if cost != distances[pos]:
            continue
        # Đường thông thoáng cho thời gian nhỏ nhất; nhiên liệu không phụ thuộc giao thông.
        weight = board.cost(pos, {})[int(fuel)]
        for _, target in board.neighbors(pos):
            candidate = cost + weight
            if candidate < distances.get(target, float("inf")):
                distances[target] = candidate
                heapq.heappush(pending, (candidate, target))
    return distances


def score_bounds(board, kinds):
    """Tính cận đầu trận, từng ngày và toàn trận cho một đội hình cố định."""
    started = time.perf_counter()
    State.initial(board, kinds)
    brands = len({spot["brand"] for spot in board.spots})
    days, cars, patrols = len(board.day_steps), len(kinds), kinds.count(0)
    supply_reachable = set()
    for start, kind in zip(board.starts, kinds):
        if kind == 1:
            # Nới lỏng: xe tiếp tế có thể nạp ở mọi ô cùng vùng liên thông ngay từ đầu.
            supply_reachable.update(shortest_costs(board, start))
    distances = []
    for start, kind in zip(board.starts, kinds):
        if kind == 0:
            distances.append((shortest_costs(board, start), shortest_costs(board, start, fuel=True),
                              start in supply_reachable))
    daily = []
    total_steps = 0
    for day, steps in enumerate(board.day_steps, 1):
        total_steps += steps
        possible_brands, portions, reachable = set(), 0, []
        for spot in board.spots:
            pos = spot["pos"]
            eligible = [i for i, (travel, fuel, refill) in enumerate(distances)
                        if travel.get(pos, float("inf")) <= total_steps and
                        (refill or fuel.get(pos, float("inf")) <= board.fuel_limit)]
            if eligible:
                possible_brands.add(spot["brand"])
                portions += min(spot["stocks"], len(eligible))
                reachable.append({"pos": pos, "patrol_indices": eligible})
        daily.append({"day": day, "types": len(possible_brands), "portions": portions,
                      "brands": sorted(possible_brands), "reachable": reachable})
    rules = (brands, days * brands, days * sum(min(s["stocks"], cars) for s in board.spots))
    count_bound = ((brands, days * brands, days * sum(min(s["stocks"], patrols) for s in board.spots))
                   if patrols else (0, 0, 0))
    reachability = (len(daily[-1]["brands"]), sum(d["types"] for d in daily), sum(d["portions"] for d in daily))
    assert all(a <= b <= c for a, b, c in zip(reachability, count_bound, rules))
    return {"rules": rules, "patrol_count": count_bound, "reachability": reachability,
            "daily": daily, "optimistic_refill": bool(supply_reachable),
            "seconds": time.perf_counter() - started}
