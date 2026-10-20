# Kết quả tour được BTC chấm

## Kiểm chứng máy chủ ngày 20/10/2026

Sau bảng offline, nhóm đã nộp thật 8 bản đồ khác nhau vào Practice riêng của đội 62. Đội hình lấy từ pipeline đã lưu, không chạy lại bộ chọn vai trò; planner dùng 5 giây/ngày và lấy giao thông thật mỗi ngày. Q02 trùng Q01, không tính thành mẫu độc lập.

| Bài | Greedy cũ, BTC | Tour mới, BTC | Đội 57, BTC |
|---|---|---|---|
| Q01 | (20, 101, 253) | (20, 200, 614) | (20, 200, 532) |
| Q03 | (20, 84, 137) | (20, 200, 659) | (20, 200, 530) |
| Q04 | (20, 72, 131) | (20, 200, 636) | (20, 200, 481) |
| Q06 | (15, 72, 193) | (15, 150, 735) | (15, 150, 454) |
| Q07 | (15, 75, 293) | (15, 150, 820) | (15, 150, 760) |
| Q08 | (15, 104, 316) | (15, 150, 685) | (15, 150, 620) |
| Q09 | (15, 72, 146) | (15, 150, 701) | (15, 150, 523) |
| Q10 | (15, 82, 244) | (15, 150, 698) | (15, 150, 551) |

Tổng cộng 80 kế hoạch ngày được nhận, 12155 frame và 188902 giá trị đối chiếu, không có sai khác. Các điểm mới là điểm BTC; bảng offline phía trên chỉ là lịch sử thử nghiệm. Đội 57 là mốc tham khảo từ điểm máy chủ đã đọc, không biết thuật toán/ngân sách của họ. Đạt cận U và D không chứng minh tối ưu Q.

Bản tổng hợp: `experiments/tour_api_evidence/summary.json`. Script `experiments/verify_tour_server.py` có reset/nộp Practice riêng đội 62 và sao lưu lịch sử trước reset; không dùng như lệnh chỉ đọc. Replay và kế hoạch chi tiết giữ tại máy, bị Git ignore.
