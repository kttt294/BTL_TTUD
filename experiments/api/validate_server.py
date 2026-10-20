"""Chạy đối chiếu trên bản luyện tập riêng của đội, không gọi API thi chính thức."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from hexudon.api import CompetitionAPI
from hexudon.model import Agent, Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day
from compare_api import compare


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default="Q03")
    parser.add_argument("--team", default="62")
    parser.add_argument("--seconds", type=float, default=0.5)
    args = parser.parse_args()
    registry = json.loads((ROOT / "docs/api/sample_games.json").read_text(encoding="utf-8"))
    question = args.question.lower()
    game = registry[args.question] + ":" + args.team
    api = CompetitionAPI()
    config = api.get("/api/game/config", game, question + "_config")
    board = Board.from_dict(config)
    history = api.get("/api/game/actions", game, question + "_history_before")
    if history["actions"]:
        print("Trận đã có lịch sử; chỉ đọc và đối chiếu, không ghi đè.")
    else:
        kinds = [0] * (len(board.starts) - 1) + [1]
        api.request("POST", "/api/game/agent-types", body={"game_id": game, "types": kinds},
                    label=question + "_select")
        state = State.initial(board, kinds)
        for day, steps in enumerate(board.day_steps):
            raw = api.get("/api/game/day", game, f"{question}_day_{day:02d}")
            if raw["day"] != day:
                raise ValueError("Ngày máy chủ không khớp, dừng trước khi nộp.")
            state.agents = [Agent(a["kind"], a["pos"], a["fuel"]) for a in raw["agents"]]
            state.traffic = {t["pos"]: t["status"] for t in raw["traffics"]}
            plan = plan_day(board, state, steps, "greedy", args.seconds)
            local = simulate_day(board, state, plan.actions, steps)
            if not local.valid:
                raise ValueError("Kế hoạch không hợp lệ trong simulator.")
            api.practice_actions(game, day, plan.actions, f"{question}_submit_{day:02d}")
            state = local.state
            print(f"{args.question}, ngày API {day}: máy chủ đã nhận kế hoạch.", flush=True)
    replay = api.get("/api/game/replay", game, question + "_replay")
    history = api.get("/api/game/actions", game, question + "_actions")
    api.get("/api/game/state", game, question + "_state")
    result = compare(config, replay, history, args.team)
    result["question"] = args.question
    result["game_id"] = game
    api.directory.joinpath(question + "_comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("examples", "days")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
