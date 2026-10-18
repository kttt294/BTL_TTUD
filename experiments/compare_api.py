"""Đối chiếu từng frame của simulator với replay được lưu từ API BTC."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hexudon.model import Board, State
from hexudon.simulator import simulate_day


def read_response(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))["response"]


def compare(config, replay, history, team_id="62"):
    board = Board.from_dict(config)
    plans = {row["day"]: row["plan"] for row in history["actions"] if row["team_id"] == team_id}
    first = next(team for team in replay["days"][0]["teams"] if team["team_id"] == team_id)
    state = State.initial(board, first["kinds"])
    for car, snapshot in zip(state.agents, first["frames"][0]["agents"]):
        car.pos, car.fuel = snapshot["cell"], snapshot["fuel"]
    differences, counts, days = [], Counter(), []
    checked_frames = checked_values = 0

    def check(day, tick, field, actual, expected):
        nonlocal checked_values
        checked_values += 1
        if actual != expected:
            counts[field] += 1
            if len(differences) < 30:
                differences.append({"day": day, "step": tick, "field": field,
                                    "simulator": actual, "server": expected})

    for index, day in enumerate(replay["days"]):
        team = next(t for t in day["teams"] if t["team_id"] == team_id)
        if day["day"] not in plans:
            counts["missing_plan"] += 1
            differences.append({"day": day["day"], "field": "missing_plan"})
            continue
        # Dùng giao thông thật cho chặng hiện tại, rồi kiểm tra dự đoán giao thông chặng sau.
        state.traffic = {int(p): v for p, v in day["road_condition"].items()}
        old_portions, old_daily = state.portions, state.daily_sum
        result = simulate_day(board, state, plans[day["day"]], day["steps"], record=True)
        if not result.valid:
            counts["validity"] += 1
            days.append({"day": day["day"], "valid": False, "errors": result.errors})
            break
        frames = team["frames"]
        check(day["day"], -1, "frame_count", len(result.trace), len(frames))
        for local, remote in zip(result.trace, frames):
            checked_frames += 1
            check(day["day"], remote["step"], "step", local["step"], remote["step"])
            for car, other in enumerate(remote["agents"]):
                check(day["day"], remote["step"], f"position_{car}", local["positions"][car], other["cell"])
                check(day["day"], remote["step"], f"fuel_{car}", local["fuel"][car], other["fuel"])
            for field in ("servings", "types", "collected"):
                if field in local:
                    check(day["day"], remote["step"], field, local[field], remote[field])
        check(day["day"], day["steps"], "day_servings", result.state.portions - old_portions, team["servings"])
        check(day["day"], day["steps"], "day_types", result.state.daily_sum - old_daily, team["types"])
        if index + 1 < len(replay["days"]):
            next_traffic = replay["days"][index + 1]["road_condition"]
            for pos, status in next_traffic.items():
                check(day["day"], day["steps"], f"next_traffic_{pos}", result.state.traffic.get(int(pos), 0), status)
        days.append({"day": day["day"], "valid": True,
                     "frames": len(frames), "servings": team["servings"], "types": team["types"]})
        state = result.state
    return {"days": days, "checked_frames": checked_frames, "checked_values": checked_values,
            "mismatch_count": sum(counts.values()), "mismatch_fields": dict(counts),
            "examples": differences, "final_score": list(state.score())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--replay", required=True)
    parser.add_argument("--actions", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--team", default="62")
    args = parser.parse_args()
    result = compare(read_response(args.config), read_response(args.replay), read_response(args.actions), args.team)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("examples", "days")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
