"""Kiểm thử các luật dễ sai và đối chiếu thuật toán với lời giải vét cạn nhỏ."""

from collections import deque
from copy import deepcopy
import random
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hexudon.model import Agent, Board, State
from hexudon.search import ALGORITHMS, find_path
from hexudon.simulator import simulate_day
from hexudon.planner import choose_types, plan_day
from hexudon.generator import generate_board


def small_board(cells=None, steps=10, fuel=10):
    return Board(cells or [[0] * 4 for _ in range(4)], [], [0, 4, 8], [steps] * 4, fuel)


def exhaustive(board, start, goal, traffic, budget, fuel_limit):
    # Vét cạn theo trạng thái đầy đủ, độc lập với phép loại nhãn trong thuật toán chính.
    queue = deque([(start, 0, 0, 0)])
    seen = set(queue)
    answers = []
    while queue:
        pos, steps, fuel, hops = queue.popleft()
        if pos == goal:
            answers.append((steps, hops))
        duration, consumption = board.cost(pos, traffic)
        for _, target in board.neighbors(pos):
            nxt = target, steps + duration, fuel + consumption, hops + 1
            if nxt[1] <= budget and nxt[2] <= fuel_limit and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return answers


class GridTests(unittest.TestCase):
    def test_directions_and_parity(self):
        board = small_board()
        self.assertEqual([board.neighbor(5, d) for d in range(6)], [0, 1, 6, 9, 8, 4])
        self.assertEqual([board.neighbor(9, d) for d in range(6)], [5, 6, 10, 14, 13, 8])

    def test_neighbors_are_symmetric_and_distance_consistent(self):
        board = small_board()
        for p in range(16):
            for direction, q in board.neighbors(p):
                self.assertEqual(board.neighbor(q, (direction + 3) % 6), p)
                self.assertEqual(board.distance(p, q), 1)
                for target in range(16):
                    self.assertLessEqual(board.distance(p, target), 1 + board.distance(q, target))

    def test_boundary_and_pond(self):
        board = small_board([[0, 3], [0, 0]])
        self.assertIsNone(board.neighbor(0, 2))
        self.assertIsNone(board.neighbor(0, 0))

    def test_source_terrain_cost(self):
        board = small_board([[0, 1, 2]])
        self.assertEqual(board.cost(0, {}), (2, 1))
        self.assertEqual(board.cost(1, {1: 2}), (4, 2))
        self.assertEqual(board.cost(2, {}), (3, 2))


class SearchTests(unittest.TestCase):
    def test_against_exhaustive_random_small_cases(self):
        for seed in range(20):
            rng = random.Random(seed)
            board = small_board([[rng.choice([0, 0, 1, 2, 3]) for _ in range(3)] for _ in range(3)])
            board.cells[0][0] = board.cells[2][2] = 0
            traffic = {p: rng.randrange(3) for p in range(9) if board.terrain(p) == 1}
            answers = exhaustive(board, 0, 8, traffic, 12, 7)
            for algorithm in ALGORITHMS:
                with self.subTest(seed=seed, algorithm=algorithm):
                    route = find_path(board, 0, 8, traffic, 12, 7, algorithm)
                    self.assertEqual(route.found, bool(answers))
                    if route.found:
                        pos, steps, fuel = 0, 0, 0
                        for direction in route.actions:
                            duration, consumption = board.cost(pos, traffic)
                            pos = board.neighbor(pos, direction)
                            self.assertIsNotNone(pos)
                            steps += duration
                            fuel += consumption
                        self.assertEqual((pos, steps, fuel), (8, route.steps, route.fuel))
                        self.assertLessEqual(fuel, 7)
                        if algorithm in ("astar", "dijkstra"):
                            self.assertEqual(steps, min(a[0] for a in answers))
                        if algorithm == "bfs":
                            self.assertEqual(len(route.actions), min(a[1] for a in answers))

    def test_keep_slow_fuel_saving_label(self):
        board = small_board([[0, 1, 1, 0], [0, 0, 0, 0]])
        route = find_path(board, 0, 3, {}, 12, 4)
        self.assertTrue(route.found)
        self.assertLessEqual(route.fuel, 4)

    def test_start_goal_and_budget(self):
        board = small_board()
        self.assertEqual(find_path(board, 0, 0, {}, 0, 0).actions, [])
        self.assertFalse(find_path(board, 0, 1, {}, 1, 10).found)


class SimulatorTests(unittest.TestCase):
    def test_wait_and_last_step_arrival(self):
        board = small_board(steps=2)
        state = State.initial(board, [0, 0, 1])
        result = simulate_day(board, state, [[2], [-2], [-2]], 2)
        self.assertTrue(result.valid)
        self.assertEqual(result.state.agents[0].pos, 1)
        self.assertEqual(state.agents[0].pos, 0)

    def test_invalid_plan_does_not_modify_state(self):
        board = small_board()
        state = State.initial(board, [0, 0, 1])
        before = deepcopy(state)
        self.assertFalse(simulate_day(board, state, [[2], [-10], [-10]], 10).valid)
        self.assertEqual(state, before)

    def test_reject_out_of_map_pond_and_bad_commands(self):
        board = small_board()
        board.cells[0][1] = 3
        state = State.initial(board, [0, 0, 1])
        for commands in ([2, -8], [0, -8], [6], [True], [1.5], "sai"):
            self.assertFalse(simulate_day(board, state, [commands, [-10], [-10]], 10).valid)

    def test_reject_insufficient_steps_and_fuel(self):
        board = small_board([[2, 0], [0, 0]], steps=2)
        state = State([Agent(0, 0, 10)])
        self.assertFalse(simulate_day(board, state, [[2]], 2).valid)
        board = small_board(steps=2)
        self.assertFalse(simulate_day(board, State([Agent(0, 0, 0)]), [[2]], 2).valid)

    def test_refill_requires_wait_before_departing_with_empty_tank(self):
        board = small_board(steps=3)
        state = State([Agent(0, 0, 0), Agent(1, 0, 0)])
        self.assertFalse(simulate_day(board, state, [[2, -1], [-3]], 3).valid)
        result = simulate_day(board, state, [[-1, 2], [-3]], 3)
        self.assertTrue(result.valid)
        self.assertEqual(result.state.agents[0].pos, 1)

    def test_supplies_do_not_consume_fuel_or_collect(self):
        board = small_board(steps=2)
        board.spots = [{"pos": 1, "brand": 3, "stocks": 1}]
        result = simulate_day(board, State([Agent(1, 0, 0)]), [[2]], 2)
        self.assertTrue(result.valid)
        self.assertEqual(result.state.portions, 0)
        self.assertEqual(result.state.agents[0].fuel, 0)

    def test_stock_limit_once_per_car_and_daily_refill(self):
        board = small_board(steps=8)
        board.spots = [{"pos": 1, "brand": 7, "stocks": 1}]
        state = State([Agent(0, 0, 10), Agent(0, 2, 10)])
        result = simulate_day(board, state, [[2, 5, 2, -2], [5, -6]], 8)
        self.assertTrue(result.valid)
        self.assertEqual(result.state.score(), (1, 1, 1))
        next_day = simulate_day(board, result.state, [[-8], [-8]], 8)
        self.assertEqual(next_day.state.score(), (1, 2, 2))

    def test_traffic_uses_exactly_two_previous_days(self):
        board = small_board([[1, 0]], steps=2)
        state = State([Agent(1, 0, 0)])
        day1 = simulate_day(board, state, [[-1, 2]], 2).state
        self.assertEqual(day1.traffic[0], 0)
        day2 = simulate_day(board, day1, [[-2]], 2).state
        self.assertEqual(day2.road_history, [{0: 1}, {}])
        day3 = simulate_day(board, day2, [[-2]], 2).state
        self.assertEqual(day3.road_history, [{}, {}])

    def test_traffic_thresholds(self):
        board = small_board([[1, 0]], steps=2)
        board.busy_threshold, board.jammed_threshold = 2, 4
        state = State([Agent(1, 0, 0)])
        day1 = simulate_day(board, state, [[-2]], 2).state
        self.assertEqual(day1.traffic[0], 1)
        day2 = simulate_day(board, day1, [[-2]], 2).state
        self.assertEqual(day2.traffic[0], 2)


class PlannerTests(unittest.TestCase):
    def test_generated_board_connected(self):
        board = generate_board(8, 5)
        reached, pending = set(), [board.starts[0]]
        while pending:
            p = pending.pop()
            if p not in reached:
                reached.add(p)
                pending.extend(q for _, q in board.neighbors(p) if q not in reached)
        self.assertEqual(len(reached), sum(v != 3 for row in board.cells for v in row))

    def test_both_planners_finish_valid_matches(self):
        for strategy in ("greedy", "lookahead"):
            for seed in (4, 5, 6):
                board = generate_board(8, seed, fuel=16)
                state = State.initial(board, [0, 0, 0, 1])
                for steps in board.day_steps:
                    plan = plan_day(board, state, steps, strategy, 0.12)
                    self.assertFalse(plan.fallback, plan.errors)
                    checked = simulate_day(board, state, plan.actions, steps)
                    self.assertTrue(checked.valid, checked.errors)
                    state = checked.state

    def test_zero_budget_produces_valid_wait(self):
        board = generate_board()
        state = State.initial(board, [0, 0, 0, 1])
        planned = plan_day(board, state, 80, seconds=0)
        self.assertEqual(planned.actions, [[-80]] * 4)
        self.assertTrue(simulate_day(board, state, planned.actions, 80).valid)

    def test_choose_types_and_no_stations(self):
        board = generate_board(8, 2, steps=20)
        kinds, trials, _ = choose_types(board, 0.2)
        self.assertEqual(len(kinds), 4)
        self.assertTrue(any(trial["complete"] for trial in trials))
        self.assertTrue(all(0 in trial["types"] for trial in trials))
        state = State.initial(board, [0] * 4)
        planned = plan_day(board, state, 20, seconds=0.1)
        self.assertTrue(simulate_day(board, state, planned.actions, 20).valid)


if __name__ == "__main__":
    unittest.main()
