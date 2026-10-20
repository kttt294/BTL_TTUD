"""Chấm lại từng kế hoạch đã lưu và tổng hợp đối chứng tách thành phần."""

import json
from pathlib import Path
from statistics import mean
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from hexudon.model import Board, State
from hexudon.simulator import simulate_day

folder=ROOT/'experiments/ablation_results'
rows=json.loads((folder/'summary.json').read_text(encoding='utf8'))
games,days=0,0
for row in rows:
    cfg=json.loads((folder/f"{row['case']}_input.json").read_text(encoding='utf8'))
    board=Board.from_dict(cfg)
    detail=json.loads((folder/f"{row['case']}_detail.json").read_text(encoding='utf8'))
    unique=[detail['evaluations'][k] for k in ('independent','coordinated','lookahead')]
    unique += [v for k,v in detail['selection_trials'].items() if k!='all_patrol']
    for trial in unique:
        state=State.initial(board,trial['types'])
        for steps,actions in zip(board.day_steps,trial['actions']):
            result=simulate_day(board,state,actions,steps)
            assert result.valid,result.errors
            state=result.state
            days+=1
        assert list(state.score())==trial['score']
        assert trial['fallback']==0
        games+=1
    selected=detail['evaluations']['selected']
    assert tuple(selected['score'])==max(tuple(t['score']) for t in detail['selection_trials'].values())
    assert tuple(selected['score'])>=tuple(detail['evaluations']['coordinated']['score'])
generated=[r for r in rows if r['group']=='generated']
comparisons=[]
for size in (8,16,32):
    subset=[r for r in generated if r['size']==size]
    for improved,baseline in [('coordinated','independent'),('lookahead','coordinated'),
                              ('last_supply','coordinated'),('selected','last_supply')]:
        pairs=[(tuple(r['scores'][improved]),tuple(r['scores'][baseline])) for r in subset]
        comparisons.append(dict(size=size,method=improved,baseline=baseline,
             n=len(pairs),wins=sum(a>b for a,b in pairs),ties=sum(a==b for a,b in pairs),losses=sum(a<b for a,b in pairs),
             mean_searches_new=mean(r['searches'][improved] for r in subset),
             mean_searches_baseline=mean(r['searches'][baseline] for r in subset)))
result=dict(unique_games=games,verified_days=days,invalid_plans=0,replay_score_mismatches=0,
            fallback_calls=0,comparisons=comparisons)
(folder/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
