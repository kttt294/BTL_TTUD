"""Kiểm tra cận không loại nhầm tiếp tế, chờ qua ngày hoặc đường đi hợp lệ."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hexudon.bounds import score_bounds
from hexudon.model import Board, State
from hexudon.simulator import simulate_day


class BoundTests(unittest.TestCase):
    def test_fuel_is_shared_across_days_but_waiting_can_collect_again(self):
        board = Board([[0] * 5], [{"pos": 1, "brand": 0, "stocks": 1},
                                 {"pos": 4, "brand": 1, "stocks": 1}], [0], [10] * 3, 1)
        result = score_bounds(board, [0])
        self.assertEqual(result["reachability"], (1, 3, 3))
        self.assertEqual(result["rules"], (2, 6, 6))
        state = State.initial(board, [0])
        for actions in ([[2, -8]], [[-10]], [[-10]]):
            checked = simulate_day(board, state, actions, 10)
            self.assertTrue(checked.valid)
            state = checked.state
        self.assertEqual(state.score(), result["reachability"])

    def test_daily_time_budget_is_cumulative_and_optimistic(self):
        board = Board([[0] * 4], [{"pos": 3, "brand": 0, "stocks": 1}], [0], [2, 2, 2], 20)
        result = score_bounds(board, [0])
        self.assertEqual([d["types"] for d in result["daily"]], [0, 0, 1])

    def test_supply_relaxation_includes_refuelled_paths(self):
        board = Board([[0] * 5], [{"pos": 4, "brand": 0, "stocks": 2}], [0, 1], [20] * 2, 1)
        self.assertEqual(score_bounds(board, [0, 0])["reachability"], (0, 0, 0))
        self.assertEqual(score_bounds(board, [0, 1])["reachability"], (1, 2, 2))

    def test_supply_cannot_cross_a_disconnected_pond(self):
        board = Board([[0, 0, 0, 3, 0]], [{"pos": 2, "brand": 0, "stocks": 1}], [0, 4], [20], 1)
        self.assertEqual(score_bounds(board, [0, 1])["reachability"], (0, 0, 0))
        self.assertEqual(score_bounds(board, [1, 1])["reachability"], (0, 0, 0))

    def test_small_exhaustive_paths_do_not_exceed_bound(self):
        board = Board([[0, 0], [0, 0]], [{"pos": 1, "brand": 0, "stocks": 1},
                                       {"pos": 3, "brand": 1, "stocks": 1}], [0], [2] * 3, 1)
        upper = score_bounds(board, [0])
        states = [State.initial(board, [0])]
        for day in range(3):
            following = []
            for state in states:
                for commands in ([-2], [0], [1], [2], [3], [4], [5]):
                    trial = simulate_day(board, state, [commands], 2)
                    if trial.valid:
                        self.assertTrue(all(a <= b for a, b in zip(trial.state.score(), upper["reachability"])))
                        daily_types = trial.state.daily_sum - state.daily_sum
                        self.assertLessEqual(daily_types, upper["daily"][day]["types"])
                        following.append(trial.state)
            states = following


if __name__ == "__main__":
    unittest.main()
