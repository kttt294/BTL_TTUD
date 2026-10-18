"""Năm thuật toán tìm đường với ràng buộc bước và nhiên liệu."""

from collections import deque
from dataclasses import dataclass
import heapq
import time


ALGORITHMS = ("dfs", "bfs", "dijkstra", "greedy", "astar")


@dataclass
class Path:
    actions: list[int]
    steps: int
    fuel: int
    expanded: int
    found: bool = True
    cutoff: bool = False


def find_path(board, start, goal, traffic, step_limit, fuel_limit=None,
              algorithm="astar", deadline=None):
    if algorithm not in ALGORITHMS:
        raise ValueError("Thuật toán tìm đường không được hỗ trợ.")
    if board.terrain(start) == 3 or board.terrain(goal) == 3:
        return Path([], 0, 0, 0, False)
    fuel_limit = step_limit * 2 if fuel_limit is None else fuel_limit
    # Mỗi nhãn lưu vị trí, thời gian, nhiên liệu, số cạnh, cha và hướng đi.
    labels = [(start, 0, 0, 0, -1, -1)]
    active = {start: [0]}
    queue = deque([0])
    heap = [(0, 0)]
    expanded = 0

    def dominates(a, b):
        resources = a[1] <= b[1] and a[2] <= b[2]
        return resources and (algorithm != "bfs" or a[3] <= b[3])

    while queue if algorithm in ("bfs", "dfs") else heap:
        if deadline is not None and time.perf_counter() >= deadline:
            return Path([], 0, 0, expanded, False, True)
        if algorithm == "bfs":
            index = queue.popleft()
        elif algorithm == "dfs":
            index = queue.pop()
        else:
            _, index = heapq.heappop(heap)
        current = labels[index]
        pos, steps, fuel, hops, _, _ = current
        if index not in active.get(pos, []):
            continue
        expanded += 1
        if pos == goal:
            actions = []
            while labels[index][4] != -1:
                actions.append(labels[index][5])
                index = labels[index][4]
            return Path(actions[::-1], steps, fuel, expanded)
        move_steps, move_fuel = board.cost(pos, traffic)
        for direction, target in board.neighbors(pos):
            candidate = (target, steps + move_steps, fuel + move_fuel, hops + 1, index, direction)
            if candidate[1] > step_limit or candidate[2] > fuel_limit:
                continue
            old_indices = active.get(target, [])
            if any(dominates(labels[old], candidate) for old in old_indices):
                continue
            new_index = len(labels)
            labels.append(candidate)
            active[target] = [old for old in old_indices if not dominates(candidate, labels[old])]
            active[target].append(new_index)
            if algorithm in ("bfs", "dfs"):
                queue.append(new_index)
            else:
                heuristic = board.distance(target, goal)
                priority = candidate[1] if algorithm == "dijkstra" else heuristic
                if algorithm == "astar":
                    priority += candidate[1]
                heapq.heappush(heap, (priority, new_index))
    return Path([], 0, 0, expanded, False)
