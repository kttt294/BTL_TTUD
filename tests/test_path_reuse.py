"""Kiểm tra bộ A* đối chứng dùng đúng chi phí của bộ tạo chặng tour."""

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('path_reuse', ROOT / 'experiments/benchmark/path_reuse.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


class PathReuseTests(unittest.TestCase):
    def test_all_pairs_match_weighted_dijkstra_with_directed_costs(self):
        board = study.Board([[0, 1, 2], [0, 3, 0], [2, 1, 0]], [], [0, 3, 5], [20], 10)
        graph = study.Legs(board, {1: 2, 7: 1}, {2, 6})
        astar = study.PairAStar(graph)
        for source in range(9):
            if board.terrain(source) == 3:
                continue
            for goal in range(9):
                if board.terrain(goal) == 3:
                    continue
                for variant, (a, b) in enumerate(study.VARIANTS):
                    query = source, goal, variant
                    x, y = graph.leg(*query), astar.leg(*query)
                    self.assertAlmostEqual(a*x[0]+b*x[1], a*y[0]+b*y[1])
                    study.verify_path(graph, astar, query, y)
        old = len(astar.cache)
        astar.leg(0, 8, 0)
        self.assertEqual(len(astar.cache), old)

    def test_unreachable_and_zero_length(self):
        board = study.Board([[0, 3, 0], [0, 3, 0]], [], [0, 3, 2], [10], 10)
        graph = study.Legs(board, {}, set())
        astar = study.PairAStar(graph)
        for variant in range(3):
            self.assertEqual(astar.leg(0, 0, variant), (0, 0, frozenset()))
            self.assertEqual(astar.leg(0, 2, variant), (study.INF, study.INF, frozenset()))
            with self.assertRaises(ValueError):
                astar.directions(0, 2, variant)


if __name__ == '__main__':
    unittest.main()
