# Tự động chơi một trận từ ID

Chạy `play_match.py` tại thư mục dự án. Script dùng API của website Việt Nam, tự lấy cấu hình, chọn vai trò nếu chưa chọn, đọc vị trí/nhiên liệu/giao thông thật đầu mỗi ngày, tạo và kiểm tra kế hoạch, rồi nộp tới khi trận kết thúc. Người dùng chỉ cần ID trận và token còn hiệu lực trong `.env`.

## Cách chạy

```powershell
python -X utf8 play_match.py ID_TRAN --algorithm greedy
```

Nếu không truyền ID, script sẽ hỏi ID trong cửa sổ lệnh:

```powershell
python -X utf8 play_match.py --algorithm greedy
```

Các lựa chọn thuật toán:

| Công tắc | Ý nghĩa |
|---|---|
| `--algorithm greedy` | Chọn mục tiêu Greedy, tìm đường A* có ràng buộc. Đây là mặc định. |
| `--algorithm lookahead` | Nhìn trước hai điểm, tìm đường A* có ràng buộc. |
| `--algorithm rollout` | Tạo kế hoạch Greedy/Lookahead rồi so kết quả dự báo tới cuối trận bằng mô phỏng một đội. |

`--predict` là tên thay thế của `--algorithm`. Script này chưa tích hợp mô hình RL. Rollout luôn lấy lại đường thật vào ngày tiếp theo; phần dự báo tương lai không biết bài nộp của đội khác, nên không bảo đảm tối ưu trong trận nhiều đội.

## Loại trận và vai trò xe

Mặc định `--mode auto` phân biệt trận tính giờ và Practice theo trường thời gian trong trạng thái máy chủ. ID Practice có hậu tố `:ID_DOI` được nhận dạng là Practice; website cũng cho phép tài khoản đội dùng ID trần và tự ánh xạ sang Practice của đội mình. Nếu API không có đủ dấu hiệu để phân biệt, script yêu cầu chỉ định mode thay vì đoán endpoint.

```powershell
python -X utf8 play_match.py ID_TRAN --mode timed --algorithm greedy
python -X utf8 play_match.py ID_TRAN --mode practice --algorithm lookahead
```

Trận tính giờ nộp qua `/api/game/actions`; Practice nộp qua `/api/game/practice/actions`. Script không gọi API reset và không sửa các ngày trước. Chế độ Competitive Practice dùng timeline chung và endpoint `/competitive/actions` chưa được tích hợp; không dùng `--mode practice` để thay cho chế độ đó. Địa chỉ mặc định là `https://hexudon.hairbui76.id.vn`; giao thức này không tự tương thích máy chủ thi chính thức khác hoặc giao thức `/setting`, `/agent`, `/` của nhánh cũ.

Mặc định `--roles auto` dành tối đa tám giây để chọn vai trò bằng mô phỏng trước trận, giới hạn thêm theo cửa sổ chọn vai trò của máy chủ. Có thể chỉ định:

```powershell
python -X utf8 play_match.py ID_TRAN --roles all-patrol
python -X utf8 play_match.py ID_TRAN --roles last-supply
python -X utf8 play_match.py ID_TRAN --types 0 1 0 0
```

`--types` phải đúng số xe, có ít nhất một xe tuần tra; `0` là tuần tra, `1` là tiếp tế. Nếu máy chủ đã chốt vai trò thì script dùng vai trò thật, không ghi đè lựa chọn đó. ID đội được lấy mặc định từ token; có `--team` nếu tài khoản thi dùng mã đội khác.

## Thời gian và trạng thái thực tế

Mặc định thuật toán được tối đa 20 giây mỗi ngày; script luôn giới hạn lại theo thời gian còn lại máy chủ báo và chừa bốn giây cho kiểm tra, truyền bài. Thời gian lựa chọn vai trò tách khỏi thời gian lập kế hoạch ngày. Không cố định ngân sách thí nghiệm 0,25 giây.

```powershell
python -X utf8 play_match.py ID_TRAN --algorithm greedy --seconds 20 --reserve 4
```

Mỗi ngày, script dùng `/api/game/day` để đọc `traffics`, vị trí và nhiên liệu, đồng thời lấy các loại udon đội mình đã thu từ trạng thái máy chủ. Nó không dùng giao thông do simulator dự báo thay cho giao thông thật. Các kế hoạch của đội khác không được tải. Trạng thái đường trong tương lai của rollout vẫn chỉ là giả định một đội. `reserve` là khoảng đệm, không phải bảo đảm mạng luôn trả lời đúng hạn; nếu đã quá hạn, script không gửi bài của ngày cũ.

## Tiếp tục sau khi ngắt

Output, trạng thái và checkpoint được lưu dưới `results/live/ID_TRAN_ID_DOI`. Chạy lại cùng lệnh để tiếp tục. Script không gửi lại ngày đã được xác nhận; khi mất phản hồi, nó kiểm tra ngày và bộ đếm nộp bài từ máy chủ. Nếu vẫn cần gửi lại, nó giữ nguyên output đã lưu thay vì sinh một kế hoạch khác. Trạng thái `advanced` nghĩa là máy chủ đã chuyển ngày sau phản hồi không chắc chắn, không tự khẳng định hash output đã được đối chiếu.

Chỉ chạy một chương trình nộp bài cho cùng đội và trận; không đồng thời chỉnh bài trên website. Khóa hệ điều hành ngăn hai tiến trình dùng cùng thư mục checkpoint, và được nhả khi tiến trình tắt. Nếu người dùng đã reset Practice bằng website, hãy chọn thư mục mới:

```powershell
python -X utf8 play_match.py ID_TRAN --mode practice --run-dir results/live/lan_thu_moi
```

Khi trận tính giờ đã có bài nộp trong ngày nhưng không có checkpoint tương ứng, script chờ ngày kế tiếp thay vì tự ghi đè bài đó. HTTP 401/403 cần kiểm tra token/quyền tham gia; script không tự đăng nhập lại hoặc in token vào nhật ký.

## Kiểm tra không nộp bài

```powershell
python -X utf8 play_match.py ID_TRAN --inspect
python -X utf8 play_match.py ID_TRAN --algorithm greedy --dry-run
```

`--inspect` chỉ đọc cấu hình/trạng thái. `--dry-run` tạo và kiểm tra output cho ngày đang chạy nhưng không POST; nếu đang ở bước chọn vai trò, nó chỉ đề xuất vai trò rồi dừng. Checkpoint chạy thử được lưu riêng, không đánh dấu như bài đã nộp thật. Có thể dùng `--max-days 1` để giới hạn một ngày được xác nhận trong một lượt kiểm tra có nộp bài.

## Phạm vi đã kiểm tra

Đặc tả API hiện tại đã được đọc ngày 19/10/2026. Script đã đọc cấu hình và trạng thái Practice Q04 của nhóm 62 trên website thật ở chế độ `--inspect`, không reset và không nộp lại trận đã kết thúc. Các luồng nộp toàn trận Practice, trận tính giờ, cập nhật road/fuel, checkpoint, mất phản hồi và chuyển ngày được kiểm thử bằng máy chủ giả lập trong bộ kiểm thử. Chưa chạy một trận tính giờ đang hoạt động trên website thật; cần chạy thử trên trận được giao trước khi dùng chính thức. Không gọi kiểm thử giả lập là bằng chứng đã nộp thành công lên BTC.

Nguồn giao thức: https://hexudon.hairbui76.id.vn/openapi.json ; bản đặc tả đã lưu ở `docs/api/openapi.json`.

Sau khi máy chủ xác nhận trận đã kết thúc và đọc được kết quả, script tự xóa các tệp chạy tạm và thư mục nếu đã rỗng. Khi bị lỗi, ngắt giữa trận, dùng --max-days, --inspect hoặc --dry-run, dữ liệu vẫn được giữ để tiếp tục hoặc kiểm tra. Dữ liệu khác do người dùng đặt trong --run-dir không bị xóa. Chỉ reset sau khi script đã kết thúc và dọn xong; nếu reset giữa lượt đang chạy, vẫn cần --run-dir mới.

## Tổ chức mã nguồn

- `src/hexudon/live.py` điều khiển lượt chơi, gọi thuật toán và xử lý từng ngày.
- `src/hexudon/live_api.py` đọc token và thực hiện GET/POST với API BTC.
- `src/hexudon/live_storage.py` ghi checkpoint, khóa chống chạy trùng và dọn dữ liệu sau trận.
- `play_match.py` là điểm chạy từ dòng lệnh; các lệnh sử dụng vẫn giữ nguyên.
