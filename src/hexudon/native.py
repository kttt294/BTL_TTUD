"""Gọi planner tour bản C++ (native/hexplan.cpp): cùng thuật toán, nhanh hơn, chạy nhiều luồng.

Tiến trình C++ nhận bài toán một ngày qua stdin, chạy mỗi luồng một seed và in kế hoạch tạm tại
các mốc giờ rồi kế hoạch cuối. Python vẫn kiểm tra và chọn kế hoạch bằng simulator; thiếu file
chạy hoặc lỗi thì nơi gọi dùng lại planner Python.
"""

from collections import Counter
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "native" / "hexplan.cpp"
EXE = ROOT / "native" / ("hexplan.exe" if os.name == "nt" else "hexplan")


# Số lần phải dùng bản Python thay cho C++ theo từng chỗ gọi; bộ đo ghi lại, runner in cảnh báo.
FALLBACKS = Counter()


def fallback(where, reason):
    FALLBACKS[where] += 1
    print(f"CẢNH BÁO: {where} bản C++ không dùng được ({reason}); dùng bản Python.", flush=True)


def build(force=False):
    """Biên dịch khi chưa có file chạy hoặc mã nguồn mới hơn; trả True nếu dùng được."""
    if EXE.exists() and not force and EXE.stat().st_mtime >= SOURCE.stat().st_mtime:
        return True
    compiler = shutil.which("g++") or ("C:/msys64/ucrt64/bin/g++.exe" if os.name == "nt" else None)
    if not compiler or not Path(compiler).exists():
        return False
    env = dict(os.environ)
    # g++ của MSYS2 cần thư mục bin của nó trong PATH để chạy cc1plus.
    env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
    command = [compiler, "-O2", "-std=c++20", "-static", "-pthread", "-o", str(EXE), str(SOURCE)]
    result = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.returncode == 0 and EXE.exists()


def available():
    return EXE.exists()


def encode(board, state, steps, until, checks, alpha=1.0, seed=0, workers=1, objective="lookahead"):
    from .tour import PARAMS
    cells = [cell for row in board.cells for cell in row]
    weights = PARAMS["weights"]
    parts = ["HEXPLAN 1", f"{board.width} {board.height}", " ".join(map(str, cells)), str(board.fuel_limit),
             f"{len(board.day_steps)} " + " ".join(map(str, board.day_steps)),
             f"{len(board.spots)} " + " ".join(f"{s['pos']} {s['brand']} {s['stocks']}" for s in board.spots),
             f"{len(state.agents)} " + " ".join(f"{a.kind} {a.pos} {a.fuel}" for a in state.agents)]
    traffic = [(p, s) for p, s in state.traffic.items() if s]
    parts.append(f"{state.day} {len(traffic)} " + " ".join(f"{p} {s}" for p, s in traffic))
    parts.append(f"{len(state.brands)} " + " ".join(map(str, sorted(state.brands))))
    parts.append(f"{steps} {alpha!r} {seed} {workers} {until!r} {len(checks)} " + " ".join(repr(c) for c in checks))
    parts.append(f"{PARAMS['positions']} {PARAMS['noise']!r} {PARAMS['max_remove']} {PARAMS['segment']} "
                 f"{PARAMS['alns']!r} {int(PARAMS['escort'])} " +
                 " ".join(repr(weights[k]) for k in ("variant_segment", "segment", "random", "reverse", "swap", "worst")) +
                 f" {PARAMS['temperature']!r} {int(PARAMS['ktemp'])} {1 if PARAMS['search'] == 'pso' else 0}"
                 f" {int(PARAMS['last_day_free'])}")
    # Cách chọn và lịch sử ô đường: C++ chấm kế hoạch bằng simulator và ước lượng ngày mai như plan_key.
    history = " ".join(f"{len(h)} " + " ".join(f"{p} {c}" for p, c in h.items()) for h in state.road_history)
    parts.append(f"{1 if objective == 'lookahead' else 0} {len(state.road_history)} {history}")
    parts.append(f"{board.busy_threshold!r} {board.jammed_threshold!r}")
    return "\n".join(parts) + "\n"


def signature(actions):
    return tuple(tuple(car) for car in actions)


class NativeRun:
    """Một tiến trình C++ cho một ngày; luồng đọc gom kế hoạch theo mốc ('0', '1', ... hoặc 'F')."""

    def __init__(self, board, state, steps, until, checks, alpha=1.0, seed=0, workers=1, objective="lookahead"):
        self.plans, self.keys, self.done, self.error = [], {}, threading.Event(), None
        self.objective = objective
        self.lock = threading.Lock()
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.process = subprocess.Popen([str(EXE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                        creationflags=flags)
        self.process.stdin.write(encode(board, state, steps, until, checks, alpha, seed, workers, objective))
        self.process.stdin.close()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            stream = self.process.stdout
            for line in stream:
                parts = line.split()
                if not parts:
                    continue
                if parts[0] == "DONE":
                    break
                if parts[0] == "PLAN":
                    tag, seed, cars = parts[1], int(parts[2]), int(parts[3])
                    # File chạy cũ không in khóa: để trống, phiên tự chọn bằng Python.
                    valid, u, d, cov, q = map(int, parts[4:9]) if len(parts) >= 9 else (0, 0, 0, -1, 0)
                    actions = []
                    for _ in range(cars):
                        numbers = list(map(int, stream.readline().split()))
                        actions.append(numbers[1:1 + numbers[0]])
                    # Khóa như tour.plan_key: lookahead (U, loại hôm nay, loại ngày mai, suất), score (U, loại, suất).
                    key = ((u, d, cov, q) if self.objective == "lookahead" else (u, d, q)) if valid else None
                    with self.lock:
                        self.plans.append((tag, seed, actions))
                        if key is not None and (self.objective != "lookahead" or cov >= 0):
                            self.keys[signature(actions)] = key
        except Exception as error:  # Lỗi đọc không được làm hỏng ngày thi: nơi gọi tự dự phòng.
            self.error = error
        finally:
            self.done.set()

    def tagged(self, tag):
        with self.lock:
            return [actions for t, _, actions in self.plans if t == tag]

    def count(self, tag):
        with self.lock:
            return sum(1 for t, _, _ in self.plans if t == tag)

    def wait(self, timeout):
        finished = self.done.wait(max(0.0, timeout))
        if finished or self.process.poll() is not None:
            return finished
        return False

    def close(self):
        """Dừng tiến trình (kế hoạch đã đọc vẫn giữ), đợi luồng đọc xong rồi đóng ống dẫn."""
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()
        self.reader.join(1.0)
        for stream in (self.process.stdout, self.process.stderr):
            try:
                stream.close()
            except Exception:
                pass


def plan_tour(board, state, steps, seconds=2.0, alpha=1.0, seed=0):
    """Một luồng, chỉ lấy kế hoạch cuối (như tour.plan_tour); None nếu lỗi."""
    until = time.time() + max(0.0, seconds)
    run = NativeRun(board, state, steps, until, [], alpha, seed, 1)
    # Lượt dựng đầu được ít nhất 0,5 giây như bản Python.
    run.wait(max(seconds, 0.5) + 0.5)
    run.close()
    plans = run.tagged("F")
    return plans[0] if plans else None


class NativeSession:
    """Giống tour.AnytimeSession nhưng các seed chạy trong một tiến trình C++ nhiều luồng."""

    def __init__(self, board, state, steps, seconds, quick, workers=8, alpha=1.0, every=0.0,
                 seed=0, objective="lookahead"):
        if workers < 1 or objective not in ("score", "lookahead", "rollout"):
            raise ValueError("Cần ít nhất một luồng và cách chọn score, lookahead hoặc rollout.")
        self.board, self.state, self.steps, self.workers = board, state, steps, workers
        self.seeds = list(range(seed, seed + workers))
        self.objective = objective
        self.valid_count = self.invalid_count = 0
        self.started = time.perf_counter()
        started = time.time()
        # Tiến trình C++ khởi động nhanh nên chừa ít hơn bản nhiều tiến trình Python.
        self.until = started + max(0.0, seconds - 0.3)
        self.quick_at = started + max(0.0, min(quick, seconds) - 0.2)
        self.marks = []
        while every > 0 and (self.marks[-1] if self.marks else self.quick_at) + every < self.until:
            self.marks.append((self.marks[-1] if self.marks else self.quick_at) + every)
        self.times = [self.quick_at] + self.marks
        self.top, self.scored = [], set()
        try:
            self.run = NativeRun(board, state, steps, self.until, self.times, alpha, seed, workers,
                                 objective if objective != "rollout" else "lookahead")
            self.futures = [self.run]  # để nơi gọi kiểm tra "có phiên chạy" như AnytimeSession
        except Exception:
            self.run, self.futures = None, []

    def _tag_at(self, moment):
        tags = [str(i) for i, t in enumerate(self.times) if t <= moment + 1e-6]
        return tags[-1] if tags else None

    def _score(self, plans):
        from .simulator import simulate_day
        for actions in plans:
            key = id(actions)
            if key in self.scored:
                continue
            self.scored.add(key)
            checked = simulate_day(self.board, self.state, actions, self.steps)
            if checked.valid:
                self.valid_count += 1
                after = checked.state
                score = (len(after.brands), after.daily_sum - self.state.daily_sum,
                         after.portions - self.state.portions)
                self.top.append((score, actions))
            else:
                self.invalid_count += 1
        self.top = sorted(self.top, key=lambda item: item[0], reverse=True)[:4]

    def key_of(self, actions):
        """Khóa C++ của một kế hoạch đã nhận (tra theo nội dung lệnh), None nếu chưa có."""
        if not self.run or actions is None:
            return None
        with self.run.lock:
            return self.run.keys.get(signature(actions))

    def _choose(self, plans):
        """Kế hoạch có khóa C++ cao nhất mà simulator Python xác nhận hợp lệ."""
        from .simulator import simulate_day
        from .tour import choose_best
        if plans and all(self.key_of(a) is None for a in plans):
            fallback("chọn kế hoạch", "kế hoạch không kèm khóa C++")
            return choose_best(self.board, self.state, self.steps, plans, time.time() + 0.3, self.objective)
        ranked = sorted(((self.key_of(a), i, a) for i, a in enumerate(plans) if self.key_of(a) is not None),
                        key=lambda item: (item[0], -item[1]), reverse=True)
        for _, _, actions in ranked:
            if simulate_day(self.board, self.state, actions, self.steps).valid:
                self.valid_count += 1
                return actions
            self.invalid_count += 1
        return None

    def quick(self):
        from .tour import choose_best
        if not self.run:
            return None
        while time.time() < self.quick_at + 0.3 and self.run.count("0") < self.workers:
            if self.run.done.is_set():
                break
            time.sleep(0.01)
        plans = self.run.tagged("0") + self.run.tagged("F")
        if self.objective != "rollout":
            return self._choose(plans)
        return choose_best(self.board, self.state, self.steps, plans, time.time() + 0.3, self.objective)

    def best_until(self, moment):
        from .tour import choose_best
        if not self.run:
            return None
        tag = self._tag_at(min(moment, self.until))
        while time.time() < min(moment, self.until) + 0.3:
            if self.run.done.is_set() or (tag is not None and self.run.count(tag) >= self.workers):
                break
            time.sleep(0.01)
        with self.run.lock:
            plans = [actions for _, _, actions in self.run.plans]
        if self.objective != "rollout":
            return self._choose(plans)
        self._score(plans)
        return choose_best(self.board, self.state, self.steps, [a for _, a in self.top],
                           time.time() + 0.3, self.objective)

    def final(self):
        from .tour import choose_best
        if not self.run:
            return None
        self.run.wait(max(0.0, self.until + 0.4 - time.time()))
        self.run.close()
        with self.run.lock:
            plans = [actions for _, _, actions in self.run.plans]
        if self.objective != "rollout":
            chosen = self._choose(plans)
            # Giữ vài kế hoạch tốt nhất cho bước beam (rollout) và thống kê.
            self.top = [(self.key_of(a), a) for a in plans if self.key_of(a) is not None]
            self.top = sorted(self.top, key=lambda item: item[0], reverse=True)[:4]
            return chosen
        self._score(plans)
        return choose_best(self.board, self.state, self.steps, [a for _, a in self.top],
                           self.until + 0.3 + 0.02 * self.workers, self.objective)

    def details(self, actions):
        from .simulator import simulate_day
        checked = simulate_day(self.board, self.state, actions, self.steps) if actions else None
        finals = self.run.count("F") if self.run else 0
        return {"workers": self.workers, "seeds": self.seeds, "objective": self.objective, "native": True,
                "finished_workers": finals, "failed_workers": self.workers - finals, "pending_workers": 0,
                "valid_candidates": self.valid_count, "invalid_candidates": self.invalid_count,
                "selected_score": list(checked.state.score()) if checked and checked.valid else None,
                "elapsed": time.perf_counter() - self.started}


def _board_text(board):
    cells = [cell for row in board.cells for cell in row]
    return "\n".join([f"{board.width} {board.height}", " ".join(map(str, cells)), str(board.fuel_limit),
                      f"{len(board.day_steps)} " + " ".join(map(str, board.day_steps)),
                      f"{len(board.spots)} " + " ".join(f"{s['pos']} {s['brand']} {s['stocks']}" for s in board.spots),
                      f"{board.busy_threshold!r} {board.jammed_threshold!r}"])


def _params_text():
    from .tour import PARAMS
    weights = PARAMS["weights"]
    return (f"{PARAMS['positions']} {PARAMS['noise']!r} {PARAMS['max_remove']} {PARAMS['segment']} "
            f"{PARAMS['alns']!r} {int(PARAMS['escort'])} " +
            " ".join(repr(weights[k]) for k in ("variant_segment", "segment", "random", "reverse", "swap", "worst")) +
            f" {PARAMS['temperature']!r} {int(PARAMS['ktemp'])} {1 if PARAMS['search'] == 'pso' else 0}"
            f" {int(PARAMS['last_day_free'])}")


def simulate_native(board, state, actions, steps, exe=None):
    """Một ngày bằng simulator C++ (để đối chiếu với simulator.py): (vị trí, nhiên liệu, điểm, giao thông) hoặc None."""
    history = " ".join(f"{len(h)} " + " ".join(f"{p} {c}" for p, c in h.items()) for h in state.road_history)
    traffic = [(p, s) for p, s in state.traffic.items() if s]
    text = "\n".join(["HEXSIM 1", _board_text(board),
                      f"{len(state.agents)} " + " ".join(f"{a.kind} {a.pos} {a.fuel}" for a in state.agents),
                      f"{state.day} {len(traffic)} " + " ".join(f"{p} {s}" for p, s in traffic),
                      f"{len(state.brands)} " + " ".join(map(str, sorted(state.brands))),
                      f"{state.daily_sum} {state.portions} {len(state.road_history)} {history}",
                      str(steps)] + [f"{len(car)} " + " ".join(map(str, car)) for car in actions]) + "\n"
    out = subprocess.run([str(exe or EXE)], input=text, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=30).stdout.split()
    if not out or out[0] != "OK":
        return None
    bar = out.index("|")
    cars = list(map(int, out[1:bar]))
    score = tuple(map(int, out[bar + 1:bar + 4]))
    traffic = {int(p): int(s) for p, s in (item.split(":") for item in out[bar + 5:])}
    return [(cars[i], cars[i + 1]) for i in range(0, len(cars), 2)], score, traffic


def select_types(board, seconds, candidates, threads=14, exe=None):
    """Chọn đội hình bằng mô phỏng cả trận trong C++ (nhiều luồng, loại dần, cùng seed mỗi vòng).

    Trả (đội hình, các lần mô phỏng) hoặc None nếu lỗi để nơi gọi dùng bộ chọn Python.
    """
    started = time.time()
    # Chừa khoảng 1 giây cho khởi động và đọc kết quả; vòng đầu (mọi đội hình) dùng khoảng 30% thời gian.
    usable = max(0.5, seconds - 1.0)
    waves = -(-len(candidates) // max(1, threads))
    day_seconds = min(0.5, max(0.02, usable * 0.3 / (waves * len(board.day_steps))))
    text = "\n".join(["HEXSELECT 1", _board_text(board), f"{len(board.starts)} " + " ".join(map(str, board.starts)),
                      f"{len(candidates)}"] + [" ".join(map(str, kinds)) for kinds in candidates] +
                     [f"{threads} {started + usable!r} {day_seconds!r}", _params_text()]) + "\n"
    try:
        result = subprocess.run([str(exe or EXE)], input=text, capture_output=True, text=True, encoding="utf-8",
                                errors="replace",
                                timeout=max(1.0, seconds + 2.0),
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except (OSError, subprocess.TimeoutExpired):
        return None
    records, best = [], None
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] == "RESULT":
            c, seed, u, d, q, complete = map(int, parts[1:])
            records.append({"types": list(candidates[c]), "seed": seed, "score": (u, d, q),
                            "complete": bool(complete), "day_seconds": day_seconds, "phase": "native"})
        elif parts and parts[0] == "BEST":
            best = list(candidates[int(parts[1])])
    if best is None or not any(r["complete"] for r in records):
        return None
    return best, records
