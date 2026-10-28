"""Thi tự động: chạy song song mọi câu của một trận, mỗi câu một runner riêng.

Mỗi câu chạy `play_match.py` trong một tiến trình con với thư mục checkpoint riêng của lượt chơi.
Runner chết giữa trận thì được khởi động lại và đọc tiếp checkpoint. Số tiến trình của một câu
được chia theo số câu chưa xong lúc nó bắt đầu (các câu Mock Contest bắt đầu lệch giờ nhau).
Kết quả được đọc ngay khi từng câu xong, trước khi câu tự reset sang lượt mới.
"""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

from .bounds import score_bounds
from .live_api import GAME_ID, APIError, LiveAPI, list_matches
from .map_analysis import NETWORK_ERRORS, bounds_by_supply, own_kinds, percent, standings
from .model import Board

ROOT = Path(__file__).resolve().parents[2]
FINISHED = ("finished", "ended", "completed")
MAX_RESTARTS = 3
MIN_SELECTION = 20


class Slot:
    """Một câu hỏi: chờ tới lượt, chạy runner, khởi động lại khi runner dừng giữa trận."""

    def __init__(self, question, folder):
        self.name, self.game_id, self.mode = question["name"], question["id"], question["mode"]
        self.folder = folder / self.name
        self.process, self.handle = None, None
        self.restarts, self.done, self.workers = 0, False, 0
        self.note, self.row = "chờ", None
        self.total_days, self.shown, self.day, self.ranked_day = None, None, 0, 0

    def launch(self, args, workers):
        self.folder.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, "-X", "utf8", str(ROOT / "play_match.py"), self.game_id,
                   "--mode", self.mode, "--algorithm", args.algorithm, "--workers", str(workers),
                   "--run-dir", str(self.folder), "--env", args.env, "--base-url", args.base_url]
        if args.no_hai_ngay:
            command.append("--no-hai-ngay")
        self.handle = (self.folder / "runner.log").open("a", encoding="utf-8")
        self.process = subprocess.Popen(command, cwd=ROOT, stdout=self.handle, stderr=subprocess.STDOUT)
        self.workers, self.note = workers, f"đang chạy ({workers} tiến trình)"

    def finish(self):
        if self.handle:
            self.handle.close()
        self.process, self.handle = None, None

    def log_text(self):
        path = self.folder / "runner.log"
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

    def last_line(self):
        lines = [line.strip() for line in self.log_text().splitlines() if line.strip()]
        return lines[-1][:110] if lines else ""

    def progress(self):
        """Ngày runner đang chơi theo log, ví dụ "ngày 7/10, đã nộp"."""
        if self.total_days is None and (self.folder / "config.json").exists():
            try:
                config = json.loads((self.folder / "config.json").read_text(encoding="utf-8"))
                self.total_days = len(config["daySteps"])
            except (ValueError, KeyError):
                pass
        text = self.log_text()
        days = re.findall(r"^Ngày (\d+):", text, re.M)
        if not days:
            return "đã chọn xe, chờ ngày 1" if "Vai trò đã chọn" in text else "chọn xe"
        day = days[-1]
        self.day = int(day)
        sent = re.search(rf"^Ngày {day}: (máy chủ đã nhận|nộp lại)", text, re.M)
        return f"ngày {day}/{self.total_days or '?'}, {'đã nộp' if sent else 'đang lập kế hoạch'}"


def own_state(api, game_id):
    state = api.request("GET", "/api/game/state", game_id=game_id, timeout=10)
    return state, state.get("teams", {}).get(str(api.team_id), {})


def game_mode(api, game_id):
    """Practice hay trận tính giờ của một game_id, không cần API quản lý.

    Đồng hồ đang chạy là trận tính giờ. Practice có đồng hồ 0 và /day không ghi rõ hết hạn nên runner
    không tự phân biệt được với trận vừa hết giờ; practice/score thì chỉ có ở Practice (Mock trả 404).
    """
    state, _ = own_state(api, game_id)
    if any((state.get(key) or 0) > 0 for key in ("day_deadline_in", "selection_deadline_in", "selection_opens_in")):
        return "timed"
    try:
        api.request("GET", "/api/game/practice/score", game_id=f"{game_id}:{api.team_id}", timeout=10)
    except APIError:
        return "timed"
    return "practice"


_TEAMS = {}


def practice_teams(api):
    """Mã đội -> tên của các trận Practice (một lần gọi API quản lý, chỉ để xếp hạng Practice).

    /result của Practice chỉ có đội mình nên phải đọc điểm từng đội; lỗi thì chỉ còn đội mình.
    """
    if not _TEAMS:
        _TEAMS[str(api.team_id)] = ""
        try:
            for match in api.manager("/match")["data"]:
                if match.get("is_practice"):
                    _TEAMS.update({str(t["id"]): t["name"] for t in match.get("teams", [])})
        except NETWORK_ERRORS:
            pass
    return _TEAMS


def ranking(api, slot):
    practice = slot.mode == "practice"
    rows, _, _ = standings(api, slot.game_id, practice_teams(api) if practice else {}, practice)
    return rows


def print_ranking(api, slot, day):
    """Xếp hạng sau một ngày: hạng của mình và ba đội đầu."""
    try:
        rows = ranking(api, slot)
    except NETWORK_ERRORS as error:
        print(f"{time.strftime('%H:%M:%S')} {slot.name}: không đọc được xếp hạng sau ngày {day} ({error})", flush=True)
        return
    me = str(api.team_id)
    score = lambda d: f"({d['distinct_types']}, {d['cumulative_daily_types']}, {d['total_servings']})"
    rank = next((i for i, (team, _) in enumerate(rows, 1) if team == me), None)
    mine = f"hạng {rank}/{len(rows)} {score(rows[rank - 1][1])}" if rank else f"chưa có điểm ({len(rows)} đội)"
    top = "  ".join(f"{i}. đội {team}{' (mình)' if team == me else ''} {score(d)}"
                    for i, (team, d) in enumerate(rows[:3], 1))
    print(f"{time.strftime('%H:%M:%S')} {slot.name}: xếp hạng sau ngày {day}: {mine} | {top}", flush=True)


def ready_to_start(api, slot, args):
    """Chờ lượt mới thì chỉ vào khi câu đang ở bước chọn xe; không thì vào ngay khi câu chưa kết thúc."""
    state, own = own_state(api, slot.game_id)
    status = state.get("status")
    if slot.mode == "practice":
        if status in FINISHED and args.reset:
            api.request("POST", "/api/game/practice/reset", body={"game_id": slot.game_id}, timeout=10)
            slot.note = "đã reset Practice"
            return False
        slot.note = "đã chơi xong, không reset" if status in FINISHED else slot.note
        return status not in FINISHED
    if args.wait_new:
        slot.note = f"chờ lượt mới ({status}, ngày {state.get('day')})"
        # Vào khi còn quá ít giờ chọn xe thì runner khởi động xong là bước chọn đã đóng và máy chủ
        # mặc định toàn tuần tra (Mock Q03, 24/10: 137 suất); chờ lượt sau thay vì chơi lượt hỏng.
        return (status == "selecting_agents" and not own.get("types_selected")
                and (state.get("selection_deadline_in") or 0) >= MIN_SELECTION)
    if status in FINISHED:
        slot.note = "đã chơi xong"
    return status not in FINISHED


def collect(api, slot):
    """Điểm máy chủ, thứ hạng trong câu và tỉ lệ so với cận của đội hình đã chốt (đọc ngay khi xong)."""
    try:
        config = api.request("GET", "/api/game/config", game_id=slot.game_id, timeout=10)
        result = api.request("GET", "/api/game/result", game_id=slot.game_id, timeout=10)
        _, own = own_state(api, slot.game_id)
        played = ranking(api, slot)
    except NETWORK_ERRORS as error:
        return {"cau": slot.name, "loi": str(error)}
    detail = result.get("detail", {})
    mine = detail.get(str(api.team_id), {})
    score = (mine.get("distinct_types", 0), mine.get("cumulative_daily_types", 0), mine.get("total_servings", 0))
    rank = next((i for i, (team, _) in enumerate(played, 1) if team == str(api.team_id)), None)
    leader = played[0][1]["total_servings"] if played else 0
    kinds = own_kinds(own) if own.get("agents") else None
    # Cận chặt tốn vài giây: tính lúc tổng kết để vòng điều phối không chậm khi câu khác đang mở.
    return {"cau": slot.name, "game_id": slot.game_id, "doi_hinh": kinds, "diem": score,
            "hang": rank, "so_doi": len(played), "dan_dau_so_phan": leader,
            "tien_trinh": slot.workers, "khoi_dong_lai": slot.restarts, "ghi_chu": slot.note, "_config": config}


def add_bounds(rows):
    """Cận chặt của đội hình đã chốt và của đội hình tốt nhất (để thấy khi chọn nhầm đội hình)."""
    for row in rows:
        config = row.pop("_config", None)
        if config is None or not row.get("doi_hinh"):
            continue
        board, cache = Board.from_dict(config), {}
        bound = score_bounds(board, row["doi_hinh"], cache, tight=True)["route"]
        best = max(bounds_by_supply(board, cache).values())[0]
        score = row["diem"]
        row.update(can=bound, can_doi_hinh_tot_nhat=best,
                   ti_le=round(score[2] / bound[2], 4) if bound[2] else None,
                   dat_can=percent(score[2], bound[2]), dat_can_tot_nhat=percent(score[2], best[2]))


def report(rows, folder):
    add_bounds(rows)
    (folder / "tong_ket.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n== Tổng kết", flush=True)
    for r in rows:
        if "loi" in r:
            print(f"  {r['cau']}: không đọc được kết quả ({r['loi']})")
            continue
        print(f"  {r['cau']}: điểm {r['diem']}, hạng {r['hang']}/{r['so_doi']}, đội dẫn đầu {r['dan_dau_so_phan']} phần, "
              f"cận {r.get('can')} (đạt {r.get('dat_can', '—')}; so với đội hình tốt nhất {r.get('dat_can_tot_nhat', '—')}), "
              f"đội hình {r['doi_hinh']}, {r['tien_trinh']} tiến trình, khởi động lại {r['khoi_dong_lai']} lần", flush=True)
    rated = [r for r in rows if r.get("ti_le")]
    if rated:
        total = sum(r["diem"][2] for r in rated) / sum(r["can"][2] for r in rated)
        print(f"  Tổng số phần đạt {100 * total:.1f}% cận; câu thấp nhất {min(r['ti_le'] for r in rated):.1%}.",
              flush=True)


def play_round(api, args, questions, folder):
    slots = [Slot(q, folder) for q in questions]
    deadline, last_status = time.monotonic() + args.timeout_minutes * 60, 0
    try:
        while not all(slot.done for slot in slots):
            if time.monotonic() > deadline:
                print("Hết thời gian chờ; dừng các câu chưa xong.", flush=True)
                break
            for slot in slots:
                if slot.done:
                    continue
                if slot.process is None:
                    try:
                        if ready_to_start(api, slot, args):
                            # Chia nhân theo số câu chưa xong, kể cả câu đang chờ lượt: chia theo số câu đang
                            # chạy thì câu vào đầu giữ 7 tiến trình cả trận, các câu sau tranh CPU nên sàng
                            # lọc đội hình nhiễu (Mock vòng 1–2, 24/10: Q01 toàn tuần tra, Q06 hai xe tiếp tế).
                            waiting = sum(1 for s in slots if not s.done)
                            slot.launch(args, max(1, args.cores // waiting))
                            print(f"{slot.name}: bắt đầu chạy với {slot.workers} tiến trình.", flush=True)
                        elif not args.wait_new and slot.note.startswith("đã chơi xong"):
                            slot.done = True
                    except NETWORK_ERRORS as error:
                        slot.note = f"lỗi mạng khi kiểm tra ({error})"
                    continue
                code = slot.process.poll()
                if code is None:
                    continue
                slot.finish()
                try:
                    state, _ = own_state(api, slot.game_id)
                    over = state.get("status") in FINISHED
                except NETWORK_ERRORS:
                    over = False
                if over or (code == 0 and slot.mode == "practice"):
                    slot.done, slot.note = True, "xong"
                    slot.row = collect(api, slot)
                    print(f"{slot.name}: xong, điểm {slot.row.get('diem')}, hạng {slot.row.get('hang')}/"
                          f"{slot.row.get('so_doi')}.", flush=True)
                elif slot.restarts < MAX_RESTARTS:
                    slot.restarts += 1
                    print(f"{slot.name}: runner dừng (mã {code}) khi trận chưa xong; khởi động lại lần {slot.restarts}. "
                          f"Dòng cuối: {slot.last_line()}", flush=True)
                    slot.launch(args, slot.workers)
                else:
                    slot.done, slot.note = True, f"dừng sau {MAX_RESTARTS} lần khởi động lại"
                    print(f"{slot.name}: {slot.note}. Dòng cuối: {slot.last_line()}", flush=True)
            for slot in slots:
                # In ngay khi câu sang ngày mới hoặc vừa nộp xong ngày đó.
                if slot.process is not None and slot.progress() != slot.shown:
                    slot.shown = slot.progress()
                    print(f"{time.strftime('%H:%M:%S')} {slot.name}: {slot.shown}", flush=True)
                    if slot.day - 1 > slot.ranked_day:
                        # Sang ngày mới thì ngày trước đã được chấm; đọc bảng ở luồng riêng để mạng
                        # chậm (Practice đọc từng đội) không giữ vòng điều phối.
                        slot.ranked_day = slot.day - 1
                        threading.Thread(target=print_ranking, args=(api, slot, slot.ranked_day), daemon=True).start()
            if time.monotonic() - last_status > 60:
                last_status = time.monotonic()
                print(time.strftime("%H:%M:%S"), " | ".join(
                    f"{s.name}: {'xong' if s.done else s.progress() if s.process else s.note}" for s in slots),
                    flush=True)
            time.sleep(2)
    finally:
        for slot in slots:
            if slot.process is not None and slot.process.poll() is None:
                slot.process.terminate()
            slot.finish()
    rows = [slot.row or collect(api, slot) for slot in slots]
    report(rows, folder)
    return rows


def main():
    parser = argparse.ArgumentParser(description="Thi tự động: chạy song song mọi câu của một trận.")
    parser.add_argument("questions", nargs="*",
                        help="game_id cần chạy (chạy thẳng, không quét trận), hoặc tên câu của trận --match")
    parser.add_argument("--match", help="game_id của trận cần chạy; hoặc mã số trận (14) để tự quét mọi câu "
                                        "của trận đó, mặc định trận tính giờ (Practice nếu --mode practice)")
    # auto: runner tự nhận Practice hay trận tính giờ từ máy chủ. Ép timed cho Practice thì runner chờ
    # máy chủ tự sang ngày mãi (Practice Q01, 24/10), nên chỉ ép khi chắc chắn.
    parser.add_argument("--mode", choices=["auto", "timed", "practice"], default="auto")
    parser.add_argument("--algorithm", choices=["greedy", "lookahead", "tour"], default="tour")
    parser.add_argument("--cores", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                        help="Số nhân dùng cho tất cả các câu; mặc định số nhân trừ 1")
    parser.add_argument("--no-hai-ngay", action="store_true",
                        help="Tắt chọn bài nộp lại theo điểm sau ngày mai (quay về cách cũ)")
    parser.add_argument("--wait-new", action="store_true",
                        help="Chỉ vào câu khi câu ở bước chọn xe (Mock Contest tự reset mỗi 10 phút)")
    parser.add_argument("--reset", action="store_true", help="Practice: reset câu đã chơi xong rồi chơi lại")
    parser.add_argument("--vong", type=int, default=1, help="Số vòng chơi liên tiếp (tổng duyệt Mock Contest)")
    parser.add_argument("--timeout-minutes", type=float, default=40, help="Giới hạn phút của mỗi vòng")
    parser.add_argument("--folder", help="Thư mục lượt chạy; dùng lại thư mục cũ để chạy tiếp sau khi ngắt")
    parser.add_argument("--env", default=str(ROOT / ".env"))
    parser.add_argument("--base-url", default="https://hexudon.hairbui76.id.vn")
    args = parser.parse_args()
    if args.reset and args.mode == "timed":
        parser.error("--reset chỉ dùng cho Practice.")
    api = LiveAPI(args.env, args.base_url)
    given = ([args.match] if args.match else []) + args.questions
    if given and all(GAME_ID.fullmatch(g.strip().lower()) for g in given):
        # Ngày thi: ID dán sẵn được chạy thẳng, không gọi API quản lý (quét trận chỉ dùng khi tổng duyệt).
        # Cùng một game viết hoa/thường hay kèm ":đội" chỉ chạy một runner, không nộp đè lẫn nhau.
        games = dict.fromkeys(g.strip().lower().split(":")[0] for g in given)
        try:
            questions = [{"name": g[:8], "id": g, "mode": args.mode if args.mode != "auto" else game_mode(api, g)}
                         for g in games]
        except NETWORK_ERRORS as error:
            parser.error(f"Không đọc được trạng thái game ({error}); kiểm tra mạng/token rồi chạy lại.")
        title = ", ".join(f"{q['name']} ({q['mode']})" for q in questions)
    else:
        if args.match and not args.match.isdigit():
            parser.error(f'--match "{args.match}" không phải game_id (UUID) hay mã số trận.')
        matches = list_matches(api)
        practice = args.mode == "practice"
        chosen = [m for m in matches
                  if (m["id"] == int(args.match) if args.match else bool(m["is_practice"]) == practice)]
        if len(chosen) != 1:
            parser.error("Không chọn được đúng một trận; thêm --match (xem phan_tich_map.py --danh-sach).")
        match = chosen[0]
        wanted = {n.lower() for n in args.questions}
        questions = [q for q in match["questions"]
                     if not wanted or q["name"].lower() in wanted or str(q["id"]).lower() in wanted]
        if not questions:
            parser.error("Không có câu nào khớp tên đã nhập.")
        title = f"Trận {match['id']} {match['name']}"
        for question in questions:
            question["mode"] = args.mode if args.mode != "auto" else (
                "practice" if match["is_practice"] else "timed")
    root = Path(args.folder) if args.folder else ROOT / "results/thi_dau" / datetime.now().strftime("%Y%m%d_%H%M%S")
    history = []
    try:
        for number in range(1, args.vong + 1):
            folder = root / f"vong_{number}" if args.vong > 1 else root
            folder.mkdir(parents=True, exist_ok=True)
            print(f"{title}, vòng {number}/{args.vong}: {len(questions)} câu; log ở {folder}", flush=True)
            history.append(play_round(api, args, questions, folder))
            (root / "lich_su.json").write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
    except KeyboardInterrupt:
        print("\nĐã dừng bộ điều phối; chạy lại với --folder", root, "để tiếp tục.", flush=True)
