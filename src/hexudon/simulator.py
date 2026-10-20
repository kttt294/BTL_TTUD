"""Mô phỏng từng step và kiểm tra kế hoạch cho một hoặc nhiều đội."""

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass


@dataclass
class DayResult:
    valid: bool
    errors: list[str]
    state: object = None
    trace: list = None


@dataclass
class MatchResult:
    valid: bool
    errors: list[str]
    states: dict = None
    traces: dict = None


def validate_timing(board, state, actions, steps):
    errors = []
    if not isinstance(actions, list) or len(actions) != len(state.agents):
        return ["Số mảng lệnh không khớp số xe."]
    for car, commands in enumerate(actions):
        if not isinstance(commands, list):
            errors.append(f"Xe {car}: kế hoạch phải là một mảng.")
            continue
        pos, total = state.agents[car].pos, 0
        for index, command in enumerate(commands):
            if type(command) is not int or command > 5:
                errors.append(f"Xe {car}, lệnh {index}: mã lệnh không hợp lệ.")
                break
            if command < 0:
                total -= command
            else:
                target = board.neighbor(pos, command)
                if target is None:
                    errors.append(f"Xe {car}, lệnh {index}: ô đích là ao hoặc ngoài bản đồ.")
                    break
                total += board.cost(pos, state.traffic)[0]
                pos = target
            if total > steps:
                errors.append(f"Xe {car}, lệnh {index}: vượt quỹ {steps} step.")
                break
        if total != steps:
            errors.append(f"Xe {car}: kế hoạch dùng {total}/{steps} step.")
    return errors


def simulate_match_day(board, states, orders, steps, record=False):
    if not states or set(states) != set(orders):
        return MatchResult(False, ["Mỗi đội phải có một trạng thái và một kế hoạch."])
    if type(steps) is not int or steps <= 0:
        return MatchResult(False, ["Quỹ step phải là số nguyên dương."])
    errors = []
    traffic = next(iter(states.values())).traffic
    for team, state in states.items():
        if state.traffic != traffic:
            errors.append(f"Đội {team}: giao thông phải giống các đội còn lại.")
        errors.extend(f"Đội {team}: {error}" for error in validate_timing(board, state, orders[team], steps))
    if errors:
        return MatchResult(False, errors)

    results = deepcopy(states)
    spot_brands = {s["pos"]: s["brand"] for s in board.spots}
    contexts = {}
    for team, state in results.items():
        count = len(state.agents)
        contexts[team] = {
            "stocks": {s["pos"]: s["stocks"] for s in board.spots},
            "visited": [set() for _ in range(count)], "today": set(),
            "roads": Counter(), "pointers": [0] * count, "remaining": [0] * count,
            "destinations": [None] * count, "fuel_costs": [0] * count,
            "arrived_today": [False] * count,
            "initial_portions": state.portions, "trace": []}

    def add_frame(team, step, collected):
        state, context = results[team], contexts[team]
        context["trace"].append({
            "step": step, "positions": [a.pos for a in state.agents],
            "fuel": [a.fuel for a in state.agents],
            "servings": state.portions - context["initial_portions"],
            "types": len(context["today"]), "collected": collected})

    # Replay BTC ghi trạng thái gốc ở frame 0, chưa thu hàng hoặc tiếp tế.
    if record:
        for team in results:
            add_frame(team, 0, [])
    for tick in range(steps):
        for team, state in results.items():
            c = contexts[team]
            for car, agent in enumerate(state.agents):
                if c["remaining"][car] == 0:
                    command = orders[team][car][c["pointers"][car]]
                    c["pointers"][car] += 1
                    if command < 0:
                        c["remaining"][car] = -command
                        c["destinations"][car] = None
                        c["fuel_costs"][car] = 0
                    else:
                        duration, fuel = board.cost(agent.pos, traffic)
                        if agent.kind == 0 and agent.fuel < fuel:
                            return MatchResult(False, [f"Đội {team}, xe {car}, step {tick}: không đủ nhiên liệu."])
                        c["remaining"][car] = duration
                        c["destinations"][car] = board.neighbor(agent.pos, command)
                        c["fuel_costs"][car] = fuel if agent.kind == 0 else 0
            # Xe vẫn ở ô nguồn cho tới khi hoàn thành lệnh, nhiên liệu cập nhật lúc đến.
            for car, agent in enumerate(state.agents):
                c["remaining"][car] -= 1
                if c["remaining"][car] == 0 and c["destinations"][car] is not None:
                    agent.pos = c["destinations"][car]
                    agent.fuel -= c["fuel_costs"][car]
                    c["arrived_today"][car] = True
            supply_positions = {a.pos for a in state.agents if a.kind == 1}
            collected = []
            for car, agent in enumerate(state.agents):
                pos = agent.pos
                if agent.kind == 0 and pos in supply_positions:
                    agent.fuel = board.fuel_limit
                # BTC đếm hiện diện và thu hàng sau khi cập nhật vị trí của step.
                # API BTC bỏ khoảng chuyển tiếp khi xe rời vị trí đầu ngày trên đường.
                # Sau lần đến ô đầu tiên, vị trí hiển thị được đếm bình thường.
                if (board.terrain(pos) == 1 and
                        (c["destinations"][car] is None or c["arrived_today"][car])):
                    c["roads"][pos] += 1
                if agent.kind == 0 and pos in c["stocks"] and pos not in c["visited"][car]:
                    c["visited"][car].add(pos)
                    if c["stocks"][pos] > 0:
                        c["stocks"][pos] -= 1
                        c["today"].add(spot_brands[pos])
                        state.brands.add(spot_brands[pos])
                        state.portions += 1
                        collected.append(pos)
            if record:
                add_frame(team, tick + 1, collected)

    total_roads = Counter()
    for team, state in results.items():
        c = contexts[team]
        state.day += 1
        state.daily_sum += len(c["today"])
        state.road_history = (state.road_history + [dict(c["roads"])])[-2:]
        for history in state.road_history:
            total_roads.update(history)
    next_traffic = {}
    for pos in range(board.width * board.height):
        if board.terrain(pos) == 1:
            average = total_roads[pos] / len(results)
            next_traffic[pos] = (2 if average >= board.jammed_threshold else
                                 1 if average >= board.busy_threshold else 0)
    for state in results.values():
        state.traffic = dict(next_traffic)
    traces = {team: c["trace"] for team, c in contexts.items()} if record else None
    return MatchResult(True, [], results, traces)


def simulate_day(board, state, actions, steps, record=False):
    """Giữ giao diện một đội để các thuật toán hiện tại tiếp tục dùng được."""
    result = simulate_match_day(board, {"team": state}, {"team": actions}, steps, record)
    if not result.valid:
        return DayResult(False, result.errors)
    trace = result.traces["team"] if record else None
    return DayResult(True, [], result.states["team"], trace)
