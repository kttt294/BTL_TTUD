"""So Dijkstra lưu cây với A* lưu từng cặp trên cùng tác vụ tạo chặng của tour."""

import argparse
from collections import defaultdict
import hashlib
import heapq
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hexudon.model import Board
from hexudon.tour import Legs, VARIANTS, INF

DATA = ROOT / 'experiments/data/path_reuse'


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


class PairAStar:
    """Cùng chi phí và đầu ra với Legs; mỗi cặp nguồn, đích, trọng số có một kết quả."""

    def __init__(self, graph):
        self.graph = graph
        self.cache, self.paths, self.heuristics = {}, {}, {}
        self.minimum = [min(a * s + b * f for p, (s, f) in enumerate(graph.cost)
                            if graph.nbrs[p]) for a, b in VARIANTS]

    def leg(self, source, goal, variant):
        key = source, goal, variant
        if key in self.cache:
            return self.cache[key]
        a, b = VARIANTS[variant]
        # Khoảng cách lục giác nhân cạnh rẻ nhất là cận dưới nhất quán.
        hkey = goal, variant
        if hkey not in self.heuristics:
            self.heuristics[hkey] = {}
        estimates = self.heuristics[hkey]

        def heuristic(pos):
            if pos not in estimates:
                estimates[pos] = self.graph.board.distance(pos, goal) * self.minimum[variant]
            return estimates[pos]

        size = len(self.graph.cost)
        dist, steps, fuel = [INF] * size, [0] * size, [0] * size
        parent, pdir = [-1] * size, [-1] * size
        dist[source] = 0.
        heap = [(heuristic(source), 0., source)]
        while heap:
            _, d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            if u == goal:
                actions, spots, pos = [], set(), goal
                while pos != source:
                    if pos in self.graph.spot_set:
                        spots.add(pos)
                    actions.append(pdir[pos])
                    pos = parent[pos]
                self.paths[key] = actions[::-1]
                self.cache[key] = steps[goal], fuel[goal], frozenset(spots)
                return self.cache[key]
            su, fu = self.graph.cost[u]
            nd = d + a * su + b * fu
            for direction, v in self.graph.nbrs[u]:
                if nd < dist[v] - 1e-9:
                    dist[v] = nd
                    steps[v], fuel[v] = steps[u] + su, fuel[u] + fu
                    parent[v], pdir[v] = u, direction
                    heapq.heappush(heap, (nd + heuristic(v), nd, v))
        self.paths[key] = []
        self.cache[key] = INF, INF, frozenset()
        return self.cache[key]

    def directions(self, source, goal, variant):
        result = self.leg(source, goal, variant)
        if result[0] == INF:
            raise ValueError('Không có đường đi giữa hai ô.')
        return self.paths[source, goal, variant]


def workload(board, seed):
    # Danh sách được xác định từ input, không chọn theo tốc độ của thuật toán.
    spots = sorted(s['pos'] for s in board.spots)
    sources = list(dict.fromkeys(board.starts + spots[:4]))
    single, many = [], []
    rng = random.Random(seed)
    for source in sources:
        goals = [p for p in spots if p != source]
        rng.shuffle(goals)
        for variant in range(3):
            single.append((source, goals[0], variant))
            many.extend((source, goal, variant) for goal in goals)
    return {'single': single, 'many': many, 'reuse': many * 3}


def verify_path(graph, solver, query, result):
    source, goal, _ = query
    if result[0] == INF:
        return
    steps, fuel, spots, pos = 0, 0, set(), source
    for direction in solver.directions(*query):
        s, f = graph.cost[pos]
        steps, fuel = steps + s, fuel + f
        target = graph.board.neighbor(pos, direction)
        assert target is not None, (query, pos, direction)
        pos = target
        if pos in graph.spot_set:
            spots.add(pos)
    assert pos == goal
    assert (steps, fuel, frozenset(spots)) == result


def summarize(rows):
    groups = []
    for size in (8, 16, 32):
        for mode in ('single', 'many', 'reuse'):
            selected = [r for r in rows if r['size'] == size and r['mode'] == mode]
            pairs = defaultdict(dict)
            for row in selected:
                pairs[row['case'], row['traffic'], row['repeat']][row['algorithm']] = row['seconds']
            means = {name: statistics.mean(r['seconds'] for r in selected if r['algorithm'] == name)
                     for name in ('dijkstra', 'astar')}
            groups.append({'size': size, 'mode': mode, 'timed_pairs': len(pairs),
                           'mean_queries': statistics.mean(r['queries'] for r in selected),
                           'dijkstra_ms': means['dijkstra'] * 1000,
                           'astar_ms': means['astar'] * 1000,
                           'astar_over_dijkstra': means['astar'] / means['dijkstra'],
                           'dijkstra_faster_pairs': sum(p['dijkstra'] < p['astar'] for p in pairs.values()),
                           'astar_faster_pairs': sum(p['astar'] < p['dijkstra'] for p in pairs.values())})
    return {'groups': groups, 'timed_runs': len(rows),
            'note': 'Ba lần đo cùng input không phải ba bản đồ độc lập. Tỷ số là thời gian A* chia Dijkstra, không phải mức tăng điểm toàn trận.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    paths = sorted((ROOT / 'experiments/data/tour_robustness/inputs').glob('*.json'))
    assert len(paths) == 30
    if args.audit_only:
        manifest = json.loads((DATA / 'manifest.json').read_text(encoding='utf8'))
        for p, expected in manifest['hashes'].items():
            assert digest(ROOT / p) == expected, p
        results = json.loads((DATA / 'results.json').read_text(encoding='utf8'))
        assert summarize(results) == json.loads((DATA / 'summary.json').read_text(encoding='utf8'))
        print('Dấu mã nguồn, input và tổng hợp thời gian khớp; audit đường đi nằm trong audit.json.')
        return
    manifest = {'date_local': '2026-10-23', 'repeats': args.repeats,
                'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'hashes': {str(p.relative_to(ROOT)).replace('\\', '/'): digest(p)
                           for p in paths + [Path(__file__), ROOT / 'src/hexudon/tour.py', ROOT / 'src/hexudon/model.py']},
                'design': '30 input đã lưu: 10 mỗi cỡ 8,16,32. Hai trạng thái đường: thông thoáng và mã trạng thái giả lập (pos+seed)%3. Nguồn là vị trí xuất phát và 4 điểm bán đầu theo chỉ số ô; đích là các điểm bán khác nguồn, xáo thứ tự bằng seed cố định. Ba trọng số đúng VARIANTS của tour. single: một đích/nguồn/trọng số; many: mọi đích; reuse: lặp nguyên many ba lần. Mỗi phép đo bắt đầu với cache rỗng của cả hai phương pháp; lần gọi lặp được cache ở cả hai.',
                'timing': 'Một tiến trình, không deadline/cutoff, thứ tự hai thuật toán đảo luân phiên. Đồ thị chi phí và láng giềng dùng chung đã tạo ngoài đồng hồ. Khởi tạo cache, tính heuristic lười, tìm và truy vết chặng nằm trong đồng hồ. Kiểm tra kết quả nằm ngoài đồng hồ; không đo đỉnh bộ nhớ. Không cô lập tác vụ khác của người dùng.',
                'scope': 'Tạo chặng theo tổng trọng số, một nhãn/ô; không áp giới hạn step/nhiên liệu riêng từng truy vấn. Không thay thế khảo sát đa nhãn trong search.py, không đo điểm toàn trận, không gọi API.'}
    (DATA / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    rows, audit = [], {'unique_pairs_checked': 0, 'weighted_cost_mismatches': 0,
                       'invalid_paths': 0, 'different_resource_pairs': 0,
                       'different_spot_sets': 0, 'unreachable_pairs': 0}
    for case_index, path in enumerate(paths):
        board = Board.from_dict(json.loads(path.read_text(encoding='utf8')))
        seed = 2026102300 + case_index
        jobs = workload(board, seed)
        for ti, traffic_name in enumerate(('free', 'varied')):
            traffic = {} if ti == 0 else {p: (p + seed) % 3 for p in range(board.width * board.height) if board.terrain(p) == 1}
            graph = Legs(board, traffic, {s['pos'] for s in board.spots})
            # Kiểm tra toàn bộ cặp trước phép đo; cache đo thời gian được tạo mới.
            reference, candidate = Legs(board, traffic, graph.spot_set), PairAStar(graph)
            for query in jobs['many']:
                left, right = reference.leg(*query), candidate.leg(*query)
                a, b = VARIANTS[query[2]]
                assert (left[0] == INF) == (right[0] == INF)
                if left[0] == INF:
                    audit['unreachable_pairs'] += 1
                else:
                    assert abs(a * left[0] + b * left[1] - a * right[0] - b * right[1]) < 1e-7, query
                    verify_path(graph, reference, query, left)
                    verify_path(graph, candidate, query, right)
                    audit['different_resource_pairs'] += left[:2] != right[:2]
                    audit['different_spot_sets'] += left[2] != right[2]
                audit['unique_pairs_checked'] += 1
            for mode, queries in jobs.items():
                for repeat in range(args.repeats):
                    order = ('dijkstra', 'astar') if (case_index + ti + repeat) % 2 == 0 else ('astar', 'dijkstra')
                    for algorithm in order:
                        start = time.perf_counter()
                        if algorithm == 'dijkstra':
                            solver = Legs.__new__(Legs)
                            solver.board, solver.spot_set = board, graph.spot_set
                            solver.cost, solver.nbrs = graph.cost, graph.nbrs
                            solver.trees, solver.legs = {}, {}
                        else:
                            solver = PairAStar(graph)
                        for query in queries:
                            solver.leg(*query)
                        elapsed = time.perf_counter() - start
                        rows.append({'case': path.stem, 'size': board.width, 'traffic': traffic_name,
                                     'mode': mode, 'repeat': repeat, 'algorithm': algorithm,
                                     'queries': len(queries), 'seconds': elapsed,
                                     'searches': len(solver.trees) if algorithm == 'dijkstra' else len(solver.cache)})
        print(case_index + 1, '/', len(paths), path.stem, flush=True)
    (DATA / 'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf8')
    (DATA / 'summary.json').write_text(json.dumps(summarize(rows), ensure_ascii=False, indent=2), encoding='utf8')
    (DATA / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf8')
    (DATA / 'machine.json').write_text(json.dumps({'python': sys.version, 'platform': platform.platform(),
                                                  'processor': platform.processor(), 'workers': 1}, indent=2), encoding='utf8')
    print(json.dumps(audit, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
