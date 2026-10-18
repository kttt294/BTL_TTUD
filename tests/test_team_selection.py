"""Kiểm tra vai trò, hạn giờ và việc chọn theo kết quả toàn trận."""

from copy import deepcopy
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hexudon.model import Board
from hexudon.team_selection import candidate_types, evaluate_types, select_types


class TeamSelectionTests(unittest.TestCase):
    def setUp(self):
        self.board = Board([[0] * 5 for _ in range(5)],
                           [{"pos": 6, "brand": 0, "stocks": 3},
                            {"pos": 18, "brand": 1, "stocks": 3}],
                           [0, 4, 24], [12] * 4, 5)

    def test_small_team_covers_every_assignment_with_patrol(self):
        options = candidate_types(self.board)
        self.assertEqual(len(options), 7)
        self.assertEqual(len({tuple(k) for k in options}), 7)
        self.assertTrue(all(0 in kinds for kinds in options))
        self.assertIn([0, 0, 0], options)
        self.assertIn([0, 1, 0], options)

    def test_winner_uses_complete_match_and_preserves_starts(self):
        original = deepcopy(self.board)
        kinds, records, elapsed = select_types(self.board, seconds=3)
        completed = [r for r in records if r["complete"]]
        self.assertEqual(sum(r["phase"] == "screen" for r in completed), 7)
        refined = [r for r in completed if r["phase"] == "refine"]
        self.assertEqual(next(r["score"] for r in refined if r["types"] == kinds),
                         max(r["score"] for r in refined))
        self.assertEqual(self.board, original)
        self.assertLess(elapsed, 3.5)

    def test_expired_budget_is_not_a_completed_trial(self):
        record = evaluate_types(self.board, [0, 1, 0], 0.1, deadline=time.perf_counter() - 1)
        self.assertFalse(record["complete"])
        self.assertEqual(record["days"], [])
        kinds, records, _ = select_types(self.board, seconds=0)
        self.assertEqual(kinds, [0, 0, 0])
        self.assertEqual(records, [])

    def test_large_team_keeps_each_possible_single_supply(self):
        self.board.starts = list(range(8))
        options = candidate_types(self.board, limit=16)
        self.assertEqual(len(options), 16)
        for i in range(8):
            self.assertIn([int(j == i) for j in range(8)], options)


if __name__ == "__main__":
    unittest.main()
