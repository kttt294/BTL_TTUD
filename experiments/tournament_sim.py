"""Giải đấu giả lập: đội mình đấu với nhiều bot ngang sức trên một mặt đường chung.

Máy chủ chia tổng lượt trên ô đường hai ngày trước cho `players` (46 ở Mock), nên ở Mock chỉ một đội
chơi thì đường luôn thông. Ngày thi mọi đội cùng chơi: nếu các đội mạnh cùng chạy các trục chính
tới cùng các điểm udon, lượt trung bình xấp xỉ lượt của một đội và đường tắc gần như Practice.
Bộ mô phỏng chia cho số đội đang mô phỏng, nên ngưỡng được nhân players / số đội cho khớp máy chủ.
Mỗi đội có kho udon riêng; các đội chỉ ảnh hưởng nhau qua mặt đường.

python -X utf8 experiments/tournament_sim.py --bots 35
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.bounds import score_bounds
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.practice_best import ROAD_WEIGHTS
from hexudon.simulator import simulate_day, simulate_match_day

OURS = "61"


def plan_job(args):
    board, state, steps, seconds, seed, following = args
    if following is None:
        return plan_day(board, state, steps, "tour", seconds, seed=seed).actions
    # Chọn theo điểm sau ngày mai như simulate_rollout. Lượt của một đội chỉ khoảng 1/50 tổng lượt
    # nên mặt đường ngày mai được giả định giống hôm nay (do các đội khác quyết định).
    best = None
    for weights in ROAD_WEIGHTS:
        actions = plan_day(board, state, steps, "tour", seconds / 2, seed=seed, road_weights=weights).actions
        checked = simulate_day(board, state, actions, steps)
        if not checked.valid:
            continue
        value = checked.state.score()
        if following:
            tomorrow = checked.state
            tomorrow.traffic = dict(state.traffic)
            plan = plan_day(board, tomorrow, following, "tour", seconds / 3, seed=seed).actions
            after = simulate_day(board, tomorrow, plan, following)
            value = after.state.score() if after.valid else value
        if best is None or value > best[0]:
            best = value, actions
    return best[1]


def scaled(config, teams):
    players = config.get("players") or 1
    factor = players / teams
    return dict(config, busyThreshold=config["busyThreshold"] * factor,
                jammedThreshold=config["jammedThreshold"] * factor)


def layouts(board):
    """Mọi đội hình một xe tiếp tế, xếp theo cận (đội mình lấy cái đầu, bot xoay vòng)."""
    count = len(board.starts)
    options = [[int(i == s) for i in range(count)] for s in range(count)]
    cache = {}
    return sorted(options, key=lambda k: score_bounds(board, k, cache)["route"], reverse=True)


def play(config, bots, our_seconds, bot_seconds, pool, seed=0, rollout=False):
    teams = 1 + bots
    board = Board.from_dict(scaled(config, teams))
    options = layouts(board)
    kinds = {OURS: options[0]}
    for b in range(bots):
        kinds[f"bot{b}"] = options[b % len(options)]
    states = {team: State.initial(board, k) for team, k in kinds.items()}
    jams = []
    for day, steps in enumerate(board.day_steps):
        names = list(states)
        following = board.day_steps[day + 1] if day + 1 < len(board.day_steps) else 0
        jobs = [(board, states[t], steps, our_seconds if t == OURS else bot_seconds,
                 seed if t == OURS else seed + 1 + i, following if t == OURS and rollout else None)
                for i, t in enumerate(names)]
        orders = dict(zip(names, pool.map(plan_job, jobs)))
        result = simulate_match_day(board, states, orders, steps)
        if not result.valid:
            raise ValueError(result.errors[:3])
        states = result.states
        traffic = next(iter(states.values())).traffic
        jams.append((sum(v == 1 for v in traffic.values()), sum(v == 2 for v in traffic.values())))
    ranking = sorted(states, key=lambda t: states[t].score(), reverse=True)
    return {"kinds": kinds[OURS], "score": states[OURS].score(), "rank": ranking.index(OURS) + 1,
            "ranking": [(t, kinds[t], states[t].score()) for t in ranking],
            "teams": teams, "best_bot": max((states[t].score() for t in states if t != OURS), default=None),
            "median_bot": sorted(states[t].score() for t in states if t != OURS)[bots // 2] if bots else None,
            "jams": jams}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("maps", nargs="*", default=["M_Q01", "M_Q02", "M_Q03", "M_Q04", "M_Q05", "M_Q06",
                                                     "M_Q11", "M_Q18"])
    parser.add_argument("--map-dir", default=str(ROOT / "experiments/data/maps"),
                        help="Thư mục chứa config <tên>.json (M_Qxx: Mock, Qxx: Practice)")
    parser.add_argument("--bots", type=int, default=35)
    parser.add_argument("--our-seconds", type=float, default=6.0)
    parser.add_argument("--bot-seconds", type=float, default=2.0)
    parser.add_argument("--cores", type=int, default=7)
    parser.add_argument("--show", type=int, default=0, help="In bảng xếp hạng N đội đầu (và đội mình)")
    parser.add_argument("--rollout", action="store_true",
                        help="Đội mình thử 6 mức phạt đường mỗi ngày, chọn theo điểm sau ngày mai")
    parser.add_argument("--out", default=str(ROOT / "results/tournament"))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with ProcessPoolExecutor(args.cores) as pool:
        for name in args.maps:
            config = json.loads((Path(args.map_dir) / f"{name}.json").read_text(encoding="utf-8"))
            started = time.time()
            solo = play(config, 0, args.our_seconds, args.bot_seconds, pool, rollout=args.rollout)
            crowd = play(config, args.bots, args.our_seconds, args.bot_seconds, pool, rollout=args.rollout)
            board = Board.from_dict(config)
            bound = score_bounds(board, crowd["kinds"], tight=True)["route"]
            row = {"map": name, "bound": bound, "solo": solo, "crowd": crowd}
            rows.append(row)
            (out / "tong_ket.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
            s, c = solo["score"], crowd["score"]
            print(f"{name}: một mình {s} ({s[2] / bound[2]:.1%}) | {crowd['teams']} đội {c} ({c[2] / bound[2]:.1%}), "
                  f"hạng {crowd['rank']}/{crowd['teams']}, bot giỏi nhất {crowd['best_bot']}, bot giữa {crowd['median_bot']} | "
                  f"đông/tắc cuối trận {crowd['jams'][-1]} | {time.time() - started:.0f}s", flush=True)
            if args.show:
                for rank, (team, kinds, score) in enumerate(crowd["ranking"], 1):
                    if rank <= args.show or team == OURS:
                        print(f"  {rank:2d}. {'ĐỘI MÌNH' if team == OURS else team:9s} {kinds} {score} "
                              f"({score[2] / bound[2]:.1%})", flush=True)
                print("  đông/tắc theo ngày:", crowd["jams"], flush=True)


if __name__ == "__main__":
    main()
