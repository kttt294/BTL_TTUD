"""Lập kế hoạch Greedy và nhìn trước hai điểm, có trạm tiếp tế."""

from dataclasses import dataclass
import time

from .model import State
from .search import find_path
from .simulator import simulate_day


@dataclass
class Plan:
    actions: list[list[int]]
    elapsed: float
    fallback: bool
    errors: list[str]
    searches: int


def plan_day(board, state, steps, strategy="greedy", seconds=2.0, alpha=1.0, workers=1, seed=0):
    if strategy not in ("greedy", "lookahead", "tour"):
        raise ValueError("Chiến lược phải là greedy, lookahead hoặc tour.")
    started = time.perf_counter()
    if strategy == "tour":
        from .tour import plan_tour, plan_tour_parallel
        try:
            if workers > 1:
                actions = plan_tour_parallel(board, state, steps, seconds * 0.9, alpha, workers)
            else:
                actions = plan_tour(board, state, steps, seconds * 0.9, alpha, seed)
        except Exception as error:  # Lỗi lập trình trên bản đồ lạ không được làm mất ngày thi.
            print(f"Planner tour lỗi ({type(error).__name__}: {error}); dùng Greedy.", flush=True)
            actions = None
        if actions is not None:
            checked = simulate_day(board, state, actions, steps)
            if checked.valid:
                return Plan(actions, time.perf_counter() - started, False, [], 0)
        # Tuyến cả đội lỗi thì dùng Greedy với phần thời gian còn lại, không đứng chờ cả ngày.
        plan = plan_day(board, state, steps, "greedy", max(0.05, seconds - (time.perf_counter() - started)))
        plan.fallback = True
        return plan
    deadline = started + max(0, seconds)
    search_deadline = deadline
    actions = [[] for _ in state.agents]
    cache = {}
    searches = 0

    def path(start, goal, budget, fuel=None):
        nonlocal searches
        key = start, goal, budget, fuel
        if key not in cache:
            searches += 1
            route = find_path(board, start, goal, state.traffic, budget, fuel, deadline=search_deadline)
            if route.cutoff:
                return route
            cache[key] = route
        return cache[key]

    spot_at = {s["pos"]: s for s in board.spots}
    stock = {s["pos"]: s["stocks"] for s in board.spots}
    collected = set(state.brands)
    daily = set()
    visits = [set() for _ in state.agents]

    def reserve(car, pos):
        if pos in spot_at and pos not in visits[car]:
            visits[car].add(pos)
            if stock[pos] > 0:
                stock[pos] -= 1
                brand = spot_at[pos]["brand"]
                collected.add(brand)
                daily.add(brand)

    for car, agent in enumerate(state.agents):
        if agent.kind == 0:
            reserve(car, agent.pos)

    # Xe tiếp tế đi đến một điểm trung tâm rồi chờ, tạo lịch hẹn đơn giản và dễ kiểm tra.
    meeting_points = []
    if board.spots:
        center = min((s["pos"] for s in board.spots),
                     key=lambda p: sum(board.distance(p, s["pos"]) for s in board.spots))
    else:
        center = state.agents[0].pos
    for car, agent in enumerate(state.agents):
        if agent.kind != 1:
            continue
        route = path(agent.pos, center, steps - 1)
        if route.found:
            actions[car] = route.actions + [-(steps - route.steps)]
            meeting_points.append((center, route.steps))
        else:
            actions[car] = [-steps]
            meeting_points.append((agent.pos, 0))

    for car, agent in enumerate(state.agents):
        if agent.kind != 0:
            continue
        # Chia thời gian còn lại để xe đầu không chiếm hết ngân sách của các xe sau.
        patrol_left = sum(a.kind == 0 for a in state.agents[car:])
        now = time.perf_counter()
        search_deadline = now + max(0, deadline - now) / patrol_left
        pos, fuel, used = agent.pos, agent.fuel, 0

        def append_route(route):
            nonlocal pos, fuel, used
            for direction in route.actions:
                actions[car].append(direction)
                pos = board.neighbor(pos, direction)
                reserve(car, pos)
            used += route.steps
            fuel -= route.fuel

        def can_return(target, remaining_fuel):
            if not meeting_points:
                return True
            for hub, _ in sorted(meeting_points, key=lambda item: board.distance(target, item[0])):
                back = path(target, hub, max(board.day_steps), remaining_fuel)
                if back.found:
                    return True
            return False

        while used < steps and time.perf_counter() < search_deadline:
            targets = [s for s in board.spots if stock[s["pos"]] > 0 and s["pos"] not in visits[car]]
            # Giới hạn số ứng viên để Lookahead không dùng hết thời gian nộp bài.
            targets.sort(key=lambda s: (s["brand"] in collected, s["brand"] in daily,
                                        board.distance(pos, s["pos"]), s["pos"]))
            candidates = []
            for spot in targets[:6]:
                route = path(pos, spot["pos"], steps - used, fuel)
                if route.found and can_return(spot["pos"], fuel - route.fuel):
                    candidates.append((spot, route))
            if candidates:
                best = None
                for spot, route in candidates:
                    brand = spot["brand"]
                    gain = (int(brand not in collected), int(brand not in daily), 1, -route.steps)
                    if strategy == "lookahead":
                        following = [s for s in targets if s["pos"] != spot["pos"]]
                        following.sort(key=lambda s: board.distance(spot["pos"], s["pos"]))
                        for second in following[:3]:
                            next_route = path(spot["pos"], second["pos"], steps - used - route.steps,
                                              fuel - route.fuel)
                            if (next_route.found and can_return(second["pos"],
                                                               fuel - route.fuel - next_route.fuel)):
                                new_brands = {brand, second["brand"]}
                                pair_gain = (len(new_brands - collected), len(new_brands - daily), 2,
                                             -route.steps - next_route.steps)
                                gain = max(gain, pair_gain)
                    if best is None or gain > best[0]:
                        best = gain, route
                append_route(best[1])
                continue

            # Xe tuần tra đến điểm hẹn, đợi xe tiếp tế tới và ở chung ít nhất một step.
            refills = []
            if fuel < board.fuel_limit:
                for hub, arrival in meeting_points:
                    route = path(pos, hub, steps - used, fuel)
                    if route.found:
                        waiting = max(1, arrival - (used + route.steps) + 1)
                        if used + route.steps + waiting < steps:
                            refills.append((route.steps + waiting, hub, route, waiting))
            if not refills:
                break
            _, _, route, waiting = min(refills, key=lambda item: item[0])
            append_route(route)
            actions[car].append(-waiting)
            used += waiting
            fuel = board.fuel_limit
        if used < steps:
            actions[car].append(-(steps - used))

    checked = simulate_day(board, state, actions, steps)
    fallback = not checked.valid
    if fallback:
        actions = [[-steps] for _ in state.agents]
    return Plan(actions, time.perf_counter() - started, fallback, checked.errors, searches)


def choose_types(board, seconds=20.0, strategy="greedy", limit=16):
    """Giữ giao diện cũ, chuyển việc đánh giá đội hình sang mô đun riêng."""
    from .team_selection import select_types
    return select_types(board, seconds, strategy, limit)
