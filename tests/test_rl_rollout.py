"""Kiểm tra phần giữ kế hoạch dự phòng, không cần tải mô hình học máy."""

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'experiments'))
from hexudon.model import Board, State
from rl_extension import complete_match, run_variant


class ExamplePolicy:
    def candidates(self, board, state, seed):
        yield 'rl_test', [[2, -2]], [0]


class RolloutTests(unittest.TestCase):
    def setUp(self):
        self.board = Board([[0, 0]], [{'pos': 1, 'brand': 0, 'stocks': 1}], [0], [4, 4], 1)
        self.initial = {'score': (0, 0, 0), 'plans': [[[-4]], [[-4]]]}

    def test_keeps_existing_feasible_plan_without_improvement(self):
        with patch('rl_extension.plan_day', return_value=SimpleNamespace(actions=[[-4]])):
            result = run_variant(self.board, 'rollout_no_rl', self.initial, None, 1)
        self.assertEqual(result['score'], (0, 0, 0))
        self.assertEqual(result['actions'], self.initial['plans'])

    def test_adopts_better_complete_plan_and_rejects_invalid_later_move(self):
        with patch('rl_extension.plan_day', return_value=SimpleNamespace(actions=[[-4]])):
            result = run_variant(self.board, 'rl_rollout', self.initial, ExamplePolicy(), 1)
        self.assertEqual(result['score'], (1, 2, 2))
        self.assertEqual(result['selected_rl_days'], 1)
        self.assertTrue(any(not c['valid'] for c in result['days'][1]['candidates']))
        self.assertEqual(self.initial['score'], (0, 0, 0))

    def test_incomplete_or_invalid_rollout_is_not_scored(self):
        state = State.initial(self.board, [0])
        self.assertIsNone(complete_match(self.board, state, [[2]], seconds=0))
        self.assertIsNone(complete_match(self.board, state, deadline=0))


if __name__ == '__main__':
    unittest.main()
