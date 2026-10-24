# HEXUDON – Procon Vietnam 2026

Chương trình thi tự động cho bài HEXUDON: tự chọn vai trò xe, lập tuyến từng ngày và nộp bài qua
API của BTC (`https://hexudon.hairbui76.id.vn`). Phần tính toán nặng (lập tuyến, chọn đội hình, chấm
kế hoạch) chạy bằng C++ nhiều luồng; Python lo gọi API, giữ thời gian, kiểm tra kế hoạch lần cuối
bằng simulator và dự phòng khi C++ lỗi.

- Hướng dẫn ngắn cho người chạy máy ngày thi: [docs/contest_day.md](docs/contest_day.md)
- Luật và cách tính điểm: [docs/rules.md](docs/rules.md)
- Lộ trình và toàn bộ kết quả đo: [docs/roadmap.md](docs/roadmap.md)

---

## 1. Cài đặt (làm một lần trên máy thi)

### 1.1. Python

Cần Python 3.10 trở lên. Chương trình thi chỉ dùng thư viện chuẩn, không cần `pip install`.

```powershell
python --version
```

### 1.2. Trình biên dịch C++ (g++)

Planner C++ cần `g++` hỗ trợ C++20. Trên Windows dùng MSYS2:

1. Cài MSYS2 từ https://www.msys2.org (mặc định vào `C:\msys64`).
2. Mở **MSYS2 UCRT64** và chạy: `pacman -S mingw-w64-ucrt-x86_64-gcc`
3. Kiểm tra: `C:\msys64\ucrt64\bin\g++.exe --version`

Không cần thêm vào `PATH`: chương trình tự tìm `g++` trong `PATH` hoặc ở `C:\msys64\ucrt64\bin`.
Lần chạy đầu (hoặc khi `native/hexplan.cpp` mới hơn file chạy), runner tự biên dịch ra
`native/hexplan.exe` (khoảng 10–20 giây). Muốn biên dịch trước:

```powershell
python -X utf8 -c "import sys; sys.path.insert(0, 'src'); from hexudon import native; print(native.build(force=True))"
```

In ra `True` là được. Nếu không có `g++`, runner vẫn chạy bằng planner Python (yếu hơn) và in
`CẢNH BÁO: ... bản C++ không dùng được`.

### 1.3. Token đội

Tạo file `.env` ở thư mục gốc dự án (file này không đưa lên git), chỉ một dòng:

```text
HEXUDON_TOKEN=<token lấy trên website BTC>
```

Token có hạn **48 giờ**. Trước mỗi trận lấy token mới và thay dòng này. Runner tự đọc ID đội từ token.

### 1.4. Kiểm tra cài đặt

```powershell
python -X utf8 -m unittest discover -s tests
```

Phải kết thúc bằng `OK`. (Test đối chiếu máy chủ cần dữ liệu API thô trong
`experiments/data/api_evidence`; thiếu thư mục này thì các test đó báo lỗi thiếu file, không ảnh
hưởng việc thi.)

---

## 2. Chạy trận thi (trận tính giờ)

Mọi lệnh chạy từ **thư mục gốc dự án**, trong PowerShell.

### Bước 1 – Chuẩn bị máy (trước giờ chọn vai trò ít nhất 30 phút)

- Cắm sạc, tắt chế độ ngủ và tắt màn hình tự động, hoãn Windows Update.
- Đóng mọi chương trình nặng (trình duyệt nhiều tab, IDE đang chạy test, đồng bộ đám mây). Chạy việc
  khác trong trận làm giảm điểm rõ rệt vì planner dùng gần hết CPU.
- Thay token mới vào `.env` (mục 1.3).

### Bước 2 – Kiểm tra trước trận (không nộp bài)

Khi đã có **ID trận** (lấy trên website BTC):

```powershell
python play.py ID_TRAN --preflight
```

Lệnh này chỉ gửi GET: kiểm tra hạn token, độ trễ mạng, đội mình có trong trận, đọc config, số nhân
CPU, planner C++ đã sẵn sàng, ghi được thư mục checkpoint và thử lập kế hoạch ngày 1. Phải thấy dòng
cuối `Kết quả: sẵn sàng.` Mỗi dòng `CẢNH BÁO` cần xử lý trước khi chạy thật.

### Bước 3 – Chạy trận

```powershell
python play.py ID_TRAN
```

Chỉ vậy là đủ: runner tự nhận trận tính giờ hay Practice, planner `tour` (C++), số luồng = số nhân
CPU − 2 (tối đa 14), không cần `-X utf8`. Runner sẽ:

1. **Chọn vai trò** trong `agent_selection_time_limit − 4` giây: mô phỏng cả trận cho tối đa 16 đội
   hình bằng C++ nhiều luồng, loại dần đội hình kém, rồi nộp đội hình tốt nhất.
2. **Mỗi ngày** (ngân sách `daySeconds − 4` giây):
   - đọc trạng thái và mặt đường BTC công bố cho ngày đó;
   - **nộp nhanh** một kế hoạch sau khoảng 1–3 giây (giảm thời gian phản hồi, tiêu chí 4);
   - tiếp tục tối ưu, **chỉ nộp lại khi bài mới tốt hơn** theo (U, D hôm nay, số loại đi được ngày
     mai, Q): kiểm tra mỗi 2 giây, các lần nộp lại cách nhau ít nhất 5 giây, tối đa 5 lần nộp/ngày;
     máy chủ giữ bài hợp lệ cuối cùng;
   - bài đã đạt cận trên của ngày thì dừng sớm.
3. Mọi kế hoạch đều qua simulator Python trước khi nộp; planner lỗi thì tự dùng phương án dự phòng
   (planner Python, rồi Greedy), không bỏ trống ngày nào.

Màn hình in trạng thái từng ngày, ví dụ `Ngày 3: máy chủ đã nhận kế hoạch (timed).`,
`đã nộp lại bài tốt hơn ...`, `giữ bài đã nộp`.

### Bước 4 – Khi có sự cố

| Tình huống | Làm gì |
|---|---|
| Runner dừng, mất mạng, lỡ tay Ctrl+C, máy treo | **Chạy lại đúng lệnh cũ.** Runner đọc checkpoint, không nộp trùng, tiếp tục ngày hiện tại nếu còn giờ. Bài đã nộp trước đó vẫn được máy chủ giữ. |
| Báo token hết hạn | Lấy token mới vào `.env`, chạy lại đúng lệnh cũ. |
| Báo `Trận đã lùi ngày hoặc được reset` | BTC đã reset trận: chạy lại với `--run-dir results/live/ten_moi`. |
| `CẢNH BÁO: ... bản C++ không dùng được` | Runner đã tự chạy bản Python; vẫn thi tiếp được. Sau trận kiểm tra `g++`/`native/`. |
| `Planner lỗi ...; dùng Greedy` | Runner đã tự dùng dự phòng; để chạy tiếp, lưu log để kiểm tra sau. |
| Máy quá chậm, nhiều ngày dự phòng | Chạy lại với `--workers 8`. |

**Không làm:** không reset trận, không nộp tay song song với runner, không chạy hai runner cho cùng
đội/trận (có khóa tệp chặn việc này), không giảm `--reserve` hay `--seconds` dưới mặc định.

### Sau trận

Thư mục `results/live/<ID>_<đội>/` chứa config, trạng thái từng ngày, lệnh đã nộp và checkpoint;
runner tự dọn khi đọc được kết quả cuối trận. Muốn giữ log, chạy với `--run-dir` riêng.

---

## 3. Chạy Practice (luyện tập trên website BTC)

ID Practice lấy trên website (dạng mã game hoặc `ID_CAU_HOI:ID_DOI`). Practice không tính giờ; runner
tự nhận chế độ practice. Nếu runner báo đang chờ máy chủ chuyển ngày mà không tiến, chạy lại kèm
`--mode practice`.

```powershell
python play.py ID_CAU_HOI:62
```

Practice chỉ giữ một lượt; muốn chạy lại phải **reset trên website** (điểm cũ trên bảng xếp hạng sẽ
bị thay bằng lượt mới), rồi chạy với `--run-dir` mới.

---

## 4. Tham số của `play.py`

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `ID_TRAN` hoặc `--game-id` | hỏi khi chạy | ID trận, hoặc `câu_hỏi:đội` cho Practice |
| `--mode` | `auto` | Tự nhận theo máy chủ (trận có đồng hồ ngày là `timed`, Practice là `practice`); ép bằng `timed` hoặc `practice` nếu runner báo không phân biệt được |
| `--algorithm` | `tour` | `tour` (khuyên dùng), `greedy` (dự phòng đơn giản) |
| `--workers` | số nhân − 2, tối đa 14 | Số luồng C++ (hoặc tiến trình Python) lập tuyến song song |
| `--seconds` | `daySeconds − reserve` | Trần thời gian lập tuyến mỗi ngày |
| `--reserve` | 4 | Giây chừa mỗi ngày để đọc trạng thái, kiểm tra và nộp |
| `--selection-seconds` | `agent_selection_time_limit − reserve` | Thời gian chọn vai trò |
| `--roles` / `--types` | `auto` | Ép vai trò: `all-patrol`, `last-supply`, hoặc `--types 0 1 0 0` (0 tuần tra, 1 tiếp tế) |
| `--no-resubmit` | tắt | Không nộp nhanh rồi nộp lại, chỉ nộp một lần mỗi ngày |
| `--no-native` | tắt | Không dùng C++, chạy planner Python |
| `--parallel-objective` | `lookahead` | Cách chọn kế hoạch: `lookahead` (xét số loại ngày mai trước Q) hoặc `score` |
| `--seed` | 0 | Seed đầu; luồng thứ i dùng seed + i |
| `--preflight` | | Kiểm tra trước trận, không nộp |
| `--inspect` | | Chỉ đọc config/trạng thái |
| `--dry-run` | | Lập kế hoạch nhưng không nộp |
| `--run-dir` | `results/live/<ID>_<đội>` | Thư mục checkpoint (đổi khi trận bị reset) |
| `--env` | `.env` | File chứa token |

---

## 5. Cấu trúc mã nguồn

```text
play.py                        Điểm vào khi thi
native/hexplan.cpp             Lõi C++: planner tour nhiều luồng (chèn điểm, phá và dựng lại có nhiệt
                               độ, phủ loại, hộ tống tiếp tế, ô neo cuối ngày), simulator một ngày,
                               chấm kế hoạch, chọn đội hình bằng mô phỏng cả trận
src/hexudon/native.py          Biên dịch và gọi lõi C++, đọc kết quả, đếm và cảnh báo khi phải dùng Python
src/hexudon/live.py            Runner: đọc trạng thái, chọn vai trò, nộp nhanh rồi nộp lại khi tốt hơn
src/hexudon/live_api.py        Gọi API BTC          src/hexudon/live_storage.py   Checkpoint, khóa tệp
src/hexudon/tour.py            Planner tour bản Python (dự phòng) và phiên tìm kiếm song song
src/hexudon/team_selection.py  Chọn vai trò (gọi C++; bản Python làm dự phòng)
src/hexudon/simulator.py       Simulator kiểm tra mọi kế hoạch trước khi nộp (độc lập với C++)
src/hexudon/planner.py, search.py   Gọi planner, Greedy dự phòng
src/hexudon/model.py           Mô hình bản đồ lục giác, xe, trạng thái
src/hexudon/generator.py       Sinh bản đồ thử
tests/                         Kiểm thử
experiments/                   Công cụ đo và tập dượt (mục 6)
```

---

## 6. Đo và tập dượt (không cần cho ngày thi)

| Lệnh | Việc |
|---|---|
| `python -X utf8 experiments/rehearse_timed.py --case Q01 --day-seconds 12 --latency 0.3 --errors 0.05` | Tập dượt trận tính giờ với máy chủ giả offline (config trong `output/team_selection/<case>/config.json`), có độ trễ và lỗi mạng |
| `python -X utf8 experiments/practice_offline.py` | Chạy toàn bộ đề Practice offline với thời gian thật, ghi `results/practice_offline/` |
| `python -X utf8 experiments/suite.py --split dev --variants base python --seconds 1 --threads 4 --workers 3` | So các cấu hình planner trên 200 bản đồ (dev) hoặc 100 bản đồ (test) |
| `python -X utf8 experiments/budget_check.py --variants base python --seconds 10` | So cấu hình ở ngân sách giống ngày thi trên đề BTC |
| `python -X utf8 experiments/selection_compare.py` | So bộ chọn đội hình C++ với bộ chọn cũ |
| `python -X utf8 experiments/ilp_day.py` / `ilp_small.py` | CP-SAT một ngày (cần `pip install ortools`) |
| `python -X utf8 experiments/compare_api.py ...` | Đối chiếu simulator với replay BTC |

Kết quả đo hiện tại (tóm tắt, chi tiết trong [docs/roadmap.md](docs/roadmap.md)): C++ nhanh hơn
Python 16–24 lần, cùng 1 giây/ngày tăng Q 4% trên bản đồ kiểu BTC; nhiệt độ (simulated annealing)
thêm khoảng 0,9% Q; trên bản đồ 8×8 planner đạt đúng tối ưu từng ngày (CP-SAT chứng minh 40/40 ngày).
