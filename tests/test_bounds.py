"""Kiểm tra cận không loại nhầm tiếp tế, chờ qua ngày hoặc đường đi hợp lệ."""

from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hexudon.bounds import score_bounds, shortest_costs
from hexudon.model import Board, State
from hexudon.simulator import simulate_day


def best_single_patrol(board, refill):
    """D và Q lớn nhất (tính riêng) của xe tuần tra đầu tiên; đường luôn thông thoáng là nới lỏng."""
    spots = {s["pos"]: (i, s["brand"]) for i, s in enumerate(board.spots)}
    results = []
    for objective in ("types", "portions"):
        frontier = {(board.starts[0], board.fuel_limit): 0}
        for steps in board.day_steps:
            following = {}
            for (start, fuel), value in frontier.items():
                # Xe đứng sẵn ở điểm thu được ngay frame đầu ngày.
                first = (start, fuel, 1 << spots[start][0] if start in spots else 0, 0)
                seen, pending = {first}, [first]
                while pending:
                    pos, left, mask, used = pending.pop()
                    duration, cost = board.cost(pos, {})
                    for _, target in board.neighbors(pos):
                        if used + duration > steps or (not refill and cost > left):
                            continue
                        visited = mask | (1 << spots[target][0]) if target in spots else mask
                        state = (target, left if refill else left - cost, visited, used + duration)
                        if state not in seen:
                            seen.add(state)
                            pending.append(state)
                for pos, left, mask, _ in seen:
                    collected = [brand for index, brand in spots.values() if mask >> index & 1]
                    gain = len(set(collected)) if objective == "types" else len(collected)
                    following[pos, left] = max(following.get((pos, left), -1), value + gain)
            frontier = following
        results.append(max(frontier.values()))
    return tuple(results)


class BoundTests(unittest.TestCase):
    def test_fuel_is_shared_across_days_but_waiting_can_collect_again(self):
        board = Board([[0] * 5], [{"pos": 1, "brand": 0, "stocks": 1},
                                 {"pos": 4, "brand": 1, "stocks": 1}], [0], [10] * 3, 1)
        result = score_bounds(board, [0])
        self.assertEqual(result["reachability"], (1, 3, 3))
        self.assertEqual(result["rules"], (2, 6, 6))
        state = State.initial(board, [0])
        for actions in ([[2, -8]], [[-10]], [[-10]]):
            checked = simulate_day(board, state, actions, 10)
            self.assertTrue(checked.valid)
            state = checked.state
        self.assertEqual(state.score(), result["reachability"])

    def test_daily_time_budget_is_cumulative_and_optimistic(self):
        board = Board([[0] * 4], [{"pos": 3, "brand": 0, "stocks": 1}], [0], [2, 2, 2], 20)
        result = score_bounds(board, [0])
        self.assertEqual([d["types"] for d in result["daily"]], [0, 0, 1])

    def test_supply_relaxation_includes_refuelled_paths(self):
        board = Board([[0] * 5], [{"pos": 4, "brand": 0, "stocks": 2}], [0, 1], [20] * 2, 1)
        self.assertEqual(score_bounds(board, [0, 0])["reachability"], (0, 0, 0))
        self.assertEqual(score_bounds(board, [0, 1])["reachability"], (1, 2, 2))

    def test_supply_cannot_cross_a_disconnected_pond(self):
        board = Board([[0, 0, 0, 3, 0]], [{"pos": 2, "brand": 0, "stocks": 1}], [0, 4], [20], 1)
        self.assertEqual(score_bounds(board, [0, 1])["reachability"], (0, 0, 0))
        self.assertEqual(score_bounds(board, [1, 1])["reachability"], (0, 0, 0))

    def test_small_exhaustive_paths_do_not_exceed_bound(self):
        board = Board([[0, 0], [0, 0]], [{"pos": 1, "brand": 0, "stocks": 1},
                                       {"pos": 3, "brand": 1, "stocks": 1}], [0], [2] * 3, 1)
        upper = score_bounds(board, [0])
        states = [State.initial(board, [0])]
        for day in range(3):
            following = []
            for state in states:
                for commands in ([-2], [0], [1], [2], [3], [4], [5]):
                    trial = simulate_day(board, state, [commands], 2)
                    if trial.valid:
                        self.assertTrue(all(a <= b for a, b in zip(trial.state.score(), upper["reachability"])))
                        daily_types = trial.state.daily_sum - state.daily_sum
                        self.assertLessEqual(daily_types, upper["daily"][day]["types"])
                        following.append(trial.state)
            states = following

    def test_route_bound_is_tighter_on_spread_spots(self):
        # Hai điểm cách nhau 6 step: ngày 8 step ghé được cả hai (2 + 6), ngày 4 step chỉ một.
        board = Board([[0] * 5], [{"pos": 1, "brand": 0, "stocks": 1},
                                 {"pos": 4, "brand": 1, "stocks": 1}], [0, 2], [8, 4, 4], 99)
        result = score_bounds(board, [0, 1])
        self.assertEqual(result["reachability"], (2, 6, 6))
        self.assertEqual(result["route"], (2, 4, 4))
        self.assertEqual([d["max_visits"] for d in result["daily"]], [[2], [1], [1]])

    def test_route_bound_never_below_best_single_patrol(self):
        rng = random.Random(7)
        for _ in range(300):
            height, width = rng.randint(1, 3), rng.randint(3, 4)
            cells = [[rng.choice((0, 0, 0, 1, 2, 3)) for _ in range(width)] for _ in range(height)]
            plains = [r * width + c for r in range(height) for c in range(width) if cells[r][c] == 0]
            if len(plains) < 3:
                continue
            rng.shuffle(plains)
            count = rng.randint(1, min(4, len(plains) - 2))
            spots = [{"pos": pos, "brand": rng.randrange(3), "stocks": 1} for pos in plains[:count]]
            board = Board(cells, spots, plains[count:count + 2],
                          [rng.randint(2, 7) for _ in range(rng.randint(1, 3))], rng.randint(1, 6))
            # Xe thứ hai làm tiếp tế; nếu cùng vùng liên thông thì nhiên liệu được nới thành vô hạn.
            refill = board.starts[0] in shortest_costs(board, board.starts[1])
            patrol_only = Board(cells, spots, board.starts[:1], board.day_steps, board.fuel_limit)
            cases = [(patrol_only, [0], False), (board, [0, 1], refill)]
            for case_board, kinds, optimistic in cases:
                best = best_single_patrol(case_board, optimistic)
                detail = (cells, spots, case_board.starts, case_board.day_steps, case_board.fuel_limit)
                for tight in (False, True):
                    upper = score_bounds(case_board, kinds, tight=tight)["route"]
                    self.assertLessEqual(best[0], upper[1], detail)
                    self.assertLessEqual(best[1], upper[2], detail)


if __name__ == "__main__":
    unittest.main()
