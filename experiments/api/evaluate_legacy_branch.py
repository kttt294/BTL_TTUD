"""Đánh giá bản chụp nhánh Procon2026 bằng máy chấm luyện tập của BTC."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from hexudon.api import CompetitionAPI
RL_MODE = "--rl" in sys.argv
SNAPSHOT = ROOT / ("scratch/Procon2026_rl_eval" if RL_MODE else "scratch/Procon2026_eval")
sys.path.insert(0, str(SNAPSHOT / "src"))
from env.models import MatchConfig, MapData, Cell, Spot, AgentState, DayState
from env.simulator import HexaUdonSimulator, complete_orders
from env.validator import validate_orders
from env.scoring import compute_score
from strategy.greedy import GreedyPlanner
from strategy.lookahead import LookaheadPlanner


def encode(orders):
    result = []
    for order in sorted(orders, key=lambda o: o.agent_id):
        actions = []
        for action in order.actions:
            if action.cmd == "move":
                actions.append(action.direction)
            elif actions and actions[-1] < 0:
                actions[-1] -= 1
            else:
                actions.append(-1)
        result.append(actions)
    return result


def run(question, uuid, api, trainer=None):
    game = uuid + ":62"
    # Lưu lịch sử trước khi đặt lại trận luyện tập riêng của đội.
    config = api.get("/api/game/config", game, question + "_config")
    for endpoint in ("actions", "replay", "state"):
        api.get("/api/game/" + endpoint, game, question + "_before_" + endpoint)
    board = config["map"]
    cfg = MatchConfig(board["width"], board["height"], len(config["daySteps"]),
                      config["daySteps"], config["players"], config["busyThreshold"],
                      config["jammedThreshold"], config["fuelLimits"])
    terrain = {0: 0, 1: 3, 2: 1, 3: 2}
    mp = MapData([Cell(r * cfg.width + c, terrain[t])
                  for r, row in enumerate(board["cells"]) for c, t in enumerate(row)],
                 [Spot(s["pos"], s["brand"], s["stocks"]) for s in config["spots"]])
    sim = HexaUdonSimulator(cfg, mp)
    greedy = GreedyPlanner(cfg, mp, sim)
    lookahead = LookaheadPlanner(cfg, mp, sim)
    if trainer is not None:
        trainer.model.set_fuel_max(cfg.fuel_max)
    api.request("POST", "/api/game/practice/reset", body={"game_id": game}, label=question + "_reset")
    kinds = [0] * len(config["agents"])
    api.request("POST", "/api/game/agent-types", body={"game_id": game, "types": kinds},
                label=question + "_types")
    collected, daily, total, logs, outputs = set(), [], 0, [], []
    for day, steps in enumerate(cfg.steps_per_day):
        raw = api.get("/api/game/day", game, f"{question}_day_{day:02d}")
        if raw["day"] != day:
            raise ValueError("Ngày máy chủ không khớp.")
        state = DayState(day + 1, steps, 30000,
                         {t["pos"]: t["status"] for t in raw["traffics"]},
                         {s.cell_id: s.max_inventory for s in mp.spots},
                         [AgentState(i, a["kind"], a["pos"], a["fuel"])
                          for i, a in enumerate(raw["agents"])],
                         [], set(collected), deepcopy(daily), total, fuel_max=cfg.fuel_max)
        started = time.monotonic()
        idle = complete_orders([], state, mp, sim.grid)
        orders = greedy.plan(state)
        mode = "greedy"
        if not validate_orders(orders, state, mp, sim.grid)[0]:
            orders, mode = idle, "idle_local_validation"
        candidate_mode = "lookahead"
        policy_log = {}
        if trainer is not None:
            import torch
            patrol_ids = [a.id for a in state.patrol_agents()]
            with torch.no_grad():
                targets, _, _, _ = trainer.model.get_action_and_value(
                    state, mp, cfg, patrol_ids, deterministic=True)
            candidate = trainer._actions_to_orders(
                state, mp, cfg, sim, patrol_ids, targets,
                secondary_routes=trainer.model.secondary_routes,
                reserve_spots=trainer.model.reserve_spots)
            candidate_mode = "rl"
            policy_log = {"rl_targets": list(targets), "rl_candidate": encode(candidate),
                          "rl_candidate_valid": validate_orders(candidate, state, mp, sim.grid)[0]}
        else:
            candidate = lookahead.plan(state)
        if candidate != orders and validate_orders(candidate, state, mp, sim.grid)[0]:
            baseline, _ = deepcopy(sim).apply_day(state, orders)
            future, _ = deepcopy(sim).apply_day(state, candidate)
            if compute_score(future) > compute_score(baseline):
                orders, mode = candidate, candidate_mode
        planning_seconds = time.monotonic() - started
        actions = encode(orders)
        # Máy chủ quyết định tính hợp lệ; không sửa đường đi khi bị từ chối.
        try:
            api.practice_actions(game, day, actions, f"{question}_submit_{day:02d}")
        except ValueError:
            logs.append({"day": day, "mode": mode, "rejected": True})
            raise
        outputs.append(actions)
        replay = api.get("/api/game/replay", game, f"{question}_replay_{day:02d}")
        current = next(d for d in replay["days"] if d["day"] == day)
        team = next(t for t in current["teams"] if str(t["team_id"]) == "62")
        visits = {p for frame in team["frames"] for p in frame["collected"]}
        series = {mp.spot_map[p].series_id for p in visits}
        daily.append(series)
        collected.update(series)
        total += team["servings"]
        logs.append({"day": day, "mode": mode, "planning_seconds": planning_seconds,
                     "servings": team["servings"], "types": team["types"], "accepted": True,
                     **policy_log})
        print(f"{question} day {day + 1}: {mode}, {planning_seconds:.3f}s, server accepted", flush=True)
    final = api.get("/api/game/state", game, question + "_final_state")
    server_result = api.get("/api/game/result", game, question + "_result")
    team = final["teams"]["62"]
    detail = server_result["detail"]["62"]
    score = [detail["distinct_types"], detail["cumulative_daily_types"], detail["total_servings"]]
    assert score == [len(team["distinct_types"]), sum(d["types"] for d in logs), team["total_servings"]]
    result = {"question": question, "game_id": game,
              "mode": "rl_greedy_score_gate" if trainer is not None else "no_checkpoint_greedy_lookahead",
              "branch_commit": "b6df084c253503b5673721c126ff261430cd0021" if RL_MODE else "67e7873781d90e0809bc295a4422316e5abe5dc3",
              "score": score,
              "days": logs, "agent_types": kinds}
    (api.directory / (question + "_output.txt")).write_text(
        "\n".join(json.dumps(day) for day in outputs) + "\n", encoding="utf-8")
    return result


def main():
    trainer = None
    evidence = "experiments/data/rl_branch_evidence" if RL_MODE else "experiments/data/legacy_branch_evidence"
    api = CompetitionAPI(evidence_dir=evidence)
    if RL_MODE:
        import hashlib
        import torch
        from rl.mappo import MAPPOTrainer
        torch.set_num_threads(1)
        checkpoint = SNAPSHOT / "runs/pilot_reserved_001/seed_20042/episode_256.pt"
        trainer = MAPPOTrainer(device="cpu", log_dir=None)
        trainer.load(str(checkpoint))
        trainer.model.eval()
        metadata = {"checkpoint": str(checkpoint.relative_to(ROOT)),
                    "sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                    "episodes_completed": trainer.episodes_completed,
                    "target_masking": trainer.model.target_masking,
                    "secondary_routes": trainer.model.secondary_routes,
                    "reserve_spots": trainer.model.reserve_spots,
                    "torch_version": torch.__version__, "device": "cpu",
                    "deterministic": True}
        (api.directory / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print(json.dumps(metadata), flush=True)
    registry = json.loads((ROOT / "docs/api/sample_games.json").read_text(encoding="utf-8"))
    results = []
    for question, uuid in registry.items():
        try:
            results.append(run(question, uuid, api, trainer))
        except Exception as error:
            results.append({"question": question, "error": str(error)})
            print(question, type(error).__name__, str(error), flush=True)
        (api.directory / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
