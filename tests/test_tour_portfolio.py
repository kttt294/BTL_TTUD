"""Kiểm tra cách chọn điểm thật và truyền seed cho các tiến trình tour."""

from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hexudon.tour import AnytimeSession, choose_best
from hexudon.model import Board, State
from hexudon.planner import plan_day


class PortfolioTests(unittest.TestCase):
    def test_score_selection_ignores_invalid_and_does_not_forecast(self):
        state = SimpleNamespace(daily_sum=10, portions=20)
        def check(board, old, actions, steps):
            valid, u, d, q = actions
            return SimpleNamespace(valid=valid, state=SimpleNamespace(
                brands=set(range(u)), daily_sum=10 + d, portions=20 + q))
        candidates = [(True, 3, 3, 6), (False, 9, 9, 99), (True, 3, 2, 90), (True, 3, 3, 8)]
        with patch("hexudon.tour.simulate_day", side_effect=check), patch(
                "hexudon.tour.next_coverage", side_effect=AssertionError("Không được dự báo")):
            result = choose_best(None, state, 30, candidates, 0, objective="score")
        self.assertEqual(result, candidates[-1])

    def test_workers_receive_distinct_seeds_from_requested_start(self):
        pool = Mock()
        with patch("hexudon.tour._pool", return_value=pool), patch("hexudon.tour._queue"):
            session = AnytimeSession(None, None, 30, 5, 2, workers=3, seed=17, objective="score")
        jobs = [call.args[1] for call in pool.submit.call_args_list]
        self.assertEqual([job[-1] for job in jobs], [17, 18, 19])
        self.assertEqual(session.seeds, [17, 18, 19])

    def test_invalid_configuration_is_rejected_before_spawning(self):
        with self.assertRaises(ValueError):
            AnytimeSession(None, None, 30, 5, 2, workers=0)

    def test_planner_passes_seed_and_selection_and_keeps_audit(self):
        board = Board([[0] * 8], [], [0, 3, 7], [10], 40)
        state = State.initial(board, [0, 0, 1])
        actions, details = [[-10], [-10], [-10]], {"seeds": [17, 18]}
        with patch("hexudon.tour.plan_tour_parallel", return_value=(actions, details)) as run:
            plan = plan_day(board, state, 10, "tour", 3, workers=2, seed=17,
                            parallel_objective="score")
        self.assertEqual(run.call_args.args[-2:], (17, "score"))
        self.assertFalse(plan.fallback)
        self.assertEqual(plan.details, details)


if __name__ == "__main__":
    unittest.main()
