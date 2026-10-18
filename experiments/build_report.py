"""Xuất báo cáo PDF từ bản Markdown, không ảnh hưởng mã thuật toán."""

import csv
from html import escape
from pathlib import Path
import re
import statistics

from reportlab.lib import colors
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderSVG
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, Preformatted,
                               SimpleDocTemplate, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = Path("C:/Windows/Fonts")


def register_fonts():
    for name, filename in [("Report", "times.ttf"), ("Report-Bold", "timesbd.ttf"),
                           ("Report-Italic", "timesi.ttf"), ("Report-BoldItalic", "timesbi.ttf")]:
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
    pdfmetrics.registerFontFamily("Report", normal="Report", bold="Report-Bold",
                                 italic="Report-Italic", boldItalic="Report-BoldItalic")
    pdfmetrics.registerFont(TTFont("Code", str(FONT_DIR / "consola.ttf")))


def make_chart():
    with (ROOT / "experiments/results/matches.csv").open(encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    drawing = Drawing(470, 255)
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 48, 45, 390, 160
    chart.data = [[statistics.mean(float(r["portions"]) for r in rows
                                  if int(r["size"]) == size and r["strategy"] == strategy)
                   for size in (8, 16, 32)] for strategy in ("greedy", "lookahead")]
    chart.categoryAxis.categoryNames = ["8 x 8", "16 x 16", "32 x 32"]
    chart.categoryAxis.labels.fontName = "Report"
    chart.categoryAxis.labels.fontSize = 10
    chart.valueAxis.labels.fontName = "Report"
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 160
    chart.valueAxis.valueStep = 40
    chart.bars[0].fillColor = colors.HexColor("#34576f")
    chart.bars[1].fillColor = colors.HexColor("#b88844")
    chart.barWidth, chart.groupSpacing = 11, 18
    chart.valueAxis.gridStrokeColor = colors.HexColor("#dddddd")
    chart.valueAxis.visibleGrid = True
    drawing.add(String(48, 230, "Tổng phần udon trung bình mỗi trận", fontName="Report-Bold", fontSize=12))
    drawing.add(chart)
    drawing.add(Rect(105, 12, 10, 9, fillColor=colors.HexColor("#34576f"), strokeColor=None))
    drawing.add(String(120, 12, "Greedy", fontName="Report", fontSize=10))
    drawing.add(Rect(235, 12, 10, 9, fillColor=colors.HexColor("#b88844"), strokeColor=None))
    drawing.add(String(250, 12, "Lookahead hai điểm", fontName="Report", fontSize=10))
    return drawing


class ReportDocument(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ("Chapter", "Section"):
            level = 0 if flowable.style.name == "Chapter" else 1
            title = flowable.getPlainText()
            key = "heading-" + str(self.seq.nextf("heading"))
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, level, False)
            if level == 0:
                self.notify("TOCEntry", (0, title, self.page, key))


def inline(text):
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    return text


def main():
    register_fonts()
    report_title = (ROOT / "docs/bao_cao.md").read_text(encoding="utf-8").splitlines()[0][2:]
    output = ROOT / "output/pdf"
    output.mkdir(parents=True, exist_ok=True)
    body = ParagraphStyle("Body", fontName="Report", fontSize=11.5, leading=16,
                          alignment=TA_JUSTIFY, spaceAfter=7, allowWidows=0, allowOrphans=0)
    chapter = ParagraphStyle("Chapter", parent=body, fontName="Report-Bold", fontSize=15,
                             leading=19, spaceBefore=16, spaceAfter=10, keepWithNext=True, alignment=TA_LEFT)
    section = ParagraphStyle("Section", parent=chapter, fontSize=12.5, leading=16,
                             spaceBefore=11, spaceAfter=7)
    small = ParagraphStyle("Cell", parent=body, fontSize=9, leading=12,
                           alignment=TA_LEFT, spaceAfter=0, allowWidows=1, allowOrphans=1)
    code_style = ParagraphStyle("CodeText", fontName="Code", fontSize=8, leading=11,
                                spaceBefore=5, spaceAfter=8, alignment=TA_LEFT)
    title_style = ParagraphStyle("ReportTitle", fontName="Report-Bold", fontSize=21,
                                 leading=31, alignment=TA_CENTER, spaceAfter=20)
    center = ParagraphStyle("Centered", parent=body, alignment=TA_CENTER, fontSize=12, leading=18)
    caption = ParagraphStyle("Caption", parent=body, alignment=TA_CENTER, fontSize=10, leading=14)
    story = []
    story.append(Spacer(1, 90))
    story.append(Paragraph("BÁO CÁO BÀI TẬP LỚN", center))
    story.append(Paragraph("MÔN THUẬT TOÁN ỨNG DỤNG", center))
    story.append(Spacer(1, 35))
    story.append(Paragraph(report_title, title_style))
    story.append(Paragraph("Bài toán HEXUDON của Procon Việt Nam 2026", center))
    story.append(Spacer(1, 38))
    story.append(Paragraph("Thuật toán đồ thị và tìm kiếm có giới hạn tài nguyên", center))
    story.append(Spacer(1, 95))
    story.append(Paragraph("Tháng 10 năm 2026", center))
    story.append(PageBreak())
    story.append(Paragraph("Mục lục", title_style))
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("TOC0", fontName="Report-Bold", fontSize=11,
                                      leading=16, spaceBefore=5),
                       ParagraphStyle("TOC1", fontName="Report", fontSize=10,
                                      leading=13, leftIndent=14)]
    story.append(toc)
    story.append(PageBreak())
    lines = (ROOT / "docs/bao_cao.md").read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        if not line or line.startswith("<!--") or line.startswith("# "):
            continue
        if line.startswith("BÁO CÁO") or line.startswith("Đề tài được xây dựng"):
            continue
        if line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), chapter))
        elif line.startswith("### "):
            story.append(Paragraph(inline(line[4:]), section))
        elif line.startswith("```"):
            commands = []
            while index < len(lines) and not lines[index].startswith("```"):
                command = lines[index]
                # Xuống dòng lệnh dài để bản in không tràn lề.
                while len(command) > 91:
                    split = command.rfind(" ", 0, 91)
                    split = split if split > 0 else 90
                    commands.append(command[:split])
                    command = "    " + command[split:].lstrip()
                commands.append(command)
                index += 1
            index += 1
            story.append(Preformatted("\n".join(commands), code_style))
        elif line.startswith("|"):
            rows = [line]
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(lines[index].strip())
                index += 1
            cells = [[cell.strip() for cell in row.strip("|").split("|")]
                     for row in rows if not re.fullmatch(r"[| :\-]+", row)]
            column_count = len(cells[0])
            if column_count == 8:
                widths = [25, 65, 55, 65, 55, 100, 55, 55]
            elif column_count == 6:
                widths = [28, 70, 75, 95, 100, 107]
            elif column_count == 5:
                widths = ([160, 40, 70, 100, 105] if cells[0][0] == "Bộ replay"
                          else [40, 110, 105, 110, 110])
            elif column_count == 4:
                widths = [55, 140, 140, 140]
            elif column_count == 3:
                widths = [195, 140, 140]
            else:
                widths = [475 / column_count] * column_count
            table_data = [[Paragraph(inline(cell), small) for cell in row] for row in cells]
            table = Table(table_data, colWidths=widths, repeatRows=1, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6edf1")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.extend([table, Spacer(1, 10)])
        elif line.startswith("!["):
            chart = make_chart()
            figure = [chart, Paragraph("Hình 1 So sánh số phần udon trong cùng ngân sách tính toán", caption)]
            if story and isinstance(story[-1], Paragraph) and story[-1].style.name == "Section":
                figure.insert(0, story.pop())
            story.append(KeepTogether(figure))
        else:
            paragraph = line
            while index < len(lines) and lines[index].strip() and not lines[index].startswith(("#", "|", "```", "<!--", "![")):
                paragraph += " " + lines[index].strip()
                index += 1
            story.append(Paragraph(inline(paragraph), body))

    def footer(canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setFont("Report", 9)
            canvas.drawCentredString(A4[0] / 2, 27, str(doc.page))
        canvas.restoreState()

    doc = ReportDocument(str(output / "bao_cao_hexudon.pdf"), pagesize=A4,
                         leftMargin=60, rightMargin=60, topMargin=48, bottomMargin=48,
                         title=report_title, author="")
    doc.multiBuild(story, onFirstPage=footer, onLaterPages=footer)
    figures = ROOT / "docs/figures"
    figures.mkdir(exist_ok=True)
    renderSVG.drawToFile(make_chart(), str(figures / "portions.svg"))
    print(output / "bao_cao_hexudon.pdf")


if __name__ == "__main__":
    main()
