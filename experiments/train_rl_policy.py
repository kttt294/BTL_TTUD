"""Huấn luyện PPO từ đầu bằng điểm simulator TTUD, giữ riêng dữ liệu kiểm tra."""

import argparse
import hashlib
import json
import random
import time

import torch

from rl_policy import ROOT, TargetPolicy, RouteExecutor, play
from hexudon.generator import generate_board, to_dict


def update(model, optimizer, transitions, rng):
    advantages, returns = [], []
    for episode in transitions:
        gae, next_value = 0., 0.
        local = []
        for t in reversed(episode):
            delta = t['reward'] + .99 * next_value - t['value']
            gae = delta + .99 * .95 * gae
            local.append((gae, gae + t['value']))
            next_value = t['value']
        for advantage, target in reversed(local):
            advantages.append(advantage)
            returns.append(target)
    batch = [t for episode in transitions for t in episode]
    if not batch:
        raise ValueError('Không có quyết định để cập nhật PPO.')
    x = torch.stack([t['x'] for t in batch])
    masks = torch.stack([t['mask'] for t in batch])
    actions = torch.tensor([t['action'] for t in batch])
    old = torch.tensor([t['log_prob'] for t in batch])
    advantage = torch.tensor(advantages)
    advantage = (advantage-advantage.mean()) / (advantage.std(unbiased=False)+1e-8)
    target = torch.tensor(returns)
    losses = []
    for epoch in range(4):
        indices = list(range(len(batch)))
        rng.shuffle(indices)
        for begin in range(0, len(indices), 256):
            idx = indices[begin:begin+256]
            dist, values = model(x[idx], masks[idx])
            ratio = (dist.log_prob(actions[idx])-old[idx]).exp()
            actor = -torch.minimum(ratio*advantage[idx], ratio.clamp(.8,1.2)*advantage[idx]).mean()
            loss = actor + .001*(values-target[idx]).square().mean() - .01*dist.entropy().mean()
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), .5)
            optimizer.step()
            losses.append(float(loss.detach()))
    return len(batch), sum(losses)/len(losses)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--episodes', type=int, default=512)
    parser.add_argument('--seeds', nargs='+', type=int, default=[71, 72, 73])
    parser.add_argument('--output', default='experiments/rl_policy_results')
    args = parser.parse_args()
    torch.set_num_threads(1)
    folder = ROOT / args.output
    folder.mkdir(parents=True, exist_ok=True)
    # Ba kích thước và tập seed cố định; không dùng cấu hình BTC để học hoặc chọn checkpoint.
    boards = [generate_board(size, 61000+i, days=6, steps=80, fuel=100)
              for i in range(48) for size in [(8, 12, 16)[i % 3]]]
    executors = [RouteExecutor(b) for b in boards]
    corpus = json.dumps([to_dict(b) for b in boards], sort_keys=True).encode()
    manifest = dict(episodes_per_seed=args.episodes, seeds=args.seeds, training_maps=48,
        training_sizes=[8,12,16], training_seeds=list(range(61000,61048)),
        train_corpus_sha256=hashlib.sha256(corpus).hexdigest(), initialization='random, no old checkpoint',
        algorithm='PPO-clip', learning_rate=.0003, gamma=.99, gae_lambda=.95, clip=.2,
        epochs=4, minibatch=256, episodes_per_update=8, reward='10 delta U + delta D + 0.05 delta Q',
        device='cpu', torch_version=torch.__version__, fallback=False,
        checkpoint_selection='final episode count, no official test score selection', runs=[])
    for seed in args.seeds:
        torch.manual_seed(seed)
        rng = random.Random(seed)
        model = TargetPolicy()
        initial = {k:v.clone() for k,v in model.state_dict().items()}
        torch.save(dict(model=initial, seed=seed, episodes=0), folder/f'initial_{seed}.pt')
        optimizer = torch.optim.Adam(model.parameters(), lr=.0003)
        started, samples, updates, history, buffer = time.perf_counter(), 0, 0, [], []
        for episode in range(1, args.episodes+1):
            idx = rng.randrange(len(boards))
            row, trajectory = play(boards[idx], model, sample=True, executor=executors[idx], collect=True)
            buffer.append(trajectory)
            history.append(dict(episode=episode, board_index=idx, score=row['score'],
                                reward=sum(t['reward'] for t in trajectory)))
            if episode % 8 == 0 or episode == args.episodes:
                count, loss = update(model, optimizer, buffer, rng)
                samples += count
                updates += 1
                buffer.clear()
            if episode % 32 == 0 or episode == args.episodes:
                print(f'seed={seed} episode={episode} decisions={samples} seconds={time.perf_counter()-started:.1f} loss={loss:.4f}', flush=True)
        destination = folder/f'policy_{seed}.pt'
        torch.save(dict(model=model.state_dict(), seed=seed, episodes=args.episodes,
                        optimizer=optimizer.state_dict()), destination)
        changed = sum(not torch.equal(initial[k],v) for k,v in model.state_dict().items())
        assert changed > 0
        run = dict(seed=seed, episodes=args.episodes, updates=updates, decisions=samples,
                   seconds=time.perf_counter()-started, changed_tensors=changed,
                   checkpoint_sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
        manifest['runs'].append(run)
        (folder/f'training_{seed}.json').write_text(json.dumps(history, ensure_ascii=False, indent=2),encoding='utf8')
        (folder/'training_metadata.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')


if __name__ == '__main__':
    main()
