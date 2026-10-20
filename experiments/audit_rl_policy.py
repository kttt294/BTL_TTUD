"""Kiểm tra checkpoint và dữ liệu tổng hợp, không huấn luyện hay chọn lại kết quả."""

import ast
import hashlib
import json
from pathlib import Path
import sys

import torch

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'experiments/rl_policy_results'
metadata=json.loads((folder/'training_metadata.json').read_text(encoding='utf8'))
rows=json.loads((folder/'evaluation_summary.json').read_text(encoding='utf8'))
audit=json.loads((folder/'evaluation_audit.json').read_text(encoding='utf8'))
assert len(rows)==21*6*3
assert audit['matches']==len(rows)
assert audit['fallback_calls']==audit['invalid_plans']==audit['replay_score_mismatches']==0
assert {r['seed'] for r in rows}==set(metadata['seeds'])
assert len({(r['case'],r['variant'],r['seed']) for r in rows})==len(rows)
tree=ast.parse((ROOT/'experiments/rl_policy.py').read_text(encoding='utf8'))
imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
assert not any(name and ('planner' in name or 'rl_extension' in name) for name in imports)
calls=[n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
assert 'plan_day' not in calls and 'complete_match' not in calls
for run in metadata['runs']:
    seed=run['seed']
    initial=torch.load(folder/f'initial_{seed}.pt',weights_only=True)['model']
    final=torch.load(folder/f'policy_{seed}.pt',weights_only=True)
    assert final['episodes']==metadata['episodes_per_seed']==1024
    assert hashlib.sha256((folder/f'policy_{seed}.pt').read_bytes()).hexdigest()==run['checkpoint_sha256']
    changed=sum(not torch.equal(initial[k],v) for k,v in final['model'].items())
    assert changed==run['changed_tensors']>0
    history=json.loads((folder/f'training_{seed}.json').read_text(encoding='utf8'))
    assert len(history)==1024
    assert all(0<=h['board_index']<48 for h in history)
audit['checkpoint_hashes_verified']=3
audit['changed_weight_tensors_verified']=[r['changed_tensors'] for r in metadata['runs']]
audit['policy_source_imports_planner']=False
audit['source_sha256']={name:hashlib.sha256((ROOT/'experiments'/name).read_bytes()).hexdigest()
                       for name in ('rl_policy.py','train_rl_policy.py','evaluate_rl_policy.py')}
(folder/'evaluation_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(audit,ensure_ascii=False,indent=2))
