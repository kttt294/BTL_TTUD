# Hướng dẫn giảng viên kiểm tra bằng chứng API

## Nguồn và phạm vi sử dụng

Nhóm đã sử dụng API chính thức tại https://hexudon.hairbui76.id.vn/ để đối chiếu simulator
ngày 19/10/2026. Tài liệu Swagger công khai nằm tại https://hexudon.hairbui76.id.vn/docs;
schema OpenAPI gốc nằm tại https://hexudon.hairbui76.id.vn/openapi.json.
Bản schema đã tải được lưu tại `docs/api/openapi.json` để tham khảo khi website thay đổi.

Danh sách câu hỏi quan sát trên giao diện Practice Match gồm Q01, Q02, Q03, Q04,
Q06, Q07, Q08, Q09 và Q10. Q05 không xuất hiện tại thời điểm kiểm tra, nên báo cáo
không mặc nhiên gọi đây là mười cấu hình đã kiểm chứng. Nhóm đã đọc cấu hình của chín câu,
đọc lịch sử Q01 và thực hiện các phép thử trên Q02, Q03, Q04, Q06 và Q10.
Q01 được giữ nguyên lịch sử của người dùng. Những câu còn lại ngoài năm câu thử chỉ được đọc cấu hình.

## Những endpoint đã dùng

| Phương thức | Endpoint | Mục đích |
|---|---|---|
| GET | `/api/game/config` | Lấy bản đồ, quỹ bước, nhiên liệu, vị trí xe và ngưỡng giao thông |
| GET | `/api/game/day` | Đọc vị trí, nhiên liệu, giao thông và chỉ số ngày thực tế |
| GET | `/api/game/state` | Đọc trạng thái và điểm tích lũy của bản luyện tập |
| GET | `/api/game/actions` | Lấy các kế hoạch đã được chấp nhận |
| GET | `/api/game/replay` | Lấy vị trí, nhiên liệu và sự kiện ở từng step |
| POST | `/api/game/agent-types` | Chọn vai trò xe cho những bản luyện tập kiểm tra |
| POST | `/api/game/practice/actions` | Nộp kế hoạch kiểm chứng trên bản luyện tập riêng |

Các phép thử không gọi endpoint nộp kế hoạch thi chính thức, không thay đổi mật khẩu và
không reset Q01. Bản luyện tập của đội dùng `game_id` dạng `mã_câu_hỏi:62`.
API đánh số ngày từ 0; vì vậy giá trị day=0 tương ứng ngày đầu tiên.

## Cách đối chiếu khi không cần đăng nhập

Giảng viên có thể mở các tệp JSON trong `experiments/api_evidence`. Mỗi request có endpoint,
thời điểm, tham số, body và phản hồi. Header chứa token không được lưu trong những tệp này.
Giảng viên có thể đối chiếu body của bản ghi submit với plan trong bản ghi actions, sau đó
kiểm tra vị trí và nhiên liệu ở các frame của replay.

Script dưới đây chỉ đọc các bằng chứng đã lưu và chạy simulator tại máy, không gửi request mới:

```powershell
python -X utf8 experiments/compare_api.py --config experiments/api_evidence/q03_config.json --replay experiments/api_evidence/q03_replay.json --actions experiments/api_evidence/q03_actions.json --output results/q03_check.json
python -X utf8 -m unittest discover -s tests -v
```

Kết quả comparison ghi số frame, số giá trị đã so và những sai khác đầu tiên nếu có.
Các trường được đối chiếu gồm vị trí từng xe, nhiên liệu từng xe, số phần và số loại trong ngày,
danh sách sự kiện thu hàng, cùng trạng thái giao thông của ngày sau. Việc so điểm cuối trận
không được dùng thay thế cho so từng frame.

## Cách kiểm tra trực tiếp trên website

Giảng viên cần tài khoản hợp lệ do BTC cung cấp để đọc các endpoint yêu cầu xác thực.
Trong Swagger, giảng viên chọn Authorize, nhập token của tài khoản được phép truy cập,
sau đó gọi GET config, actions và replay cho cùng một game_id. Các game_id đã sử dụng
được liệt kê trong `docs/api/sample_games.json`; khi kiểm tra tài khoản khác phải dùng
hậu tố đội tương ứng, không mặc nhiên dùng quyền truy cập của đội 62.

Giao diện danh sách được truy cập tại
https://hexudon.hairbui76.id.vn/tournament/1/round/1/match/11/questions sau khi đăng nhập.
Điểm số hiển thị trên các trận thử là điểm của những kế hoạch phục vụ xác minh luật,
không phải tất cả đều là kế hoạch tối ưu do thuật toán tạo ra.

Nếu muốn tạo một phép thử mới bằng tài khoản của mình, người kiểm tra có thể lưu token
trong `.env` dưới tên `HEXUDON_TOKEN` và chạy `validate_server.py` với đúng `--team`.
Script chỉ dùng chế độ luyện tập. Nếu đã có lịch sử, script đọc và đối chiếu thay vì ghi đè.
Nếu chưa có lịch sử, script sẽ chọn đội hình và nộp một trận Greedy; cần hiểu tác động này trước khi chạy.

## Những kết luận chưa được phép rút ra

Replay khớp cho thấy hai hệ thống có cùng kết quả trên những phép thử đã thực hiện,
không phải chứng minh tương đương cho toàn bộ không gian trạng thái. Bộ bằng chứng hiện tại
chưa đối chiếu nhiều đội cùng chạy, kho ít hơn số xe tuần tra hoặc mọi trường hợp bơm nhiên liệu
khi xe đã cạn hoàn toàn. Các trường hợp đó được kiểm thử nội bộ hoặc ghi nhận để mở rộng.

Riêng giao thông, API có hành vi biên khi xe bắt đầu ngày trên đường: khoảng chuyển tiếp
rời vị trí đầu ngày không được tính như các frame hiển thị ô nguồn. Các biến thể Q10 được dùng
để tái hiện hiện tượng này. Simulator theo hành vi đã quan sát của máy chủ, đồng thời ghi rõ
đây là đặc điểm tương thích phiên bản đã kiểm tra, không suy diễn thành một điều luật mới của BTC.
