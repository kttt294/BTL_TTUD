"""Kiểm tra planner tour bản C++: kế hoạch hợp lệ, phiên nhiều luồng và dự phòng về Python."""

from pathlib import Path
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hexudon import native, tour
from hexudon.model import Agent, Board, State
from hexudon.planner import plan_day
from hexudon.simulator import simulate_day


def line_board(fuel=40, days=(30, 30, 30)):
    return Board([[0] * 8 for _ in range(2)],
                 [{"pos": 2, "brand": 0, "stocks": 2},
                  {"pos": 5, "brand": 1, "stocks": 2},
                  {"pos": 12, "brand": 2, "stocks": 1}],
                 [0, 8], list(days), fuel)


@unittest.skipUnless(native.available(), "chưa biên dịch native/hexplan")
class NativeTests(unittest.TestCase):
    def test_plan_is_valid_and_collects_every_brand(self):
        board = line_board()
        state = State.initial(board, [0, 0])
        actions = native.plan_tour(board, state, 30, 0.3)
        checked = simulate_day(board, state, actions, 30)
        self.assertTrue(checked.valid, checked.errors)
        self.assertEqual(checked.state.score()[:2], (3, 3))

    def test_supply_and_escort_plans_are_valid(self):
        for fuel in (40, 4):  # 4: một bình không đủ cả ngày, có thể hộ tống
            board = line_board(fuel=fuel)
            state = State([Agent(0, 0, fuel), Agent(1, 8, 0)])
            actions = native.plan_tour(board, state, 30, 0.3)
            checked = simulate_day(board, state, actions, 30)
            self.assertTrue(checked.valid, checked.errors)
            self.assertEqual(checked.state.score()[:2], (3, 3))

    def test_session_gives_quick_and_final_plans(self):
        board = line_board()
        state = State.initial(board, [0, 1])
        session = native.NativeSession(board, state, 30, 1.5, 0.6, workers=3, every=0.4)
        quick = session.quick()
        self.assertTrue(simulate_day(board, state, quick, 30).valid)
        for mark in session.marks:
            self.assertTrue(simulate_day(board, state, session.best_until(mark), 30).valid)
        started = time.time()
        final = session.final()
        self.assertTrue(simulate_day(board, state, final, 30).valid)
        self.assertLess(time.time() - started, 2.0)
        self.assertEqual(session.details(final)["valid_candidates"] > 0, True)

    def test_search_variants_give_valid_plans(self):
        board = line_board()
        state = State.initial(board, [0, 1])
        for params in ({"temperature": 2.0}, {"temperature": 4.0, "ktemp": True}, {"search": "pso"}):
            with mock.patch.dict(tour.PARAMS, {"native": True, **params}):
                plan = plan_day(board, state, 30, "tour", 0.8, workers=3)
            self.assertFalse(plan.fallback)
            self.assertTrue(simulate_day(board, state, plan.actions, 30).valid)


class NativeFallbackTests(unittest.TestCase):
    def test_missing_executable_falls_back_to_python(self):
        board = line_board()
        state = State.initial(board, [0, 0])
        with mock.patch.dict(tour.PARAMS, {"native": True}), mock.patch.object(native, "available", return_value=False):
            plan = plan_day(board, state, 30, "tour", 0.3)
            session = tour.make_session(board, state, 30, 1.0, 0.5, workers=2)
        self.assertFalse(plan.fallback)
        self.assertTrue(simulate_day(board, state, plan.actions, 30).valid)
        self.assertIsInstance(session, tour.AnytimeSession)
        session.final()


if __name__ == "__main__":
    unittest.main()
