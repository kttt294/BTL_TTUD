# Lập kế hoạch đa tác tử trên đồ thị lục giác

Bài tập lớn môn **Thuật toán ứng dụng**, dựa trên đề HEXUDON của Procon Việt Nam 2026.
Mục tiêu là thiết kế, cài đặt và đánh giá các thuật toán lập lộ trình, phân công mục tiêu
và phối hợp tiếp nhiên liệu dưới ràng buộc thời gian và tài nguyên.

## Trạng thái

Nhánh `ttud_clean` đang được xây dựng lại từ đầu theo tài liệu BTC Việt Nam.
Hiện chỉ có tài liệu nền; chưa có chương trình chạy hoặc kết quả thực nghiệm.
Phạm vi bài tập lớn sử dụng thuật toán tự cài đặt, không sử dụng ML/RL.
Lịch sử triển khai trước được giữ trong Git và nhánh `ttud`.

## Cấu trúc dự kiến

Hiện có `Đề bài/` và `docs/`. Các thư mục chương trình sẽ được tạo khi triển khai,
không giữ thư mục rỗng hoặc file `.gitkeep`.

```text
Đề bài/             Tài liệu và mẫu do người dùng cung cấp
docs/               Luật, mô hình và kế hoạch triển khai
src/core/           Mô hình dữ liệu, đồ thị lục giác, chi phí
src/simulation/     Mô phỏng đồng thời và kiểm tra kế hoạch
src/pathfinding/    DFS, BFS, Dijkstra, Greedy Best-First, A*
src/planning/       Chọn loại xe, Greedy, Lookahead, tiếp tế
tests/              Kiểm thử luật và thuật toán
experiments/        Thí nghiệm so sánh có thể tái hiện
```

Đọc [luật và thông tin đã xác nhận](docs/rules.md) trước khi triển khai.
Thứ tự thực hiện nằm trong [kế hoạch](docs/implementation_plan.md).

## Đánh giá dự kiến

- Tìm đường: tỷ lệ tìm được đường, chi phí bước, nhiên liệu, số trạng thái và thời gian.
- Toàn trận: loại udon toàn trận, tổng loại theo ngày, tổng phần và thời gian chạy.
- Các thuật toán được so sánh trên cùng dữ liệu, ràng buộc và điều kiện đo.
- Kết luận được rút ra từ thực nghiệm; không giả định trước thuật toán thắng.
