"""Practice: chạy nhiều lượt cả trận offline song song, nộp lượt điểm cao nhất lên máy chủ.

Practice chỉ có một đội tạo giao thông và simulator khớp máy chủ, nên chuỗi lệnh đã mô phỏng được
máy chủ tái hiện y hệt. Mỗi lượt tour dao động khoảng ±15–20 suất, nên lấy lượt tốt nhất trong
nhiều lượt (nhiều seed, mọi vị trí đặt xe tiếp tế) cho điểm cao hơn một lượt chạy trực tiếp.
Chỉ reset khi lượt tốt nhất hơn điểm đang có trên máy chủ; trước mỗi ngày đối chiếu trạng thái
máy chủ với mô phỏng, lệch thì dừng.

Xe nhà làm tắc các trục đường (Q01: 596 suất, gần bằng 574 khi mọi đường luôn đông, so với 694 khi
đường luôn thông). Mỗi lượt vì vậy thử vài mức phạt ô đường sắp tắc cho từng ngày và chọn theo điểm
sau ngày hôm sau (simulate_rollout): Q01/Q03/Q08 được 616/686/707 so với 596/654/686 một lượt cũ.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from .bounds import score_bounds
from .live_api import LiveAPI, list_matches
from .map_analysis import NETWORK_ERRORS, percent, report_standings
from .model import Board, State
from .planner import plan_day
from .simulator import simulate_day
from .tour import ROAD_WEIGHTS

ROOT = Path(__file__).resolve().parents[2]
ACTIVE_MINUTES = 15



def simulate_match(config, kinds, seconds, seed):
    """Một lượt cả trận bằng tour (một tiến trình); trả điểm và lệnh từng ngày."""
    board = Board.from_dict(config)
    state = State.initial(board, kinds)
    days = []
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, "tour", seconds, seed=seed)
        checked = simulate_day(board, state, plan.actions, steps)
        if not checked.valid:
            return None
        days.append(plan.actions)
        state = checked.state
    return {"score": list(state.score()), "kinds": kinds, "seed": seed, "days": days}


def simulate_rollout(config, kinds, seconds, look, seed):
    """Một lượt cả trận; mỗi ngày thử ROAD_WEIGHTS, giữ kế hoạch có điểm (U, D, Q) cao nhất sau khi
    lập kế hoạch nhanh (look giây) cho ngày hôm sau trên mặt đường mà hôm nay để lại."""
    board = Board.from_dict(config)
    state = State.initial(board, kinds)
    days = []
    for day, steps in enumerate(board.day_steps):
        best = None
        for weights in ROAD_WEIGHTS:
            actions = plan_day(board, state, steps, "tour", seconds, seed=seed, road_weights=weights).actions
            checked = simulate_day(board, state, actions, steps)
            if not checked.valid:
                continue
            value = checked.state.score()
            if day + 1 < len(board.day_steps) and look > 0:
                following = board.day_steps[day + 1]
                tomorrow = plan_day(board, checked.state, following, "tour", look, seed=seed).actions
                after = simulate_day(board, checked.state, tomorrow, following)
                value = after.state.score() if after.valid else value
            if best is None or value > best[0]:
                best = value, actions, checked.state
        if best is None:
            return None
        days.append(best[1])
        state = best[2]
    return {"score": list(state.score()), "kinds": kinds, "seed": seed, "days": days}


def search(config, runs, seconds, cores, look=0.0):
    """Chia đều số lượt cho mọi đội hình một xe tiếp tế, chạy song song, trả lượt tốt nhất."""
    count = len(config["agents"])
    layouts = [[int(i == s) for i in range(count)] for s in range(count)] if count > 1 else [[0]]
    jobs = [(layouts[i % len(layouts)], i // len(layouts)) for i in range(max(runs, len(layouts)))]
    best, results = None, []
    with ProcessPoolExecutor(max(1, cores)) as pool:
        futures = [pool.submit(simulate_rollout, config, kinds, seconds, look, seed) if look > 0 else
                   pool.submit(simulate_match, config, kinds, seconds, seed) for kinds, seed in jobs]
        for future in as_completed(futures):
            result = future.result()
            if result is None:
                continue
            results.append((result["score"], result["kinds"], result["seed"]))
            if best is None or tuple(result["score"]) > tuple(best["score"]):
                best = result
    return best, sorted(results, reverse=True)


def server_score(api, game_id):
    detail = api.request("GET", "/api/game/result", game_id=game_id, timeout=10)["detail"].get(str(api.team_id), {})
    return (detail.get("distinct_types", 0), detail.get("cumulative_daily_types", 0),
            detail.get("total_servings", 0))


def matches_server(board, state, raw):
    """Vị trí, nhiên liệu và mặt đường trên máy chủ có đúng như mô phỏng đầu ngày không."""
    agents = [(a["kind"], a["pos"], a["fuel"]) for a in raw["agents"]]
    expected = [(a.kind, a.pos, a.fuel) for a in state.agents]
    roads = {t["pos"]: t["status"] for t in raw["traffics"] if t["status"]}
    return agents == expected and roads == {p: s for p, s in state.traffic.items() if s}


def submit(api, game_id, board, best, log):
    """Chọn loại xe rồi nộp từng ngày, đối chiếu trạng thái máy chủ trước mỗi lần nộp."""
    api.request("POST", "/api/game/agent-types", body={"game_id": game_id, "types": best["kinds"]}, timeout=10)
    state = State.initial(board, best["kinds"])
    for day, actions in enumerate(best["days"]):
        raw = None
        for _ in range(30):
            raw = api.request("GET", "/api/game/day", game_id=game_id, timeout=10)
            if raw.get("day") == day:
                break
            time.sleep(1)
        if raw is None or raw.get("day") != day:
            log(f"  ngày {day + 1}: máy chủ chưa tới ngày này; dừng.")
            return False
        if not matches_server(board, state, raw):
            log(f"  ngày {day + 1}: trạng thái máy chủ khác mô phỏng; dừng, không nộp tiếp.")
            return False
        api.request("POST", "/api/game/practice/actions",
                    body={"game_id": game_id, "day": day, "actions": actions}, timeout=15)
        state = simulate_day(board, state, actions, board.day_steps[day]).state
    return True


def recently_active(own):
    stamp = own.get("last_submitted_at")
    if not stamp:
        return False
    try:
        moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - moment).total_seconds() < ACTIVE_MINUTES * 60


def main():
    parser = argparse.ArgumentParser(description="Practice: chạy nhiều lượt offline, nộp lượt tốt nhất.")
    parser.add_argument("questions", nargs="*", help="Tên câu (mặc định mọi câu của trận Practice)")
    parser.add_argument("--runs", type=int, default=7, help="Số lượt cả trận mỗi câu")
    # 6+3 giây hơn 3+2 giây ở Q04 (657 so với 650) và Q06 (772 so với 756), một lượt khoảng 9 phút.
    parser.add_argument("--seconds", type=float, default=6.0,
                        help="Giây lập kế hoạch một phương án ngày (mỗi ngày thử 6 mức phạt đường)")
    parser.add_argument("--look", type=float, default=3.0,
                        help="Giây lập kế hoạch thử ngày hôm sau để chọn phương án; 0 = một phương án mỗi ngày như cũ")
    parser.add_argument("--cores", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--dry-run", action="store_true", help="Chỉ mô phỏng và so sánh, không reset/nộp")
    parser.add_argument("--force", action="store_true", help="Cho phép reset cả câu đang chơi dở")
    parser.add_argument("--env", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default="https://hexudon.hairbui76.id.vn")
    args = parser.parse_args()
    api = LiveAPI(args.env, args.base_url)
    matches = list_matches(api)
    practice = [m for m in matches if m["is_practice"]]
    if len(practice) != 1:
        parser.error("Không tìm thấy đúng một trận Practice.")
    match = practice[0]
    questions = [q for q in match["questions"]
                 if not args.questions or q["name"].lower() in {n.lower() for n in args.questions}]
    folder = ROOT / "results/practice_best" / datetime.now().strftime("%Y%m%d_%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    teams = {str(t["id"]): t["name"] for t in match["teams"]}
    summary = []

    def log(text):
        print(text, flush=True)
        with (folder / "log.txt").open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")

    for question in questions:
        game_id, name = question["id"], question["name"]
        config = api.request("GET", "/api/game/config", game_id=game_id, timeout=10)
        board = Board.from_dict(config)
        started = time.time()
        best, results = search(config, args.runs, args.seconds, args.cores, args.look)
        if best is None:
            log(f"{name}: không có lượt mô phỏng hợp lệ.")
            continue
        bound = score_bounds(board, best["kinds"], tight=True)["route"]
        (folder / f"{name}.json").write_text(json.dumps(best), encoding="utf-8")
        state = api.request("GET", "/api/game/state", game_id=game_id, timeout=10)
        own = state.get("teams", {}).get(str(api.team_id), {})
        current = server_score(api, game_id)
        log(f"{name}: tốt nhất {tuple(best['score'])} (đội hình {best['kinds']}, seed {best['seed']}) trong "
            f"{len(results)} lượt, {time.time() - started:.0f}s; cận {bound}, đạt {percent(best['score'][2], bound[2])}; "
            f"máy chủ đang có {current} ({state.get('status')}).")
        row = {"cau": name, "game_id": game_id, "mo_phong": best["score"], "doi_hinh": best["kinds"],
               "can": bound, "may_chu_truoc": current, "cac_luot": results[:5]}
        if args.dry_run or tuple(best["score"]) <= tuple(current):
            log(f"  giữ điểm máy chủ (lượt mới không tốt hơn hoặc đang chạy thử).")
        elif state.get("status") == "in_progress" and (recently_active(own) or not args.force):
            # Máy chủ không trả thời điểm nộp nên không biết lượt dở là của ai (Q02, 28/10: đè lên
            # một lượt đang chơi); chỉ reset lượt dở khi được yêu cầu rõ bằng --force.
            log(f"  câu đang chơi dở trên máy chủ ({current}; có thể thành viên khác đang chơi); bỏ qua. "
                f"Chạy lại với --force nếu chắc chắn muốn reset.")
        else:
            if state.get("status") != "selecting_agents":
                api.request("POST", "/api/game/practice/reset", body={"game_id": game_id}, timeout=10)
                time.sleep(1)
            ok = submit(api, game_id, board, best, log)
            time.sleep(2)
            after = server_score(api, game_id)
            row["may_chu_sau"] = after
            log(f"  đã nộp {'đủ' if ok else 'một phần'}; máy chủ chấm {after} "
                f"({'khớp' if tuple(after) == tuple(best['score']) else 'KHÔNG khớp'} mô phỏng).")
        try:
            report_standings(api, game_id, dict(teams, **{str(api.team_id): teams.get(str(api.team_id), "")}))
        except NETWORK_ERRORS as error:
            log(f"  không đọc được xếp hạng: {error}")
        summary.append(row)
        (folder / "tong_ket.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
