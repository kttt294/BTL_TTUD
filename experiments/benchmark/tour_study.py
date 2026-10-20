"""Đối chứng thành phần tour trên cùng input, đội hình và ngân sách; chỉ chạy offline."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'experiments/data/tour_study'
sys.path.insert(0, str(ROOT / 'src'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def run(job):
    from hexudon.model import Board, State
    from hexudon.planner import plan_day
    from hexudon.simulator import simulate_day
    import hexudon.tour as tour
    board = Board.from_dict(json.loads((DATA/'inputs'/f"{job['case']}.json").read_text(encoding='utf8')))
    originals = {n: getattr(tour, n) for n in ['improve','cover_types','find_anchors']}
    activity = {n: 0 for n in originals}
    disabled = {'no_local':'improve','no_cover':'cover_types','no_anchor':'find_anchors'}.get(job['variant'])
    def instrument(name):
        def call(*args, **kwargs):
            activity[name] += 1
            if name == disabled:
                if name == 'improve': return args[1]
                if name == 'cover_types': return args[-1]
                return None
            return originals[name](*args, **kwargs)
        return call
    for name in originals: setattr(tour, name, instrument(name))
    state = State.initial(board, job['types'])
    brands = len({s['brand'] for s in board.spots})
    daily=[]; started=time.perf_counter()
    try:
        for steps in board.day_steps:
            old=deepcopy(state); before=time.perf_counter(); fall=False
            if job['variant']=='greedy':
                plan=plan_day(board,state,steps,'greedy',job['seconds'])
                actions=plan.actions;fall=plan.fallback
            else:
                actions=tour.plan_tour(board,state,steps,job['seconds']*.9,seed=job['seed'])
            planning=time.perf_counter()-before
            checked=simulate_day(board,state,actions,steps,record=True)
            if not checked.valid: raise ValueError(str(checked.errors))
            state=checked.state
            daily.append({'day':state.day,'steps':steps,'types':state.daily_sum-old.daily_sum,
                          'servings':state.portions-old.portions,'score':list(state.score()),
                          'planning_seconds':planning,'greedy_fallback':fall,
                          'start_fuel':[a.fuel for a in old.agents],
                          'end_fuel':[a.fuel for a in state.agents],
                          'start_positions':[a.pos for a in old.agents],
                          'end_positions':[a.pos for a in state.agents],
                          'actions':actions})
        return {**job,'valid':True,'score':list(state.score()),'U_bound':brands,
                'D_bound':brands*len(board.day_steps),'full_D':state.daily_sum==brands*len(board.day_steps),
                'daily':daily,'activity':activity,'elapsed_seconds':time.perf_counter()-started}
    except Exception as error:
        return {**job,'valid':False,'error':str(error),'daily':daily,
                'activity':activity,'elapsed_seconds':time.perf_counter()-started}
    finally:
        for name, fn in originals.items():setattr(tour,name,fn)


def jobs(manifest):
    output=[]
    for case in manifest['cases']:
        variants=['greedy','full']
        if case['case'] in manifest['ablation_cases']:
            variants+=['no_local','no_cover','no_anchor']
        for seed in manifest['seeds']:
            for variant in variants:
                output.append({'case':case['case'],'source':case['source'],'seed':seed,
                               'variant':variant,'types':case['types'],'seconds':1.0,'experiment':'matched'})
    # Phép đối chứng 2x2: planner và đội hình là hai yếu tố được giữ tách biệt.
    q01=next(c for c in manifest['cases'] if c['case']=='Q01')
    for seed in manifest['seeds']:
        for variant in ['greedy','full']:
            output.append({'case':'Q01','source':'practice','seed':seed,'variant':variant,
                           'types':[0]*len(q01['types']),'seconds':1.0,'experiment':'roles'})
    # Tăng ngân sách trên ba input; không coi đây là giới hạn chính thức của cuộc thi.
    for case in ['Q01','Q06','G16']:
        c=next(c for c in manifest['cases'] if c['case']==case)
        for seed in manifest['seeds']:
            output.append({'case':case,'source':c['source'],'seed':seed,'variant':'full',
                           'types':c['types'],'seconds':3.0,'experiment':'budget'})
    return output


def audit(rows):
    from hexudon.model import Board,State
    from hexudon.simulator import simulate_day
    days=0
    for r in rows:
        if not r['valid']:continue
        b=Board.from_dict(json.loads((DATA/'inputs'/f"{r['case']}.json").read_text(encoding='utf8')))
        s=State.initial(b,r['types'])
        for step,d in zip(b.day_steps,r['daily']):
            checked=simulate_day(b,s,d['actions'],step)
            assert checked.valid,(r['case'],r['variant'],d['day'])
            s=checked.state
            assert list(s.score())==d['score']
            assert [a.fuel for a in s.agents]==d['end_fuel']
            assert [a.pos for a in s.agents]==d['end_positions']
            days+=1
        assert list(s.score())==r['score']
    return {'runs':len(rows),'invalid_runs':sum(not r['valid'] for r in rows),'verified_daily_plans':days,
            'score_position_fuel_mismatches':0,'greedy_fallback_days':sum(d['greedy_fallback'] for r in rows for d in r['daily'])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--audit-only',action='store_true')
    parser.add_argument('--cases',nargs='+')
    parser.add_argument('--seeds',nargs='+',type=int)
    args=parser.parse_args()
    manifest=json.loads((DATA/'manifest.json').read_text(encoding='utf8'))
    # Xác nhận mã dùng đo không bị thay đổi so với bản được mô tả trong báo cáo.
    for path,expected in manifest['source_hashes'].items():
        if args.audit_only and path not in ('src/hexudon/model.py','src/hexudon/simulator.py'):
            continue
        assert hashlib.sha256((ROOT/path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()==expected,path
    for name,expected in manifest['input_hashes'].items():
        assert hashlib.sha256((DATA/'inputs'/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==expected,name
    alljobs=jobs(manifest)
    if args.cases:alljobs=[j for j in alljobs if j['case'] in args.cases]
    if args.seeds:alljobs=[j for j in alljobs if j['seed'] in args.seeds]
    fields=['case','source','seed','variant','types','seconds','experiment']
    key=lambda j:hashlib.sha256(json.dumps({k:j[k] for k in fields},sort_keys=True).encode()).hexdigest()[:16]
    results_path=DATA/'results.json'
    saved=json.loads(results_path.read_text(encoding='utf8')) if results_path.exists() else []
    existing={key(r):r for r in saved}
    if args.audit_only:
        rows=[existing[key(j)] for j in alljobs]
    else:
        pending=[j for j in alljobs if key(j) not in existing]
        print('Lượt cần đo:',len(pending),'/',len(alljobs),flush=True)
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(run,j):j for j in pending}
            for n,future in enumerate(as_completed(futures),1):
                value=future.result();existing[key(futures[future])]=value
                save(results_path,list(existing.values()))
                print(n,'/',len(pending),value['case'],value['variant'],value['seed'],value.get('score',value.get('error')),flush=True)
        rows=[existing[key(j)] for j in alljobs]
        save(DATA/'machine.json',{'python':platform.python_version(),'platform':platform.platform(),
             'processor':platform.processor(),'logical_cpu_count':os.cpu_count(),'workers':args.workers,
             'note':'Cùng máy, tối đa 3 tiến trình; ngân sách theo đồng hồ thực, có thể vượt do bước không bị ngắt.'})
    result=audit(rows);save(DATA/'audit.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
