"""Tổng hợp số liệu gốc thành các bảng có thể dùng trong báo cáo."""

import csv
import json
from pathlib import Path
import statistics
import sys


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "experiments" / "results"


def read_rows(name):
    with (RESULTS / name).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def mean(rows, key):
    return statistics.mean(float(row[key]) for row in rows)


def main():
    paths, matches = read_rows("pathfinding.csv"), read_rows("matches.csv")
    validations = read_rows("validation.csv")
    stress = read_rows("validation_stress.csv")
    metadata = json.loads((RESULTS / "metadata.json").read_text(encoding="utf-8"))
    lines = ["# Kết quả thực nghiệm", "",
             f"Thí nghiệm chạy trên Python {metadata['python']}, {metadata['platform']}.",
             f"Bộ dữ liệu có {metadata['games_per_size']} bản đồ cho mỗi kích thước, "
             f"seed từ {metadata['seed']}, mỗi bản đồ có ba truy vấn tìm đường.",
             f"Ngân sách mỗi truy vấn và mỗi ngày lập kế hoạch là {metadata['budget_seconds']} giây.", "",
             "## Tìm đường", "",
             "| Cỡ | Thuật toán | Thành công | Dừng do hạn giờ | Thời gian TB ms | Trạng thái TB |",
             "|---|---|---:|---:|---:|---:|"]
    common = {}
    for size in metadata["sizes"]:
        group = [r for r in paths if int(r["size"]) == size]
        keys = {(r["seed"], r["query"]) for r in group}
        common[size] = [key for key in keys
                        if all(r["found"] == "1" for r in group if (r["seed"], r["query"]) == key)]
        for algorithm in ("dfs", "bfs", "dijkstra", "greedy", "astar"):
            rows = [r for r in group if r["algorithm"] == algorithm]
            success = sum(int(r["found"]) for r in rows)
            cutoff = sum(int(r["cutoff"]) for r in rows)
            lines.append(f"| {size} | {algorithm} | {success}/{len(rows)} | {cutoff} | "
                         f"{mean(rows, 'seconds') * 1000:.3f} | {mean(rows, 'expanded'):.1f} |")
    lines += ["", "### Chi phí trên cùng truy vấn thành công", "",
              "Bảng sau chỉ giữ truy vấn mà cả năm thuật toán đều tìm được đường trong hạn giờ.", "",
              "| Cỡ | Số truy vấn chung | Thuật toán | Bước TB | Nhiên liệu TB | Số cạnh TB |",
              "|---|---:|---|---:|---:|---:|"]
    for size in metadata["sizes"]:
        for algorithm in ("dfs", "bfs", "dijkstra", "greedy", "astar"):
            rows = [r for r in paths if int(r["size"]) == size and r["algorithm"] == algorithm
                    and (r["seed"], r["query"]) in common[size]]
            if rows:
                lines.append(f"| {size} | {len(rows)} | {algorithm} | {mean(rows, 'steps'):.2f} | "
                             f"{mean(rows, 'fuel'):.2f} | {mean(rows, 'hops'):.2f} |")
    lines += ["", "## Kế hoạch toàn trận", "",
              "Mỗi trận có bốn ngày, 80 step/ngày, nhiên liệu tối đa 40 và đội hình [0,0,0,1].", "",
              "| Cỡ | Chiến lược | Loại toàn trận TB | Tổng loại ngày TB | Tổng phần TB | Thời gian trận TB s | Hợp lệ | Dự phòng |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for size in metadata["sizes"]:
        for strategy in ("greedy", "lookahead"):
            rows = [r for r in matches if int(r["size"]) == size and r["strategy"] == strategy]
            lines.append(f"| {size} | {strategy} | {mean(rows, 'unique'):.2f} | {mean(rows, 'daily'):.2f} | "
                         f"{mean(rows, 'portions'):.2f} | {mean(rows, 'planning_seconds'):.3f} | "
                         f"{sum(int(r['valid']) for r in rows)}/{len(rows)} | "
                         f"{sum(int(r['fallbacks']) for r in rows)} |")
    lines += ["", "### So sánh theo cặp seed", "",
              "Thắng/hòa/thua của Lookahead được tính theo bộ ba điểm, không theo riêng tổng phần.", "",
              "| Cỡ | Lookahead thắng | Hòa | Lookahead thua |", "|---|---:|---:|---:|"]
    outcomes = {}
    for size in metadata["sizes"]:
        win = tie = loss = 0
        rows = [r for r in matches if int(r["size"]) == size]
        for seed in sorted({r["seed"] for r in rows}):
            scores = {r["strategy"]: tuple(int(r[k]) for k in ("unique", "daily", "portions"))
                      for r in rows if r["seed"] == seed}
            win += scores["lookahead"] > scores["greedy"]
            tie += scores["lookahead"] == scores["greedy"]
            loss += scores["lookahead"] < scores["greedy"]
        outcomes[size] = [win, tie, loss]
        lines.append(f"| {size} | {win} | {tie} | {loss} |")
    lines += ["", "## Thời gian bộ kiểm tra", "",
              "| Cỡ | Số kế hoạch | Trung vị ms | Lớn nhất ms | Hợp lệ |",
              "|---|---:|---:|---:|---:|"]
    for size in metadata["sizes"]:
        rows = [r for r in validations if int(r["size"]) == size]
        timings = [float(r["seconds"]) * 1000 for r in rows]
        lines.append(f"| {size} | {len(rows)} | {statistics.median(timings):.3f} | {max(timings):.3f} | "
                     f"{sum(int(r['valid']) for r in rows)}/{len(rows)} |")
    lines += ["", "### Phép đo bổ sung trên bản đồ 32×32", "",
              "Mỗi cấu hình lặp 30 lần với kế hoạch chờ toàn ngày; phép đo này không đại diện mọi lộ trình.", "",
              "| Số xe | Step/ngày | Trung vị ms | Lớn nhất ms |", "|---|---:|---:|---:|"]
    for row in stress:
        lines.append(f"| {row['agents']} | {row['steps']} | {float(row['median_ms']):.3f} | "
                     f"{float(row['max_ms']):.3f} |")
    lines += ["", "## Giới hạn của phép đo", "",
              "Các trận chạy riêng cho từng chiến lược, không phải đối đầu nhiều đội có giao thông chung. "
              "Thời gian là đồng hồ thực trên một máy, có thể bị ảnh hưởng bởi tải hệ thống. "
              "Các seed được tái hiện nhưng quyết định sát hạn giờ có thể thay đổi. "
              "Thí nghiệm không bao gồm huấn luyện hoặc so sánh RL.", ""]
    destination = ROOT / "docs" / "experiment_results.md"
    destination.write_text("\n".join(lines), encoding="utf-8")
    report = ROOT / "docs" / "bao_cao.md"
    if report.exists() and "--update-report" in sys.argv:
        text = report.read_text(encoding="utf-8")
        start, end = "<!-- BANG_KET_QUA -->", "<!-- HET_BANG_KET_QUA -->"
        if end not in text:
            text = text.replace(start, start + "\n" + end)
        headings = {"## Tìm đường": "Kết quả tìm đường",
                    "### Chi phí trên cùng truy vấn thành công": "Chi phí trên các truy vấn chung",
                    "## Kế hoạch toàn trận": "Kết quả toàn trận",
                    "### So sánh theo cặp seed": "Kết quả so sánh theo cặp",
                    "## Thời gian bộ kiểm tra": "Thời gian kiểm tra kế hoạch",
                    "### Phép đo bổ sung trên bản đồ 32×32": "Phép đo kiểm tra bổ sung"}
        tables = []
        for line in lines:
            if line in headings:
                tables += ["", "### " + headings[line], ""]
            elif line.startswith("|"):
                tables.append(line)
        text = text[:text.index(start) + len(start)] + "\n\n" + "\n".join(tables) + "\n\n" + text[text.index(end):]
        report.write_text(text, encoding="utf-8")
    summary = {"matches": len(matches), "path_queries": len(paths), "outcomes": outcomes,
               "valid_plans": sum(int(r["valid"]) for r in validations),
               "plans": len(validations), "fallbacks": sum(int(r["fallbacks"]) for r in matches)}
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
