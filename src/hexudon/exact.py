"""Quy hoạch động chính xác cho bài nhỏ: một xe, không đường và không tiếp tế."""

from dataclasses import dataclass
import time


@dataclass
class ExactResult:
    score: tuple[int, int, int]
    actions: list[list[list[int]]]
    states: int
    seconds: float


def solve_small(board):
    if len(board.starts) != 1 or any(c == 1 for row in board.cells for c in row):
        raise ValueError("Bộ giải chỉ hỗ trợ một xe tuần tra và bản đồ không có đường.")
    if len(board.spots) > 10 or sum(board.day_steps) > 32:
        raise ValueError("Chỉ dùng bộ giải chính xác cho bài nhỏ (tối đa 10 điểm, 32 step).")
    started = time.perf_counter()
    brands = {b: i for i, b in enumerate(sorted({s['brand'] for s in board.spots}))}
    spots = {s['pos']: (i, brands[s['brand']]) for i, s in enumerate(board.spots)}
    # Khóa đầu ngày là vị trí, nhiên liệu và tập loại toàn trận.
    frontier = {(board.starts[0], board.fuel_limit, 0): (0, 0, [])}
    count = 0
    for steps in board.day_steps:
        layers = [{} for _ in range(steps + 1)]
        for (pos, fuel, all_types), (daily_sum, portions, history) in frontier.items():
            layers[0][pos, fuel, all_types, 0, 0] = (daily_sum, portions, history, [])
        for elapsed in range(steps):
            for key, value in layers[elapsed].items():
                count += 1
                pos, fuel, all_types, today, visited = key
                daily_sum, portions, history, commands = value
                duration, cost = board.cost(pos, {})
                choices = [(-1, pos, 1, 0)]
                choices += [(direction, target, duration, cost)
                            for direction, target in board.neighbors(pos) if cost <= fuel]
                for command, target, ticks, spent in choices:
                    end = elapsed + ticks
                    if end > steps:
                        continue
                    new_all, new_today, new_visited, gained = all_types, today, visited, 0
                    # Trong chuyển động nhiều step, xe còn ở nguồn trước step đến đích.
                    positions = [pos, target] if ticks > 1 else [target]
                    for location in positions:
                        if location in spots:
                            index, brand = spots[location]
                            if not new_visited & (1 << index):
                                new_visited |= 1 << index
                                new_all |= 1 << brand
                                new_today |= 1 << brand
                                gained += 1
                    next_key = target, fuel - spent, new_all, new_today, new_visited
                    next_value = daily_sum, portions + gained, history, commands + [command]
                    old = layers[end].get(next_key)
                    if old is None or next_value[:2] > old[:2]:
                        layers[end][next_key] = next_value
        frontier = {}
        for (pos, fuel, all_types, today, _), value in layers[steps].items():
            daily_sum, portions, history, commands = value
            key = pos, fuel, all_types
            candidate = daily_sum + today.bit_count(), portions, history + [[commands]]
            old = frontier.get(key)
            if old is None or candidate[:2] > old[:2]:
                frontier[key] = candidate
    key, value = max(frontier.items(), key=lambda item: (item[0][2].bit_count(), *item[1][:2]))
    return ExactResult((key[2].bit_count(), *value[:2]), value[2], count,
                       time.perf_counter() - started)
