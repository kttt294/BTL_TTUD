"""Chấm offline các câu hỏi mock contest bằng simulator, đúng quy trình thi của runner.

Mỗi câu: chọn vai trò trong agent_selection_time_limit − 4 giây (select_types tour), rồi mỗi ngày
chạy AnytimeSession như trận tính giờ: bài nhanh 2–5 giây, kiểm tra mỗi CHECK_EVERY giây, nộp lại
khi tốt hơn (cách nhau ≥ MIN_GAP giây, tối đa MID_SUBMITS lần giữa ngày) và bài cuối nếu tốt hơn.
Bài được tính là bài nộp cuối cùng; thời gian phản hồi ước tính = thời điểm nộp cuối (+0,3 giây
gửi bài). Giao thông chỉ do đội mình tạo (không có dữ liệu các đội khác của mock contest).

python -X utf8 experiments/score_offline.py results/mock_contest/configs/*.json
"""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.live import CHECK_EVERY, MID_SUBMITS, MIN_GAP
from hexudon.model import Board, State
from hexudon.simulator import simulate_day
from hexudon.team_selection import select_types
from hexudon.tour import AnytimeSession, plan_key, reaches_bound, warm_up


def play_day(board, state, seconds, workers):
    started = time.time()
    steps = board.day_steps[state.day]
    session = AnytimeSession(board, state, steps, seconds, min(5., max(2., .12 * seconds)), workers,
                             every=CHECK_EVERY)
    current = session.quick()
    submitted_at, submissions = time.time() - started, 1
    if current is None or reaches_bound(board, state, current):
        return current, submitted_at, submissions
    key, last, sent = plan_key(board, state, current), time.time(), 0
    for mark in session.marks:
        candidate = session.best_until(mark)
        if candidate is None or sent >= MID_SUBMITS or time.time() - last < MIN_GAP:
            continue
        new = plan_key(board, state, candidate)
        if new is not None and new > key:
            current, key, last, sent = candidate, new, time.time(), sent + 1
            submitted_at, submissions = time.time() - started, submissions + 1
            if reaches_bound(board, state, current):
                return current, submitted_at, submissions
    final = session.final()
    new = plan_key(board, state, final) if final is not None else None
    if new is not None and new > key:
        current, submitted_at, submissions = final, time.time() - started, submissions + 1
    return current, submitted_at, submissions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("configs", nargs="+")
    parser.add_argument("--reserve", type=float, default=4.0)
    parser.add_argument("--workers", type=int, default=14)
    parser.add_argument("--output", default=str(ROOT / "results/mock_contest/offline_scores.json"))
    args = parser.parse_args()
    warm_up(args.workers)
    output = Path(args.output)
    results = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    for path in args.configs:
        name = Path(path).stem
        config = json.loads(Path(path).read_text(encoding="utf-8"))
        board = Board.from_dict(config)
        selection = (config.get("agent_selection_time_limit") or 30.) - args.reserve
        kinds, _, _ = select_types(board, selection, "tour")
        state = State.initial(board, kinds)
        brands = len({s["brand"] for s in board.spots})
        times, counts, lost = [], [], []
        for day, steps in enumerate(board.day_steps):
            seconds = (config.get("daySeconds") or [30.] * len(board.day_steps))[day] - args.reserve
            actions, at, count = play_day(board, state, seconds, args.workers)
            checked = simulate_day(board, state, actions, steps)
            if not checked.valid:
                raise ValueError(f"{name} ngày {day + 1}: {checked.errors[:2]}")
            before = state.daily_sum
            state = checked.state
            times.append(round(at + 0.3, 2))
            counts.append(count)
            if state.daily_sum - before < brands:
                lost.append(day + 1)
        results[name] = {"score": list(state.score()), "types": kinds, "max_u": brands,
                         "max_d": brands * len(board.day_steps), "response_seconds": round(sum(times), 1),
                         "day_times": times, "submissions": counts, "d_lost_days": lost,
                         "size": f"{board.width}x{board.height}", "agents": len(board.starts),
                         "days": len(board.day_steps), "day_seconds": config.get("daySeconds", [None])[0]}
        output.write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"{name}: {tuple(state.score())} / tối đa U {brands}, D {brands * len(board.day_steps)} | đội hình {kinds} | "
              f"phản hồi lũy kế {sum(times):.1f} giây | số lần nộp/ngày {counts} | mất D {lost}", flush=True)


if __name__ == "__main__":
    main()
