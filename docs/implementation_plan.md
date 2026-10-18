# Kế hoạch triển khai

## Mở rộng chọn đội hình ngày 19 tháng 10

- Giữ nguyên vị trí xuất phát, duyệt cách gán hai vai trò và luôn giữ ít nhất một xe tuần tra.
- Sàng lọc ứng viên theo vị trí; giữ toàn tuần tra, từng xe tiếp tế và ba cấu hình của bộ chọn cũ.
- Mô phỏng toàn trận một đội, cập nhật giao thông từ lịch sử xe; đánh giá lại ứng viên tốt trước khi chốt.
- Tách ngân sách chọn đội hình với ngân sách lập kế hoạch ngày và không chấm trận bị cắt giữa chừng.
- Đối chứng trên cấu hình BTC và bản đồ tự sinh; kiểm tra một số output bằng Practice riêng.
- Cập nhật báo cáo Word, phân biệt rõ điểm offline và điểm BTC; chưa đánh giá giao thông đối thủ.

## Phạm vi

Cập nhật ngày 19/10/2026: trọng tâm mở rộng là xây dựng và kiểm chứng môi trường mô phỏng.
Mốc hiện tại dừng trước RL theo yêu cầu người dùng. Phần bàn giao nằm trong `simulator_handover.md`.
Simulator đã có engine nhiều đội, 35 phương thức kiểm thử và sáu tập replay BTC đối chiếu.

Xây dựng lại bài tập lớn bằng Python, chỉ dùng thuật toán tự cài đặt.
Giữ tài liệu BTC Việt Nam làm nguồn luật; không chuyển nguyên code hoặc giả định từ bản cũ.

## Các giai đoạn

1. Đặc tả luật, đồ thị lục giác, trạng thái và những quy ước mô phỏng chưa được BTC mô tả đủ.
2. Cài đặt mô hình dữ liệu, bộ mô phỏng theo step và bộ kiểm tra kế hoạch.
   Kiểm thử tiếp tế, thu thập, chi phí ô nguồn, chuyển ngày và giao thông trước khi tối ưu.
3. Cài đặt DFS, BFS, Dijkstra, Greedy Best-First và A*.
   Với ràng buộc nhiên liệu, không loại đường đi chỉ vì nó đến cùng ô chậm hơn nhưng còn nhiều nhiên liệu hơn.
4. Xây Greedy chọn mục tiêu và lịch tiếp tế; tạo bản mô phỏng toàn trận hợp lệ.
5. Bổ sung Lookahead và chọn loại xe theo bản đồ, vị trí ban đầu, quỹ bước và nhiên liệu.
6. Chạy thí nghiệm riêng cho tìm đường và toàn trận trên cùng seed, nhiều kích thước và tình huống.
7. Hoàn thiện demo, báo cáo mô hình, thuật toán, độ phức tạp và phân tích kết quả.

## Nguyên tắc đánh giá

Bản triển khai ngày 18/10/2026 đã có mô hình, năm thuật toán tìm đường, simulator,
Greedy, Lookahead hai điểm, lịch hẹn tiếp tế, bộ chọn loại xe và các lệnh chạy offline.
Kết quả đo nằm trong `experiments/results`, báo cáo chính nằm tại `bao_cao.md`.
Những quy ước chưa đối chiếu máy chủ được ghi tại `simulation_conventions.md`.

- BFS tối ưu số cạnh, không mặc nhiên tối ưu thời gian trên đồ thị có trọng số.
- Greedy Best-First tìm đường khác với Greedy chọn mục tiêu toàn trận.
- Greedy và Lookahead dùng chung simulator và bộ tìm đường khi so sánh chiến lược.
- Không coi một đường thất bại là đường có chi phí bằng không.
- Thời gian chạy offline được báo cáo riêng với thời gian phản hồi mà máy chủ cuộc thi ghi nhận.
- Quy ước bổ sung phải được công bố; chưa gọi simulator tương thích hoàn toàn máy chủ khi chưa đối chiếu.
