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


def to_dict(board):
    return {"map": {"height": board.height, "width": board.width, "cells": board.cells},
            "spots": board.spots, "agents": board.starts, "daySteps": board.day_steps,
            "fuelLimits": board.fuel_limit, "busyThreshold": board.busy_threshold,
            "jammedThreshold": board.jammed_threshold, "players": 1}
