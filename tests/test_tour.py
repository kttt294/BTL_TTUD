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
from hexudon.tour import DayProblem, Legs, allowances, find_anchors, plan_tour


def line_board(fuel=40, days=(30, 30, 30)):
    # Hai hàng đồng bằng, ba điểm thuộc ba chuỗi khác nhau.
    return Board([[0] * 8 for _ in range(2)],
                 [{"pos": 2, "brand": 0, "stocks": 2},
                  {"pos": 5, "brand": 1, "stocks": 2},
                  {"pos": 12, "brand": 2, "stocks": 1}],
                 [0, 8], list(days), fuel)


class TourTests(unittest.TestCase):
    def test_unreachable_leg_is_infinite_and_has_no_directions(self):
        # Cột ao ngăn hai vùng; truy vết trước đây bị lặp ở nút cha -1.
        board = Board([[0, 0, 3, 0, 0] for _ in range(3)], [], [0, 5, 10], [12], 40)
        legs = Legs(board, {}, set())
        for variant in range(3):
            self.assertEqual(legs.leg(0, 4, variant), (float('inf'), float('inf'), frozenset()))
            with self.assertRaisesRegex(ValueError, 'Không có đường đi'):
                legs.directions(0, 4, variant)
        self.assertEqual(legs.leg(0, 0, 0), (0, 0, frozenset()))
        self.assertEqual(legs.directions(0, 1, 0), [2])

    def test_tour_handles_spot_on_disconnected_island(self):
        cells = [[0] * 8 for _ in range(8)]
        for row in cells:
            row[4] = 3
        board = Board(cells, [{'pos': 2, 'brand': 0, 'stocks': 2},
                              {'pos': 7, 'brand': 1, 'stocks': 2}], [0, 8, 16], [12, 12], 40)
        state = State.initial(board, [0, 0, 0])
        for steps in board.day_steps:
            result = simulate_day(board, state, plan_tour(board, state, steps, .15), steps)
            self.assertTrue(result.valid, result.errors)
            state = result.state
        self.assertEqual(state.score()[:2], (1, 2))

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

    def test_plan_day_rejects_invalid_tour_without_greedy(self):
        board = line_board()
        state = State.initial(board, [0, 0])
        with mock.patch("hexudon.tour.plan_tour", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "không chuyển sang Greedy"):
                plan_day(board, state, 30, "tour", 0.3)

    def test_expired_coverage_is_not_cached_as_zero(self):
        board = line_board()
        state = State.initial(board, [0, 0])
        problem = DayProblem(board, state, 30, [], allowances(board, state, 30, 1.0), next_steps=4)
        key = ((0, 40), (8, 40))
        self.assertIsNone(problem.coverage_from(key, time.perf_counter() - 1))
        self.assertNotIn(key, problem.coverages)

    def test_short_budget_remains_valid_on_large_board(self):
        from hexudon.generator import generate_board
        board = generate_board(32, 71)
        state = State.initial(board, [1, 0, 0, 0])
        started = time.perf_counter()
        actions = plan_tour(board, state, board.day_steps[0], 0.05)
        self.assertLess(time.perf_counter() - started, 0.3)
        self.assertTrue(simulate_day(board, state, actions, board.day_steps[0]).valid)

    def test_anchor_forces_end_position_and_improves_next_day(self):
        # Ngày mai chỉ 4 step: xe phải dừng sẵn cạnh điểm thì mới thu được loại đó.
        board = line_board(days=(30, 4))
        state = State.initial(board, [0, 0])
        problem = DayProblem(board, state, 30, [], allowances(board, state, 30, 1.0), next_steps=4)
        problem.anchors = {0: 12}
        run = problem.run(0, [2], 0)
        self.assertTrue(run.feasible)
        self.assertEqual(run.end, 12)
        runs = {c: problem.run(c, [], 0) for c in problem.patrols}
        before = problem.coverage(runs)
        problem.anchors = {}
        anchors, covered = find_anchors(problem, runs, time.perf_counter() + 0.3, __import__("random").Random(1))
        self.assertGreater(covered, before)
        self.assertEqual(set(anchors), {0, 1})

    def test_parallel_selection_returns_valid_roles(self):
        board = line_board()
        kinds, records, elapsed = select_types(board, 6, "tour")
        self.assertIn(0, kinds)
        self.assertEqual(len(kinds), 2)
        self.assertTrue(any(r["complete"] for r in records))
        self.assertLess(elapsed, 8)


if __name__ == "__main__":
    unittest.main()
