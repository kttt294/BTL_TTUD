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
from hexudon.tour import DayProblem, allowances, extended_move, find_anchors, plan_tour, removal_savings


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

    def test_parallel_seeds_return_valid_plan_within_budget(self):
        board = line_board()
        state = State.initial(board, [0, 1])
        started = time.perf_counter()
        plan = plan_day(board, state, 30, "tour", 3.0, workers=2)
        self.assertLess(time.perf_counter() - started, 3.5)
        self.assertFalse(plan.fallback)
        checked = simulate_day(board, state, plan.actions, 30)
        self.assertTrue(checked.valid, checked.errors)
        self.assertEqual(checked.state.score()[:2], (3, 3))

    def test_plan_day_survives_exception_inside_tour(self):
        board = line_board()
        state = State.initial(board, [0, 0])
        with mock.patch("hexudon.tour.plan_tour", side_effect=IndexError("lỗi giả lập")):
            plan = plan_day(board, state, 30, "tour", 0.3)
        self.assertTrue(plan.fallback)
        self.assertTrue(simulate_day(board, state, plan.actions, 30).valid)

    def test_anytime_session_gives_quick_then_final_plan_on_time(self):
        from hexudon.tour import AnytimeSession, plan_key, warm_up
        board = line_board()
        state = State.initial(board, [0, 1])
        self.assertTrue(warm_up(2))
        started = time.perf_counter()
        session = AnytimeSession(board, state, 30, 4.0, 2.0, workers=2)
        quick = session.quick()
        quick_at = time.perf_counter() - started
        final = session.final()
        final_at = time.perf_counter() - started
        self.assertLess(quick_at, 2.5)
        self.assertLess(final_at, 4.2)
        for actions in (quick, final):
            self.assertTrue(simulate_day(board, state, actions, 30).valid)
        self.assertGreaterEqual(plan_key(board, state, final), plan_key(board, state, quick))

    def test_first_construction_is_bounded_on_large_map(self):
        from hexudon.generator import generate_config
        config = generate_config(1000, "wide")  # 32x21, 8 xe
        board = Board.from_dict(config)
        state = State.initial(board, [0] * (len(board.starts) - 1) + [1])
        started = time.perf_counter()
        actions = plan_tour(board, state, board.day_steps[0], 0.1)
        self.assertLess(time.perf_counter() - started, 1.5)
        self.assertTrue(simulate_day(board, state, actions, board.day_steps[0]).valid)

    def test_extended_moves_keep_every_spot_once_per_route(self):
        import random
        board = line_board()
        state = State.initial(board, [0, 0])
        problem = DayProblem(board, state, 30, [], allowances(board, state, 30, 1.0))
        savings = removal_savings(problem, 0, [2, 5, 12], 0)
        self.assertEqual(sorted(i for _, i in savings), [0, 1, 2])
        self.assertTrue(all(saved >= 0 for saved, _ in savings))
        rng = random.Random(3)
        for _ in range(50):
            routes = {0: [2, 5, 12], 1: [5, 2]}
            if extended_move(problem, routes, {0: 0, 1: 0}, rng):
                for route in routes.values():
                    self.assertEqual(len(route), len(set(route)))

    def test_day_bound_counts_only_reachable_spots(self):
        from hexudon.tour import day_bound
        board = line_board(days=(30, 3))
        state = State.initial(board, [0, 0])
        # 30 step: mọi điểm đều tới kịp, kho (2, 2, 1) với 2 xe → 5 suất, 3 loại.
        self.assertEqual(day_bound(board, state), (3, 5))
        # Ngày 3 step: điểm gần nhất cách 2 bước đồng bằng (4 step); không điểm nào kịp.
        state.day = 1
        self.assertEqual(day_bound(board, state), (0, 0))

    def test_parallel_selection_returns_valid_roles(self):
        board = line_board()
        kinds, records, elapsed = select_types(board, 6, "tour")
        self.assertIn(0, kinds)
        self.assertEqual(len(kinds), 2)
        self.assertTrue(any(r["complete"] for r in records))
        self.assertLess(elapsed, 8)


if __name__ == "__main__":
    unittest.main()
