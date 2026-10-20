# Hướng dẫn sử dụng và kiểm chứng bài tập lớn HEXUDON

Tài liệu này tập hợp hướng dẫn chạy chương trình, quy tắc mô phỏng và nguồn kiểm chứng kết quả. Báo cáo chính thức nằm tại [bản DOCX](../bao_cao_hexudon.docx).

Phần kết quả hiện tại sử dụng phiên bản lập tuyến `tour`. Các số liệu đối chứng cũ và RL được giữ ở cuối tài liệu để tra cứu phụ lục; chúng không thay thế bảng điểm hiện tại. Những đường dẫn Markdown cũ được nhắc trong các tài liệu đã phát hành tương ứng với tên nguồn ghi đầu từng phần dưới đây.

## Cấu trúc thư mục thực nghiệm

Thư mục `experiments/` được tổ chức thành bốn nhóm: `benchmark/` đo và tổng hợp hiệu năng, `api/` đối chiếu máy chủ, `rl/` huấn luyện và đánh giá học tăng cường, `data/` chứa các bộ dữ liệu và kết quả. Việc sắp xếp chỉ đổi vị trí tệp; số liệu thực nghiệm đã lưu được giữ nguyên. Các đường dẫn trong báo cáo DOCX phát hành trước lần sắp xếp này tương ứng với đường dẫn mới: mã chuyển vào nhóm chức năng, còn các thư mục kết quả chuyển vào `experiments/data/` với nguyên tên.

Có thể chạy trực tiếp script theo đường dẫn mới hoặc dùng một điểm vào chung:

```powershell
python -X utf8 experiments/run.py --help
python -X utf8 experiments/run.py benchmark --games 10 --sizes 8 16 32 --seconds 0.25
python -X utf8 experiments/run.py summarize
python -X utf8 experiments/run.py train_rl_policy --episodes 1024 --seeds 71 72 73
```

Các công cụ trong nhóm API giữ nguyên hành vi nộp hoặc reset được mô tả ở từng mục; việc gom thư mục không biến chúng thành lệnh chỉ đọc. Cần token và các dữ liệu đầu vào tại máy như trước đây.

## Mục lục

- [Đối chứng có kiểm soát cho tour](#thuc-nghiem-tour)

1. [Hướng dẫn chạy và nộp bài](#su-dung)
2. [Kết quả hiện tại được Ban tổ chức chấm](#ket-qua)
3. [Hướng dẫn kiểm chứng và API đã sử dụng](#kiem-chung)
4. [Quy tắc bài toán](#quy-tac)
5. [Quy ước của bộ mô phỏng](#mo-phong)
6. [Phương pháp lập tuyến cho đội xe](#thuat-toan)
7. [Đối chiếu API trong giai đoạn xây dựng simulator](#doi-chieu-api)
8. [Thí nghiệm huấn luyện học tăng cường](#rl)
9. [Đối chứng Greedy và Lookahead ở phiên bản trước](#doi-chung-cu)
10. [Đối chứng RL kết hợp heuristic ở phiên bản trước](#rl-cu)

<a id="su-dung"></a>

## 1. Hướng dẫn chạy và nộp bài

Nguồn trước khi hợp nhất: `auto_submit.md`.

<!-- begin:auto_submit.md -->
Chạy `play_match.py` tại thư mục dự án. Script dùng API của website Việt Nam, tự lấy cấu hình, chọn vai trò nếu chưa chọn, đọc vị trí/nhiên liệu/giao thông thật đầu mỗi ngày, tạo và kiểm tra kế hoạch, rồi nộp tới khi trận kết thúc. Người dùng chỉ cần ID trận và token còn hiệu lực trong `.env`.

### Cách chạy

```powershell
python -X utf8 play_match.py ID_TRAN --algorithm tour
```

Nếu không truyền ID, script sẽ hỏi ID trong cửa sổ lệnh:

```powershell
python -X utf8 play_match.py --algorithm tour
```

Luồng nộp bài chỉ sử dụng `tour`, cũng là mặc định. Công tắc `--predict` là tên thay thế của `--algorithm`. Nếu tour không tạo được kế hoạch hợp lệ, chương trình dừng trước khi gửi; nó không tự chuyển sang Greedy.

Greedy được giữ trong `src/hexudon/planner.py` để xem mã và chạy đối chứng offline, không dùng trong `play_match.py`. Ví dụ tạo kế hoạch trên bản đồ mẫu mà không nộp bài:

```powershell
python -X utf8 src/main.py demo --size 8 --strategy greedy --seconds 1
```

### Loại trận và vai trò xe

Mặc định `--mode auto` phân biệt trận tính giờ và Practice theo trường thời gian trong trạng thái máy chủ. ID Practice có hậu tố `:ID_DOI` được nhận dạng là Practice; website cũng cho phép tài khoản đội dùng ID trần và tự ánh xạ sang Practice của đội mình. Nếu API không có đủ dấu hiệu để phân biệt, script yêu cầu chỉ định mode thay vì đoán endpoint.

```powershell
python -X utf8 play_match.py ID_TRAN --mode timed --algorithm tour
python -X utf8 play_match.py ID_TRAN --mode practice --algorithm tour
```

Trận tính giờ nộp qua `/api/game/actions`; Practice nộp qua `/api/game/practice/actions`. Script không gọi API reset và không sửa các ngày trước. Chế độ Competitive Practice dùng timeline chung và endpoint `/competitive/actions` chưa được tích hợp; không dùng `--mode practice` để thay cho chế độ đó. Địa chỉ mặc định là `https://hexudon.hairbui76.id.vn`; giao thức này không tự tương thích máy chủ thi chính thức khác hoặc giao thức `/setting`, `/agent`, `/` của nhánh cũ.

Mặc định `--roles auto` dành tối đa 20 giây để chọn vai trò bằng mô phỏng trước trận, giới hạn thêm theo cửa sổ chọn vai trò của máy chủ. Có thể chỉ định:

```powershell
python -X utf8 play_match.py ID_TRAN --roles all-patrol
python -X utf8 play_match.py ID_TRAN --roles last-supply
python -X utf8 play_match.py ID_TRAN --types 0 1 0 0
```

`--types` phải đúng số xe, có ít nhất một xe tuần tra; `0` là tuần tra, `1` là tiếp tế. Nếu máy chủ đã chốt vai trò thì script dùng vai trò thật, không ghi đè lựa chọn đó. ID đội được lấy mặc định từ token; có `--team` nếu tài khoản thi dùng mã đội khác.

### Thời gian và trạng thái thực tế

Mặc định thuật toán được tối đa 20 giây mỗi ngày; script luôn giới hạn lại theo thời gian còn lại máy chủ báo và chừa bốn giây cho kiểm tra, truyền bài. Thời gian lựa chọn vai trò tách khỏi thời gian lập kế hoạch ngày. Không cố định ngân sách thí nghiệm 0,25 giây.

```powershell
python -X utf8 play_match.py ID_TRAN --algorithm tour --seconds 20 --reserve 4
```

Mỗi ngày, script dùng `/api/game/day` để đọc `traffics`, vị trí và nhiên liệu, đồng thời lấy các loại udon đội mình đã thu từ trạng thái máy chủ. Nó không dùng giao thông do simulator dự báo thay cho giao thông thật. Các kế hoạch của đội khác không được tải. `reserve` là khoảng đệm, không phải bảo đảm mạng luôn trả lời đúng hạn; nếu đã quá hạn, script không gửi bài của ngày cũ.

### Tiếp tục sau khi ngắt

Output, trạng thái và checkpoint được lưu dưới `results/live/ID_TRAN_ID_DOI`. Chạy lại cùng lệnh để tiếp tục. Script không gửi lại ngày đã được xác nhận; khi mất phản hồi, nó kiểm tra ngày và bộ đếm nộp bài từ máy chủ. Nếu vẫn cần gửi lại, nó giữ nguyên output đã lưu thay vì sinh một kế hoạch khác. Trạng thái `advanced` nghĩa là máy chủ đã chuyển ngày sau phản hồi không chắc chắn, không tự khẳng định hash output đã được đối chiếu.

Chỉ chạy một chương trình nộp bài cho cùng đội và trận; không đồng thời chỉnh bài trên website. Khóa hệ điều hành ngăn hai tiến trình dùng cùng thư mục checkpoint, và được nhả khi tiến trình tắt. Nếu người dùng đã reset Practice bằng website, hãy chọn thư mục mới:

```powershell
python -X utf8 play_match.py ID_TRAN --mode practice --run-dir results/live/lan_thu_moi
```

Khi trận tính giờ đã có bài nộp trong ngày nhưng không có checkpoint tương ứng, script chờ ngày kế tiếp thay vì tự ghi đè bài đó. HTTP 401/403 cần kiểm tra token/quyền tham gia; script không tự đăng nhập lại hoặc in token vào nhật ký.

### Kiểm tra không nộp bài

```powershell
python -X utf8 play_match.py ID_TRAN --inspect
python -X utf8 play_match.py ID_TRAN --algorithm tour --dry-run
```

`--inspect` chỉ đọc cấu hình/trạng thái. `--dry-run` tạo và kiểm tra output cho ngày đang chạy nhưng không POST; nếu đang ở bước chọn vai trò, nó chỉ đề xuất vai trò rồi dừng. Checkpoint chạy thử được lưu riêng, không đánh dấu như bài đã nộp thật. Có thể dùng `--max-days 1` để giới hạn một ngày được xác nhận trong một lượt kiểm tra có nộp bài.

### Phạm vi đã kiểm tra

Đặc tả API được lưu tại docs/api/openapi.json. Tới ngày 20/10/2026, runner đã nộp thật các lượt Practice Greedy và 8 bài tour, tổng 80 kế hoạch ngày của đợt tour; đối chiếu 12155 frame không phát hiện sai khác ở các trường kiểm tra. Kết quả nằm trong experiments/data/tour_api_evidence/summary.json. Luồng trận tính giờ và các tình huống mất phản hồi vẫn được kiểm thử bằng máy chủ giả lập; chưa chạy một trận tính giờ thật trọn vẹn. Practice thành công không thay thế kiểm chứng hạn nộp 30 giây.

Nguồn giao thức: https://hexudon.hairbui76.id.vn/openapi.json ; bản đặc tả đã lưu ở `docs/api/openapi.json`.

Sau khi máy chủ xác nhận trận đã kết thúc và đọc được kết quả, script tự xóa các tệp chạy tạm và thư mục nếu đã rỗng. Khi bị lỗi, ngắt giữa trận, dùng --max-days, --inspect hoặc --dry-run, dữ liệu vẫn được giữ để tiếp tục hoặc kiểm tra. Dữ liệu khác do người dùng đặt trong --run-dir không bị xóa. Chỉ reset sau khi script đã kết thúc và dọn xong; nếu reset giữa lượt đang chạy, vẫn cần --run-dir mới.

### Tổ chức mã nguồn

- `src/hexudon/live.py` điều khiển lượt chơi, gọi thuật toán và xử lý từng ngày.
- `src/hexudon/live_api.py` đọc token và thực hiện GET/POST với API BTC.
- `src/hexudon/live_storage.py` ghi checkpoint, khóa chống chạy trùng và dọn dữ liệu sau trận.
- `play_match.py` là điểm chạy từ dòng lệnh; các lệnh sử dụng vẫn giữ nguyên.
<!-- end:auto_submit.md -->

<a id="ket-qua"></a>

## 2. Kết quả hiện tại được Ban tổ chức chấm

Nguồn trước khi hợp nhất: `tour_server_results.md`.

<!-- begin:tour_server_results.md -->
Ngày kiểm chứng: 20/10/2026. Tám bản đồ Practice khác nhau, đội 62; Q02 trùng Q01 nên không tính là mẫu độc lập. Đội hình cố định theo lượt chọn đã lưu; planner dùng 5 giây/ngày và giao thông thật từ API mỗi ngày.

| Bài | Điểm BTC (U, D, Q) | Cận U, D tối đa theo đề bài |
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

Số liệu gốc: `experiments/data/tour_api_evidence/summary.json`. Mốc điểm đội 57: `experiments/data/tour_results/server_baseline.json`; không biết thuật toán hoặc ngân sách của đội đó.

Script `experiments/api/verify_tour_server.py` có reset và nộp Practice riêng đội 62, sao lưu lịch sử trước reset và đối chiếu replay. Không dùng script này như lệnh chỉ đọc. ID mẫu cần đặt tại máy trong `docs/api/sample_games.json`; token đọc từ `.env`. Các replay chi tiết bị Git ignore. Giảng viên có thể kiểm tra trực tiếp trên website bằng tài khoản trong báo cáo.
<!-- end:tour_server_results.md -->

<a id="kiem-chung"></a>

## 3. Hướng dẫn kiểm chứng và API đã sử dụng

Nguồn trước khi hợp nhất: `api_manual_check.md`.

<!-- begin:api_manual_check.md -->
> Phần này ghi nhận phạm vi và số liệu tại thời điểm thực nghiệm trước đây. Kết quả tour hiện tại được trình bày ở mục 2.

### Nguồn và phạm vi sử dụng

Nhóm đã sử dụng API chính thức tại https://hexudon.hairbui76.id.vn/ để đối chiếu simulator
ngày 19/10/2026. Tài liệu Swagger công khai nằm tại https://hexudon.hairbui76.id.vn/docs;
schema OpenAPI gốc nằm tại https://hexudon.hairbui76.id.vn/openapi.json.
Bản schema đã tải được lưu tại `docs/api/openapi.json` để tham khảo khi website thay đổi.

Danh sách câu hỏi quan sát trên giao diện Practice Match gồm Q01, Q02, Q03, Q04,
Q06, Q07, Q08, Q09 và Q10. Q05 không xuất hiện tại thời điểm kiểm tra, nên báo cáo
không mặc nhiên gọi đây là mười cấu hình đã kiểm chứng. Nhóm đã đọc cấu hình của chín câu,
đọc lịch sử Q01 và thực hiện các phép thử trên Q02, Q03, Q04, Q06 và Q10.
Q01 được giữ nguyên lịch sử của người dùng. Những câu còn lại ngoài năm câu thử chỉ được đọc cấu hình.

### Những endpoint đã dùng

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

### Cách đối chiếu khi không cần đăng nhập

Giảng viên có thể mở các tệp JSON trong `experiments/data/api_evidence`. Mỗi request có endpoint,
thời điểm, tham số, body và phản hồi. Header chứa token không được lưu trong những tệp này.
Giảng viên có thể đối chiếu body của bản ghi submit với plan trong bản ghi actions, sau đó
kiểm tra vị trí và nhiên liệu ở các frame của replay.

Script dưới đây chỉ đọc các bằng chứng đã lưu và chạy simulator tại máy, không gửi request mới:

```powershell
python -X utf8 experiments/api/compare_api.py --config experiments/data/api_evidence/q03_config.json --replay experiments/data/api_evidence/q03_replay.json --actions experiments/data/api_evidence/q03_actions.json --output results/q03_check.json
python -X utf8 -m unittest discover -s tests -v
```

Kết quả comparison ghi số frame, số giá trị đã so và những sai khác đầu tiên nếu có.
Các trường được đối chiếu gồm vị trí từng xe, nhiên liệu từng xe, số phần và số loại trong ngày,
danh sách sự kiện thu hàng, cùng trạng thái giao thông của ngày sau. Việc so điểm cuối trận
không được dùng thay thế cho so từng frame.

### Cách kiểm tra trực tiếp trên website

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

### Những kết luận chưa được phép rút ra

Replay khớp cho thấy hai hệ thống có cùng kết quả trên những phép thử đã thực hiện,
không phải chứng minh tương đương cho toàn bộ không gian trạng thái. Bộ bằng chứng hiện tại
chưa đối chiếu nhiều đội cùng chạy, kho ít hơn số xe tuần tra hoặc mọi trường hợp bơm nhiên liệu
khi xe đã cạn hoàn toàn. Các trường hợp đó được kiểm thử nội bộ hoặc ghi nhận để mở rộng.

Riêng giao thông, API có hành vi biên khi xe bắt đầu ngày trên đường: khoảng chuyển tiếp
rời vị trí đầu ngày không được tính như các frame hiển thị ô nguồn. Các biến thể Q10 được dùng
để tái hiện hiện tượng này. Simulator theo hành vi đã quan sát của máy chủ, đồng thời ghi rõ
đây là đặc điểm tương thích phiên bản đã kiểm tra, không suy diễn thành một điều luật mới của BTC.
<!-- end:api_manual_check.md -->

<a id="quy-tac"></a>

## 4. Quy tắc bài toán

Nguồn trước khi hợp nhất: `rules.md`.

<!-- begin:rules.md -->
### Nguồn

- `Đề bài/2026_Procon_Problem VI.pdf`: luật chính thức, 6 trang.
- `Đề bài/giao diện chọn loại agent đầu game.png`: giao diện chọn loại và vị trí ban đầu.
- `Đề bài/giao diện nộp bài.png`: cách nhập lệnh mỗi ngày.
- `Đề bài/input_sample.json`, `Đề bài/output_sample.txt`: mẫu dữ liệu.
- `Đề bài/Techinical_Presentation.pptx`: 3 slide hướng dẫn website và luồng API.
- API docs: https://hexudon.hairbui76.id.vn/docs (đã đọc ngày 18/10/2026).
- Schema được slide liên kết: https://drive.google.com/file/d/1Oc6RyIBX3oQa6RGeZ4MNDN4tKeOL6t1V/view
  (3 trang, tự ghi là bản dịch tiếng Anh không chính thức của tài liệu Nhật).

### Theo đề chính thức

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

### Bổ sung từ ảnh giao diện

- Mã loại xe: `0` = tuần tra, `1` = tiếp xăng.
- Vị trí xuất phát của từng xe được hiển thị trước khi chọn loại.
- Có thể gửi lại lựa chọn trong cửa sổ chọn loại.
- Nếu không chọn kịp, tất cả xe mặc định là tuần tra; vẫn được nộp kế hoạch mỗi ngày.
- Ảnh minh họa có 4 xe, lần lượt ở ô 558, 998, 130, 955.
  Đây là dữ liệu ví dụ, không phải cấu hình cố định.
- Mỗi xe có một mảng lệnh theo thứ tự xe: `0–5` là hướng đi, số âm là số bước chờ.
- Mỗi xe phải sử dụng đúng quỹ bước của ngày; ảnh nộp bài minh họa 228 bước.

### Bổ sung từ tài liệu kỹ thuật và API docs

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

### Bổ sung từ schema được BTC liên kết

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

### Các điểm cần làm rõ trước khi nối máy chủ

- Đối chiếu schema với phản hồi thực tế, đặc biệt trường `agents` và chỉ số `day`.
- Body riêng của API luyện tập và cơ chế xác thực khi tích hợp.
- Thứ tự chi tiết trong một step: trừ nhiên liệu, tiếp tế, đến ô và thu thập.
- Quy tắc khi nhiều xe cùng đến điểm có kho không đủ trong cùng step.
- Cách xử lý thu thập khi xe đã ở điểm đến ngay đầu ngày.

Mẫu JSON cục bộ hiện có không chứa `agents`, trong khi schema mô tả trường này.
Không tự gán các vị trí trong ảnh
cho mọi bản đồ. Những điểm chưa rõ sẽ được tách thành quy ước mô phỏng công khai,
không trình bày như luật đã được BTC xác nhận.


### Cập nhật sau khi đối chiếu API ngày 19 tháng 10 năm 2026

API config đã xác nhận trường agents và vị trí xuất phát. API day dùng chỉ số 0 cho ngày đầu,
trong khi giao diện người dùng đếm từ ngày 1. Replay đã xác minh nhiên liệu cập nhật khi đến,
tiếp tế sau khi đến (kể cả step cuối), thu hàng từ frame 1 khi đứng sẵn tại điểm và các trạng thái
đường. Phần chưa rõ ở các mục trước phản ánh tình trạng tài liệu ban đầu; kết luận mới và giới hạn
hiện tại phải đọc theo `simulation_conventions.md` và `api_manual_check.md`.
<!-- end:rules.md -->

<a id="mo-phong"></a>

## 5. Quy ước của bộ mô phỏng

Nguồn trước khi hợp nhất: `simulation_conventions.md`.

<!-- begin:simulation_conventions.md -->
### Cơ sở và ngày xác minh

Bản simulator này được điều chỉnh bằng replay từ API BTC ngày 19/10/2026.
Nguồn chính thức và cách kiểm tra thủ công nằm trong `api_manual_check.md`.
Kết quả theo từng bộ replay nằm trong `api_validation_results.md`.
Các mô tả dưới đây tách hành vi đã quan sát với trường hợp mới chỉ có kiểm thử nội bộ.

### Thứ tự trong một step

1. Xe đã kết thúc lệnh trước bắt đầu lệnh mới. Simulator kiểm tra đủ nhiên liệu để đi nhưng chưa trừ ngay.
2. Simulator giảm thời gian còn lại của lệnh. Khi lệnh đi hoàn thành, xe đến ô đích và bị trừ nhiên liệu theo ô nguồn.
3. Simulator tìm các xe tiếp tế cùng đội đang có cùng vị trí hiển thị và nạp đầy cho xe tuần tra.
4. Simulator đếm giao thông và thu udon theo các vị trí đã cập nhật, rồi ghi frame.

Frame 0 giữ nguyên trạng thái đầu ngày, chưa thu hàng và chưa nạp thêm nhiên liệu.
Xe đứng sẵn ở điểm có thể thu tại frame 1. Xe vừa đến ô tiếp tế đúng step cuối vẫn được nạp đầy.
Trong thời gian di chuyển chưa hoàn thành, replay giữ vị trí nguồn; xe vẫn có thể nhận tiếp tế
khi xe tiếp tế đến cùng vị trí hiển thị. Các trường hợp này có replay BTC đối chiếu.

Nếu xe hoàn toàn hết nhiên liệu ngay từ đầu ngày mà đang cùng ô xe tiếp tế, simulator yêu cầu
chờ một step trước khi khởi hành. Trường hợp này có kiểm thử nội bộ, chưa có bằng chứng API riêng.

### Giao thông và hành vi biên

Simulator cộng lịch sử hai ngày của mọi đội, chia số đội và áp dụng ngưỡng đông đúc/ùn tắc.
Giao thông cố định trong ngày. Hàm một đội dùng cùng engine, với mẫu số bằng 1.

Thông thường, simulator đếm theo vị trí hiển thị sau mỗi step. Tuy nhiên, API có hành vi biên:
khoảng chuyển tiếp rời vị trí đầu ngày trên đường không được đếm như khi xe đã đến một ô
trong ngày. Chờ tại vị trí đầu ngày vẫn được đếm. Sau lần hoàn thành di chuyển đầu tiên,
những khoảng chuyển tiếp sau được tính theo vị trí hiển thị.

Hai biến thể Q10 và ca Q02 xác minh khác biệt này. Biến `arrived_today` mô hình hóa hành vi
đã quan sát. Đây là một quy tắc tương thích máy chủ tại thời điểm thử, không phải điều luật
được tự bổ sung vào đề chính thức. Nếu BTC sửa engine, cần chạy lại đối chiếu trước khi cập nhật.

### Kho, thu thập và nhiều đội

Mỗi đội có kho riêng, bổ sung đầu ngày. Mỗi xe chỉ thu tối đa một phần tại mỗi điểm mỗi ngày.
Nếu kho không đủ khi nhiều xe cùng đến, simulator ưu tiên chỉ số xe nhỏ hơn.
Thứ tự ưu tiên này mới được kiểm thử nội bộ; các bản mẫu đã thử chưa tạo thiếu kho cùng lúc.

`simulate_match_day` dùng timeline chung, kho riêng và tiếp tế trong cùng đội.
Các phép thử về nhiều đội được tính tay, chưa được so với replay BTC nhiều đội.
Nếu một kế hoạch sai, hàm trả lỗi và không sửa bất kỳ trạng thái đầu vào nào. Đây là cơ chế
kiểm tra giao dịch của thư viện; lớp điều phối chịu trách nhiệm thay kế hoạch lỗi bằng chờ nếu cần.

### Mức độ tin cậy

Sáu tập đối chiếu có 6.331 frame và 97.345 giá trị được kiểm tra với 0 sai khác ở bản cuối.
Hai biến thể Q10 trùng ngày đầu nên không được xem mọi frame là mẫu độc lập.
Không được dùng kết quả này để khẳng định tương đương tuyệt đối trên tất cả cấu hình.

### Giới hạn của chiến lược

Xe tiếp tế chọn một điểm trung tâm theo tổng khoảng cách lục giác tới các điểm udon,
đi đến đó nếu kịp rồi đứng chờ. Xe tuần tra tìm đường tới trạm bằng nhiên liệu hiện có
và chờ ít nhất một step sau khi cả hai xe có mặt. Bộ lập kế hoạch chỉ tính nhiên liệu
được nhận tại các cuộc hẹn này; việc được tiếp thêm trên đường nếu có là phần dư an toàn.

Greedy và Lookahead cùng xét tối đa sáu điểm ứng viên theo ưu tiên loại mới và khoảng cách.
Lookahead nhìn thêm tối đa ba điểm kế tiếp cho từng ứng viên và chỉ thực hiện chặng đầu,
sau đó tính lại kế hoạch. Thuật toán đánh giá các điểm đích trong phép nhìn trước;
những điểm đi ngang được cập nhật khi tuyến được chọn, chưa được tính đầy đủ trong điểm dự đoán.

Việc giữ kho cho xe được thực hiện lần lượt theo chỉ số xe, không đặt chỗ theo thời điểm đến.
Nếu thứ tự thu thật khác dự kiến, simulator vẫn giới hạn đúng kho nhưng điểm dự đoán có thể lệch.
Nhiều xe tiếp tế hiện có thể chọn cùng một trạm, nên việc tăng số xe tiếp tế chưa chắc hữu ích.

Giới hạn thời gian trong bộ lập kế hoạch dừng phần tìm kiếm rồi vẫn chạy kiểm tra cuối.
Đây là ngân sách mềm, có thể vượt nhẹ do xử lý và kiểm tra. Khi thi cần chừa thời gian gửi mạng.
Kế hoạch dự phòng là mọi xe chờ hết ngày; chương trình kiểm tra lại trước khi ghi output.
<!-- end:simulation_conventions.md -->

<a id="thuat-toan"></a>

## 6. Phương pháp lập tuyến cho đội xe

Nguồn trước khi hợp nhất: `tour_planner.md`.

<!-- begin:tour_planner.md -->
Mã nguồn: `src/hexudon/tour.py`. Gọi qua `plan_day(..., strategy="tour")`, `play_match.py --algorithm tour`
hoặc `src/main.py ... --strategy tour`. Chỉ dùng thư viện chuẩn, không dùng RL.

### Mô hình một ngày

- Mỗi xe tuần tra có một dãy điểm udon. Chặng giữa hai điểm là đường ngắn nhất theo trọng số
  `a·step + b·nhiên liệu` với ba kiểu: nhanh, cân bằng, tiết kiệm. Cây đường đi được tính
  lười bằng Dijkstra trên giao thông thật của ngày, chi phí theo ô nguồn như simulator.
- Điểm udon nằm trên đường đi cũng được tính là đã ghé.
- Điểm ngày: `(loại mới toàn trận, số loại trong ngày, số suất, -nhiên liệu, -step)`, so theo
  thứ tự từ điển. Số suất tính đúng bằng `Σ min(kho, số xe ghé điểm)`, không phụ thuộc thứ tự.
- **Đội không có xe tiếp tế:** mỗi xe chỉ được tiêu
  `nhiên liệu × min(1, α × step hôm nay / step còn lại của trận)`; ngày cuối dùng hết. Mặc định α = 1.
- **Đội có xe tiếp tế:** mỗi xe tiếp tế chọn một điểm hẹn trong ngày (đứng yên, điểm trung tâm,
  điểm gần các xe tuần tra, hoặc chỗ xe tuần tra sắp cạn nhiên liệu), đi đường nhanh nhất tới
  đó rồi chờ. Xe tuần tra tự rẽ vào điểm hẹn khi nhiên liệu không đủ cho chặng tiếp theo cộng
  đường quay về, và cuối ngày phải còn đủ nhiên liệu để về điểm hẹn. Xe đứng yên luôn hợp lệ.

### Tìm kiếm

1. Với mỗi phương án điểm hẹn, dựng nhanh bằng chèn tham lam: ưu tiên điểm cho loại mới toàn
   trận, rồi loại mới trong ngày, rồi thêm suất; trong cùng lớp chọn chỗ chèn tăng chi phí ít
   nhất. Phương án đầu luôn được dựng trọn, kể cả khi ngân sách nhỏ.
2. Giữ phương án điểm hẹn tốt nhất, dùng phần thời gian còn lại cho phá và dựng lại: bỏ ngẫu
   nhiên vài điểm hoặc một đoạn tuyến, đôi khi đổi kiểu đường của một xe, chèn lại có nhiễu,
   nhận nếu điểm ngày không giảm.
3. Chuyển thành lệnh, kiểm tra bằng simulator. Nếu lỗi thì dùng Greedy cũ với thời gian còn lại
   thay vì đứng chờ cả ngày.

### Bảo vệ D ở ngày ngắn

Thiếu một loại trong một ngày là thua dù Q cao hơn nhiều (D xếp trên Q). Các lần mất D đều rơi
vào ngày ngắn (Q01 ngày 6: 69 step, Q03 ngày 5: 72 step, Q06 ngày 6: 62 step). Có hai cơ chế:

- **Phủ loại nhiều lần (`cover_types`)**: nếu phương án tốt nhất hôm nay còn thiếu loại, dựng lại
  nhiều lần chỉ nhắm loại, có nhiễu, trên mọi phương án điểm hẹn; khung phủ nhiều loại nhất được
  chèn thêm suất. Dùng tới 40% thời gian còn lại, dừng sớm khi đủ loại. Chạy lại đúng các ngày
  từng lỗi: trước đó 19/20 loại, sau đó 15/16 lượt đủ 20.
- **Ô neo cho ngày mai (`find_anchors`)**: sau 30% thời gian, ước lượng số loại ngày mai đi được từ
  vị trí và nhiên liệu cuối ngày (dựng chỉ nhắm loại, giao thông hôm nay làm dự báo). Nếu thiếu,
  leo đồi trên ô dừng cuối ngày của từng xe để ước lượng ngày mai cao nhất, rồi lập lại tuyến hôm
  nay buộc dừng ở ô neo. Chỉ nhận khi `(loại mới, loại hôm nay, loại ngày mai)` tốt hơn.

Đo trên 6 bài khó (Q01, Q03, Q04, Q06, Q09, Q10) với đội hình đã chọn: ở 1 giây/ngày còn 5/48
lượt mất D; ở 5 giây/ngày là 0/36. Khi thi nên để ngân sách mỗi ngày từ 5 giây trở lên
(mặc định runner là 20 giây). Ước lượng ngày mai còn bi quan vì chỉ dựng một lượt tham lam.

### Chọn vai trò

`select_types(..., strategy="tour")` mô phỏng các đội hình song song bằng nhiều tiến trình
(`select_types_parallel`), sàng lọc với ngân sách nhỏ rồi đánh giá lại tối đa bốn đội hình tốt
nhất. Nếu bản đồ quá lớn để chạy hết trận trong hạn, chọn theo số ngày đã mô phỏng rồi điểm.
`play_match.py --algorithm tour` mặc định dành 20 giây cho bước này.


### Kết quả đã kiểm chứng

Xem [bảng điểm BTC](#ket-qua). Giới hạn U và D đã đạt trên tám bài Practice; Q chưa được chứng minh tối ưu.
<!-- end:tour_planner.md -->

<a id="doi-chieu-api"></a>

## 7. Đối chiếu API trong giai đoạn xây dựng simulator

Nguồn trước khi hợp nhất: `api_validation_results.md`.

<!-- begin:api_validation_results.md -->
> Phần này ghi nhận phạm vi và số liệu tại thời điểm thực nghiệm trước đây. Kết quả tour hiện tại được trình bày ở mục 2.

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

### Điểm truy cập và bằng chứng

Tài liệu công khai: https://hexudon.hairbui76.id.vn/docs . Schema gốc: https://hexudon.hairbui76.id.vn/openapi.json .

Các JSON gốc nằm tại `experiments/data/api_evidence`; request không chứa header Authorization. Mỗi bản ghi có thời điểm UTC, endpoint, tham số, body, HTTP status và phản hồi. Danh mục SHA-256 nằm tại `manifest.json`. Hàm băm giúp nhận biết tệp thay đổi, không phải chữ ký xác nhận của BTC.

Các so sánh trên xác minh một đội trong những bản luyện tập đã thử. Phần nhiều đội mới có kiểm thử nội bộ, chưa có replay đối chiếu từ BTC. Kết quả không chứng minh simulator đúng trong mọi trường hợp và không phải chứng nhận của BTC.
<!-- end:api_validation_results.md -->

<a id="rl"></a>

## 8. Thí nghiệm huấn luyện học tăng cường

Nguồn trước khi hợp nhất: `rl_policy_training.md`.

<!-- begin:rl_policy_training.md -->
### Mục đích

Thí nghiệm này thay cách chọn ứng viên ở `rl_extension.py` bằng một chính sách PPO được huấn luyện từ đầu. Mỗi khi xe cần chọn đích mới, mạng chấm tất cả đích khả thi và hành động chờ. Khi đánh giá, hệ thống lấy hành động có xác suất lớn nhất. Hệ thống không so điểm với Greedy, không dùng Lookahead và không giữ kế hoạch Greedy dự phòng. Nếu kế hoạch không hợp lệ, phép đo dừng và báo lỗi, thay vì tự thay bài nộp.

Đây là **RL chọn mục tiêu kết hợp bộ tìm đường cố định**, không phải RL học từng hướng 0–5. Bộ thực thi dùng Dijkstra để xác định một đường ít step tới mỗi đích. Nó chỉ biến mục tiêu mạng chọn thành lệnh, cắt tiền tố liên tục khi hết quỹ ngày và thêm thời gian chờ còn thiếu. Mặt nạ loại đích nếu đường cố định vượt nhiên liệu còn lại. Nó có thể loại một đích mà một đường khác ít nhiên liệu hơn vẫn tới được; thí nghiệm không tuyên bố bộ thực thi đã xét mọi đường khả thi. Những hạn chế này được áp dụng như nhau cho tất cả đối chứng.

### Học và phân chia dữ liệu

- Mạng chia sẻ cho mọi xe: 18 đặc trưng cho mỗi ứng viên, hai tầng 64 nút Tanh, actor chấm từng ứng viên và critic lấy trung bình biểu diễn ứng viên hợp lệ.
- Hành động gồm tất cả điểm còn hàng, chưa được xe thăm trong ngày, có đường cố định phù hợp nhiên liệu, cùng một hành động chờ. Không cắt danh sách theo điểm Greedy.
- Huấn luyện từ khởi tạo ngẫu nhiên với ba seed 71, 72, 73. Không dùng checkpoint cũ, nhãn Greedy hoặc học bắt chước.
- Tập học có 48 bản đồ sinh trước, seed 61000–61047, kích thước 8, 12, 16 luân phiên; mỗi trận sáu ngày, 80 step/ngày, nhiên liệu 100, toàn xe tuần tra.
- Reward tại cuối ngày lấy từ **simulator TTUD thực thi cả đội**, bằng `10 ΔU + ΔD + 0,05 ΔQ`. Phép đặt chỗ tạm khi tạo tuyến không trực tiếp tạo reward. Tổng có trọng số này là mục tiêu học gần đúng, không tương đương thứ tự từ điển trong mọi trường hợp.
- PPO dùng learning rate 0,0003; gamma 0,99; GAE lambda 0,95; clip 0,2; bốn lượt cập nhật mỗi nhóm tám trận; minibatch 256; entropy 0,01; hệ số value loss 0,001; giới hạn norm gradient 0,5.
- Lưu checkpoint sau đúng số trận quy định. Không chọn checkpoint hoặc seed tốt nhất theo điểm chín bài BTC. Báo cáo đủ cả ba seed.
- Tập kiểm tra gồm các cấu hình BTC đã lưu và bản đồ sinh riêng có seed 91000 trở đi ở kích thước 8, 16, 32. Bản đồ kiểm tra 32×32 và bản đồ BTC khác phân phối kích thước/horizon của tập học. Q01/Q02 trùng cấu hình nên không được xem là hai mẫu độc lập.

### Đối chứng

Tất cả biến thể dùng cùng Dijkstra, mặt nạ, quy tắc đặt chỗ và mã mô phỏng:

1. `trained`: trọng số sau PPO, chọn argmax, không chọn theo điểm rollout.
2. `untrained`: cùng mạng tại thời điểm khởi tạo trước PPO, chọn argmax.
3. `random`: chọn đều trong các ứng viên hợp lệ và chờ, không dùng mạng.
4. `nearest`: luôn chọn đích gần nhất theo step trong bộ thực thi. Đây là một đối chứng riêng, không được gọi từ `trained`.
5. `trained_sampled` và `untrained_sampled`: lấy đúng một mẫu cho mỗi quyết định từ phân phối tương ứng sau/trước học, cùng seed đo. Không lấy nhiều kế hoạch rồi chọn điểm cao nhất. Hai biến thể này được bổ sung sau khi chẩn đoán argmax chọn chờ trên Q04 và bản đồ sinh 8×8 seed 91000; không thay đổi quá trình học hoặc chọn checkpoint theo điểm chẩn đoán. Đây là phân tích bổ sung sau quan sát, không phải giao thức hoàn toàn định trước.

Điểm số của cả bốn biến thể đều được tính bằng thực thi và chấm lại toàn bộ kế hoạch. Điều kiện `fallback_calls=0` có ý nghĩa đi cùng cấu trúc mã: đường thực thi không nhập hay gọi planner Greedy/Lookahead. Đối chứng mạng ban đầu giúp đo hiệu quả huấn luyện; đối chứng ngẫu nhiên và gần nhất giúp đánh giá chính sách trong cùng không gian hành động. Kết quả này không chứng minh mạng tự học tìm đường.

### Tái hiện

```text
python -X utf8 experiments/rl/train_rl_policy.py --episodes 1024 --seeds 71 72 73
python -X utf8 experiments/rl/evaluate_rl_policy.py
python -X utf8 -m unittest discover -s tests
```

PyTorch là phụ thuộc tùy chọn cho phần mở rộng, không phải yêu cầu của thuật toán lõi. CPU được đặt một luồng để giảm nhiễu. Không cần gửi dữ liệu hay thông tin đăng nhập Kaggle nếu phép đo tốc độ cho thấy CPU đủ phù hợp. Checkpoint và kế hoạch chi tiết chỉ lưu tại máy; metadata và bảng tổng hợp được giữ trong repository. Máy chủ BTC không được dùng trong vòng huấn luyện. Những điểm chưa nộp máy chủ phải được ghi rõ là điểm simulator offline.

Nguồn phương pháp PPO: Schulman và cộng sự (2017), *Proximal Policy Optimization Algorithms*, https://arxiv.org/abs/1707.06347. Simulator và bộ sinh bản đồ là mã của nhóm, không phải thư viện chấm chính thức của BTC.
<!-- end:rl_policy_training.md -->

<a id="doi-chung-cu"></a>

## 9. Đối chứng Greedy và Lookahead ở phiên bản trước

Nguồn trước khi hợp nhất: `legacy_branch_evaluation.md`.

<!-- begin:legacy_branch_evaluation.md -->
> Phần này ghi nhận phạm vi và số liệu tại thời điểm thực nghiệm trước đây. Kết quả tour hiện tại được trình bày ở mục 2.

Thí nghiệm sử dụng bản chụp `origin/Procon2026` tại commit `67e7873781d90e0809bc295a4422316e5abe5dc3`, không thay thế mã đang phát triển trên nhánh `ttud_clean`. Ngày thực hiện là 19/10/2026. Chương trình nộp trực tiếp vào các trận luyện tập riêng của đội 62 trên https://hexudon.hairbui76.id.vn/.

### Phạm vi thực sự đã chạy

Nhánh Procon2026 có mã MAPPO và cơ chế chuyển sang thuật toán dự phòng khi không có checkpoint. Tại thời điểm thí nghiệm, thư mục dự án và cây tệp của nhánh không có mô hình đã huấn luyện dạng `.pt`, `.pth` hoặc `.ckpt`. Vì vậy, thí nghiệm này đánh giá Greedy/Lookahead của nhánh và **không phải kết quả đánh giá chính sách RL đã huấn luyện**. Chúng ta chưa thể dùng các điểm này để kết luận RL tốt hơn hoặc kém hơn thuật toán truyền thống.

Client gốc sử dụng giao thức khác với API của website Việt Nam. Tệp `experiments/api/evaluate_legacy_branch.py` thực hiện chuyển đổi cấu trúc input, mã địa hình, chỉ số ngày và định dạng output; các lớp GreedyPlanner, LookaheadPlanner, tìm đường, validator và simulator dùng để so sánh ứng viên vẫn được nhập trực tiếp từ bản chụp nhánh. Mỗi ngày, adapter lấy vị trí, nhiên liệu, giao thông và lịch sử thu thập thực tế từ máy chủ, thay vì để sai khác mô phỏng tích lũy qua nhiều ngày.

Chương trình chọn toàn bộ xe tuần tra, đúng cách chọn mặc định trong `run_play` của nhánh gốc. Chương trình tạo phương án Greedy, dùng Lookahead để tìm ứng viên và chỉ thay thế nếu bộ chấm nội bộ của nhánh đánh giá ứng viên tốt hơn. Adapter chỉ nộp phương án cuối cùng một lần mỗi ngày; nó không thực hiện bước nộp Greedy tạm thời rồi nộp cải thiện như client gốc. Vì vậy, đây là đánh giá thuật toán qua adapter tương thích, không phải phép chạy nguyên trạng client mạng của nhánh.

Thí nghiệm dùng ngân sách lập kế hoạch danh nghĩa 30 giây mỗi ngày trong chế độ luyện tập. Chế độ luyện tập không chứng minh được khả năng đáp ứng hạn nộp trong trận thi thật. Thời gian lập kế hoạch trong nhật ký không bao gồm truyền mạng và tải replay. Chương trình không sửa đường đi nếu máy chủ từ chối, mà dừng bài đó và ghi lỗi.

### Nguồn điểm và bằng chứng

Điểm chính thức được đọc từ `GET /api/game/result`, với ba trường `distinct_types`, `cumulative_daily_types` và `total_servings`. Chúng lần lượt là số loại udon khác nhau của toàn trận, tổng số loại thu thập được theo từng ngày và tổng số suất udon. Ba chỉ tiêu được so sánh theo thứ tự ưu tiên, không cộng thành một điểm tổng tùy ý.

Adapter lưu bản sao config, actions, replay và state cũ trước khi đặt lại trận luyện tập. Thư mục `experiments/data/legacy_branch_evidence` chứa các phản hồi API trước/sau, kế hoạch từng ngày, nhật ký và bảng tổng hợp `summary.json`. Các tệp `Qxx_output.txt` có mỗi dòng là mảng lệnh của một ngày, theo thứ tự từ ngày 1; mỗi ngày chứa một mảng cho từng xe. Khi nộp qua API, chương trình gửi từng dòng kèm trường ngày tương ứng, không gửi cả mười dòng trong một yêu cầu.

Website hiện hiển thị Q01, Q02, Q03, Q04, Q06, Q07, Q08, Q09 và Q10 ở danh sách Practice Match. Q05 không có trong danh sách quan sát được nên không có output hoặc điểm cho bài này. Config Q01 và Q02 giống hệt nhau ở mọi trường trả về; hai nhãn này không tạo thành hai trường hợp đầu vào độc lập.

### Tài liệu để kiểm tra thủ công

- Danh sách bài luyện tập: https://hexudon.hairbui76.id.vn/tournament/1/round/1/match/11/questions
- Tài liệu API BTC: https://hexudon.hairbui76.id.vn/docs
- Đặc tả OpenAPI: https://hexudon.hairbui76.id.vn/openapi.json
- Các endpoint được dùng: `/api/game/config`, `/api/game/day`, `/api/game/agent-types`, `/api/game/practice/reset`, `/api/game/practice/actions`, `/api/game/actions`, `/api/game/replay`, `/api/game/state` và `/api/game/result`.

Giảng viên có thể dùng tài khoản có quyền truy cập để mở từng bài luyện tập hoặc kiểm tra các phản hồi JSON đã lưu. Thông tin xác thực không được đưa vào các tệp bằng chứng hoặc báo cáo.

### Kết quả máy chủ

| Bài | Loại toàn trận | Tổng loại theo ngày | Tổng suất |
|---|---:|---:|---:|
| Q01 | 20 | 92 | 245 |
| Q02 | 20 | 92 | 245 |
| Q03 | 20 | 67 | 132 |
| Q04 | 20 | 70 | 145 |
| Q05 | Không có trong danh sách | — | — |
| Q06 | 15 | 75 | 189 |
| Q07 | 15 | 71 | 344 |
| Q08 | 15 | 101 | 308 |
| Q09 | 15 | 85 | 201 |
| Q10 | 15 | 92 | 266 |

Máy chủ đã nhận và lưu đúng 90 kế hoạch ngày. Thời gian lập kế hoạch lớn nhất: 0.281 giây, không gồm truyền mạng.
<!-- end:legacy_branch_evaluation.md -->

<a id="rl-cu"></a>

## 10. Đối chứng RL kết hợp heuristic ở phiên bản trước

Nguồn trước khi hợp nhất: `rl_branch_evaluation.md`.

<!-- begin:rl_branch_evaluation.md -->
> Phần này ghi nhận phạm vi và số liệu tại thời điểm thực nghiệm trước đây. Kết quả tour hiện tại được trình bày ở mục 2.

Thí nghiệm này được thực hiện sau khi lấy bản mới nhất của nhánh `Procon2026` từ GitHub vào ngày 19/10/2026. Bản được đánh giá là commit `b6df084c253503b5673721c126ff261430cd0021`. Checkpoint được lấy cùng nhánh có đường dẫn `runs/pilot_reserved_001/seed_20042/episode_256.pt`. Mã nhánh `ttud_clean` và bằng chứng của lượt Greedy/Lookahead trước đó được giữ lại.

### Phương pháp

Chương trình nạp checkpoint bằng phương thức `MAPPOTrainer.load` của nhánh, chuyển mô hình sang chế độ đánh giá và chọn hành động xác định. RL chọn điểm đích cho từng xe tuần tra, còn A* và bộ tạo đường đi của nhánh chuyển lựa chọn đó thành lệnh di chuyển. Các tùy chọn masking, tuyến phụ và giữ chỗ tồn kho được lấy từ chính checkpoint, không tự bật hoặc tắt để cải thiện điểm. Tệp `model_metadata.json` lưu cấu hình được nạp, số episode và mã SHA-256 của checkpoint.

Thí nghiệm giữ cơ chế lựa chọn ứng viên trong `run_play` của nhánh: Greedy tạo phương án cơ sở, sau đó phương án RL chỉ được chọn khi hợp lệ và có bộ điểm dự đoán tốt hơn theo simulator của nhánh. Vì vậy, kết quả phải được gọi là **RL kết hợp Greedy và bộ chọn theo điểm dự đoán**, không phải điểm RL thuần. Nhật ký lưu cả đích do RL chọn, ứng viên RL và phương pháp thực sự được nộp trong từng ngày. Nếu RL không được chọn trong một ngày thì điểm ngày đó không được quy hoàn toàn cho RL.

Adapter `experiments/api/evaluate_legacy_branch.py --rl` chuyển cấu trúc API Việt Nam sang cấu trúc dữ liệu của nhánh. Adapter lấy vị trí, nhiên liệu, giao thông và lịch sử thu thập từ máy chủ vào mỗi ngày. Các thuật toán của nhánh được nhập trực tiếp từ bản chụp tại commit nói trên. Adapter nộp một phương án cuối cùng cho mỗi ngày, thay vì nộp Greedy tạm thời rồi nộp cải thiện như client mạng gốc. Toàn bộ xe được chọn là xe tuần tra theo mặc định của `run_play`; thí nghiệm không tối ưu lại cách chọn loại xe.

Mỗi ngày có ngân sách lập kế hoạch danh nghĩa 30 giây. Thời gian tính toán được lưu riêng và không bao gồm truyền mạng hoặc tải replay. Chế độ luyện tập không xác nhận khả năng đáp ứng hạn nộp trong trận thi thật. Nếu xảy ra lỗi RL, adapter ghi lỗi và dừng bài tương ứng, không âm thầm báo điểm fallback là điểm RL.

### Nguồn kết quả và kiểm chứng

Chương trình nộp vào trận luyện tập riêng của đội 62 qua API BTC. Điểm được đọc trực tiếp từ `/api/game/result`, gồm số loại udon toàn trận, tổng số loại theo ngày và tổng số suất. Thứ tự ưu tiên này được giữ nguyên khi so sánh; chúng ta không cộng ba thành phần thành một điểm tùy ý. Thư mục `experiments/data/rl_branch_evidence` lưu config, kế hoạch trước/sau, phản hồi nộp bài, replay, trạng thái cuối và kết quả máy chủ. Thí nghiệm không lấy điểm mô phỏng nội bộ làm kết quả chính thức.

Website hiện hiển thị chín bài Q01, Q02, Q03, Q04, Q06, Q07, Q08, Q09 và Q10; Q05 không có trong danh sách quan sát được. Q01 và Q02 có config giống hệt nhau, do đó chúng không đại diện cho hai input độc lập. Mỗi tệp `Qxx_output.txt` gồm mười dòng tương ứng mười ngày. API nhận từng ngày riêng kèm chỉ số ngày; tệp này là bản lưu toàn trận, không phải một yêu cầu nộp duy nhất.

Giảng viên có thể kiểm tra các phản hồi JSON đã lưu hoặc truy cập các nguồn của BTC bằng tài khoản có quyền:

- Danh sách Practice Match: https://hexudon.hairbui76.id.vn/tournament/1/round/1/match/11/questions
- Tài liệu API: https://hexudon.hairbui76.id.vn/docs
- Đặc tả API: https://hexudon.hairbui76.id.vn/openapi.json

Các API được sử dụng gồm `/api/game/config`, `/api/game/day`, `/api/game/agent-types`, `/api/game/practice/reset`, `/api/game/practice/actions`, `/api/game/actions`, `/api/game/replay`, `/api/game/state` và `/api/game/result`. Bằng chứng không chứa token xác thực.

### Kết quả máy chủ

| Bài | Loại toàn trận | Tổng loại theo ngày | Tổng suất |
|---|---:|---:|---:|
| Q01 | 20 | 57 | 167 |
| Q02 | 20 | 57 | 167 |
| Q03 | 19 | 59 | 121 |
| Q04 | 15 | 42 | 96 |
| Q05 | Không có trong danh sách | — | — |
| Q06 | 15 | 55 | 143 |
| Q07 | 15 | 61 | 236 |
| Q08 | 15 | 61 | 215 |
| Q09 | 14 | 47 | 129 |
| Q10 | 15 | 64 | 192 |

Máy chủ đã nhận và lưu đúng 90 kế hoạch ngày. Thời gian lập kế hoạch lớn nhất: 2.250 giây, không gồm truyền mạng.

### So sánh với lượt Greedy/Lookahead trước đó

| Bài | Greedy/Lookahead | RL kết hợp Greedy | So sánh |
|---|---|---|---|
| Q01 | (20, 92, 245) | (20, 57, 167) | Kém hơn |
| Q02 | (20, 92, 245) | (20, 57, 167) | Kém hơn |
| Q03 | (20, 67, 132) | (19, 59, 121) | Kém hơn |
| Q04 | (20, 70, 145) | (15, 42, 96) | Kém hơn |
| Q06 | (15, 75, 189) | (15, 55, 143) | Kém hơn |
| Q07 | (15, 71, 344) | (15, 61, 236) | Kém hơn |
| Q08 | (15, 101, 308) | (15, 61, 215) | Kém hơn |
| Q09 | (15, 85, 201) | (14, 47, 129) | Kém hơn |
| Q10 | (15, 92, 266) | (15, 64, 192) | Kém hơn |

Trong 90 ngày, mô hình đã tạo 90 ứng viên; bộ chọn đã dùng RL cho 43 ngày. Các ngày còn lại dùng Greedy.

Theo thứ tự ưu tiên ba thành phần điểm, lượt RL kết hợp Greedy tốt hơn ở 0 bài, kém hơn ở 9 bài và bằng nhau ở 0 bài. Thống kê này bao gồm hai nhãn Q01/Q02 có input trùng nhau. Đây là so sánh hai cấu hình hoàn chỉnh, không tách riêng tác động của chính sách RL và các heuristic hỗ trợ.
<!-- end:rl_branch_evaluation.md -->


<a id="thuc-nghiem-tour"></a>

## 11. Đối chứng có kiểm soát cho phương pháp tour

Bộ đo bổ sung gồm 135 lượt và 1.062 kế hoạch ngày: tám bản đồ Practice khác nhau, ba bản đồ sinh 8×8/16×16/32×32, ba lượt lặp. Hai planner dùng cùng đội hình và ngân sách yêu cầu 1 giây/ngày. Phép tách thành phần chạy trên sáu input; phép tăng ngân sách dùng 3 giây/ngày trên ba input. Đây là số liệu offline, không ghi đè các lượt Practice trên website. Các ngưỡng thời gian là giới hạn mềm, không phải cam kết đáp ứng deadline cứng.

```powershell
# Chấm lại toàn bộ hành trình đã lưu, không gọi API
python -X utf8 experiments/run.py tour_study --audit-only
# Tính lại các bảng tổng hợp từ kết quả đã lưu
python -X utf8 experiments/run.py summarize_tour_study
# Chạy bộ đo; các lượt đã có được bỏ qua
python -X utf8 experiments/run.py tour_study --workers 3
```

Dữ liệu nằm trong `experiments/data/tour_study/`: `inputs/` giữ 11 cấu hình, `manifest.json` giữ đội hình, seed và dấu kiểm tra mã nguồn; `results.json` chứa mọi chuỗi lệnh và trạng thái cuối ngày; `summary.json`, `audit.json` và `machine.json` chứa thống kê và điều kiện đo. Có thể chuyển `results.json` sang một tên dự phòng trước khi chạy để đo lại từ đầu; thời hạn thực và tải máy có thể làm kết quả khác lần đã lưu. Việc chạy lại dùng kết quả mới, không bảo đảm lặp đúng từng chữ số. Bộ kiểm tra không cần checkpoint RL hoặc token.

Các biến thể chỉ thay đổi một thành phần: bỏ hàm cải thiện tuyến, bỏ lượt dựng lại để phủ loại hôm nay, hoặc bỏ tìm điểm neo. Những thành phần còn lại, simulator và luật chấm được giữ nguyên. Có thêm đối chứng 2×2 trên Q01 để phân biệt tác động của planner với việc đổi đội hình.


<a id="do-ben-vung"></a>

## 12. Đánh giá trên 30 bản đồ tự sinh

Bộ dữ liệu `experiments/data/tour_robustness/` gồm 10 bản đồ ở mỗi cỡ 8×8, 16×16 và 32×32. Các input thay đổi seed, nhiên liệu và quỹ step; đội hình luôn là một xe tiếp tế và ba xe tuần tra. Mỗi phương án chạy ba lượt. Phép đo mới sử dụng phiên bản có kiểm tra thời gian trong vòng chèn và dự báo ngày sau; nó được tách khỏi số liệu trước lần bổ sung này.

```powershell
# Phát lại đúng các output được báo cáo, không cần token
python -X utf8 experiments/run.py tour_robustness --audit-only
# Chạy bộ đo; các lượt đã lưu được dùng lại
python -X utf8 experiments/run.py tour_robustness --workers 4
```

Muốn tính lại từ đầu, chuyển `experiments/data/tour_robustness/results.json` và thư mục `results/tour_robustness_runs/` (nếu có) sang chỗ dự phòng trước khi chạy. Có 180 lượt Greedy/tour cùng đội hình ở ngân sách yêu cầu 1 giây/ngày; phép tách thành phần trên sáu bản đồ ở 1 và 5 giây dùng thêm 126 lượt, tổng cộng 306 lượt và 1.224 kế hoạch ngày. Ba lượt Greedy là đo lặp, vì Greedy không sử dụng seed. Giao thông chỉ được cập nhật từ đội đang mô phỏng.

`summary.json` giữ thống kê theo kích thước, theo input, các cặp thắng/hòa/thua và thời gian thực tế; `results.json` giữ output và trạng thái từng ngày. `manifest.json` giữ input cùng dấu kiểm tra mã, còn `audit.json` ghi kết quả phát lại. Kiểm tra thời gian làm giảm bước xử lý không bị ngắt, nhưng không phải bảo đảm deadline cứng cho mọi máy hoặc mạng.

Ở cả hai bộ đo, `--audit-only` kiểm tra dấu của model và simulator rồi phát lại output; nó không cần planner hiện tại giống phiên bản đã tạo output. Việc tính lại từ đầu kiểm tra toàn bộ mã lõi. Bộ `tour_study` ban đầu vì vậy vẫn chấm lại được sau khi cải tiến kiểm soát thời gian, nhưng không trộn số liệu mới vào kết quả cũ.
