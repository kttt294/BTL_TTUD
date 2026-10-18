"""Dựng ảnh từ PDF do Word xuất và lập danh sách trang cần xem kỹ."""

import json
import argparse
from pathlib import Path
import sys

from pdf2image import convert_from_path
from PIL import Image, ImageDraw
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--pdf", default="scratch/word_report_review/report.pdf")
parser.add_argument("--folder", default="scratch/word_report_review")
args = parser.parse_args()
folder = ROOT / args.folder
folder.mkdir(parents=True, exist_ok=True)
pdf = ROOT / args.pdf
poppler = Path(sys.executable).parent.parent / "native/poppler/Library/bin"
pages = convert_from_path(str(pdf), dpi=120, poppler_path=str(poppler))
texts = [page.extract_text() for page in PdfReader(pdf).pages]
(folder / "report.txt").write_text("\n\f\n".join(texts), encoding="utf-8")
for i, page in enumerate(pages, 1):
    page.save(folder / f"page-{i:02d}.png")
for start in range(0, len(pages), 6):
    sheet = Image.new("RGB", (1100, 3 * 800), "#dddddd")
    draw = ImageDraw.Draw(sheet)
    for index in range(start, min(start + 6, len(pages))):
        page = pages[index].copy()
        page.thumbnail((535, 760))
        x, y = ((index - start) % 2) * 550, ((index - start) // 2) * 800
        draw.text((x + 12, y + 6), f"Page {index + 1}", fill="black")
        sheet.paste(page, (x + 8, y + 30))
    sheet.save(folder / f"overview-{start // 6 + 1}.png")
targets = [i + 1 for i, text in enumerate(texts) if any(t in text for t in [
    "Mục lục", "9.5 Kết quả", "Cận nguồn", "Cận tiếp", "10.4 Chạy", "Kiểm chứng hai đội hình"])]
(folder / "review_pages.json").write_text(json.dumps({"pages": len(pages), "targets": targets}), encoding="utf-8")
print("Pages:", len(pages), "Detailed targets:", targets)
