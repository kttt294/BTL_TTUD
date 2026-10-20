"""Nộp kế hoạch đội hình đã chọn lên Practice riêng và đối chiếu điểm thực."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from hexudon.api import CompetitionAPI
from hexudon.model import Board, State
from hexudon.simulator import simulate_day
from compare_api import compare


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("questions", nargs="+", default=["Q03", "Q04"])
    args = parser.parse_args()
    api = CompetitionAPI(evidence_dir="experiments/data/team_selection_api_evidence")
    registry = json.loads((ROOT / "docs/api/sample_games.json").read_text(encoding="utf-8"))
    results = []
    for question in args.questions:
        case = json.loads((ROOT / f"experiments/data/team_selection_results/{question}.json").read_text(encoding="utf-8"))
        game = registry[question] + ":62"
        config = api.get("/api/game/config", game, question + "_config")
        for endpoint in ("actions", "replay", "state"):
            api.get("/api/game/" + endpoint, game, question + "_before_" + endpoint)
        kinds = case["summary"]["types"]
        board = Board.from_dict(config)
        state = State.initial(board, kinds)
        api.request("POST", "/api/game/practice/reset", body={"game_id": game}, label=question + "_reset")
        api.request("POST", "/api/game/agent-types", body={"game_id": game, "types": kinds}, label=question + "_types")
        for day, plan in enumerate(case["evaluations"]["selected"]["days"]):
            raw = api.get("/api/game/day", game, f"{question}_day_{day:02d}")
            assert raw["day"] == day
            assert [(a.kind, a.pos, a.fuel) for a in state.agents] == [
                (a["kind"], a["pos"], a["fuel"]) for a in raw["agents"]]
            assert all(state.traffic.get(t["pos"], 0) == t["status"] for t in raw["traffics"])
            checked = simulate_day(board, state, plan["actions"], board.day_steps[day])
            assert checked.valid
            api.practice_actions(game, day, plan["actions"], f"{question}_submit_{day:02d}")
            state = checked.state
            print(question, "day", day + 1, "accepted", flush=True)
        replay = api.get("/api/game/replay", game, question + "_replay")
        history = api.get("/api/game/actions", game, question + "_actions")
        actual = api.get("/api/game/result", game, question + "_result")["detail"]["62"]
        score = [actual["distinct_types"], actual["cumulative_daily_types"], actual["total_servings"]]
        assert score == list(state.score()) == case["summary"]["scores"]["selected"]
        comparison = compare(config, replay, history)
        result = {"question": question, "types": kinds, "server_score": score, "comparison": comparison}
        results.append(result)
        (api.directory / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(question, "server_score", score, flush=True)


if __name__ == "__main__":
    main()
