# Hướng dẫn vận hành ngày thi

Dành cho người chạy máy thi. Mọi lệnh chạy từ thư mục gốc dự án, PowerShell, Python 3.10+ (không cần `-X utf8`).

## Trước trận (làm sớm, ít nhất 30 phút trước giờ chọn vai trò)

1. **Lấy token mới** trên website BTC và thay dòng `HEXUDON_TOKEN=...` trong `.env`. Token có
   hạn 48 giờ; runner tự dừng trước bước chọn vai trò nếu token hết hạn trước khi trận kết thúc.
2. **Chuẩn bị máy:** cắm sạc; tắt chế độ ngủ và màn hình tắt; hoãn Windows Update; đóng mọi
   chương trình khác (trình duyệt nặng, IDE đang chạy test, đồng bộ đám mây). Chạy việc khác
   trong trận làm giảm điểm rõ rệt (tập dượt: Q01 tụt từ 627 xuống 577).
3. **Kiểm tra trước trận** khi đã có ID trận (chỉ đọc, không nộp bài):

   ```powershell
   python play.py ID_TRAN --preflight
   ```

   Phải thấy `Kết quả: sẵn sàng.` Nếu có `CẢNH BÁO`, xử lý trước khi chạy thật (token, mạng,
   số nhân CPU, thời gian khởi động tiến trình).

## Chạy trận

```powershell
python play.py ID_TRAN
```

- Không cần thêm tham số: ngân sách lập kế hoạch tự lấy theo `daySeconds` của config trừ 4 giây
  dự phòng; chọn vai trò theo `agent_selection_time_limit` trừ 4 giây; 14 tiến trình song song.
- Mỗi ngày runner nộp một bài sau khoảng 2–5 giây, rồi tối ưu tiếp và **chỉ nộp lại nếu bài mới
  tốt hơn** (máy chủ giữ bài hợp lệ cuối cùng): kiểm tra mỗi 2 giây, các lần nộp lại cách nhau ít
  nhất 5 giây, tối đa 5 lần nộp/ngày. Bài đã đạt cận trên của ngày thì dừng, để thời gian phản
  hồi thấp. Tập dượt: tổng thời gian phản hồi khoảng 46–84 giây/trận.
- Màn hình in trạng thái từng ngày: `máy chủ đã nhận kế hoạch`, `đã nộp lại bài tốt hơn ...` hoặc
  `giữ bài đã nộp`.
- Không chạy hai runner cho cùng đội/trận. Runner có khóa tệp để chặn việc này.

## Khi có sự cố

| Tình huống | Làm gì |
|---|---|
| Runner dừng, mất mạng, lỡ tay Ctrl+C | **Chạy lại đúng lệnh cũ.** Runner đọc checkpoint, không nộp trùng, tiếp tục ngày hiện tại nếu còn giờ. Bài đã nộp sớm trong ngày vẫn được máy chủ giữ. |
| Báo token hết hạn | Lấy token mới vào `.env`, chạy lại đúng lệnh cũ. |
| Báo `Trận đã lùi ngày hoặc được reset` | BTC đã reset trận: chạy lại với `--run-dir` mới. |
| Báo `Planner lỗi ...; dùng Greedy` | Runner đã tự dùng phương án dự phòng; để chạy tiếp, lưu log để kiểm tra sau. |
| Máy quá chậm, nhiều ngày `dự phòng` | Giảm số tiến trình: thêm `--workers 8`. |

## Không làm

- Không reset trận, không gửi bài bằng tay song song với runner.
- Không đổi `--seconds`/`--reserve` nhỏ hơn mặc định: dưới 5 giây/ngày tỷ lệ mất D tăng.
- Không đổi `tour.PARAMS` hay `--parallel-objective` trong ngày thi ngoài cấu hình đã diễn tập.

## Sau trận

- Thư mục `results/live/<ID>_<đội>/` chứa config, trạng thái từng ngày, lệnh đã nộp và
  checkpoint; runner tự dọn khi đọc được kết quả cuối trận. Muốn giữ log, sao chép thư mục này
  trước khi trận kết thúc hoặc chạy với `--run-dir` riêng.
