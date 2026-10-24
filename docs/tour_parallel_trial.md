# Thử nghiệm tour nhiều tiến trình

Mỗi tiến trình nhận cùng trạng thái đầu ngày và lập tuyến cho toàn bộ đội xe bằng một seed khác nhau. Tiến trình chính kiểm tra kế hoạch bằng simulator rồi chọn kết quả để nộp. Các tiến trình con không gọi API. Nhóm tiến trình được dùng lại qua nhiều ngày.

Nhánh `src_procon` đã có cơ chế tìm kiếm song song và gửi kế hoạch tạm. Đợt thử này bổ sung việc truyền seed khởi đầu, chọn thuần theo điểm cuối ngày và lưu số liệu kiểm tra các ứng viên.

## Chạy trên một trận

```powershell
python -X utf8 play_match.py --algorithm tour --workers 4 --seed 0 --parallel-objective score --seconds 20 --game-id ID_TRAN
```

Trong ví dụ trên, bốn tiến trình dùng seed 0, 1, 2, 3; mỗi seed còn được kết hợp với chỉ số ngày trong game. `--workers 1` chạy một tiến trình. Cùng seed vẫn có thể cho kết quả khác khi số vòng tìm kiếm bị thay đổi bởi hạn giờ.

`--parallel-objective score` chọn theo U, D, Q cuối ngày. `lookahead` giữ cách chọn cũ của nhánh này: xét thêm số loại dự báo cho ngày mai trước Q. Chế độ tính giờ dùng cùng lựa chọn khi xét nộp lại một kế hoạch tốt hơn.

## So sánh bằng máy chủ Practice

```powershell
python -X utf8 experiments/compare_parallel_server.py --cases Q01 Q02 Q06 --workers 1 4 --seconds 5 --objective score --output results/parallel_trial_20261024
```

Script chỉ thao tác Practice riêng của đội 62. Script sao lưu cấu hình, đội hình, điểm, bài nộp và replay trước khi reset, giữ nguyên đội hình giữa các lượt thử và đọc trạng thái đường thật mỗi ngày. Nếu tour phải dùng Greedy dự phòng, script dừng và không tính lượt đó là kết quả tour.

Sau mỗi lượt, script đọc điểm và replay từ máy chủ, đối chiếu với simulator. Cuối mỗi bài, script giữ hoặc khôi phục lượt có điểm cao nhất giữa bài có sẵn và các lượt thử. Khi cần khôi phục, script nộp lại các kế hoạch đã sao lưu; không chỉnh điểm trên máy chủ.

Thư mục kết quả có `summary.json`, các bản sao lưu và số liệu từng ngày. `valid_candidates` đếm các bản kế hoạch được kiểm tra hợp lệ, bao gồm kế hoạch tạm và kế hoạch cuối; đây không phải số tuyến khác nhau. `pending_workers` cho biết số tác vụ chưa kết thúc khi thu kết quả cuối.

Một lượt thử chưa đủ chứng minh phương pháp tốt hơn ổn định. Q01 và Q02 có cùng cấu hình bản đồ; không được tính hai bài này là hai bản đồ độc lập. Điểm có sẵn chỉ là mốc thực tế; phép đối chứng trực tiếp là một và nhiều tiến trình trong cùng đợt thử, cùng đội hình và ngân sách.
