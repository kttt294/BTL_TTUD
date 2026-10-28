"""Phân tích bản đồ: cận trên số udon theo đội hình, điểm hiện tại và đội hình đề xuất."""

import argparse
from itertools import product
import json
from pathlib import Path
from urllib.error import URLError

from .bounds import score_bounds
from .live_api import APIError, LiveAPI, list_matches, resolve_game_id
from .model import Board
from .team_selection import average_trials, select_types

ROOT = Path(__file__).resolve().parents[2]
NETWORK_ERRORS = (APIError, URLError, TimeoutError, OSError)


def bounds_by_supply(board, cache=None):
    """Cận route cao nhất cho từng số xe tiếp tế, kèm đội hình đạt cận đó."""
    cache = {} if cache is None else cache
    best = {}
    for kinds in product((0, 1), repeat=len(board.starts)):
        if 0 not in kinds:
            continue
        route = score_bounds(board, list(kinds), cache, tight=True)["route"]
        supplies = sum(kinds)
        if supplies not in best or route > best[supplies][0]:
            best[supplies] = (route, list(kinds))
    return {supplies: best[supplies] for supplies in sorted(best)}


def percent(value, upper):
    return f"{100 * value / upper:.0f}%" if upper else "—"


def report_board(board, label, cache):
    brands = len({spot["brand"] for spot in board.spots})
    print(f"== {label}: {board.height}×{board.width}, {len(board.starts)} xe, {len(board.spots)} điểm, "
          f"{brands} loại, {len(board.day_steps)} ngày, nhiên liệu {board.fuel_limit}")
    rules = score_bounds(board, [0] * len(board.starts), cache)["rules"]
    print(f"Trần theo luật (loại, tổng loại theo ngày, số phần): {rules}")
    print("Cận trên theo số xe tiếp tế (không đội nào vượt được; chưa chắc đạt được):")
    table = bounds_by_supply(board, cache)
    for supplies, (route, kinds) in table.items():
        print(f"  {supplies} tiếp tế: {str(route):<16} đội hình {kinds}")
    return table


def report_score(api, game_id, board, cache):
    """Điểm máy chủ của đội mình so với cận của đúng đội hình đã chốt; chỉ gửi GET."""
    state = api.request("GET", "/api/game/state", game_id=game_id, timeout=10)
    own = state.get("teams", {}).get(str(api.team_id))
    if not own or not own.get("types_selected"):
        print(f"Đội {api.team_id}: chưa chọn loại xe trong trận này.")
        return
    kinds = own_kinds(own)
    detail = api.request("GET", "/api/game/result", game_id=game_id, timeout=10)["detail"].get(str(api.team_id), {})
    score = (detail.get("distinct_types", 0), detail.get("cumulative_daily_types", 0),
             detail.get("total_servings", 0))
    route = score_bounds(board, kinds, cache, tight=True)["route"]
    print(f"Điểm máy chủ của đội {api.team_id} (đội hình {kinds}, trạng thái {state.get('status')}): {score}; "
          f"cận của đội hình này {route}, số phần đạt {percent(score[2], route[2])}.")


def own_kinds(team):
    return [0 if agent["type"] == "patrol" else 1 for agent in team["agents"]]


def report_matches(api, matches):
    """Liệt kê trận, câu hỏi (game_id) và trạng thái của đội mình ở từng câu; chỉ gửi GET."""
    for match in matches:
        kind = "Practice" if match["is_practice"] else "tính giờ"
        reset = ", không cho reset" if match["no_reset"] else ""
        print(f"== Trận {match['id']} {match['name']} ({kind}{reset}, {len(match['teams'])} đội)")
        for question in match["questions"]:
            try:
                state = api.request("GET", "/api/game/state", game_id=question["id"], timeout=10)
                own = state.get("teams", {}).get(str(api.team_id))
                if own and own.get("types_selected"):
                    status = (f"{state.get('status')}, đội hình {own_kinds(own)}, "
                              f"đã nộp {own.get('days_submitted', 0)} ngày, {own.get('total_servings', 0)} phần")
                else:
                    status = f"{state.get('status')}, chưa chọn loại xe"
            except NETWORK_ERRORS as error:
                status = f"không đọc được trạng thái ({error})"
            print(f"  {question['name']:<4} {question['id']}  {status}")


def standings(api, game_id, teams, practice=True):
    """Các đội đã nộp bài theo đúng thứ tự luật: loại, tổng loại theo ngày, số phần, thời gian.

    teams: mã đội -> tên. Practice mỗi đội có ván riêng nên đọc điểm từng đội (website chỉ hiện
    bảng này ở Practice không cho reset); trận tính giờ có điểm mọi đội trong /result.
    Trả (các dòng (đội, điểm), số đội đọc được, các đội lỗi mạng).
    """
    base = game_id.split(":")[0]
    skipped = []
    if practice:
        details = {}
        for team in teams:
            try:
                details[team] = api.request("GET", "/api/game/practice/score", game_id=f"{base}:{team}",
                                            timeout=10)["detail"].get(team)
            except APIError as error:
                if error.status != 404:
                    skipped.append(team)
            except (URLError, TimeoutError, OSError):
                # Một đội trả chậm không được làm mất cả bảng xếp hạng.
                skipped.append(team)
    else:
        details = api.request("GET", "/api/game/result", game_id=base, timeout=10)["detail"]
    rows = [(team, d) for team, d in details.items() if d and d.get("days_submitted")]
    rows.sort(key=lambda row: (-row[1]["distinct_types"], -row[1]["cumulative_daily_types"],
                               -row[1]["total_servings"], row[1]["cumulative_response_time"]))
    return rows, len(details), skipped


def report_standings(api, game_id, teams, practice=True):
    rows, count, skipped = standings(api, game_id, teams, practice)
    print(f"Xếp hạng {'Practice' if practice else 'trận'} ({len(rows)}/{count} đội đã nộp bài):")
    if skipped:
        print(f"  (không đọc được đội {', '.join(skipped)} do lỗi mạng; thứ hạng có thể thiếu các đội này)")
    for rank, (team, d) in enumerate(rows, 1):
        label = " ".join(filter(None, [f"đội {team}", teams.get(team),
                                        "(mình)" if team == str(api.team_id) else None]))
        print(f"  {rank}. {label}: ({d['distinct_types']}, "
              f"{d['cumulative_daily_types']}, {d['total_servings']}), thời gian {d['cumulative_response_time']:.1f} giây")


def report_selection(board, seconds, cache):
    kinds, records, elapsed = select_types(board, seconds, "tour")
    trials = [r for r in records if r["types"] == kinds and r["complete"] and r.get("phase") == "refine"]
    trials = trials or [r for r in records if r["types"] == kinds and r["complete"]]
    route = score_bounds(board, kinds, cache, tight=True)["route"]
    if not trials:
        print(f"Đội hình đề xuất: {kinds} (chưa mô phỏng xong trận nào trong {elapsed:.0f} giây).")
        return
    score = average_trials(trials)
    print(f"Đội hình đề xuất (mô phỏng tour {elapsed:.0f} giây): {kinds}, điểm mô phỏng "
          f"({score[0]}, {score[1]}, {score[2]:.0f}); cận {route}, số phần đạt {percent(score[2], route[2])}.")


def main():
    parser = argparse.ArgumentParser(description="Tính udon tối đa của bản đồ và đề xuất đội hình.")
    parser.add_argument("games", nargs="*", help="Tên câu (Q02) hoặc game_id; chỉ gửi GET, không nộp bài")
    parser.add_argument("--danh-sach", action="store_true",
                        help="Liệt kê các trận, câu hỏi kèm game_id và trạng thái của đội mình")
    parser.add_argument("--tat-ca", action="store_true", help="Phân tích mọi câu của trận Practice (hoặc --match)")
    parser.add_argument("--match", type=int, help="Mã trận khi tên câu có ở nhiều trận (xem --danh-sach)")
    parser.add_argument("--config", help="Phân tích file cấu hình thay vì tải từ máy chủ")
    parser.add_argument("--starts", nargs="+", type=int, help="Vị trí xuất phát nếu config thiếu agents")
    parser.add_argument("--select", type=float, default=0, metavar="GIÂY",
                        help="Chạy bộ chọn đội hình tour trong số giây này (runner dùng khoảng 26)")
    parser.add_argument("--xep-hang", action="store_true", help="In bảng xếp hạng Practice của các đội trong trận")
    parser.add_argument("--env", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default="https://hexudon.hairbui76.id.vn")
    parser.add_argument("--save-dir", default=str(ROOT / "results/maps"),
                        help="Nơi lưu bản sao config đã tải để chạy offline")
    args = parser.parse_args()
    if not (args.games or args.config or args.danh_sach or args.tat_ca):
        parser.error("Cần tên câu/game_id, --tat-ca, --danh-sach hoặc --config.")
    if args.select < 0:
        parser.error("--select không được âm.")
    if args.config:
        config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
        board, cache = Board.from_dict(config, args.starts), {}
        report_board(board, Path(args.config).name, cache)
        if args.select:
            report_selection(board, args.select, cache)
    if not (args.games or args.danh_sach or args.tat_ca):
        return
    api = LiveAPI(args.env, args.base_url)
    try:
        matches = list_matches(api)
    except NETWORK_ERRORS as error:
        # Vẫn phân tích được game_id đầy đủ; chỉ mất tên câu, danh sách đội và --tat-ca.
        print(f"Không đọc được danh sách trận ({error}).")
        matches = []
    if args.danh_sach:
        report_matches(api, matches)
    games = []
    for name in args.games:
        try:
            games.append(resolve_game_id(api, name, args.match, matches=matches))
        except ValueError as error:
            print(error)
    if args.tat_ca:
        chosen = [m for m in matches if m["id"] == args.match] if args.match else \
                 [m for m in matches if m["is_practice"]]
        games += [q["id"] for m in chosen for q in m["questions"]]
    owner = {q["id"]: (m, q["name"]) for m in matches for q in m["questions"]}
    for game_id in games:
        match, name = owner.get(game_id.split(":")[0], (None, None))
        label = f"{name} ({game_id})" if name else game_id
        try:
            config = api.request("GET", "/api/game/config", game_id=game_id, timeout=10)
        except NETWORK_ERRORS as error:
            print(f"== {label}: không đọc được config ({error}).")
            continue
        folder = Path(args.save_dir)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{game_id.split(':')[0]}.json").write_text(json.dumps(config), encoding="utf-8")
        board, cache = Board.from_dict(config), {}
        report_board(board, label, cache)
        try:
            report_score(api, game_id, board, cache)
            if args.xep_hang:
                teams = {str(t["id"]): t["name"] for t in match["teams"]} if match else {}
                teams.setdefault(str(api.team_id), "")
                report_standings(api, game_id, teams, practice=not match or bool(match["is_practice"]))
        except NETWORK_ERRORS as error:
            print(f"Không đọc được điểm của đội: {error}")
        if args.select:
            report_selection(board, args.select, cache)
        print()
