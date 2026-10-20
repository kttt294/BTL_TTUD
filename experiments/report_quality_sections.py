"""Các mục báo cáo được tạo từ kết quả đối chứng tối ưu và độ nhạy."""

import json
from pathlib import Path


def add_method(section, para, figure):
    section('4.7. Quy hoạch động làm đối chứng tối ưu trên bài nhỏ', 2)
    para('Nhóm xây dựng thêm bộ giải chính xác để có một mốc chất lượng đã biết, thay vì chỉ '
         'so các heuristic với nhau hoặc chia điểm cho một cận còn lỏng. Bộ giải xét một xe '
         'tuần tra, không có xe tiếp tế và không có ô đường; bản đồ vẫn có thể chứa núi và ao. '
         'Nhiên liệu được dùng chung qua các ngày, tồn kho được bổ sung mỗi ngày và thứ tự '
         'ưu tiên (U, D, Q) được giữ nguyên. Đây là một phiên bản thu nhỏ của bài toán, không '
         'phải bộ giải tối ưu cho cấu hình nhiều xe của BTC. Bản đồ 2×2, 3×3 và một xe '
         'nằm ngoài dải kích thước và số xe của BTC; đây là phép đo thu nhỏ để kiểm tra '
         'thuật toán, không phải các input thi chính thức.')
    para('Tại một ngày và thời điểm đã dùng t step, khóa trạng thái gồm vị trí p, nhiên liệu '
         'còn lại f, tập loại toàn trận G, tập loại trong ngày C và tập điểm đã ghé W. Các tập '
         'được mã hóa bằng bitmask. Với cùng khóa, chương trình chỉ giữ cặp (D đã cộng từ '
         'các ngày trước, Q đã thu) lớn nhất theo thứ tự từ điển và lưu hành động để truy vết. '
         'Hai đường tới cùng khóa có tương lai giống nhau, nên đường có cặp giá trị nhỏ hơn '
         'không thể trở thành nghiệm tốt hơn sau khi nối cùng phần còn lại.')
    para('Ở mỗi trạng thái, chương trình xét chờ một step hoặc di chuyển theo một trong sáu '
         'hướng hợp lệ. Lệnh đi chỉ được sinh nếu còn đủ nhiên liệu và đủ thời gian hoàn tất '
         'trong ngày. Khi di chuyển nhiều step, xe có thể thu hàng ở ô nguồn trước khi đến '
         'ô đích; chương trình xử lý hai vị trí này theo đúng thứ tự thời gian. Lệnh chờ dài '
         'được thay bằng nhiều lệnh chờ một step mà không thay đổi kết quả trong phạm vi '
         'một xe, không tiếp tế và không có đường.')
    para('Khi hết ngày, chương trình cộng số bit của C vào D, giữ lại vị trí, nhiên liệu và G, '
         'sau đó đặt C và W về rỗng cho ngày mới. Khi hết trận, chương trình chọn trạng thái '
         'có (số bit của G, D, Q) lớn nhất. Mọi chuyển tiếp đều tăng thời gian, vì vậy các '
         'trạng thái tạo thành một đồ thị không chu trình theo thời điểm. Bằng quy nạp theo '
         'thời điểm và ngày, mọi chuỗi lệnh hợp lệ đều có chuyển tiếp tương ứng; quy tắc giữ '
         'giá trị tốt nhất chỉ bỏ những tiền tố không thể thắng khi có cùng tương lai. Hai '
         'điều này tạo cơ sở cho tính tối ưu của bộ giải trong phạm vi đã nêu.')
    para('Với H ngày, T step tối đa mỗi ngày, V ô, F nhiên liệu, B loại và S điểm bán, số '
         'khóa được chặn bởi O(H×T×V×(F+1)×2^(2B+S)). Mỗi khóa xét tối đa bảy hành động. '
         'Đây là cận theo toàn bộ không gian trạng thái, không phải số trạng thái thực được '
         'mở rộng. Bản cài đặt còn sao chép chuỗi truy vết khi tạo nhãn nên có thêm chi phí '
         'theo chiều dài lịch sử; nó phù hợp làm đối chứng bài nhỏ và không được đề xuất '
         'thay thế A* hoặc heuristic cho bản đồ 32×32.')
    para('Nhóm kiểm tra bộ giải theo hai hướng: so điểm với vét cạn chuỗi lệnh qua simulator '
         'trên sáu cấu hình có núi, ao và loại trùng; đồng thời phát lại nghiệm tối ưu của '
         'toàn bộ 24 bài đo để so điểm. Các phép kiểm tra không chứng minh simulator đúng '
         'trên mọi tình huống, nhưng giúp phát hiện sai khác giữa chuyển tiếp quy hoạch động '
         'và cơ chế thực thi trước khi dùng nghiệm làm mốc đánh giá.')


def add_protocol(section, para):
    section('6.5. Đối chứng tối ưu và thí nghiệm độ nhạy bổ sung', 2)
    meta = json.loads((Path(__file__).resolve().parent / 'quality_results/budgets_metadata.json').read_text(encoding='utf-8'))
    para(f"Đợt đo bổ sung chạy bằng Python {meta['python']} trên {meta['platform']}, "
         f"CPU được hệ thống nhận diện là {meta['processor']}. Nhóm lưu thông số này cùng "
         'CSV để phân biệt chênh lệch máy với chênh lệch thuật toán; các phép đo chạy trên '
         'CPU và không sử dụng GPU.')
    para('Nhóm dùng 24 bài nhỏ, gồm 12 seed từ 3100 đến 3111 cho mỗi cỡ 2×2 và 3×3. '
         'Mỗi bài có một xe tuần tra, hai ngày với sáu step mỗi ngày, bình nhiên liệu từ '
         '5 đến 7 và tối đa bốn điểm bán với ba loại udon. Bộ sinh cho phép núi; các ô '
         'xuất phát và điểm bán được đặt trên đồng bằng. Greedy và Lookahead nhận cùng '
         'input, cùng bình nhiên liệu và ngân sách 0,25 giây mỗi ngày. Input và hành động '
         'của cả nghiệm tối ưu lẫn hai heuristic được lưu trong bộ dữ liệu nhỏ đi kèm repo.')
    para('Chất lượng được đo bằng số bài khớp đúng bộ điểm tối ưu. Nhóm còn ghi độ thiếu '
         'hụt U; chỉ so độ thiếu hụt D trên những bài đã bằng U tối ưu, và chỉ so độ thiếu '
         'hụt Q khi cả U và D đều bằng tối ưu. Cách đánh giá có điều kiện này tránh cộng '
         'hoặc trung bình ba thành phần thành một điểm không đúng luật. Mẫu số của từng '
         'phép đo có điều kiện được ghi ngay trong bảng.')
    para('Thí nghiệm độ nhạy giữ 30 input tự sinh: 10 seed từ 2026 đến 2035 cho mỗi cỡ '
         '8×8, 16×16 và 32×32. Mỗi input được chạy với hai chiến lược ở bốn mức ngân sách '
         '0,05; 0,25; 1 và 3 giây mỗi ngày, tạo 240 trận và 960 kế hoạch ngày. Các trận '
         'đều có bốn xe với vai trò [0,0,0,1], bốn ngày, 80 step mỗi ngày và bình 40. '
         'Thứ tự chạy hai chiến lược được đảo giữa các seed. Mỗi chiến lược tự tạo lịch sử '
         'giao thông và tiêu hao nhiên liệu của mình; hai bộ không dùng chung trạng thái '
         'sau ngày đầu.')
    para('Các seed là đơn vị đối chứng; bốn mức thời gian trên cùng seed không được tính '
         'như bốn mẫu độc lập. Mỗi tổ hợp chỉ chạy một lần và chưa có đo lặp theo tải máy, '
         'nên kết quả mô tả xu hướng thực nghiệm, không kèm tuyên bố ý nghĩa thống kê. '
         'Số trung bình trên biểu đồ giúp quan sát riêng U, D và Q; kết luận thắng/thua '
         'vẫn dựa vào bộ điểm của từng cặp, không dựa vào việc cộng các đường biểu diễn.')


def add_results(root, section, para, table, figure):
    data = json.loads((root / 'experiments/quality_results/summary.json').read_text(encoding='utf-8'))
    section('7.6. Khoảng cách tới nghiệm tối ưu trên 24 bài nhỏ', 2)
    rows = []
    for r in data['exact']:
        rows.append([f"{r['size']}×{r['size']} / {r['strategy']}", f"{r['optimal']}/{r['n']}",
                     f"{r['mean_u_gap']:.2f}",
                     f"{r['mean_d_gap_given_u']:.2f} (n={r['same_u']})",
                     f"{r['mean_q_gap_given_ud']:.2f} (n={r['same_ud']})" if r['same_ud'] else 'Không có mẫu'])
    table('Bảng 19. Chất lượng so với nghiệm tối ưu chính xác',
          ['Cỡ / chiến lược', 'Khớp tối ưu', 'Thiếu U TB', 'Thiếu D khi U bằng', 'Thiếu Q khi U,D bằng'],
          rows, [4, 2.5, 2.5, 3.5, 3.5], 10.5)
    totals = {strategy: sum(r['optimal'] for r in data['exact'] if r['strategy'] == strategy)
              for strategy in ('greedy', 'lookahead')}
    para(f"Trên 24 input nhỏ, Greedy khớp bộ điểm tối ưu ở {totals['greedy']} bài, còn "
         f"Lookahead khớp ở {totals['lookahead']} bài. Cả hai đều đạt U tối ưu trên toàn "
         'bộ input nhưng vẫn có thể bỏ lỡ tổng loại theo ngày D hoặc số suất Q. Vì vậy, '
         'chỉ nhìn số loại toàn trận có thể tạo cảm giác thuật toán đã đạt tối ưu dù '
         'vẫn tồn tại một hành trình tốt hơn. Lợi thế của Lookahead trên bộ nhỏ này '
         'không mâu thuẫn với kết quả kém hơn ở nhiều bản đồ lớn, vì quy mô bài và '
         'chi phí tìm kiếm dưới deadline là những yếu tố khác nhau.')
    para(f"Bộ giải mở rộng nhiều nhất {data['dp_max_states']:,} trạng thái và mất nhiều nhất "
         f"{data['dp_max_seconds'] * 1000:.2f} ms trong bộ đo này. Tất cả 24 nghiệm được phát "
         'lại hợp lệ và khớp điểm. Chi phí nhỏ ở đây đến từ phạm vi một xe và bản đồ rất '
         'nhỏ; nó không cho phép suy ra quy hoạch động vẫn chạy nhanh khi tăng số xe hoặc '
         'số điểm bán.')
    figure('tiny_optimal_routes.png', 'Hình 3. Ví dụ 3×3, seed 3103: nét liền/ngắt chỉ ngày 1/2; ô 2* là xuất phát.', 16)
    para('Ở ví dụ trong hình 3, ba phương án đạt lần lượt (3,5,5), (3,5,6) và (3,5,7). '
         'Chúng bằng nhau ở U và D nên có thể so trực tiếp số suất: Greedy thiếu hai suất, '
         'còn Lookahead thiếu một suất so với tối ưu. Nghiệm DP ngày đầu dùng [5,5,4], '
         'ngày hai dùng [1,2,3]. Từ ô xuất phát 2, tuyến ngày đầu đi qua 1, 0, 3; tuyến '
         'ngày hai đi qua 0, 1, 5. Các ô có loại trùng vẫn có thể tăng Q mà không tăng U. '
         'Ví dụ này minh họa lợi ích nhìn trước và giới hạn của nó, thay vì chỉ nói rằng '
         'một thuật toán phức tạp hơn sẽ tốt hơn.')
    section('7.7. Chất lượng theo ngân sách tính toán', 2)
    rows = [[f"{r['size']}×{r['size']}", f"{r['budget']:g}", r['wins'], r['ties'], r['losses'],
             f"{r['means']['greedy']['searches']:.0f} / {r['means']['lookahead']['searches']:.0f}"]
            for r in data['budget_comparisons']]
    table('Bảng 20. Lookahead đối chiếu Greedy trên cùng input và cùng ngân sách',
          ['Cỡ', 'Giây/ngày', 'Thắng', 'Hòa', 'Thua', 'Truy vấn TB G / L'],
          rows, [2.4, 2.4, 2, 2, 2, 5.2], 10.5)
    figure('budget_sensitivity.png', 'Hình 4. Điểm trung bình của 10 input mỗi cỡ ở bốn mức thời gian.', 16)
    totals = []
    for budget in (.05, .25, 1., 3.):
        entries = [r for r in data['budget_comparisons'] if r['budget'] == budget]
        w, t, l = (sum(r[k] for r in entries) for k in ('wins', 'ties', 'losses'))
        totals.append(f"{budget:g} giây: {w} thắng, {t} hòa, {l} thua")
    para('Khi tổng hợp 30 cặp mỗi mức, Lookahead có kết quả như sau: ' + '; '.join(totals) +
         '. Số cặp thắng tăng từ 3 lên 11 khi chuyển từ 0,05 lên 3 giây/ngày, trong khi '
         'số cặp thua giảm từ 22 xuống 14. Điều này hỗ trợ nhận định rằng ngân sách tính '
         'toán ảnh hưởng tới Lookahead trong bản cài đặt đang xét, nhưng chưa đủ để gọi '
         'nó là phương pháp vượt Greedy ổn định. Đợt đo này được tách khỏi bảng 8 vì các '
         'quyết định theo đồng hồ có thể đổi giữa hai lần chạy.')
    para('Ở 8×8, chất lượng gần chững lại khi tăng ngân sách từ 1 lên 3 giây; cấp thêm '
         'thời gian không còn tạo lợi ích rõ như khi tăng từ 0,05 lên 0,25 giây. Ở 32×32 '
         'với 3 giây/ngày, Lookahead có D trung bình 44,2 và Q trung bình 66,0, cao hơn '
         '44,0 và 65,2 của Greedy, nhưng U trung bình lại thấp hơn (11,8 so với 11,9). '
         'Vì U được ưu tiên trước, hai cột D và Q không đủ để tuyên bố Lookahead tốt hơn; '
         'đối chứng từng cặp ở mức này cho kết quả 5 thắng và 5 thua.')
    para(f"Cả {data['budget_games']} trận mới đều được mô phỏng hợp lệ; bộ lập kế hoạch có "
         f"{data['fallbacks']} lần dự phòng. Việc tăng ngân sách không bảo đảm điểm tăng "
         'đơn điệu: thời gian thay đổi số ứng viên được đánh giá, tuyến đã chọn và giao '
         'thông các ngày sau. Bảng 20 cần được đọc cùng hình 4 để phân biệt lợi ích về '
         'loại với lợi ích về suất. Số truy vấn A* tăng cũng chưa tự chứng minh là nguyên '
         'nhân giảm điểm, vì độ khó và độ dài từng truy vấn khác nhau.')


def add_reproduction(section, para, table):
    section('B.3. Phạm vi dữ liệu bàn giao và phép đo mới', 2)
    table('Bảng B1. Dữ liệu đi kèm repo và dữ liệu chỉ lưu tại máy',
          ['Nhóm dữ liệu', 'Có trong repo', 'Cách kiểm tra hoặc tái tạo'],
          [['Input, nghiệm DP và hai heuristic của 24 bài nhỏ', 'Có', 'quality_results/tiny_*.json; chạy verify_quality.py'],
           ['240 dòng kết quả độ nhạy và thông số máy', 'Có', 'quality_results/budgets.csv và budgets_metadata.json'],
           ['Kết quả tổng hợp BTC, checkpoint metadata', 'Có', 'Các summary.json; đối chiếu bảng điểm và nguồn API'],
           ['Replay, request/response từng ngày và output nộp BTC', 'Không', 'Lưu tại máy; xem API bằng tài khoản có quyền hoặc thu lại'],
           ['Mô hình RL và snapshot mã nhánh Procon2026', 'Không', 'Lấy từ nhánh/commit và đường dẫn checkpoint ở mục 5.4']],
          [5, 2.5, 8.5], 10.5)
    for command in ['python -X utf8 experiments/benchmark_quality.py --mode exact --cases 12',
                    'python -X utf8 experiments/verify_quality.py',
                    'python -X utf8 experiments/benchmark_quality.py --mode budgets --cases 10',
                    'python -X utf8 experiments/summarize_quality.py']:
        p = para(command)
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    para('Các lệnh mới chạy offline và không gọi API. Hai bộ đo chỉ cần thư viện chuẩn; '
         'lệnh vẽ hình cần Matplotlib. Dữ liệu tiny đi kèm cho phép chấm lại chính xác các '
         'chuỗi lệnh đã báo cáo, còn phép đo ngân sách lưu CSV và seed, không lưu toàn bộ '
         'chuỗi lệnh của 240 trận. Chạy lại phép đo theo thời gian thực có thể làm đổi điểm '
         'và không được cam kết tái tạo từng chữ số trong bảng. Khi kiểm tra lại, người '
         'dùng nên sao lưu CSV trước khi chạy vì script ghi kết quả mới vào cùng thư mục.')
