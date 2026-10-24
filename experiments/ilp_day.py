"""ILP/CP-SAT cho bài toán một ngày: cận trên và lời giải để so với tour (nhánh test).

Mô hình (OR-Tools CP-SAT): mỗi xe tuần tra một chu trình qua ô xuất phát và các điểm udon được chọn
(AddCircuit, điểm không ghé là vòng tự lặp, quay về ô xuất phát không tốn step nên tuyến là đường
mở); thời gian tới mỗi điểm theo đường nhanh nhất của ngày, không vượt quỹ step. Đi ngang một điểm
tương đương ghé nó (bất đẳng thức tam giác) nên mô hình bao cả trường hợp đó. Bỏ qua nhiên liệu nên
giá trị tối ưu là cận trên của điểm ngày (loại mới, loại hôm nay, suất).

Lời giải CP-SAT được chuyển qua DayProblem.run (tự rẽ tiếp nhiên liệu ở điểm hẹn) rồi kiểm tra bằng
simulator; khả thi thì đó là một kế hoạch thật, so được trực tiếp với tour.

python -X utf8 experiments/ilp_day.py --cases Q01 Q03 --seconds 30
"""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ortools.sat.python import cp_model
from hexudon import tour
from hexudon.model import Board, State
from hexudon.simulator import simulate_day

EVIDENCE = ROOT / "experiments/data/tour_api_evidence"
MOCK = ROOT / "results/mock_contest/configs"


def solve_day(board, state, steps, seconds=30.0, workers=8, hint=None):
    """Trả (cận trên, giá trị tốt nhất, tuyến từng xe tuần tra, trạng thái lời giải)."""
    legs = tour.cached_legs(board, state.traffic)
    patrols = [i for i, a in enumerate(state.agents) if a.kind == 0]
    spots = board.spots
    brands = sorted({s["brand"] for s in spots})
    model = cp_model.CpModel()
    visit = {}   # (xe, chỉ số điểm) -> bool
    order = {}   # (xe, chỉ số điểm) -> thời gian tới
    for car in patrols:
        start = state.agents[car].pos
        reach = [i for i, s in enumerate(spots) if legs.leg(start, s["pos"], 0)[0] <= steps]
        arcs = []
        nodes = [None] + reach  # nút 0 là ô xuất phát
        times = {0: 0}
        for n, i in enumerate(reach, 1):
            visit[car, i] = model.NewBoolVar("")
            times[n] = model.NewIntVar(0, steps, "")
            order[car, i] = times[n]
            arcs.append((n, n, visit[car, i].Not()))
        for a, i in enumerate(nodes):
            for b, j in enumerate(nodes):
                if a == b:
                    continue
                if b == 0:
                    arcs.append((a, 0, model.NewBoolVar("")))  # kết thúc tuyến, không tốn step
                    continue
                src = start if i is None else spots[i]["pos"]
                d = legs.leg(src, spots[j]["pos"], 0)[0]
                if d > steps:
                    continue
                lit = model.NewBoolVar("")
                arcs.append((a, b, lit))
                if a == 0:
                    model.Add(times[b] >= d).OnlyEnforceIf(lit)
                else:
                    model.Add(times[b] >= times[a] + d).OnlyEnforceIf(lit)
        if not reach:
            continue
        model.AddCircuit(arcs)
    covered_brand, portions, new_brands = [], [], []
    for i, s in enumerate(spots):
        lits = [visit[c, i] for c in patrols if (c, i) in visit]
        if not lits:
            continue
        p = model.NewIntVar(0, s["stocks"], "")
        model.Add(p <= sum(lits))
        portions.append(p)
    for b in brands:
        lits = [visit[c, i] for c in patrols for i, s in enumerate(spots) if s["brand"] == b and (c, i) in visit]
        if not lits:
            continue
        z = model.NewBoolVar("")
        model.AddBoolOr(lits).OnlyEnforceIf(z)
        covered_brand.append(z)
        if b not in state.brands:
            new_brands.append(z)
    big = sum(s["stocks"] for s in spots) + 1
    model.Maximize(big * (len(brands) + 1) * sum(new_brands) + big * sum(covered_brand) + sum(portions))
    if hint:
        for (car, i), var in visit.items():
            model.AddHint(var, i in hint.get(car, ()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_workers = workers
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    routes = {}
    for car in patrols:
        chosen = [(solver.Value(order[car, i]), i) for i in range(len(spots))
                  if (car, i) in visit and solver.Value(visit[car, i])]
        routes[car] = [spots[i]["pos"] for _, i in sorted(chosen)]
    def unpack(value):
        value = int(round(value))
        new, rest = divmod(value, big * (len(brands) + 1))
        brand, portion = divmod(rest, big)
        return new, brand, portion
    return unpack(solver.BestObjectiveBound()), unpack(solver.ObjectiveValue()), routes, solver.StatusName(status)


def plan_from_routes(board, state, steps, routes):
    """Biến tuyến CP-SAT thành lệnh: điểm hẹn = xe tiếp tế đứng yên, xe tuần tra tự rẽ tiếp nhiên liệu."""
    supplies = [i for i, a in enumerate(state.agents) if a.kind == 1]
    option = [(car, (state.agents[car].pos, 0)) for car in supplies]
    problem = tour.DayProblem(board, state, steps, [hub for _, hub in option],
                              tour.allowances(board, state, steps, 1.0), legs=tour.cached_legs(board, state.traffic))
    runs = {}
    for car in problem.patrols:
        route = list(routes.get(car, []))
        run = problem.run(car, route, 0)
        while not run.feasible and route:
            route.pop()  # thiếu nhiên liệu/thời gian khi thêm đường rẽ: bỏ dần điểm cuối
            run = problem.run(car, route, 0)
        if not run.feasible:
            return None
        runs[car] = run
    return tour.commands(problem, runs, {car: hub for car, hub in option})


def config_path(name):
    path = EVIDENCE / f"{name}_config.json"
    return path if path.exists() else MOCK / f"{name}.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="+", default=["Q01", "Q03", "Q04", "Q06", "Q07", "Q08", "Q09", "Q10"])
    parser.add_argument("--seconds", type=float, default=30.0, help="Thời gian CP-SAT mỗi ngày")
    parser.add_argument("--tour-seconds", type=float, default=5.0)
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--native", action="store_true", help="tour chạy bản C++")
    args = parser.parse_args()
    tour.PARAMS["native"] = args.native
    summary = json.loads((EVIDENCE / "summary.json").read_text(encoding="utf8"))
    kinds_of = {s["case"]: s["types"] for s in summary}
    rows = []
    for name in args.cases:
        board = Board.from_dict(json.loads(config_path(name).read_text(encoding="utf8")))
        kinds = kinds_of.get(name) or [int(i == 0) for i in range(len(board.starts))]
        state = State.initial(board, kinds)
        for day, steps in enumerate(board.day_steps[:args.days]):
            started = time.perf_counter()
            actions = tour.plan_tour(board, state, steps, args.tour_seconds, seed=0)
            tour_after = simulate_day(board, state, actions, steps).state
            tour_score = (len(tour_after.brands - state.brands), tour_after.daily_sum - state.daily_sum,
                          tour_after.portions - state.portions)
            result = solve_day(board, state, steps, args.seconds)
            ilp_plan = ilp_score = None
            if result:
                bound, value, routes, status = result
                plan = plan_from_routes(board, state, steps, routes)
                if plan:
                    checked = simulate_day(board, state, plan, steps)
                    if checked.valid:
                        a = checked.state
                        ilp_score = (len(a.brands - state.brands), a.daily_sum - state.daily_sum, a.portions - state.portions)
            row = {"case": name, "day": day + 1, "steps": steps, "tour": tour_score,
                   "bound": result[0] if result else None, "cpsat": result[1] if result else None,
                   "status": result[3] if result else None, "cpsat_plan": ilp_score,
                   "seconds": round(time.perf_counter() - started, 1)}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            state = tour_after
    out = ROOT / "results/ilp_day.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf8")
    gaps = [r["bound"][2] - r["tour"][2] for r in rows if r["bound"] and r["bound"][:2] == r["tour"][:2]]
    print(f"Ngày có cận: {len(gaps)}; tour đạt cận suất ở {sum(g == 0 for g in gaps)} ngày; "
          f"thiếu TB {sum(gaps) / max(1, len(gaps)):.2f} suất/ngày")


if __name__ == "__main__":
    main()
