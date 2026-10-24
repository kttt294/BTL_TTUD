"""Đánh giá đội hình theo danh sách job (tầng 2, 3 của dữ liệu chọn đội hình; nhánh test).

Mỗi job: một bản đồ (sinh từ profile/seed hoặc config BTC), danh sách đội hình, seed và ngân sách:
- mode "single": mỗi trận một luồng C++, các trận chạy song song (native.evaluate_all), cho tầng 2;
- mode "session": mỗi ngày một phiên C++ nhiều luồng như runner khi thi (plan_day workers=threads),
  kế hoạch kiểm tra bằng simulator Python, cho tầng 3 (ngân sách thi: luồng × giây/ngày như máy thi).
Ghi nối tiếp JSONL, chạy lại được khi bị ngắt.

python -X utf8 experiments/composition_eval.py --jobs jobs.json --out results/labels/eval.jsonl
"""

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon import native
from hexudon.generator import generate_config
from hexudon.model import Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day


def board_of(job):
    if "config" in job:
        return Board.from_dict(job["config"])
    return Board.from_dict(generate_config(job["seed"], job["profile"]))


def session_match(board, kinds, seed, day_seconds, threads):
    state = State.initial(board, list(kinds))
    for steps in board.day_steps:
        plan = plan_day(board, state, steps, "tour", day_seconds, seed=seed * 100, workers=threads)
        checked = simulate_day(board, state, plan.actions, steps)
        if not checked.valid:
            return None
        state = checked.state
    return list(state.score())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--deadline", type=float, default=0.0, help="Không nhận job mới sau số giây này (0 = không)")
    args = parser.parse_args()
    if not native.build():
        raise SystemExit("Không biên dịch được native/hexplan.cpp")
    jobs = json.loads(Path(args.jobs).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        done = {json.loads(line)["key"] for line in out.read_text(encoding="utf-8").splitlines() if line.strip()}
    started = time.time()
    for job in jobs:
        if args.deadline and time.time() - started > args.deadline:
            break
        board = board_of(job)
        name = job.get("name") or f"{job['profile']}:{job['seed']}"
        if job["mode"] == "single":
            key = f"{name}|single|{job['day_seconds']}"
            if key in done:
                continue
            t = time.time()
            records = native.evaluate_all(board, job["candidates"], len(job["seeds"]), job["day_seconds"], args.threads)
            row = {"key": key, "map": name, "mode": "single", "day_seconds": job["day_seconds"], "records": records,
                   "seconds": round(time.time() - t, 1)}
            with out.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
            print(key, len(records), "trận", row["seconds"], "giây", flush=True)
            continue
        for kinds in job["candidates"]:
            for seed in job["seeds"]:
                key = f"{name}|{''.join(map(str, kinds))}|{seed}|{job['day_seconds']}"
                if key in done:
                    continue
                t = time.time()
                score = session_match(board, kinds, seed, job["day_seconds"], args.threads)
                row = {"key": key, "map": name, "mode": "session", "types": kinds, "seed": seed,
                       "day_seconds": job["day_seconds"], "threads": args.threads, "score": score,
                       "seconds": round(time.time() - t, 1), "native_fallbacks": dict(native.FALLBACKS)}
                with out.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row) + "\n")
                print(key, score, row["seconds"], "giây", flush=True)


if __name__ == "__main__":
    main()
