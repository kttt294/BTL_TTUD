"""Nộp lại các trận Practice của đội mình bằng tour, dùng gần hết thời hạn mỗi ngày như khi thi.

Mỗi bài: sao lưu config/state/replay/result hiện tại, reset Practice của đội mình, chạy runner
với ngân sách = daySeconds - dự phòng và chọn vai trò trong agent_selection_time_limit - dự phòng,
rồi đọc kết quả. Cuối cùng đọc điểm Practice mới nhất của các đội khác qua practice/score.
Chỉ dùng HEXUDON_TOKEN của đội mình.

Thời gian: máy chủ Practice không đo thời gian phản hồi (cumulative_response_time = 0) và chuyển
ngày ngay khi nộp, nên script tự đo hai con số mỗi ngày:
- thực tế Practice: từ lúc nhận xong /day tới lúc máy chủ nhận bài;
- ước tính trận tính giờ: chạy đúng cơ chế anytime của trận thi (bài nhanh 2–5 giây, bài cuối hết
  ngân sách); nếu bài cuối tốt hơn thì tính thời điểm bài cuối, không thì thời điểm bài nhanh, cộng
  độ trễ gửi bài. Bài được nộp là bài tốt hơn trong hai bài, như khi thi.

python -X utf8 experiments/run_practice_full_time.py --cases Q01 Q03
"""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
from fetch_peer_traffic import GAMES, TEAMS
from hexudon.live import MatchRunner
from hexudon.live_api import APIError, LiveAPI
from hexudon.tour import AnytimeSession, plan_key, reaches_bound


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class TimedAPI:
    """Bọc LiveAPI để ghi thời điểm nhận /day và thời điểm máy chủ nhận bài của từng ngày."""

    def __init__(self, api):
        self.api, self.team_id, self.timeout = api, api.team_id, api.timeout
        self.expires_at = getattr(api, "expires_at", None)
        self.day_ready, self.posted, self.post_latency = {}, {}, {}

    def request(self, method, endpoint, game_id=None, body=None, timeout=None):
        started = time.time()
        response = self.api.request(method, endpoint, game_id=game_id, body=body, timeout=timeout)
        if endpoint == "/api/game/day":
            self.day_ready[response["day"]] = time.time()
        if endpoint == "/api/game/practice/actions":
            self.posted[body["day"]] = time.time()
            self.post_latency[body["day"]] = time.time() - started
        return response


def anytime_predictor(workers, log):
    """Chạy đúng cơ chế anytime của trận tính giờ, ghi thời điểm bài nhanh/bài cuối."""

    def predictor(board, state, algorithm, seconds):
        started = time.time()
        steps = board.day_steps[state.day]
        session = AnytimeSession(board, state, steps, seconds, min(5., max(2., .12 * seconds)), workers)
        quick = session.quick()
        quick_at = time.time() - started
        record = {"day": state.day, "quick_at": round(quick_at, 2)}
        if quick is not None and reaches_bound(board, state, quick):
            # Như khi thi: bài nhanh đã chạm cận trên của ngày thì nộp luôn, không chờ bài cuối.
            record.update(final_at=None, improved=False, bound=True)
            log.append(record)
            return quick, {"algorithm": "tour", "anytime": record}
        final = session.final()
        final_at = time.time() - started
        quick_key = plan_key(board, state, quick) if quick is not None else None
        final_key = plan_key(board, state, final) if final is not None else None
        improved = final_key is not None and (quick_key is None or final_key > quick_key)
        record.update(final_at=round(final_at, 2), improved=improved, bound=False,
                      quick_key=quick_key, final_key=final_key)
        log.append(record)
        return (final if improved else quick), {"algorithm": "tour", "anytime": record}

    return predictor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", default=list(GAMES))
    parser.add_argument("--reserve", type=float, default=4.0, help="Giây chừa lại trong mỗi thời hạn")
    parser.add_argument("--workers", type=int, default=14)
    parser.add_argument("--output", default=str(ROOT / "results/full_time"))
    args = parser.parse_args()
    base_api = LiveAPI(ROOT / ".env")
    team = base_api.team_id
    stamp = time.strftime("%Y%m%d_%H%M%S")
    output = Path(args.output) / stamp
    summary = {}
    for case in args.cases:
        game = f"{GAMES[case]}:{team}"
        folder = output / case
        config = base_api.request("GET", "/api/game/config", game_id=game, timeout=30)
        for endpoint in ("state", "replay", "result"):
            try:
                save(folder / f"before_{endpoint}.json",
                     base_api.request("GET", f"/api/game/{endpoint}", game_id=game, timeout=30))
            except APIError as error:
                save(folder / f"before_{endpoint}.json", {"error": str(error)[:300]})
        save(folder / "config.json", config)
        base_api.request("POST", "/api/game/practice/reset", body={"game_id": game}, timeout=30)
        day_seconds = min(config.get("daySeconds") or [30.0]) - args.reserve
        selection = (config.get("agent_selection_time_limit") or 30.0) - args.reserve
        print(f"{case}: reset xong; {day_seconds:.0f} giây/ngày, chọn vai trò {selection:.0f} giây", flush=True)
        api, log = TimedAPI(base_api), []
        started = time.perf_counter()
        runner = MatchRunner(api, game, folder / "run", algorithm="tour", mode="practice",
                             seconds=day_seconds, reserve=args.reserve, selection_seconds=selection,
                             predictor=anytime_predictor(args.workers, log), team_id=team,
                             workers=args.workers)
        runner.run()
        result = base_api.request("GET", "/api/game/result", game_id=game, timeout=30)
        save(folder / "after_result.json", result)
        detail = result.get("detail", {}).get(team, {})
        score = [detail.get("distinct_types"), detail.get("cumulative_daily_types"), detail.get("total_servings")]
        practice = [api.posted[d] - api.day_ready[d] for d in sorted(api.posted) if d in api.day_ready]
        timed = []
        for record in log:
            latency = api.post_latency.get(record["day"], 0.2)
            chosen = record["final_at"] if record["improved"] else record["quick_at"]
            timed.append((chosen or record["quick_at"]) + latency)
        summary[case] = {
            "score": score, "types": runner.journal.get("types"),
            "server_response_time": detail.get("cumulative_response_time"),
            "practice_seconds": round(sum(practice), 1), "timed_estimate_seconds": round(sum(timed), 1),
            "days_improved": sum(r["improved"] for r in log), "days_at_bound": sum(r["bound"] for r in log),
            "per_day": log, "minutes": round((time.perf_counter() - started) / 60, 1)}
        print(f"{case}: BTC chấm {tuple(score)} với đội hình {runner.journal.get('types')} | thời gian Practice "
              f"{sum(practice):.1f} giây, ước tính trận tính giờ {sum(timed):.1f} giây", flush=True)
        save(output / "summary.json", summary)
    peers = {}
    for case in args.cases:
        peers[case] = {}
        for peer, name in TEAMS.items():
            if peer == team:
                continue
            try:
                peers[case][name] = base_api.request("GET", "/api/game/practice/score",
                                                     game_id=f"{GAMES[case]}:{peer}", timeout=20)
            except APIError as error:
                peers[case][name] = {"error": str(error)[:200]}
            time.sleep(0.3)
    save(output / "peer_scores.json", peers)
    print("Đã lưu", output)


if __name__ == "__main__":
    main()
