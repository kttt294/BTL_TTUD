"""Đánh giá Greedy và tour trên nhiều bản đồ, chỉ chạy offline và không gọi API."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics as st
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'experiments/data/tour_robustness'
RUNS = ROOT / 'results/tour_robustness_runs'
sys.path.insert(0, str(ROOT / 'src'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Các hành trình dài để JSON gọn; tệp tổng hợp vẫn thụt dòng để dễ đọc.
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=None if path.name == 'results.json' else 2), encoding='utf8')
    temporary.replace(path)


def initialize():
    from hexudon.generator import generate_board, to_dict
    cases=[]
    for size in (8, 16, 32):
        for index in range(1, 11):
            seed=2026102100+size*100+index
            fuel=(40, 70, 100)[(index-1)%3]
            board=generate_board(size, seed, days=4, fuel=fuel)
            shift=(index%3-1)*5
            board.day_steps=[size*4+20+shift, size*2+10, size*5+10+shift, size*2+15]
            name=f'G{size}_{index:02d}'
            save(DATA/'inputs'/f'{name}.json', to_dict(board))
            cases.append({'case':name,'size':size,'map_seed':seed,'fuel_limit':fuel,
                          'steps':board.day_steps,'types':[1,0,0,0]})
    manifest={'cases':cases,'seeds':[71,72,73],'ablation_cases':[c['case'] for c in cases if c['case'].endswith(('_01','_02'))],
              'source_hashes':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in sorted((ROOT/'src').rglob('*.py'))},
              'input_hashes':{p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in sorted((DATA/'inputs').glob('*.json'))},
              'traffic':'Cập nhật từ riêng đội được mô phỏng; không biết trước giao thông ngày sau.',
              'budgets':[1,5],'default_workers':4}
    save(DATA/'manifest.json',manifest)


def jobs(manifest):
    output=[]
    for case in manifest['cases']:
        for seed in manifest['seeds']:
            for variant in ('greedy','full'):
                output.append({'case':case['case'],'seed':seed,'variant':variant,'seconds':1.,'types':case['types'],'size':case['size']})
            if case['case'] in manifest['ablation_cases']:
                for budget in (1.,5.):
                    for variant in ('full','no_local','no_cover','no_anchor'):
                        if budget==1. and variant=='full':continue
                        output.append({'case':case['case'],'seed':seed,'variant':variant,'seconds':budget,'types':case['types'],'size':case['size']})
    return output


def run(job):
    from hexudon.model import Board, State
    from hexudon.planner import plan_day
    from hexudon.simulator import simulate_day
    import hexudon.tour as tour
    board=Board.from_dict(json.loads((DATA/'inputs'/f"{job['case']}.json").read_text(encoding='utf8')))
    original={name:getattr(tour,name) for name in ('improve','cover_types','find_anchors')}
    disabled={'no_local':'improve','no_cover':'cover_types','no_anchor':'find_anchors'}.get(job['variant'])
    if disabled=='improve':tour.improve=lambda problem,solution,deadline,rng:solution
    if disabled=='cover_types':tour.cover_types=lambda candidates,deadline,rng,variants,best:best
    if disabled=='find_anchors':tour.find_anchors=lambda problem,runs,deadline,rng:None
    state=State.initial(board,job['types']);daily=[]
    try:
        for steps in board.day_steps:
            started=time.perf_counter();old_D=state.daily_sum;old_Q=state.portions
            if job['variant']=='greedy':
                plan=plan_day(board,state,steps,'greedy',job['seconds'])
                if plan.fallback:raise ValueError('Greedy phải dùng phương án chờ thay thế.')
                actions=plan.actions
            else:
                actions=tour.plan_tour(board,state,steps,job['seconds']*.9,seed=job['seed'])
            checked=simulate_day(board,state,actions,steps)
            elapsed=time.perf_counter()-started
            if not checked.valid:raise ValueError(str(checked.errors))
            state=checked.state
            daily.append({'day':state.day,'steps':steps,'types':state.daily_sum-old_D,'servings':state.portions-old_Q,
                          'score':list(state.score()),'planning_seconds':elapsed,'actions':actions,
                          'end_fuel':[a.fuel for a in state.agents],'end_positions':[a.pos for a in state.agents]})
        brands=len({p['brand'] for p in board.spots})
        return {**job,'valid':True,'score':list(state.score()),'U_bound':brands,'D_bound':brands*len(board.day_steps),'daily':daily}
    except Exception as error:
        return {**job,'valid':False,'error':str(error),'daily':daily}
    finally:
        for name,fn in original.items():setattr(tour,name,fn)


def audit(rows):
    from hexudon.model import Board,State
    from hexudon.simulator import simulate_day
    days=0
    for r in rows:
        assert r['valid'],(r['case'],r['variant'],r.get('error'))
        board=Board.from_dict(json.loads((DATA/'inputs'/f"{r['case']}.json").read_text(encoding='utf8')))
        state=State.initial(board,r['types'])
        assert len(r['daily'])==len(board.day_steps)
        for steps,day in zip(board.day_steps,r['daily']):
            result=simulate_day(board,state,day['actions'],steps)
            assert result.valid
            state=result.state
            assert list(state.score())==day['score']
            assert [a.fuel for a in state.agents]==day['end_fuel']
            assert [a.pos for a in state.agents]==day['end_positions']
            days+=1
        assert list(state.score())==r['score']
    return {'valid_runs':len(rows),'daily_plans':days,'mismatches':0,'fallback_days':0}


def stats(rows):
    times=sorted(d['planning_seconds'] for r in rows for d in r['daily'])
    return {'runs':len(rows),'mean_score':[round(st.mean(r['score'][i] for r in rows),2) for i in range(3)],
            'full_U':sum(r['score'][0]==r['U_bound'] for r in rows),'full_D':sum(r['score'][1]==r['D_bound'] for r in rows),
            'mean_D_ratio':round(st.mean(r['score'][1]/r['D_bound'] for r in rows),4),
            'mean_seconds':round(st.mean(times),4),'p95_seconds':round(times[max(0,math.ceil(.95*len(times))-1)],4),
            'max_seconds':round(max(times),4),'over_budget_days':sum(d['planning_seconds']>r['seconds'] for r in rows for d in r['daily'])}


def pairs(rows,other,budget=1.,size=None):
    sub=[r for r in rows if r['seconds']==budget and (size is None or r['size']==size)]
    base={(r['case'],r['seed']):r['score'] for r in sub if r['variant']=='full'}
    scores=[(base[r['case'],r['seed']],r['score']) for r in sub if r['variant']==other]
    return [sum(a>b for a,b in scores),sum(a==b for a,b in scores),sum(a<b for a,b in scores)]


def summarize(rows,manifest):
    matched=[r for r in rows if r['seconds']==1 and r['variant'] in ('greedy','full')]
    summary={'matched':{str(size):{v:stats([r for r in matched if r['size']==size and r['variant']==v]) for v in ('greedy','full')} for size in (8,16,32)},
             'paired':{str(size):pairs(matched,'greedy',size=size) for size in (8,16,32)},
             'per_case':{c['case']:{v:stats([r for r in matched if r['case']==c['case'] and r['variant']==v]) for v in ('greedy','full')} for c in manifest['cases']},
             'ablation':{},'budget_pairs':{},'timing':{}}
    for seconds in (1.,5.):
        subset=[r for r in rows if r['case'] in manifest['ablation_cases'] and r['seconds']==seconds and r['variant']!='greedy']
        summary['ablation'][str(int(seconds))]={v:{**stats([r for r in subset if r['variant']==v]),'paired':pairs(subset,v,seconds)} for v in ('full','no_local','no_cover','no_anchor')}
        summary['timing'][str(int(seconds))]=stats([r for r in rows if r['seconds']==seconds and r['variant']=='full'])
    for case in manifest['ablation_cases']:
        by_budget={b:{r['seed']:r['score'] for r in rows if r['case']==case and r['variant']=='full' and r['seconds']==b} for b in (1,5)}
        summary['budget_pairs'][case]=[sum(by_budget[5][s]>by_budget[1][s] for s in manifest['seeds']),sum(by_budget[5][s]==by_budget[1][s] for s in manifest['seeds']),sum(by_budget[5][s]<by_budget[1][s] for s in manifest['seeds'])]
    save(DATA/'summary.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--init',action='store_true')
    parser.add_argument('--audit-only',action='store_true')
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    if args.init:
        if (DATA/'manifest.json').exists():parser.error('Bộ input đã tồn tại; không tạo đè dữ liệu.')
        initialize()
    manifest=json.loads((DATA/'manifest.json').read_text(encoding='utf8'))
    for path,expected in manifest['source_hashes'].items():
        if args.audit_only and path not in ('src/hexudon/model.py','src/hexudon/simulator.py'):continue
        assert hashlib.sha256((ROOT/path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==expected,path
    for name,expected in manifest['input_hashes'].items():assert hashlib.sha256((DATA/'inputs'/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==expected,name
    key=lambda r:(r['case'],r['seed'],r['variant'],r['seconds'])
    path=DATA/'results.json'
    existing={key(r):r for r in json.loads(path.read_text(encoding='utf8'))} if path.exists() else {}
    # Mỗi lượt lưu riêng trước khi tổng hợp để có thể tiếp tục khi chương trình bị ngắt.
    for saved in ([] if args.audit_only else RUNS.glob('*.json')):
        r=json.loads(saved.read_text(encoding='utf8'));existing[key(r)]=r
    alljobs=jobs(manifest)
    if not args.audit_only:
        pending=[j for j in alljobs if key(j) not in existing]
        print('Lượt cần chạy:',len(pending),'/',len(alljobs),flush=True)
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(run,j):j for j in pending}
            for n,future in enumerate(as_completed(futures),1):
                r=future.result();existing[key(r)]=r
                name=f"{r['case']}_{r['variant']}_{r['seconds']}_{r['seed']}.json"
                save(RUNS/name,r)
                print(n,'/',len(pending),r['case'],r['variant'],r['seconds'],r['seed'],r.get('score',r.get('error')),flush=True)
        if pending:save(DATA/'machine.json',{'python':platform.python_version(),'platform':platform.platform(),'logical_cpus':os.cpu_count(),'workers':args.workers})
    rows=[existing[key(j)] for j in alljobs]
    if not args.audit_only:save(path,rows)
    checked=audit(rows);save(DATA/'audit.json',checked);summarize(rows,manifest)
    print('Kiểm tra:',checked,flush=True)


if __name__=='__main__':main()
