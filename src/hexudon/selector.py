"""Model chọn đội hình: đặc trưng bản đồ/đội hình và tính model LightGBM (xuất JSON) bằng Python thuần.

Học bằng experiments/train_selector.py trên dữ liệu experiments/composition_labels.py. Khi thi chỉ cần
thư viện chuẩn: rank() xếp các đội hình ứng viên theo (mất D dự đoán, % Q mất dự đoán).
"""

import json
from pathlib import Path
import statistics

MODEL = Path(__file__).resolve().parent / "selector_model.json"


def map_features(board):
    """Đặc trưng bản đồ: kích thước, xe, điểm, nhiên liệu so với độ dài ngày, địa hình, độ phân tán."""
    cells = [c for row in board.cells for c in row]
    size = len(cells)
    spots = [s["pos"] for s in board.spots]
    steps = board.day_steps
    spread = statistics.mean(board.distance(a, b) for a in spots for b in spots if a != b) if len(spots) > 1 else 0
    return {
        "width": board.width, "height": board.height, "cars": len(board.starts), "spots": len(spots),
        "brands": len({s["brand"] for s in board.spots}), "stocks": sum(s["stocks"] for s in board.spots),
        "days": len(steps), "steps_mean": statistics.mean(steps), "steps_min": min(steps), "steps_max": max(steps),
        "fuel": board.fuel_limit, "fuel_per_step": board.fuel_limit / statistics.mean(steps),
        "plain": cells.count(0) / size, "road": cells.count(1) / size, "mountain": cells.count(2) / size,
        "pond": cells.count(3) / size, "spot_spread": spread,
        "busy": board.busy_threshold, "jammed": board.jammed_threshold,
    }


def composition_features(board, kinds):
    """Đặc trưng đội hình: số xe tiếp tế, độ trung tâm của xe tiếp tế và xe tuần tra so với các điểm."""
    spots = [s["pos"] for s in board.spots]
    centrality = [statistics.mean(board.distance(p, q) for q in spots) for p in board.starts]
    order = sorted(range(len(board.starts)), key=lambda i: centrality[i])
    rank = {car: r for r, car in enumerate(order)}
    supplies = [i for i, k in enumerate(kinds) if k == 1]
    patrols = [i for i, k in enumerate(kinds) if k == 0]
    return {
        "supplies": len(supplies),
        "supply_rank_min": min((rank[i] for i in supplies), default=-1),
        "supply_rank_mean": statistics.mean(rank[i] for i in supplies) if supplies else -1,
        "supply_centrality": statistics.mean(centrality[i] for i in supplies) if supplies else -1,
        "patrol_centrality": statistics.mean(centrality[i] for i in patrols) if patrols else -1,
        "supply_gap": (min(board.distance(board.starts[a], board.starts[b]) for a in supplies for b in supplies if a < b)
                       if len(supplies) > 1 else -1),
    }


MAP_KEYS = ["width", "height", "cars", "spots", "brands", "stocks", "days", "steps_mean", "steps_min", "steps_max",
            "fuel", "fuel_per_step", "plain", "road", "mountain", "pond", "spot_spread", "busy", "jammed"]
COMP_KEYS = ["supplies", "supply_rank_min", "supply_rank_mean", "supply_centrality", "patrol_centrality", "supply_gap"]
# Đặc trưng ghép: một bình đi tối đa 2 step mỗi nhiên liệu, nên steps/(2 × bình) là số bình cần mỗi ngày;
# match_tanks ≤ 1 nghĩa là một bình đủ cả trận (đội toàn tuần tra không bao giờ được đổ xăng).
FEATURES = MAP_KEYS + COMP_KEYS + ["tanks_per_day", "patrols", "supply_share", "spots_per_patrol",
                                   "total_steps", "match_tanks", "area", "spot_density"]


def row_features(map_f, comp_f):
    patrols = map_f["cars"] - comp_f["supplies"]
    total = map_f["steps_mean"] * map_f["days"]
    area = map_f["width"] * map_f["height"]
    extra = [map_f["steps_mean"] / (2.0 * map_f["fuel"]), patrols, comp_f["supplies"] / map_f["cars"],
             map_f["spots"] / max(1, patrols), total, total / (2.0 * map_f["fuel"]), area, map_f["spots"] / area]
    return [float(map_f[k]) for k in MAP_KEYS] + [float(comp_f[k]) for k in COMP_KEYS] + extra


def _tree_value(node, x):
    while "leaf_value" not in node:
        value = x[node["split_feature"]]
        node = node["left_child"] if value <= node["threshold"] else node["right_child"]
    return node["leaf_value"]


def _predict(model, x):
    return sum(_tree_value(tree["tree_structure"], x) for tree in model["tree_info"])


_LOADED = None


def load():
    global _LOADED
    if _LOADED is None and MODEL.exists():
        _LOADED = json.loads(MODEL.read_text(encoding="utf-8"))
    return _LOADED


def rank(board, candidates):
    """Xếp đội hình theo model (tốt nhất trước); None nếu chưa có model."""
    model = load()
    if model is None or model.get("features") != FEATURES:
        return None
    map_f = map_features(board)
    scored = []
    for kinds in candidates:
        x = row_features(map_f, composition_features(board, kinds))
        scored.append((_predict(model["loss"], x), _predict(model["regret"], x), kinds))
    floor = min(s[0] for s in scored)
    # Ưu tiên không mất D: đội hình có mất D dự đoán gần mức thấp nhất đứng trước, trong nhóm xếp theo % Q mất.
    return [k for _, _, k in sorted(scored, key=lambda s: (s[0] > floor + model.get("margin", 0.3), s[1]))]
