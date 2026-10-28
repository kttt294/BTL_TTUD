"""Chọn kế hoạch ngày theo điểm sau ngày hôm sau, chạy song song trong runner thi.

Mỗi tiến trình lập kế hoạch hôm nay với một mức phạt ô đường (tour.ROAD_WEIGHTS), rồi lập thử ngày
mai từ trạng thái cuối ngày; kế hoạch được chấm bằng điểm (U, D, Q) sau hai ngày. Giải đấu giả lập
50 đội (experiments/tournament_sim.py, 28/10) cho +12 đến +16 suất và hạng 1-3 trên 5 map Mock, chủ
yếu nhờ kết thúc ngày ở vị trí và nhiên liệu tốt cho ngày mai, và giữ đủ D ở map ít nhiên liệu.

Trận tính giờ: mặt đường ngày mai do mọi đội tạo ra (lượt của một đội chỉ vài phần trăm), nên khi
nhìn trước giả định mặt đường ngày mai giống hôm nay. Practice: một đội nên giữ mặt đường mô phỏng.
"""

import time

from .simulator import simulate_day
from .tour import ROAD_WEIGHTS, ROAD_WEIGHTS_FEW, _pool, plan_tour

# Phần ngân sách ngày dành cho các phương án; phần còn lại để chờ kết quả, chấm và nộp lại.
USABLE = 0.85
PLAN_SHARE, LOOK_SHARE = 0.6, 0.3


def two_day_value(board, state, actions, following, look_seconds, keep_traffic, seed=0):
    """Điểm (U, D, Q) sau ngày mai nếu nộp `actions` hôm nay; None nếu kế hoạch không hợp lệ."""
    checked = simulate_day(board, state, actions, board.day_steps[state.day])
    if not checked.valid:
        return None
    value = checked.state.score()
    if following:
        tomorrow = checked.state
        if keep_traffic:
            tomorrow.traffic = dict(state.traffic)
        plan = plan_tour(board, tomorrow, following, look_seconds, 1.0, seed)
        if plan is not None:
            after = simulate_day(board, tomorrow, plan, following)
            if after.valid:
                value = after.state.score()
    return value


def _job(args):
    board, state, steps, following, plan_seconds, look_seconds, weights, seed, keep_traffic = args
    actions = plan_tour(board, state, steps, plan_seconds, 1.0, seed, weights)
    if actions is None:
        return None
    value = two_day_value(board, state, actions, following, look_seconds, keep_traffic, seed)
    return None if value is None else (actions, value, weights)


class TwoDaySession:
    """Gửi các phương án vào nhóm tiến trình ngay đầu ngày; choose() so với bài đã nộp."""

    def __init__(self, board, state, steps, budget, workers, keep_traffic=True):
        self.board, self.state, self.keep_traffic = board, state, keep_traffic
        day = state.day
        self.following = board.day_steps[day + 1] if day + 1 < len(board.day_steps) else 0
        weights = ROAD_WEIGHTS if workers >= 3 else ROAD_WEIGHTS_FEW
        rounds = -(-len(weights) // max(1, workers))
        per = max(1.0, budget * USABLE / rounds)
        self.plan_seconds, self.look_seconds = per * PLAN_SHARE, per * LOOK_SHARE
        self.until = time.time() + budget * USABLE + 1.0
        jobs = [(board, state, steps, self.following, self.plan_seconds, self.look_seconds, w, seed,
                 keep_traffic) for seed, w in enumerate(weights)]
        self.futures = [_pool(max(1, workers)).submit(_job, job) for job in jobs]

    def choose(self, submitted):
        """Phương án có điểm sau hai ngày cao hơn bài đã nộp, hoặc None; kèm thông tin để ghi log."""
        # Chấm bài đã nộp trong tiến trình chính trong lúc các tiến trình con còn chạy.
        base = two_day_value(self.board, self.state, submitted, self.following, self.look_seconds,
                             self.keep_traffic)
        best = None
        for future in self.futures:
            try:
                result = future.result(timeout=max(0.0, self.until - time.time()))
            except Exception:
                future.cancel()
                continue
            if result is not None and (best is None or result[1] > best[1]):
                best = result
        info = {'submitted_value': base, 'best_value': best[1] if best else None,
                'weights': best[2] if best else None, 'candidates': len(self.futures)}
        if best is None or base is not None and best[1] <= base:
            return None, info
        return best[0], info
