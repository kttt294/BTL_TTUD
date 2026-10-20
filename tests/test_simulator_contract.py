"""Kiểm thử hồi quy từ replay BTC và luật nhiều đội tính tay."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments" / "api"))
from hexudon.model import Agent, Board, State
from hexudon.simulator import simulate_day, simulate_match_day
from compare_api import compare, read_response


class TimelineTests(unittest.TestCase):
    def test_fuel_changes_only_on_arrival(self):
        board = Board([[0, 0]], [], [0], [2], 10)
        result = simulate_day(board, State([Agent(0, 0, 10)]), [[2]], 2, True)
        self.assertEqual(result.trace[1]["positions"], [0])
        self.assertEqual(result.trace[1]["fuel"], [10])
        self.assertEqual(result.trace[2]["fuel"], [9])

    def test_refuel_on_arrival_even_at_last_step(self):
        board = Board([[0, 0]], [], [0, 1], [2], 10)
        result = simulate_day(board, State([Agent(0, 0, 5), Agent(1, 1, 0)]), [[2], [-2]], 2)
        self.assertTrue(result.valid)
        self.assertEqual(result.state.agents[0].fuel, 10)

    def test_no_collect_at_frame_zero(self):
        board = Board([[0, 0]], [{"pos": 0, "brand": 7, "stocks": 1}], [1], [2], 10)
        result = simulate_day(board, State([Agent(0, 0, 10)]), [[-2]], 2, True)
        self.assertEqual(result.trace[0]["servings"], 0)
        self.assertEqual(result.trace[1]["servings"], 1)
        self.assertEqual(result.trace[1]["collected"], [0])

    def test_road_count_uses_position_after_step(self):
        board = Board([[0, 1]], [], [0], [4], 10, 3, 4)
        result = simulate_day(board, State([Agent(0, 0, 10)]), [[2, -2]], 4)
        self.assertEqual(result.state.road_history, [{1: 3}])
        self.assertEqual(result.state.traffic[1], 1)

    def test_road_departure_does_not_count_old_position(self):
        board = Board([[1, 0]], [], [1], [1], 10)
        result = simulate_day(board, State([Agent(0, 0, 10)]), [[2]], 1)
        self.assertEqual(result.state.road_history, [{}])

    def test_busy_road_transit_is_not_stationary_traffic(self):
        board = Board([[1, 0]], [], [1], [2], 10)
        state = State([Agent(0, 0, 10)], {0: 1})
        result = simulate_day(board, state, [[2]], 2, True)
        self.assertEqual(result.trace[1]["positions"], [0])
        self.assertEqual(result.state.road_history, [{}])

    def test_traffic_after_first_arrival_includes_transition(self):
        board = Board([[0, 1, 0]], [], [0], [4], 10)
        state = State([Agent(0, 0, 10)], {1: 1})
        result = simulate_day(board, state, [[2, 2]], 4)
        self.assertEqual(result.state.road_history, [{1: 2}])

    def test_refuel_can_happen_before_current_move_finishes(self):
        board = Board([[1, 1], [0, 0]], [], [2, 3], [4], 10)
        state = State([Agent(0, 0, 7), Agent(1, 2, 0)], {0: 2})
        result = simulate_day(board, state, [[2], [1, -2]], 4, True)
        self.assertEqual(result.trace[2]["positions"], [0, 0])
        self.assertEqual(result.trace[2]["fuel"], [10, 0])
        self.assertEqual(result.trace[-1]["fuel"][0], 8)

    def test_simultaneous_stock_cap(self):
        board = Board([[0, 0, 0]], [{"pos": 1, "brand": 7, "stocks": 1}], [0, 2], [2], 10)
        state = State([Agent(0, 0, 10), Agent(0, 2, 10)])
        result = simulate_day(board, state, [[2], [5]], 2, True)
        self.assertEqual(result.state.score(), (1, 1, 1))
        self.assertEqual(result.trace[-1]["collected"], [1])


class MultipleTeamTests(unittest.TestCase):
    def test_stocks_are_separate_between_teams(self):
        board = Board([[0, 0]], [{"pos": 1, "brand": 0, "stocks": 1}], [0], [2], 10)
        states = {"a": State([Agent(0, 0, 10)]), "b": State([Agent(0, 0, 10)])}
        result = simulate_match_day(board, states, {"a": [[2]], "b": [[2]]}, 2)
        self.assertTrue(result.valid)
        self.assertEqual(result.states["a"].portions, 1)
        self.assertEqual(result.states["b"].portions, 1)

    def test_supply_does_not_refuel_another_team(self):
        board = Board([[0, 0]], [], [0], [2], 10)
        states = {"a": State([Agent(0, 0, 5)]), "b": State([Agent(1, 1, 0)])}
        result = simulate_match_day(board, states, {"a": [[2]], "b": [[-2]]}, 2)
        self.assertEqual(result.states["a"].agents[0].fuel, 4)

    def test_traffic_divides_by_number_of_teams(self):
        board = Board([[1, 0]], [], [1], [4], 10, 3, 4)
        states = {"a": State([Agent(1, 0, 0)]), "b": State([Agent(1, 1, 0)])}
        orders = {"a": [[-4]], "b": [[-4]]}
        day1 = simulate_match_day(board, states, orders, 4)
        self.assertEqual(day1.states["a"].traffic[0], 0)
        day2 = simulate_match_day(board, day1.states, orders, 4)
        self.assertEqual(day2.states["a"].traffic[0], 2)
        self.assertEqual(day2.states["a"].traffic, day2.states["b"].traffic)

    def test_invalid_team_does_not_mutate_input(self):
        board = Board([[0, 0]], [], [0], [2], 10)
        states = {"a": State([Agent(0, 0, 0)]), "b": State([Agent(0, 0, 10)])}
        original = deepcopy(states)
        result = simulate_match_day(board, states, {"a": [[2]], "b": [[2]]}, 2)
        self.assertFalse(result.valid)
        self.assertEqual(states, original)


class ServerReplayTests(unittest.TestCase):
    def test_saved_server_replays(self):
        directory = ROOT / "experiments/data/api_evidence"
        cases = [("q02_before_config", "q02_in_transit_replay", "q02_final_actions"),
                 ("q10_config", "q10_immediate_replay", "q10_immediate_actions"),
                 ("q10_config", "q10_wait_replay", "q10_wait_actions")]
        for question in ("q03", "q04", "q06"):
            cases.append((question + "_config", question + "_replay", question + "_actions"))
        for config, replay, actions in cases:
            with self.subTest(replay=replay):
                result = compare(read_response(directory / (config + ".json")),
                                 read_response(directory / (replay + ".json")),
                                 read_response(directory / (actions + ".json")))
                self.assertGreater(result["checked_frames"], 0)
                self.assertEqual(result["mismatch_count"], 0, result["examples"])

    def test_server_rejects_invalid_plans(self):
        directory = ROOT / "experiments/data/api_evidence"
        for name in ("q02_invalid_command", "q02_invalid_too_many_steps",
                     "q02_invalid_pond", "q06_invalid_fuel"):
            record = json.loads((directory / (name + ".json")).read_text(encoding="utf-8"))
            self.assertIn(record["status"], (409, 422))
            self.assertIn("detail", record["response"])


if __name__ == "__main__":
    unittest.main()
