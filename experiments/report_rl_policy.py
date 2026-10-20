"""Bổ sung kết quả PPO học mới vào phụ lục, không đổi dữ liệu các chương chính."""

import json
from statistics import mean
from docx.enum.text import WD_ALIGN_PARAGRAPH


def add_policy_results(root, section, para, table):
    folder = root/'experiments/rl_policy_results'
    if not (folder/'evaluation_audit.json').exists():
        raise FileNotFoundError('Chưa hoàn tất đánh giá RL; không đưa số liệu dở vào báo cáo.')
    meta = json.loads((folder/'training_metadata.json').read_text(encoding='utf8'))
    rows = json.loads((folder/'evaluation_summary.json').read_text(encoding='utf8'))
    audit = json.loads((folder/'evaluation_audit.json').read_text(encoding='utf8'))
    fmt = lambda v: '('+', '.join(map(str,v))+')'
    section('C.10. Huấn luyện PPO và đánh giá không chọn thay bằng heuristic', 2)
    para('Lượt thử mới xây dựng một chính sách PPO từ khởi tạo ngẫu nhiên, không tải '
         'checkpoint episode_256.pt và không học bắt chước nhãn Greedy. Mục tiêu là '
         'đánh giá phần ra quyết định thực sự của mạng, thay vì coi điểm của cả bộ chọn '
         'nhiều ứng viên là điểm riêng của RL. Mỗi lần xe cần một mục tiêu mới trong ngày, '
         'mạng chọn một điểm bán hoặc hành động chờ. Nhóm đo riêng cách lấy argmax và '
         'cách lấy một mẫu từ phân phối; cả hai đều không thử nhiều phương án rồi chọn '
         'theo điểm simulator.')
    para('Dijkstra chỉ tạo một đường ít step cố định đến mỗi đích. Bộ thực thi loại '
         'đích nếu đường đó vượt nhiên liệu còn lại, lấy tiền tố liên tục khi không đủ '
         'step trong ngày và thêm lệnh chờ cho phần còn thiếu. Nó không gọi Greedy, '
         'Lookahead, heuristic điểm phụ hay kế hoạch dự phòng. Nếu kiểm tra cuối phát '
         'hiện kế hoạch sai, thí nghiệm dừng và báo lỗi. Do đó, đây là RL chọn mục tiêu '
         'kết hợp thuật toán tìm đường, chưa phải RL học từng hướng 0–5. Đường cố định '
         'cũng có thể bỏ sót một đường dài hơn nhưng ít tốn nhiên liệu hơn; nhóm chưa '
         'tuyên bố mặt nạ tìm được mọi đích khả thi.')
    para('Mạng dùng chung cho các xe và chấm từng ứng viên bằng 18 đặc trưng, gồm '
         'tình trạng loại udon đã thu, kho, chi phí đường đi, nhiên liệu, quỹ bước, '
         'ngày hiện tại, vị trí và mật độ điểm bán lân cận. Hai tầng 64 nút Tanh tạo '
         'biểu diễn; actor chấm từng đích và critic lấy trung bình biểu diễn của các '
         'ứng viên hợp lệ. Danh sách không bị cắt theo thứ tự ưu tiên Greedy. Việc '
         'đặt chỗ tạm để các xe tránh chọn cùng kho là quy tắc chung của bộ thực thi; '
         'reward chỉ lấy từ simulator sau khi thực thi đồng thời cả đội.')
    para('Tập học gồm 48 bản đồ sinh riêng với seed 61000–61047, lần lượt luân phiên '
         'kích thước 8×8, 12×12 và 16×16. Mỗi trận có sáu ngày, 80 step/ngày, nhiên liệu '
         '100 và bốn xe tuần tra. Ba seed khởi tạo mạng là 71, 72 và 73; mỗi seed học '
         f"{meta['episodes_per_seed']} trận. Nhóm dùng checkpoint cuối theo số trận đã định, "
         'không chọn checkpoint hoặc seed theo điểm BTC. Reward tại cuối ngày là '
         '10ΔU + ΔD + 0,05ΔQ, lấy từ điểm thật của simulator TTUD. Tổng có trọng số '
         'này là mục tiêu học gần đúng, không tương đương thứ tự từ điển trong mọi trường hợp.')
    para('PPO dùng learning rate 0,0003; gamma 0,99; GAE lambda 0,95; clip 0,2; '
         'bốn lượt cập nhật mỗi nhóm tám trận, minibatch 256, hệ số entropy 0,01, '
         'hệ số value loss 0,001 và giới hạn norm gradient 0,5. Mạng chạy CPU một '
         'luồng bằng PyTorch '+meta['torch_version']+'. Đo thử cho thấy cấu hình nhỏ '
         'này đủ nhanh trên CPU nên lượt học không sử dụng Kaggle hoặc GPU. Phương '
         'pháp cập nhật chính sách tham khảo PPO [C1]; mô hình, đặc trưng và môi trường '
         'huấn luyện trong lượt này do nhóm cài đặt.')
    table('Bảng C8. Nhật ký huấn luyện mới và bằng chứng trọng số đã thay đổi',
          ['Seed khởi tạo', 'Số trận đã học', 'Số nhóm cập nhật PPO',
           'Số quyết định lấy mẫu', 'Số tensor trọng số thay đổi', 'Thời gian học CPU (giây)'],
          [[r['seed'],r['episodes'],r['updates'],r['decisions'],r['changed_tensors'],f"{r['seconds']:.1f}"]
           for r in meta['runs']], [1.6,2.4,2.9,3.1,3.2,2.8],10.5)
    para('Tập kiểm tra gồm chín nhãn bài BTC đã tải và các bản đồ sinh riêng với '
         'seed 91000–91003 ở kích thước 8×8, 16×16 và 32×32. Không có bản đồ kiểm tra '
         'nào được đưa vào vòng học. Q01/Q02 trùng cấu hình nên không tạo thành hai '
         'mẫu độc lập. Bản đồ 32×32 và các trận BTC có khác biệt kích thước hoặc số '
         'ngày so với tập học; vì vậy nhóm báo cáo riêng dữ liệu sinh và dữ liệu BTC '
         'để người đọc thấy giới hạn khái quát hóa.')
    para('Các biến thể dùng chung mặt nạ và bộ thực thi: mạng sau PPO; đúng mạng tại '
         'thời điểm trước PPO; chọn ngẫu nhiên đều trong tập hành động hợp lệ kể cả '
         'chờ; và chọn đích có đường ít step nhất. Biến thể gần nhất là đối chứng '
         'riêng, không được gọi bên trong RL. Mỗi lượt đo khởi tạo lại bộ nhớ đệm '
         'đường đi để hạn chế lợi thế chạy sau. Thời gian chưa bao gồm tải checkpoint '
         'hoặc giao tiếp máy chủ. Toàn bộ điểm mới dưới đây là điểm simulator offline, '
         'không phải điểm máy chủ BTC và không phải kết quả Mock Contest.')
    para('Sau khi chẩn đoán argmax của seed 71 chọn chờ trên Q04 và bản đồ sinh '
         '8×8 seed 91000, nhóm bổ sung cách lấy mẫu cho cả mạng trước và sau học. '
         'Mỗi lần quyết định chỉ lấy đúng một mẫu, không chọn tốt nhất trong nhiều '
         'mẫu. Seed đánh giá gắn với seed mạng để tái hiện; mỗi cặp trước/sau học '
         'khởi tạo lại cùng seed. Đây là phân tích bổ sung sau quan sát; nhóm không '
         'thay đổi quá trình học hoặc chọn checkpoint dựa trên các điểm chẩn đoán.')
    lookup = {(r['case'],r['variant'],r['seed']):r for r in rows}
    questions = sorted({r['case'] for r in rows if r['group']=='official'})
    table('Bảng C9. Điểm RL lấy mẫu một lần mỗi quyết định trên cấu hình BTC',
          ['Mã bài kiểm tra', 'RL lấy mẫu seed 71 (U,D,Q)', 'RL lấy mẫu seed 72 (U,D,Q)',
           'RL lấy mẫu seed 73 (U,D,Q)', 'Chọn đích gần nhất cùng bộ thực thi (U,D,Q)'],
          [[q,*[fmt(lookup[q,'trained_sampled',s]['score']) for s in meta['seeds']],
            fmt(lookup[q,'nearest',meta['seeds'][0]]['score'])] for q in questions],
          [1.6,3.5,3.5,3.5,4.],10.5)
    comparisons = []
    for group,label in [('official','Cấu hình BTC'),('generated_heldout','Bản đồ sinh kiểm tra')]:
        trained = [r for r in rows if r['group']==group and r['variant']=='trained_sampled']
        for variant,name in [('untrained_sampled','Mạng trước học, lấy mẫu'),('random','Chọn ngẫu nhiên'),('nearest','Chọn đích gần nhất')]:
            pairs = [(tuple(r['score']),tuple(lookup[r['case'],variant,r['seed']]['score'])) for r in trained]
            comparisons.append([label,name,len(pairs),sum(a>b for a,b in pairs),
                                sum(a==b for a,b in pairs),sum(a<b for a,b in pairs)])
    table('Bảng C10. So sánh ghép cặp theo input và seed, dùng thứ tự điểm từ điển',
          ['Nhóm bản đồ', 'Đối chứng cùng bộ thực thi', 'Số cặp input–seed',
           'RL lấy mẫu tốt hơn', 'RL lấy mẫu bằng điểm', 'RL lấy mẫu kém hơn'], comparisons,
          [3.3,4.2,2.5,2,2,2],10.5)
    means=[]
    for variant,label in [('trained','Mạng sau PPO, argmax'),('untrained','Mạng trước học, argmax'),
                          ('trained_sampled','Mạng sau PPO, lấy mẫu'),('untrained_sampled','Mạng trước học, lấy mẫu'),
                          ('random','Chọn ngẫu nhiên'),('nearest','Chọn đích gần nhất')]:
        subset=[r for r in rows if r['group']=='generated_heldout' and r['variant']==variant]
        means.append([label,len(subset),*[f"{mean(r['score'][i] for r in subset):.2f}" for i in range(3)]])
    table('Bảng C11. Trung bình từng thành phần điểm trên bản đồ sinh kiểm tra',
          ['Phương pháp chọn mục tiêu', 'Số lượt input–seed', 'Số loại toàn trận U',
           'Tổng số loại theo ngày D', 'Tổng số suất Q'],means,[4.8,2.8,3,3,3],10.5)
    para('Mỗi cặp ở bảng C10 so đúng cùng input và seed. Số cặp không phải số bản đồ '
         'độc lập vì có lặp theo ba seed và có Q01/Q02 trùng cấu hình. Các trung bình '
         'ở bảng C11 chỉ tóm tắt từng thành phần, không thay thế phép so điểm từ điển. '
         'Thắng mạng trước học trên dữ liệu kiểm tra là bằng chứng thực nghiệm về '
         'tác động của cập nhật trọng số trong kiến trúc này; thắng đối chứng gần nhất '
         'mới cho thấy lợi ích so với quy tắc chọn đích đơn giản dùng cùng bộ thực thi. '
         'Nhóm không chọn riêng seed tốt nhất để tuyên bố RL vượt thuật toán.')
    for label in ('Cấu hình BTC','Bản đồ sinh kiểm tra'):
        for row in comparisons:
            if row[0]==label and row[1] in ('Mạng trước học, lấy mẫu','Chọn đích gần nhất'):
                group_name = label.lower().replace('btc', 'BTC')
                para(f"Trên {group_name}, RL sau PPO lấy mẫu so với {row[1].lower()} tốt hơn "
                     f"{row[3]}/{row[2]} cặp, bằng {row[4]}/{row[2]} cặp và kém "
                     f"{row[5]}/{row[2]} cặp. Đây là kết quả của cả ba seed đã định trước, "
                     'không phải kết quả chọn lại theo điểm mô phỏng.')
    deterministic = [r for r in rows if r['variant']=='trained']
    zeros = sum(tuple(r['score'])==(0,0,0) for r in deterministic)
    para(f"Cách lấy argmax của mạng sau PPO có {zeros}/{len(deterministic)} lượt đạt "
         '(0,0,0). Nhóm giữ nguyên các kết quả này trong evaluation_summary.json, '
         'không thay bằng kết quả lấy mẫu hoặc heuristic. Hiện tượng xác suất chờ '
         'lớn hơn xác suất của từng đích riêng lẻ có thể làm argmax chọn chờ dù tổng '
         'xác suất đi tới các đích vẫn lớn; do đó, chính sách lấy mẫu và argmax cần '
         'được phân biệt. Lượt huấn luyện này chưa cho thấy một chính sách argmax '
         'đáng tin cậy và không được trình bày như kết quả RL đã giải tốt bài toán.')
    para(f"Nhóm đã chấm lại {audit['matches']} trận, tương ứng {audit['replay_verified_days']} "
         f"kế hoạch ngày; số kế hoạch sai là {audit['invalid_plans']}, số sai khác điểm "
         f"khi phát lại là {audit['replay_score_mismatches']} và số lần gọi fallback "
         f"là {audit['fallback_calls']}. Bộ kiểm thử có 52 phương thức, gồm kiểm tra "
         'ép mạng chọn chờ để xác nhận hệ thống không tự chuyển sang Greedy và kiểm '
         'tra tiền tố đường đi cùng nhiên liệu kế thừa qua nhiều ngày.')
    para('Các giới hạn còn lại gồm tập học hữu hạn, chỉ ba seed, vai trò toàn tuần '
         'tra, chưa có đội đối thủ và chưa học điều khiển từng hướng. Nhiên liệu được '
         'giữ liên tục cả trận và giao thông cập nhật từ chính đội đang chạy. Các '
         'quy tắc đường đi, mặt nạ và đặt chỗ vẫn đóng góp vào kết quả, nên cách gọi '
         'chính xác là chính sách RL chọn mục tiêu với bộ thực thi thuật toán cố định; '
         'không gọi đây là mô hình học toàn bộ bài toán từ đầu đến cuối.')
    commands = para('Để tái hiện, người dùng chạy experiments/train_rl_policy.py với --episodes '
         '1024 --seeds 71 72 73, sau đó chạy experiments/evaluate_rl_policy.py. Metadata '
         'và hash checkpoint nằm trong experiments/rl_policy_results/training_metadata.json; '
         'evaluation_summary.json lưu đủ mọi biến thể, input và seed; evaluation_audit.json '
         'lưu kết quả chấm lại. Checkpoint và kế hoạch chi tiết chỉ lưu tại máy theo '
         'quy tắc Git ignore. Tài liệu docs/rl_policy_training.md nêu đầy đủ reward, '
         'dữ liệu và giới hạn; mã không cần snapshot nhánh Procon2026 để chạy lượt mới này.')
    commands.alignment = WD_ALIGN_PARAGRAPH.LEFT
