"""Đối chiếu quy hoạch động với vét cạn lệnh và mô phỏng độc lập."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hexudon.exact import solve_small
from hexudon.model import Board, State
from hexudon.simulator import simulate_day


def brute_force(board):
    def orders(pos, fuel, remaining, commands):
        if remaining == 0:
            yield commands
            return
        yield from orders(pos, fuel, remaining - 1, commands + [-1])
        duration, cost = board.cost(pos, {})
        if duration <= remaining and cost <= fuel:
            for direction, target in board.neighbors(pos):
                yield from orders(target, fuel - cost, remaining - duration, commands + [direction])

    def visit(state, day):
        if day == len(board.day_steps):
            return state.score()
        agent = state.agents[0]
        best = (0, 0, 0)
        for commands in orders(agent.pos, agent.fuel, board.day_steps[day], []):
            result = simulate_day(board, state, [commands], board.day_steps[day])
            assert result.valid
            best = max(best, visit(result.state, day + 1))
        return best
    return visit(State.initial(board, [0]), 0)


class ExactTests(unittest.TestCase):
    def test_matches_exhaustive_commands(self):
        for terrain in (0, 2, 3):
            for repeated in (False, True):
                board = Board([[0, 0], [terrain, 0]],
                              [{'pos': 1, 'brand': 0, 'stocks': 1},
                               {'pos': 3, 'brand': 0 if repeated else 1, 'stocks': 1}],
                              [0], [3, 3], 2)
                exact = solve_small(board)
                self.assertEqual(exact.score, brute_force(board))
                state = State.initial(board, [0])
                for steps, commands in zip(board.day_steps, exact.actions):
                    replay = simulate_day(board, state, commands, steps)
                    self.assertTrue(replay.valid)
                    state = replay.state
                self.assertEqual(state.score(), exact.score)

    def test_fuel_carries_and_wait_collects_next_day(self):
        board = Board([[0, 0, 0]], [{'pos': 1, 'brand': 0, 'stocks': 1},
                                  {'pos': 2, 'brand': 1, 'stocks': 1}], [0], [2, 2], 1)
        self.assertEqual(solve_small(board).score, (1, 2, 2))

    def test_rejects_unsupported_domain(self):
        with self.assertRaises(ValueError):
            solve_small(Board([[0, 1]], [], [0], [2], 1))
        with self.assertRaises(ValueError):
            solve_small(Board([[0, 0]], [], [0, 1], [2], 1))


if __name__ == '__main__':
    unittest.main()
