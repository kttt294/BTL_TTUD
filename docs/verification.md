# Ghi nhận kiểm chứng bản triển khai

## Mã nguồn và luật

Ngày cập nhật kiểm tra: 19/10/2026. Môi trường thuật toán: Python 3.12.6 trên Windows 11.

- Lệnh `python -X utf8 -m unittest discover -s tests -v` đã chạy đạt 35 phương thức kiểm thử.
- Phép đối chiếu tìm đường trong bộ kiểm thử có 20 bản đồ nhỏ và 5 thuật toán, tổng cộng 100 tổ hợp.
- Thử thêm đội 3 xe và 8 xe trên bản đồ 8×8, nhiên liệu tối đa 8, trong bốn ngày và với cả hai chiến lược.
  Các kế hoạch đều vượt qua kiểm tra, không dùng phương án dự phòng.
- Tình huống không có điểm udon vẫn xuất kế hoạch chờ hợp lệ.
- Bản đồ mẫu 32×32 dùng vị trí từ ảnh 558, 998, 130, 955 và loại xe [0,0,1,0].
  Lệnh plan với ngân sách 2 giây đã xuất `examples/output_day1.txt`; lệnh validate đã xác nhận hợp lệ.
- Demo 8×8 seed 42 đã hoàn thành bốn ngày, replay nằm tại `examples/demo_replay.json`.

## Thực nghiệm

Bản chạy cuối sau khi chia ngân sách cho từng xe có 450 lần chạy tìm đường, 60 trận và
240 kế hoạch ngày. Toàn bộ 240 kế hoạch hợp lệ, không phải dùng phương án dự phòng.
Các file CSV và metadata trong `experiments/results` là dữ liệu gốc của báo cáo.

## Đối chiếu với máy chủ BTC

Dự án đã thực hiện nộp các kế hoạch kiểm tra qua API luyện tập và lưu request/response tại
`experiments/api_evidence`. Sáu bộ đối chiếu trên Q02, Q03, Q04, Q06 và hai biến thể Q10
có 6.331 frame, 97.345 giá trị được kiểm tra và 0 sai khác. Hai biến thể Q10 có ngày đầu chung.
Các ca sai mã hướng, vượt step, vào ao và thiếu nhiên liệu đều được API từ chối.

Phiên bản cũ có sai khác về thời điểm trừ nhiên liệu, tiếp tế và giao thông ở ranh giới ngày.
Phiên bản mới đã sửa theo bằng chứng. Kết quả offline được chạy lại; dữ liệu cũ nằm trong
`experiments/archive/pre_validation_2026_10_18` và không được gộp vào kết quả mới.

Giới hạn hiện tại gồm việc chưa đối chiếu replay nhiều đội, thiếu kho khi nhiều xe đến cùng lúc
và mọi trường hợp xe hết nhiên liệu hoàn toàn. Các kiểm thử nội bộ vẫn bao gồm những nhóm này.
Phần RL chưa được triển khai, theo mốc dừng đã thống nhất với người dùng.

## Tài liệu

Báo cáo PDF được tạo từ `docs/bao_cao.md`. Các trang đã được kết xuất để kiểm tra bố cục,
ký tự tiếng Việt, bảng, mục lục và biểu đồ. Chương trình thuật toán không phụ thuộc vào
thư viện tạo báo cáo. Việc xuất lại PDF cần ReportLab và các phông Times New Roman,
Consolas trong thư mục phông hệ thống Windows.
