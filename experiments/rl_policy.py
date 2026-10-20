"""Chính sách PPO chọn đích; không gọi Greedy, Lookahead hoặc bộ chọn dự phòng."""

import heapq
from pathlib import Path
import sys
import time

import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from hexudon.model import State
from hexudon.simulator import simulate_day

FEATURES = 18
MAX_TARGETS = 65


class TargetPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(FEATURES, 64), nn.Tanh(),
                                     nn.Linear(64, 64), nn.Tanh())
        self.actor = nn.Linear(64, 1)
        self.critic = nn.Linear(64, 1)

    def forward(self, features, mask):
        hidden = self.encoder(features)
        logits = self.actor(hidden).squeeze(-1).masked_fill(~mask, -1e9)
        pooled = (hidden * mask.unsqueeze(-1)).sum(-2) / mask.sum(-1, keepdim=True)
        return torch.distributions.Categorical(logits=logits), self.critic(pooled).squeeze(-1)


class RouteExecutor:
    """Cố định một đường ngắn nhất theo step cho mỗi đích, không tối ưu chọn đích."""
    def __init__(self, board):
        self.board = board
        self.cache = {}

    def routes(self, start, traffic):
        key = start, tuple(sorted((p, s) for p, s in traffic.items() if s))
        if key in self.cache:
            return self.cache[key]
        board = self.board
        distances, parents = {start: 0}, {}
        heap = [(0, start)]
        while heap:
            cost, pos = heapq.heappop(heap)
            if cost != distances[pos]:
                continue
            duration, _ = board.cost(pos, traffic)
            for direction, target in board.neighbors(pos):
                new = cost + duration
                if new < distances.get(target, float('inf')):
                    distances[target] = new
                    parents[target] = pos, direction
                    heapq.heappush(heap, (new, target))
        paths = {}
        for spot in board.spots:
            goal = spot['pos']
            if goal not in distances:
                continue
            pos, reverse = goal, []
            while pos != start:
                pos, direction = parents[pos]
                reverse.append(direction)
            paths[goal] = reverse[::-1]
        self.cache[key] = paths
        return paths


def play(board, model=None, mode='policy', sample=False, executor=None, collect=False):
    """Mọi ngày đều do chính sách chọn; kế hoạch lỗi làm dừng phép đo, không thay kế hoạch."""
    executor = executor or RouteExecutor(board)
    state = State.initial(board, [0] * len(board.starts))
    trajectory, plans, decisions = [], [], []
    spot_at = {s['pos']: s for s in board.spots}
    max_seconds = 0
    for day, steps in enumerate(board.day_steps):
        started = time.perf_counter()
        actions = [[] for _ in state.agents]
        stock = {s['pos']: s['stocks'] for s in board.spots}
        known, daily = set(state.brands), set()
        visited = [set() for _ in state.agents]
        day_begin = len(trajectory)

        def reserve(car, pos):
            if pos in spot_at and pos not in visited[car]:
                visited[car].add(pos)
                if stock[pos] > 0:
                    stock[pos] -= 1
                    known.add(spot_at[pos]['brand'])
                    daily.add(spot_at[pos]['brand'])

        for car, agent in enumerate(state.agents):
            reserve(car, agent.pos)
        day_decisions = 0
        for car, agent in enumerate(state.agents):
            pos, fuel, used = agent.pos, agent.fuel, 0
            while used < steps:
                paths = executor.routes(pos, state.traffic)
                candidates, features = [], []
                for spot in board.spots:
                    goal = spot['pos']
                    if goal in visited[car] or stock[goal] <= 0 or goal not in paths:
                        continue
                    route = paths[goal]
                    location, total_steps, total_fuel = pos, 0, 0
                    prefix, duration, spent, blocked = [], 0, 0, False
                    for direction in route:
                        dt, df = board.cost(location, state.traffic)
                        if not blocked and duration + dt <= steps - used:
                            prefix.append(direction)
                            duration += dt
                            spent += df
                        else:
                            blocked = True
                        total_steps += dt
                        total_fuel += df
                        location = board.neighbor(location, direction)
                    # Đây là mặt nạ khả thi trên đường cố định, không xếp hạng mục tiêu.
                    if not prefix or total_fuel > fuel:
                        continue
                    new = float(spot['brand'] not in known)
                    fresh = float(spot['brand'] not in daily)
                    near = sum(board.distance(goal, s['pos']) <= 4 and stock[s['pos']] > 0
                               for s in board.spots) / len(board.spots)
                    features.append([new, fresh, stock[goal] / len(state.agents),
                        total_steps / max(board.day_steps), total_fuel / board.fuel_limit,
                        fuel / board.fuel_limit, (steps-used) / steps,
                        day / len(board.day_steps), car / len(state.agents), near,
                        (goal % board.width) / board.width, (goal // board.width) / board.height,
                        len(known) / len(board.spots), len(daily) / len(board.spots),
                        float(duration == total_steps), 0., board.width / 32.,
                        sum(board.day_steps[day+1:]) / sum(board.day_steps)])
                    candidates.append((goal, prefix, duration, spent))
                if not candidates:
                    break
                if len(candidates) >= MAX_TARGETS:
                    raise ValueError('Số điểm vượt kích thước mạng; cần tăng MAX_TARGETS.')
                features.append([0.] * 15 + [1., board.width / 32.,
                                           sum(board.day_steps[day+1:]) / sum(board.day_steps)])
                features += [[0.] * FEATURES] * (MAX_TARGETS - len(features))
                x = torch.tensor(features, dtype=torch.float32)
                mask = torch.arange(MAX_TARGETS) <= len(candidates)
                if mode == 'nearest':
                    action = min(range(len(candidates)), key=lambda i: (features[i][3], i))
                elif mode == 'random':
                    action = int(torch.randint(len(candidates) + 1, (1,)))
                else:
                    with torch.no_grad():
                        distribution, value = model(x, mask)
                        selected = distribution.sample() if sample else distribution.logits.argmax()
                        action = int(selected)
                        if collect:
                            trajectory.append(dict(x=x, mask=mask, action=action,
                                log_prob=float(distribution.log_prob(selected)),
                                value=float(value), reward=0.))
                day_decisions += 1
                if action == len(candidates):
                    break
                goal, route, duration, spent = candidates[action]
                for direction in route:
                    actions[car].append(direction)
                    pos = board.neighbor(pos, direction)
                    reserve(car, pos)
                used += duration
                fuel -= spent
            if used < steps:
                actions[car].append(-(steps-used))
        result = simulate_day(board, state, actions, steps)
        if not result.valid:
            raise ValueError(f'Kế hoạch RL không hợp lệ, không dùng fallback: {result.errors}')
        if collect and len(trajectory) > day_begin:
            before, after = state.score(), result.state.score()
            # Chỉ điểm thật của simulator mới sinh reward, không thưởng dự đoán đặt chỗ.
            trajectory[-1]['reward'] += 10*(after[0]-before[0]) + after[1]-before[1] + .05*(after[2]-before[2])
        state = result.state
        plans.append(actions)
        decisions.append(day_decisions)
        max_seconds = max(max_seconds, time.perf_counter()-started)
    return dict(score=state.score(), actions=plans, decisions=decisions,
                fallback_calls=0, max_day_seconds=max_seconds), trajectory
