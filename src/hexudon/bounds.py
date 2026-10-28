"""Cận trên từ các điều kiện cần về tiếp cận và độ dài đường giữa các điểm.

Không giả định ghé được mọi điểm: cận chỉ chứng minh không thể vượt, không bảo đảm đạt được.
"""

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


def tree_edges(indices, spots, distances):
    """Cạnh của cây khung nhỏ nhất nối các điểm trong indices, xếp tăng dần.

    Đường ghé k điểm khác nhau trong một ngày là một cây khung của k điểm đó. Theo tính chất
    tham lam của matroid, cạnh nhỏ thứ j của cây này không nhỏ hơn cạnh thứ j của cây khung
    nhỏ nhất, nên tổng k-1 cạnh đầu là cận dưới cho thời gian (hoặc nhiên liệu) của đường.
    Trọng số lấy chiều nhỏ hơn giữa hai điểm vì chi phí tính theo ô nguồn, không đối xứng.
    """
    infinity = float("inf")
    edges = sorted((min(distances[i].get(spots[j], infinity), distances[j].get(spots[i], infinity)), i, j)
                   for a, i in enumerate(indices) for j in indices[a + 1:])
    root = {i: i for i in indices}

    def find(i):
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i

    chosen = []
    for weight, i, j in edges:
        a, b = find(i), find(j)
        if a != b and weight < infinity:
            root[a] = b
            chosen.append(weight)
    return chosen


NG_SIZE = 10


def ng_visits(times, starts, horizon, size=NG_SIZE):
    """best[t]: số điểm tối đa ghé được trong t step (t = 0..horizon), nới lỏng ng-route.

    Mỗi điểm nhớ `size` điểm gần nó nhất; đường không được quay lại điểm đang nhớ. Mọi đường thật
    (không lặp điểm) đều thỏa nên đây là cận trên. Nó loại các vòng lặp rẻ quanh một cụm điểm mà cận
    cây khung không loại được, nên chặt hơn hẳn ở ngày ngắn (Q06, 91 step: 15 so với 18 điểm).
    times[i][j]: step ngắn nhất từ điểm i tới j theo đúng chiều; starts: (điểm, step tới điểm đó).
    """
    n = len(times)
    near = []
    for i in range(n):
        order = sorted((j for j in range(n) if j != i), key=lambda j: times[i][j] + times[j][i])[:size]
        near.append(sum(1 << j for j in order) | (1 << i))
    best = [0] * (horizon + 1)
    buckets = [[] for _ in range(horizon + 1)]
    seen = {}
    for v, offset in starts:
        if offset <= horizon:
            buckets[offset].append((v, 1 << v, 1))
    for t in range(horizon + 1):
        for v, mask, count in buckets[t]:
            # Cùng điểm, cùng trí nhớ, tới muộn hơn mà không ghé nhiều hơn thì bị trội.
            if seen.get((v, mask), 0) >= count:
                continue
            seen[v, mask] = count
            best[t] = max(best[t], count)
            for w, step in enumerate(times[v]):
                if not mask >> w & 1 and t + step <= horizon:
                    buckets[t + step].append((w, (mask & near[w]) | (1 << w), count + 1))
        buckets[t] = None
    for t in range(1, horizon + 1):
        best[t] = max(best[t], best[t - 1])
    return best


def route_visits(board, travel, fuel, refill, eligible, between, trees, paths=None):
    """Số điểm tối đa một xe tuần tra thu được mỗi ngày và cả trận.

    between = (thời gian, nhiên liệu) từ mỗi điểm; trees lưu cây khung theo vùng liên thông.
    paths = (ng_visits từ ô xuất phát, ng_visits từ điểm bất kỳ) nếu tính cận chặt.
    Ngày 1 xe phải đi từ ô xuất phát tới điểm đầu tiên; từ ngày 2 giả định lạc quan xe đã
    đứng sẵn ở một điểm. Không có tiếp tế thì cả trận chỉ có một bình nhiên liệu: mỗi ngày,
    chặng thứ j tốn ít nhất cạnh nhiên liệu thứ j, nên chọn các chặng rẻ nhất trên mọi ngày.
    """
    spots = [s["pos"] for s in board.spots]
    reachable = tuple(i for i, pos in enumerate(spots) if pos in travel)
    if not reachable:
        return [0] * len(board.day_steps), 0
    if reachable not in trees:
        trees[reachable] = tuple(tree_edges(reachable, spots, costs) for costs in between)
    time_edges, fuel_edges = trees[reachable]
    first_time = min(travel[spots[i]] for i in reachable)
    first_fuel = min(fuel.get(spots[i], float("inf")) for i in reachable)
    visits, offers = [], []
    for day, steps in enumerate(board.day_steps):
        budget = steps - (first_time if day == 0 else 0)
        count, used = 0, 0
        if budget >= 0:
            count = 1
            while count - 1 < len(time_edges) and used + time_edges[count - 1] <= budget:
                used += time_edges[count - 1]
                count += 1
        if paths is not None:
            # Hai cận đều hợp lệ nên lấy cận nhỏ hơn: ng-route chặt ở ngày ngắn, cây khung ở ngày dài.
            first, anywhere = paths
            count = min(count, first[steps] if day == 0 else anywhere[steps])
        count = min(count, eligible[day])
        visits.append(count)
        offers += fuel_edges[:max(0, count - 1)]
    if refill:
        return visits, sum(visits)
    left = board.fuel_limit - first_fuel
    if left < 0:
        return [0] * len(visits), 0
    extra = 0
    for cost in sorted(offers):
        if cost > left:
            break
        left -= cost
        extra += 1
    return visits, sum(1 for count in visits if count) + extra


def score_bounds(board, kinds, cache=None, tight=False):
    """Tính cận đầu trận, từng ngày và toàn trận cho một đội hình cố định.

    cache dùng lại Dijkstra và cây khung khi tính cho nhiều đội hình trên cùng bản đồ.
    tight=True thêm cận ng-route (vài giây mỗi bản đồ, dùng khi báo cáo; bộ chọn đội hình dùng cận nhanh).
    """
    started = time.perf_counter()
    State.initial(board, kinds)
    cache = {} if cache is None else cache

    def costs(pos, fuel=False):
        if (pos, fuel) not in cache:
            cache[pos, fuel] = shortest_costs(board, pos, fuel)
        return cache[pos, fuel]

    brands = len({spot["brand"] for spot in board.spots})
    days, cars, patrols = len(board.day_steps), len(kinds), kinds.count(0)
    supply_reachable = set()
    for start, kind in zip(board.starts, kinds):
        if kind == 1:
            # Nới lỏng: xe tiếp tế có thể nạp ở mọi ô cùng vùng liên thông ngay từ đầu.
            supply_reachable.update(costs(start))
    distances = []
    for start, kind in zip(board.starts, kinds):
        if kind == 0:
            distances.append((costs(start), costs(start, True), start in supply_reachable))
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
    spots = [s["pos"] for s in board.spots]
    between = ([costs(pos) for pos in spots], [costs(pos, True) for pos in spots])
    cars, trees = [], cache.setdefault("trees", {})
    times = None
    if tight:
        far = 10 ** 6
        times = [[0 if i == j else row.get(spots[j], far) for j in range(len(spots))] for i, row in enumerate(between[0])]
        if "ng_any" not in cache:
            cache["ng_any"] = ng_visits(times, [(i, 0) for i in range(len(spots))], max(board.day_steps))
    patrol_starts = [start for start, kind in zip(board.starts, kinds) if kind == 0]
    for index, (travel, fuel, refill) in enumerate(distances):
        eligible = [sum(index in spot["patrol_indices"] for spot in d["reachable"]) for d in daily]
        paths = None
        if tight:
            start = patrol_starts[index]
            if ("ng_start", start) not in cache:
                offsets = [(i, travel[pos]) for i, pos in enumerate(spots) if pos in travel]
                cache["ng_start", start] = ng_visits(times, offsets, board.day_steps[0])
            paths = cache["ng_start", start], cache["ng_any"]
        cars.append(route_visits(board, travel, fuel, refill, eligible, between, trees, paths))
    for day, entry in enumerate(daily):
        entry["max_visits"] = [visits[day] for visits, _ in cars]
    totals = sum(total for _, total in cars)
    route = (min(reachability[0], totals),
             sum(min(d["types"], sum(d["max_visits"])) for d in daily),
             min(totals, sum(min(d["portions"], sum(d["max_visits"])) for d in daily)))
    assert all(a <= b for a, b in zip(route, reachability))
    return {"rules": rules, "patrol_count": count_bound, "reachability": reachability,
            "route": route, "daily": daily, "optimistic_refill": bool(supply_reachable),
            "seconds": time.perf_counter() - started}
