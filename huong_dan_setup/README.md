# Hướng dẫn cài đặt và chạy kết nối máy chủ HEXUDON

Dành cho thành viên lần đầu chạy runner trên máy mình. Làm hết hướng dẫn này, bạn sẽ
kiểm tra được token, chạy thử offline và chơi trọn một trận Practice bằng planner `tour`.
Ngày thi tính giờ có thêm lưu ý riêng ở [docs/contest_day.md](../docs/contest_day.md).

Mọi lệnh viết cho PowerShell và **chạy trong thư mục `BTL_TTUD`** (cùng cấp `play_match.py`).

## 1. Yêu cầu

| Thành phần | Yêu cầu                                                                                                                   |
| ------------ | --------------------------------------------------------------------------------------------------------------------------- |
| Python       | 3.10 trở lên (đã chạy với 3.10.11). Kiểm tra bằng `python --version`.                                             |
| Thư viện   | Không cần cài thêm. Runner và thuật toán chỉ dùng thư viện chuẩn; PyTorch chỉ dùng cho phần RL thử nghiệm. |
| Mạng        | Truy cập được https://hexudon.hairbui76.id.vn                                                                           |
| CPU          | Càng nhiều nhân càng tốt: `tour` lập kế hoạch song song (máy 8 nhân dùng 6 tiến trình).                      |
| Tài khoản  | Tài khoản đội trên website BTC để lấy token.                                                                        |

## 2. Cấu hình token

1. Đăng nhập website BTC bằng tài khoản đội và lấy token (chuỗi JWT, dạng `eyJ...`).
   Token có hạn **48 giờ**, hết hạn thì lấy lại.
2. Tạo file `.env` trong thư mục `BTL_TTUD` với đúng một dòng:

   ```
   HEXUDON_TOKEN=eyJ...
   ```
3. `.env` đã có trong `.gitignore`. Không commit, không dán token vào chat hay tài liệu.

Mã đội được đọc từ token. Runner chơi cho đội nào là do token quyết định, nên muốn chơi cho
đội khác thì phải dùng token của đội đó.

## 3. Kiểm tra cài đặt

**Bộ kiểm thử** (khoảng 20 giây):

```powershell
python -X utf8 -m unittest discover -s tests
```

Có 103 test. Trên bản mã không kèm dữ liệu replay BTC, **8 lỗi sau là bình thường** vì do môi trường:

- 7 test `ServerReplayTests` cần thư mục `experiments/data/api_evidence`, thư mục này không được đưa lên Git;
- `test_rl_policy` cần PyTorch hoạt động.

Mọi test còn lại phải đạt.

**Kiểm tra kết nối** với một ID trận (chỉ đọc, không nộp bài):

```powershell
python -X utf8 play_match.py --preflight --game-id ID_TRAN --algorithm tour --mode practice
```

Các dòng phải là `OK`: token còn hạn, đội có trong trận, đọc được bản đồ và thử lập kế hoạch hợp lệ.
Cảnh báo độ trễ `/state` khoảng 1–2 giây đã gặp khi thử và không cản việc chạy Practice.

## 4. Chạy thử offline (không cần mạng)

Dùng bản đồ mẫu trong `Đề bài/` để xem trước điểm của từng đội hình. Trong `--types`,
`0` là xe tuần tra, `1` là xe tiếp tế, theo đúng thứ tự xe.

```powershell
# Bộ chọn tự thử các đội hình (20 giây)
python -X utf8 src/main.py select --config "Đề bài/input_sample.json" --starts 558 998 130 955 --strategy tour --seconds 20 --output results/types.json

# Mô phỏng cả trận với một đội hình cụ thể (khoảng 50 giây)
python -X utf8 src/main.py demo --config "Đề bài/input_sample.json" --starts 558 998 130 955 --types 1 0 0 0 --strategy tour --seconds 5 --output results/demo.json
```

`--starts` là vị trí xuất phát của trận mẫu, không dùng cho trận khác. Với trận mới, xem mục 5:
runner tự lấy cấu hình từ máy chủ.

Kết quả tham khảo trên bản đồ mẫu (`tour`, 5 giây/ngày), dạng (số loại, tổng loại theo ngày, số phần):

| Đội hình                   | Điểm         |
| ----------------------------- | -------------- |
| `1 1 1 0` (1 xe tuần tra)  | (20, 175, 229) |
| `0 0 0 0` (toàn tuần tra) | (20, 185, 333) |
| `1 0 0 0` (1 xe tiếp tế)  | (20, 200, 604) |

## 5. Chơi một trận Practice

### Bước 1: xem danh sách câu và trạng thái

Không cần chép ID trận bằng tay. Lệnh sau (chỉ đọc) liệt kê mọi trận, từng câu kèm game_id,
và trạng thái của đội mình ở mỗi câu:

```powershell
python -X utf8 phan_tich_map.py --danh-sach
```

```
== Trận 11 Practice Match (Practice, 23 đội)
  Q01  c57bfe4b-55ef-416f-893f-1ccaf86a8b87  finished, đội hình [1, 0, 0, 0], đã nộp 55 ngày, 622 phần
  Q04  83f54883-4731-472e-bec2-f36f161b1374  selecting_agents, chưa chọn loại xe
  ...
== Trận 14 Mock Contest (tính giờ, 22 đội)
  ...
```

| Kết quả                                                      | Làm gì                                                                               |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `selecting_agents`, loại xe chưa chọn                     | Sang bước 2, runner sẽ chọn xe.                                                    |
| `in_progress`, loại xe đã chốt và hợp lý              | Sang bước 2, runner dùng loại xe đã chốt.                                       |
| Loại xe đã chốt nhưng kém (ví dụ chỉ 1 xe `patrol`) | Không đổi được nữa (máy chủ trả lỗi 400). Reset theo mục 6 rồi làm lại. |
| `finished`                                                   | Trận đã chơi xong. Muốn chơi lại thì reset theo mục 6.                        |

### Bước 2: chạy runner	

```powershell
# Gõ tên câu; runner tự đổi thành game_id và để tour tự chọn đội hình bằng mô phỏng
python -X utf8 play_match.py Q07 --mode practice --algorithm tour

# Hoặc chỉ định đội hình đã thử ở mục 4
python -X utf8 play_match.py Q07 --mode practice --algorithm tour --types 1 0 0 0
```

- Luôn ghi rõ `--mode practice`. Practice có thể trả đồng hồ bằng 0, nên `auto` dễ nhận nhầm loại trận.
  `--mode practice` cũng giúp tên câu chỉ được tìm trong trận Practice. Nếu tên câu có ở nhiều trận
  cùng loại, thêm `--match MÃ_TRẬN`. Vẫn có thể dán game_id đầy đủ như trước.
- `--types` phải đủ số xe và có ít nhất một xe tuần tra. Nếu loại xe đã chốt trên máy chủ,
  runner dùng loại đã chốt và bỏ qua `--types`.
- Mỗi ngày runner lập kế hoạch khoảng 26 giây (`daySeconds` trừ 4 giây dự phòng). Trận 10 ngày mất
  khoảng 5 phút. Không dùng máy cho việc nặng khác trong lúc chạy.

Màn hình khi chạy đúng:

```
Vai trò đã chọn (0 tuần tra, 1 tiếp tế): [1, 0, 0, 0]
Ngày 1: tạo output bằng tour, ngân sách 26.00s.
Ngày 1: máy chủ đã nhận kế hoạch (practice).
...
Trận đã kết thúc. Kết quả đội mình: {'distinct_types': 20, 'cumulative_daily_types': 200, 'total_servings': 622, ...}
Đã dọn dữ liệu chạy tạm của trận.
```

Kết quả trên là lượt chạy thật ngày 23/10/2026 (đội 61, trận mẫu `c57bfe4b-...`, đội hình `1 0 0 0`).
Trường `days_submitted` có thể lớn hơn số ngày (ví dụ 55 cho trận 10 ngày). Đó là bộ đếm của
máy chủ, không phải lỗi.

## 6. Reset trận Practice

Reset **xóa mọi bài đã nộp và điểm Practice** của đội trong trận đó, rồi đưa trận về bước chọn
loại xe. Chỉ dùng cho Practice của đội mình, **không bao giờ dùng trong trận thi chính thức**.
Không reset khi runner đang chạy.

```powershell
@'
import sys; sys.path.insert(0, 'src')
from hexudon.live_api import LiveAPI, resolve_game_id
api = LiveAPI('.env')
# practice=True: tên câu chỉ được tìm trong trận Practice, không bao giờ trỏ tới trận tính giờ.
game_id = resolve_game_id(api, sys.argv[1], practice=True)
print(api.request('POST', '/api/game/practice/reset', body={'game_id': game_id}))
'@ | python -X utf8 - Q02
```

Kết quả đúng có dạng `{'ok': True, 'game_id': 'GAME_ID:ID_DOI'}`. Sau đó chạy lại mục 5.
Nếu trước khi reset có một lượt runner chưa chạy xong, thêm `--run-dir results/live/lan_moi`
để không dùng lại checkpoint cũ.

## 7. Lỗi thường gặp

| Thông báo                                                          | Nguyên nhân và cách xử lý                                                                |
| -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `Cần HEXUDON_TOKEN trong .env`                                    | Thiếu `.env`, đặt sai thư mục hoặc sai tên biến. Xem mục 2.                         |
| `API HTTP 401` / `403`                                           | Token hết hạn hoặc không thuộc đội trong trận. Lấy token mới.                        |
| `API HTTP 400: agent type selection is closed`                     | Loại xe đã chốt. Practice thì reset (mục 6), trận thi thì chơi với loại đã chốt. |
| `Trận đã trở lại bước chọn vai trò; dùng --run-dir mới` | Trận vừa bị reset sau một lượt chạy cũ. Thêm `--run-dir` mới.                      |
| `Cấu hình trận đã đổi; cần dùng --run-dir mới.`          | Checkpoint cũ không khớp trận hiện tại. Thêm `--run-dir` mới.                        |
| Runner bị ngắt (Ctrl+C, mất mạng)                                | Chạy lại **đúng lệnh cũ**. Runner đọc checkpoint và không nộp trùng ngày.   |
| `Planner tour lỗi ...; dùng Greedy`                              | Runner tự chuyển sang phương án dự phòng. Để chạy tiếp và lưu log để kiểm tra. |

## 8. Phân tích map: udon tối đa, đội hình và xếp hạng

`phan_tich_map.py` chỉ gửi GET, không chọn xe và không nộp bài.

```powershell
# Danh sách trận, câu hỏi (game_id) và trạng thái của đội mình
python -X utf8 phan_tich_map.py --danh-sach

# Cận trên theo số xe tiếp tế và điểm hiện tại của đội mình
python -X utf8 phan_tich_map.py Q07

# Thêm đội hình đề xuất (mô phỏng 26 giây như runner) và bảng xếp hạng
python -X utf8 phan_tich_map.py Q07 --select 26 --xep-hang

# Mọi câu của trận Practice; --match 14 để xem trận Mock Contest
python -X utf8 phan_tich_map.py --tat-ca --xep-hang
python -X utf8 phan_tich_map.py Q01 --match 14 --xep-hang

# File cấu hình offline
python -X utf8 phan_tich_map.py --config "Đề bài/input_sample.json" --starts 558 998 130 955
```

Ví dụ kết quả (trận mẫu, đội 61):

```
Cận trên theo số xe tiếp tế (không đội nào vượt được; chưa chắc đạt được):
  0 tiếp tế: (20, 200, 640)   đội hình [0, 0, 0, 0]
  1 tiếp tế: (20, 200, 825)   đội hình [0, 0, 0, 1]
  2 tiếp tế: (20, 200, 550)   đội hình [0, 0, 1, 1]
  3 tiếp tế: (20, 198, 275)   đội hình [0, 1, 1, 1]
Điểm máy chủ của đội 61 (đội hình [1, 0, 0, 0], ...): (20, 200, 622); cận ... (20, 200, 825), số phần đạt 75%.
```

- **Cận trên** là mức không đội nào vượt được với đội hình đó. Mỗi xe mỗi ngày được tính số điểm tối
  đa theo hai cách đều có chứng minh, lấy giá trị nhỏ hơn: cây khung nhỏ nhất giữa các điểm (chặt ở
  ngày dài) và quy hoạch động ng-route (chặt ở ngày ngắn; Q06 Mock: cận giảm từ 1039 xuống 952). Khi
  không có xe tiếp tế còn tính thêm giới hạn nhiên liệu. Đây không phải điểm chắc chắn đạt được; đội
  hình có cận thấp hơn điểm đã đạt thì chắc chắn kém hơn. Cận giả định đường luôn thông thoáng, nên
  ở Practice (một đội, xe tự gây tắc đường) tỉ lệ đạt thấp hơn trận nhiều đội.
- **Đội hình đề xuất** dùng đúng bộ chọn của runner. Runner tự chọn đội hình khi chạy không có `--types`.
  Bộ chọn bỏ trước các đội hình có cận dưới 81% cận cao nhất (ở Mock, đội hình dẫn đầu luôn đạt trên
  mức đó), rồi chỉ mô phỏng các đội hình còn lại.
- **Xếp hạng:** website chỉ hiện "Bảng xếp hạng tạm thời" trên trang câu hỏi Practice không cho reset.
  Trang "Xếp hạng vòng" thuộc quyền quản trị. `--xep-hang` lấy danh sách đội thật của trận rồi đọc
  điểm từng đội (Practice), hoặc đọc kết quả chung của trận (trận tính giờ).
- Danh sách trận lấy từ API quản lý của website (`/manager/api`) bằng cùng token. Nếu API này lỗi,
  công cụ và runner vẫn chạy được với game_id dán tay.

## 9. Thi tự động mọi câu cùng lúc (`thi_dau.py`)

Dùng cho vòng thi tính giờ: tự lấy danh sách câu, mỗi câu một runner riêng chạy song song, tự
khởi động lại runner bị dừng giữa trận, đọc điểm ngay khi từng câu xong và so với cận.

```powershell
# Ngày thi: dán ID trận (game_id) là chạy, không quét danh sách trận. Chương trình tự nhận
# Practice hay trận tính giờ (in ra ở dòng đầu, ví dụ "f06e9b26 (timed)"); ép bằng --mode nếu cần
python -X utf8 thi_dau.py --match f06e9b26-9e6e-4401-b058-7bceaddf10cb

# Nhiều ID cùng lúc: mỗi ID một runner song song
python -X utf8 thi_dau.py <game_id_1> <game_id_2>

# Tổng duyệt: mã số trận (14) thì tự quét mọi câu của trận đó
python -X utf8 thi_dau.py --match 14

# Mock Contest tự reset mỗi 10 phút: chỉ vào câu khi câu ở bước chọn xe, chơi 2 vòng liên tiếp
python -X utf8 thi_dau.py --match 14 --wait-new --vong 2

# Chỉ một số câu
python -X utf8 thi_dau.py --match 14 Q01 Q04
```

- Số nhân dùng mặc định là số nhân của máy trừ 1 (`--cores`), chia đều cho các câu chưa xong (kể cả
  câu đang chờ lượt), tối thiểu 1 tiến trình mỗi câu; câu vào sau khi nhiều câu đã xong được nhiều
  tiến trình hơn. Không để câu vào đầu giữ hết nhân: các câu sau tranh CPU, sàng lọc đội hình bị nhiễu.
- Màn hình in ngay khi từng câu sang ngày mới (`ngày 7/10, đã nộp`), kèm xếp hạng sau ngày vừa xong:
  hạng của mình và ba đội đầu. Trận tính giờ đọc một lần `/result`; Practice đọc điểm từng đội (danh
  sách đội lấy một lần từ API quản lý), mất vài giây và không làm chậm runner.
- Log từng câu ở `results/thi_dau/<thời điểm>/<câu>/runner.log`, tổng kết ở `tong_ket.json`.
- Thời gian một câu do máy chủ quyết định (số ngày × `daySeconds` + thời gian chọn xe, khoảng 5,5–8,5
  phút ở Mock Contest); chương trình luôn nộp kịp mỗi ngày rồi nộp lại khi có bài tốt hơn.
- Tổng duyệt đêm 23–24/10/2026 (8 câu Mock Contest song song, 11 vòng): mọi câu chạy trọn, không
  runner nào phải khởi động lại. 9 vòng chọn đúng đội hình đạt trung bình 90,1% cận chặt (89,6–90,5%).
  Từng câu: Q05 92,7%, Q01 92,0%, Q04 90,8%, Q06 89,8%, Q02 88,6%, Q11 88,6%, Q03 88,2%, Q18 87,9%.
  2 vòng còn lại (85,7%, 85,8%) chọn nhầm đội hình khi tám câu tranh CPU; lỗi này đã sửa (mục 8, cách
  chia nhân ở trên), 2 vòng chạy lại sau khi sửa đạt 89,8% và 90,1%.

## 10. Tối ưu điểm Practice (`toi_uu_practice.py`)

Practice chỉ có một đội tạo giao thông và simulator khớp máy chủ, nên có thể chạy nhiều lượt cả trận
offline song song (mọi vị trí đặt xe tiếp tế × nhiều seed) rồi nộp lượt điểm cao nhất.

```powershell
# Chỉ mô phỏng và so với điểm đang có trên máy chủ, không reset/nộp
python -X utf8 toi_uu_practice.py Q04 --dry-run

# Mọi câu Practice: reset và nộp lại CHỈ khi lượt tốt nhất cao hơn điểm đang có
python -X utf8 toi_uu_practice.py

# Cách cũ (một phương án mỗi ngày, không xét tắc đường ngày mai)
python -X utf8 toi_uu_practice.py --look 0 --runs 14 --seconds 5
```

- Ở Practice chỉ có xe của đội mình nhưng ngưỡng tắc rất thấp (đông 3, tắc 4 lượt trong hai ngày), nên
  xe nhà làm tắc các trục đường chính: Q01 được 596 suất, gần bằng 574 khi mọi đường luôn đông, so
  với 694 khi đường luôn thông. Vì vậy mỗi ngày chương trình thử 6 mức phạt ô đường sắp tắc (chỉ đổi
  đường được chọn, số bước vẫn theo chi phí thật), lập kế hoạch thử cho ngày hôm sau rồi giữ phương án
  có điểm sau hai ngày cao nhất. Một lượt mất khoảng 5 phút (mặc định 7 lượt song song mỗi câu).
- Cận trên giả định đường luôn thông, nên ở Practice không đạt được gần cận: ở Q01 và Q03, 90% cận
  còn cao hơn điểm planner đạt khi đường luôn thông. Mọi đội đều dưới khoảng 80% cận ở Practice.

- Trước khi nộp mỗi ngày, chương trình đối chiếu vị trí, nhiên liệu và mặt đường trên máy chủ với mô
  phỏng; lệch thì dừng, không nộp tiếp.
- Bỏ qua câu có lượt nộp trong 15 phút gần đây (có thể thành viên khác đang chơi).
- Kết quả và chuỗi lệnh tốt nhất lưu ở `results/practice_best/<thời điểm>/`.
- Đêm 24/10/2026: 8 lượt nộp đều được máy chủ chấm khớp tuyệt đối với mô phỏng; đội 61 đứng hạng 1
  ở 8/9 câu Practice (Q03 hạng 2: 693 so với 697).

## 11. Tài liệu liên quan

- [docs/contest_day.md](../docs/contest_day.md): quy trình ngày thi tính giờ (`--mode timed`).
- [docs/auto_submit.md](../docs/auto_submit.md): toàn bộ tùy chọn của `play_match.py`, checkpoint, `--dry-run`.
- [docs/tour_planner.md](../docs/tour_planner.md): cách planner `tour` hoạt động.
- [docs/rules.md](../docs/rules.md): luật chơi và quy ước API.
