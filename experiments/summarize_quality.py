"""Tổng hợp phép đo mới và vẽ hình đen trắng dùng trong báo cáo."""

import csv
import json
import hashlib
from pathlib import Path
import statistics as st

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'experiments/quality_results'


def read(name):
    return list(csv.DictReader((FOLDER / name).open(encoding='utf-8-sig')))


def score(row):
    return tuple(int(row[c]) for c in ('u', 'd', 'q'))


def summarize():
    exact = read('exact.csv')
    budgets = read('budgets.csv')
    groups, comparisons = [], []
    for size in (2, 3):
        for strategy in ('greedy', 'lookahead'):
            rows = [r for r in exact if int(r['size']) == size and r['strategy'] == strategy]
            same_u = [r for r in rows if r['u'] == r['optimal_u']]
            same_ud = [r for r in same_u if r['d'] == r['optimal_d']]
            groups.append({'size': size, 'strategy': strategy, 'n': len(rows),
                           'optimal': sum(int(r['optimal']) for r in rows),
                           'mean_u_gap': st.mean(int(r['optimal_u']) - int(r['u']) for r in rows),
                           'same_u': len(same_u), 'same_ud': len(same_ud),
                           'mean_d_gap_given_u': st.mean(int(r['optimal_d']) - int(r['d']) for r in same_u) if same_u else None,
                           'mean_q_gap_given_ud': st.mean(int(r['optimal_q']) - int(r['q']) for r in same_ud) if same_ud else None})
    for size in (8, 16, 32):
        for budget in (.05, .25, 1., 3.):
            rows = [r for r in budgets if int(r['size']) == size and float(r['budget']) == budget]
            greedy = {r['seed']: r for r in rows if r['strategy'] == 'greedy'}
            lookahead = {r['seed']: r for r in rows if r['strategy'] == 'lookahead'}
            assert len(greedy) == len(lookahead) == 10
            wins = sum(score(lookahead[s]) > score(greedy[s]) for s in greedy)
            ties = sum(score(lookahead[s]) == score(greedy[s]) for s in greedy)
            comparisons.append({'size': size, 'budget': budget, 'wins': wins, 'ties': ties,
                                'losses': len(greedy) - wins - ties,
                                'means': {strategy: {
                                    **{c: st.mean(int(r[c]) for r in rows if r['strategy'] == strategy) for c in ('u', 'd', 'q', 'searches')},
                                    'seconds': st.mean(float(r['seconds']) for r in rows if r['strategy'] == strategy)}
                                    for strategy in ('greedy', 'lookahead')}})
    result = {'exact': groups, 'budget_comparisons': comparisons, 'budget_games': len(budgets),
              'fallbacks': sum(int(r['fallback']) for r in budgets),
              'dp_max_seconds': max(float(r['dp_seconds']) for r in exact),
              'dp_max_states': max(int(r['dp_states']) for r in exact)}
    (FOLDER / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    files = [*FOLDER.glob('*.csv'), *FOLDER.glob('tiny_*.json'),
             *FOLDER.glob('*metadata.json'), ROOT / 'src/hexudon/exact.py',
             ROOT / 'src/hexudon/planner.py', ROOT / 'src/hexudon/search.py',
             ROOT / 'src/hexudon/simulator.py', ROOT / 'src/hexudon/model.py',
             ROOT / 'src/hexudon/generator.py', ROOT / 'experiments/benchmark_quality.py']
    manifest = {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in files}
    (FOLDER / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return result


def plots(summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import RegularPolygon
    import math
    import sys
    sys.path.insert(0, str(ROOT / 'src'))
    from hexudon.model import Board
    plt.rcParams.update({'font.family': 'Times New Roman', 'font.size': 14,
                         'text.color': 'black', 'axes.labelcolor': 'black'})
    folder = ROOT / 'docs/figures'
    folder.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5), constrained_layout=True)
    path_rows = list(csv.DictReader((ROOT / 'experiments/results/pathfinding.csv').open(encoding='utf-8-sig')))
    for ax, column, label in zip(axes, ('expanded', 'seconds'), ('Nhãn mở rộng trung bình', 'Thời gian trung bình (ms)')):
        for strategy, marker, line in [('dijkstra', 'o', '-'), ('astar', 's', '--')]:
            values = [st.mean(float(r[column]) for r in path_rows if int(r['size']) == size and r['algorithm'] == strategy) for size in (8, 16, 32)]
            if column == 'seconds':
                values = [v * 1000 for v in values]
            ax.plot([8, 16, 32], values, marker=marker, linestyle=line, color='black', label='A*' if strategy == 'astar' else 'Dijkstra')
        ax.set(xlabel='Cạnh bản đồ', ylabel=label, xticks=[8, 16, 32])
        ax.grid(alpha=.25)
        ax.legend()
    fig.savefig(folder / 'path_comparison.png', dpi=220)
    plt.close(fig)

    fig, axes = plt.subplots(3, 3, figsize=(9.3, 8), constrained_layout=True)
    for row, size in enumerate((8, 16, 32)):
        entries = [r for r in summary['budget_comparisons'] if r['size'] == size]
        for col, component in enumerate(('u', 'd', 'q')):
            ax = axes[row, col]
            for strategy, marker, line in [('greedy', 'o', '-'), ('lookahead', 's', '--')]:
                ax.plot([r['budget'] for r in entries], [r['means'][strategy][component] for r in entries],
                        marker=marker, linestyle=line, color='black', label=strategy.capitalize())
            ax.set_xscale('log')
            ax.set_xticks([.05, .25, 1, 3], ['0,05', '0,25', '1', '3'])
            ax.set_title(f'{size}×{size}: {component.upper()} trung bình')
            ax.grid(alpha=.25)
            if row == 2:
                ax.set_xlabel('Ngân sách mỗi ngày (giây)')
            if row == 0 and col == 0:
                ax.legend(fontsize=13)
    fig.savefig(folder / 'budget_sensitivity.png', dpi=220)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.8, 3.4), constrained_layout=True)
    ax.scatter([5, 7, 8], [6, 4, 7], s=70, facecolor='white', edgecolor='black')
    for x, y, label in [(5, 6, 'a (5, 6)'), (7, 4, 'b (7, 4)'), (8, 7, 'c (8, 7)')]:
        ax.annotate(label, (x, y), xytext=(8, 7), textcoords='offset points')
    ax.plot([5, 8], [6, 7], ':', color='black')
    ax.annotate('a trội c; a và b không trội nhau', (5.2, 4.5))
    ax.set(xlabel='Step đã dùng', ylabel='Nhiên liệu đã dùng', xlim=(4, 10), ylim=(3, 8.5))
    ax.grid(alpha=.25)
    fig.savefig(folder / 'resource_labels.png', dpi=220)
    plt.close(fig)

    data = json.loads((FOLDER / 'tiny_3_3103.json').read_text(encoding='utf-8'))
    board = Board.from_dict(data['config'])
    fig, axes = plt.subplots(1, 3, figsize=(9, 3.5), constrained_layout=True)
    locations = {}
    for pos in range(9):
        row, col = divmod(pos, 3)
        locations[pos] = col - .5 * (row % 2), -row * math.sqrt(3) / 2
    entries = [('Greedy', data['heuristics']['greedy']), ('Lookahead', data['heuristics']['lookahead']),
               ('Tối ưu DP', {'actions': data['optimal_actions'], 'score': data['optimal_score']})]
    spots = {s['pos']: s['brand'] for s in board.spots}
    for ax, (name, entry) in zip(axes, entries):
        for pos, (x, y) in locations.items():
            ax.add_patch(RegularPolygon((x, y), 6, radius=.56, orientation=0, fill=False, edgecolor='gray'))
            label = f'{pos}' + ('*' if pos == board.starts[0] else '')
            ax.text(x, y, label + (f'\nloại {spots[pos]}' if pos in spots else ''),
                    ha='center', va='center', fontsize=12, zorder=5,
                    bbox=dict(facecolor='white', edgecolor='none', pad=.4))
        pos = board.starts[0]
        for day, commands in enumerate(entry['actions']):
            for command in commands[0]:
                if command < 0:
                    continue
                target = board.neighbor(pos, command)
                x, y = locations[pos]
                tx, ty = locations[target]
                # Dịch nhẹ nét ngày hai để còn phân biệt khi hai tuyến trùng nhau.
                shift = .08 if day else -.08
                ax.annotate('', (tx, ty + shift), (x, y + shift),
                            arrowprops=dict(arrowstyle='->', color='black', linestyle='--' if day else '-', lw=1.2))
                pos = target
        ax.set_title(f'{name}: {tuple(entry["score"])}', fontsize=14)
        ax.set(xlim=(-1.1, 2.7), ylim=(-2.4, .8), aspect='equal')
        ax.axis('off')
    fig.savefig(folder / 'tiny_optimal_routes.png', dpi=220)
    plt.close(fig)


if __name__ == '__main__':
    result = summarize()
    plots(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
