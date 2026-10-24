"""Chạy lại toàn bộ đề Practice của BTC bằng đúng đường chạy thi trên máy chủ giả offline (nhánh test).

Mỗi đề: chọn vai trò trong agent_selection_time_limit, mỗi ngày daySeconds thật, nộp nhanh rồi nộp
lại khi tốt hơn (experiments/rehearse_timed.py). Không gọi API BTC.

python -X utf8 experiments/practice_offline.py --out results/practice_offline
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CASES = ["Q01", "Q02", "Q03", "Q04", "Q06", "Q07", "Q08", "Q09", "Q10"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", default=CASES)
    parser.add_argument("--out", default="results/practice_offline")
    parser.add_argument("--latency", type=float, default=0.1)
    args = parser.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    for case in args.cases:
        target = out / f"{case}.json"
        if target.exists():
            continue
        subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "experiments/rehearse_timed.py"), "--case", case,
                        "--latency", str(args.latency), "--json", str(target)], check=True)
        result = json.loads(target.read_text(encoding="utf-8"))
        print(f"{case}: {tuple(result['score'])} | vai trò {result['kinds']} | phản hồi {result['response']} giây | "
              f"thiếu bài {result['missed']}", flush=True)


if __name__ == "__main__":
    main()
