# Đánh giá nhánh Procon2026 trên máy chấm BTC

Thí nghiệm sử dụng bản chụp `origin/Procon2026` tại commit `67e7873781d90e0809bc295a4422316e5abe5dc3`, không thay thế mã đang phát triển trên nhánh `ttud_clean`. Ngày thực hiện là 19/10/2026. Chương trình nộp trực tiếp vào các trận luyện tập riêng của đội 62 trên https://hexudon.hairbui76.id.vn/.

## Phạm vi thực sự đã chạy

Nhánh Procon2026 có mã MAPPO và cơ chế chuyển sang thuật toán dự phòng khi không có checkpoint. Tại thời điểm thí nghiệm, thư mục dự án và cây tệp của nhánh không có mô hình đã huấn luyện dạng `.pt`, `.pth` hoặc `.ckpt`. Vì vậy, thí nghiệm này đánh giá Greedy/Lookahead của nhánh và **không phải kết quả đánh giá chính sách RL đã huấn luyện**. Chúng ta chưa thể dùng các điểm này để kết luận RL tốt hơn hoặc kém hơn thuật toán truyền thống.

Client gốc sử dụng giao thức khác với API của website Việt Nam. Tệp `experiments/evaluate_legacy_branch.py` thực hiện chuyển đổi cấu trúc input, mã địa hình, chỉ số ngày và định dạng output; các lớp GreedyPlanner, LookaheadPlanner, tìm đường, validator và simulator dùng để so sánh ứng viên vẫn được nhập trực tiếp từ bản chụp nhánh. Mỗi ngày, adapter lấy vị trí, nhiên liệu, giao thông và lịch sử thu thập thực tế từ máy chủ, thay vì để sai khác mô phỏng tích lũy qua nhiều ngày.

Chương trình chọn toàn bộ xe tuần tra, đúng cách chọn mặc định trong `run_play` của nhánh gốc. Chương trình tạo phương án Greedy, dùng Lookahead để tìm ứng viên và chỉ thay thế nếu bộ chấm nội bộ của nhánh đánh giá ứng viên tốt hơn. Adapter chỉ nộp phương án cuối cùng một lần mỗi ngày; nó không thực hiện bước nộp Greedy tạm thời rồi nộp cải thiện như client gốc. Vì vậy, đây là đánh giá thuật toán qua adapter tương thích, không phải phép chạy nguyên trạng client mạng của nhánh.

Thí nghiệm dùng ngân sách lập kế hoạch danh nghĩa 30 giây mỗi ngày trong chế độ luyện tập. Chế độ luyện tập không chứng minh được khả năng đáp ứng hạn nộp trong trận thi thật. Thời gian lập kế hoạch trong nhật ký không bao gồm truyền mạng và tải replay. Chương trình không sửa đường đi nếu máy chủ từ chối, mà dừng bài đó và ghi lỗi.

## Nguồn điểm và bằng chứng

Điểm chính thức được đọc từ `GET /api/game/result`, với ba trường `distinct_types`, `cumulative_daily_types` và `total_servings`. Chúng lần lượt là số loại udon khác nhau của toàn trận, tổng số loại thu thập được theo từng ngày và tổng số suất udon. Ba chỉ tiêu được so sánh theo thứ tự ưu tiên, không cộng thành một điểm tổng tùy ý.

Adapter lưu bản sao config, actions, replay và state cũ trước khi đặt lại trận luyện tập. Thư mục `experiments/legacy_branch_evidence` chứa các phản hồi API trước/sau, kế hoạch từng ngày, nhật ký và bảng tổng hợp `summary.json`. Các tệp `Qxx_output.txt` có mỗi dòng là mảng lệnh của một ngày, theo thứ tự từ ngày 1; mỗi ngày chứa một mảng cho từng xe. Khi nộp qua API, chương trình gửi từng dòng kèm trường ngày tương ứng, không gửi cả mười dòng trong một yêu cầu.

Website hiện hiển thị Q01, Q02, Q03, Q04, Q06, Q07, Q08, Q09 và Q10 ở danh sách Practice Match. Q05 không có trong danh sách quan sát được nên không có output hoặc điểm cho bài này. Config Q01 và Q02 giống hệt nhau ở mọi trường trả về; hai nhãn này không tạo thành hai trường hợp đầu vào độc lập.

## Tài liệu để kiểm tra thủ công

- Danh sách bài luyện tập: https://hexudon.hairbui76.id.vn/tournament/1/round/1/match/11/questions
- Tài liệu API BTC: https://hexudon.hairbui76.id.vn/docs
- Đặc tả OpenAPI: https://hexudon.hairbui76.id.vn/openapi.json
- Các endpoint được dùng: `/api/game/config`, `/api/game/day`, `/api/game/agent-types`, `/api/game/practice/reset`, `/api/game/practice/actions`, `/api/game/actions`, `/api/game/replay`, `/api/game/state` và `/api/game/result`.

Giảng viên có thể dùng tài khoản có quyền truy cập để mở từng bài luyện tập hoặc kiểm tra các phản hồi JSON đã lưu. Thông tin xác thực không được đưa vào các tệp bằng chứng hoặc báo cáo.

## Kết quả máy chủ

| Bài | Loại toàn trận | Tổng loại theo ngày | Tổng suất |
|---|---:|---:|---:|
| Q01 | 20 | 92 | 245 |
| Q02 | 20 | 92 | 245 |
| Q03 | 20 | 67 | 132 |
| Q04 | 20 | 70 | 145 |
| Q05 | Không có trong danh sách | — | — |
| Q06 | 15 | 75 | 189 |
| Q07 | 15 | 71 | 344 |
| Q08 | 15 | 101 | 308 |
| Q09 | 15 | 85 | 201 |
| Q10 | 15 | 92 | 266 |

Máy chủ đã nhận và lưu đúng 90 kế hoạch ngày. Thời gian lập kế hoạch lớn nhất: 0.281 giây, không gồm truyền mạng.
