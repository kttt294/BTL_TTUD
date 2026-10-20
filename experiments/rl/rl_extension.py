"""Thử RL đề xuất nhiều mục tiêu và chọn bằng mô phỏng tới cuối trận, hoàn toàn offline."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day

SNAPSHOT = ROOT / 'scratch/Procon2026_rl_eval'
VARIANTS = ('greedy', 'rollout_no_rl', 'rl_daily', 'rl_rollout')


def complete_match(board, state, first=None, seconds=.03, deadline=None):
    """Nối một kế hoạch ngày với Greedy cho các ngày còn lại; không dùng điểm trận dở."""
    current = deepcopy(state)
    plans = []
    while current.day < len(board.day_steps):
        if deadline is not None and time.perf_counter() >= deadline:
            return None
        steps = board.day_steps[current.day]
        actions = first if not plans and first is not None else plan_day(
            board, current, steps, 'greedy', seconds).actions
        result = simulate_day(board, current, actions, steps)
        if not result.valid:
            return None
        plans.append(actions)
        current = result.state
    return {'score': current.score(), 'plans': plans}


class FrozenPolicy:
    def __init__(self, samples=3):
        os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
        sys.path.insert(0, str(SNAPSHOT / 'src'))
        import torch
        from rl.mappo import MAPPOTrainer
        torch.set_num_threads(1)
        self.torch = torch
        self.trainer = MAPPOTrainer(device='cpu', log_dir=None)
        checkpoint = SNAPSHOT / 'runs/pilot_reserved_001/seed_20042/episode_256.pt'
        self.trainer.load(str(checkpoint))
        self.trainer.model.eval()
        self.samples = samples
        self.metadata = {'branch_commit': 'b6df084c253503b5673721c126ff261430cd0021',
                         'checkpoint': str(checkpoint.relative_to(ROOT)),
                         'checkpoint_sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                         'episodes_completed': self.trainer.episodes_completed,
                         'torch_version': torch.__version__, 'device': 'cpu',
                         'new_training': False, 'sampled_joint_targets': samples,
                         'argmax_joint_targets': 1}

    def configure(self, board):
        from env.models import MatchConfig, MapData, Cell, Spot
        from env.simulator import HexaUdonSimulator
        self.cfg = MatchConfig(board.width, board.height, len(board.day_steps), board.day_steps,
                               1, board.busy_threshold, board.jammed_threshold, board.fuel_limit)
        terrain = {0: 0, 1: 3, 2: 1, 3: 2}
        self.map = MapData([Cell(r * board.width + c, terrain[t])
                            for r, row in enumerate(board.cells) for c, t in enumerate(row)],
                           [Spot(s['pos'], s['brand'], s['stocks']) for s in board.spots])
        self.simulator = HexaUdonSimulator(self.cfg, self.map)
        self.trainer.model.set_fuel_max(board.fuel_limit)

    def candidates(self, board, state, seed):
        from env.models import AgentState, DayState
        source = DayState(state.day + 1, board.day_steps[state.day], 30000, dict(state.traffic),
                          {s['pos']: s['stocks'] for s in board.spots},
                          [AgentState(i, a.kind, a.pos, a.fuel) for i, a in enumerate(state.agents)],
                          [], set(state.brands), [], state.portions, fuel_max=board.fuel_limit)
        # Actor của checkpoint không đọc daily_series; vị trí, nhiên liệu và loại đã thu đều là thật.
        patrols = [a.id for a in source.patrol_agents()]
        self.torch.manual_seed(seed + state.day)
        seen = set()
        with self.torch.no_grad():
            for sample in range(self.samples + 1):
                targets, _, _, _ = self.trainer.model.get_action_and_value(
                    source, self.map, self.cfg, patrols, deterministic=sample == 0)
                key = tuple(targets)
                if key in seen:
                    continue
                seen.add(key)
                orders = self.trainer._actions_to_orders(
                    source, self.map, self.cfg, self.simulator, patrols, targets,
                    secondary_routes=self.trainer.model.secondary_routes,
                    reserve_spots=self.trainer.model.reserve_spots)
                actions = []
                for order in sorted(orders, key=lambda o: o.agent_id):
                    commands = []
                    for action in order.actions:
                        if action.cmd == 'move':
                            commands.append(action.direction)
                        elif commands and commands[-1] < 0:
                            commands[-1] -= 1
                        else:
                            commands.append(-1)
                    actions.append(commands)
                yield ('rl_argmax' if sample == 0 else f'rl_sample_{sample}'), actions, list(targets)


def run_variant(board, variant, initial, policy, seed, daily_seconds=.12, future_seconds=.03):
    state = State.initial(board, [0] * len(board.starts))
    incumbent = deepcopy(initial)
    plans, logs = [], []
    for day, steps in enumerate(board.day_steps):
        started = time.perf_counter()
        deadline = started + 20
        if variant == 'greedy':
            candidates = []
        else:
            candidates = [(name, plan_day(board, state, steps, name, daily_seconds).actions, None)
                          for name in ('greedy', 'lookahead')]
            if variant.startswith('rl_'):
                candidates += list(policy.candidates(board, state, seed))
        generated = len(candidates)
        seen, unique = set(), []
        for candidate in candidates:
            key = tuple(tuple(commands) for commands in candidate[1])
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        candidates = unique
        best = incumbent
        origin = 'retained_plan'
        candidate_logs = []
        if variant == 'rl_daily':
            best = None
        for name, actions, targets in candidates:
            if time.perf_counter() >= deadline:
                break
            checked = simulate_day(board, state, actions, steps)
            if not checked.valid:
                candidate_logs.append({'source': name, 'valid': False, 'errors': checked.errors})
                continue
            if variant == 'rl_daily':
                predicted = {'score': checked.state.score(), 'plans': [actions]}
            else:
                predicted = complete_match(board, state, actions, future_seconds, deadline)
            if predicted is None:
                candidate_logs.append({'source': name, 'valid': True, 'completed': False})
                continue
            candidate_logs.append({'source': name, 'valid': True, 'completed': True,
                                   'predicted_score': predicted['score'], 'targets': targets})
            if best is None or tuple(predicted['score']) > tuple(best['score']):
                best, origin = predicted, name
        if best is None:
            raise ValueError('Không có kế hoạch khả thi để thực thi.')
        actions = best['plans'][0]
        decision_seconds = time.perf_counter() - started
        result = simulate_day(board, state, actions, steps)
        assert result.valid, result.errors
        if variant != 'rl_daily':
            assert tuple(best['score']) >= tuple(incumbent['score'])
            incumbent = {'score': best['score'], 'plans': best['plans'][1:]}
        state = result.state
        plans.append(actions)
        logs.append({'day': day + 1, 'source': origin, 'decision_seconds': decision_seconds,
                     'score_after_day': state.score(), 'predicted_score': best['score'],
                     'generated_candidates': generated, 'unique_candidates': len(candidates),
                     'candidates': candidate_logs})
    if variant != 'rl_daily':
        assert state.score() == tuple(incumbent['score']) >= tuple(initial['score'])
    return {'variant': variant, 'score': state.score(), 'initial_greedy_score': initial['score'],
            'max_decision_seconds': max(r['decision_seconds'] for r in logs),
            'selected_rl_days': sum(r['source'].startswith('rl_') for r in logs),
            'valid_days': len(logs), 'days': logs, 'actions': plans}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--questions', nargs='+', default=['Q01', 'Q02', 'Q03', 'Q04', 'Q06', 'Q07', 'Q08', 'Q09', 'Q10'])
    parser.add_argument('--variants', nargs='+', choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument('--config-dir', default='experiments/data/rl_branch_evidence')
    parser.add_argument('--output', default='experiments/data/rl_extension_results')
    parser.add_argument('--samples', type=int, default=3)
    args = parser.parse_args()
    folder = ROOT / args.output
    folder.mkdir(parents=True, exist_ok=True)
    policy = FrozenPolicy(args.samples)
    metadata = {**policy.metadata, 'daily_planner_seconds': .12, 'continuation_planner_seconds': .03,
                'decision_deadline_seconds': 20, 'agent_types': 'all_patrol',
                'simulator': 'ttud_clean, one team', 'rollout_horizon': 'all_remaining_days',
                'variants': args.variants, 'questions': args.questions,
                'baseline_cache_shared_between_variants': True}
    (folder / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    results = []
    for question in args.questions:
        config_path = ROOT / args.config_dir / f'{question}_config.json'
        raw = json.loads(config_path.read_text(encoding='utf-8'))
        config = raw.get('response', raw)
        board = Board.from_dict(config)
        policy.configure(board)
        initial = complete_match(board, State.initial(board, [0] * len(board.starts)), seconds=.12)
        assert initial is not None
        seed = 4200 + int(question[1:])
        for variant in args.variants:
            started = time.perf_counter()
            row = run_variant(board, variant, initial, policy, seed)
            row.update(question=question, evaluation_seconds=time.perf_counter() - started,
                       seed=seed, config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest())
            (folder / f'{question}_{variant}.json').write_text(
                json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
            summary = {k: v for k, v in row.items() if k not in ('days', 'actions')}
            results.append(summary)
            (folder / 'summary.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
            print(question, variant, row['score'], f"RL days={row['selected_rl_days']}; {row['evaluation_seconds']:.2f}s", flush=True)


if __name__ == '__main__':
    main()
