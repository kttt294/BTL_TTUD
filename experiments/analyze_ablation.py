"""Truy nguyên trường hợp thắng/thua từ các kế hoạch đã lưu, không chọn lại kế hoạch."""

import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from hexudon.model import Board, State
from hexudon.simulator import simulate_day

folder=ROOT/'experiments/ablation_results'
cases=['generated_8_42000','generated_16_42000','generated_32_42000','scarce_fuel']
results={}
for name in cases:
    board=Board.from_dict(json.loads((folder/f'{name}_input.json').read_text(encoding='utf8')))
    detail=json.loads((folder/f'{name}_detail.json').read_text(encoding='utf8'))
    results[name]={}
    for method,trial in detail['evaluations'].items():
        state=State.initial(board,trial['types'])
        records=[]
        for steps,actions in zip(board.day_steps,trial['actions']):
            before=state.score()
            checked=simulate_day(board,state,actions,steps,record=True)
            assert checked.valid,checked.errors
            stock={s['pos']:s['stocks'] for s in board.spots}
            visited=[set() for a in state.agents]
            empty,refill=0,0
            previous=checked.trace[0]
            for frame in checked.trace[1:]:
                observed=[]
                for car,agent in enumerate(state.agents):
                    pos=frame['positions'][car]
                    if agent.kind==0:
                        refill+=int(frame['fuel'][car]>previous['fuel'][car])
                        if pos in stock and pos not in visited[car]:
                            visited[car].add(pos)
                            if stock[pos]>0:
                                stock[pos]-=1
                                observed.append(pos)
                            else:
                                empty+=1
                assert observed==frame['collected']
                previous=frame
            state=checked.state
            records.append(dict(day=state.day,score=state.score(),daily_types=state.score()[1]-before[1],
                collected=state.portions-before[2],empty_stock_visits=empty,fuel_increase_events=refill,
                final_positions=[a.pos for a in state.agents],final_fuel=[a.fuel for a in state.agents]))
        results[name][method]=records
(folder/'mechanisms.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
for name,methods in results.items():
    print(name)
    for method,records in methods.items():
        print(method,'score',records[-1]['score'],'empty',sum(r['empty_stock_visits'] for r in records),
              'refill',sum(r['fuel_increase_events'] for r in records),
              'daily_types',[r['daily_types'] for r in records], 'fuel',[r['final_fuel'] for r in records])
