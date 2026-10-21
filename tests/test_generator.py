"""Kiểm tra bộ sinh config giống phân bố BTC: hợp lệ, liên thông, đúng tỷ lệ địa hình."""

from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hexudon.generator import BTC_TERRAIN, generate_config
from hexudon.model import Board


class GeneratorTests(unittest.TestCase):
    def test_configs_are_valid_connected_and_match_terrain_share(self):
        for profile in ("btc", "wide"):
            for seed in range(8):
                with self.subTest(profile=profile, seed=seed):
                    config = generate_config(seed, profile)
                    board = Board.from_dict(config)
                    size = board.width * board.height
                    walkable = [p for p in range(size) if board.terrain(p) != 3]
                    seen, stack = {walkable[0]}, [walkable[0]]
                    while stack:
                        for _, nxt in board.neighbors(stack.pop()):
                            if nxt not in seen:
                                seen.add(nxt)
                                stack.append(nxt)
                    self.assertEqual(len(seen), len(walkable))
                    share = Counter(board.terrain(p) for p in range(size))
                    for terrain, expected in enumerate(BTC_TERRAIN):
                        self.assertAlmostEqual(share[terrain] / size, expected, delta=0.01)
                    self.assertTrue(3 <= len(board.starts) <= 8)
                    self.assertTrue(4 <= len(board.day_steps) <= 10)

    def test_same_seed_gives_same_config(self):
        self.assertEqual(generate_config(7, "wide"), generate_config(7, "wide"))


if __name__ == "__main__":
    unittest.main()
