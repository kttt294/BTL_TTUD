"""Đo đóng góp phối hợp mục tiêu, Lookahead và chọn vai trò với cùng bộ điều khiển."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from hexudon.generator import generate_board, to_dict
from hexudon.model import Board, State
from hexudon.simulator import simulate_day
from ablation_planner import plan_day


def illustrative_board(name):
    # Hai input minh họa có kích thước 8×8 và bốn xe như dải quy định BTC.
    if name=='shared_stock':
        return Board([[0]*8 for _ in range(8)],
                     [dict(pos=p,brand=i,stocks=1) for i,p in enumerate((28,29,35,36))],
                     [18,19,26,27],[14,14],24)
    return Board([[0]*8 for _ in range(8)],
                 [dict(pos=p,brand=i%3,stocks=4) for i,p in enumerate((19,20,27,28,35,36))],
                 [9,10,17,18],[32]*4,8)


def play(board, kinds, coordinate=True, strategy='greedy'):
    state=State.initial(board,kinds)
    plans, days, total_searches, fallback = [], [], 0, 0
    started=time.perf_counter()
    for day, steps in enumerate(board.day_steps):
        plan=plan_day(board,state,steps,strategy,coordinate)
        if plan.fallback:
            raise ValueError(f'Thí nghiệm không dùng fallback: {plan.errors}')
        result=simulate_day(board,state,plan.actions,steps,record=True)
        assert result.valid,result.errors
        collected=[p for frame in result.trace for p in frame['collected']]
        plans.append(plan.actions)
        days.append(dict(day=day+1, score=result.state.score(),searches=plan.searches,
                         seconds=plan.elapsed, fuel=[a.fuel for a in result.state.agents],
                         positions=[a.pos for a in result.state.agents],
                         collected_positions=collected,
                         road_busy=sum(v==1 for v in result.state.traffic.values()),
                         road_jammed=sum(v==2 for v in result.state.traffic.values())))
        total_searches+=plan.searches
        fallback+=int(plan.fallback)
        state=result.state
    return dict(types=kinds,score=state.score(),actions=plans,days=days,
                searches=total_searches,seconds=time.perf_counter()-started,fallback=fallback)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--seeds',nargs='+',type=int,default=[42000,42001,42002])
    parser.add_argument('--sizes',nargs='+',type=int,default=[8,16,32])
    parser.add_argument('--output',default='experiments/ablation_results')
    args=parser.parse_args()
    folder=ROOT/args.output
    folder.mkdir(parents=True,exist_ok=True)
    inputs=[(f'generated_{size}_{seed}',generate_board(size,seed), 'generated')
            for size in args.sizes for seed in args.seeds]
    inputs += [(name,illustrative_board(name),'illustrative') for name in ('shared_stock','scarce_fuel')]
    rows=[]
    for name,board,group in inputs:
        (folder/f'{name}_input.json').write_text(json.dumps(to_dict(board),ensure_ascii=False,indent=2),encoding='utf8')
        count=len(board.starts)
        trials={}
        evaluations={}
        evaluations['independent']=play(board,[0]*count,False)
        evaluations['coordinated']=play(board,[0]*count)
        evaluations['lookahead']=play(board,[0]*count,strategy='lookahead')
        trials['all_patrol']=evaluations['coordinated']
        for car in range(count):
            kinds=[0]*count
            kinds[car]=1
            trials[f'supply_{car}']=play(board,kinds)
        evaluations['last_supply']=trials[f'supply_{count-1}']
        best_name=max(trials,key=lambda key:tuple(trials[key]['score']))
        evaluations['selected']=trials[best_name]
        row=dict(case=name,group=group,size=board.width,
                 scores={k:v['score'] for k,v in evaluations.items()},
                 seconds={k:v['seconds'] for k,v in evaluations.items()},
                 searches={k:v['searches'] for k,v in evaluations.items()},
                 selected_types=evaluations['selected']['types'],selected_candidate=best_name,
                 selection_candidates=len(trials),
                 selection_seconds=sum(v['seconds'] for v in trials.values()),
                 executed_games=3+count,days_per_game=len(board.day_steps))
        (folder/f'{name}_detail.json').write_text(json.dumps(dict(summary=row,evaluations=evaluations,
                     selection_trials=trials),ensure_ascii=False,indent=2),encoding='utf8')
        rows.append(row)
        (folder/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
        print(name,row['scores'],f"selection={row['selection_seconds']:.2f}s",flush=True)
    metadata=dict(python=platform.python_version(),platform=platform.platform(),sizes=args.sizes,
                  seeds=args.seeds,deadline=False,source='one team, simulator TTUD',
                  note='Đo bỏ thành phần bằng planner sao chép cố định; không dùng để chứng minh đạt hạn 30 giây.',
                  unique_games=sum(r['executed_games'] for r in rows),
                  unique_days=sum(r['executed_games']*r['days_per_game'] for r in rows),
                  selection_family='all patrol or exactly one supply, fixed initial positions',
                  planner_sha256=hashlib.sha256((ROOT/'experiments/ablation_planner.py').read_bytes()).hexdigest())
    (folder/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':
    main()
