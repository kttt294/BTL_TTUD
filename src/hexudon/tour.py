"""Lập tuyến cả đội trong một ngày: chèn điểm tham lam, tìm kiếm lân cận và chia nhiên liệu.

Mỗi xe tuần tra có một dãy điểm udon; chặng giữa hai điểm là đường ngắn nhất theo một
trọng số step/nhiên liệu. Đội không có xe tiếp tế được chia nhiên liệu theo tỷ lệ step còn
lại của trận. Đội có xe tiếp tế đặt mỗi xe tiếp tế ở một điểm hẹn trong ngày; xe tuần tra
tự rẽ vào điểm hẹn khi không đủ nhiên liệu cho chặng tiếp theo và đường quay về.
"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
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

    def __init__(self, board, traffic, spot_set, penalty=None):
        self.board, self.spot_set, self.penalty = board, spot_set, penalty
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
            cost, nbrs, penalty = self.cost, self.nbrs, self.penalty
            while heap:
                d, u = heapq.heappop(heap)
                if d > dist[u]:
                    continue
                su, fu = cost[u]
                # Phạt chỉ đổi đường được chọn; số bước và nhiên liệu vẫn theo chi phí thật.
                nd, ns, nf = d + a * su + b * fu + (penalty[u] if penalty else 0), steps[u] + su, fuel[u] + fu
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
            # Ô ở vùng tách rời không có nút cha; không truy vết từ chỉ số -1.
            if start != goal and parent[goal] == -1:
                self.legs[key] = INF, INF, frozenset()
                return self.legs[key]
            spots, pos = [], goal
            while pos != start:
                if pos in self.spot_set:
                    spots.append(pos)
                pos = parent[pos]
            self.legs[key] = steps[goal], fuel[goal], frozenset(spots)
        return self.legs[key]

    def directions(self, start, goal, variant):
        _, _, parent, pdir = self.tree(start, variant)
        if start != goal and parent[goal] == -1:
            raise ValueError("Không có đường đi giữa hai ô thuộc các vùng tách rời.")
        reverse, pos = [], goal
        while pos != start:
            reverse.append(pdir[pos])
            pos = parent[pos]
        return reverse[::-1]


class DayProblem:
    def __init__(self, board, state, steps, hubs, allowance, next_steps=None, legs=None, penalty=None):
        self.board, self.state, self.steps = board, state, steps
        self.next_steps = next_steps
        self.spot_at = {s["pos"]: s for s in board.spots}
        self.legs = legs or Legs(board, state.traffic, set(self.spot_at), penalty)
        self.patrols = [i for i, a in enumerate(state.agents) if a.kind == 0]
        self.hubs = hubs  # danh sách (ô hẹn, step xe tiếp tế tới nơi)
        self.hub_arrival = {}
        for hub, arrival in hubs:
            self.hub_arrival[hub] = min(arrival, self.hub_arrival.get(hub, INF))
        # escort: xe tuần tra có xe tiếp tế đi kèm -> (xe tiếp tế, step xe tiếp tế tới chỗ nó).
        self.escort = {}
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
        if car in self.escort:
            return self.escorted(car, stops, variant, self.escort[car][1])
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
            if t >= self.hub_arrival.get(pos, INF):
                # Dừng ở điểm hẹn khi xe tiếp tế đã tới: simulator đổ đầy bình.
                fuel, refueled = self.limit, True
        if stops and self.hub_arrival.get(pos, INF) <= T:
            # Kết thúc ngày ở điểm hẹn: xe tiếp tế tới trước cuối ngày thì bình đầy.
            fuel, refueled = self.limit, True
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

    def escorted(self, car, stops, variant, arrival):
        """Xe tuần tra chờ xe tiếp tế tới rồi hai xe đi cùng lệnh: cùng tới mỗi ô ở cùng step nên
        xe tuần tra được đổ đầy sau mỗi bước, không giới hạn nhiên liệu."""
        pos = self.state.agents[car].pos
        t, visited = arrival, {pos} if pos in self.spot_at else set()
        segments = [("wait", arrival)] if arrival else []
        for stop in stops:
            leg = self.legs.leg(pos, stop, variant)
            segments.append(("leg", pos, stop, variant))
            t += leg[0]
            visited |= leg[2]
            pos = stop
            if t > self.steps:
                return CarRun(False)
        return CarRun(True, t, self.limit, 0, frozenset(visited), tuple(segments), t / self.steps, pos)

    def score(self, runs):
        counts = Counter(p for run in runs.values() for p in run.visited)
        brands = {self.spot_at[p]["brand"] for p in counts}
        portions = sum(min(c, self.spot_at[p]["stocks"]) for p, c in counts.items())
        new = len(brands - self.state.brands)
        spent = sum(r.spent for r in runs.values())
        steps = sum(r.steps for r in runs.values())
        return new, len(brands), portions, -spent, -steps

    def coverage(self, runs):
        """Số loại tối đa ngày mai theo bản dựng chỉ nhắm loại, giao thông hôm nay làm dự báo."""
        return self.coverage_from(tuple((runs[c].end, runs[c].fuel) for c in self.patrols))

    def coverage_from(self, key):
        if not self.next_steps:
            return 0
        ends = dict(zip(self.patrols, key))
        if key not in self.coverages:
            hubs = iter([hub for hub, _ in self.hubs])
            escorting = {supply: ends[patrol][0] for patrol, (supply, _) in self.escort.items()}
            agents = []
            for car, agent in enumerate(self.state.agents):
                if agent.kind == 0:
                    agents.append(Agent(0, *ends[car]))
                else:
                    agents.append(Agent(1, escorting[car] if car in escorting else next(hubs, agent.pos), 0))
            tomorrow = State(agents, self.state.traffic, set(), day=self.state.day + 1)
            self.coverages[key] = types_coverage(self.board, tomorrow, self.next_steps,
                                                 [(a.pos, 0) for a in agents if a.kind == 1], self.alpha)
        return self.coverages[key]

    @property
    def brand_count(self):
        return len({s["brand"] for s in self.board.spots})


def car_insertions(problem, car, route, variant, current, positions=None):
    """Phương án chèn rẻ nhất cho từng điểm vào tuyến của một xe."""
    legs, T = problem.legs, problem.steps
    positions = positions or PARAMS["positions"]
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
        # Lượt đầu mỗi (phương án, kiểu đường) dựng không nhiễu: trên ngày ngắn bản này thường đủ
        # loại khi bản có nhiễu không tìm ra (2058 ngày 6: 18/18 so với 15–17).
        noise = 0.0 if attempt < len(candidates) * len(variants) else 1.0 + rng.random()
        attempt += 1
        skeleton = construct(problem, variant, deadline, True, rng, noise)
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


# Các mốc gửi kế hoạch của tiến trình con: {"times": [time.time(), ...], "queue": hàng đợi, "seed": số}.
_CHECKPOINT = None


def emit_checkpoint(problem, runs):
    """Tới mỗi mốc thì gửi kế hoạch hiện có về tiến trình chính, rồi tối ưu tiếp."""
    if _CHECKPOINT is None or not _CHECKPOINT["times"] or time.time() < _CHECKPOINT["times"][0]:
        return
    now = time.time()
    while _CHECKPOINT["times"] and _CHECKPOINT["times"][0] <= now:
        _CHECKPOINT["times"].pop(0)
    supply = {car: hub for car, hub in getattr(problem, "option", [])}
    try:
        _CHECKPOINT["queue"].put((_CHECKPOINT["seed"], commands(problem, runs, supply)))
    except Exception:
        pass


def removal_savings(problem, car, route, variant):
    """Số step tiết kiệm được khi bỏ từng điểm khỏi tuyến (chưa tính rẽ tiếp nhiên liệu)."""
    legs = problem.legs
    seq = [problem.state.agents[car].pos] + route
    savings = []
    for i in range(1, len(seq)):
        saved = legs.leg(seq[i - 1], seq[i], variant)[0]
        if i + 1 < len(seq):
            saved += legs.leg(seq[i], seq[i + 1], variant)[0] - legs.leg(seq[i - 1], seq[i + 1], variant)[0]
        savings.append((saved, i - 1))
    return savings


def extended_move(problem, routes, variants, rng, kind=None):
    """Một toán tử mới: đảo đoạn ("reverse"), đổi điểm giữa hai xe ("swap") hoặc bỏ điểm tốn kém
    nhất ("worst"); kind=None thì chọn ngẫu nhiên theo tỷ lệ 4:3:3. False = bỏ qua."""
    cars = [c for c in problem.patrols if routes[c]]
    if not cars:
        return False
    if kind is None:
        kind = rng.choices(("reverse", "swap", "worst"), (4, 3, 3))[0]
    if kind == "reverse":
        car = rng.choice(cars)
        route = routes[car]
        if len(route) < 3:
            return False
        i = rng.randrange(len(route) - 1)
        j = rng.randint(i + 2, min(len(route), i + 8))
        route[i:j] = route[i:j][::-1]
    elif kind == "swap":
        if len(cars) < 2:
            return False
        a, b = rng.sample(cars, 2)
        i, j = rng.randrange(len(routes[a])), rng.randrange(len(routes[b]))
        if routes[a][i] in routes[b] or routes[b][j] in routes[a]:
            return False
        routes[a][i], routes[b][j] = routes[b][j], routes[a][i]
    else:
        car = rng.choice(cars)
        savings = sorted(removal_savings(problem, car, routes[car], variants[car]), reverse=True)
        count = rng.randint(1, min(3, len(savings)))
        for _, index in sorted(savings[:count], key=lambda item: -item[1]):
            del routes[car][index]
    return True


# Tham số tìm kiếm (giá trị mặc định = cấu hình đã kiểm chứng). Các thí nghiệm ghi đè trong tiến
# trình con. OPERATOR_WEIGHTS: xác suất chọn từng toán tử phá; ALNS > 0 bật tự điều chỉnh trọng số
# theo mức thành công (tốc độ học), 0 = giữ cố định.
PARAMS = {"positions": 3, "noise": 0.5, "max_remove": 4, "segment": 4, "alns": 0.0, "escort": True,
          "weights": {"variant_segment": 0.105, "segment": 0.14, "random": 0.455,
                      "reverse": 0.12, "swap": 0.09, "worst": 0.09}}
EXTENDED = ("reverse", "swap", "worst")


def destroy(problem, routes, variants, rng, operator):
    """Áp một toán tử phá; trả False nếu không áp được (bỏ qua vòng này)."""
    if operator in EXTENDED:
        return extended_move(problem, routes, variants, rng, operator)
    if operator == "variant_segment":
        car = rng.choice(problem.patrols)
        variants[car] = rng.randrange(len(VARIANTS))
    stops = [(c, i) for c, r in routes.items() for i in range(len(r))]
    if stops:
        if operator in ("variant_segment", "segment"):
            car = rng.choice(problem.patrols)
            if routes[car]:
                i = rng.randrange(len(routes[car]))
                j = rng.randint(i + 1, min(len(routes[car]), i + PARAMS["segment"]))
                del routes[car][i:j]
        else:
            count = rng.randint(1, min(PARAMS["max_remove"], len(stops)))
            for c, i in sorted(rng.sample(stops, count), key=lambda x: -x[1]):
                del routes[c][i]
    return True


def improve(problem, solution, deadline, rng):
    """Phá và dựng lại: bỏ vài điểm, một đoạn tuyến hoặc đổi kiểu đường của một xe; hoặc đảo đoạn,
    đổi điểm giữa hai xe, bỏ điểm tốn kém nhất; rồi chèn lại có nhiễu, nhận nếu điểm không giảm.
    Toán tử chọn theo PARAMS["weights"]; với PARAMS["alns"] > 0 trọng số tự điều chỉnh (ALNS)."""
    score, routes, variants, runs = solution
    emit_checkpoint(problem, runs)
    weights = dict(PARAMS["weights"])
    names = list(weights)
    gained = {name: 0.0 for name in names}
    used = {name: 0 for name in names}
    rate = PARAMS["alns"]
    rounds = 0
    while time.perf_counter() < deadline and problem.patrols:
        new_routes = {c: list(r) for c, r in routes.items()}
        new_variants = dict(variants)
        operator = rng.choices(names, [weights[n] for n in names])[0]
        if not destroy(problem, new_routes, new_variants, rng, operator):
            continue
        new_runs = {}
        for c in problem.patrols:
            run = problem.run(c, new_routes[c], new_variants[c])
            if not run.feasible:
                if operator in EXTENDED:
                    new_runs = None
                    break
                new_routes[c], run = [], problem.run(c, [], new_variants[c])
            new_runs[c] = run
        if new_runs is None or not all(r.feasible for r in new_runs.values()):
            continue
        insert_greedy(problem, new_routes, new_variants, new_runs, rng, PARAMS["noise"], deadline)
        new_score = problem.score(new_runs)
        used[operator] += 1
        if new_score >= score:
            gained[operator] += 5.0 if new_score > score else 1.0
            score, routes, variants, runs = new_score, new_routes, new_variants, new_runs
        emit_checkpoint(problem, runs)
        rounds += 1
        if rate and rounds % 50 == 0:
            for name in names:
                if used[name]:
                    weights[name] = max(0.02, (1 - rate) * weights[name] + rate * gained[name] / used[name])
                gained[name], used[name] = 0.0, 0
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
    for car, (hub, arrival, *escort) in supply_routes.items():
        pos = problem.state.agents[car].pos
        if hub != pos:
            actions[car].extend(legs.directions(pos, hub, 0))
        if escort:
            # Hộ tống: tới ô của xe tuần tra rồi lặp lại đúng các lệnh của nó sau lượt chờ đầu.
            actions[car].extend(actions[escort[0]][1:] if arrival else actions[escort[0]])
        elif arrival < steps:
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


def fuel_free_types(board, state, steps, legs):
    """Số loại dựng chỉ nhắm loại được khi mọi xe là tuần tra hiện có và nhiên liệu không giới hạn."""
    agents = [Agent(a.kind, a.pos, 10 ** 9 if a.kind == 0 else 0) for a in state.agents]
    relaxed = State(agents, state.traffic, state.brands, day=state.day)
    problem = DayProblem(board, relaxed, steps, [], {i: 10 ** 9 for i in range(len(agents))}, legs=legs)
    result = construct(problem, 0, types_only=True)
    return result[0][1] if result is not None else 0


def allowances(board, state, steps, alpha):
    remaining = sum(board.day_steps[state.day:]) or steps
    share = 1.0 if state.day >= len(board.day_steps) - 1 else min(1.0, alpha * steps / remaining)
    return {i: int(a.fuel * share) for i, a in enumerate(state.agents)}


def spread_anchors(problem, reach, radius):
    """Bộ ô neo rải đều: lần lượt chọn cho mỗi xe ô tới kịp hôm nay làm tăng nhiều nhất số loại
    mới nằm trong `radius` step quanh nó (ước lượng tầm với ngày mai)."""
    legs, covered, anchors = problem.legs, set(), {}
    brand = {p: info["brand"] for p, info in problem.spot_at.items()}
    near = {}
    for car in sorted(problem.patrols, key=lambda c: len(reach[c])):
        best = None
        for spot in reach[car]:
            if spot not in near:
                near[spot] = {brand[q] for q in brand if legs.leg(spot, q, 0)[0] <= radius}
            gain = len(near[spot] - covered), -reach[car][spot].steps
            if best is None or gain > best[0]:
                best = gain, spot
        anchors[car] = best[1]
        covered |= near[best[1]]
    return anchors


def find_anchors(problem, runs, deadline, rng):
    """Tìm ô dừng cuối ngày của từng xe để ngày mai phủ đủ loại, đi ít step nhất.

    Bắt đầu từ vị trí cuối ngày hiện tại và vài bộ ô neo rải đều (bán kính 35/50/70% số step ngày
    mai), leo đồi từ bộ tốt nhất; kẹt lâu thì khởi động lại từ một bộ khởi đầu khác có xáo trộn.
    """
    reach = {}
    # Ô neo: các điểm udon và cả điểm hẹn (kết thúc ngày ở đó thì bình đầy).
    cells = list(problem.spot_at) + [h for h in problem.hub_arrival if h not in problem.spot_at]
    for car in problem.patrols:
        options = {}
        for spot in cells:
            run = problem.run(car, [spot], 0)
            if run.feasible:
                options[spot] = run
        if not options:
            return None
        reach[car] = options

    def key(anchors):
        ends = tuple((a, reach[c][a].fuel) for c, a in anchors.items())
        return problem.coverage_from(ends), -sum(reach[c][a].steps for c, a in anchors.items())

    starts = [{c: runs[c].end if runs[c].end in reach[c] else rng.choice(list(reach[c])) for c in problem.patrols}]
    for share in (0.35, 0.5, 0.7):
        if time.perf_counter() >= deadline:
            break
        starts.append(spread_anchors(problem, reach, share * (problem.next_steps or problem.steps)))
    scored = sorted(((key(a), a) for a in starts), key=lambda item: item[0], reverse=True)
    best, best_anchors = scored[0]
    current, current_key, stale = dict(best_anchors), best, 0
    while time.perf_counter() < deadline and best[0] < problem.brand_count:
        if stale >= 40:
            # Kẹt: quay về một bộ khởi đầu khác rồi xáo trộn một xe.
            current = dict(rng.choice(scored)[1])
            car = rng.choice(problem.patrols)
            current[car] = rng.choice(list(reach[car]))
            current_key, stale = key(current), 0
        trial = dict(current)
        for car in rng.sample(problem.patrols, rng.randint(1, min(2, len(problem.patrols)))):
            trial[car] = rng.choice(list(reach[car]))
        score = key(trial)
        if score >= current_key:
            stale = 0 if score > current_key else stale + 1
            current, current_key = trial, score
            if score > best:
                best, best_anchors = score, dict(trial)
        else:
            stale += 1
    return best_anchors, best[0]


# (ô còn thông, ô sẽ đông, ô sẽ tắc) cho road_penalties; (0, 0, 0) là planner gốc. Dò tham số 28/10
# (Q04, Q01, Q06, 2 seed): bộ phạt nhẹ này hơn bộ (0.3/1/3 ... 2/4/10) ở Q01 (620 so với 611), ngang ở
# Q04/Q06; bộ phạt mạnh hơn kém đi. ROAD_WEIGHTS_FEW dùng khi ít tiến trình.
ROAD_WEIGHTS = [(0, 0, 0), (0.1, 0.5, 1.5), (0.2, 1, 3), (0.3, 1, 3), (0, 1, 4), (0.5, 2, 6)]
ROAD_WEIGHTS_FEW = [(0, 0, 0), (0.2, 1, 3), (0.5, 2, 6)]


def road_penalties(board, state, weights):
    """Phạt chọn đường cho ô đường mà đi qua hôm nay sẽ làm ngày mai đông hoặc tắc.

    weights = (ô còn thông, ô sẽ đông, ô sẽ tắc), tính bằng bước. Mỗi bước xe đứng trên ô đường là một
    lượt; mặt đường ngày mai tính từ lượt của hôm qua và hôm nay. Dùng cho Practice (một đội, ngưỡng
    không chia theo số đội): xe nhà làm tắc trục đường chính nên điểm gần bằng khi mọi đường luôn đông.
    """
    free, busy, jammed = weights
    history = state.road_history[-1] if state.road_history else {}
    penalty = [0.0] * (board.width * board.height)
    for pos in range(len(penalty)):
        if board.terrain(pos) == 1:
            total = history.get(pos, 0) + board.cost(pos, state.traffic)[0]
            penalty[pos] = (jammed if total >= board.jammed_threshold else
                            busy if total >= board.busy_threshold else free)
    return penalty


def plan_tour(board, state, steps, seconds=2.0, alpha=1.0, seed=0, road_weights=None):
    started = time.perf_counter()
    deadline = started + max(0.0, seconds)
    first_deadline = started + max(seconds, 0.5)
    rng = random.Random(seed + 7919 * state.day)
    supplies = [i for i, a in enumerate(state.agents) if a.kind == 1]
    allowance = allowances(board, state, steps, alpha)
    following = board.day_steps[state.day + 1] if state.day + 1 < len(board.day_steps) else None
    penalty = road_penalties(board, state, road_weights) if road_weights and any(road_weights) else None
    base = DayProblem(board, state, steps, [], allowance, following, penalty=penalty)
    options = [[]]
    for car in supplies:
        cands = hub_candidates(board, state, car, base.legs, steps)
        options = [o + [(car, c)] for o in options for c in cands][:12]
    # Đội không có tiếp tế phải tiết kiệm nhiên liệu nên thử cả ba kiểu đường khi dựng.
    variants = (0,) if supplies else (0, 1, 2)
    best, candidates = None, []
    def make(option):
        problem = DayProblem(board, state, steps, [hub for _, hub in option if len(hub) == 2], allowance,
                             following, legs=base.legs)
        problem.escort = {hub[2]: (car, hub[1]) for car, hub in option if len(hub) == 3}
        return problem

    for index, option in enumerate(options):
        problem = make(option)
        for variant in variants:
            # Luôn dựng xong phương án đầu tiên; các phương án sau chỉ dựng khi còn giờ.
            if best is not None and time.perf_counter() >= started + seconds * 0.4:
                break
            # Lượt dựng đầu được ít nhất 0,5 giây để không quá kém khi ngân sách rất nhỏ, nhưng không
            # chạy quá max(ngân sách, 0,5 giây); bị cắt giữa chừng thì tuyến dựng dở vẫn hợp lệ.
            result = construct(problem, variant, first_deadline if best is None else deadline)
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
    # Một bình đầy đi tối đa 2 step mỗi nhiên liệu (đồng bằng), nên 2 × bình < số step nghĩa là
    # một bình không đủ cho cả ngày.
    if (PARAMS["escort"] and supplies and 2 * board.fuel_limit < steps and best[0][0][1] < base.brand_count
            and best[2].patrols and fuel_free_types(board, state, steps, base.legs) > best[0][0][1]):
        # Điểm hẹn vẫn thiếu loại sau khi dựng lại và nhiên liệu là nút thắt (bỏ giới hạn nhiên liệu
        # thì đi được nhiều loại hơn): thử hộ tống (một xe tiếp tế tới chỗ một xe tuần tra rồi đi
        # cùng nó cả ngày, xe tiếp tế khác đứng yên làm điểm hẹn). Chỉ nhận khi đi được nhiều loại
        # hơn: dùng hộ tống để tăng suất làm mất D về sau trên bản đồ nhiều nhiên liệu.
        escort_until = time.perf_counter() + max(0.0, deadline - time.perf_counter()) * 0.3
        escorts = []
        for car in supplies:
            pos = state.agents[car].pos
            for patrol in base.patrols:
                target = state.agents[patrol].pos
                arrival = base.legs.leg(pos, target, 0)[0] if pos != target else 0
                if arrival < steps:
                    escorts.append([(c, (target, arrival, patrol)) if c == car else
                                    (c, (state.agents[c].pos, 0)) for c in supplies])
        escorts.sort(key=lambda o: sum(c[1] for _, c in o))
        tried = []
        for option in escorts:
            if time.perf_counter() >= escort_until:
                break
            problem = make(option)
            result = construct(problem, 0, escort_until)
            if result is not None:
                tried.append((result, option, problem))
        if tried:
            rescue = max(tried, key=lambda item: item[0][0])
            if rescue[0][0][1] < base.brand_count:
                rescue = cover_types(tried, escort_until, rng, (0,), rescue)
            if rescue[0][0][:2] > best[0][0][:2]:
                best = rescue
    solution, option, problem = best
    problem.alpha, problem.option = alpha, option
    if following and problem.patrols:
        # Kiểm tra ngày mai có đi đủ loại từ vị trí cuối ngày không. Nếu thiếu, tìm ô neo cho
        # từng xe rồi lập lại tuyến phải dừng ở ô neo; chỉ nhận khi (loại hôm nay, loại ngày mai)
        # không kém, vì D xếp trên Q.
        remaining = lambda: max(0.0, deadline - time.perf_counter())
        solution = improve(problem, solution, time.perf_counter() + remaining() * 0.3, rng)
        covered = problem.coverage(solution[3])
        if covered < problem.brand_count:
            # Ngày mai ngắn (ít step hơn hôm nay) thì phủ loại khó hơn: dành nhiều thời gian hơn cho ô neo.
            share = 0.4 if following < steps else 0.25
            found = find_anchors(problem, solution[3], time.perf_counter() + remaining() * share, rng)
            if found is not None and found[1] > covered:
                anchored = DayProblem(board, state, steps, problem.hubs, allowance, following, legs=problem.legs)
                anchored.coverages, anchored.option = problem.coverages, option
                anchored.escort = problem.escort
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


_POOL = None


def _pool(workers):
    """Giữ một nhóm tiến trình cho cả trận để không tốn thời gian khởi động mỗi ngày."""
    global _POOL
    if _POOL is None or _POOL._max_workers != workers:
        if _POOL is not None:
            _POOL.shutdown(wait=False, cancel_futures=True)
        _POOL = ProcessPoolExecutor(workers)
    return _POOL


_LEGS = {}


def cached_legs(board, traffic):
    """Cây đường đi theo một mặt đường, dùng lại giữa các lần ước lượng trong cùng ngày."""
    key = id(board), frozenset((p, s) for p, s in traffic.items() if s)
    if key not in _LEGS:
        if len(_LEGS) > 16:
            _LEGS.clear()
        _LEGS[key] = Legs(board, traffic, {s["pos"] for s in board.spots})
    return _LEGS[key]


def types_coverage(board, state, steps, hubs, alpha=1.0):
    """Số loại đi được trong ngày `steps` từ `state`, dựng chỉ nhắm loại."""
    problem = DayProblem(board, state, steps, hubs, allowances(board, state, steps, alpha),
                         legs=cached_legs(board, state.traffic))
    best = 0
    for variant in ((0,) if hubs else (0, 2)):
        result = construct(problem, variant, types_only=True)
        if result is not None:
            best = max(best, result[0][1])
        if best == problem.brand_count:
            break
    return best


def next_coverage(board, state):
    """Số loại ngày tiếp theo đi được từ trạng thái cuối ngày `state` (dựng chỉ nhắm loại),
    với mặt đường simulator dự đoán từ riêng đội mình."""
    if state.day >= len(board.day_steps):
        return 0
    steps = board.day_steps[state.day]
    hubs = [(a.pos, 0) for a in state.agents if a.kind == 1]
    return types_coverage(board, state, steps, hubs)


def plan_tour_parallel(board, state, steps, seconds=2.0, alpha=1.0, workers=8):
    """Chạy nhiều seed song song, chọn theo (U, loại hôm nay, loại ngày mai, số suất).

    Mỗi tiến trình gửi một kế hoạch tạm ở nửa ngân sách; nếu kết quả cuối không kịp về (bản đồ
    quá lớn, máy quá tải) thì dùng kế hoạch tạm tốt nhất thay vì bỏ trống.
    """
    started = time.time()
    session = AnytimeSession(board, state, steps, seconds, seconds * 0.5, workers, alpha)
    if not session.futures:
        # Nhóm tiến trình hỏng hoặc đã đóng: hôm nay chạy một tiến trình, ngày sau tạo lại nhóm.
        return plan_tour(board, state, steps, max(0.0, started + seconds * 0.8 - time.time()), alpha, 0)
    return session.final()


def choose_best(board, state, steps, candidates, limit):
    """Chọn theo (U, loại hôm nay, loại ngày mai ước lượng, số suất) trong các kế hoạch hợp lệ.

    Ước lượng ngày mai tốn thời gian: chỉ xét nhóm có (U, loại hôm nay) cao nhất, theo số suất
    giảm dần, dừng ở kế hoạch đầu tiên đủ loại cho ngày mai hoặc khi quá `limit` (time.time()).
    """
    plans = []
    for actions in candidates:
        checked = simulate_day(board, state, actions, steps)
        if checked.valid:
            after = checked.state
            plans.append(((len(after.brands), after.daily_sum - state.daily_sum,
                           after.portions - state.portions), actions, after))
    if not plans:
        return None
    plans.sort(key=lambda item: item[0], reverse=True)
    top = [item for item in plans if item[0][:2] == plans[0][0][:2]]
    full = len({s["brand"] for s in board.spots})
    best = None
    for (u, d, q), actions, after in top:
        covered = next_coverage(board, after)
        if best is None or (covered, q) > best[0]:
            best = (covered, q), actions
        if covered == full or time.time() > limit:
            break
    return best[1]


def day_bound(board, state):
    """Cận trên điểm ngày (số loại, số suất), bỏ qua nhiên liệu và thứ tự ghé.

    Một điểm chỉ được tính cho những xe tuần tra đi tới nó kịp trong số step của ngày (đường ngắn
    nhất theo giao thông của ngày); số suất ở điểm đó không vượt kho. Đây là điều kiện cần nên
    là cận trên hợp lệ; đạt được nghĩa là kế hoạch tối ưu cho ngày, không cần tìm thêm.
    """
    steps = board.day_steps[state.day]
    legs = cached_legs(board, state.traffic)
    patrols = [a.pos for a in state.agents if a.kind == 0]
    brands, portions = set(), 0
    for spot in board.spots:
        reach = sum(1 for start in patrols if legs.leg(start, spot["pos"], 0)[0] <= steps)
        if reach:
            brands.add(spot["brand"])
            portions += min(spot["stocks"], reach)
    return len(brands), portions


def reaches_bound(board, state, actions):
    checked = simulate_day(board, state, actions, board.day_steps[state.day])
    if not checked.valid:
        return False
    after = checked.state
    return (after.daily_sum - state.daily_sum, after.portions - state.portions) == day_bound(board, state)


_MANAGER = None


def _queue():
    """Hàng đợi dùng chung giữa các tiến trình, tạo một lần cho cả trận."""
    global _MANAGER
    if _MANAGER is None:
        from multiprocessing import Manager
        _MANAGER = Manager()
    return _MANAGER.Queue()


def _ping(value):
    return value


def warm_up(workers):
    """Khởi động sẵn nhóm tiến trình và hàng đợi để ngày 1 không mất vài giây cho việc này."""
    global _POOL
    try:
        pool = _pool(workers)
        list(pool.map(_ping, range(workers)))
        _queue()
        return True
    except Exception:
        _POOL = None
        return False


def _anytime_job(args):
    board, state, steps, until, times, queue, alpha, seed = args
    global _CHECKPOINT
    _CHECKPOINT = {"times": list(times) if isinstance(times, list) else [times], "queue": queue, "seed": seed}
    try:
        return plan_tour(board, state, steps, max(0.0, until - time.time()), alpha, seed)
    finally:
        _CHECKPOINT = None


class AnytimeSession:
    """Một lượt tìm kiếm song song cho cả ngày, cho hai kết quả: bài nộp nhanh và bài cuối.

    Mọi tiến trình chạy tới hết ngân sách; tại mốc nộp nhanh mỗi tiến trình gửi kế hoạch hiện có
    qua hàng đợi rồi tối ưu tiếp, nên bài cuối không phải chạy lại từ đầu.
    """

    def __init__(self, board, state, steps, seconds, quick, workers=8, alpha=1.0, every=0.0):
        self.board, self.state, self.steps, self.workers = board, state, steps, workers
        started = time.time()
        self.until = started + max(0.0, seconds - 0.4 - 0.05 * workers)
        self.quick_at = started + max(0.0, min(quick, seconds) - 0.3 - 0.03 * workers)
        # every > 0: sau bài nhanh, tiến trình con gửi kế hoạch hiện có mỗi `every` giây để tiến
        # trình chính nộp lại ngay khi có bài tốt hơn.
        self.marks = []
        while every > 0 and (self.marks[-1] if self.marks else self.quick_at) + every < self.until:
            self.marks.append((self.marks[-1] if self.marks else self.quick_at) + every)
        # Chỉ chấm kế hoạch mới nhận; giữ vài kế hoạch tốt nhất theo (U, loại hôm nay, suất).
        self.scored, self.top = 0, []
        self.candidates, self.futures, self.queue = [], [], None
        global _POOL
        try:
            self.queue = _queue()
            times = [self.quick_at] + self.marks
            jobs = [(board, state, steps, self.until, list(times), self.queue, alpha, seed)
                    for seed in range(workers)]
            self.futures = [_pool(workers).submit(_anytime_job, job) for job in jobs]
        except Exception:
            _POOL, self.futures = None, []

    def _drain(self):
        while self.queue is not None:
            try:
                _, actions = self.queue.get_nowait()
            except Exception:
                break
            self.candidates.append(actions)

    def quick(self):
        """Kế hoạch tốt nhất tại mốc nộp nhanh (gồm cả tiến trình đã chạy xong sớm)."""
        if not self.futures:
            return None
        while time.time() < self.quick_at + 0.25 and len(self.candidates) < self.workers:
            self._drain()
            if all(f.done() for f in self.futures):
                break
            time.sleep(0.02)
        self._drain()
        early = [f.result() for f in self.futures if f.done() and f.exception() is None and f.result()]
        return choose_best(self.board, self.state, self.steps, self.candidates + early,
                           time.time() + 0.3)

    def _score_new(self, extra=()):
        """Chấm các kế hoạch mới nhận (và `extra`), giữ 4 kế hoạch tốt nhất theo (U, loại, suất)."""
        fresh = self.candidates[self.scored:] + list(extra)
        self.scored = len(self.candidates)
        for actions in fresh:
            checked = simulate_day(self.board, self.state, actions, self.steps)
            if checked.valid:
                after = checked.state
                key = (len(after.brands), after.daily_sum - self.state.daily_sum,
                       after.portions - self.state.portions)
                self.top.append((key, actions))
        self.top = sorted(self.top, key=lambda item: item[0], reverse=True)[:4]

    def best_until(self, moment):
        """Kế hoạch tốt nhất đã nhận được tới mốc `moment` (time.time()), gồm tiến trình đã xong."""
        if not self.futures:
            return None
        while time.time() < min(moment, self.until) + 0.25:
            time.sleep(0.02)
        self._drain()
        done = [f.result() for f in self.futures if f.done() and f.exception() is None and f.result()]
        self._score_new(done)
        return choose_best(self.board, self.state, self.steps, [a for _, a in self.top], time.time() + 0.3)

    def final(self):
        """Kế hoạch tốt nhất khi mọi tiến trình hết ngân sách, so cả với các kế hoạch tạm."""
        global _POOL
        if not self.futures:
            return None
        done, pending = wait(self.futures, timeout=max(0.0, self.until + 0.3 - time.time()))
        for future in pending:
            future.cancel()
        results = []
        for future in done:
            if isinstance(future.exception(), BrokenProcessPool):
                _POOL = None
            if future.exception() is None and future.result() is not None:
                results.append(future.result())
        self._drain()
        self._score_new(results)
        return choose_best(self.board, self.state, self.steps, [a for _, a in self.top],
                           self.until + 0.3 + 0.05 * self.workers)


def plan_key(board, state, actions, after=None, floor=None):
    """Thứ tự so hai kế hoạch cùng ngày: (U, loại hôm nay, loại ngày mai ước lượng, số suất).

    Kết quả trong ngày của đội mình chỉ phụ thuộc lệnh của đội và giao thông cố định của ngày,
    nên simulator tính đúng điểm ngày mà không cần hỏi máy chủ. Trả None nếu kế hoạch lỗi hoặc
    hai thành phần đầu đã kém floor (bỏ qua bước ước lượng ngày mai tốn thời gian).
    """
    if after is None:
        checked = simulate_day(board, state, actions, board.day_steps[state.day])
        if not checked.valid:
            return None
        after = checked.state
    key = (len(after.brands), after.daily_sum - state.daily_sum)
    if floor is not None and key < floor[:2]:
        return None
    return key + (next_coverage(board, after), after.portions - state.portions)
