"""Đo bộ chọn đội hình khi thi (team_selection.select_types, ngân sách thật) trên bản đồ giữ riêng của
train_selector.py và các config BTC; ghi JSONL (chạy lại được) để chấm bằng nhãn đã có (nhánh test).

python -X utf8 experiments/selector_check.py --configs jobs.json --seconds 26 --out results/labels/selector_check.jsonl
"""

import argparse
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))
from hexudon.generator import generate_config
from hexudon.model import Board
from hexudon.team_selection import select_types
from train_selector import load


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default="results/labels/**/*.jsonl")
    parser.add_argument("--configs", help="Danh sách job tầng 3 (name, config) để đo trên đề BTC")
    parser.add_argument("--maps", type=int, default=240, help="Số bản đồ giữ riêng (xen kẽ profile)")
    parser.add_argument("--seconds", type=float, default=26.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        done = {json.loads(line)["map"] for line in out.read_text(encoding="utf-8").splitlines() if line.strip()}
    boards = []
    if args.configs:
        for job in json.loads(Path(args.configs).read_text(encoding="utf-8")):
            boards.append((job["name"], job["config"]))
    maps = load(args.labels)
    random.Random(0).shuffle(maps)
    test = maps[int(len(maps) * 0.8):]
    by = {}
    for m in test:
        by.setdefault(m["profile"], []).append(m)
    order = [m for group in zip(*by.values()) for m in group] + [m for g in by.values() for m in g]
    seen = set()
    for m in order:
        name = f"{m['profile']}:{m['seed']}"
        if name not in seen and len(seen) < args.maps:
            seen.add(name)
            boards.append((name, generate_config(m["seed"], m["profile"])))
    for name, config in boards:
        if name in done:
            continue
        board = Board.from_dict(config)
        t = time.time()
        kinds, records, _ = select_types(board, args.seconds, "tour")
        row = {"map": name, "types": list(kinds), "seconds": round(time.time() - t, 1), "records": len(records)}
        with out.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        print(name, "".join(map(str, kinds)), row["seconds"], "giây", flush=True)


if __name__ == "__main__":
    main()
