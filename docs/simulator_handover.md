# Mốc bàn giao simulator trước giai đoạn RL

Ngày bàn giao: 19/10/2026. Phần RL chưa được viết hoặc huấn luyện.

## Những phần đã hoàn thành

- Engine dùng chung cho một đội và nhiều đội, với timeline, kho riêng và giao thông chung.
- API client đọc token từ .env và lưu bằng chứng không kèm header xác thực.
- Công cụ đọc replay BTC rồi so từng frame với simulator.
- Kiểm chứng sáu bộ replay trên năm bản mẫu, bao gồm bản đồ 32×32, 32×30 và 30×30.
- Kiểm thử các trường hợp API từ chối, đồng thời bổ sung hồi quy cho các sai khác đã phát hiện.
- Chạy lại benchmark offline và cập nhật báo cáo sau khi thay đổi simulator.

## Phạm vi có thể dùng cho bước tiếp theo

Giao diện `simulate_day` nhận board, state, actions và steps; kết quả có valid, errors, state và trace.
Giao diện `simulate_match_day` nhận ánh xạ trạng thái và kế hoạch của từng đội trên cùng bản đồ.
Các đối tượng đầu vào không bị sửa. Hàm tìm đường A* và bộ kiểm tra cuối có thể được dùng
chung cho một phương pháp chọn mục tiêu bằng RL khi người dùng giao việc tiếp.

Nền hiện tại đủ để bắt đầu thiết kế prototype RL offline trong phạm vi đã công bố.
Không dùng kết quả đối chiếu hữu hạn để khẳng định simulator đã đúng tuyệt đối.

## Những giới hạn cần giữ rõ

- Phần nhiều đội mới được kiểm thử nội bộ, chưa có replay máy chủ nhiều đội.
- Chưa có bằng chứng API riêng cho mọi trường hợp tranh kho thiếu hàng và xe hoàn toàn cạn nhiên liệu.
- Giao thông có quy tắc tương thích hành vi biên của phiên bản BTC đã kiểm tra; cần đối chiếu lại khi máy chủ thay đổi.
- Client chỉ dùng chế độ luyện tập, không có vòng tự động nộp thi chính thức.
- Các quyết định sát hạn giờ có thể thay đổi theo tải máy; benchmark mới vẫn lưu seed và thông số môi trường.

Người dùng sẽ giao phạm vi RL sau khi xem kết quả bàn giao này. Dự án chưa tự lựa chọn
kiến trúc RL, hàm thưởng hoặc ngân sách huấn luyện ở giai đoạn hiện tại.
