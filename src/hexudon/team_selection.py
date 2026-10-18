"""Chọn vai trò xe tại các vị trí xuất phát bằng mô phỏng toàn trận một đội."""

from itertools import product
import time

from .model import State
from .simulator import simulate_day


def candidate_types(board, limit=16):
    """Luôn giữ toàn tuần tra, từng xe tiếp tế và hai cấu hình của bộ chọn cũ."""
    count = len(board.starts)
    all_types = [list(kinds) for kinds in product((0, 1), repeat=count) if 0 in kinds]
    if not board.spots:
        return [[0] * count]
    hub = min((s["pos"] for s in board.spots),
              key=lambda pos: sum(board.distance(pos, s["pos"]) for s in board.spots))
    center = min(board.starts,
                 key=lambda pos: sum(board.distance(pos, s["pos"]) for s in board.spots))
    old_order = sorted(range(count), key=lambda i: board.distance(board.starts[i], center))
    options = [[0] * count]
    for supplies in (1, 2):
        if supplies < count:
            options.append([int(i in old_order[:supplies]) for i in range(count)])
    for supply in range(count):
        kinds = [int(i == supply) for i in range(count)]
        if kinds not in options and 0 in kinds:
            options.append(kinds)

    def rank(kinds):
        supplies = [board.starts[i] for i, kind in enumerate(kinds) if kind == 1]
        patrols = [board.starts[i] for i, kind in enumerate(kinds) if kind == 0]
        travel = sum(board.distance(pos, hub) for pos in supplies)
        coverage = sum(min(board.distance(pos, s["pos"]) for s in board.spots) for pos in patrols)
        return len(supplies), travel + coverage, kinds

    # Khoảng cách lục giác chỉ dùng sàng lọc; mô phỏng mới quyết định đội hình thắng.
    for kinds in sorted(all_types, key=rank):
        if len(options) >= max(limit, len(board.starts) + 2):
            break
        if kinds not in options:
            options.append(kinds)
    return options


def evaluate_types(board, kinds, day_seconds, strategy="greedy", deadline=None):
    from .planner import plan_day

    started = time.perf_counter()
    state = State.initial(board, kinds)
    days = []
    for steps in board.day_steps:
        if deadline is not None and time.perf_counter() >= deadline:
            break
        budget = day_seconds
        if deadline is not None:
            budget = min(budget, max(0, deadline - time.perf_counter()))
        plan = plan_day(board, state, steps, strategy, budget)
        checked = simulate_day(board, state, plan.actions, steps)
        if not checked.valid:
            raise ValueError("Kế hoạch không vượt qua simulator khi chọn đội hình.")
        state = checked.state
        days.append({"score": state.score(), "actions": plan.actions,
                     "fallback": plan.fallback, "planning_seconds": plan.elapsed})
    return {"types": kinds[:], "score": state.score(), "complete": len(days) == len(board.day_steps),
            "days": days, "seconds": time.perf_counter() - started,
            "day_seconds": day_seconds, "strategy": strategy}


def select_types(board, seconds=20.0, strategy="greedy", limit=16):
    started = time.perf_counter()
    deadline = started + max(0, seconds)
    candidates = candidate_types(board, limit)
    # Chừa thời gian cho mô phỏng, kiểm tra và ghi kết quả; hạn giờ vẫn là giới hạn mềm.
    day_seconds = min(0.15, max(0, seconds * 0.4) /
                      (1.3 * len(candidates) * len(board.day_steps)))
    best_types, best_score, records = [0] * len(board.starts), None, []
    for kinds in candidates:
        if time.perf_counter() >= deadline or day_seconds == 0:
            break
        trial = evaluate_types(board, kinds, day_seconds, strategy, deadline)
        trial["phase"] = "screen"
        records.append(trial)
        # Không dùng điểm của một trận bị cắt giữa chừng để chọn đội hình.
        if trial["complete"] and (best_score is None or tuple(trial["score"]) > best_score):
            best_types, best_score = kinds[:], tuple(trial["score"])
    complete = [r for r in records if r["complete"]]
    if complete and time.perf_counter() < deadline:
        # Giữ hai đối chứng quen thuộc và đội hình thắng của bộ chọn cũ khi đánh giá lại.
        old = [r for r in complete if r["types"] in candidates[:3]]
        old_best = max(old, key=lambda r: tuple(r["score"]))["types"]
        finalists = [[0] * len(board.starts), [0] * (len(board.starts) - 1) + [1], old_best]
        finalists = [k for i, k in enumerate(finalists) if k not in finalists[:i] and 0 in k]
        for trial in sorted(complete, key=lambda r: tuple(r["score"]), reverse=True):
            if trial["types"] not in finalists:
                finalists.append(trial["types"])
            if len(finalists) >= 5:
                break
        remaining = max(0, deadline - time.perf_counter())
        refine_seconds = min(0.15, remaining * 0.85 / (len(finalists) * len(board.day_steps)))
        refined_best = None
        for kinds in finalists:
            if time.perf_counter() >= deadline:
                break
            trial = evaluate_types(board, kinds, refine_seconds, strategy, deadline)
            trial["phase"] = "refine"
            records.append(trial)
            if trial["complete"] and (refined_best is None or tuple(trial["score"]) > refined_best):
                best_types, refined_best = kinds[:], tuple(trial["score"])
    return best_types, records, time.perf_counter() - started
