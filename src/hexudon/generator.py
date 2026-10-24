"""Sinh bản đồ có thể tái hiện, với toàn bộ vùng đi được liên thông."""

import random
from .model import Board


def generate_board(size=8, seed=42, days=4, steps=80, fuel=40):
    rng = random.Random(seed)
    cells = [[rng.choices([0, 1, 2], [6, 3, 1])[0] for _ in range(size)] for _ in range(size)]
    board = Board(cells, [], [], [steps] * days, fuel)
    # Chỉ đặt ao nếu phần còn lại của bản đồ vẫn liên thông.
    for pos in rng.sample(range(size * size), size * size // 8):
        row, col = divmod(pos, size)
        old = cells[row][col]
        cells[row][col] = 3
        walkable = {p for p in range(size * size) if board.terrain(p) != 3}
        reached, pending = set(), [min(walkable)]
        while pending:
            current = pending.pop()
            if current not in reached:
                reached.add(current)
                pending.extend(p for _, p in board.neighbors(current) if p not in reached)
        if reached != walkable:
            cells[row][col] = old
    plain = [p for p in range(size * size) if board.terrain(p) == 0]
    rng.shuffle(plain)
    board.starts = plain[:4]
    positions = plain[4:4 + min(24, size * size // 4)]
    brand_count = max(1, len(positions) // 2)
    board.spots = [{"pos": p, "brand": i % brand_count, "stocks": rng.randint(1, 4)}
                   for i, p in enumerate(positions)]
    return board


# Tỷ lệ địa hình đo trên cả 9 config Practice của BTC: đồng bằng, đường, núi, ao.
BTC_TERRAIN = (0.21, 0.34, 0.20, 0.25)


def _connect(cells, width, height, rng):
    """Đổi ô đi được bị cô lập với ô ao sát vùng lớn nhất, giữ nguyên tỷ lệ địa hình."""
    board = Board(cells, [], [], [1], 1)
    size = width * height
    while True:
        walkable = [p for p in range(size) if board.terrain(p) != 3]
        seen, components = set(), []
        for start in walkable:
            if start in seen:
                continue
            group, stack = [], [start]
            seen.add(start)
            while stack:
                pos = stack.pop()
                group.append(pos)
                for _, nxt in board.neighbors(pos):
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            components.append(group)
        if len(components) <= 1:
            return
        largest = max(components, key=len)
        main = set(largest)
        border = [p for p in range(size) if board.terrain(p) == 3 and _touches(board, p, main)]
        stray = [p for group in components if group is not largest for p in group]
        if not border:
            return
        for pos in stray:
            if not border:
                break
            target = border.pop(rng.randrange(len(border)))
            (r1, c1), (r2, c2) = divmod(pos, width), divmod(target, width)
            cells[r2][c2], cells[r1][c1] = cells[r1][c1], 3


def _touches(board, pos, group):
    row, col = divmod(pos, board.width)
    shift = 1 if row % 2 == 0 else 0
    for dr, dc in [(-1, shift - 1), (-1, shift), (0, 1), (1, shift), (1, shift - 1), (0, -1)]:
        r, c = row + dr, col + dc
        if 0 <= r < board.height and 0 <= c < board.width and r * board.width + c in group:
            return True
    return False


def generate_config(seed, profile="btc"):
    """Sinh config dạng JSON của BTC (dùng được cho Board.from_dict và máy chủ giả).

    profile "btc": giống các bài Practice (30–32 ô, 4–6 xe, 10 ngày, kho ≈ số xe).
    profile "wide": trải phạm vi luật (8–32 ô, 3–8 xe, 4–10 ngày, kho 1..số xe).
    profile "mix": như wide nhưng tỷ lệ địa hình, mật độ điểm và tỷ lệ loại cũng ngẫu nhiên.
    Địa hình rải ngẫu nhiên độc lập (btc, wide theo BTC_TERRAIN như bản đồ thật); mọi ô đi được liên thông.
    """
    rng = random.Random(seed)
    if profile == "btc":
        width, height = rng.choice([30, 30, 32]), rng.choice([30, 30, 32])
        agents, days = rng.randint(4, 6), 10
    else:
        width, height = rng.randint(8, 32), rng.randint(8, 32)
        agents, days = rng.randint(3, 8), rng.randint(4, 10)
    size = width * height
    shares = BTC_TERRAIN
    if profile == "mix":
        road, mountain, pond = rng.uniform(0.15, 0.45), rng.uniform(0.05, 0.30), rng.uniform(0.05, 0.30)
        shares = (max(0.15, 1 - road - mountain - pond), road, mountain, pond)
        shares = tuple(x / sum(shares) for x in shares)
    counts = [round(share * size) for share in shares]
    counts[0] += size - sum(counts)
    flat = [t for t, n in enumerate(counts) for _ in range(n)]
    rng.shuffle(flat)
    cells = [flat[r * width:(r + 1) * width] for r in range(height)]
    _connect(cells, width, height, rng)
    plains = [p for p in range(size) if cells[p // width][p % width] == 0]
    rng.shuffle(plains)
    starts = plains[:agents]
    density, variety = ((0.5, 1.5), (0.3, 0.8)) if profile == "mix" else ((0.9, 1.1), (0.45, 0.68))
    spot_count = min(len(plains) - agents, max(4, round((width + height) / 2 * rng.uniform(*density))))
    positions = plains[agents:agents + spot_count]
    brand_count = max(1, min(spot_count, round(spot_count * rng.uniform(*variety))))
    brands = list(range(brand_count)) + [rng.randrange(brand_count) for _ in range(spot_count - brand_count)]
    rng.shuffle(brands)
    if profile == "btc":
        stock = lambda: agents if rng.random() < 0.7 else agents - 1
    else:
        stock = lambda: rng.randint(1, agents)
    spots = [{"pos": p, "brand": b, "stocks": max(1, stock())} for p, b in zip(positions, brands)]
    low, high = (60, 256) if profile == "btc" else (30, 256)
    busy = rng.randint(2, 5)
    return {"map": {"height": height, "width": width, "cells": cells}, "spots": spots, "agents": starts,
            "daySteps": [rng.randint(low, high) for _ in range(days)],
            "fuelLimits": rng.randint(150, 470) if profile == "btc" else rng.randint(30, 500),
            "busyThreshold": busy, "jammedThreshold": busy + rng.randint(1, 6), "players": 1,
            "daySeconds": [rng.choice([30.0, 45.0])] * days, "agent_selection_time_limit": rng.choice([30.0, 60.0]),
            "generator": {"seed": seed, "profile": profile}}


def to_dict(board):
    return {"map": {"height": board.height, "width": board.width, "cells": board.cells},
            "spots": board.spots, "agents": board.starts, "daySteps": board.day_steps,
            "fuelLimits": board.fuel_limit, "busyThreshold": board.busy_threshold,
            "jammedThreshold": board.jammed_threshold, "players": 1}
