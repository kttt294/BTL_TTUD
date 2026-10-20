# Kết quả tour được BTC chấm

Ngày kiểm chứng: 20/10/2026. Tám bản đồ Practice khác nhau, đội 62; Q02 trùng Q01 nên không tính là mẫu độc lập. Đội hình cố định theo lượt chọn đã lưu; planner dùng 5 giây/ngày và giao thông thật từ API mỗi ngày.

| Bài | Điểm BTC (U, D, Q) | Cận U, D |
|---|---|---|
| Q01 | (20, 200, 614) | (20, 200) |
| Q03 | (20, 200, 659) | (20, 200) |
| Q04 | (20, 200, 636) | (20, 200) |
| Q06 | (15, 150, 735) | (15, 150) |
| Q07 | (15, 150, 820) | (15, 150) |
| Q08 | (15, 150, 685) | (15, 150) |
| Q09 | (15, 150, 701) | (15, 150) |
| Q10 | (15, 150, 698) | (15, 150) |

Tổng cộng 80 kế hoạch ngày được nhận, 12.155 khung trạng thái và 188.902 giá trị được đối chiếu, không phát hiện sai khác ở các trường được kiểm tra. Đạt cận U và D chưa chứng minh tối ưu Q hoặc mọi trường hợp nhiều đội.

Số liệu gốc: `experiments/tour_api_evidence/summary.json`. Mốc điểm đội 57: `experiments/tour_results/server_baseline.json`; không biết thuật toán hoặc ngân sách của đội đó.

Script `experiments/verify_tour_server.py` có reset và nộp Practice riêng đội 62, sao lưu lịch sử trước reset và đối chiếu replay. Không dùng script này như lệnh chỉ đọc. ID mẫu cần đặt tại máy trong `docs/api/sample_games.json`; token đọc từ `.env`. Các replay chi tiết bị Git ignore. Giảng viên có thể kiểm tra trực tiếp trên website bằng tài khoản trong báo cáo.
