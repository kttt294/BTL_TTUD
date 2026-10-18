"""Tính cận và kiểm tra mọi kế hoạch đối chứng đã lưu không vượt cận tương ứng."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.bounds import score_bounds
from hexudon.model import Board


def main():
    directory = ROOT / "experiments/team_selection_results"
    rows = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    results, checked_days = [], 0
    for row in rows:
        case = json.loads((directory / (row["case"] + ".json")).read_text(encoding="utf-8"))
        board = Board.from_dict(case["config"])
        methods = {}
        for method, trial in case["evaluations"].items():
            bound = score_bounds(board, trial["types"])
            types, portions = 0, 0
            for actual, upper in zip(trial["days"], bound["daily"]):
                types += upper["types"]
                portions += upper["portions"]
                assert all(a <= b for a, b in zip(actual["score"], (upper["types"], types, portions)))
                checked_days += 1
            methods[method] = bound
        results.append({"case": row["case"], "types": row["types"], "methods": methods})
        exported = ROOT / "output/team_selection" / row["case"]
        if exported.exists():
            (exported / "bounds.json").write_text(
                json.dumps(methods["selected"], ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"checked_days": checked_days, "cases": results}
    (directory / "reachability_bounds.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Verified days:", checked_days)
    for row in results:
        bound = row["methods"]["selected"]
        print(row["case"], bound["patrol_count"], "->", bound["reachability"], round(bound["seconds"], 4))


if __name__ == "__main__":
    main()
