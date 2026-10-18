"""Đối chiếu output đã xuất với lịch sử thực tế trên máy chủ BTC."""

import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hexudon.api import CompetitionAPI


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rl_mode = "--rl" in sys.argv
    api = CompetitionAPI(evidence_dir="experiments/rl_branch_evidence" if rl_mode else "experiments/legacy_branch_evidence")
    results = json.loads((api.directory / "summary.json").read_text(encoding="utf-8"))
    output = ROOT / ("output/rl_branch_evaluation" if rl_mode else "output/legacy_branch_evaluation")
    output.mkdir(parents=True, exist_ok=True)
    lines = ["| Bài | Loại toàn trận | Tổng loại theo ngày | Tổng suất |", "|---|---:|---:|---:|"]
    verified = 0
    for result in results:
        question = result["question"]
        if "error" in result:
            raise ValueError(result)
        cached = api.directory / (question + "_final_actions.json")
        record = json.loads(cached.read_text(encoding="utf-8")) if cached.exists() else {}
        if record.get("status") == 200:
            history = record["response"]
        else:
            time.sleep(0.3)
            history = api.get("/api/game/actions", result["game_id"], question + "_final_actions")
        actual = {a["day"]: a["plan"] for a in history["actions"] if str(a["team_id"]) == "62"}
        expected = [json.loads(line) for line in (api.directory / (question + "_output.txt")).read_text().splitlines()]
        assert len(actual) == len(expected) == 10
        assert all(actual[day] == plan for day, plan in enumerate(expected))
        server = json.loads((api.directory / (question + "_result.json")).read_text())["response"]["detail"]["62"]
        assert result["score"] == [server["distinct_types"], server["cumulative_daily_types"], server["total_servings"]]
        verified += len(expected)
        shutil.copyfile(api.directory / (question + "_output.txt"), output / (question + "_output.txt"))
        lines.append("| " + question + " | " + " | ".join(map(str, result["score"])) + " |")
    lines.insert(6, "| Q05 | Không có trong danh sách | — | — |")
    maximum = max(d["planning_seconds"] for r in results for d in r["days"])
    audit = {"verified_days": verified, "server_plan_mismatches": 0,
             "score_mismatches": 0, "max_planning_seconds": maximum,
             "checkpoint": "episode_256.pt" if rl_mode else None,
             "rl_evaluated": rl_mode, "unavailable_questions": ["Q05"]}
    if rl_mode:
        audit["rl_candidates"] = sum("rl_targets" in day for r in results for day in r["days"])
        audit["rl_selected_days"] = sum(day["mode"] == "rl" for r in results for day in r["days"])
    (api.directory / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    shutil.copyfile(api.directory / "summary.json", output / "summary.json")
    text = "\n".join(lines) + f"\n\nMáy chủ đã nhận và lưu đúng {verified} kế hoạch ngày. Thời gian lập kế hoạch lớn nhất: {maximum:.3f} giây, không gồm truyền mạng.\n"
    document = ROOT / ("docs/rl_branch_evaluation.md" if rl_mode else "docs/legacy_branch_evaluation.md")
    report = document.read_text(encoding="utf-8")
    marker = "\n## Kết quả máy chủ\n"
    report = report.split(marker)[0] + marker + "\n" + text
    if rl_mode:
        shutil.copyfile(api.directory / "model_metadata.json", output / "model_metadata.json")
        baseline = {r["question"]: r["score"] for r in json.loads(
            (ROOT / "experiments/legacy_branch_evidence/summary.json").read_text(encoding="utf-8"))}
        comparison = ["\n## So sánh với lượt Greedy/Lookahead trước đó\n",
                      "| Bài | Greedy/Lookahead | RL kết hợp Greedy | So sánh |",
                      "|---|---|---|---|"]
        counts = {"Tốt hơn": 0, "Kém hơn": 0, "Bằng nhau": 0}
        for result in results:
            before, after = baseline[result["question"]], result["score"]
            verdict = "Tốt hơn" if after > before else "Kém hơn" if after < before else "Bằng nhau"
            counts[verdict] += 1
            comparison.append(f"| {result['question']} | {tuple(before)} | {tuple(after)} | {verdict} |")
        comparison.append(f"\nTrong 90 ngày, mô hình đã tạo {audit['rl_candidates']} ứng viên; bộ chọn đã dùng RL cho {audit['rl_selected_days']} ngày. Các ngày còn lại dùng Greedy.\n")
        comparison.append(f"Theo thứ tự ưu tiên ba thành phần điểm, lượt RL kết hợp Greedy tốt hơn ở {counts['Tốt hơn']} bài, kém hơn ở {counts['Kém hơn']} bài và bằng nhau ở {counts['Bằng nhau']} bài. Thống kê này bao gồm hai nhãn Q01/Q02 có input trùng nhau. Đây là so sánh hai cấu hình hoàn chỉnh, không tách riêng tác động của chính sách RL và các heuristic hỗ trợ.\n")
        report += "\n".join(comparison)
    document.write_text(report, encoding="utf-8")
    (output / "README.md").write_text(report, encoding="utf-8")
    print(text)
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
