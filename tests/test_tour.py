"""Kiểm tra planner tuyến cả đội: hợp lệ, chia nhiên liệu, tiếp tế và hạn giờ."""

from pathlib import Path
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hexudon.model import Agent, Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day
from hexudon.team_selection import select_types
from hexudon.tour import allowances, plan_tour


def line_board(fuel=40, days=(30, 30, 30)):
    # Hai hàng đồng bằng, ba điểm thuộc ba chuỗi khác nhau.
    return Board([[0] * 8 for _ in range(2)],
                 [{"pos": 2, "brand": 0, "stocks": 2},
                  {"pos": 5, "brand": 1, "stocks": 2},
                  {"pos": 12, "brand": 2, "stocks": 1}],
                 [0, 8], list(days), fuel)


class TourTests(unittest.TestCase):
    def test_plan_is_valid_and_collects_every_brand(self):
        board = line_board()
        state = State.initial(board, [0, 0])
        actions = plan_tour(board, state, 30, 0.3)
        checked = simulate_day(board, state, actions, 30)
        self.assertTrue(checked.valid, checked.errors)
        self.assertEqual(checked.state.score()[:2], (3, 3))

    def test_patrol_team_keeps_fuel_for_later_days(self):
        board = line_board(fuel=12)
        state = State.initial(board, [0, 0])
        limit = allowances(board, state, 30, 1.0)
        actions = plan_tour(board, state, 30, 0.3)
        after = simulate_day(board, state, actions, 30).state
        for before, agent in zip(state.agents, after.agents):
            self.assertLessEqual(before.fuel - agent.fuel, limit[0])
        # Ngày cuối được dùng hết nhiên liệu còn lại.
        state.day = len(board.day_steps) - 1
        self.assertEqual(allowances(board, state, 30, 1.0)[0], 12)

    def test_empty_tank_refuels_at_supply_meeting_point(self):
        board = line_board(fuel=6)
        state = State([Agent(0, 0, 0), Agent(1, 8, 0)])
        actions = plan_tour(board, state, 30, 0.3)
        checked = simulate_day(board, state, actions, 30)
        self.assertTrue(checked.valid, checked.errors)
        self.assertGreater(checked.state.portions, 0)

    def test_budget_is_respected_after_first_construction(self):
        board = line_board()
        state = State.initial(board, [0, 1])
        started = time.perf_counter()
        plan_tour(board, state, 30, 0.2)
        self.assertLess(time.perf_counter() - started, 0.5)

    def test_plan_day_falls_back_to_greedy_instead_of_waiting(self):
        board = line_board()
        state = State.initial(board, [0, 0])
        with mock.patch("hexudon.tour.plan_tour", return_value=None):
            plan = plan_day(board, state, 30, "tour", 0.3)
        self.assertTrue(plan.fallback)
        checked = simulate_day(board, state, plan.actions, 30)
        self.assertTrue(checked.valid)
        self.assertGreater(checked.state.portions, 0)

    def test_parallel_selection_returns_valid_roles(self):
        board = line_board()
        kinds, records, elapsed = select_types(board, 6, "tour")
        self.assertIn(0, kinds)
        self.assertEqual(len(kinds), 2)
        self.assertTrue(any(r["complete"] for r in records))
        self.assertLess(elapsed, 8)


if __name__ == "__main__":
    unittest.main()
