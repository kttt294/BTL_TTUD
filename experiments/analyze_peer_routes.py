"""Phân tích cách các đội chọn điểm và đường đi từ replay Practice đầy đủ (results/peer_comparison).

Các chỉ số, tính trên mọi xe tuần tra và mọi ngày:
- next_nearest_pct: điểm udon kế tiếp (chưa ghé trong ngày) là điểm gần nhất theo step.
- next_rank_mean: thứ hạng khoảng cách trung bình của điểm kế tiếp (1 = gần nhất).
- new_brand_pct: khi còn loại chưa thu trong ngày, điểm kế tiếp thuộc loại chưa thu.
- shortest_pct: đoạn giữa hai điểm có số step bằng đường ngắn nhất.
- min_fuel_pct: trong các đoạn ngắn nhất, nhiên liệu bằng mức thấp nhất trong các đường cùng step.
- road_step_pct: tỷ lệ bước đi xuất phát từ ô đường.
- overlap: số xe tuần tra trung bình ghé một điểm đã được ghé trong ngày.
- supply_moves/day, colocated_pct: xe tiếp tế di chuyển bao nhiêu lần, bao nhiêu step đứng cùng ô xe tuần tra.
- refuel_by_supply_pct: ở lần tiếp nhiên liệu, xe tiếp tế là xe vừa di chuyển tới (đi tìm xe tuần tra).
- refuel_fuel_pct: nhiên liệu còn lại (theo % dung tích) lúc được nạp, trung vị.
- end_on_spot_pct: xe tuần tra kết thúc ngày trên điểm udon.

python -X utf8 experiments/analyze_peer_routes.py
"""

from collections import Counter, defaultdict
import heapq
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
from fetch_peer_traffic import load_board

FULL = ROOT / "results/peer_comparison"


def lex_dijkstra(board, source, traffic):
    """Khoảng cách theo (step, nhiên liệu) và (step, -nhiên liệu) từ một ô."""
    best = {}
    for sign in (1, -1):
        dist = {source: (0, 0)}
        heap = [(0, 0, source)]
        while heap:
            s, f, u = heapq.heappop(heap)
            if (s, f) != dist[u]:
                continue
            ds, df = board.cost(u, traffic)
            for _, v in board.neighbors(u):
                cand = (s + ds, f + sign * df)
                if cand < dist.get(v, (1e9, 1e9)):
                    dist[v] = cand
                    heapq.heappush(heap, (cand[0], cand[1], v))
        best[sign] = dist
    return best


def analyse(board, replay):
    spots = {s["pos"]: s["brand"] for s in board.spots}
    stat = Counter()
    ranks, refuel_levels = [], []
    for day in replay["days"]:
        traffic = {int(p): s for p, s in day["road_condition"].items()}
        team = day["teams"][0]
        kinds, frames = team["kinds"], team["frames"]
        cache = {}

        def dist(p):
            if p not in cache:
                cache[p] = lex_dijkstra(board, p, traffic)
            return cache[p]

        cells = {car: [f["agents"][car]["cell"] for f in frames] for car in range(len(kinds))}
        fuels = {car: [f["agents"][car]["fuel"] for f in frames] for car in range(len(kinds))}
        # Thời điểm lần đầu mỗi xe tới mỗi điểm, để biết loại nào đã thu trước đó trong ngày.
        first = []
        visits = Counter()
        for car, kind in enumerate(kinds):
            if kind != 0:
                continue
            seen = set()
            for t, p in enumerate(cells[car]):
                if p in spots and p not in seen:
                    seen.add(p)
                    first.append((t, car, p))
                    visits[p] += 1
        stat["visited_spots"] += len(visits)
        stat["visits"] += sum(visits.values())
        for car, kind in enumerate(kinds):
            seq = cells[car]
            path = [seq[0]] + [seq[t] for t in range(1, len(seq)) if seq[t] != seq[t - 1]]
            if kind == 1:
                stat["supply_days"] += 1
                stat["supply_moves"] += len(path) - 1
                patrols = [c for c, k in enumerate(kinds) if k == 0]
                stat["supply_steps"] += len(seq) - 1
                stat["colocated"] += sum(any(cells[c][t] == seq[t] for c in patrols) for t in range(1, len(seq)))
                continue
            stat["patrol_days"] += 1
            stat["moves"] += len(path) - 1
            stat["road_moves"] += sum(board.terrain(p) == 1 for p in path[:-1])
            stat["end_on_spot"] += path[-1] in spots
            # Thứ tự ghé điểm
            seen = {seq[0]} if seq[0] in spots else set()
            stops = [i for i, p in enumerate(path) if p in spots]
            for a, b in zip(stops, stops[1:]):
                here, nxt = path[a], path[b]
                if nxt in seen:
                    continue
                d = dist(here)[1]
                options = sorted((d[q][0], q) for q in spots if q not in seen and q != here and q in d)
                if options:
                    rank = 1 + sum(1 for s, _ in options if s < d[nxt][0])
                    ranks.append(rank)
                    stat["next_total"] += 1
                    stat["next_nearest"] += rank == 1
                    # Loại đã thu trong ngày tính tới lúc xe rời điểm hiện tại
                    t_here = next(t for t in range(len(seq)) if seq[t] == here and t >= 0)
                    collected = {spots[p] for t, c, p in first if t <= t_here}
                    missing = [q for _, q in options if spots[q] not in collected]
                    if missing:
                        stat["new_total"] += 1
                        stat["new_brand"] += spots[nxt] not in collected
                seen.add(nxt)
                # Đường đi giữa hai điểm
                steps = sum(board.cost(path[k], traffic)[0] for k in range(a, b))
                fuel = sum(board.cost(path[k], traffic)[1] for k in range(a, b))
                lo, hi = dist(here)[1][nxt], dist(here)[-1][nxt]
                stat["segments"] += 1
                if steps == lo[0]:
                    stat["shortest"] += 1
                    stat["min_fuel"] += fuel == lo[1]
                    stat["tie_choice"] += lo[1] != -hi[1]
                    stat["tie_min_fuel"] += lo[1] != -hi[1] and fuel == lo[1]
            # Tiếp nhiên liệu: xe nào vừa di chuyển tới
            for t in range(1, len(seq)):
                if fuels[car][t] > fuels[car][t - 1]:
                    supply = [c for c, k in enumerate(kinds) if k == 1 and cells[c][t] == seq[t]]
                    if supply:
                        stat["refuels"] += 1
                        stat["refuel_by_supply"] += cells[supply[0]][t - 1] != cells[supply[0]][t]
                        refuel_levels.append(100 * fuels[car][t - 1] / board.fuel_limit)
    return stat, ranks, refuel_levels


def main():
    totals = defaultdict(Counter)
    ranks, levels = defaultdict(list), defaultdict(list)
    for path in sorted(FULL.glob("*_Q*.json")):
        team, case = path.stem.rsplit("_", 1)
        replay = json.loads(path.read_text(encoding="utf-8")).get("replay", {})
        if not replay.get("days") or len(replay["days"][0]["teams"][0]["frames"]) <= 1:
            continue
        stat, r, lv = analyse(load_board(case), replay)
        totals[team].update(stat)
        ranks[team] += r
        levels[team] += lv
    rows = {}
    for team, s in sorted(totals.items()):
        pct = lambda a, b: round(100 * s[a] / s[b], 1) if s[b] else None
        rows[team] = {
            "next_nearest_pct": pct("next_nearest", "next_total"),
            "next_rank_mean": round(statistics.mean(ranks[team]), 2),
            "new_brand_pct": pct("new_brand", "new_total"),
            "shortest_pct": pct("shortest", "segments"),
            "min_fuel_pct": pct("min_fuel", "shortest"),
            "tie_min_fuel_pct": pct("tie_min_fuel", "tie_choice"),
            "road_step_pct": pct("road_moves", "moves"),
            "overlap": round(s["visits"] / s["visited_spots"], 2),
            "supply_moves_per_day": round(s["supply_moves"] / s["supply_days"], 1) if s["supply_days"] else None,
            "colocated_pct": pct("colocated", "supply_steps"),
            "refuel_by_supply_pct": pct("refuel_by_supply", "refuels"),
            "refuel_fuel_pct": round(statistics.median(levels[team]), 1) if levels[team] else None,
            "end_on_spot_pct": pct("end_on_spot", "patrol_days"),
        }
    out = ROOT / "results/peer_traffic/route_analysis.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    keys = list(next(iter(rows.values())))
    print("team".ljust(12) + "".join(k[:14].rjust(15) for k in keys))
    for team, row in rows.items():
        print(team.ljust(12) + "".join(str(row[k]).rjust(15) for k in keys))


if __name__ == "__main__":
    main()
