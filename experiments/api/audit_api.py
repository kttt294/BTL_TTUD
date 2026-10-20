"""Tạo bảng đối chiếu và danh mục bằng chứng API để kiểm tra thủ công."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    directory = ROOT / "experiments/data/api_evidence"
    files = ["q02_comparison", "q03_comparison", "q04_comparison", "q06_comparison",
             "q10_immediate_comparison", "q10_wait_comparison"]
    names = ["Q02 các ca luật", "Q03 toàn trận", "Q04 toàn trận", "Q06 toàn trận",
             "Q10 rời đường ngay", "Q10 chờ trước khi rời đường"]
    cases = []
    for name, filename in zip(names, files):
        row = json.loads((directory / (filename + ".json")).read_text(encoding="utf-8"))
        cases.append({"name": name, "days": len(row["days"]), "frames": row["checked_frames"],
                      "values": row["checked_values"], "mismatches": row["mismatch_count"],
                      "score": row["final_score"], "file": filename + ".json"})
    summary = {"date_local": "2026-10-19", "timezone": "Asia/Bangkok", "cases": cases,
               "frames_including_shared_prefixes": sum(row["frames"] for row in cases),
               "checked_values": sum(row["values"] for row in cases),
               "mismatches": sum(row["mismatches"] for row in cases),
               "note": "Hai biến thể Q10 có chung ngày đầu, không phải mẫu độc lập."}
    (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = []
    for path in sorted(directory.glob("*.json")):
        if path.name == "manifest.json":
            continue
        manifest.append({"file": path.name, "bytes": path.stat().st_size,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = ["# Kết quả đối chiếu simulator với API BTC", "",
             "Ngày đối chiếu: 19/10/2026, tài khoản đội 62, chỉ dùng chế độ luyện tập riêng.", "",
             "| Bộ replay | Ngày | Frame | Giá trị so sánh | Sai khác |",
             "|---|---:|---:|---:|---:|"]
    for row in cases:
        lines.append(f"| {row['name']} | {row['days']} | {row['frames']} | {row['values']} | {row['mismatches']} |")
    lines += ["", f"Tổng số frame được kiểm tra là {summary['frames_including_shared_prefixes']}; "
              "ngày đầu Q10 được tính trong cả hai biến thể, nên không coi tổng này là số mẫu độc lập.",
              "Mỗi frame được so vị trí, nhiên liệu, số phần trong ngày, số loại trong ngày và sự kiện thu thập. "
              "Giao thông dự đoán được so với đầu ngày tiếp theo khi replay có ngày đó.", "",
              "| Output sai | HTTP máy chủ | Kết luận |", "|---|---:|---|"]
    for name, label in [("q02_invalid_command", "Mã hướng ngoài miền"),
                        ("q02_invalid_too_many_steps", "Vượt quỹ step"),
                        ("q02_invalid_pond", "Đi vào ao"), ("q06_invalid_fuel", "Thiếu nhiên liệu")]:
        record = json.loads((directory / (name + ".json")).read_text(encoding="utf-8"))
        lines.append(f"| {label} | {record['status']} | Máy chủ từ chối |")
    lines += ["", "## Điểm truy cập và bằng chứng", "",
              "Tài liệu công khai: https://hexudon.hairbui76.id.vn/docs . "
              "Schema gốc: https://hexudon.hairbui76.id.vn/openapi.json .", "",
              "Các JSON gốc nằm tại `experiments/data/api_evidence`; request không chứa header Authorization. "
              "Mỗi bản ghi có thời điểm UTC, endpoint, tham số, body, HTTP status và phản hồi. "
              "Danh mục SHA-256 nằm tại `manifest.json`. Hàm băm giúp nhận biết tệp thay đổi, "
              "không phải chữ ký xác nhận của BTC.", "",
              "Các so sánh trên xác minh một đội trong những bản luyện tập đã thử. "
              "Phần nhiều đội mới có kiểm thử nội bộ, chưa có replay đối chiếu từ BTC. "
              "Kết quả không chứng minh simulator đúng trong mọi trường hợp và không phải chứng nhận của BTC.", ""]
    (directory / "audit_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
