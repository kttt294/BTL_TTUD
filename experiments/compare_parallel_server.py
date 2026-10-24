"""So tour một và nhiều tiến trình trên Practice, cùng đội hình và ngân sách.

Script sao lưu lượt hiện tại trước khi reset. Mọi ngày đều đọc giao thông thật,
kiểm tra output rồi mới nộp. Cuối mỗi bài, script khôi phục lượt tốt nhất giữa
lượt có sẵn và các lượt thử; không thay điểm tốt bằng một kết quả thử kém hơn.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.live import authoritative_state
from hexudon.live_api import LiveAPI, APIError
from hexudon.live_storage import run_lock
from hexudon.model import Board
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day
from hexudon.tour import warm_up
from compare_api import compare


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def score(result, team):
    detail = result["detail"][team]
    return [detail[k] for k in ("distinct_types", "cumulative_daily_types", "total_servings")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", default=["Q01", "Q02", "Q06"])
    parser.add_argument("--workers", nargs="+", type=int, default=[1, 4])
    parser.add_argument("--seconds", type=float, default=5.)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--objective", choices=["score", "lookahead"], default="score")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.seconds <= 0 or any(n < 1 for n in args.workers):
        parser.error("Ngân sách và số tiến trình phải dương.")
    output = Path(args.output)
    api = LiveAPI(ROOT / ".env", timeout=20)
    if api.team_id != "62":
        raise ValueError("Thử nghiệm này chỉ reset Practice riêng của đội 62.")
    team = api.team_id
    games = json.loads((ROOT / "docs/api/sample_games.json").read_text(encoding="utf-8"))

    def request(method, endpoint, game, body=None):
        for attempt in range(3):
            try:
                result = api.request(method, endpoint, game_id=game if method == "GET" else None,
                                     body=body)
                time.sleep(.15)
                return result
            except APIError as error:
                if method != "GET" or error.status not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
                time.sleep(1)

    def reset(game, kinds):
        request("POST", "/api/game/practice/reset", game, {"game_id": game})
        request("POST", "/api/game/agent-types", game, {"game_id": game, "types": kinds})

    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    save(output / "settings.json", {**vars(args), "time_utc": datetime.now(timezone.utc).isoformat(),
                                    "comparison": "cùng nhánh src_procon, đội hình và hạn giờ; không dùng Greedy dự phòng"})
    for case in args.cases:
        if summary.get(case, {}).get("complete"):
            continue
        game = games[case] + ":" + team
        folder = output / case
        lock_dir = ROOT / "results/live" / f"{games[case]}_{team}"
        lock_dir.mkdir(parents=True, exist_ok=True)
        with run_lock(lock_dir):
            before_path = folder / "before.json"
            if before_path.exists():
                before = json.loads(before_path.read_text(encoding="utf-8"))
            else:
                before = {name: request("GET", "/api/game/" + name, game)
                          for name in ("config", "state", "actions", "replay", "result")}
                save(before_path, before)
            config = before["config"]
            if config.get("players") != 1:
                raise ValueError("Không reset trận nhiều đội.")
            if args.seconds > min(config.get("daySeconds") or [30]) - 4:
                raise ValueError("Ngân sách thử phải chừa ít nhất bốn giây trong hạn cấu hình.")
            board = Board.from_dict(config)
            first = next(t for t in before["replay"]["days"][0]["teams"] if str(t["team_id"]) == team)
            kinds = first["kinds"]
            old_score = score(before["result"], team)
            old_plans = {str(row["day"]): row["plan"] for row in before["actions"]["actions"]
                         if str(row["team_id"]) == team}
            if len(old_plans) != len(board.day_steps):
                raise ValueError("Cần lượt trước hoàn tất để giữ mốc đối chiếu và khôi phục an toàn.")
            best_score, best_plans, best_name = old_score, old_plans, "before"
            rows = []
            for workers in args.workers:
                run_dir = folder / f"workers_{workers}"
                completed = run_dir / "result.json"
                if completed.exists():
                    row = json.loads(completed.read_text(encoding="utf-8"))
                    plans = json.loads((run_dir / "plans.json").read_text(encoding="utf-8"))
                else:
                    if workers > 1 and not warm_up(workers):
                        raise RuntimeError("Không khởi động được các tiến trình; chưa reset trận.")
                    reset(game, kinds)
                    journal, records, plans = {"brands": []}, [], {}
                    print(f"{case}: bắt đầu {workers} tiến trình, {args.seconds}s/ngày, đội hình {kinds}", flush=True)
                    for day, steps in enumerate(board.day_steps):
                        raw = request("GET", "/api/game/day", game)
                        remote = request("GET", "/api/game/state", game)
                        if raw["day"] != day:
                            raise ValueError("Ngày máy chủ không đúng lượt thử; dừng để tránh nộp nhầm.")
                        state = authoritative_state(board, raw, remote["teams"][team], journal)
                        plan = plan_day(board, state, steps, "tour", args.seconds, workers=workers,
                                        seed=args.seed, parallel_objective=args.objective)
                        if plan.fallback:
                            raise RuntimeError("Tour chuyển dự phòng; không được tính là kết quả thử tour.")
                        checked = simulate_day(board, state, plan.actions, steps)
                        if not checked.valid:
                            raise ValueError(checked.errors)
                        record = {"day": day, "planning_seconds": plan.elapsed,
                                  "score": list(checked.state.score()), "parallel": plan.details}
                        save(run_dir / f"day_{day:02d}.json", {"input": raw, "actions": plan.actions, **record})
                        request("POST", "/api/game/practice/actions", game,
                                {"game_id": game, "day": day, "actions": plan.actions})
                        plans[str(day)] = plan.actions
                        records.append(record)
                        journal = {"brands": sorted(checked.state.brands), "daily_sum": checked.state.daily_sum,
                                   "road_history": checked.state.road_history}
                        print(f"{case}/{workers}: ngày {day+1}, {checked.state.score()}, {plan.elapsed:.2f}s", flush=True)
                    final = request("GET", "/api/game/result", game)
                    replay = request("GET", "/api/game/replay", game)
                    history = request("GET", "/api/game/actions", game)
                    audit = compare(config, replay, history)
                    if audit["mismatch_count"] or score(final, team) != list(checked.state.score()):
                        raise ValueError("Điểm hoặc replay máy chủ khác mô phỏng; dừng khảo sát.")
                    row = {"workers": workers, "score": score(final, team), "days": records,
                           "max_planning_seconds": max(r["planning_seconds"] for r in records),
                           "fallback_days": 0, "audit": audit}
                    for name, value in (("server_result", final), ("replay", replay), ("actions", history),
                                        ("plans", plans), ("result", row)):
                        save(run_dir / f"{name}.json", value)
                rows.append(row)
                if tuple(row["score"]) > tuple(best_score):
                    best_score, best_plans, best_name = row["score"], plans, f"workers_{workers}"
                print(case, workers, "BTC", row["score"], "trước thử", old_score, flush=True)
            # Giữ kết quả tốt nhất trên server, kể cả khi lượt nhiều tiến trình kém hơn lượt trước.
            current = score(request("GET", "/api/game/result", game), team)
            if current != best_score:
                print(case, "khôi phục lượt tốt nhất", best_name, best_score, flush=True)
                reset(game, kinds)
                for day in range(len(board.day_steps)):
                    request("POST", "/api/game/practice/actions", game,
                            {"game_id": game, "day": day, "actions": best_plans[str(day)]})
                current = score(request("GET", "/api/game/result", game), team)
                if current != best_score:
                    raise ValueError("Khôi phục không khớp điểm; đã giữ toàn bộ bản sao lưu.")
            summary[case] = {"before_score": old_score, "types": kinds, "trials": rows,
                             "retained": best_name, "retained_score": current, "complete": True}
            save(summary_path, summary)
    print("Đã lưu kết quả tại", output, flush=True)


if __name__ == "__main__":
    main()
