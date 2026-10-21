"""Tải trạng thái đường Practice mới nhất của các đội và replay đầy đủ của đội mình.

Chỉ dùng HEXUDON_TOKEN của đội mình và chỉ gửi GET.
- GET /api/game/practice/peer (game_id "<trận>:<đội khác>"): mỗi ngày chỉ có frame cuối ngày,
  road_condition, loại xe, số suất và số loại. Không có quỹ đạo từng step.
- GET /api/game/replay (game_id "<trận>:<đội mình>"): replay đầy đủ, dùng để kiểm chứng cách đếm
  lưu lượng và hiệu chỉnh phép ước lượng lưu lượng từ trạng thái đường.

Lưu lượng của một đội được đếm như simulator: mỗi step, mỗi xe đứng trên ô đường được tính
một lần, trừ các step xe đang rời ô đầu ngày trước lần đến ô đầu tiên.

python -X utf8 experiments/fetch_peer_traffic.py
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.live_api import APIError, LiveAPI
from hexudon.model import Board

GAMES = {"Q01": "c57bfe4b-55ef-416f-893f-1ccaf86a8b87", "Q02": "145bdf65-54f2-41ad-a0e0-29783efdf9b3",
         "Q03": "ca50dfe3-0423-4c4d-be40-7520becda4cf", "Q04": "83f54883-4731-472e-bec2-f36f161b1374",
         "Q06": "764f35b8-83d2-45f8-99ef-8561a8ceeed3", "Q07": "66bb1d31-0e5e-44b7-a5db-88cb20e31775",
         "Q08": "777d23b7-18c9-498d-a2b0-fb5e6bcfd0d6", "Q09": "aedebf80-4659-4b77-ae06-0aa2e272baa5",
         "Q10": "483dd871-8ccf-402d-971b-9f17c4615a8a"}
# Q02 dùng chung cấu hình với Q01.
CONFIGS = {"Q02": "Q01"}
TEAMS = {"53": "IUH_1", "57": "HCMUTE_1", "58": "HCMUTE_2", "62": "Phenikaa_2",
         "65": "HAUI_3", "78": "DAU_2", "81": "CTU_1"}


def load_board(case):
    folder = CONFIGS.get(case, case)
    config = json.loads((ROOT / "output/team_selection" / folder / "config.json").read_text(encoding="utf-8"))
    return Board.from_dict(config)


def day_counts(board, day):
    """Số step dừng trên từng ô đường của một đội trong một ngày, theo quy ước simulator."""
    traffic = {int(p): s for p, s in day["road_condition"].items()}
    frames = day["teams"][0]["frames"]
    counts = Counter()
    for car in range(len(frames[0]["agents"])):
        cells = [frame["agents"][car]["cell"] for frame in frames]
        start = cells[0]
        leave = next((t for t in range(1, len(cells)) if cells[t] != start), None)
        # Các step cuối cùng ở ô đầu ngày trước khi rời là lúc đang di chuyển: không đếm.
        moving_from = leave - board.cost(start, traffic)[0] + 1 if leave is not None else None
        for t in range(1, len(cells)):
            pos = cells[t]
            if board.terrain(pos) != 1:
                continue
            if leave is not None and t < leave and t >= moving_from:
                continue
            counts[pos] += 1
    return counts


def status(board, total):
    return {p: (2 if total.get(p, 0) >= board.jammed_threshold else
                1 if total.get(p, 0) >= board.busy_threshold else 0)
            for p in range(board.width * board.height) if board.terrain(p) == 1}


def verify(board, days, counts):
    """Tính lại road_condition ngày d từ lưu lượng ngày d-1 và d-2 của chính đội đó."""
    mismatches = 0
    for d in range(1, len(days)):
        total = Counter(counts[d - 1])
        if d >= 2:
            total.update(counts[d - 2])
        expected = status(board, total)
        actual = {int(p): s for p, s in days[d]["road_condition"].items()}
        mismatches += sum(expected[p] != actual.get(p, 0) for p in expected)
    return mismatches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", default=list(GAMES))
    parser.add_argument("--teams", nargs="+", default=[t for t in TEAMS if t != "62"],
                        help="ID đội cần đọc; mặc định mọi đội đã biết trừ đội mình")
    parser.add_argument("--output", default=str(ROOT / "results/peer_traffic"))
    parser.add_argument("--pause", type=float, default=0.5, help="Giây nghỉ giữa hai request")
    args = parser.parse_args()
    api = LiveAPI(ROOT / ".env")
    output = Path(args.output)
    for folder in ("replays", "own"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    summary = {}
    for case in args.cases:
        board = load_board(case)
        summary[case] = {"peers": {}}
        own = api.request("GET", "/api/game/replay", game_id=f"{GAMES[case]}:{api.team_id}", timeout=30)
        (output / "own" / f"{case}.json").write_text(json.dumps(own), encoding="utf-8")
        days = own.get("days", [])
        full = bool(days) and len(days[0]["teams"][0]["frames"]) > 1
        mismatches = verify(board, days, [day_counts(board, d) for d in days]) if full else None
        summary[case]["own"] = {"days": len(days), "full_frames": full, "road_status_mismatches": mismatches}
        print(f"{case} đội mình: {len(days)} ngày, sai khác khi tính lại road_condition={mismatches}", flush=True)
        time.sleep(args.pause)
        for team in args.teams:
            name = TEAMS.get(team, team)
            try:
                replay = api.request("GET", "/api/game/practice/peer", game_id=f"{GAMES[case]}:{team}", timeout=20)
            except APIError as error:
                summary[case]["peers"][team] = {"team": name, "error": str(error)[:200]}
                print(f"{case} {name}: lỗi {error.status}", flush=True)
                time.sleep(args.pause)
                continue
            days = replay.get("days", [])
            (output / "replays" / f"{case}_{team}.json").write_text(json.dumps(replay), encoding="utf-8")
            summary[case]["peers"][team] = {
                "team": name, "days": len(days), "complete": len(days) == len(board.day_steps),
                "kinds": days[0]["teams"][0]["kinds"] if days else None,
                "daily": [[d["teams"][0]["types"], d["teams"][0]["servings"]] for d in days]}
            print(f"{case} {name}: {len(days)}/{len(board.day_steps)} ngày", flush=True)
            time.sleep(args.pause)
    (output / "peer_traffic.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print("Đã lưu", output / "peer_traffic.json")


if __name__ == "__main__":
    main()
