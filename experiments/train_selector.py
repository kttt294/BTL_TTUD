"""Học model chọn đội hình từ dữ liệu composition_labels.py và đánh giá trên bản đồ giữ riêng (nhánh test).

Mỗi mẫu là một cặp (bản đồ, đội hình). Nhãn gộp các seed như bộ chọn: U thấp nhất, D thấp nhất, Q trung
bình; so với đội hình tốt nhất cùng bản đồ: mất D và % Q mất. Hai model LightGBM: dự đoán mất D và % Q
mất; chọn đội hình có (mất D dự đoán, % Q mất dự đoán) nhỏ nhất. Cây quyết định nông cho quy tắc đọc
được về số xe tiếp tế. Model xuất ra JSON để runner tính bằng Python thuần.

python -X utf8 experiments/train_selector.py --labels "results/labels/*.jsonl" --out src/hexudon/selector_model.json
"""

import argparse
import glob
import json
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.selector import FEATURES, row_features


def load(pattern):
    maps, seen = [], set()
    for path in sorted(glob.glob(str(ROOT / pattern) if not Path(pattern).is_absolute() else pattern)):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row["profile"], row["seed"])
            if key in seen:
                continue
            seen.add(key)
            cands = []
            for c in row["candidates"]:
                runs = [r for r in c["runs"] if r[4]]
                if not runs:
                    continue
                cands.append({"types": c["types"], "features": c["features"],
                              "u": min(r[1] for r in runs), "d": min(r[2] for r in runs),
                              "q": statistics.mean(r[3] for r in runs),
                              "q0": runs[0][3], "d0": runs[0][2], "u0": runs[0][1]})
            if len(cands) >= 2:
                best = max(cands, key=lambda c: (c["u"], c["d"], c["q"]))
                for c in cands:
                    c["d_loss"] = (best["u"] - c["u"]) * 1000 + (best["d"] - c["d"])
                    c["q_regret"] = 100.0 * (best["q"] - c["q"]) / max(1.0, best["q"])
                maps.append({"profile": row["profile"], "seed": row["seed"], "features": row["features"], "cands": cands})
    return maps


def matrix(maps):
    X, yd, yq, groups = [], [], [], []
    for i, m in enumerate(maps):
        for c in m["cands"]:
            X.append(row_features(m["features"], c["features"]))
            yd.append(min(c["d_loss"], 50))
            yq.append(c["q_regret"])
            groups.append(i)
    return X, yd, yq, groups


def evaluate(maps, choose):
    """Đội hình được chọn trên mỗi bản đồ: số bản đồ mất D, tổng D mất, % Q mất TB, tỷ lệ trúng tốt nhất."""
    picks = [choose(m) for m in maps]
    return {"maps": len(maps), "d_loss_maps": sum(p["d_loss"] > 0 for p in picks),
            "d_loss": sum(p["d_loss"] for p in picks), "q_regret": statistics.mean(p["q_regret"] for p in picks),
            "best": sum(p["d_loss"] == 0 and p["q_regret"] == 0 for p in picks)}


def central(m):
    """Quy tắc: 1 xe tiếp tế ở vị trí trung tâm nhất (supply_rank_min = 0)."""
    single = [c for c in m["cands"] if c["features"]["supplies"] == 1 and c["features"]["supply_rank_min"] == 0]
    return single[0] if single else m["cands"][0]


def one_run(m):
    """Như mô phỏng ngắn: chọn theo đúng một trận (seed đầu) của mỗi đội hình."""
    return max(m["cands"], key=lambda c: (c["u0"], c["d0"], c["q0"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default="results/labels/*.jsonl")
    parser.add_argument("--holdout", type=float, default=0.2)
    parser.add_argument("--out", default=str(ROOT / "src/hexudon/selector_model.json"))
    args = parser.parse_args()
    import lightgbm as lgb
    from sklearn.tree import DecisionTreeClassifier, export_text
    maps = load(args.labels)
    rng = random.Random(0)
    rng.shuffle(maps)
    cut = int(len(maps) * (1 - args.holdout))
    train, test = maps[:cut], maps[cut:]
    print(f"{len(maps)} bản đồ: học {len(train)}, giữ riêng {len(test)}")
    X, yd, yq, _ = matrix(train)
    params = dict(n_estimators=300, learning_rate=0.05, num_leaves=31, min_child_samples=20, subsample=0.8,
                  subsample_freq=1, colsample_bytree=0.8, verbose=-1)
    model_d = lgb.LGBMRegressor(**params).fit(X, yd)
    model_q = lgb.LGBMRegressor(**params).fit(X, yq)

    def learned(m):
        rows = [row_features(m["features"], c["features"]) for c in m["cands"]]
        pd, pq = model_d.predict(rows), model_q.predict(rows)
        floor = min(pd)
        # Ưu tiên không mất D: chỉ xét đội hình có mất D dự đoán gần mức thấp nhất, rồi lấy % Q mất nhỏ nhất.
        best = min((i for i in range(len(rows)) if pd[i] <= floor + 0.3), key=lambda i: pq[i])
        return m["cands"][best]

    report = {}
    for name, split in (("học", train), ("giữ riêng", test)):
        for label, fn in (("quy tắc trung tâm", central), ("một trận mỗi đội hình", one_run), ("model", learned)):
            report[f"{name} | {label}"] = evaluate(split, fn)
    for prof in ("btc", "wide", "mix"):
        part = [m for m in test if m["profile"] == prof]
        if part:
            for label, fn in (("quy tắc trung tâm", central), ("một trận mỗi đội hình", one_run), ("model", learned)):
                report[f"giữ riêng {prof} | {label}"] = evaluate(part, fn)
    for k, v in report.items():
        print(f"{k:45} mất D ở {v['d_loss_maps']:3}/{v['maps']} bản đồ (tổng {v['d_loss']}), "
              f"% Q mất TB {v['q_regret']:.2f}, trúng tốt nhất {v['best']}")
    # Quy tắc đọc được: số xe tiếp tế của đội hình tốt nhất theo đặc trưng bản đồ.
    names = list(train[0]["features"])
    Xm = [[m["features"][k] for k in names] for m in train]
    ym = [min(m["cands"], key=lambda c: (c["d_loss"], c["q_regret"]))["features"]["supplies"] for m in train]
    tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=20).fit(Xm, ym)
    print("Quy tắc số xe tiếp tế (cây độ sâu 3):")
    print(export_text(tree, feature_names=names))
    Path(args.out).write_text(json.dumps({"features": FEATURES, "loss": model_d.booster_.dump_model(),
                                          "regret": model_q.booster_.dump_model(), "margin": 0.3,
                                          "report": report}), encoding="utf-8")
    print("Đã ghi", args.out)


if __name__ == "__main__":
    main()
