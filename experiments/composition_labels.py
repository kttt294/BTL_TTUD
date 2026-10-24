"""Tạo dữ liệu học chọn đội hình: mỗi bản đồ sinh, mọi đội hình ứng viên × nhiều seed bằng C++ (nhánh test).

Mỗi dòng JSONL: bản đồ (profile, seed), đặc trưng bản đồ, và từng đội hình với đặc trưng đội hình cùng
điểm (U, D, Q) của mọi seed (cùng seed cho mọi đội hình). Ghi nối tiếp nên chạy lại được khi bị ngắt;
chia khoảng seed để chạy song song trên nhiều máy (local, Kaggle).

python -X utf8 experiments/composition_labels.py --profile mix --start 0 --count 100 --out results/labels/mix_0.jsonl
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
from hexudon.model import Board
from hexudon.selector import composition_features, map_features
from hexudon.team_selection import candidate_types


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="mix", choices=["btc", "wide", "mix"])
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--seeds", type=int, default=4, help="Số seed mỗi đội hình")
    parser.add_argument("--day-seconds", type=float, default=0.2, help="Thời gian lập tuyến mỗi ngày mỗi trận")
    parser.add_argument("--limit", type=int, default=24, help="Số đội hình ứng viên tối đa")
    parser.add_argument("--threads", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    parser.add_argument("--deadline", type=float, default=0.0, help="Dừng nhận bản đồ mới sau số giây này (0 = không)")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if not native.build():
        raise SystemExit("Không biên dịch được native/hexplan.cpp")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        done = {json.loads(line)["seed"] for line in out.read_text(encoding="utf-8").splitlines() if line.strip()}
    started = time.time()
    for seed in range(args.start, args.start + args.count):
        if seed in done:
            continue
        if args.deadline and time.time() - started > args.deadline:
            break
        board = Board.from_dict(generate_config(seed, args.profile))
        candidates = candidate_types(board, args.limit)
        t = time.time()
        records = native.evaluate_all(board, candidates, args.seeds, args.day_seconds, args.threads)
        runs = {}
        for r in records:
            runs.setdefault(tuple(r["types"]), []).append([r["seed"], *r["score"], int(r["complete"])])
        row = {"profile": args.profile, "seed": seed, "features": map_features(board),
               "candidates": [{"types": list(k), "features": composition_features(board, k), "runs": sorted(v)}
                              for k, v in runs.items()],
               "seconds": round(time.time() - t, 1)}
        with out.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        print(f"{args.profile} {seed}: {len(candidates)} đội hình, {len(records)} trận, {row['seconds']} giây", flush=True)


if __name__ == "__main__":
    main()
