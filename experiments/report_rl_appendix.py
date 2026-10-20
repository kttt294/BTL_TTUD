"""Tách toàn bộ mô tả và kết quả RL khỏi phần chính, giữ đối chứng thuật toán độc lập."""

import json
import re
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH


def node_text(element):
    return ''.join(element.xpath('.//w:t/text()'))


def restructure_rl(doc, root, section, para, table, clean_run):
    body = doc.element.body

    def take(begin, end):
        children = list(body)
        first = next(i for i, e in enumerate(children) if node_text(e) == begin)
        last = next(i for i, e in enumerate(children) if i > first and node_text(e) == end)
        nodes = children[first:last]
        for node in nodes:
            body.remove(node)
        return nodes

    architecture = take('5. Ứng dụng các thuật toán trong phương pháp kết hợp RL',
                        '6. Thiết kế thực nghiệm và độ tin cậy của phép đo')[1:]
    protocol = take('6.4. Điều kiện riêng của đối chứng RL',
                    '6.5. Đối chứng tối ưu và thí nghiệm độ nhạy bổ sung')
    old_results = take('7.4. Đối chứng checkpoint RL kết hợp Greedy',
                       '7.5. Chi phí kiểm tra và bằng chứng tương thích')
    rl_references = []
    for p in list(doc.paragraphs):
        if re.match(r'^\[(7|8|9)\] ', p.text):
            rl_references.append(p._p)
            body.remove(p._p)

    # Chỉ giữ các nhóm thuật toán truyền thống trong bảng phạm vi và bảng thực nghiệm chính.
    for t in doc.tables:
        for row in list(t.rows[1:]):
            if row.cells[0].text in ('Ứng dụng trong hệ thống có học máy', 'RL kết hợp'):
                t._tbl.remove(row._tr)

    section_map = {'5': 'C', **{f'5.{i}': f'C.{i}' for i in range(1, 6)},
                   '6': '5', '6.1': '5.1', '6.2': '5.2', '6.3': '5.3',
                   '6.4': 'C.6', '6.5': '5.4', '7': '6', '7.1': '6.1',
                   '7.2': '6.2', '7.3': '6.3', '7.4': 'C.7', '7.5': '6.4',
                   '7.6': '6.5', '7.7': '6.6', '8': '7',
                   **{f'8.{i}': f'7.{i}' for i in range(1, 5)}}
    all_nodes = [*list(body), *architecture, *protocol, *old_results, *rl_references]
    heading_ids = {doc.styles[f'Heading {i}'].style_id for i in (1, 2, 3)}
    reference_map = {'7': 'C1', '8': 'C2', '9': 'C3', '10': '7', '11': '8'}
    for node in all_nodes:
        if node.tag == qn('w:p'):
            style = node.find('w:pPr/w:pStyle', namespaces=node.nsmap)
            if style is not None and style.get(qn('w:val')) in heading_ids:
                texts = node.xpath('.//w:t')
                if texts:
                    match = re.match(r'^(\d+(?:\.\d+)*)\. ', texts[0].text or '')
                    if match and match[1] in section_map:
                        texts[0].text = section_map[match[1]] + texts[0].text[len(match[1]):]
        for text in node.xpath('.//w:t'):
            text.text = re.sub(r'(?i)\b(mục|chương) (\d+(?:\.\d+)*)\b',
                               lambda m: m[1] + ' ' + section_map.get(m[2], m[2]), text.text or '')
            text.text = re.sub(r'\[(7|8|9|10|11)\]', lambda m: '[' + reference_map[m[1]] + ']', text.text)

    def replace_paragraph(p, value):
        p.text = value
        for run in p.runs:
            clean_run(run)

    for p in list(doc.paragraphs):
        text = p.text
        if text.startswith('Phần mở rộng đánh giá checkpoint MAPPO'):
            replace_paragraph(p, 'Học tăng cường được xem là một hướng mở rộng đáng thử. '
                              'Nhóm tách toàn bộ mô tả và kết quả thử nghiệm hướng này vào phụ lục C, '
                              'để phần chính tập trung vào các thuật toán của môn học.')
        elif text.startswith('Các câu hỏi chính được đặt ra:'):
            replace_paragraph(p, 'Các câu hỏi chính được đặt ra là: A* giảm lượng tìm kiếm so với '
                              'Dijkstra ra sao khi có giới hạn nhiên liệu; Lookahead có tăng điểm so '
                              'với Greedy trong cùng ngân sách không; chọn vai trò xe theo mô phỏng có '
                              'tốt hơn đội hình cố định không; và các heuristic còn cách nghiệm tối ưu '
                              'bao xa trên bài thu nhỏ. Mỗi câu hỏi được đánh giá ở đúng lớp quyết định, '
                              'tránh lấy đường đi ngắn để suy ra điểm toàn trận tối ưu.')
        elif text.startswith('Sản phẩm gồm năm thuật toán'):
            replace_paragraph(p, text.split(' Phần RL')[0])
        elif text.startswith('Báo cáo đi từ mô hình tối thiểu'):
            replace_paragraph(p, 'Mục 2 giới thiệu đề bài và mô hình tài nguyên. Mục 3 trình bày '
                              'các thuật toán tìm đường, còn mục 4 xây dựng chiến lược lập kế hoạch '
                              'và chọn đội hình. Mục 5 xác định các phép đối chứng; mục 6 phân tích '
                              'kết quả; mục 7 tổng hợp giới hạn và hướng phát triển. Phụ lục cung cấp '
                              'chi tiết thực thi và hướng dẫn tái hiện để phần chính tập trung vào '
                              'các quyết định thuật toán.')
        elif 'Lookahead và RL đang thử' in text:
            replace_paragraph(p, text.replace('Lookahead và RL đang thử', 'Lookahead đang thử'))
        elif text.startswith('Phần RL chỉ có một checkpoint'):
            replace_paragraph(p, 'Toàn bộ đánh giá chiến lược chính hiện tại thuộc phạm vi một đội. '
                              'Khả năng nhiều đội của simulator chưa được đối chiếu với replay BTC '
                              'nhiều đội. Mức tương thích API chỉ được khẳng định trong phạm vi kế '
                              'hoạch và luật đã kiểm tra, không phải trên mọi trạng thái có thể có.')
        elif text.startswith('Ở hướng RL, nhóm có thể thử'):
            replace_paragraph(p, 'Học tăng cường là một hướng đáng thử để hỗ trợ lựa chọn mục tiêu '
                              'hoặc hành trình. Các thử nghiệm mở rộng được tách vào phụ lục C và '
                              'không làm thay đổi trọng tâm đánh giá các thuật toán của môn học.')
        elif text.startswith('Đề tài cho thấy một bài toán'):
            replace_paragraph(p, text.split(' Phần kết hợp RL')[0])
        elif text.startswith('Nhóm kết quả RL đi kèm repo'):
            body.remove(p._p)
        elif 'nhánh cũ, RL và chọn đội hình' in text:
            replace_paragraph(p, text.replace('nhánh cũ, RL và chọn đội hình', 'nhánh cũ và chọn đội hình'))
        elif 'Bộ kiểm thử có 47 phương thức' in text:
            replace_paragraph(p, text.replace('Bộ kiểm thử có 47 phương thức', 'Bộ kiểm thử lõi có 47 phương thức'))

    section('Phụ lục C. Thử nghiệm mở rộng với học tăng cường')
    para('Phụ lục này lưu phần phát triển thêm ngoài trọng tâm của bài tập lớn. Mục tiêu là '
         'kiểm tra khả năng dùng mô hình đã học để đề xuất kế hoạch, trong khi A*, heuristic '
         'và simulator vẫn đảm nhiệm việc tạo tuyến và kiểm tra ràng buộc. Những điểm số ở '
         'đây không thay thế các phép so sánh thuật toán truyền thống trong phần chính.')
    for node in [*architecture, *protocol, *old_results]:
        body.insert(len(body) - 1, node)
    add_extension_results(root, section, para, table)
    from report_rl_policy import add_policy_results
    add_policy_results(root, section, para, table)
    section('C.11. Tài liệu tham khảo riêng của phần mở rộng', 2)
    for node in rl_references:
        body.insert(len(body) - 1, node)

    # Sau khi chuyển chương, đánh lại số bảng phần chính và số bảng riêng ở phụ lục C.
    mapping, main_count, appendix_count, in_c = {}, 0, 0, False
    captions = {}
    for p in doc.paragraphs:
        if p.text.startswith('Phụ lục C.'):
            in_c = True
        match = re.match(r'^Bảng (\d+)\. (.*)', p.text)
        if match:
            if in_c:
                appendix_count += 1
                number = f'C{appendix_count}'
            else:
                main_count += 1
                number = str(main_count)
            mapping[match[1]] = number
            captions[p._p] = f'Bảng {number}. {match[2]}'
    for p in doc.paragraphs:
        if p._p in captions:
            replace_paragraph(p, captions[p._p])
            for run in p.runs:
                run.bold = True
        else:
            for run in p.runs:
                updated = re.sub(r'(?i)\bbảng (\d+)\b',
                                 lambda m: m[0].split(' ')[0] + ' ' + mapping.get(m[1], m[1]), run.text)
                if updated != run.text:
                    run.text = updated
    # Giữ nguồn checkpoint ở bảng tài nguyên trỏ đúng vị trí mới trong phụ lục.
    return len(doc.tables)


def add_extension_results(root, section, para, table):
    folder = root / 'experiments/rl_extension_results'
    rows = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    variants = ('greedy', 'rollout_no_rl', 'rl_daily', 'rl_rollout')
    questions = sorted({r['question'] for r in rows})
    assert len(rows) == len(questions) * 4 == 36
    lookup = {(r['question'], r['variant']): r for r in rows}
    fmt = lambda value: '(' + ', '.join(map(str, value)) + ')'
    section('C.8. Đối chứng hệ thống lai có chọn lại bằng heuristic', 2)
    para('Các kết quả ở mục này thuộc hệ thống lai, chưa phải kết quả riêng của chính '
         'sách RL. Bộ chọn có thể dùng heuristic hoặc kế hoạch dự phòng mà không dùng '
         'mục tiêu mạng đề xuất. Thí nghiệm học lại không chọn thay bằng heuristic được '
         'trình bày riêng ở mục C.10; hai nhóm kết quả không được gộp để kết luận RL cải thiện.')
    para('Lượt mở rộng giữ nguyên checkpoint episode_256.pt và không cập nhật trọng số. '
         'Mô hình tạo một bộ mục tiêu xác định và thêm ba bộ mục tiêu lấy mẫu cho cả đội. '
         'Các bộ trùng nhau được bỏ; các chuỗi hành động trùng nhau với heuristic cũng '
         'không được tính lại như một ứng viên RL mới. Mỗi ứng viên vẫn được chuyển thành '
         'tuyến bằng A* và heuristic điểm phụ của nhánh gốc. Khác lượt cũ, việc thực thi '
         'và đánh giá dùng simulator TTUD đã đối chiếu với máy chủ.')
    para('Bộ chọn nhiều ngày bắt đầu bằng một kế hoạch Greedy hoàn chỉnh cho cả trận. '
         'Tại mỗi ngày, nó thử kế hoạch Greedy, Lookahead và các ứng viên RL của ngày hiện '
         'tại, rồi nối mỗi ứng viên với Greedy tới cuối trận. Chỉ mô phỏng hoàn tất và hợp '
         'lệ mới được so theo (U,D,Q). Nếu phương án mới tốt hơn, bộ chọn thay kế hoạch '
         'đang giữ; nếu không, nó tiếp tục dùng kế hoạch cũ. Sau khi thực thi ngày đầu, '
         'phần kế hoạch còn lại được giữ làm dự phòng cho ngày sau.')
    para('Trong môi trường một đội với đúng luật mô phỏng và đầu vào không thay đổi, '
         'cách giữ kế hoạch bảo đảm điểm dự đoán cuối trận không giảm so với kế hoạch '
         'Greedy khởi tạo đã lưu. Đây là tính chất của bộ chọn và simulator, không phải '
         'bảo đảm riêng của mạng RL. Khi có đội khác làm thay đổi giao thông, lập luận '
         'này không còn tự áp dụng nếu thiếu dự báo đối thủ.')
    para('Thí nghiệm dùng chín nhãn bài cấu hình BTC, cùng vai trò toàn tuần tra và một '
         'kế hoạch Greedy khởi tạo được chia sẻ giữa bốn biến thể trên từng input. Greedy '
         'nền chỉ thực thi kế hoạch khởi tạo; rollout không RL dùng hai heuristic để cải '
         'thiện kế hoạch; RL một ngày chọn theo điểm sau ngày hiện tại; RL nhiều ngày '
         'dùng cả ứng viên mô hình và cơ chế giữ kế hoạch tới cuối trận. Q01/Q02 trùng '
         'cấu hình nên không được tính như hai mẫu dữ liệu độc lập.')
    para('Ngân sách lập kế hoạch hiện tại là 0,12 giây cho mỗi heuristic; phần nối các '
         'ngày sau dùng 0,03 giây mỗi ngày. Bộ chọn có hạn mềm 20 giây mỗi ngày. Mô hình '
         'chạy trên CPU với PyTorch một luồng, seed lấy mẫu là 4200 cộng số bài và chỉ '
         'số ngày. Số ứng viên và thời gian tính toán của bản có RL lớn hơn bản không '
         'RL; do đó, so sánh này đánh giá cấu hình hoàn chỉnh, chưa cô lập hoàn toàn '
         'tác động của chính sách học khỏi lượng tính toán bổ sung.')
    table('Bảng C5. Điểm offline của bốn biến thể trong lượt mở rộng',
          ['Mã bài thử nghiệm', 'Greedy khởi tạo (U,D,Q)', 'Mô phỏng nhiều ngày không RL (U,D,Q)',
           'RL chọn theo điểm một ngày (U,D,Q)', 'RL chọn theo mô phỏng cuối trận (U,D,Q)'],
          [[q, *[fmt(lookup[q, v]['score']) for v in variants]] for q in questions],
          [1.6, 3.6, 3.6, 3.6, 3.6], 10.5)
    for baseline in ('greedy', 'rollout_no_rl', 'rl_daily'):
        names = {'greedy': 'Greedy khởi tạo', 'rollout_no_rl': 'rollout không RL', 'rl_daily': 'RL chọn theo điểm một ngày'}
        pairs = [(tuple(lookup[q, 'rl_rollout']['score']), tuple(lookup[q, baseline]['score'])) for q in questions]
        wins = sum(a > b for a, b in pairs)
        ties = sum(a == b for a, b in pairs)
        para(f"So với {names[baseline]}, cấu hình RL chọn tới cuối trận tốt hơn ở {wins} bài, "
             f"bằng ở {ties} bài và kém hơn ở {len(pairs)-wins-ties} bài trong bộ đo offline này.")
    metric_rows = []
    labels = {'rollout_no_rl': 'Mô phỏng nhiều ngày không RL', 'rl_daily': 'RL chọn theo điểm một ngày',
              'rl_rollout': 'RL chọn theo mô phỏng cuối trận'}
    for variant in variants[1:]:
        subset = [r for r in rows if r['variant'] == variant]
        metric_rows.append([labels[variant], len(subset), sum(r['selected_rl_days'] for r in subset),
                            f"{max(r['max_decision_seconds'] for r in subset):.3f}"])
    table('Bảng C6. Tần suất dùng ứng viên RL và chi phí chọn kế hoạch',
          ['Cấu hình bộ chọn', 'Số trận được đánh giá', 'Tổng số ngày chọn ứng viên RL',
           'Thời gian chọn kế hoạch ngày lớn nhất (giây)'], metric_rows, [5.5, 3, 3.5, 4], 10.5)
    rl_days = sum(r['selected_rl_days'] for r in rows if r['variant'] == 'rl_rollout')
    para(f"Bản RL nhiều ngày chọn ứng viên mang nguồn RL ở {rl_days} ngày. Các ngày còn "
         'lại dùng heuristic hoặc phần kế hoạch đang giữ. Nếu bản có RL đạt điểm cao hơn '
         'ở một bài nhưng không chọn ứng viên RL nào, kết quả đó không chứng minh mô '
         'hình đã giúp tăng điểm; deadline của các lần lập kế hoạch heuristic có thể '
         'làm thay đổi tuyến. Muốn quy nguyên nhân cho RL cần thêm đối chứng với bộ '
         'tạo tuyến xác định, nhiều seed lấy mẫu và ngân sách tính toán cân bằng.')
    para('Thời gian ở bảng C6 đo bước chọn kế hoạch ngày, gồm tạo ứng viên và đánh giá '
         'phần tương lai; chưa gồm tải checkpoint, tạo kế hoạch Greedy khởi tạo, truyền '
         'mạng hoặc tải replay. Những giới hạn này cần được giữ khi so với hạn nộp '
         '30 giây. Nhóm đã bổ sung ba kiểm thử cho việc giữ dự phòng, nhận cải thiện và '
         'loại mô phỏng dở hoặc sai; bộ kiểm thử tại thời điểm lượt này có 50 phương thức.')
    evidence_path = root / 'experiments/rl_extension_api_evidence/summary.json'
    if evidence_path.exists():
        verified = json.loads(evidence_path.read_text(encoding='utf-8'))
        table('Bảng C7. Kế hoạch mở rộng được máy chủ Ban tổ chức kiểm chứng',
              ['Mã bài thử nghiệm', 'Điểm máy chủ trả về (U,D,Q)', 'Số kế hoạch ngày được nhận',
               'Số khung trạng thái đối chiếu', 'Số sai khác với máy chủ'],
              [[r['question'], fmt(r['server_score']), r['accepted_days'], r['checked_frames'], r['mismatches']] for r in verified],
              [2, 4.8, 3, 3.4, 2.8], 10.5)
        para('Các điểm trong bảng C7 được máy chủ Practice riêng của đội chấm trực tiếp; '
             'những điểm còn lại ở bảng C5 vẫn là điểm offline. Nhóm lưu lịch sử trận '
             'trước khi đặt lại Practice, đối chiếu các mảng lệnh đã nộp và chạy lại '
             'replay bằng simulator TTUD để kiểm tra vị trí, nhiên liệu, thu hàng và '
             'giao thông. Đây không phải kết quả Mock Contest hoặc trận nhiều đội. '
             'Practice có thể chỉ hiển thị lượt gần nhất sau khi reset; các lượt cũ '
             'trong báo cáo được đối chiếu bằng bằng chứng JSON đã lưu riêng, không '
             'suy từ trạng thái đang hiển thị trên website.')
    section('C.9. Tái hiện thí nghiệm mở rộng', 2)
    for command in ['python -X utf8 experiments/rl_extension.py',
                    'python -X utf8 experiments/audit_rl_extension.py']:
        para(command).alignment = WD_ALIGN_PARAGRAPH.LEFT
    para('Các lệnh này chạy offline. Người dùng cần PyTorch và các phụ thuộc của nhánh '
         'Procon2026, bản chụp mã nguồn và checkpoint đúng đường dẫn ở mục C.4, cùng '
         'các cấu hình BTC đã tải trong experiments/rl_branch_evidence. File summary.json, '
         'metadata.json và audit.json của lượt mới nằm trong experiments/rl_extension_results; '
         'kế hoạch và nhật ký chi tiết chỉ lưu tại máy theo quy tắc Git ignore.')
    para('Script verify_rl_extension_server.py có thao tác đặt lại và nộp Practice riêng '
         'cho các bài được chỉ định; nó chỉ dùng khi cần chấm máy chủ, không dùng để xem '
         'lại số liệu offline. Bằng chứng API của lượt mở rộng được tách trong '
         'experiments/rl_extension_api_evidence. Các thử nghiệm mới chưa huấn luyện lại '
         'mạng, chưa cho RL điều khiển từng hướng và chưa áp dụng đội hình có xe tiếp tế.')
