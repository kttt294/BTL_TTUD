"""Giao diện dòng lệnh để chạy demo, lập kế hoạch và kiểm tra output."""

import argparse
import json
from pathlib import Path

from .generator import generate_board, to_dict
from .bounds import score_bounds
from .model import Agent, Board, State
from .planner import choose_types, plan_day
from .simulator import simulate_day


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Bài tập lớn Thuật toán ứng dụng HEXUDON")
    parser.add_argument("command", choices=["demo", "plan", "validate", "select", "bounds"])
    parser.add_argument("--config")
    parser.add_argument("--state", help="JSON trạng thái đầu ngày, cộng lịch sử brands nếu có")
    parser.add_argument("--starts", nargs="+", type=int)
    type_options = parser.add_mutually_exclusive_group()
    type_options.add_argument("--types", nargs="+", type=int)
    type_options.add_argument("--types-file", help="Đọc danh sách vai trò từ output của lệnh select")
    parser.add_argument("--day", type=int, default=1, help="Ngày theo cách đếm của người dùng, bắt đầu từ 1")
    parser.add_argument("--strategy", choices=["greedy", "lookahead"], default="greedy")
    parser.add_argument("--seconds", type=float, help="Mặc định select dùng 20 giây, lệnh khác dùng 2 giây")
    parser.add_argument("--candidates", type=int, default=16, help="Số đội hình sàng lọc cho lệnh select")
    parser.add_argument("--selection-log", help="Lưu chi tiết mô phỏng đội hình vào JSON")
    parser.add_argument("--output", default="results/output.txt")
    parser.add_argument("--actions", help="File output cần kiểm tra")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--size", type=int, default=8)
    args = parser.parse_args()
    if args.seconds is None:
        args.seconds = 20.0 if args.command == "select" else 2.0
    if args.command != "demo" and not args.config:
        parser.error("Lệnh này cần --config.")
    if args.command == "validate" and not args.actions:
        parser.error("Kiểm tra kế hoạch cần --actions.")
    if args.size < 8 or args.size > 32:
        parser.error("Kích thước demo phải nằm trong khoảng 8–32.")
    board = Board.from_dict(read_json(args.config), args.starts) if args.config else generate_board(args.size, args.seed)
    if not 1 <= args.day <= len(board.day_steps):
        parser.error("Ngày nằm ngoài số ngày của trận.")
    if args.command == "select":
        kinds, trials, elapsed = choose_types(board, args.seconds, args.strategy, args.candidates)
        write_json(args.output, kinds)
        detail = {"types": kinds, "trials": trials, "seconds": elapsed}
        if args.selection_log:
            write_json(args.selection_log, detail)
        print(json.dumps({"types": kinds, "seconds": elapsed,
                          "completed": sum(t["complete"] for t in trials),
                          "trials": [{k: v for k, v in t.items() if k != "days"} for t in trials]},
                         ensure_ascii=False, indent=2))
        return
    if args.types_file:
        args.types = read_json(args.types_file)
    kinds = args.types if args.types is not None else [0, 0, 0, 1][:len(board.starts)]
    if args.types is None and len(board.starts) != 4:
        kinds = [0] * (len(board.starts) - 1) + [1]
    if args.command == "bounds":
        if args.state or args.day != 1:
            parser.error("Lệnh bounds tính cận từ cấu hình đầu trận, không nhận trạng thái giữa trận.")
        result = score_bounds(board, kinds)
        write_json(args.output, result)
        print(json.dumps({k: v for k, v in result.items() if k != "daily"}, ensure_ascii=False, indent=2))
        return
    state = State.initial(board, kinds)
    if args.state:
        raw = read_json(args.state)
        agents = raw["agents"]
        if len(agents) != len(board.starts):
            parser.error("Số xe trong trạng thái không khớp cấu hình.")
        if any(type(a["kind"]) is not int or a["kind"] not in (0, 1)
               or type(a["pos"]) is not int or not 0 <= a["pos"] < board.width * board.height
               or board.terrain(a["pos"]) == 3 or type(a["fuel"]) is not int
               or not 0 <= a["fuel"] <= board.fuel_limit for a in agents):
            parser.error("Trạng thái xe không hợp lệ.")
        state.agents = [Agent(a["kind"], a["pos"], a["fuel"]) for a in agents]
        state.traffic = {t["pos"]: t["status"] for t in raw.get("traffics", [])}
        if any(type(p) is not int or not 0 <= p < board.width * board.height
               or board.terrain(p) != 1 or type(s) is not int or s not in (0, 1, 2)
               for p, s in state.traffic.items()):
            parser.error("Dữ liệu giao thông không hợp lệ.")
        if args.day > 1 and "traffics" not in raw:
            parser.error("Ngày sau ngày 1 cần trường traffics từ máy chủ.")
        state.brands = set(raw.get("brands", []))
        if args.day > 1 and "brands" not in raw:
            print("Lưu ý: thiếu lịch sử brands, chiến lược chưa biết các loại đã thu trước đó.")
        state.day = args.day - 1
    elif args.day != 1:
        parser.error("Lập kế hoạch từ ngày 2 cần --state; không dùng lại vị trí và nhiên liệu ngày 1.")
    if args.command == "validate":
        checked = simulate_day(board, state, read_json(args.actions), board.day_steps[args.day - 1])
        print(json.dumps({"valid": checked.valid, "errors": checked.errors}, ensure_ascii=False, indent=2))
        if not checked.valid:
            raise SystemExit(1)
        return
    if args.command == "plan":
        planned = plan_day(board, state, board.day_steps[args.day - 1], args.strategy, args.seconds)
        checked = simulate_day(board, state, planned.actions, board.day_steps[args.day - 1])
        if not checked.valid:
            raise ValueError("Kế hoạch dự phòng không vượt qua bộ kiểm tra.")
        write_json(args.output, planned.actions)
        print(json.dumps({"output": args.output, "seconds": planned.elapsed,
                          "fallback": planned.fallback, "errors": planned.errors,
                          "searches": planned.searches}, ensure_ascii=False, indent=2))
        return
    replay, metrics = [], []
    for day, steps in enumerate(board.day_steps, 1):
        planned = plan_day(board, state, steps, args.strategy, args.seconds)
        checked = simulate_day(board, state, planned.actions, steps, record=True)
        if not checked.valid:
            raise ValueError("Demo phát hiện kế hoạch không hợp lệ.")
        replay.append({"day": day, "actions": planned.actions, "trace": checked.trace})
        state = checked.state
        row = {"day": day, "score": state.score(), "seconds": round(planned.elapsed, 4),
               "fallback": planned.fallback, "searches": planned.searches}
        metrics.append(row)
        print(json.dumps(row, ensure_ascii=False))
    write_json(args.output, {"config": to_dict(board), "types": kinds, "days": replay, "metrics": metrics})


if __name__ == "__main__":
    main()
