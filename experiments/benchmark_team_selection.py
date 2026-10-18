"""So sánh đội hình bằng simulator một đội, không coi điểm offline là điểm BTC."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.generator import generate_board, to_dict
from hexudon.model import Board
from hexudon.team_selection import candidate_types, evaluate_types, select_types


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-seconds", type=float, default=12)
    parser.add_argument("--day-seconds", type=float, default=0.15)
    args = parser.parse_args()
    output = ROOT / "experiments/team_selection_results"
    output.mkdir(parents=True, exist_ok=True)
    inputs = []
    for path in sorted((ROOT / "experiments/rl_branch_evidence").glob("Q*_config.json")):
        inputs.append((path.stem.replace("_config", ""), json.loads(path.read_text())["response"], args.selection_seconds))
    for size in (8, 16, 32):
        for seed in (2026, 2027):
            inputs.append((f"generated_{size}_{seed}", to_dict(generate_board(size, seed)), 4))
    summary = []
    for name, config, seconds in inputs:
        board = Board.from_dict(config)
        kinds, records, elapsed = select_types(board, seconds)
        complete = [r for r in records if r["complete"]]
        options = candidate_types(board)
        old = max((r for r in complete if r["types"] in options[:3]), key=lambda r: tuple(r["score"]))["types"]
        choices = {"all_patrol": [0] * len(board.starts),
                   "last_supply": [0] * (len(board.starts) - 1) + [1],
                   "old_three": old, "selected": kinds}
        # Đánh giá lại bằng cùng ngân sách ngày, tách khỏi ngân sách sàng lọc đội hình.
        cache, evaluations = {}, {}
        for method, types in choices.items():
            key = tuple(types)
            if key not in cache:
                cache[key] = evaluate_types(board, types, args.day_seconds)
            evaluations[method] = cache[key]
        row = {"case": name, "source": "BTC_config_offline" if name.startswith("Q") else "generated_offline",
               "types": kinds, "starts": board.starts, "selection_seconds": elapsed,
               "candidate_count": len(options), "completed": len(complete),
               "screen_completed": sum(r["phase"] == "screen" for r in complete),
               "refine_completed": sum(r["phase"] == "refine" for r in complete),
               "all_assignments": 2 ** len(board.starts) - 1,
               "predicted_score": [r["score"] for r in complete if r["types"] == kinds][-1],
               "scores": {method: trial["score"] for method, trial in evaluations.items()},
               "fallbacks": {method: sum(d["fallback"] for d in trial["days"]) for method, trial in evaluations.items()}}
        summary.append(row)
        (output / (name + ".json")).write_text(json.dumps({"config": config, "summary": row,
                "trials": records, "evaluations": evaluations}, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(name, kinds, row["scores"], f"{elapsed:.2f}s", flush=True)


if __name__ == "__main__":
    main()
