"""Dựng báo cáo tập trung vào thuật toán, theo bản sao mẫu NLP của người dùng."""

from copy import deepcopy
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import sys

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageOps
from report_problem_sections import intro, problem_model, search_table, planning_table, rl_table
from report_table_headers import apply_readable_headers
from report_rl_appendix import restructure_rl
from report_quality_sections import add_method, add_protocol, add_results, add_reproduction

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "scratch/algorithm_rewrite"
REFERENCE = Path("C:/Users/trang/Desktop/NLP_BTL/docs/BaoCao_BTL.docx")
EXPECTED_HASH = "ead2a52dbb22a3a5f0a7d382222b90b4dc0fbc6078e67b4241bbacdbc79e7a61"
assert hashlib.sha256(REFERENCE.read_bytes()).hexdigest() == EXPECTED_HASH
old = Document(TMP / "report_before.docx")
doc = Document(REFERENCE)
title = next(p.text for p in old.paragraphs if p.style.name == "Title")
teams = json.loads((ROOT / "experiments/team_selection_results/summary.json").read_text(encoding="utf-8"))
rl = json.loads((ROOT / "experiments/rl_branch_evidence/summary.json").read_text(encoding="utf-8"))
baseline = {r["question"]: r for r in json.loads((ROOT / "experiments/legacy_branch_evidence/summary.json").read_text(encoding="utf-8"))}
metadata = json.loads((ROOT / "experiments/rl_branch_evidence/model_metadata.json").read_text(encoding="utf-8"))
bounds = {r["case"]: r for r in json.loads((ROOT / "experiments/team_selection_results/upper_bounds.json").read_text(encoding="utf-8"))}
verified = json.loads((ROOT / "experiments/team_selection_api_evidence/summary.json").read_text(encoding="utf-8"))


def clean_run(run, size=12.5):
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0, 0, 0)
    fonts = run._r.get_or_add_rPr().get_or_add_rFonts()
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn("w:" + key), "Times New Roman")
    for key in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        fonts.attrib.pop(qn("w:" + key), None)


def para(text="", bold=False, center=False, style=None):
    p = doc.add_paragraph(text, style)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.3
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.widow_control = True
    for run in p.runs:
        clean_run(run)
        if bold:
            run.bold = True
    return p


def heading(text, level=1):
    p = para(text, bold=True, style=f"Heading {level}")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(12 if level == 1 else 8)
    return p


def section(text, level=1):
    return heading(text, level)


def figure(filename, caption, width=15):
    p = para()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(ROOT / 'docs/figures' / filename), width=Cm(width))
    p = para(caption, center=True)
    p.paragraph_format.keep_together = True


def table(caption, headers, values, widths=None, size=11):
    p = para(caption, bold=True)
    p.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    widths = widths or [16 / len(headers)] * len(headers)
    for column, width in zip(t.columns, widths):
        column.width = Cm(width)
    for cell, text in zip(t.rows[0].cells, headers):
        cell.text = str(text)
    repeat = OxmlElement("w:tblHeader")
    t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for values_row in values:
        for cell, text in zip(t.add_row().cells, values_row):
            cell.text = str(text)
    for index, row in enumerate(t.rows):
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for cell, width in zip(row.cells, widths):
            cell.width = Cm(width)
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.line_spacing = 1.3
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.keep_with_next = index == 0 or (len(values) <= 10 and index < len(values))
                for run in p.runs:
                    clean_run(run, size)
                    run.bold = index == 0
            margins = OxmlElement("w:tcMar")
            for side in ("top", "left", "bottom", "right"):
                element = OxmlElement("w:" + side)
                element.set(qn("w:w"), "65")
                element.set(qn("w:type"), "dxa")
                margins.append(element)
            cell._tc.get_or_add_tcPr().append(margins)
    para().paragraph_format.space_after = Pt(1)
    return t


def old_text(prefix):
    paragraphs = old.paragraphs
    begin = next(i for i, p in enumerate(paragraphs)
                 if p.style.name.startswith("Heading") and p.text.startswith(prefix))
    result = []
    for p in paragraphs[begin + 1:]:
        if p.style.name.startswith("Heading"):
            break
        if p.text.strip():
            result.append(p.text)
    return result


def reuse(prefix, limit=None):
    for text in old_text(prefix)[:limit]:
        para(text)


def source_table(index):
    return [[c.text for c in row.cells] for row in old.tables[index].rows]


def score(value):
    return "(" + ", ".join(map(str, value)) + ")"


def page_field(p):
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    p._p.append(field)


def new_section(number_format=None):
    s = doc.add_section(WD_SECTION_START.NEW_PAGE)
    s.header.is_linked_to_previous = False
    s.footer.is_linked_to_previous = False
    for part in (s.header, s.footer):
        for child in list(part._element):
            part._element.remove(child)
        part.add_paragraph()
    if number_format:
        page_field(s.footer.paragraphs[0])
        numbering = s._sectPr.find(qn("w:pgNumType"))
        if numbering is None:
            numbering = OxmlElement("w:pgNumType")
            s._sectPr.append(numbering)
        numbering.set(qn("w:fmt"), number_format)
        numbering.set(qn("w:start"), "1")
    return s


# Bản sao tham chiếu giữ phần quan hệ và logo; nội dung NLP được thay hoàn toàn.
cover = [deepcopy(p._p) for p in doc.paragraphs[:15]]
final_section = deepcopy(doc.element.body.sectPr)
for child in list(doc.element.body):
    doc.element.body.remove(child)
doc.element.body.append(final_section)
for style in doc.styles:
    if hasattr(style, "font"):
        style.font.name = "Times New Roman"
        style.font.size = Pt(12.5)
        style.font.color.rgb = RGBColor(0, 0, 0)
        fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
        for key in ("ascii", "hAnsi", "eastAsia", "cs"):
            fonts.set(qn("w:" + key), "Times New Roman")
        for key in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
            fonts.attrib.pop(qn("w:" + key), None)
    if hasattr(style, "paragraph_format"):
        style.paragraph_format.line_spacing = 1.3
        style.paragraph_format.space_after = Pt(6)
for style_name in ("Heading 1", "Heading 2", "Heading 3"):
    doc.styles[style_name].font.bold = True
    doc.styles[style_name].paragraph_format.keep_with_next = True
for style_name in ("TOC 1", "TOC 2", "TOC 3"):
    if style_name not in doc.styles:
        from docx.enum.style import WD_STYLE_TYPE
        doc.styles.add_style(style_name, WD_STYLE_TYPE.PARAGRAPH)
    s = doc.styles[style_name]
    s.font.name = "Times New Roman"
    s.font.size = Pt(12.5)
    s.font.color.rgb = RGBColor(0, 0, 0)
    s.paragraph_format.line_spacing = 1.3
    s.paragraph_format.space_after = Pt(3)

cover_text = {0: "ĐẠI HỌC PHENIKAA", 1: "TRƯỜNG CÔNG NGHỆ THÔNG TIN PHENIKAA",
              3: "BÁO CÁO BÀI TẬP LỚN", 5: "MÔN: THUẬT TOÁN ỨNG DỤNG",
              7: title, 8: "Giảng viên hướng dẫn: TS. Trần Đình Tân",
              9: "24100093 - Kiều Thị Thu Trang - 24100093@st.phenikaa-uni.edu.vn",
              10: "24100012 - Trần Minh Sang - 24100012@st.phenikaa-uni.edu.vn",
              12: "Link Github dự án: https://github.com/kttt294/BTL_TTUD",
              14: "Hà Nội, tháng 10 năm 2026"}
for part in (doc.sections[0].header, doc.sections[0].footer):
    for child in list(part._element):
        part._element.remove(child)
    part.add_paragraph()
from docx.text.paragraph import Paragraph
for index, element in enumerate(cover):
    if index == 4:
        continue
    doc.element.body.insert(len(doc.element.body) - 1, element)
    p = Paragraph(element, doc._body)
    if index in cover_text:
        p.text = cover_text[index]
    if index == 12:
        p.text = "Link Github dự án: "
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("r:id"), doc.part.relate_to("https://github.com/kttt294/BTL_TTUD", RT.HYPERLINK, is_external=True))
        run = OxmlElement("w:r")
        properties = OxmlElement("w:rPr")
        font = OxmlElement("w:rFonts")
        font.set(qn("w:ascii"), "Times New Roman")
        font.set(qn("w:hAnsi"), "Times New Roman")
        properties.append(font)
        size = OxmlElement("w:sz")
        size.set(qn("w:val"), "25")
        properties.append(size)
        color = OxmlElement("w:color")
        color.set(qn("w:val"), "000000")
        properties.append(color)
        run.append(properties)
        value = OxmlElement("w:t")
        value.text = "https://github.com/kttt294/BTL_TTUD"
        run.append(value)
        hyperlink.append(run)
        p._p.append(hyperlink)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.line_spacing = 1.3
    for run in p.runs:
        clean_run(run)
        if index in (0, 1, 3, 5, 7):
            run.bold = True
    if index == 2:
        for blip in p._p.xpath('.//a:blip'):
            part = doc.part.related_parts[blip.get(qn('r:embed'))]
            im = Image.open(BytesIO(part.blob)).convert("RGB")
            data = BytesIO()
            im.save(data, "PNG")
            # Dùng quan hệ ảnh mới để giữ nguyên loại nội dung của ảnh tham chiếu.
            rid, _ = doc.part.get_or_add_image(BytesIO(data.getvalue()))
            blip.set(qn('r:embed'), rid)

new_section("lowerRoman")
para("LỜI MỞ ĐẦU", bold=True, center=True)
para("Đề tài của nhóm sử dụng bài toán Tối ưu hóa lộ trình HEXUDON trong cuộc thi lập trình "
     "Procon Việt Nam 2026, theo đề bài do Ban tổ chức (viết tắt là BTC) cung cấp [1]. "
     "Chúng em chuyển đề thi thành bài tập lớn để nghiên cứu, cài đặt và so sánh các thuật "
     "toán tìm đường và lập kế hoạch cho một đội xe trên bản đồ lục giác có giới hạn nhiên "
     "liệu và thời gian. Bộ mô phỏng và website chấm bài được dùng để kiểm tra kết quả, "
     "còn trọng tâm của báo cáo là cách ứng dụng và đánh giá thuật toán.")
# Người dùng yêu cầu đưa tài khoản vào bản báo cáo gửi giảng viên.
# Đọc từ .env để không ghi thông tin đăng nhập trực tiếp trong mã nguồn.
review_credentials = {}
for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        review_credentials[key.strip()] = value.strip()
website = para("Website tổ chức và chấm bài được nhóm sử dụng: ")
link = OxmlElement('w:hyperlink')
link.set(qn('r:id'), doc.part.relate_to('https://hexudon.hairbui76.id.vn/', RT.HYPERLINK, is_external=True))
link_run = OxmlElement('w:r')
link_text = OxmlElement('w:t')
link_text.text = 'https://hexudon.hairbui76.id.vn/'
link_run.append(link_text)
link.append(link_run)
website._p.append(link)
website.add_run('. Giảng viên có thể truy cập để xem giao diện, các bài Practice và kết quả '
                'thuộc tài khoản nhóm. Thông tin đăng nhập được cung cấp như sau:')
for run in website.runs:
    clean_run(run)
account = para('Tên đăng nhập: ' + review_credentials['HEXUDON_REVIEW_USERNAME'] + '\n'
               'Mật khẩu: ' + review_credentials['HEXUDON_REVIEW_PASSWORD'])
account.alignment = WD_ALIGN_PARAGRAPH.LEFT
account.paragraph_format.keep_together = True
para("Ở lớp tìm đường, nhóm đối chiếu DFS, BFS, Greedy Best-First, Dijkstra và A* trên trạng thái "
     "có tài nguyên. Ở lớp lập kế hoạch, nhóm so sánh Greedy với Lookahead hai điểm và đánh giá "
     "cách chọn vai trò tuần tra hoặc tiếp tế bằng mô phỏng toàn trận. Bộ mô phỏng và bộ kiểm tra "
     "được dùng để tạo điều kiện đối chứng nhất quán; báo cáo nêu rõ phạm vi kiểm chứng API và "
     "phân biệt điểm offline với điểm máy chủ.")
para("Kết quả cho thấy số tầng nhìn trước nhiều hơn không tự bảo đảm chất lượng tốt hơn khi ngân "
     "sách tính toán bị giới hạn. Trong 30 cặp thử nghiệm toàn trận, Lookahead thắng 3 và thua 27 "
     "cặp so với Greedy. Bộ chọn đội hình mới tốt hơn cấu hình toàn tuần tra ở 3 trong 9 nhãn bài "
     "BTC chạy offline và bằng ở 6 bài. Hai đội hình được kiểm chứng trên Practice có điểm khớp "
     "máy chủ qua 2.807 frame. Các cận trên được tính riêng và không được coi là điểm tối ưu đã biết.")
para("Nhóm bổ sung quy hoạch động để tìm nghiệm tối ưu trên 24 bài nhỏ và đo hai heuristic "
     "ở bốn ngân sách thời gian trên 30 input, tạo thêm 240 trận. Các phép đo này làm rõ "
     "khoảng cách tới tối ưu trong phiên bản thu nhỏ và ảnh hưởng của thời gian tính toán.")
para("Phần mở rộng đánh giá checkpoint MAPPO có sẵn, ghi nhận 256 episode, trong kiến trúc RL "
     "chọn mục tiêu và A* tạo tuyến. Cấu hình RL kết hợp Greedy thua Greedy/Lookahead ở cả 9 bài "
     "Practice đã thử. Nhóm chưa huấn luyện mô hình mới trên simulator hiện tại và chưa thực hiện "
     "thí nghiệm tách thành phần để định lượng riêng lợi ích của A*, masking hoặc Greedy đối với RL. "
     "Mọi kết quả chiến lược trong báo cáo đều thuộc phạm vi một đội.")
doc.add_page_break()
para("MỤC LỤC", bold=True, center=True)
p = para()
field = OxmlElement("w:fldSimple")
field.set(qn("w:instr"), 'TOC \\o "1-2" \\h \\z \\u')
p._p.append(field)
new_section("decimal")

section("1. Giới thiệu đề tài")
intro(section, para, table, figure)
section("1.2. Động cơ và câu hỏi nghiên cứu", 2)
para("Một tuyến ngắn chưa đủ để tạo kế hoạch thu thập tốt cho cả đội xe. Xe còn phải chọn điểm "
     "ghé, dành nhiên liệu cho những ngày sau và phối hợp với xe tiếp tế. Chúng em chọn bài toán "
     "này để quan sát trực tiếp cách các thuật toán đồ thị và heuristic tác động tới chất lượng "
     "một hệ thống hoàn chỉnh. Tên đề tài được giữ theo phạm vi môi trường mô phỏng, nhưng các "
     "quyết định thuật toán và bằng chứng thực nghiệm là trọng tâm của báo cáo.")
para("Các câu hỏi chính được đặt ra: A* thay đổi lượng tìm kiếm so với Dijkstra ra sao khi có "
     "ràng buộc nhiên liệu; Lookahead có tăng điểm so với Greedy trong cùng ngân sách hay không; "
     "việc tìm kiếm vai trò xe có tốt hơn đội hình cố định không; và một checkpoint RL kết hợp "
     "các thuật toán này có vượt được đối chứng heuristic hay không. Mỗi câu hỏi được đánh giá "
     "ở đúng lớp quyết định, tránh lấy đường đi ngắn để suy ra điểm toàn trận tối ưu.")
section("1.3. Phạm vi và các sản phẩm đã thực hiện", 2)
para("Nhóm xem xét một đội với nhiều xe hoạt động qua nhiều ngày. Vị trí xuất phát do BTC cho "
     "sẵn, còn vai trò xe được chọn trước trận và giữ cố định. Giao thông trong thực nghiệm được "
     "cập nhật từ lịch sử xe của chính đội mình. Mã simulator có giao diện nhiều đội nhưng phần "
     "đó chỉ có kiểm thử nội bộ; báo cáo không đánh giá chiến lược đối kháng hoặc giao thông do "
     "các tài khoản Practice riêng khác gây ra.")
para("Sản phẩm gồm năm thuật toán tìm đường có xét tài nguyên, hai heuristic lập kế hoạch, bộ "
     "chọn đội hình, bộ tính cận tiếp cận, simulator và validator, các phép đo có lưu input/output "
     "và công cụ đối chiếu API. Phần RL sử dụng bản chụp nhánh Procon2026 và checkpoint có sẵn; "
     "nhóm không trình bày checkpoint này như một mô hình vừa được huấn luyện trên nhánh ttud_clean.")
section("1.4. Cách tổ chức và nguyên tắc đánh giá", 2)
para("Báo cáo đi từ mô hình tối thiểu ở mục 2 đến thuật toán tìm đường ở mục 3, lập kế hoạch và "
     "chọn đội hình ở mục 4, sau đó trình bày ứng dụng hỗ trợ RL ở mục 5. Mục 6 xác định các phép "
     "đối chứng; mục 7 trình bày số liệu và phân tích; mục 8 tổng hợp giới hạn. Chi tiết vận hành "
     "simulator và lệnh chạy được chuyển sang phụ lục để phần chính tập trung vào thuật toán.")

problem_model(section, para, table, figure)

section("3. Các thuật toán tìm đường có ràng buộc tài nguyên")
search_table(table)
section("3.1. Các nhãn trạng thái và quy tắc loại nhãn", 2)
reuse("3.3 ")
para("Trong cài đặt, mỗi ô có thể giữ nhiều nhãn chưa bị trội. Dijkstra và A* mở rộng nhãn theo "
     "chi phí thời gian, còn quan hệ trội đồng thời kiểm tra nhiên liệu. BFS bổ sung số cạnh vào "
     "điều kiện loại nhãn để không phá mục tiêu ít cạnh. Vì vậy, độ phức tạp không thể được báo "
     "cáo chỉ bằng số ô như một bài Dijkstra không ràng buộc tài nguyên. Khi hết hạn, kết quả "
     "được đánh dấu cutoff; đó không phải bằng chứng đích không thể tới.")
figure('resource_labels.png', 'Hình 1. Nhãn tài nguyên tại cùng một ô và quan hệ trội.')
section("3.2. DFS và BFS làm đối chứng cấu trúc", 2)
reuse("4.1 ")
reuse("4.2 ")
para("Hai phương pháp này giúp tách ảnh hưởng của thứ tự duyệt khỏi việc sử dụng trọng số. "
     "BFS chỉ tối ưu số cạnh trong phạm vi trạng thái được tìm đầy đủ, còn DFS không bảo đảm "
     "đường ít cạnh hay ít step. Khi địa hình có chi phí khác nhau, báo cáo không gọi một tuyến "
     "BFS ít cạnh hơn là tuyến nhanh hơn. Các tuyến đều phải qua cùng bước kiểm tra tài nguyên.")
section("3.3. Dijkstra theo chi phí thời gian", 2)
para("Dijkstra là cơ sở tìm đường theo trọng số không âm [10]. Khi đưa vào bài toán này, "
     "nhóm mở rộng trạng thái bằng nhãn tài nguyên; bảo đảm tối ưu chỉ được dùng cho một "
     "chặng với thời gian giao thông cố định và điều kiện loại nhãn đã nêu ở mục 3.1.")
reuse("4.3 ")
para("Trong một ngày có giao thông cố định, trọng số dương và quy tắc giữ nhãn đúng, Dijkstra "
     "là đối chứng tìm đường tối thiểu step dưới giới hạn nhiên liệu khi tìm kiếm kết thúc đầy "
     "đủ. Bảo đảm này áp dụng cho một truy vấn nguồn–đích, không áp dụng cho thứ tự ghé nhiều "
     "điểm hoặc điểm toàn trận. Cài đặt dùng heap nhị phân, không triển khai Fibonacci heap.")
section("3.4. Greedy Best First và A*", 2)
para("A* kết hợp chi phí đã đi với ước lượng chi phí còn lại; tài liệu gốc trình bày cơ sở "
     "của tìm kiếm dùng heuristic [11]. Trong báo cáo, tính khả chấp và nhất quán của "
     "heuristic lục giác được giải thích trực tiếp từ chi phí tối thiểu của một bước đi.")
reuse("4.4 ")
reuse("4.5 ")
para("Để tính khoảng cách, chương trình đổi ô (row, col) sang tọa độ lập phương với "
     "x = col − (row + row mod 2)/2, y = row và z = −x − y. Khoảng cách là giá trị lớn nhất "
     "trong ba độ chênh tuyệt đối của x, y, z giữa hai ô. Các hàng chẵn và lẻ có bảng láng "
     "giềng khác nhau; kiểm thử tính đối xứng và khoảng cách giúp phát hiện lỗi lệch lưới.")
section("3.5. Mã giả và độ phức tạp", 2)
para("Quy trình chung cho Dijkstra và A* có thể viết ngắn gọn như sau:")
pseudo = para("1. Tạo nhãn nguồn và đưa vào heap.\n"
     "2. Lấy nhãn có độ ưu tiên nhỏ nhất; bỏ nhãn đã bị trội.\n"
     "3. Nếu nhãn ở đích, truy vết chuỗi hướng và trả kết quả.\n"
     "4. Sinh các ô kề; cộng step và nhiên liệu theo ô nguồn.\n"
     "5. Bỏ nhãn vượt tài nguyên hoặc bị nhãn đang giữ trội.\n"
     "6. Lưu nhãn mới và đưa vào heap; lặp đến khi tìm được đích, hết heap hoặc hết giờ.")
pseudo.alignment = WD_ALIGN_PARAGRAPH.LEFT
reuse("7.1 ")
reuse("7.2 ")
para("Phép so sánh thực nghiệm vì thế ghi thêm số nhãn mở rộng và tỷ lệ hết giờ, thay vì chỉ "
     "ghi thời gian. Nhãn bị cắt theo deadline không được nhập vào thống kê chi phí của một "
     "tuyến thành công. Để so chất lượng, các thuật toán chỉ được so trên tập truy vấn chung "
     "mà tất cả đã tìm được tuyến hợp lệ.")

section("4. Thuật toán lập kế hoạch và chọn đội hình")
planning_table(table)
section("4.1. Greedy chọn điểm và phân biệt với tìm đường tham lam", 2)
reuse("5.1 ")
reuse("5.2 ")
para("Greedy ở đây là heuristic chọn điểm ghé, khác Greedy Best-First của mục 3. Một phương "
     "pháp hoạt động trên các mục tiêu thu thập, phương pháp còn lại quyết định nhãn nào được "
     "mở rộng trong một truy vấn tìm đường. Trong đối chứng toàn trận, Greedy và Lookahead "
     "đều dùng A*, cùng quy tắc tiếp tế và cùng simulator để hạn chế yếu tố gây nhiễu.")
section("4.2. Lookahead hai điểm và giới hạn ngân sách", 2)
reuse("5.3 ")
para("Cài đặt chỉ xét tối đa sáu điểm ứng viên ở bước đầu và ba điểm tiếp theo cho mỗi ứng viên. "
     "Đây là nhìn trước cục bộ hai điểm, không phải tìm kiếm tối ưu nhiều ngày hoặc duyệt cây "
     "toàn bộ hành động. Một phần lợi ích tiềm năng có thể bị mất nếu các truy vấn phụ chiếm "
     "ngân sách trước khi tuyến đầu tiên được hoàn thiện. Nhận định này là lý do thiết kế phép "
     "đo, còn nguyên nhân chính xác cần được tách bằng thử nghiệm bổ sung.")
section("4.3. Lịch hẹn tiếp tế và tính khả thi của tuyến", 2)
reuse("5.4 ")
para("Bộ điều khiển không chọn điểm tiếp tế tùy ý cho từng đội hình. Do đó, chất lượng đội "
     "hình được đánh giá luôn gắn với lịch hẹn hiện tại. Việc tăng số xe tiếp tế có thể giảm "
     "số xe thu hàng mà chưa tạo thêm lợi ích tương ứng nếu chúng cùng đi về một trạm.")
section("4.4. Sàng lọc vai trò xe bằng mô phỏng toàn trận", 2)
reuse("5.5 ")
para("Bước sàng lọc dùng khoảng cách lục giác để giảm số ứng viên, không dùng nó thay cho chi "
     "phí đường đi thực. Vòng mô phỏng sau mới xét nhiên liệu, tiếp tế, thu hàng và giao thông. "
     "Cách phân tầng này giúp giữ mã đơn giản, nhưng cũng tạo sai lệch giữa điểm dự đoán bằng "
     "ngân sách ngắn và kết quả khi cấp ngân sách ngày lớn hơn. Phép đo riêng ở mục 7 giữ lại "
     "cả các trường hợp sai lệch này.")
section("4.5. Thời gian, dự phòng và chi phí tính toán", 2)
reuse("5.6 ")
reuse("7.3 ", limit=2)
para("Với C ứng viên, H ngày và chi phí lập một ngày là T_plan, mô phỏng đội hình có chi phí "
     "xấp xỉ C×H×(T_plan + T_sim). Việc liệt kê 2^A − 1 cách gán vai trò với tối đa 8 xe còn "
     "nhỏ, nhưng mô phỏng từng cách mới là phần tốn thời gian. Cấu hình mặc định sàng lọc tối "
     "đa 16 ứng viên và đánh giá lại tối đa 5 ứng viên; đây là giới hạn tính toán, không phải "
     "một bảo đảm về chất lượng xấp xỉ.")
section("4.6. Dijkstra tính cận tiếp cận nhiên liệu", 2)
para("Một cận nguồn cung được tính từ B loại, H ngày, A xe và tồn kho s_i ở mỗi điểm: số loại "
     "toàn trận không quá B, tổng loại theo ngày không quá H×B và tổng suất không quá H nhân "
     "tổng min(s_i,A). Nếu đã chọn P xe tuần tra, thay A bằng P cho cận theo số xe. Với P bằng "
     "0, đội không thể thu hàng. Những cận này chưa xét khả năng di chuyển.")
para("Để xét thêm vị trí và nhiên liệu, nhóm chạy Dijkstra riêng theo nhiên liệu và thời gian "
     "thông thoáng từ từng xe. Điểm chỉ được tính ở ngày d nếu thời gian tối thiểu không vượt "
     "tổng step từ đầu trận đến ngày d. Khi vùng liên thông không có xe tiếp tế, nhiên liệu "
     "tối thiểu tới điểm còn phải không vượt bình ban đầu, dùng chung cho cả trận. Hai khoảng "
     "cách được tính độc lập nên có thể thuộc hai tuyến khác nhau; việc kiểm tra là điều kiện "
     "cần, không khẳng định có tuyến đồng thời đáp ứng tất cả ràng buộc.")
para("Khi vùng liên thông có xe tiếp tế, phép tính nới lỏng bằng cách cho phép nạp ở mọi ô "
     "trong vùng ngay từ đầu. Ràng buộc thời gian gặp xe tiếp tế được bỏ qua, nên không loại "
     "nhầm kế hoạch hợp lệ. Một xe tiếp tế ở vùng bị ao ngăn cách không mở rộng nhiên liệu cho "
     "xe tuần tra ở vùng khác. Trong từng ngày, cận loại là số loại trong hợp các điểm còn có "
     "thể tới; cận suất cộng min(tồn kho, số xe tuần tra đủ điều kiện tới điểm) trên các điểm.")
para("Cận toàn trận lấy hợp loại cuối trận và cộng các cận ngày. Mọi kế hoạch hợp lệ phải "
     "nằm dưới các thành phần này, nhưng một xe đủ nhiên liệu tới từng điểm khi xét riêng có "
     "thể không đủ nhiên liệu ghé tất cả trong cùng hành trình. Xe đứng ở điểm qua nhiều ngày "
     "vẫn có thể lấy hàng dù không còn nhiên liệu. Vì đây là cận lỏng, tỷ lệ điểm chia cho cận "
     "không được gọi là tỷ lệ tối ưu. Chi phí chủ yếu là các lượt Dijkstra và quét điểm theo "
     "ngày; phần này dùng Dijkstra một trọng số, khác bộ tìm đường nhiều nhãn ở mục 3.")

add_method(section, para, figure)
section("5. Ứng dụng các thuật toán trong phương pháp kết hợp RL")
section("5.1. Câu hỏi và phạm vi thử nghiệm RL", 2)
para("Học tăng cường được đưa vào như một hướng ứng dụng của các thuật toán đã xây dựng: "
     "mô hình học chọn mục tiêu ở mức cao, còn tìm đường và kiểm tra ràng buộc tạo kế hoạch "
     "thực thi. Phép thử hiện tại hỏi cấu hình kết hợp có cải thiện điểm so với heuristic hay "
     "không. Nó không nhằm chứng minh RL luôn tốt hơn và cũng không đo riêng đóng góp của "
     "từng thành phần khi chưa có đối chứng bật/tắt tương ứng.")
section("5.2. PPO và kiến trúc actor critic đang sử dụng", 2)
para("PPO cập nhật chính sách từ dữ liệu tương tác và hạn chế mức thay đổi thông qua hàm mục "
     "tiêu có clipping [7]. MAPPO khai thác cấu trúc actor–critic cho bài toán hợp tác nhiều tác "
     "tử [8]. Trong bản cài đặt được đánh giá, các xe chia sẻ mạng actor và critic đánh giá trạng "
     "thái toàn đội. Tên lớp MAPPOTrainer là tên trong nhánh mã nguồn; báo cáo không coi bản "
     "cài đặt này là một phép tái lập đầy đủ mọi thiết lập của bài báo MAPPO.")
para("Mạng nhận bản đồ qua CNN với mười kênh đặc trưng gồm địa hình, giao thông, điểm bán, "
     "trạng thái thu loại, kho và vị trí đối thủ nếu có. Đặc trưng từng xe gồm thông tin không "
     "gian, nhiên liệu, loại xe và vị trí. Mạng ghép thông tin các xe với lịch sử loại và thông "
     "tin ngày để tạo đặc trưng toàn đội. Actor trả lựa chọn chỉ số điểm bán hoặc chờ cho mỗi "
     "xe tuần tra, còn critic trả giá trị trạng thái [9]. Trong Practice một đội, đầu vào không "
     "có đối thủ, nên kênh đối thủ không tạo bằng chứng về khả năng chơi nhiều đội.")
section("5.3. Vai trò của A*, masking và Greedy", 2)
table("Bảng 2. Các thành phần trong chuỗi quyết định kết hợp", ["Thành phần", "Nhiệm vụ", "Điều chưa được bảo đảm"],
      [["RL", "Chọn điểm đích cho từng xe", "Không tự xuất chuỗi lệnh hợp lệ"],
       ["A*", "Chuyển mục tiêu thành tuyến theo step và nhiên liệu", "Tuyến ngắn chưa tối ưu điểm toàn trận"],
       ["Masking và giữ chỗ kho", "Hạn chế lựa chọn không phù hợp; phân bổ tồn kho dự kiến", "Không thay cho kiểm tra timeline đầy đủ"],
       ["Greedy", "Tạo phương án nền và dự phòng", "Không bảo đảm tối ưu toàn cục"],
       ["Simulator và validator", "So ứng viên, kiểm tra ràng buộc", "Điểm dự đoán có thể khác hiệu quả dài hạn"]], [3.2, 6.4, 6.4], 11)
para("Checkpoint bật target masking, tuyến phụ và giữ chỗ tồn kho. Vì vậy, kết quả không chỉ "
     "đến từ một quyết định RL thuần: sau khi chọn đích đầu, bộ tạo tuyến còn có thể thêm các "
     "điểm phụ bằng heuristic. Trong run_play của nhánh, Greedy tạo phương án cơ sở; ứng viên "
     "RL chỉ thay thế khi hợp lệ và có bộ điểm sau ngày tốt hơn theo simulator của nhánh. "
     "Đây là RL kết hợp Greedy với bộ chọn theo điểm dự đoán, không phải phép đo chính sách "
     "RL độc lập. A* là bộ chuyển hành động bắt buộc của kiến trúc hiện tại, nên không thể bỏ "
     "nó rồi lấy việc hệ thống không chạy làm bằng chứng tăng điểm.")
section("5.4. Nguồn checkpoint và quy trình suy luận", 2)
para("Nhóm lấy nhánh Procon2026 tại commit b6df084c253503b5673721c126ff261430cd0021 và checkpoint "
     "runs/pilot_reserved_001/seed_20042/episode_256.pt. Metadata ghi episodes_completed = 256; "
     "đây là thông tin lưu trong checkpoint, không phải số episode nhóm vừa huấn luyện lại ở "
     "thí nghiệm này. File được nhận diện bằng SHA-256 lưu trong model_metadata.json [9]. "
     "Mô hình được chạy ở chế độ đánh giá, chọn hành động xác định trên CPU và không cập nhật "
     "trọng số trong các trận BTC.")
para("Client gốc dùng giao thức khác API Việt Nam nên nhóm viết adapter đổi cấu trúc dữ liệu, "
     "mã địa hình, chỉ số ngày và output. Adapter đọc vị trí, nhiên liệu, giao thông và lịch sử "
     "thu thực tế mỗi ngày. Các lớp RL, A*, Greedy và simulator đánh giá ứng viên vẫn được nhập "
     "từ bản chụp nhánh. Adapter nộp một phương án cuối cho mỗi ngày thay vì nộp tạm Greedy rồi "
     "nộp cải thiện. Toàn bộ xe là tuần tra theo mặc định run_play; chưa kết hợp bộ chọn đội "
     "hình mới vào lượt RL này.")
rl_table(table)
section("5.5. Mục tiêu học và các giới hạn diễn giải", 2)
para("Mã huấn luyện trong nhánh có phần thưởng trọng số cho loại mới, loại theo ngày và số "
     "suất, cùng cơ chế shaping theo khoảng cách. Phần thưởng số thực này không mặc nhiên "
     "tương đương thứ tự ưu tiên từ điển của BTC. Đây là một điểm cần kiểm tra khi huấn luyện "
     "tiếp, nhưng báo cáo chưa có thí nghiệm chứng minh nó là nguyên nhân của chênh lệch điểm. "
     "Nhóm chưa kiểm chứng lại dữ liệu huấn luyện, mức hội tụ hoặc toàn bộ lịch sử các episode "
     "chỉ từ một file checkpoint.")
para("Để định lượng trợ giúp cho RL, hướng tiếp theo là giữ cùng checkpoint và dữ liệu, rồi "
     "đối chứng bật/tắt tuyến phụ, giữ chỗ hoặc bộ chọn Greedy. So sánh bộ tìm đường cần dùng "
     "những phương án thay thế có cùng đầu ra hợp lệ. Những phép tách thành phần đó chưa được "
     "thực hiện, nên báo cáo chỉ kết luận về cấu hình kết hợp đã chạy, không quy toàn bộ điểm "
     "cho RL hoặc khẳng định mọi thành phần đều làm tăng chất lượng.")

section("6. Thiết kế thực nghiệm và độ tin cậy của phép đo")
section("6.1. Các nhóm dữ liệu và đối chứng", 2)
table("Bảng 3. Phân biệt các nhóm thực nghiệm", ["Nhóm", "Dữ liệu và phương pháp", "Nguồn kết quả"],
      [["Tìm đường", "30 bản đồ 8×8, 16×16, 32×32; 90 truy vấn; 5 thuật toán", "450 lượt chạy offline"],
       ["Chiến lược TTUD", "30 cấu hình cùng seed; Greedy và Lookahead", "60 trận offline, 240 kế hoạch ngày"],
       ["Chọn đội hình", "9 nhãn cấu hình BTC và 6 bản đồ tự sinh; 4 đối chứng", "Offline; Q04/Q06 kiểm chứng BTC riêng"],
       ["RL kết hợp", "9 bài Practice; checkpoint 256 episode; toàn tuần tra", "90 kế hoạch được BTC nhận"]], [3.2, 8.5, 4.3], 11)
para("Nhóm tìm đường có ba cặp nguồn–đích cho mỗi bản đồ, dùng cùng trạng thái giao thông được "
     "sinh theo seed và cùng giới hạn 80 step, 40 nhiên liệu, 0,25 giây mỗi truy vấn. Thí nghiệm "
     "toàn trận dùng quỹ ngày 80 step, bình 40 và 0,25 giây lập kế hoạch mỗi ngày cho từng chiến "
     "lược; mỗi cấu hình được chạy với cả Greedy và Lookahead. Các giá trị gốc được giữ trong "
     "experiments/results để đối chiếu, thay vì suy ra từ hình biểu đồ.")
para("Thí nghiệm đội hình cấp hạn 12 giây cho cấu hình BTC, 4 giây cho bản đồ tự sinh và đánh "
     "giá lại độc lập với 0,15 giây lập kế hoạch mỗi ngày. Hai seed tự sinh là 2026 và 2027 ở "
     "mỗi kích thước. Lượt sàng lọc và lượt đánh giá lại có ngân sách khác nhau, nên thứ hạng "
     "có thể đổi; các trường hợp giảm điểm vẫn được giữ. Q01 và Q02 có config giống hệt nhau "
     "nên không được xem là hai mẫu độc lập.")
section("6.2. Chỉ số và quy tắc so sánh công bằng", 2)
para("Tìm đường được đánh giá bằng tính hợp lệ, tỷ lệ tìm được, tỷ lệ hết giờ, step, nhiên "
     "liệu, số cạnh, nhãn mở rộng và thời gian. Chi phí trung bình giữa các thuật toán chỉ "
     "được đối chiếu trên các truy vấn chung thành công. Ở cấp toàn trận, bộ điểm được so "
     "theo cặp input và thứ tự ưu tiên (U, D, Q); thời gian và số lần dự phòng được báo cáo riêng.")
para("Điểm simulator, điểm BTC và cận trên được phân biệt trong từng bảng. Thời gian offline "
     "không gồm truyền mạng, khởi tạo thư viện hoặc xếp hàng máy chủ. Cơ chế deadline là giới "
     "hạn mềm do một số bước kiểm tra diễn ra sau tìm kiếm. Các quyết định sát hạn có thể đổi "
     "theo tải máy; cùng input không bảo đảm tái tạo đúng tuyến khi chạy lại theo đồng hồ thực. "
     "Mảng lệnh đã lưu cho phép tái hiện chính xác một phép chấm mà không chạy lại bộ lập kế hoạch.")
section("6.3. Simulator và kiểm chứng API làm công cụ đánh giá", 2)
para("Simulator chạy timeline chung của các xe, kiểm tra nhiên liệu, tiếp tế, thu hàng và giao "
     "thông rồi trả trạng thái ngày sau. Bộ kiểm thử có 47 phương thức, bao gồm tìm đường đối "
     "chiếu vét cạn nhỏ, chi phí ô nguồn, nhiều loại lỗi output, tiếp tế và các cận tiếp cận. "
     "Đối với dữ liệu BTC, nhóm nộp vào Practice riêng của đội 62, lưu request/response không "
     "kèm token và chạy lại cùng output để so từng frame. Đây là bằng chứng về những kế hoạch "
     "đã thử, không phải chứng minh simulator đúng trên toàn bộ không gian trạng thái [4], [6].")
para("Các endpoint được sử dụng gồm config, day, agent-types, practice/actions, practice/reset, "
     "actions, replay, state và result dưới /api/game. Thư mục bằng chứng tách riêng lượt "
     "kiểm chứng simulator, Greedy/Lookahead nhánh cũ, RL và chọn đội hình. Giảng viên có thể "
     "kiểm tra JSON tổng hợp offline hoặc xem website bằng tài khoản có quyền; dữ liệu thô chỉ lưu tại máy. Báo cáo không "
     "đính kèm thông tin xác thực. Những lần đặt lại Practice đều lưu lịch sử trước đó.")
section("6.4. Điều kiện riêng của đối chứng RL", 2)
para("Baseline của lượt RL là Greedy/Lookahead trong cùng nhánh Procon2026 với adapter tương "
     "ứng, không phải Greedy của nhánh ttud_clean vừa thêm bộ chọn đội hình. Cả hai cấu hình "
     "chọn toàn tuần tra và được chấm trên cùng tập bài Practice một đội. Vì thuật toán quyết "
     "định tuyến khác nhau, chúng tạo lịch sử giao thông khác nhau sau ngày đầu; đó là một "
     "phần kết quả của chiến lược, không phải lỗi cần ép về cùng giao thông cố định.")
para("Practice đang hiển thị Q01–Q04 và Q06–Q10 trong danh sách đã kiểm tra, không có Q05. "
     "Thí nghiệm RL chưa nộp vào Mock Contest và chưa kiểm tra ảnh hưởng của đối thủ. Các "
     "kết luận chỉ bao phủ checkpoint, cấu hình adapter và các input này; không có nhiều seed "
     "huấn luyện hoặc kiểm định thống kê để suy rộng thành ưu thế của một họ phương pháp.")

add_protocol(section, para)
section("7. Kết quả và phân tích thuật toán")
section("7.1. So sánh năm thuật toán tìm đường", 2)
data = source_table(3)
table("Bảng 4. Khả năng hoàn thành và chi phí tìm kiếm", ["Cỡ / thuật toán", "Thành công", "Dừng hạn", "TB ms", "Nhãn TB"],
      [[r[0] + " / " + r[1], *r[2:]] for r in data[1:]], [4, 3, 3, 3, 3], 10.5)
data = source_table(4)
table("Bảng 5. Chất lượng tuyến trên các truy vấn chung thành công", ["Cỡ / thuật toán", "Truy vấn", "Step TB", "Fuel TB", "Cạnh TB"],
      [[r[0] + " / " + r[2], r[1], *r[3:]] for r in data[1:]], [4, 3, 3, 3, 3], 10.5)
reuse("9.1 ")
para("Kết quả này cho thấy cần đọc đồng thời tỷ lệ hoàn thành và thời gian. Một thuật toán "
     "rất nhanh ở các lần thành công nhưng bỏ nhiều truy vấn không mặc nhiên phù hợp hơn cho "
     "hệ thống. Các so sánh độ dài tuyến ở bảng 5 đã được giới hạn về tập truy vấn chung; việc "
     "lọc này không làm mất thông tin thất bại vì bảng 4 vẫn báo riêng đầy đủ.")
figure('path_comparison.png', 'Hình 2. Dijkstra và A* trên 90 truy vấn, chia theo cỡ bản đồ.', 16)
section("7.2. Greedy và Lookahead trong cùng ngân sách", 2)
data = source_table(5)
table("Bảng 6. Điểm trung bình toàn trận của nhánh TTUD", ["Cỡ / chiến lược", "U trung bình", "D trung bình", "Q trung bình"],
      [[r[0] + " / " + r[1], *r[2:5]] for r in data[1:]], [4.6, 3.8, 3.8, 3.8], 11)
table("Bảng 7. Thời gian và tính hợp lệ của cùng phép đo", ["Cỡ / chiến lược", "Giây TB / trận", "Hợp lệ", "Dự phòng"],
      [[r[0] + " / " + r[1], *r[5:]] for r in data[1:]], [4.6, 3.8, 3.8, 3.8], 11)
data = source_table(6)
table("Bảng 8. So sánh Lookahead với Greedy theo từng cặp", data[0], data[1:], [4, 4, 4, 4], 11)
para("Lookahead thắng 3 cặp và thua 27 cặp trong 30 cấu hình. Ở 8×8 và 16×16, Lookahead thua "
     "cả 10 cặp mỗi cỡ; ở 32×32, nó thắng 3 và thua 7 cặp. Vì vậy, nhóm chưa có cơ sở gọi "
     "Lookahead là cải tiến chất lượng trên cấu hình đang đo. Mức nhìn trước hai điểm làm "
     "tăng số truy vấn A*; dưới cùng thời hạn 0,25 giây, chi phí đó có thể làm giảm số tuyến "
     "hoàn thiện. Mục 7.7 bổ sung phép đo theo nhiều ngân sách để khảo sát yếu tố "
     "này, thay vì kết luận mọi phương pháp nhìn trước đều kém.")
section("7.3. Kết quả chọn đội hình và ý nghĩa của cận trên", 2)
official = [r for r in teams if r["case"].startswith("Q")]
table("Bảng 9. Điểm offline sau khi đánh giá lại đội hình", ["Bài", "Toàn tuần tra", "Xe cuối tiếp tế", "Đội hình chọn"],
      [[r["case"], score(r["scores"]["all_patrol"]), score(r["scores"]["last_supply"]), score(r["scores"]["selected"])] for r in official],
      [1.6, 4.8, 4.8, 4.8], 11)
table("Bảng 10. Vai trò đã chọn và thời gian chọn offline", ["Bài", "Danh sách vai trò", "Ứng viên ban đầu", "Thời gian s"],
      [[r["case"], str(r["types"]).replace(" ", ""), r["candidate_count"], f"{r['selection_seconds']:.2f}"] for r in official],
      [1.6, 6.2, 4.1, 4.1], 11)
para("Vai trò 0 là tuần tra và 1 là tiếp tế, theo đúng thứ tự agent của input. Q04 chọn xe "
     "số 1 làm tiếp tế, Q06 chọn xe số 0 và Q09 chọn xe số 4; những bài còn lại trong bảng "
     "giữ toàn tuần tra. Chỉ số xe bắt đầu từ 0. Bộ chọn không di chuyển ô xuất phát của bất "
     "kỳ xe nào. Thời gian lớn nhất trên chín nhãn bài là 10,89 giây trong lượt có hạn 12 giây; "
     "mức đo này không bảo đảm mọi máy hoặc mọi input đều hoàn tất trong cùng thời gian.")
table("Bảng 11. Kết quả thực nghiệm và hai cận trên của đội hình chọn", ["Bài", "Điểm offline", "Cận nguồn cung", "Cận tiếp cận"],
      [[r["case"], score(r["scores"]["selected"]), score(bounds[r["case"]]["rules"]), score(bounds[r["case"]]["selected_types"])] for r in official],
      [1.6, 4.8, 4.8, 4.8], 11)
para("Cận nguồn cung không cố định đội hình, còn cận tiếp cận dùng đúng vai trò ở bảng 10 và "
     "phép nới lỏng ở mục 4.6. Cả hai là giới hạn theo từng thành phần, chưa chắc có kế hoạch "
     "đạt đồng thời. Trên chín cấu hình BTC và sáu bản đồ tự sinh, cận tiếp cận chưa giảm so "
     "với cận chỉ xét số xe tuần tra: đủ xe có thể tới mỗi điểm khi xét riêng, nhưng việc ghé "
     "nhiều điểm trong cùng hành trình vẫn khó. Do đó, các bảng không chứng minh điểm thực "
     "nghiệm đang gần hoặc xa tối ưu một tỷ lệ xác định.")
table("Bảng 12. Tốt hơn, bằng và kém hơn các cấu hình đối chứng", ["Nhóm / đối chứng", "Tốt hơn", "Bằng", "Kém hơn"],
      [["BTC / toàn tuần tra", 3, 6, 0], ["BTC / xe cuối tiếp tế", 6, 1, 2], ["BTC / bộ ba cũ", 1, 8, 0],
       ["Tự sinh / toàn tuần tra", 5, 0, 1], ["Tự sinh / xe cuối tiếp tế", 3, 1, 2], ["Tự sinh / bộ ba cũ", 0, 3, 3]],
      [7, 3, 3, 3], 11)
para("Chọn vai trò theo mô phỏng có ích ở một số cấu hình, nhưng chưa luôn tốt hơn cách chọn "
     "xe cuối làm tiếp tế hoặc bộ ba ứng viên cũ. Q03 và Q10 vẫn kém đối chứng xe cuối tiếp tế "
     "ở lượt đánh giá lại. Các bản đồ tự sinh còn cho thấy trường hợp bộ chọn mới giảm điểm "
     "so với bộ cũ. Đây là hạn chế thực của quy trình sàng lọc ngắn và ngân sách ngày khác nhau, "
     "không được loại khỏi bảng để tạo ấn tượng cải thiện đồng đều.")
table("Bảng 13. Hai đội hình được máy chủ BTC kiểm chứng", ["Bài", "Điểm BTC", "Frame so sánh", "Sai khác"],
      [[r["question"], score(r["server_score"]), r["comparison"]["checked_frames"], r["comparison"]["mismatch_count"]] for r in verified],
      [1.6, 6.4, 4, 4], 11)
para("Cả 20 kế hoạch ngày của Q04 và Q06 được BTC nhận; điểm khớp simulator, qua tổng cộng "
     "2.807 frame và 44.220 giá trị đối chiếu. Với Q06, (15,133,145) được ưu tiên hơn "
     "(15,111,192) của toàn tuần tra vì D lớn hơn dù Q nhỏ hơn. Điểm BTC trong bảng chỉ áp "
     "dụng hai kế hoạch đã nộp, không biến các điểm offline còn lại thành điểm máy chủ.")
section("7.4. Đối chứng checkpoint RL kết hợp Greedy", 2)
table("Bảng 14. Điểm BTC của hai cấu hình trên nhánh Procon2026", ["Bài", "Greedy / Lookahead", "RL kết hợp Greedy"],
      [[r["question"], score(baseline[r["question"]]["score"]), score(r["score"])] for r in rl], [1.6, 7.2, 7.2], 11.5)
para("Cấu hình RL kết hợp thua đối chứng ở cả 9 nhãn bài theo thứ tự ưu tiên của BTC. Ở Q03, "
     "Q04 và Q09, nó còn thu ít loại toàn trận hơn; ở các bài còn lại, số loại bằng nhau "
     "nhưng tổng loại theo ngày thấp hơn. Ví dụ Q04 giảm từ (20,70,145) xuống (15,42,96). "
     "Đây là kết quả âm cần được giữ lại, không phải bằng chứng rằng mọi RL đều không phù hợp "
     "với bài toán.")
table("Bảng 15. Số ngày bộ chọn dùng ứng viên RL", ["Bài", "Dùng RL", "Giữ Greedy", "Tổng ngày"],
      [[r["question"], sum(d["mode"] == "rl" for d in r["days"]), sum(d["mode"] != "rl" for d in r["days"]), len(r["days"])] for r in rl],
      [4, 4, 4, 4], 11)
para("Mô hình tạo 90 ứng viên và bộ chọn sử dụng RL ở 43 ngày, giữ Greedy ở 47 ngày. Cả "
     "90 kế hoạch cuối cùng được BTC chấp nhận và lịch sử máy chủ khớp output đã lưu. Thời "
     "gian lập kế hoạch lớn nhất là 2,25 giây trên CPU trong lượt thử, chưa gồm khởi tạo thư "
     "viện, mạng và tải replay. Vì còn có tuyến phụ và Greedy, báo cáo không gán tất cả điểm "
     "này cho riêng chính sách RL.")
para("Một hướng giải thích cần kiểm chứng là bộ chọn chỉ so điểm sau một ngày, trong khi "
     "tiêu hao nhiên liệu có hậu quả nhiều ngày. Những yếu tố khác gồm chất lượng checkpoint, "
     "phân bố dữ liệu huấn luyện và phần thưởng khác mục tiêu ưu tiên. Nhóm chưa tách các yếu "
     "tố này bằng thí nghiệm, nên chưa kết luận nguyên nhân nào chi phối. Bộ chọn đội hình mới "
     "cũng chưa được dùng trong lượt RL; không thể lấy điểm Q04 đã tối ưu đội hình ở bảng 13 "
     "để quy toàn bộ chênh lệch so với RL cho năng lực học.")
section("7.5. Chi phí kiểm tra và bằng chứng tương thích", 2)
data = source_table(7)
table("Bảng 16. Thời gian kiểm tra kế hoạch trong nhóm toàn trận", data[0], data[1:], [2, 4, 3.5, 3.5, 3], 10.5)
data = source_table(8)
table("Bảng 17. Kiểm tra bổ sung khi tăng số xe và step", data[0], data[1:], [4, 4, 4, 4], 11)
para("Các số đo cho thấy kiểm tra kế hoạch tốn ít thời gian so với hạn 30 giây trong những "
     "cấu hình đã thử; chúng không bảo đảm mọi dữ liệu hoặc mọi máy có cùng độ trễ. Với A xe, "
     "T step, V ô, S điểm và N lệnh, phần kiểm tra có chi phí phù hợp dạng O(N + A×T + V + S) "
     "trong chế độ một đội. Kiểm tra không bật replay nếu không cần để tránh tăng bộ nhớ theo "
     "số frame.")
data = source_table(9)
table("Bảng 18. Các tập replay BTC dùng kiểm chứng simulator ban đầu", data[0], data[1:], [5.2, 2.2, 2.3, 3.6, 2.7], 10.5)
para("Sáu tập replay kiểm tra 6.331 frame và 97.345 giá trị, không phát hiện sai khác sau các "
     "bản sửa đã ghi nhận. Q10 có ngày đầu chung giữa hai biến thể, nên số frame là số lần "
     "đối chiếu chứ không phải số trạng thái độc lập. Hai phép kiểm chứng đội hình mới được "
     "báo cáo riêng ở bảng 13. Bộ cận còn được kiểm tra trên 456 ngày thuộc các kế hoạch "
     "đối chứng đã lưu; không có điểm nào vượt cận tương ứng [6].")

add_results(ROOT, section, para, table, figure)
section("8. Đánh giá giới hạn và kết luận")
section("8.1. Những kết luận có thể rút ra", 2)
para("Bài tập lớn đã thể hiện ba lớp ứng dụng thuật toán. A* và Dijkstra xử lý tìm đường có "
     "tài nguyên; Greedy và Lookahead tổ chức mục tiêu thu thập; tìm kiếm giới hạn thời gian "
     "chọn vai trò xe. Bộ cận dùng Dijkstra theo cách khác để tìm điều kiện cần về tiếp cận. "
     "Việc phân biệt các lớp giúp tránh đánh đồng tối ưu một tuyến với tối ưu cả trận.")
para("Các đối chứng cho thấy A* có lợi trong lượng tìm kiếm của bản triển khai, còn Greedy "
     "là baseline mạnh dưới ngân sách ngắn. Lookahead và RL đang thử chưa cải thiện kết quả "
     "một cách ổn định. Chọn đội hình có thể nâng điểm ở một số input, nhưng phụ thuộc bộ "
     "điều khiển dùng để đánh giá. Simulator và API làm cơ sở kiểm tra số liệu thay vì thay "
     "thế phần phân tích thuật toán.")
para("Đối chứng quy hoạch động bổ sung mốc tối ưu thực sự cho 24 bài thu nhỏ: Greedy "
     "khớp tối ưu ở 12 bài và Lookahead ở 15 bài. Phép đo 240 trận cho thấy khi tăng "
     "ngân sách từ 0,05 lên 3 giây/ngày, Lookahead tăng số cặp thắng từ 3 lên 11 trong "
     "30 cặp mỗi mức, nhưng vẫn còn 14 cặp thua ở mức 3 giây. Hai kết quả cho thấy "
     "cần phân biệt tiềm năng của nhìn trước trên bài nhỏ với hiệu quả thực thi dưới "
     "ràng buộc thời gian; chúng không chứng minh Lookahead luôn vượt Greedy.")
section("8.2. Giới hạn của các kết luận", 2)
para("Các bản đồ BTC đã thử chủ yếu có kích thước lớn và số nhãn bài độc lập ít hơn số tên "
     "do Q01/Q02 trùng config. Nhóm bổ sung dữ liệu tự sinh nhưng hai seed mỗi cỡ trong thí "
     "nghiệm đội hình chưa đủ cho kết luận rộng. Các hạn giờ thực gây biến động tuyến; bộ "
     "chọn chưa đo trên nhiều chính sách điều khiển hoặc nhiều mức ngân sách. Cận tiếp cận "
     "vẫn lỏng vì không ràng buộc cả hành trình và lịch gặp tiếp tế.")
para("Phần RL chỉ có một checkpoint với metadata 256 episode, chưa có huấn luyện mới, nhiều "
     "seed hay thí nghiệm tách thành phần. Nhánh RL và nhánh TTUD có các bộ điều khiển khác "
     "nhau, nên chỉ những phép đối chứng cùng nhóm mới được dùng để quy tác động. Toàn bộ "
     "đánh giá chiến lược hiện tại là một đội; khả năng nhiều đội của simulator chưa được "
     "đối chiếu với replay BTC nhiều đội. Mức tương thích API cũng chỉ được khẳng định trong "
     "phạm vi kế hoạch và luật đã kiểm tra.")
section("8.3. Các hướng cải tiến có thể kiểm chứng", 2)
para("Sau phép đo nhiều ngân sách ở mục 7.7, hướng tiếp theo là đánh giá đội "
     "hình bằng một bộ điều khiển nhất quán hơn và thử cải thiện tuyến bằng tìm kiếm cục bộ. "
     "Những phép đổi tuyến phải được kiểm lại step, nhiên liệu và lịch tiếp tế; báo cáo chưa "
     "cài 2-opt, 3-opt hoặc beam search. Việc bổ sung tên thuật toán chỉ có ý nghĩa khi có "
     "câu hỏi đối chứng và số liệu tương ứng.")
para("Ở hướng RL, nhóm có thể thử bộ chọn đội hình mới, đánh giá tiếp nhiều ngày trước khi "
     "chọn ứng viên và đối chứng các heuristic hỗ trợ bằng cùng checkpoint. Nếu huấn luyện "
     "lại, cần ghi rõ dữ liệu, seed, phần thưởng, phiên bản luật và thời gian tính toán. Các "
     "bước này là kế hoạch tiếp theo, không được trình bày như kết quả đã hoàn thành.")
section("8.4. Kết luận", 2)
para("Đề tài cho thấy một bài toán có nguồn gốc từ cuộc thi có thể trở thành môi trường để "
     "phân tích và ứng dụng thuật toán ở nhiều cấp quyết định. Giá trị chính của báo cáo là "
     "mô hình hóa tài nguyên đúng, cài đặt và đối chứng rõ ràng, giữ lại cả kết quả giảm điểm "
     "và giới hạn những gì có thể kết luận. Phần kết hợp RL minh họa vai trò thực thi và kiểm "
     "tra của thuật toán truyền thống trong một hệ thống có học máy, nhưng chưa chứng minh "
     "checkpoint hiện tại tạo ra lời giải tốt hơn các heuristic.")

section("Tài liệu tham khảo")
references = [
    "[1] Ban tổ chức Procon Việt Nam. Tối ưu hoá lộ trình HEXUDON. Tài liệu 2026_Procon_Problem VI.pdf, 2026, trong thư mục Đề bài.",
    "[2] Ban tổ chức. Techinical_Presentation.pptx. Hướng dẫn website, schema và luồng API, trong thư mục Đề bài.",
    "[3] About the Formats of the Competition Division HEXUDON. Schema kỹ thuật liên kết trong tài liệu BTC; bản tiếng Anh không chính thức. https://drive.google.com/file/d/1Oc6RyIBX3oQa6RGeZ4MNDN4tKeOL6t1V/view. Truy cập 18/10/2026.",
    "[4] HEXUDON server. API documentation và OpenAPI. https://hexudon.hairbui76.id.vn/docs; https://hexudon.hairbui76.id.vn/openapi.json. Truy cập 19/10/2026.",
    "[5] Nhóm thực hiện. Mã nguồn và dữ liệu BTL TTUD, nhánh làm việc ttud_clean. Kho dự kiến bàn giao: https://github.com/kttt294/BTL_TTUD. Tại thời điểm báo cáo, đường dẫn này chưa được dùng làm bằng chứng rằng mã hiện tại đã được đẩy lên.",
    "[6] Nhóm thực hiện. Dữ liệu thực nghiệm và bằng chứng API ngày 19/10/2026: experiments/results, team_selection_results, api_evidence, team_selection_api_evidence, legacy_branch_evidence và rl_branch_evidence. Các request/response lưu không có token.",
    "[7] J. Schulman, F. Wolski, P. Dhariwal, A. Radford và O. Klimov. Proximal Policy Optimization Algorithms. 2017. https://arxiv.org/abs/1707.06347.",
    "[8] C. Yu và cộng sự. The Surprising Effectiveness of PPO in Cooperative, Multi-Agent Games. 2022. https://arxiv.org/abs/2103.01955.",
    "[9] Mã nguồn nhánh Procon2026, commit b6df084c253503b5673721c126ff261430cd0021. https://github.com/kttt294/Procon2026/tree/b6df084c253503b5673721c126ff261430cd0021. Checkpoint episode_256.pt; SHA-256: " + metadata["sha256"] + ".",
]
references += [
    "[10] E. W. Dijkstra. A note on two problems in connexion with graphs. Numerische Mathematik 1, 269–271, 1959. https://doi.org/10.1007/BF01386390.",
    "[11] P. E. Hart, N. J. Nilsson và B. Raphael. A Formal Basis for the Heuristic Determination of Minimum Cost Paths. IEEE Transactions on Systems Science and Cybernetics 4(2), 100–107, 1968. https://doi.org/10.1109/TSSC.1968.300136.",
]
for text in references:
    p = para(text)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.keep_together = True

section("Phụ lục A. Luật thực thi và kiểm chứng")
section("A.1. Các quy tắc timeline cần giữ nhất quán", 2)
para("Trong mỗi step, xe vẫn ở ô nguồn cho tới khi hoàn thành lệnh đi; nhiên liệu bị trừ lúc "
     "đến. Sau cập nhật di chuyển, simulator xử lý tiếp tế rồi thu thập theo vị trí hiển thị. "
     "Frame 0 là trạng thái ban đầu, chưa thu hàng hoặc nạp nhiên liệu. Xe tiếp tế không lấy "
     "hàng và chỉ nạp xe cùng đội. Những quy tắc này được ghi rõ vì một điểm cuối trận đúng "
     "vẫn có thể che sai khác về nhiên liệu hoặc sự kiện giữa chừng.")
para("Đếm hiện diện trên đường được đối chiếu riêng: khi xe xuất phát ngày trên ô đường, "
     "quãng chuyển tiếp rời ô xuất phát chưa được đếm như đứng chờ; sau lần đến ô đầu tiên, "
     "vị trí hiển thị được tính bình thường cả trong chuyển tiếp. Đây là quy tắc tương thích "
     "rút ra từ các replay đã thử, không phải diễn giải chắc chắn mọi phiên bản server đều "
     "giữ nguyên. Bằng chứng và test hồi quy nằm trong simulation_conventions.md [6].")
section("A.2. Kiểm tra output và phạm vi API", 2)
table("Bảng A1. Quy ước hướng đi trên lưới", ["Mã", "Hướng", "Ghi chú"],
      [[0, "Trên trái", "NW"], [1, "Trên phải", "NE"], [2, "Phải", "E"],
       [3, "Dưới phải", "SE"], [4, "Dưới trái", "SW"], [5, "Trái", "W"]], [2, 8, 6], 11.5)
para("Validator kiểm tra số xe, kiểu lệnh, hướng hợp lệ, ô đích, đủ step cho mỗi lần đi, đủ "
     "nhiên liệu và tổng thời lượng đúng ngày. Simulator sao chép trạng thái trước khi chạy; "
     "lỗi không được sửa trực tiếp trạng thái gốc. Điều phối bài nộp của các đội khác là vấn "
     "đề riêng, không suy ra từ cơ chế giao dịch của thư viện một đội.")
data = source_table(10)
table("Bảng A2. Một số output sai bị máy chủ từ chối", data[0], data[1:], [6, 4, 6], 11)
para("Giảng viên có thể kiểm tra thủ công tại danh sách Practice Match: "
     "https://hexudon.hairbui76.id.vn/tournament/1/round/1/match/11/questions. Trong các bản "
     "Practice riêng đã đo, config có players = 1 và trạng thái ngày có others rỗng. Tắc "
     "đường vẫn xuất hiện do xe đội mình; ví dụ Q01 lượt RL có 36 ô tắc ở ngày 3. Các tài "
     "khoản khác nộp trong lượt riêng không được cộng vào lịch sử giao thông của đội 62.")

section("Phụ lục B. Chạy chương trình và tái hiện số liệu")
section("B.1. Các lệnh chính", 2)
para("Lõi TTUD dùng Python 3.10 trở lên và thư viện chuẩn. Chỉ phần RL và công cụ dựng tài "
     "liệu cần các thư viện riêng. Tùy chọn -X utf8 hỗ trợ hiển thị tiếng Việt trên Windows. "
     "Người dùng chạy từ thư mục gốc của dự án; các ví dụ sau không tự nộp bài lên website.")
commands = [
    "python -X utf8 -m unittest discover -s tests -v",
    "python -X utf8 src/main.py demo --size 8 --seed 42 --seconds 1 --output results/demo.json",
    'python -X utf8 src/main.py select --config "Đề bài/input_sample.json" --starts 558 998 130 955 --seconds 20 --output results/types.json --selection-log results/selection.json',
    'python -X utf8 src/main.py plan --config "Đề bài/input_sample.json" --starts 558 998 130 955 --types-file results/types.json --output results/output.txt',
    'python -X utf8 src/main.py validate --config "Đề bài/input_sample.json" --starts 558 998 130 955 --types-file results/types.json --actions results/output.txt',
    'python -X utf8 src/main.py bounds --config "Đề bài/input_sample.json" --starts 558 998 130 955 --types-file results/types.json --output results/bounds.json',
]
for command in commands:
    para(command).alignment = WD_ALIGN_PARAGRAPH.LEFT
para("Vị trí trong ví dụ chỉ áp dụng cho input mẫu. Từ ngày 2, lệnh plan cần --state chứa "
     "trạng thái thật và --day đúng ngày; không dùng lại nhiên liệu hoặc vị trí đầu trận. "
     "Lệnh bounds hiện chỉ tính từ cấu hình đầu trận và vai trò đã chọn, không nhận trạng "
     "thái giữa trận. Cận xuất gồm nguồn cung, số xe tuần tra, tiếp cận và chi tiết từng ngày.")
section("B.2. Tái hiện các phép đo", 2)
for command in ["python -X utf8 experiments/benchmark.py --games 10 --sizes 8 16 32 --seconds 0.25",
                "python -X utf8 experiments/summarize.py",
                "python -X utf8 experiments/benchmark_team_selection.py",
                "python -X utf8 experiments/calculate_bounds.py"]:
    para(command).alignment = WD_ALIGN_PARAGRAPH.LEFT
para("Nhóm kết quả RL đi kèm repo có thể được kiểm tra từ summary.json và model_metadata.json "
     "trong experiments/rl_branch_evidence. File audit.json, replay và output từng ngày chỉ "
     "lưu tại máy. Script evaluate_legacy_branch.py --rl có thao tác đặt lại/nộp Practice; "
     "người chạy cần đọc phạm vi trước khi dùng. Script không huấn luyện mô hình và không "
     "được chạy nếu chỉ muốn xem lại số liệu. Các file dưới output/team_selection cũng chỉ "
     "lưu tại máy; người chạy cần tạo lại trước khi dùng các công cụ phụ thuộc chúng.")
add_reproduction(section, para, table)

# Đánh lại số theo thứ tự xuất hiện, đồng thời cập nhật các dẫn chiếu trong văn bản.
number_map = {}
captions = {}
counts = {"Bảng": 0, "Hình": 0}
for p in doc.paragraphs:
    match = re.match(r"^(Bảng|Hình) ([TX]?\d+)\. (.*)", p.text)
    if match:
        kind, original, text = match.groups()
        counts[kind] += 1
        number_map[(kind.lower(), original)] = str(counts[kind])
        captions[p._p] = (kind, str(counts[kind]), text)
for p in doc.paragraphs:
    if p._p in captions:
        kind, number, text = captions[p._p]
        p.text = f"{kind} {number}. {text}"
        for run in p.runs:
            clean_run(run)
            run.bold = kind == "Bảng"
    else:
        def replace_reference(match):
            kind, old = match.groups()
            return kind + " " + number_map.get((kind.lower(), old), old)
        for run in p.runs:
            updated = re.sub(r"(?i)\b(bảng|hình) (\d+)\b", replace_reference, run.text)
            if updated != run.text:
                run.text = updated

apply_readable_headers(doc, clean_run)
final_table_count = restructure_rl(doc, ROOT, section, para, table, clean_run)
from report_ablation import add_ablation
final_table_count = add_ablation(doc, ROOT, section, para, table, figure)

# Chuẩn hóa phần kế thừa, kể cả các run nằm trong hyperlink và footer.
for s in doc.sections:
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.top_margin, s.bottom_margin, s.left_margin, s.right_margin = Cm(2.5), Cm(2.5), Cm(3), Cm(2)
    s.header_distance = Cm(1.25)
    s.footer_distance = Cm(1.25)
    s.different_first_page_header_footer = False
for root in [doc.element, *[s.header._element for s in doc.sections], *[s.footer._element for s in doc.sections]]:
    for color in root.xpath('.//w:color'):
        color.set(qn("w:val"), "000000")
        for attribute in list(color.attrib):
            if attribute != qn("w:val"):
                del color.attrib[attribute]
    for border in list(root.xpath('.//w:pBdr')):
        border.getparent().remove(border)
for style in doc.styles:
    if hasattr(style, "element"):
        for border in list(style.element.xpath('.//w:pBdr')):
            border.getparent().remove(border)
        for color in style.element.xpath('.//w:color'):
            color.attrib.clear()
            color.set(qn("w:val"), "000000")
settings = doc.settings.element
update = settings.find(qn("w:updateFields"))
if update is None:
    update = OxmlElement("w:updateFields")
    settings.append(update)
update.set(qn("w:val"), "true")
doc.core_properties.title = title
doc.core_properties.author = "Kiều Thị Thu Trang; Trần Minh Sang"
destination = ROOT / "output/docx/bao_cao_hexudon.docx"
doc.save(destination)
assert hashlib.sha256(REFERENCE.read_bytes()).hexdigest() == EXPECTED_HASH
check = Document(destination)
assert len(check.sections) == 3
assert all(p.text != "NHÓM 2" for p in check.paragraphs)
assert sum(p.text.startswith("5. ") for p in check.paragraphs) == 1
assert len(check.tables) == final_table_count
assert sum(sum(d["mode"] == "rl" for d in r["days"]) for r in rl) == 43
(TMP / "build_audit.json").write_text(json.dumps({"reference_sha256": EXPECTED_HASH,
    "tables": len(check.tables), "sections": len(check.sections), "rl_questions": len(rl),
    "body_font": "Times New Roman", "body_size": 12.5, "line_spacing": 1.3,
    "table_size_range": [10.5, 11.5]}, indent=2), encoding="utf-8")
print(destination)
