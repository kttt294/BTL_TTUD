"""Lập tuyến cả đội trong một ngày: chèn điểm tham lam, tìm kiếm lân cận và chia nhiên liệu.

Mỗi xe tuần tra có một dãy điểm udon; chặng giữa hai điểm là đường ngắn nhất theo một
trọng số step/nhiên liệu. Đội không có xe tiếp tế được chia nhiên liệu theo tỷ lệ step còn
lại của trận. Đội có xe tiếp tế đặt mỗi xe tiếp tế ở một điểm hẹn trong ngày; xe tuần tra
tự rẽ vào điểm hẹn khi không đủ nhiên liệu cho chặng tiếp theo và đường quay về.
"""

from collections import Counter
from dataclasses import dataclass
import heapq
import random
import time

from .model import Agent, State
from .simulator import simulate_day

# Trọng số (step, nhiên liệu) của ba kiểu đường: nhanh, cân bằng, tiết kiệm.
VARIANTS = ((1.0, 0.001), (1.0, 1.0), (0.001, 1.0))
INF = float("inf")


@dataclass
class CarRun:
    feasible: bool
    steps: int = 0
    fuel: int = 0
    spent: int = 0
    visited: frozenset = frozenset()
    segments: tuple = ()
    cost: float = 0.0
    end: int = -1


class Legs:
    """Cây đường ngắn nhất từ từng ô nguồn, tính lười và lưu lại trong ngày."""

    def __init__(self, board, traffic, spot_set):
        self.board, self.spot_set = board, spot_set
        size = board.width * board.height
        self.cost = [board.cost(p, traffic) if board.terrain(p) != 3 else (0, 0) for p in range(size)]
        self.nbrs = [board.neighbors(p) if board.terrain(p) != 3 else [] for p in range(size)]
        self.trees, self.legs = {}, {}

    def tree(self, source, variant):
        key = source, variant
        if key not in self.trees:
            a, b = VARIANTS[variant]
            size = len(self.cost)
            dist, steps, fuel = [INF] * size, [0] * size, [0] * size
            parent, pdir = [-1] * size, [-1] * size
            dist[source] = 0.0
            heap = [(0.0, source)]
            cost, nbrs = self.cost, self.nbrs
            while heap:
                d, u = heapq.heappop(heap)
                if d > dist[u]:
                    continue
                su, fu = cost[u]
                nd, ns, nf = d + a * su + b * fu, steps[u] + su, fuel[u] + fu
                for direction, v in nbrs[u]:
                    if nd < dist[v] - 1e-9:
                        dist[v], steps[v], fuel[v] = nd, ns, nf
                        parent[v], pdir[v] = u, direction
                        heapq.heappush(heap, (nd, v))
            self.trees[key] = steps, fuel, parent, pdir
        return self.trees[key]

    def leg(self, start, goal, variant):
        """Trả về (step, nhiên liệu, các điểm udon đi qua kể cả đích)."""
        key = start, goal, variant
        if key not in self.legs:
            steps, fuel, parent, _ = self.tree(start, variant)
            spots, pos = [], goal
            while pos != start:
                if pos in self.spot_set:
                    spots.append(pos)
                pos = parent[pos]
            self.legs[key] = steps[goal], fuel[goal], frozenset(spots)
        return self.legs[key]

    def directions(self, start, goal, variant):
        _, _, parent, pdir = self.tree(start, variant)
        reverse, pos = [], goal
        while pos != start:
            reverse.append(pdir[pos])
            pos = parent[pos]
        return reverse[::-1]


class DayProblem:
    def __init__(self, board, state, steps, hubs, allowance, next_steps=None, beta=0.0):
        self.board, self.state, self.steps = board, state, steps
        self.next_steps, self.beta, self.values = next_steps, beta, {}
        self.spot_at = {s["pos"]: s for s in board.spots}
        self.legs = Legs(board, state.traffic, set(self.spot_at))
        self.patrols = [i for i, a in enumerate(state.agents) if a.kind == 0]
        self.hubs = hubs  # danh sách (ô hẹn, step xe tiếp tế tới nơi)
        self.allowance = allowance
        self.limit = board.fuel_limit
        self.reserves = {}
        # anchors: ô xe tuần tra phải dừng cuối ngày để ngày mai đi đủ loại.
        self.anchors, self.coverages, self.alpha = {}, {}, 1.0

    def reserve(self, pos):
        if not self.hubs:
            return 0
        if pos not in self.reserves:
            self.reserves[pos] = min(self.legs.leg(pos, hub, 2)[1] for hub, _ in self.hubs)
        return self.reserves[pos]

    def refuel_hub(self, pos, goal, variant):
        best = None
        for hub, arrival in self.hubs:
            go = self.legs.leg(pos, hub, variant)
            back = self.legs.leg(hub, goal, variant) if goal is not None else (0, 0, frozenset())
            total = go[0] + back[0]
            if best is None or total < best[0]:
                best = total, hub, arrival, go
        return best

    def run(self, car, stops, variant):
        anchor = self.anchors.get(car)
        if anchor is not None and (not stops or stops[-1] != anchor):
            stops = list(stops) + [anchor]
        agent = self.state.agents[car]
        pos, t, fuel, spent_since = agent.pos, 0, agent.fuel, 0
        visited = {pos} if pos in self.spot_at else set()
        segments, refueled = [], False
        T, legs = self.steps, self.legs
        for stop in stops:
            leg = legs.leg(pos, stop, variant)
            if self.hubs and fuel < leg[1] + self.reserve(stop):
                _, hub, arrival, go = self.refuel_hub(pos, stop, variant)
                if fuel < go[1]:
                    return CarRun(False)
                if hub != pos:
                    segments.append(("leg", pos, hub, variant))
                    visited |= go[2]
                t += go[0]
                fuel -= go[1]
                if arrival > t:
                    segments.append(("wait", arrival - t))
                    t = arrival
                fuel, pos, refueled = self.limit, hub, True
                leg = legs.leg(pos, stop, variant)
                if fuel < leg[1] + self.reserve(stop):
                    return CarRun(False)
            elif fuel < leg[1]:
                return CarRun(False)
            segments.append(("leg", pos, stop, variant))
            t += leg[0]
            fuel -= leg[1]
            visited |= leg[2]
            pos = stop
            if t > T:
                return CarRun(False)
        if self.hubs and stops:
            # Xe đứng yên luôn hợp lệ; xe đã di chuyển phải còn đủ nhiên liệu về điểm hẹn.
            if fuel < self.reserve(pos):
                _, hub, arrival, go = self.refuel_hub(pos, None, variant)
                if fuel < go[1] or t + go[0] > T:
                    return CarRun(False)
                segments.append(("leg", pos, hub, variant))
                visited |= go[2]
                t += go[0]
                fuel = self.limit if max(t, arrival) <= T else fuel - go[1]
                refueled = refueled or fuel == self.limit
                pos = hub
        elif agent.fuel - fuel > self.allowance[car]:
            return CarRun(False)
        spent = agent.fuel - fuel if not refueled else self.limit - fuel
        scale = self.limit if self.hubs else max(1, self.allowance[car])
        return CarRun(True, t, fuel, max(0, spent), frozenset(visited), tuple(segments),
                      t / T + max(0, agent.fuel - fuel) / scale, pos)

    def value(self, pos):
        """Số điểm một xe ghé được ngày mai nếu xuất phát tại pos, theo láng giềng gần nhất."""
        if not self.next_steps or not self.beta:
            return 0
        if pos not in self.values:
            left, here, seen, count = self.next_steps, pos, {pos}, int(pos in self.spot_at)
            while True:
                options = [(self.legs.leg(here, q, 0)[0], q) for q in self.spot_at if q not in seen]
                options = [o for o in options if o[0] <= left]
                if not options:
                    break
                cost, here = min(options)
                left -= cost
                seen.add(here)
                count += 1
            self.values[pos] = count
        return self.values[pos]

    def score(self, runs):
        counts = Counter(p for run in runs.values() for p in run.visited)
        brands = {self.spot_at[p]["brand"] for p in counts}
        portions = sum(min(c, self.spot_at[p]["stocks"]) for p, c in counts.items())
        new = len(brands - self.state.brands)
        spent = sum(r.spent for r in runs.values())
        steps = sum(r.steps for r in runs.values())
        future = self.beta * sum(self.value(r.end) for r in runs.values()) if self.beta else 0
        return new, len(brands), portions + future, -spent, -steps

    def coverage(self, runs):
        """Số loại tối đa ngày mai theo bản dựng chỉ nhắm loại, giao thông hôm nay làm dự báo."""
        return self.coverage_from(tuple((runs[c].end, runs[c].fuel) for c in self.patrols))

    def coverage_from(self, key):
        if not self.next_steps:
            return 0
        ends = dict(zip(self.patrols, key))
        if key not in self.coverages:
            hubs = iter([hub for hub, _ in self.hubs])
            agents = []
            for car, agent in enumerate(self.state.agents):
                if agent.kind == 0:
                    agents.append(Agent(0, *ends[car]))
                else:
                    agents.append(Agent(1, next(hubs, agent.pos), 0))
            tomorrow = State(agents, self.state.traffic, set(), day=self.state.day + 1)
            problem = DayProblem(self.board, tomorrow, self.next_steps, [(h, 0) for h, _ in self.hubs],
                                 allowances(self.board, tomorrow, self.next_steps, self.alpha))
            problem.legs = self.legs
            best = 0
            for variant in ((0,) if self.hubs else (0, 2)):
                result = construct(problem, variant, types_only=True)
                if result is not None:
                    best = max(best, result[0][1])
                if best == self.brand_count:
                    break
            self.coverages[key] = best
        return self.coverages[key]

    @property
    def brand_count(self):
        return len({s["brand"] for s in self.board.spots})


def car_insertions(problem, car, route, variant, current, positions=3):
    """Phương án chèn rẻ nhất cho từng điểm vào tuyến của một xe."""
    legs, T = problem.legs, problem.steps
    seq = [problem.state.agents[car].pos] + route
    options = {}
    for spot in problem.spot_at:
        if spot in current.visited:
            continue
        # Ước lượng step tăng thêm khi chưa tính đường rẽ tiếp nhiên liệu để lọc vị trí chèn.
        quick = []
        for k in range(len(seq)):
            a = seq[k]
            extra = legs.leg(a, spot, variant)[0]
            if k + 1 < len(seq):
                b = seq[k + 1]
                extra += legs.leg(spot, b, variant)[0] - legs.leg(a, b, variant)[0]
            if current.steps + extra <= T:
                quick.append((extra, k))
        quick.sort()
        best = None
        for _, k in quick[:positions]:
            trial = route[:k] + [spot] + route[k:]
            run = problem.run(car, trial, variant)
            if run.feasible and (best is None or run.cost < best[0]):
                best = run.cost - current.cost, trial, run
        if best is not None:
            options[spot] = best
    return options


def insert_greedy(problem, routes, variants, runs, rng=None, noise=0.0, deadline=None,
                  types_only=False):
    spot_at, brands_before = problem.spot_at, problem.state.brands
    cache = {}
    while deadline is None or time.perf_counter() < deadline:
        counts = Counter(p for run in runs.values() for p in run.visited)
        today = {spot_at[p]["brand"] for p in counts}
        best = None
        for car in problem.patrols:
            if car not in cache:
                cache[car] = car_insertions(problem, car, routes[car], variants[car], runs[car])
            for spot, (delta, trial, run) in cache[car].items():
                info = spot_at[spot]
                brand = info["brand"]
                gain = (brand not in brands_before and brand not in today,
                        brand not in today, counts[spot] < info["stocks"])
                if not any(gain) or types_only and not gain[1]:
                    continue
                if rng is not None and noise:
                    delta *= 1 + noise * rng.random()
                key = gain, -delta
                if best is None or key > best[0]:
                    best = key, car, trial, run
        if best is None:
            return
        _, car, trial, run = best
        routes[car], runs[car] = trial, run
        del cache[car]


def construct(problem, variant, deadline=None, types_only=False, rng=None, noise=0.0):
    routes = {c: [] for c in problem.patrols}
    variants = {c: variant for c in problem.patrols}
    runs = {c: problem.run(c, [], variant) for c in problem.patrols}
    if not all(r.feasible for r in runs.values()):
        return None
    insert_greedy(problem, routes, variants, runs, rng, noise, deadline, types_only)
    return problem.score(runs), routes, variants, runs


def cover_types(candidates, deadline, rng, variants, best):
    """Dựng lại nhiều lần chỉ nhắm loại, có nhiễu, rồi chèn thêm suất vào khung đủ loại nhất."""
    attempt = 0
    while time.perf_counter() < deadline:
        _, option, problem = candidates[attempt % len(candidates)]
        variant = variants[(attempt // len(candidates)) % len(variants)]
        attempt += 1
        skeleton = construct(problem, variant, deadline, True, rng, 1.0 + rng.random())
        if skeleton is None or skeleton[0][1] < best[0][0][1]:
            continue
        _, routes, chosen, runs = skeleton
        insert_greedy(problem, routes, chosen, runs, deadline=deadline)
        score = problem.score(runs)
        if score > best[0][0]:
            best = (score, routes, chosen, runs), option, problem
        if best[0][0][1] == problem.brand_count:
            break
    return best


def improve(problem, solution, deadline, rng):
    """Phá và dựng lại: bỏ vài điểm hoặc đổi kiểu đường của một xe, chèn lại có nhiễu."""
    score, routes, variants, runs = solution
    while time.perf_counter() < deadline and problem.patrols:
        new_routes = {c: list(r) for c, r in routes.items()}
        new_variants = dict(variants)
        move = rng.random()
        if move < 0.15:
            car = rng.choice(problem.patrols)
            new_variants[car] = rng.randrange(len(VARIANTS))
        stops = [(c, i) for c, r in new_routes.items() for i in range(len(r))]
        if stops:
            count = rng.randint(1, min(4, len(stops)))
            if move < 0.35:
                car = rng.choice(problem.patrols)
                if new_routes[car]:
                    i = rng.randrange(len(new_routes[car]))
                    j = rng.randint(i + 1, min(len(new_routes[car]), i + 4))
                    del new_routes[car][i:j]
            else:
                for c, i in sorted(rng.sample(stops, count), key=lambda x: -x[1]):
                    del new_routes[c][i]
        new_runs = {}
        for c in problem.patrols:
            run = problem.run(c, new_routes[c], new_variants[c])
            if not run.feasible:
                new_routes[c], run = [], problem.run(c, [], new_variants[c])
            new_runs[c] = run
        if not all(r.feasible for r in new_runs.values()):
            continue
        insert_greedy(problem, new_routes, new_variants, new_runs, rng, 0.5, deadline)
        new_score = problem.score(new_runs)
        if new_score >= score:
            score, routes, variants, runs = new_score, new_routes, new_variants, new_runs
    return score, routes, variants, runs


def commands(problem, runs, supply_routes):
    legs, steps = problem.legs, problem.steps
    actions = [[] for _ in problem.state.agents]
    for car, run in runs.items():
        used = 0
        for segment in run.segments:
            if segment[0] == "wait":
                actions[car].append(-segment[1])
                used += segment[1]
            else:
                _, a, b, variant = segment
                actions[car].extend(legs.directions(a, b, variant))
                used += legs.leg(a, b, variant)[0]
        if used < steps:
            actions[car].append(-(steps - used))
    for car, (hub, arrival) in supply_routes.items():
        pos = problem.state.agents[car].pos
        if hub != pos:
            actions[car].extend(legs.directions(pos, hub, 0))
        if arrival < steps:
            actions[car].append(-(steps - arrival))
    return actions


def hub_candidates(board, state, car, legs, steps, count=4):
    spots = [s["pos"] for s in board.spots]
    patrols = [a.pos for a in state.agents if a.kind == 0]
    pos = state.agents[car].pos
    central = sorted(spots, key=lambda p: sum(board.distance(p, q) for q in spots))
    near = sorted(spots, key=lambda p: sum(board.distance(p, q) for q in patrols))
    # Xe tuần tra gần cạn nhiên liệu chỉ được cứu khi xe tiếp tế tự chạy tới chỗ nó.
    stranded = [a.pos for a in state.agents if a.kind == 0 and a.fuel < board.fuel_limit // 4]
    options = [pos]
    for p in stranded + central[:count] + near[:count]:
        if p not in options:
            options.append(p)
    result = []
    for hub in options:
        arrival = legs.leg(pos, hub, 0)[0] if hub != pos else 0
        if arrival <= steps:
            result.append((hub, arrival))
    return result


def allowances(board, state, steps, alpha):
    remaining = sum(board.day_steps[state.day:]) or steps
    share = 1.0 if state.day >= len(board.day_steps) - 1 else min(1.0, alpha * steps / remaining)
    return {i: int(a.fuel * share) for i, a in enumerate(state.agents)}


def find_anchors(problem, runs, deadline, rng):
    """Leo đồi trên ô dừng cuối ngày của từng xe để ngày mai phủ đủ loại, đi ít step nhất."""
    reach = {}
    for car in problem.patrols:
        options = {}
        for spot in problem.spot_at:
            run = problem.run(car, [spot], 0)
            if run.feasible:
                options[spot] = run
        if not options:
            return None
        reach[car] = options
    current = {c: runs[c].end if runs[c].end in reach[c] else rng.choice(list(reach[c])) for c in problem.patrols}

    def key(anchors):
        ends = tuple((a, reach[c][a].fuel) for c, a in anchors.items())
        return problem.coverage_from(ends), -sum(reach[c][a].steps for c, a in anchors.items())

    best = key(current)
    while time.perf_counter() < deadline:
        trial = dict(current)
        for car in rng.sample(problem.patrols, rng.randint(1, min(2, len(problem.patrols)))):
            trial[car] = rng.choice(list(reach[car]))
        score = key(trial)
        if score >= best:
            current, best = trial, score
    return current, best[0]


def plan_tour(board, state, steps, seconds=2.0, alpha=1.0, seed=0, beta=0.0):
    started = time.perf_counter()
    deadline = started + max(0.0, seconds)
    rng = random.Random(seed + 7919 * state.day)
    supplies = [i for i, a in enumerate(state.agents) if a.kind == 1]
    allowance = allowances(board, state, steps, alpha)
    following = board.day_steps[state.day + 1] if state.day + 1 < len(board.day_steps) else None
    base = DayProblem(board, state, steps, [], allowance, following, beta)
    options = [[]]
    for car in supplies:
        cands = hub_candidates(board, state, car, base.legs, steps)
        options = [o + [(car, c)] for o in options for c in cands][:12]
    # Đội không có tiếp tế phải tiết kiệm nhiên liệu nên thử cả ba kiểu đường khi dựng.
    variants = (0,) if supplies else (0, 1, 2)
    best, candidates = None, []
    for index, option in enumerate(options):
        problem = DayProblem(board, state, steps, [hub for _, hub in option], allowance, following, beta)
        problem.legs, problem.values = base.legs, base.values
        for variant in variants:
            # Luôn dựng xong phương án đầu tiên; các phương án sau chỉ dựng khi còn giờ.
            if best is not None and time.perf_counter() >= started + seconds * 0.4:
                break
            result = construct(problem, variant, None if best is None else deadline)
            if result is None:
                continue
            if (option, problem) not in [(o, p) for _, o, p in candidates]:
                candidates.append((result, option, problem))
            if best is None or result[0] > best[0][0]:
                best = result, option, problem
    if best is None:
        return None
    if best[0][0][1] < base.brand_count and best[2].patrols:
        # Ngày ngắn: phủ đủ loại là bài toán chặt, chèn tham lam một lượt dễ thiếu một loại.
        cover_until = time.perf_counter() + max(0.0, deadline - time.perf_counter()) * 0.4
        best = cover_types(candidates, cover_until, rng, variants if supplies else (0, 2), best)
    solution, option, problem = best
    problem.alpha = alpha
    if following and problem.patrols:
        # Kiểm tra ngày mai có đi đủ loại từ vị trí cuối ngày không. Nếu thiếu, tìm ô neo cho
        # từng xe rồi lập lại tuyến phải dừng ở ô neo; chỉ nhận khi (loại hôm nay, loại ngày mai)
        # không kém, vì D xếp trên Q.
        remaining = lambda: max(0.0, deadline - time.perf_counter())
        solution = improve(problem, solution, time.perf_counter() + remaining() * 0.3, rng)
        covered = problem.coverage(solution[3])
        if covered < problem.brand_count:
            found = find_anchors(problem, solution[3], time.perf_counter() + remaining() * 0.25, rng)
            if found is not None and found[1] > covered:
                anchored = DayProblem(board, state, steps, problem.hubs, allowance, following, beta)
                anchored.legs, anchored.values, anchored.coverages = problem.legs, problem.values, problem.coverages
                anchored.anchors, anchored.alpha = found[0], alpha
                trial = None
                for variant in variants:
                    result = construct(anchored, variant, deadline)
                    if result is not None and (trial is None or result[0] > trial[0]):
                        trial = result
                if trial is not None:
                    trial = improve(anchored, trial, time.perf_counter() + remaining() * 0.5, rng)
                    old_key = solution[0][:2] + (covered,)
                    new_key = trial[0][:2] + (anchored.coverage(trial[3]),)
                    if new_key > old_key:
                        problem, solution = anchored, trial
    _, _, _, runs = improve(problem, solution, deadline, rng)
    return commands(problem, runs, {car: hub for car, hub in option})
