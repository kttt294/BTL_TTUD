"""Đối chứng chính sách đã học với mạng ban đầu, ngẫu nhiên và gần nhất cùng bộ thực thi."""

import argparse
import hashlib
import json
import time

import torch

from rl_policy import ROOT, TargetPolicy, RouteExecutor, play
from hexudon.generator import generate_board, to_dict
from hexudon.model import Board, State
from hexudon.simulator import simulate_day


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', default='experiments/data/rl_policy_results')
    parser.add_argument('--questions', nargs='*', default=['Q01','Q02','Q03','Q04','Q06','Q07','Q08','Q09','Q10'])
    parser.add_argument('--generated-per-size', type=int, default=4)
    args = parser.parse_args()
    torch.set_num_threads(1)
    folder = ROOT / args.folder
    meta = json.loads((folder/'training_metadata.json').read_text(encoding='utf8'))
    models = {}
    for seed in meta['seeds']:
        for variant, filename in [('trained',f'policy_{seed}.pt'),('untrained',f'initial_{seed}.pt')]:
            model = TargetPolicy()
            saved = torch.load(folder/filename, weights_only=True)
            model.load_state_dict(saved['model'])
            model.eval()
            models[variant,seed] = model
    cases = []
    for q in args.questions:
        raw = json.loads((ROOT/'experiments/data/rl_branch_evidence'/f'{q}_config.json').read_text(encoding='utf8'))
        cfg = raw.get('response',raw)
        cases.append((q, 'official', Board.from_dict(cfg)))
    for size in (8,16,32):
        for i in range(args.generated_per_size):
            seed = 91000+i
            cases.append((f'G{size}_{seed}','generated_heldout',generate_board(size,seed,days=6,steps=80,fuel=100)))
    rows = []
    for name, group, board in cases:
        for variant in ('trained','untrained','trained_sampled','untrained_sampled','random','nearest'):
            for seed in meta['seeds']:
                executor = RouteExecutor(board)
                torch.manual_seed(seed)
                started = time.perf_counter()
                sampled = variant.endswith('_sampled')
                model_key = variant.replace('_sampled','')
                mode = 'policy' if model_key in ('trained','untrained') else variant
                row, _ = play(board, models.get((model_key,seed)), mode=mode,
                              sample=sampled, executor=executor)
                row.update(case=name,group=group,variant=variant,seed=seed,
                           total_seconds=time.perf_counter()-started,
                           config_sha256=hashlib.sha256(json.dumps(to_dict(board),sort_keys=True).encode()).hexdigest())
                state = State.initial(board,[0]*len(board.starts))
                for steps, actions in zip(board.day_steps,row['actions']):
                    result = simulate_day(board,state,actions,steps)
                    assert result.valid, result.errors
                    state = result.state
                assert tuple(row['score']) == state.score()
                (folder/f'{name}_{variant}_{seed}.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8')
                rows.append({k:v for k,v in row.items() if k!='actions'})
                (folder/'evaluation_summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
            print(name,variant,[r['score'] for r in rows[-len(meta['seeds']):]],flush=True)
    audit = dict(matches=len(rows), replay_verified_days=sum(len(r['decisions']) for r in rows),
                 invalid_plans=0, replay_score_mismatches=0,fallback_calls=sum(r['fallback_calls'] for r in rows),
                 official_used_for_training=False, official_used_for_checkpoint_selection=False,
                 notes='Mỗi ngày chạy đúng một chuỗi quyết định; không chọn tốt nhất trong nhiều mẫu. Đánh giá thêm lấy mẫu sau khi chẩn đoán argmax chọn chờ trên Q04 và một bản đồ sinh; không đổi trọng số hoặc chọn checkpoint theo các điểm này.')
    (folder/'evaluation_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')


if __name__ == '__main__':
    main()
