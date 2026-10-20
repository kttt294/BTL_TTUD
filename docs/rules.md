# Luật và dữ liệu đã xác nhận

## Nguồn

- `Đề bài/2026_Procon_Problem VI.pdf`: luật chính thức, 6 trang.
- `Đề bài/giao diện chọn loại agent đầu game.png`: giao diện chọn loại và vị trí ban đầu.
- `Đề bài/giao diện nộp bài.png`: cách nhập lệnh mỗi ngày.
- `Đề bài/input_sample.json`, `Đề bài/output_sample.txt`: mẫu dữ liệu.
- `Đề bài/Techinical_Presentation.pptx`: 3 slide hướng dẫn website và luồng API.
- API docs: https://hexudon.hairbui76.id.vn/docs (đã đọc ngày 18/10/2026).
- Schema được slide liên kết: https://drive.google.com/file/d/1Oc6RyIBX3oQa6RGeZ4MNDN4tKeOL6t1V/view
  (3 trang, tự ghi là bản dịch tiếng Anh không chính thức của tài liệu Nhật).

## Theo đề chính thức

- Bản đồ lục giác có chiều rộng, chiều cao từ 8 đến 32; các ô đi được liên thông.
- Trận có 4–10 ngày, mỗi đội có 3–8 xe; quỹ bước có thể khác nhau theo ngày.
- Xe được chọn loại đầu trận và không đổi loại trong trận.
- Xe đến ô kề sau khi dùng đủ thời gian di chuyển theo địa hình ô xuất phát.
- Đồng bằng: 2 bước, 1 nhiên liệu. Núi: 3 bước, 2 nhiên liệu.
- Đường thông thoáng/đông đúc/ùn tắc: 1/2/4 bước, đều tốn 2 nhiên liệu.
- Ao không thể đi vào. Nhiều xe được đứng cùng ô; xe được chờ.
- Chỉ xe tuần tra tiêu thụ nhiên liệu và thu udon.
- Xe tiếp nhiên liệu có nguồn vô hạn, di chuyển không tốn nhiên liệu.
- Khi hai loại xe cùng ô trong ít nhất một step, xe tuần tra tự động được nạp đầy.
- Di chuyển thiếu nhiên liệu, thiếu bước hoặc đến ô không hợp lệ làm câu trả lời không hợp lệ.
- Mỗi xe tuần tra lấy tối đa một phần tại mỗi điểm trong một ngày.
- Điểm đến nằm trên đồng bằng; kho riêng từng đội, phục hồi lên mức tối đa đầu ngày.
- Vị trí và nhiên liệu còn lại được giữ qua ngày; đầu ngày 1 nhiên liệu đầy.
- Giao thông lấy tổng số bước các xe ở ô đường trong hai ngày trước, chia số đội.
  Ngày 1 đường thông thoáng; ngày 2 chỉ dùng lịch sử ngày 1. Trạng thái cố định trong ngày.
- Xếp hạng theo thứ tự: loại udon toàn trận, tổng loại theo ngày, tổng phần,
  tổng thời gian phản hồi hợp lệ cuối cùng của mỗi ngày; sau đó hòa hoặc tung xúc xắc.

## Bổ sung từ ảnh giao diện

- Mã loại xe: `0` = tuần tra, `1` = tiếp xăng.
- Vị trí xuất phát của từng xe được hiển thị trước khi chọn loại.
- Có thể gửi lại lựa chọn trong cửa sổ chọn loại.
- Nếu không chọn kịp, tất cả xe mặc định là tuần tra; vẫn được nộp kế hoạch mỗi ngày.
- Ảnh minh họa có 4 xe, lần lượt ở ô 558, 998, 130, 955.
  Đây là dữ liệu ví dụ, không phải cấu hình cố định.
- Mỗi xe có một mảng lệnh theo thứ tự xe: `0–5` là hướng đi, số âm là số bước chờ.
- Mỗi xe phải sử dụng đúng quỹ bước của ngày; ảnh nộp bài minh họa 228 bước.

## Bổ sung từ tài liệu kỹ thuật và API docs

- Website: https://hexudon.hairbui76.id.vn/ . API docs đọc công khai, không cần đăng nhập.
- `GET /api/game/config?game_id=...`: lấy cấu hình.
- `POST /api/game/agent-types`: body gồm `game_id` và `types`, ví dụ
  `{"game_id":"...","types":[0,1,0,0]}`. Mảng phải theo đúng thứ tự xe.
- `GET /api/game/day?game_id=...`: lấy thông tin ngày hiện tại.
- `POST /api/game/actions`: body gồm `game_id`, `day`, `actions`.
  Ví dụ hình dạng: `{"game_id":"...","day":1,"actions":[[-228],[-228],[-228],[-228]]}`.
  Chỉ dùng ví dụ này nếu thực tế có 4 xe và quỹ ngày là 228 bước.
- Slide chỉ dẫn luyện tập dùng `game_id:team_id` và gửi kế hoạch qua
  `POST /api/game/practice/actions`; cần đối chiếu body của endpoint luyện tập trước khi tích hợp.
- Slide phân biệt thi chính thức chạy theo thời gian và luyện tập tự tiến độ, riêng từng đội.
  API docs hiện còn có nhóm Competitive Practice; không mặc nhiên áp dụng luật nhóm đó cho bài tập lớn.

## Bổ sung từ schema được BTC liên kết

Các thông tin dưới đây lấy từ schema được slide giới thiệu, chưa đối chiếu bằng phản hồi máy chủ thực tế:

- Mã địa hình: `0` đồng bằng, `1` đường bộ, `2` núi, `3` ao.
- Hướng: `0` trên trái, `1` trên phải, tiếp tục theo chiều kim đồng hồ:
  `2` phải, `3` dưới phải, `4` dưới trái, `5` trái.
  Cần kết hợp hình bản đồ trong đề để chuyển thành tọa độ ô kề, không dùng lưới vuông.
- Cấu hình có `agents`: danh sách vị trí xuất phát, thứ tự xe giữ nhất quán giữa các bản tin.
- Trạng thái ngày có `endsAt`, `day`, `agents`, `others`, `traffics`.
  Mỗi xe có `kind`, `pos`, `fuel`; đội khác có `id` và danh sách xe.
- Giao thông có `pos`, `status`: `0` thông thoáng, `1` đông đúc, `2` ùn tắc.
- Schema mô tả `day` là ngày trước thời điểm cung cấp trạng thái và bằng 0 ở đầu ngày đầu tiên.
  Ví dụ lại ghi `day: 1`, và API yêu cầu `day` trong body nộp kế hoạch nhưng chưa giải thích phép chuyển.
  Cần xác minh quy ước chỉ số ngày của máy chủ trước khi gửi kế hoạch.
- Nếu một xe có kế hoạch sai thì toàn bộ kế hoạch bị từ chối.
  Nếu không có kế hoạch hợp lệ trong thời hạn thì tất cả xe chờ hết ngày.

## Các điểm cần làm rõ trước khi nối máy chủ

- Đối chiếu schema với phản hồi thực tế, đặc biệt trường `agents` và chỉ số `day`.
- Body riêng của API luyện tập và cơ chế xác thực khi tích hợp.
- Thứ tự chi tiết trong một step: trừ nhiên liệu, tiếp tế, đến ô và thu thập.
- Quy tắc khi nhiều xe cùng đến điểm có kho không đủ trong cùng step.
- Cách xử lý thu thập khi xe đã ở điểm đến ngay đầu ngày.

Mẫu JSON cục bộ hiện có không chứa `agents`, trong khi schema mô tả trường này.
Không tự gán các vị trí trong ảnh
cho mọi bản đồ. Những điểm chưa rõ sẽ được tách thành quy ước mô phỏng công khai,
không trình bày như luật đã được BTC xác nhận.


## Cập nhật sau khi đối chiếu API ngày 19 tháng 10 năm 2026

API config đã xác nhận trường agents và vị trí xuất phát. API day dùng chỉ số 0 cho ngày đầu,
trong khi giao diện người dùng đếm từ ngày 1. Replay đã xác minh nhiên liệu cập nhật khi đến,
tiếp tế sau khi đến (kể cả step cuối), thu hàng từ frame 1 khi đứng sẵn tại điểm và các trạng thái
đường. Phần chưa rõ ở các mục trước phản ánh tình trạng tài liệu ban đầu; kết luận mới và giới hạn
hiện tại phải đọc theo `simulation_conventions.md` và `api_manual_check.md`.
