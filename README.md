# Lập kế hoạch đa tác tử trên đồ thị lục giác

Bài tập lớn **Thuật toán ứng dụng**, dựa trên đề HEXUDON của Procon Việt Nam 2026.
Chương trình dùng Python 3.10 trở lên và thư viện chuẩn, không cần cài gói ngoài để chạy thuật toán.
Code và chú thích được viết theo hướng đơn giản, không có thành phần ML/RL.

## Những phần đã triển khai

- Mô hình lục giác so le, chi phí theo ô xuất phát và giao thông.
- DFS, BFS, Dijkstra, Greedy Best-First và A* với giới hạn bước, nhiên liệu.
- Greedy chọn điểm, Lookahead hai điểm, lịch hẹn tiếp nhiên liệu và chọn cơ cấu xe.
- Kiểm tra output bằng mô phỏng đồng thời, chèn thời gian chờ và kế hoạch dự phòng.
- Demo toàn trận, lưu replay, xuất output đúng dạng mảng JSON.
- Thí nghiệm tái hiện được và báo cáo có số liệu thực tế.

Simulator đã hỗ trợ **một hoặc nhiều đội** và được đối chiếu bằng API luyện tập BTC.
Các phép đo chiến lược hiện vẫn chạy một đội. Phần nhiều đội có kiểm thử nội bộ,
chưa có replay BTC tương ứng. Chi tiết nằm trong [đặc tả](docs/simulation_conventions.md).
Giai đoạn hiện tại hoàn tất nền simulator và dừng trước khi triển khai RL.

## Bằng chứng đối chiếu với BTC

- 35 phương thức kiểm thử đã chạy đạt.
- Sáu tập replay có 6.331 frame, 97.345 giá trị được so sánh và 0 sai khác.
- Hai biến thể Q10 có phần đầu chung; số frame không phải số mẫu độc lập.
- Request/response gốc nằm trong `experiments/api_evidence`, không chứa header token.
- [Hướng dẫn giảng viên kiểm tra thủ công](docs/api_manual_check.md).
- [Bảng kết quả đối chiếu](docs/api_validation_results.md).

Lệnh dưới đây chỉ đọc dữ liệu đã lưu, không gửi request lên máy chủ:

```powershell
python -X utf8 experiments/compare_api.py --config experiments/api_evidence/q03_config.json --replay experiments/api_evidence/q03_replay.json --actions experiments/api_evidence/q03_actions.json --output results/q03_check.json
```

`experiments/validate_server.py` là công cụ chạy API luyện tập có xác thực qua `.env`.
Nếu trận chưa có lịch sử, công cụ sẽ chọn loại xe và nộp kế hoạch; nếu đã có lịch sử,
công cụ chỉ đọc và đối chiếu. Công cụ không gọi endpoint nộp bài thi chính thức.

## Chạy nhanh

Các lệnh dưới đây chạy từ thư mục gốc dự án.

```powershell
python -X utf8 -m unittest discover -s tests -v
python -X utf8 src/main.py demo --size 8 --seed 42 --seconds 1 --output results/demo.json
```

Mỗi dòng demo cho biết điểm tích lũy, thời gian và việc dùng kế hoạch dự phòng.
File JSON lưu vị trí, nhiên liệu ở từng step, lệnh từng xe và cấu hình bản đồ.

## Xuất kế hoạch cho bản đồ BTC

File mẫu thiếu trường `agents`. Các vị trí dưới đây lấy từ ảnh chọn xe của đúng trận mẫu:

```powershell
python -X utf8 src/main.py plan --config "Đề bài/input_sample.json" --starts 558 998 130 955 --types 0 0 1 0 --day 1 --seconds 2 --output results/output.txt
python -X utf8 src/main.py validate --config "Đề bài/input_sample.json" --starts 558 998 130 955 --types 0 0 1 0 --actions results/output.txt
```

Nội dung `output.txt` chỉ gồm mảng lệnh của tất cả xe, có thể sao chép vào ô nộp bài.
Ví dụ chạy nằm tại [examples/output_day1.txt](examples/output_day1.txt).
Không dùng các vị trí mẫu cho trận khác và không dùng lại trạng thái đầu trận cho ngày sau.

Khi có JSON trạng thái thật, dùng `--state`, `--day` và đúng cấu hình trận:

```powershell
python -X utf8 src/main.py plan --config results/config.json --state results/day2.json --day 2 --seconds 2 --output results/output_day2.txt
```

Trạng thái có `agents` (mỗi xe gồm `kind`, `pos`, `fuel`) và `traffics` (mỗi ô đường gồm
`pos`, `status`). Có thể thêm `brands` chứa các loại udon đã thu trong những ngày trước.
Nếu thiếu `brands`, kế hoạch vẫn được kiểm tra nhưng việc ưu tiên loại mới kém chính xác.
Tham số `--day` bắt đầu từ 1 theo ngày người dùng muốn giải, không tự suy ra từ trường
`day` của API vì quy ước đánh số đó còn cần đối chiếu.

## Chọn loại xe

```powershell
python -X utf8 src/main.py select --config "Đề bài/input_sample.json" --starts 558 998 130 955 --seconds 20 --output results/types.json --selection-log results/selection.json
```

Chương trình giữ nguyên vị trí xuất phát của BTC và thử các cách gán tuần tra/tiếp tế.
Bộ chọn giữ cấu hình toàn tuần tra, từng cách chọn một xe tiếp tế và các cấu hình cũ,
sau đó bổ sung ứng viên theo vị trí; mặc định danh sách sàng lọc tối đa 16 cấu hình.
Những đội hình tốt được mô phỏng lại với ngân sách lớn hơn trước khi chọn theo bộ điểm
ưu tiên của toàn trận. Giao thông tự cập nhật từ hoạt động của một đội trong từng lượt mô phỏng.
Đây là tìm kiếm giới hạn thời gian, không bảo đảm đội hình tối ưu toàn cục; điểm mô phỏng
phụ thuộc cả bộ lập kế hoạch và ngân sách tìm đường. Dùng `--candidates` để thay số ứng viên
và `--strategy` để chọn greedy hoặc lookahead. Nhật ký phân biệt lượt screen và refine,
đồng thời đánh dấu những trận chưa mô phỏng xong; chúng không được dùng để so điểm cuối trận.
Các lệnh `plan` và `demo` dùng `--types` khi được chỉ định, nếu bỏ qua thì mặc định xe cuối là tiếp tế.
Lệnh `select` chạy riêng và không tự thay đổi đội hình trên website.
Sau khi chọn, dùng `--types-file results/types.json` với `plan` hoặc `demo` để giữ đúng
vai trò đã chọn. Vị trí xuất phát do BTC cung cấp, không được tự đổi vị trí khi thử đội hình.

Chạy đối chứng chọn đội hình bằng `python -X utf8 experiments/benchmark_team_selection.py`.
Các kết quả nằm trong `experiments/team_selection_results`; điểm BTC kiểm chứng riêng nằm
trong `experiments/team_selection_api_evidence`. Hai loại điểm được báo cáo tách biệt.

## Tính cận tiếp cận theo nhiên liệu

```powershell
python -X utf8 src/main.py bounds --config output/team_selection/Q04/config.json --types-file output/team_selection/Q04/types.json --output results/bounds.json
python -X utf8 experiments/calculate_bounds.py
```

Lệnh `bounds` tính cận từ đầu trận và lưu cả cận theo từng ngày. Xe không có tiếp tế dùng
chung nhiên liệu ban đầu cho cả trận. Khi cùng vùng liên thông có xe tiếp tế, phép tính nới
lỏng bằng cách cho phép nạp ở mọi nơi trong vùng từ đầu trận. Dijkstra thời gian dùng đường
thông thoáng; các khoảng cách nhiên liệu và thời gian được xét riêng nên có thể thuộc hai
tuyến khác nhau. Đây chỉ là những điều kiện cần: cận không bảo đảm xe đi được một hành trình
ghé mọi điểm được tính. Xe đứng tại điểm udon qua nhiều ngày vẫn có thể thu tiếp dù hết nhiên liệu.

## Chạy thực nghiệm

```powershell
python -X utf8 experiments/benchmark.py --games 10 --sizes 8 16 32 --seconds 0.25
python -X utf8 experiments/summarize.py
```

Kết quả gốc, thông số máy và phần tổng hợp nằm trong `experiments/results/`.
Mỗi kích thước có 10 bản đồ, mỗi bản đồ có 3 truy vấn tìm đường và một cặp trận Greedy/Lookahead.
Ngân sách 0,25 giây là cấu hình đo nhanh, không đại diện toàn bộ giới hạn thi chính thức 30 giây.

## Cấu trúc mã nguồn

```text
src/hexudon/model.py       Dữ liệu, láng giềng, khoảng cách, chi phí
src/hexudon/search.py      Năm thuật toán và nhãn tài nguyên
src/hexudon/simulator.py   Kiểm tra kế hoạch và chuyển trạng thái
src/hexudon/planner.py     Greedy, Lookahead, điểm hẹn, chọn loại xe
src/hexudon/generator.py   Sinh bản đồ liên thông theo seed
src/hexudon/__main__.py    Các lệnh demo, plan, validate, select
src/main.py               Điểm chạy từ thư mục gốc
tests/                    Kiểm thử luật và đối chiếu vét cạn
experiments/              Chạy đo và tổng hợp kết quả
docs/                     Luật, kế hoạch, quy ước và báo cáo
examples/                 Output và replay đã chạy
```

Báo cáo hiện hành: [output/docx/bao_cao_hexudon.docx](output/docx/bao_cao_hexudon.docx).
Bản Word đã được viết lại theo hướng so sánh thuật toán, có phần mở rộng RL và dùng
phong cách báo cáo NLP. Nội dung Markdown và PDF là phiên bản cũ, không được cập nhật
đồng thời với bản Word theo yêu cầu của nhóm.

Quy trình dựng bản mới nằm trong `experiments/rewrite_algorithm_report.py`, sau đó
cập nhật mục lục và kiểm tra bố cục bằng `experiments/render_report_word.ps1`.
Trình dựng cần bản mẫu NLP và bản chụp báo cáo trước khi viết lại trong thư mục
`scratch/algorithm_rewrite`; đây là công cụ biên soạn tại máy, không phải phụ thuộc
để chạy thuật toán. Các trình dựng báo cáo cũ có thể ghi đè nội dung mới nên không
được dùng để cập nhật bản Word hiện hành.
Greedy là chiến lược mặc định; dùng `--strategy lookahead` để chạy bản nhìn trước hai điểm.

Phần xuất báo cáo PDF chạy riêng bằng `experiments/build_report.py` và cần ReportLab.
Thư viện này chỉ dùng để tạo tài liệu, không phải phụ thuộc của các thuật toán.
