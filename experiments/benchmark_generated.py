"""Bộ đo chuẩn trên bản đồ sinh giống phân bố đề (Giai đoạn 1 trong docs/roadmap.md).

Mỗi bản đồ: chọn vai trò như khi thi (select_types_parallel, ngân sách nhỏ để đo nhanh) rồi chơi
cả trận một đội bằng tour với ngân sách cố định. Báo tỷ lệ mất D, Q so với cận trên, số lần dự
phòng, ngày lâu nhất. Tập phát triển: seed 1000+; tập kiểm tra: seed 9000+ (chỉ dùng để chốt).

python -X utf8 experiments/benchmark_generated.py --profile wide --maps 24 --seconds 2
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.generator import generate_config
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day
from hexudon.team_selection import candidate_types, evaluate_types

SPLITS = {"dev": 1000, "test": 9000}


def play(job):
    seed, profile, seconds, select_seconds = job
    config = generate_config(seed, profile)
    board = Board.from_dict(config)
    started = time.perf_counter()
    # Chọn vai trò tuần tự (mỗi tiến trình một bản đồ): sàng lọc ứng viên với ngân sách nhỏ.
    candidates = candidate_types(board, 8)
    per_day = max(0.05, select_seconds / (len(candidates) * len(board.day_steps)))
    trials = [evaluate_types(board, kinds, per_day, "tour") for kinds in candidates]
    kinds = max(trials, key=lambda t: tuple(t["score"]))["types"]
    state = State.initial(board, kinds)
    brands = len({s["brand"] for s in board.spots})
    lost, fallbacks, longest, day_q, day_bound = [], 0, 0.0, [], []
    patrols = kinds.count(0)
    for day, steps in enumerate(board.day_steps):
        plan = plan_day(board, state, steps, "tour", seconds)
        checked = simulate_day(board, state, plan.actions, steps)
        if not checked.valid:
            raise ValueError(f"seed {seed}: {checked.errors[:2]}")
        before = state.daily_sum, state.portions
        state = checked.state
        if state.daily_sum - before[0] < brands:
            lost.append(day + 1)
        day_q.append(state.portions - before[1])
        day_bound.append(sum(min(s["stocks"], patrols) for s in board.spots))
        fallbacks += plan.fallback
        longest = max(longest, plan.elapsed)
    return {"seed": seed, "profile": profile, "size": [board.width, board.height],
            "agents": len(board.starts), "days": len(board.day_steps), "types": kinds,
            "score": list(state.score()), "max_u": brands, "max_d": brands * len(board.day_steps),
            "q_bound": sum(day_bound), "d_lost_days": lost, "fallbacks": fallbacks,
            "longest_day": round(longest, 2), "minutes": round((time.perf_counter() - started) / 60, 1)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["btc", "wide"], default="wide")
    parser.add_argument("--split", choices=list(SPLITS), default="dev")
    parser.add_argument("--maps", type=int, default=24)
    parser.add_argument("--seconds", type=float, default=2.0, help="Giây lập kế hoạch mỗi ngày")
    parser.add_argument("--select-seconds", type=float, default=6.0)
    parser.add_argument("--workers", type=int, default=14)
    parser.add_argument("--output")
    args = parser.parse_args()
    base = SPLITS[args.split]
    jobs = [(base + i, args.profile, args.seconds, args.select_seconds) for i in range(args.maps)]
    output = Path(args.output or ROOT / f"results/generated/{args.profile}_{args.split}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with ProcessPoolExecutor(args.workers) as pool:
        for result in pool.map(play, jobs):
            results.append(result)
            u, d, q = result["score"]
            print(f"seed {result['seed']} {result['size'][0]}x{result['size'][1]} {result['agents']} xe "
                  f"{result['days']} ngày | U {u}/{result['max_u']} D {d}/{result['max_d']} "
                  f"Q {q}/{result['q_bound']} | mất D {result['d_lost_days']} dự phòng {result['fallbacks']} "
                  f"lâu nhất {result['longest_day']}s", flush=True)
            output.write_text(json.dumps(results, indent=1), encoding="utf-8")
    full_u = sum(r["score"][0] == r["max_u"] for r in results)
    lost = sum(bool(r["d_lost_days"]) for r in results)
    ratio = statistics.mean(r["score"][2] / r["q_bound"] for r in results)
    print(f"\n{len(results)} bản đồ: U tối đa {full_u}/{len(results)}, trận mất D {lost}/{len(results)}, "
          f"Q/cận TB {ratio:.2f}, dự phòng {sum(r['fallbacks'] for r in results)}, "
          f"ngày lâu nhất {max(r['longest_day'] for r in results)}s")


if __name__ == "__main__":
    main()
