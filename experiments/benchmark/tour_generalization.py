"""Đối chứng offline trên cấu hình đa dạng và kiểm tra riêng cơ chế ô neo."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'experiments/data/tour_generalization'
sys.path.insert(0, str(ROOT / 'src'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def make_board(size, seed, topology, cars, days, fuel, schedule):
    from hexudon.model import Board
    rng = random.Random(seed)
    cells = [[0 for _ in range(size)] for _ in range(size)]
    for row in range(size):
        for col in range(size):
            if topology == 'mixed':
                cells[row][col] = rng.choices([0, 1, 2], [6, 3, 1])[0]
            elif topology == 'bridge':
                # Vách ao giữa bản đồ, chỉ có cầu đường ở hàng giữa.
                cells[row][col] = 3 if col == size // 2 else 0
                if row == size // 2:
                    cells[row][col] = 1
            elif topology == 'islands':
                # Hai vùng đi được tách rời để kiểm tra cả loại không tiếp cận được.
                cells[row][col] = 3 if col == size // 2 else 0
    if schedule == 'alternating':
        steps = [size * (5 if day % 2 == 0 else 1) + 8 for day in range(days)]
    elif schedule == 'steady':
        steps = [size * 3 + 8] * days
    else:
        steps = [size * 2 + 12] * days
    board = Board(cells, [], [], steps, fuel)
    plain = [p for p in range(size * size) if board.terrain(p) == 0]
    rng.shuffle(plain)
    # Cố định thứ tự xe trong từng input, không chọn lại đội hình theo thuật toán.
    starts = plain[:cars]
    positions = plain[cars:cars + min(24, size * size // 4)]
    if topology == 'islands':
        starts = [p for p in plain if p % size < size // 2][:cars]
        positions = [p for p in plain if p not in starts][:min(24, size * size // 4)]
    board.starts = starts
    brands = min(12, max(4, len(positions) // 2))
    board.spots = [{'pos': p, 'brand': i % brands, 'stocks': rng.randint(1, cars)}
                   for i, p in enumerate(positions)]
    return board


def initialize():
    from hexudon.generator import to_dict
    from hexudon.model import Board
    cases = []
    for size in (8, 16, 32):
        for ti, topology in enumerate(('mixed', 'bridge', 'islands')):
            for setting in range(2):
                cars = (3, 5, 8)[(ti + setting) % 3]
                days = (2, 5, 10)[(ti + setting) % 3]
                fuel = (40, 100, 200)[(ti + setting) % 3]
                kinds = ([0] * cars if setting == 0 else [1] + [0] * (cars - 1))
                name = f'V{size}_{topology}_{setting + 1}'
                board = make_board(size, 2026102200 + size * 100 + ti * 10 + setting,
                                   topology, cars, days, fuel, 'ordinary')
                cases.append({'case': name, 'group': 'diverse', 'size': size, 'topology': topology,
                              'types': kinds, 'days': days, 'fuel': fuel, 'schedule': 'ordinary'})
                save(DATA / 'inputs' / f'{name}.json', to_dict(board))
    # Chọn sẵn cặp lịch; không giữ riêng những input mà ô neo thắng.
    for size in (8, 16, 32):
        for schedule in ('steady', 'alternating'):
            name = f'A{size}_{schedule}'
            board = make_board(size, 2026102300 + size, 'bridge', 3, 4, 160, schedule)
            cases.append({'case': name, 'group': 'anchor', 'size': size, 'topology': 'bridge',
                          'types': [1, 0, 0], 'days': 4, 'fuel': 160, 'schedule': schedule})
            save(DATA / 'inputs' / f'{name}.json', to_dict(board))
    for c in cases:
        Board.from_dict(json.loads((DATA / 'inputs' / f"{c['case']}.json").read_text(encoding='utf8')))
    manifest = {'cases': cases, 'seeds': [71, 72], 'diverse_seconds': 1., 'anchor_seconds': 3.,
                'variants': ['greedy', 'full', 'no_anchor'],
                'scope': 'Một đội; giao thông từ lịch sử riêng; không dùng API; input không được lọc theo điểm.',
                'design_limit': 'Thiết kế cấu hình đan xen, không phải toàn bộ tích Descartes; hai lượt theo seed không là hai bản đồ độc lập.',
                'source_hashes': {str(p.relative_to(ROOT)).replace('\\', '/'): digest(p)
                                  for p in sorted((ROOT / 'src').rglob('*.py'))},
                'input_hashes': {p.name: digest(p) for p in sorted((DATA / 'inputs').glob('*.json'))}}
    save(DATA / 'manifest.json', manifest)


def jobs(manifest):
    return [{**c, 'seed': seed, 'variant': variant,
             'seconds': manifest['anchor_seconds' if c['group'] == 'anchor' else 'diverse_seconds']}
            for c in manifest['cases'] for seed in manifest['seeds']
            for variant in (('full', 'no_anchor') if c['group'] == 'anchor' else manifest['variants'])]


def run(job):
    from hexudon.model import Board, State
    from hexudon.planner import plan_day
    from hexudon.simulator import simulate_day
    import hexudon.tour as tour
    board = Board.from_dict(json.loads((DATA / 'inputs' / f"{job['case']}.json").read_text(encoding='utf8')))
    state = State.initial(board, job['types'])
    original = tour.find_anchors
    events = []
    def observe(problem, runs, deadline, rng):
        started = time.perf_counter()
        result = None if job['variant'] == 'no_anchor' else original(problem, runs, deadline, rng)
        events.append({'day': state.day + 1, 'found': result is not None,
                       'seconds': time.perf_counter() - started})
        return result
    tour.find_anchors = observe
    daily = []
    try:
        for steps in board.day_steps:
            started = time.perf_counter()
            old_D, old_Q = state.daily_sum, state.portions
            if job['variant'] == 'greedy':
                plan = plan_day(board, state, steps, 'greedy', job['seconds'])
                assert not plan.fallback, 'Greedy đã dùng kế hoạch thay thế.'
                actions = plan.actions
            else:
                actions = tour.plan_tour(board, state, steps, .9 * job['seconds'], seed=job['seed'])
            result = simulate_day(board, state, actions, steps)
            elapsed = time.perf_counter() - started
            assert result.valid, result.errors
            state = result.state
            daily.append({'day': state.day, 'steps': steps, 'types': state.daily_sum - old_D,
                          'servings': state.portions - old_Q, 'score': list(state.score()),
                          'actions': actions, 'seconds': elapsed,
                          'positions': [a.pos for a in state.agents], 'fuel': [a.fuel for a in state.agents]})
    finally:
        tour.find_anchors = original
    brands = len({s['brand'] for s in board.spots})
    return {**job, 'score': list(state.score()), 'U_bound': brands,
            'D_bound': brands * len(board.day_steps), 'daily': daily, 'anchor_calls': events}


def summarize(rows):
    key = lambda r: (r['case'], r['seed'])
    full = {key(r): r for r in rows if r['variant'] == 'full'}
    def compare(subset, variant):
        pairs = [(full[key(r)]['score'], r['score']) for r in subset if r['variant'] == variant]
        return {'pairs': len(pairs), 'full_wins': sum(a > b for a, b in pairs),
                'ties': sum(a == b for a, b in pairs), 'full_losses': sum(a < b for a, b in pairs)}
    def stats(subset):
        times = [d['seconds'] for r in subset for d in r['daily']]
        return {'runs': len(subset), 'mean_score': [round(statistics.mean(r['score'][i] for r in subset), 3) for i in range(3)],
                'full_U': sum(r['score'][0] == r['U_bound'] for r in subset),
                'full_D': sum(r['score'][1] == r['D_bound'] for r in subset),
                'mean_seconds': round(statistics.mean(times), 4), 'max_seconds': round(max(times), 4),
                'over_budget_days': sum(d['seconds'] > r['seconds'] for r in subset for d in r['daily']),
                'anchor_calls': sum(len(r['anchor_calls']) for r in subset),
                'found_anchor_calls': sum(e['found'] for r in subset for e in r['anchor_calls'])}
    groups = {}
    for group, field, values in [('diverse', 'topology', ['mixed', 'bridge', 'islands']),
                                  ('anchor', 'schedule', ['steady', 'alternating'])]:
        for value in values:
            subset = [r for r in rows if r['group'] == group and r[field] == value]
            groups[f'{group}/{value}'] = {'comparisons': {v: compare(subset, v) for v in ['greedy', 'no_anchor']
                                                         if any(r['variant'] == v for r in subset)},
                                         'stats': {v: stats([r for r in subset if r['variant'] == v])
                                                   for v in ['greedy', 'full', 'no_anchor'] if any(r['variant'] == v for r in subset)}}
    return {'runs': len(rows), 'daily_plans': sum(len(r['daily']) for r in rows), 'groups': groups,
            'per_case': {case: {v: compare([r for r in rows if r['case'] == case], v) for v in ['greedy', 'no_anchor']
                                 if any(r['case'] == case and r['variant'] == v for r in rows)}
                         for case in sorted({r['case'] for r in rows})},
            'found_anchor_is_acceptance': False,
            'notes': 'Số lần tìm thấy ô neo chỉ ghi đầu ra find_anchors, không khẳng định tuyến neo được chọn. Bỏ ô neo giải phóng thời gian cho phần khác; đây là so cấu hình cùng ngân sách.'}


def audit(rows, manifest):
    from hexudon.model import Board, State
    from hexudon.simulator import simulate_day
    count = 0
    for row in rows:
        board = Board.from_dict(json.loads((DATA / 'inputs' / f"{row['case']}.json").read_text(encoding='utf8')))
        state = State.initial(board, row['types'])
        assert len(row['daily']) == len(board.day_steps)
        for steps, day in zip(board.day_steps, row['daily']):
            result = simulate_day(board, state, day['actions'], steps)
            assert result.valid, (row['case'], result.errors)
            state = result.state
            assert list(state.score()) == day['score']
            assert [a.pos for a in state.agents] == day['positions']
            assert [a.fuel for a in state.agents] == day['fuel']
            count += 1
        assert list(state.score()) == row['score']
    expected = jobs(manifest)
    key = lambda j: (j['case'], j['seed'], j['variant'])
    assert {key(r) for r in rows} == {key(j) for j in expected}
    return {'runs': len(rows), 'daily_plans': count, 'mismatches': 0, 'invalid': 0, 'fallback': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--init', action='store_true')
    parser.add_argument('--audit-only', action='store_true')
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()
    if args.init:
        if (DATA / 'manifest.json').exists():
            parser.error('Bộ input đã tồn tại; không ghi đè.')
        initialize()
    manifest = json.loads((DATA / 'manifest.json').read_text(encoding='utf8'))
    for path, expected in manifest['source_hashes'].items():
        if not args.audit_only or path in ('src/hexudon/model.py', 'src/hexudon/simulator.py'):
            assert digest(ROOT / path) == expected, path
    for path, expected in manifest['input_hashes'].items():
        assert digest(DATA / 'inputs' / path) == expected, path
    job_list = jobs(manifest)
    output = DATA / 'runs'
    key = lambda j: f"{j['case']}_{j['seed']}_{j['variant']}.json"
    pending = [j for j in job_list if not (output / key(j)).exists()]
    if not args.audit_only:
        print('Lượt cần chạy:', len(pending), '/', len(job_list), flush=True)
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for index, row in enumerate(pool.map(run, pending), 1):
                save(output / key(row), row)
                print(index, '/', len(pending), row['case'], row['variant'], row['score'], flush=True)
        save(DATA / 'machine.json', {'python': platform.python_version(), 'platform': platform.platform(),
                                    'workers': args.workers, 'concurrent_other_workloads': 'Không cô lập tải; người dùng đang chạy thí nghiệm riêng.'})
    rows = [json.loads((output / key(j)).read_text(encoding='utf8')) for j in job_list]
    save(DATA / 'audit.json', audit(rows, manifest))
    save(DATA / 'summary.json', summarize(rows))
    print('Hoàn tất:', len(rows), 'lượt.', flush=True)


if __name__ == '__main__':
    main()
