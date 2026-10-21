"""Mô phỏng trận nhiều đội: giao thông gồm lưu lượng của ta và lưu lượng ước lượng của đội khác.

Đội khác chỉ có road_condition theo ngày (GET /api/game/practice/peer), tức tổng lưu lượng hai
ngày trước của riêng họ đã qua ngưỡng. Mỗi trạng thái 0/1/2 được đổi thành lưu lượng hai ngày
trung bình đo trên replay đầy đủ của chính đội ta ở cùng bài (cùng ngưỡng). Lưu lượng của ta
tính chính xác từ simulator. Trạng thái ngày sau = ngưỡng(tổng các đội / số đội), như đề.

Đây là phát lại một chiều: kế hoạch của đội khác không phản ứng với đường của trận chung.

python -X utf8 experiments/fetch_peer_traffic.py      # tải dữ liệu trước
python -X utf8 experiments/peer_traffic_demo.py --seconds 5
"""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
from fetch_peer_traffic import GAMES, day_counts, load_board
from hexudon.model import State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day

DATA = ROOT / "results/peer_traffic"


def status_of(board, value):
    return 2 if value >= board.jammed_threshold else 1 if value >= board.busy_threshold else 0


def roads(board):
    return [p for p in range(board.width * board.height) if board.terrain(p) == 1]


def windows(board, replay):
    """Tổng lưu lượng hai ngày trước của ngày d (d ≥ 1), đếm chính xác từ replay đầy đủ."""
    counts = [day_counts(board, day) for day in replay["days"]]
    result = []
    for d in range(1, len(counts)):
        total = Counter(counts[d - 1])
        if d >= 2:
            total.update(counts[d - 2])
        result.append(total)
    return result


def calibrate(board, replay):
    """Lưu lượng hai ngày trung bình theo trạng thái đường, đo trên replay đầy đủ của đội ta."""
    groups = {0: [], 1: [], 2: []}
    for total in windows(board, replay):
        for p in roads(board):
            groups[status_of(board, total.get(p, 0))].append(total.get(p, 0))
    fallback = {0: 0.0, 1: (board.busy_threshold + board.jammed_threshold - 1) / 2, 2: board.jammed_threshold + 1}
    return {s: (sum(v) / len(v) if v else fallback[s]) for s, v in groups.items()}


def peer_windows(board, replay, table):
    """Ước lượng tổng lưu lượng hai ngày của đội khác từ road_condition của họ, cho ngày 1..n-1."""
    result = []
    for day in replay["days"][1:]:
        condition = {int(p): s for p, s in day["road_condition"].items()}
        result.append({p: table[condition.get(p, 0)] for p in roads(board)})
    return result


FULL = ROOT / "results/peer_comparison"
OWN_NAME = "Phenikaa_2"


def peers_for(case, board, table, source="full"):
    """Lưu lượng hai ngày của đội khác: đếm chính xác từ replay đầy đủ nếu có, không thì ước lượng."""
    peers = {}
    if source == "full":
        for path in sorted(FULL.glob(f"*_{case}.json")):
            team = path.stem.rsplit("_", 1)[0]
            replay = json.loads(path.read_text(encoding="utf-8")).get("replay", {})
            days = replay.get("days", [])
            if team != OWN_NAME and len(days) == len(board.day_steps) and len(days[0]["teams"][0]["frames"]) > 1:
                peers[team] = [{p: w.get(p, 0) for p in roads(board)} for w in windows(board, replay)]
        return peers
    for path in sorted(DATA.glob(f"replays/{case}_*.json")):
        replay = json.loads(path.read_text(encoding="utf-8"))
        if len(replay.get("days", [])) == len(board.day_steps):
            peers[path.stem.split("_")[1]] = peer_windows(board, replay, table)
    return peers


def calibration_check():
    """Q01 và Q02 cùng bản đồ, đều là lượt của ta: coi Q02 là đội khác chỉ biết road_condition."""
    board = load_board("Q01")
    a = json.loads((DATA / "own/Q01.json").read_text(encoding="utf-8"))
    b = json.loads((DATA / "own/Q02.json").read_text(encoding="utf-8"))
    table = calibrate(board, a)
    wa, wb = windows(board, a), windows(board, b)
    eb = peer_windows(board, b, table)
    stats = Counter()
    for d in range(len(wa)):
        for p in roads(board):
            truth = status_of(board, (wa[d].get(p, 0) + wb[d].get(p, 0)) / 2)
            guess = status_of(board, (wa[d].get(p, 0) + eb[d][p]) / 2)
            alone = status_of(board, wa[d].get(p, 0))
            stats["cells"] += 1
            stats["estimate_ok"] += guess == truth
            stats["single_ok"] += alone == truth
            if truth or guess:
                stats["active"] += 1
                stats["active_estimate_ok"] += guess == truth
                stats["active_single_ok"] += alone == truth
    return table, dict(stats)


def play(job):
    case, kinds, seconds, multi, source = job
    board = load_board(case)
    own = json.loads((DATA / f"own/{case}.json").read_text(encoding="utf-8"))
    table = calibrate(board, own)
    peers = peers_for(case, board, table, source) if multi else {}
    teams = 1 + len(peers)
    state = State.initial(board, kinds)
    congested = []
    for d, steps in enumerate(board.day_steps):
        congested.append(sum(1 for s in state.traffic.values() if s))
        plan = plan_day(board, state, steps, "tour", seconds)
        checked = simulate_day(board, state, plan.actions, steps)
        if not checked.valid:
            raise ValueError(f"{case}: {checked.errors}")
        state = checked.state
        if peers and d + 1 < len(board.day_steps):
            total = Counter()
            for history in state.road_history:
                total.update(history)
            for windows_of_peer in peers.values():
                for p, value in windows_of_peer[d].items():
                    total[p] += value
            state.traffic = {p: status_of(board, total.get(p, 0) / teams) for p in roads(board)}
    return {"case": case, "multi": multi, "teams": teams, "peers": sorted(peers), "types": kinds,
            "score": list(state.score()), "congested_roads_per_day": congested}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", default=list(GAMES))
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--workers", type=int, default=14)
    parser.add_argument("--source", choices=["full", "estimate"], default="full",
                        help="full: đếm từ replay đầy đủ trong results/peer_comparison; estimate: từ road_condition")
    parser.add_argument("--output", default=str(DATA / "demo.json"))
    args = parser.parse_args()
    table, stats = calibration_check()
    print("Bảng ước lượng Q01 (trạng thái → lưu lượng hai ngày):", {k: round(v, 2) for k, v in table.items()})
    print(f"Kiểm tra Q01+Q02: đúng trạng thái {stats['estimate_ok']}/{stats['cells']} ô-ngày; "
          f"trên ô có đông/tắc: ước lượng đúng {stats['active_estimate_ok']}/{stats['active']}, "
          f"bỏ qua đội kia đúng {stats['active_single_ok']}/{stats['active']}")
    jobs = []
    for case in args.cases:
        own = json.loads((DATA / f"own/{case}.json").read_text(encoding="utf-8"))
        kinds = own["days"][0]["teams"][0]["kinds"]
        jobs += [(case, kinds, args.seconds, False, args.source), (case, kinds, args.seconds, True, args.source)]
    with ProcessPoolExecutor(args.workers) as pool:
        results = list(pool.map(play, jobs))
    Path(args.output).write_text(json.dumps(results, indent=1), encoding="utf-8")
    for case in args.cases:
        alone = next(r for r in results if r["case"] == case and not r["multi"])
        multi = next(r for r in results if r["case"] == case and r["multi"])
        print(f"{case}: một đội {tuple(alone['score'])} | {multi['teams']} đội {tuple(multi['score'])} {multi['peers']} "
              f"| ô đông/tắc TB/ngày {sum(alone['congested_roads_per_day']) / 10:.0f} → "
              f"{sum(multi['congested_roads_per_day']) / 10:.0f}")


if __name__ == "__main__":
    main()
