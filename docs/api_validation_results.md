# Kết quả đối chiếu simulator với API BTC

Ngày đối chiếu: 19/10/2026, tài khoản đội 62, chỉ dùng chế độ luyện tập riêng.

| Bộ replay | Ngày | Frame | Giá trị so sánh | Sai khác |
|---|---:|---:|---:|---:|
| Q02 các ca luật | 8 | 1284 | 17868 | 0 |
| Q03 toàn trận | 10 | 1544 | 24580 | 0 |
| Q04 toàn trận | 10 | 1565 | 21564 | 0 |
| Q06 toàn trận | 10 | 1242 | 22656 | 0 |
| Q10 rời đường ngay | 2 | 317 | 4750 | 0 |
| Q10 chờ trước khi rời đường | 3 | 379 | 5927 | 0 |

Tổng số frame được kiểm tra là 6331; ngày đầu Q10 được tính trong cả hai biến thể, nên không coi tổng này là số mẫu độc lập.
Mỗi frame được so vị trí, nhiên liệu, số phần trong ngày, số loại trong ngày và sự kiện thu thập. Giao thông dự đoán được so với đầu ngày tiếp theo khi replay có ngày đó.

| Output sai | HTTP máy chủ | Kết luận |
|---|---:|---|
| Mã hướng ngoài miền | 422 | Máy chủ từ chối |
| Vượt quỹ step | 409 | Máy chủ từ chối |
| Đi vào ao | 409 | Máy chủ từ chối |
| Thiếu nhiên liệu | 409 | Máy chủ từ chối |

## Điểm truy cập và bằng chứng

Tài liệu công khai: https://hexudon.hairbui76.id.vn/docs . Schema gốc: https://hexudon.hairbui76.id.vn/openapi.json .

Các JSON gốc nằm tại `experiments/api_evidence`; request không chứa header Authorization. Mỗi bản ghi có thời điểm UTC, endpoint, tham số, body, HTTP status và phản hồi. Danh mục SHA-256 nằm tại `manifest.json`. Hàm băm giúp nhận biết tệp thay đổi, không phải chữ ký xác nhận của BTC.

Các so sánh trên xác minh một đội trong những bản luyện tập đã thử. Phần nhiều đội mới có kiểm thử nội bộ, chưa có replay đối chiếu từ BTC. Kết quả không chứng minh simulator đúng trong mọi trường hợp và không phải chứng nhận của BTC.
