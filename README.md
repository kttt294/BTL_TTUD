# HEXUDON – Procon Vietnam 2026

Chương trình thi tự động: chọn vai trò xe, lập tuyến từng ngày và nộp bài qua API của BTC.
Hướng dẫn vận hành ngày thi: [docs/contest_day.md](docs/contest_day.md). Luật: [docs/rules.md](docs/rules.md).
Lộ trình và kết quả đo: [docs/roadmap.md](docs/roadmap.md).

## Chạy trận

```powershell
python -X utf8 play_match.py --preflight --game-id ID_TRAN --algorithm tour   # kiểm tra, không nộp
python -X utf8 play_match.py --algorithm tour --mode timed ID_TRAN
```

Token đội đặt trong `.env` (`HEXUDON_TOKEN=...`), không đưa lên git.

## Cấu trúc

```text
play_match.py              Điểm vào khi thi
src/hexudon/live.py        Runner: đọc trạng thái, chọn vai trò, nộp nhanh rồi nộp lại khi tốt hơn
src/hexudon/live_api.py    Gọi API BTC        src/hexudon/live_storage.py  Checkpoint, khóa tệp
src/hexudon/tour.py        Planner tour (Python) và phiên tìm kiếm song song
src/hexudon/native.py      Gọi planner tour bản C++ (native/hexplan.cpp), tự biên dịch bằng g++
src/hexudon/team_selection.py  Chọn vai trò bằng mô phỏng
src/hexudon/simulator.py   Simulator kiểm tra mọi kế hoạch trước khi nộp
src/hexudon/planner.py, search.py  Gọi planner, Greedy dự phòng
src/hexudon/model.py, generator.py Mô hình bản đồ, sinh bản đồ thử
experiments/suite.py       Bộ đo 300 bản đồ (dev 200, test 100) so các biến thể
experiments/rehearse_timed.py  Tập dượt trận tính giờ với máy chủ giả
experiments/ilp_day.py     CP-SAT cho bài toán một ngày (cận trên, so với tour)
experiments/compare_api.py Đối chiếu simulator với replay BTC (dùng trong test)
tests/                     Kiểm thử
```

## Kiểm thử

```powershell
python -X utf8 -m unittest discover -s tests
```

Test đối chiếu máy chủ cần dữ liệu API thô trong `experiments/data/api_evidence` (không đưa lên git).
