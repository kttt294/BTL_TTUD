"""Tập dượt trận tính giờ với máy chủ giả trong tiến trình, đồng hồ thật.

Máy chủ giả dùng config BTC, mở chọn vai trò trong agent_selection_time_limit giây, rồi mỗi ngày
mở trong daySeconds giây; bài nộp sau hạn bị từ chối (409). Có thể thêm độ trễ mạng và lỗi 5xx
ngẫu nhiên. Ghi thời điểm nộp hợp lệ cuối cùng mỗi ngày (thời gian phản hồi, tiêu chí 4).

python -X utf8 experiments/rehearse_timed.py --case Q01 --day-seconds 12 --latency 0.3 --errors 0.1
"""

import argparse
import contextlib
import io
import json
from pathlib import Path
import random
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.live import MatchRunner, predict
from hexudon.live_api import APIError
from hexudon.model import Board, State
from hexudon.simulator import simulate_day


class TimedServer:
    """Máy chủ giả: chọn vai trò, rồi từng ngày theo đồng hồ thật; mặc định chờ cả ngày nếu không nộp."""

    team_id = "62"
    timeout = 5.0

    def __init__(self, config, day_seconds=None, latency=0.0, errors=0.0, seed=0):
        self.config = dict(config)
        if day_seconds:
            self.config["daySeconds"] = [day_seconds] * len(config["daySteps"])
        self.board = Board.from_dict(self.config)
        self.selection = self.config.get("agent_selection_time_limit") or 30.0
        self.latency, self.errors, self.rng = latency, errors, random.Random(seed)
        self.lock = threading.Lock()
        self.started = time.monotonic()
        self.kinds, self.state, self.day, self.day_started = None, None, -1, None
        self.pending, self.submissions, self.response, self.last_valid = {}, [], [], {}

    def _advance(self):
        now = time.monotonic()
        if self.day == -1 and now - self.started >= self.selection:
            self.kinds = self.kinds or [0] * len(self.board.starts)
            self.state = State.initial(self.board, self.kinds)
            self.day, self.day_started = 0, self.started + self.selection
        while 0 <= self.day < len(self.board.day_steps):
            limit = self.config["daySeconds"][self.day]
            if now < self.day_started + limit:
                break
            steps = self.board.day_steps[self.day]
            actions = self.pending.get(self.day, [[-steps]] * len(self.board.starts))
            self.state = simulate_day(self.board, self.state, actions, steps).state
            # Không có bài hợp lệ thì coi như phản hồi hết cả ngày.
            self.response.append(self.last_valid.get(self.day, limit))
            self.day_started += limit
            self.day += 1

    def request(self, method, endpoint, game_id=None, body=None, timeout=None):
        if self.latency:
            time.sleep(self.rng.uniform(0, self.latency))
        if self.errors and self.rng.random() < self.errors:
            raise APIError(503, "lỗi máy chủ giả lập")
        with self.lock:
            self._advance()
            now = time.monotonic()
            finished = self.day >= len(self.board.day_steps)
            if endpoint == "/api/game/config":
                return dict(self.config)
            if endpoint == "/api/game/state":
                selecting = self.day == -1
                left = (self.started + self.selection - now) if selecting else (
                    None if finished else self.day_started + self.config["daySeconds"][self.day] - now)
                return {"status": "finished" if finished else ("selection" if selecting else "running"),
                        "day": max(self.day, 0) if not finished else self.day,
                        "day_deadline_in": None if selecting else left,
                        "selection_deadline_in": left if selecting else None, "selection_opens_in": 0,
                        "teams": {"62": {"types_selected": self.kinds is not None,
                                         "distinct_types": sorted(self.state.brands) if self.state else [],
                                         "cumulative_daily_types": self.state.daily_sum if self.state else 0,
                                         "total_servings": self.state.portions if self.state else 0,
                                         "submit_count": len([s for s in self.submissions if s[0] == self.day])}}}
            if endpoint == "/api/game/agent-types":
                if self.day != -1:
                    raise APIError(409, "hết giờ chọn vai trò")
                self.kinds = body["types"]
                return {"ok": True}
            if endpoint == "/api/game/day":
                return {"day": self.day, "endsAt": 1,
                        "agents": [{"kind": a.kind, "pos": a.pos, "fuel": a.fuel} for a in self.state.agents],
                        "others": [],
                        "traffics": [{"pos": p, "status": self.state.traffic.get(p, 0)}
                                     for p in range(self.board.width * self.board.height) if self.board.terrain(p) == 1]}
            if endpoint == "/api/game/result":
                return {"detail": {"62": {"score": list(self.state.score())}}}
            if endpoint == "/api/game/actions":
                if finished or body["day"] != self.day:
                    raise APIError(409, "ngày đã đóng")
                steps = self.board.day_steps[self.day]
                checked = simulate_day(self.board, self.state, body["actions"], steps)
                if not checked.valid:
                    raise APIError(422, str(checked.errors[:1]))
                self.pending[self.day] = body["actions"]
                elapsed = now - self.day_started
                self.submissions.append((self.day, round(elapsed, 2)))
                self.last_valid[self.day] = elapsed
                return {"ok": True}
        raise APIError(404, endpoint)


class Clock:
    monotonic = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="Q01")
    parser.add_argument("--day-seconds", type=float, help="Thu ngắn daySeconds để tập dượt nhanh")
    parser.add_argument("--selection-seconds", type=float, help="Thu ngắn thời gian chọn vai trò")
    parser.add_argument("--latency", type=float, default=0.0, help="Độ trễ tối đa mỗi request (giây)")
    parser.add_argument("--errors", type=float, default=0.0, help="Xác suất lỗi 503 mỗi request")
    parser.add_argument("--workers", type=int, default=14)
    parser.add_argument("--crash-at", type=float,
                        help="Ngắt runner (như Ctrl+C) ở giây thứ X kể từ đầu trận, rồi chạy lại runner mới cùng checkpoint")
    parser.add_argument("--restart-delay", type=float, default=5.0, help="Giây chờ trước khi chạy lại")
    args = parser.parse_args()
    config = json.loads((ROOT / "output/team_selection" / args.case / "config.json").read_text(encoding="utf-8"))
    if args.selection_seconds:
        config["agent_selection_time_limit"] = args.selection_seconds
    server = TimedServer(config, args.day_seconds, args.latency, args.errors)
    from functools import partial
    predictor = partial(predict, workers=args.workers)
    if args.crash_at:
        import _thread
        threading.Timer(args.crash_at, _thread.interrupt_main).start()

    def make_runner(folder):
        return MatchRunner(server, "rehearsal", folder, algorithm="tour", mode="timed", seconds=None,
                           selection_seconds=None, poll=0.3, clock=Clock, predictor=predictor,
                           workers=args.workers)

    with tempfile.TemporaryDirectory(dir=ROOT / "scratch") as folder:
        log = io.StringIO()
        started = time.monotonic()
        with contextlib.redirect_stdout(log):
            try:
                make_runner(folder).run()
            except KeyboardInterrupt:
                crashed_at = (server.day, round(time.monotonic() - (server.day_started or started), 1))
                print(f"Runner bị tắt ở ngày {crashed_at[0] + 1}, giây {crashed_at[1]}; chạy lại sau "
                      f"{args.restart_delay} giây.", flush=True)
                time.sleep(args.restart_delay)
                make_runner(folder).run()
    days = len(server.board.day_steps)
    missed = [d + 1 for d in range(days) if d not in server.pending]
    for line in log.getvalue().splitlines():
        if "bị tắt" in line:
            print(line)
    print(f"{args.case}: điểm {server.state.score()} | vai trò {server.kinds} | ngày không có bài: {missed}")
    print("Các lần nộp (ngày, giây kể từ đầu ngày):", server.submissions)
    print(f"Thời gian phản hồi lũy kế {sum(server.response):.1f} giây | chạy {time.monotonic() - started:.0f} giây")
    Path(ROOT / "results/rehearsal").mkdir(parents=True, exist_ok=True)
    (ROOT / f"results/rehearsal/{args.case}_{int(time.time())}.log").write_text(log.getvalue(), encoding="utf-8")


if __name__ == "__main__":
    main()
