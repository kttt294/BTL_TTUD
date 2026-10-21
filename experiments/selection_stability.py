"""Độ ổn định của bộ chọn vai trò: chạy nhiều lần trên cùng bài, đếm số đội hình khác nhau.

Ngân sách mỗi lần = agent_selection_time_limit − 4 giây như runner. Bộ chọn tự chạy song song.
python -X utf8 experiments/selection_stability.py --repeats 4
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.model import Board
from hexudon.team_selection import select_types

CASES = ["Q01", "Q03", "Q04", "Q06", "Q07", "Q08", "Q09", "Q10"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", default=CASES)
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--output", default=str(ROOT / "results/selection_stability.json"))
    args = parser.parse_args()
    results = {}
    for case in args.cases:
        config = json.loads((ROOT / "output/team_selection" / case / "config.json").read_text(encoding="utf-8"))
        board = Board.from_dict(config)
        seconds = (config.get("agent_selection_time_limit") or 30.0) - 4
        picks = [tuple(select_types(board, seconds, "tour")[0]) for _ in range(args.repeats)]
        results[case] = [list(p) for p in picks]
        counts = Counter(picks)
        print(f"{case} ({seconds:.0f} giây): {len(counts)} đội hình khác nhau / {args.repeats} lần:",
              ", ".join(f"{list(k)}×{v}" for k, v in counts.most_common()), flush=True)
        Path(args.output).write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
