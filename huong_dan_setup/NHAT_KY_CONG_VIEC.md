# Nhật ký công việc tối ưu HEXUDON (23/10 - 28/10/2026)

Tài liệu này dành cho người nhận tiếp dự án. Nó ghi lại toàn bộ những gì đã làm trong đợt tối ưu từ tối 23/10 đến chiều 28/10/2026:

- công cụ mới và cách dùng;
- thay đổi trong mã nguồn;
- các thí nghiệm, kể cả thí nghiệm thất bại;
- sự cố đã gặp;
- trạng thái hiện tại và việc còn dở.

Cách cài đặt và chạy cơ bản nằm ở [README.md](README.md) trong cùng thư mục. Tài liệu này không lặp lại phần đó.

Mọi đường dẫn trong tài liệu tính từ thư mục `BTL_TTUD/`.

---

## Mục lục

1. [Tóm tắt nhanh](#1-tóm-tắt-nhanh)
2. [Những điểm của luật cần nắm](#2-những-điểm-của-luật-cần-nắm)
3. [Mức trần (cận trên) và ý nghĩa của "% trần"](#3-mức-trần-cận-trên-và-ý-nghĩa-của--trần)
4. [Công cụ mới và cách dùng](#4-công-cụ-mới-và-cách-dùng)
5. [Thay đổi trong mã nguồn](#5-thay-đổi-trong-mã-nguồn)
6. [Kết quả trên máy chủ](#6-kết-quả-trên-máy-chủ)
7. [Các thí nghiệm và bài học](#7-các-thí-nghiệm-và-bài-học)
8. [Sự cố đã gặp và cách xử lý](#8-sự-cố-đã-gặp-và-cách-xử-lý)
9. [Việc còn dở và đề xuất tiếp theo](#9-việc-còn-dở-và-đề-xuất-tiếp-theo)
10. [Lưu ý vận hành](#10-lưu-ý-vận-hành)
11. [Vị trí dữ liệu, log và kết quả](#11-vị-trí-dữ-liệu-log-và-kết-quả)

---

## 1. Tóm tắt nhanh

| Hạng mục | Trạng thái |
|---|---|
| Thi tính giờ (Mock, chỉ đội mình chơi) | Trung bình **90,1%** trần qua 9 vòng (89,6 - 90,5%). Từng câu đạt 87,9 - 92,7%. |
| Thi tính giờ khi có 50 đội ngang sức (giả lập) | Đường tắc nặng, điểm chỉ còn **72 - 82%** trần. Cách "chọn kế hoạch theo điểm hai ngày" giúp lên hạng 1 - 3 trên 50 đội, nhưng **chưa có trong `thi_dau.py`**. |
| Practice | Tổng **80,2%** trần (74,5 - 88,3% từng câu). Đội 61 hạng 1 ở 4/9 câu (lúc 12:53 ngày 28/10). |
| Mục tiêu 90% ở Practice | **Không đạt được** với trần hiện tại. Lý do và bằng chứng ở mục 3 và 7.3. |
| Mục tiêu 85% ở Practice | Đạt ở 1/9 câu (Q07, 88,3%). Q04 ở 84,0%. |
| RL, ILP | Đã đánh giá, **không dùng làm planner**. Lý do ở mục 7.6 và 7.7. |
| Mã nguồn | Toàn bộ thay đổi **chưa commit**. Bộ test có 105 test, chỉ còn 7 lỗi do thiếu dữ liệu replay của BTC. |

Ba phát hiện quan trọng nhất:

1. **Tắc đường quyết định điểm, không phải chất lượng tìm đường.**
   - Ở Practice, xe nhà tự làm tắc đường. Điểm thực tế gần bằng trường hợp "mọi đường luôn đông" (Q01: 596 so với 574), trong khi đường luôn thông thì được 694.
   - Trong vòng thi thật có nhiều đội, đường cũng sẽ tắc như vậy.
2. **Thứ hạng khi đông đội phụ thuộc rất mạnh vào D (số loại udon mỗi ngày).** Thiếu 1 loại trong 1 ngày là tụt từ top 3 xuống hạng 17 - 50, dù số suất cao.
3. **Chọn kế hoạch theo điểm hai ngày là cải tiến duy nhất có hiệu quả ổn định.**
   - Mỗi ngày tạo 6 phương án, mỗi phương án dùng một mức phạt ô đường sắp tắc khác nhau.
   - Với mỗi phương án, lập thử kế hoạch cho ngày mai rồi chọn phương án có điểm sau hai ngày cao nhất.
   - Kết quả: +11 đến +30 suất trong mọi điều kiện đã thử (Practice, chạy một mình, 50 đội).

---

## 2. Những điểm của luật cần nắm

Phần này chỉ nhắc những chi tiết luật mà các phần sau dựa vào. Đề đầy đủ ở `docs/rules.md` và thư mục `Đề bài/`.

- **Lưới và chi phí:**
  - Lưới lục giác dạng odd-r: hàng chẵn lệch phải, có 6 hướng 0 - 5.
  - Chi phí một bước tính theo **ô đang đứng** (ô nguồn):
    - đồng bằng: 2 bước, 1 nhiên liệu;
    - núi: 3 bước, 2 nhiên liệu;
    - đường: 1 / 2 / 4 bước (thông / đông / tắc), 2 nhiên liệu;
    - ao: không đi được.
- **Tổng thời gian mỗi ngày:** tổng thời gian các lệnh của mỗi xe phải bằng **đúng** số bước của ngày. Lệnh âm là đứng chờ.
- **Xe:**
  - Xe tuần tra (loại 0) thu udon và tiêu nhiên liệu.
  - Xe tiếp tế (loại 1) không thu udon. Xe tuần tra đứng cùng ô với xe tiếp tế thì được đổ đầy nhiên liệu.
- **Tồn kho:** tồn kho mỗi điểm làm mới mỗi ngày. Mỗi xe tuần tra thu một điểm tối đa 1 lần mỗi ngày. Đi ngang qua điểm cũng thu.
- **Điểm số** so theo thứ tự từ điển **(U, D, Q)**:
  - U là số loại udon đã thu trong cả trận;
  - D là tổng số loại thu được của từng ngày;
  - Q là tổng số suất.
  - Hòa thì so thời gian phản hồi.
  - **D đứng trước Q**, nên thiếu 1 loại trong 1 ngày là thua mọi đội đủ D, dù số suất cao.
- **Tắc đường:**
  - Mỗi bước một xe đứng trên ô đường được tính 1 lượt cho ô đó. Đi qua ô thông là 1 lượt, ô đông là 2, ô tắc là 4. Đứng chờ thì mỗi bước 1 lượt.
  - Trạng thái ô đường ngày mai = ngưỡng(tổng lượt của **mọi đội** trong 2 ngày gần nhất / `players`), so với `busyThreshold` và `jammedThreshold`.
  - **Practice** có `players = 1`, nên xe nhà tự làm tắc đường. Ngưỡng tùy map: Q03, Q08 là 2/4; Q10 là 2/3; Q07 là 5/9.
  - **Mock** có `players = 46`, nhưng chỉ đội mình chơi, nên tổng chia 46 gần như bằng 0 và đường luôn thông.
  - **Ngày thi thật:** mọi đội cùng chơi, nên đường sẽ tắc. Xem mục 7.8.
- **Mô phỏng offline:**
  - `simulator.py` khớp máy chủ tuyệt đối. Mọi lần nộp Practice trong đợt này đều được máy chủ chấm đúng bằng điểm mô phỏng.
  - Muốn mô phỏng điều kiện Mock bằng một đội, nhân hai ngưỡng tắc với `players`.

---

## 3. Mức trần (cận trên) và ý nghĩa của "% trần"

"% trần" trong mọi báo cáo bằng:

```
Q đạt được / Q của cận chặt, với đội hình (vị trí xe tiếp tế) đã chọn
```

Cách tính trần nằm ở `src/hexudon/bounds.py`, hàm `score_bounds(..., tight=True)`:

- **Mỗi xe mỗi ngày:** tính số điểm tối đa ghé được theo hai cách, cả hai đều có chứng minh, rồi lấy giá trị nhỏ hơn:
  - **cây khung nhỏ nhất (MST):** k điểm cần ít nhất (k - 1) cạnh rẻ nhất của MST. Cách này chặt ở ngày dài;
  - **quy hoạch động ng-route** (`ng_visits`, `NG_SIZE = 10`): chặt ở ngày ngắn. Ví dụ Q06 Mock giảm từ 1039 xuống 952.
- Lấy thêm giới hạn từ tồn kho, số loại và nhiên liệu (khi không có xe tiếp tế).

**Các giả định lạc quan.** Trần phải đúng với **mọi** chiến lược, nên:

- **Đường luôn thông.** Đây là giả định quan trọng nhất. Một chiến lược thông minh có thể không bao giờ làm tắc đường, nên không thể giả định tắc khi chứng minh cận.
- **Nhiên liệu được tiếp tế khi cần** (`optimistic_refill`): không tính số bước đi đến chỗ xe tiếp tế.
- **Lộ trình được nới lỏng** (MST hoặc ng-route): luôn lớn hơn hoặc bằng lộ trình thật.

**Hệ quả:**

- Ở Mock khi chỉ có mình, trần sát thực tế. Đội mình đạt khoảng 90%.
- Ở Practice và trong trận đông đội, trần đặt cao hơn mức có thể đạt được thật. Map có ngưỡng tắc càng thấp thì càng xa.
- Ở Practice, **không đội nào trong 23 đội** vượt quá khoảng 81% trần này.
- Ở Q01 và Q03, mốc 90% trần còn **cao hơn cả điểm planner đạt được khi đường luôn thông**:

  | Map | 90% trần | Planner, đường luôn thông |
  |---|---|---|
  | Q01 | 700 | 694 - 715 |
  | Q03 | 838 | 791 - 824 |

  Vì vậy 90% ở Practice gần như không thể đạt nếu không có một trần mới tính đến tắc đường (xem mục 9).

Hàm hỗ trợ:

- `bounds_by_supply` (trong `map_analysis.py`): trần theo số xe tiếp tế.
- `report_score`: in "% trần".
- Cận MST thường (`tight=False`) chỉ mất khoảng 0,5 giây mỗi map. Cận chặt mất 5 - 30 giây mỗi map.

---

## 4. Công cụ mới và cách dùng

Mọi lệnh chạy từ `BTL_TTUD/` với `python -X utf8`. Token đọc từ `.env`. Không in token ra màn hình, không dán vào tài liệu.

### 4.1. `thi_dau.py`: chạy thi tự động (dùng cho ngày thi)

Mã ở `src/hexudon/orchestrator.py`. Công cụ này chạy song song nhiều game, mỗi game một runner (`play_match.py`) riêng.

```powershell
# Ngày thi: dán game_id (UUID trên website) là chạy, không quét danh sách trận
python -X utf8 thi_dau.py --match f06e9b26-9e6e-4401-b058-7bceaddf10cb

# Nhiều game cùng lúc
python -X utf8 thi_dau.py <game_id_1> <game_id_2>

# Tổng duyệt: mã số trận -> tự quét mọi câu của trận đó
python -X utf8 thi_dau.py --match 14 --wait-new --vong 2
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `--match` | Nhận game_id (UUID) hoặc mã số trận. UUID thì chạy thẳng game đó, không gọi API quản lý. Mã số thì tự lấy mọi câu của trận đó. |
| `--mode auto/timed/practice` | Mặc định `auto`: tự nhận Practice hay game tính giờ (xem bên dưới). |
| `--wait-new` | Chỉ vào câu khi câu đang ở bước chọn xe và còn ít nhất 20 giây (`MIN_SELECTION`). **Bắt buộc với Mock**, vì Mock tự reset mỗi 10 phút. |
| `--vong N` | Chơi N vòng liên tiếp. Lịch sử ghi ở `lich_su.json`. |
| `--cores` | Mặc định là số nhân trừ 1. Nhân được chia đều cho các câu chưa xong. |
| `--reset` | Chỉ dùng cho Practice: reset câu đã chơi xong rồi chơi lại. |
| `--timeout-minutes` | Giới hạn thời gian mỗi vòng (mặc định 40). |
| `--folder` | Dùng lại thư mục của lần chạy trước để chạy tiếp sau khi bị ngắt. |

Cách hoạt động:

- **Tự nhận loại game** (`game_mode`):
  - Nếu đồng hồ của game đang chạy (`day_deadline_in`, `selection_deadline_in`, `selection_opens_in` lớn hơn 0) thì là game tính giờ.
  - Nếu không, gọi `GET /api/game/practice/score?game_id=<id>:<đội>`: trả điểm thì là Practice, trả 404 thì là game tính giờ.
  - Không dùng được bộ tự nhận trong `live.py`, vì Practice trả đồng hồ bằng 0 và `/day` không ghi `endsAt`.
- **Hiển thị tiến độ:**
  - In ngay khi một câu sang ngày mới hoặc vừa nộp xong (`ngày 7/10, đã nộp`).
  - In xếp hạng sau mỗi ngày: hạng của mình và ba đội đầu. Phần này chạy ở luồng riêng để không làm chậm runner.
    - Game tính giờ: đọc một lần `/api/game/result`.
    - Practice: đọc điểm từng đội, danh sách đội lấy một lần từ API quản lý.
- **Tự khởi động lại** runner bị dừng giữa trận, tối đa 3 lần (`MAX_RESTARTS`). Runner đọc tiếp từ checkpoint.
- **Đọc kết quả ngay khi câu xong** (`collect`), trước khi Mock tự reset.
- **Tổng kết ở `tong_ket.json`:** điểm, hạng, đội hình, trần chặt của đội hình đã chọn, trần của đội hình tốt nhất, "% trần", số tiến trình, số lần khởi động lại.
- **Thời gian một câu do máy chủ quyết định:** khoảng thời gian chọn xe + số ngày x số giây mỗi ngày. Ở Mock là 5,5 - 8,5 phút. Nhiều câu chạy song song thì tổng thời gian bằng câu lâu nhất.

### 4.2. `toi_uu_practice.py`: tối ưu điểm Practice offline rồi nộp

Mã ở `src/hexudon/practice_best.py`. Practice chỉ có một đội và simulator khớp máy chủ, nên công cụ chạy nhiều lượt cả trận offline song song rồi chỉ nộp lượt tốt nhất.

```powershell
python -X utf8 toi_uu_practice.py Q04            # một câu
python -X utf8 toi_uu_practice.py                # mọi câu Practice
python -X utf8 toi_uu_practice.py Q04 --dry-run  # chỉ mô phỏng, không nộp
python -X utf8 toi_uu_practice.py --look 0 --runs 14 --seconds 5   # cách cũ
```

| Tùy chọn | Mặc định | Ý nghĩa |
|---|---|---|
| `--runs` | 7 | Số lượt cả trận mỗi câu. Các lượt chia đều cho mọi vị trí đặt một xe tiếp tế. |
| `--seconds` | 6 | Số giây lập kế hoạch cho một phương án ngày. |
| `--look` | 3 | Số giây lập kế hoạch thử ngày mai để chọn phương án. Đặt 0 thì quay về cách cũ (một phương án mỗi ngày). |
| `--cores` | số nhân - 1 | |
| `--dry-run` | | Chỉ mô phỏng và so với điểm máy chủ. |
| `--force` | | Cho phép reset cả câu đang chơi dở (xem mục 8.1). |

Quy tắc an toàn khi nộp:

- Chỉ reset và nộp khi lượt tốt nhất cao hơn điểm đang có trên máy chủ.
- Mặc định **bỏ qua câu đang chơi dở** (`in_progress`).
- Trước mỗi ngày, đối chiếu vị trí, nhiên liệu và mặt đường trên máy chủ với mô phỏng (`matches_server`). Lệch thì dừng.
- Kết quả và chuỗi lệnh tốt nhất lưu ở `results/practice_best/<thời điểm>/`.

Thời gian: mỗi lượt khoảng 9 phút (10 ngày x 6 phương án x (6 + 3) giây). 7 lượt chạy song song, nên mỗi câu khoảng 9 phút.

### 4.3. `phan_tich_map.py`: trần, đội hình đề xuất, xếp hạng

Mã ở `src/hexudon/map_analysis.py`.

```powershell
python -X utf8 phan_tich_map.py --danh-sach            # liệt kê trận và game_id các câu
python -X utf8 phan_tich_map.py Q01 --xep-hang          # trần + bảng xếp hạng đầy đủ
python -X utf8 phan_tich_map.py --tat-ca --xep-hang     # mọi câu Practice
python -X utf8 phan_tich_map.py Q01 --select            # thêm đội hình đề xuất (mô phỏng 26 giây)
```

- Hàm `standings()` dùng chung với `thi_dau.py`. Nó trả về các đội đã nộp, xếp đúng thứ tự luật.
  - Practice: đọc `practice/score` từng đội; đội bị lỗi mạng được bỏ qua và ghi chú lại.
  - Game tính giờ: đọc `/result`.
- Bảng xếp hạng công khai trên website: trang câu hỏi Practice, mục "Bảng xếp hạng tạm thời" (`https://hexudon.hairbui76.id.vn/tournament/1/round/1/match/11/questions`). Trang "Xếp hạng vòng" thuộc quyền quản trị.

### 4.4. `experiments/tournament_sim.py`: giải đấu giả lập nhiều đội

```powershell
# 8 map Mock, đội mình + 49 bot, in top 10
python -X utf8 experiments/tournament_sim.py --bots 49 --show 10

# Một map, đội mình dùng cách chọn theo điểm hai ngày
python -X utf8 experiments/tournament_sim.py M_Q01 --bots 49 --show 10 --rollout --our-seconds 12
```

- Bản đồ lấy từ `experiments/data/maps/` (M_Qxx là Mock, Qxx là Practice, đều là config gốc lấy từ máy chủ).
- Bot dùng `tour` 2 giây mỗi ngày (`--bot-seconds`), mỗi bot một seed và xoay vòng các vị trí đặt một xe tiếp tế.
- Đội mình dùng `tour` với `--our-seconds` giây. Có `--rollout` thì đội mình chọn theo điểm hai ngày: thử 6 mức phạt, mỗi mức `seconds/2` giây, nhìn trước `seconds/3` giây.
- Ngưỡng tắc được nhân `players / số đội`, để phép chia cho số đội đang mô phỏng khớp với phép chia cho `players` của máy chủ.
- Mỗi đội có kho udon riêng, nên các đội chỉ ảnh hưởng nhau qua mặt đường.
- Mỗi map chạy hai lần: chỉ mình mình, và đông đội.
- Kết quả lưu ở `results/tournament/` (hoặc `--out`), gồm điểm, hạng, bảng xếp hạng đầy đủ và số ô đông/tắc theo ngày.
- Thời gian: 50 đội khoảng 4 phút mỗi map. Có `--rollout` thì khoảng 12 - 18 phút.

---

## 5. Thay đổi trong mã nguồn

Toàn bộ **chưa commit**. Xem bằng `git status` và `git diff`.

### 5.1. File đã có, bị sửa

| File | Thay đổi |
|---|---|
| `src/hexudon/bounds.py` | Trần chặt bằng ng-route (`ng_visits`, `route_visits`, `tree_edges`, khóa `"route"`); cache Dijkstra dùng chung giữa các đội hình. Tính trần cho mọi đội hình giảm từ khoảng 0,55 giây mỗi đội hình xuống khoảng 0,55 giây tổng. |
| `src/hexudon/team_selection.py` | Sửa bộ chọn đội hình (mục 7.1): `screen_key` (nới D 2 điểm, không vượt trần), loại theo trần, mỗi nhóm số xe tiếp tế một đại diện, `GROUP_BOUND_RATIO = 0.81` (`viable_types`), sửa nhánh dự phòng khi sàng lọc chưa xong. |
| `src/hexudon/live.py` | Thêm `--match`, đổi tên câu (Q02) thành game_id, chọn đội hình với số tiến trình được cấp. |
| `src/hexudon/live_api.py` | `LiveAPI.manager()` cho API quản lý (header `Authorization: <token>`, không có `Bearer`), `GAME_ID`, `list_matches`, `resolve_game_id`. |
| `src/hexudon/tour.py` | `road_penalties()`; `Legs`, `DayProblem`, `plan_tour` nhận mảng phạt. Mảng phạt **chỉ đổi đường được chọn**; số bước và nhiên liệu vẫn theo chi phí thật, nên kế hoạch vẫn khớp đúng số bước của ngày. |
| `src/hexudon/planner.py` | `plan_day(..., road_weights=None)` truyền mảng phạt cho `tour`. |
| `tests/test_bounds.py` | Test trần tuyến chặt hơn và không bao giờ thấp hơn lời giải một xe tốt nhất (300 bản đồ ngẫu nhiên). |
| `tests/test_team_selection.py` | Test `viable_types`. |
| `tests/test_tour.py` | Test phạt đường: đổi lộ trình nhưng số bước vẫn đúng chi phí thật. |

### 5.2. File mới

| File | Nội dung |
|---|---|
| `thi_dau.py`, `src/hexudon/orchestrator.py` | Bộ điều phối thi (mục 4.1). |
| `toi_uu_practice.py`, `src/hexudon/practice_best.py` | Tối ưu Practice (mục 4.2). `simulate_rollout` là cách chọn theo điểm hai ngày. `ROAD_WEIGHTS` là bộ phạt nhẹ đã dò ngày 28/10. |
| `phan_tich_map.py`, `src/hexudon/map_analysis.py` | Phân tích map và xếp hạng (mục 4.3). |
| `experiments/tournament_sim.py` | Giải đấu giả lập (mục 4.4). |
| `experiments/data/maps/*.json` | Config 9 map Practice và 8 map Mock. |
| `huong_dan_setup/README.md` | Hướng dẫn cài đặt và chạy. |
| `huong_dan_setup/NHAT_KY_CONG_VIEC.md` | Tài liệu này. |

### 5.3. Bộ test

```powershell
python -X utf8 -m unittest discover -s tests
```

Có 105 test. **7 lỗi là bình thường**: `test_simulator_contract.ServerReplayTests` cần dữ liệu replay của BTC trong `experiments/data/api_evidence/`, mà bản mã hiện tại không kèm. Ngoài 7 lỗi đó, mọi test đều qua.

---

## 6. Kết quả trên máy chủ

### 6.1. Mock Contest (trận 14), chỉ đội mình chơi

Số liệu từ 9 vòng chọn đúng đội hình, ngày 24/10. Mỗi vòng 8 câu chạy song song bằng `thi_dau.py --wait-new`.

| Câu | TB % trần | Thấp nhất - cao nhất |
|---|---|---|
| Q05 | 92,7 | 91,5 - 93,5 |
| Q01 | 92,0 | 90,7 - 92,9 |
| Q04 | 90,8 | 89,6 - 91,4 |
| Q06 | 89,8 | 89,0 - 90,6 |
| Q02 | 88,6 | 87,8 - 89,4 |
| Q11 | 88,6 | 88,1 - 89,7 |
| Q03 | 88,2 | 86,1 - 89,1 |
| Q18 | 87,9 | 86,1 - 90,0 |
| **Cả vòng** | **90,1** | 89,6 - 90,5 |

- Mọi câu đạt U và D tối đa. Không runner nào phải khởi động lại.
- 2 vòng khác (85,7% và 85,8%) bị lỗi chọn đội hình. Lỗi này đã sửa (mục 7.1).
- Ở Mock, bảng xếp hạng luôn là 1/1, vì chỉ có đội 61 nộp bài.

### 6.2. Practice (trận 11)

Số liệu lúc 12:53 ngày 28/10/2026. Đội 61 là "Phenikaa 1" (token trong `.env`). Đội 62 là "Phenikaa 2", cùng trường, cũng đang tối ưu liên tục.

| Câu | Điểm | Trần | % trần | Hạng | Đội đứng trên / đứng sau |
|---|---|---|---|---|---|
| Q01 | (20, 200, 628) | 777 | 80,8 | 2/8 | 62: 633 |
| Q02 | (20, 200, 619) | 777 | 79,7 | 3/6 | 62: 624, 81: 621 |
| Q03 | (20, 200, 694) | 931 | 74,5 | 1/6 | 62: 689 |
| Q04 | (20, 200, 663) | 789 | 84,0 | 2/6 | 62: 664 |
| Q06 | (15, 150, 774) | 953 | 81,2 | 2/6 | 62: 778 |
| Q07 | (15, 150, 865) | 980 | **88,3** | 1/5 | 62: 851 |
| Q08 | (15, 150, 708) | 908 | 78,0 | 1/5 | 62: 705 |
| Q09 | (15, 150, 732) | 933 | 78,5 | 1/5 | 62: 727 |
| Q10 | (15, 150, 718) | 936 | 76,7 | 2/5 | 62: 725 |
| **Tổng** | 6401 | 7984 | **80,2** | | |

- Mọi lần nộp bằng `toi_uu_practice.py` đều được máy chủ chấm **khớp tuyệt đối** với mô phỏng.
- % trần tương quan rất rõ với ngưỡng tắc của map:

  | Map | Ngưỡng đông / tắc | % trần |
  |---|---|---|
  | Q07 | 5 / 9 | 88% |
  | Q04 | 4 / 10 | 84% |
  | Q03, Q08 | 2 / 4 | 74 - 78% |
  | Q10 | 2 / 3 | 77% |

  Q03 còn thêm 161 nhiên liệu và 5 xe, nên thấp nhất.

Game_id các câu (lấy lại bằng `phan_tich_map.py --danh-sach`):

| Câu | Practice (trận 11) | Mock Contest (trận 14) |
|---|---|---|
| Q01 | `c57bfe4b-55ef-416f-893f-1ccaf86a8b87` | `f06e9b26-9e6e-4401-b058-7bceaddf10cb` |
| Q02 | `145bdf65-54f2-41ad-a0e0-29783efdf9b3` | `ca4f5676-4ee2-4b07-8503-7074e5489757` |
| Q03 | `ca50dfe3-0423-4c4d-be40-7520becda4cf` | `1addebd7-50bd-4536-8261-b6186b2a9569` |
| Q04 | `83f54883-4731-472e-bec2-f36f161b1374` | `087d9b9a-9cf5-4838-9fc1-ad49c36a7190` |
| Q05 | - | `2dd1ab59-8954-4a8c-8400-2529e47cafa9` |
| Q06 | `764f35b8-83d2-45f8-99ef-8561a8ceeed3` | `de0d6219-87b4-4ecb-ba65-14d640ec31a4` |
| Q07 | `66bb1d31-0e5e-44b7-a5db-88cb20e31775` | - |
| Q08 | `777d23b7-18c9-498d-a2b0-fb5e6bcfd0d6` | - |
| Q09 | `aedebf80-4659-4b77-ae06-0aa2e272baa5` | - |
| Q10 | `483dd871-8ccf-402d-971b-9f17c4615a8a` | - |
| Q11 | - | `58924333-dcc6-491a-abe4-74b5fe82447f` |
| Q18 | - | `004df232-875a-4ce9-92dd-81cbf8aa8e3b` |

**Chú ý:** cả hai trận đều có câu tên "Q01", nhưng ID khác nhau. Đã có lần chạy nhầm Q01 của Mock vì dán nhầm ID.

---

## 7. Các thí nghiệm và bài học

### 7.1. Bộ chọn đội hình (team selection)

Đội hình là việc chọn xe nào làm xe tiếp tế. Chọn sai làm mất tới hơn nửa số điểm.

**Lỗi 1: D bị nhiễu khi sàng lọc nhanh.**
- Sàng lọc chỉ có vài phần mười giây mỗi ngày, nên D dao động 1 - 2 điểm. Bộ chọn từng chọn đội 2 xe tiếp tế chỉ vì được D 200 so với 199.
- Hậu quả: Q06 được 617 thay vì 747; Mock Q04 được 470 thay vì khoảng 715.
- Sửa:
  - `screen_key` nới D tối đa 2 điểm nhưng không vượt trần;
  - loại đội hình có trần thấp hơn điểm đã đạt;
  - mỗi nhóm số xe tiếp tế có một đại diện vào vòng tinh chỉnh, nhóm có trần cao hơn vào trước;
  - khi chỉ có 1 tiến trình, tin nhóm có trần cao nhất.

**Lỗi 2: tranh CPU khi 8 câu chạy cùng lúc.**
- Câu khởi động đầu tiên giữ 7 tiến trình suốt cả trận, nên các câu sau sàng lọc không xong.
- Nhánh dự phòng khi đó chọn đội hình được mô phỏng đầu tiên, tức đội toàn xe tuần tra.
- Hậu quả: Q01 được 318 so với 716; Q06 chọn 2 xe tiếp tế, được 683 so với 855.
- Sửa:
  - `GROUP_BOUND_RATIO = 0.81`: bỏ trước khi sàng lọc mọi đội hình có trần dưới 81% trần cao nhất. Trong 70 lượt Mock, đội dẫn đầu luôn đạt ít nhất 81,2% trần MST, nên các đội hình bị bỏ không thể thắng. Q11 toàn tuần tra ở mức 86% vẫn được mô phỏng.
  - Nhánh dự phòng chỉ so theo số ngày đã mô phỏng khi mọi đội hình thật sự chạy song song.
  - Bộ điều phối chia nhân theo số câu chưa xong.
- Kiểm chứng: 2 vòng Mock sau khi sửa đạt 89,8% và 90,1%, mọi câu chọn đúng đội 1 xe tiếp tế.

**Lỗi 3: vào câu khi chỉ còn ít thời gian chọn xe.**
- Máy chủ mặc định toàn xe tuần tra. Mock Q03 chỉ được 137 suất.
- Sửa: `MIN_SELECTION = 20` giây.

**Kết luận:** trên mọi map Practice và Mock đã kiểm tra, **đội hình 1 xe tiếp tế luôn tốt nhất**.

### 7.2. Trần chặt hơn

- Trần MST lỏng ở ngày ngắn. ng-route với `NG_SIZE = 10` (khoảng 5 giây mỗi map) làm trần Q06 Mock giảm từ 1039 xuống 952.
- **DSSR** (trần chính xác cho ngày dài) bị tràn bộ nhớ và quá chậm trong Python thuần. **Không thử lại.**
- **Phạt Lagrange theo bậc** cho cây khung: không chặt hơn. Đã bỏ.

### 7.3. Practice: tắc đường do xe nhà gây ra

Cùng planner, chạy trong ba điều kiện đường:

| Map | Tắc thật | Đường luôn đông | Đường luôn thông | 90% trần |
|---|---|---|---|---|
| Q01 | 596 | 574 | 694 | 700 |
| Q03 | 658 | 648 | 798 | 838 |
| Q08 | 684 | 690 | 840 | 820 |

- Ở Practice, điểm thực tế **gần bằng** trường hợp mọi đường luôn đông. Nghĩa là xe nhà làm mất hoàn toàn lợi thế đi nhanh của đường.
- Mất 7 - 18 điểm phần trăm so với đường luôn thông. Trên 9 map Practice, tắc thật đạt 73 - 84%, đường luôn thông đạt 86 - 92%.
- Ở Q03, từ ngày 3 trở đi ngày nào cũng mất 10 - 23 suất. Sau ngày 4 đã có 51 ô đường bị tắc.
- Planner đã tự tránh đứng chờ trên đường, nên lỗ không đến từ việc chờ.
- Cho planner nhiều thời gian hơn khi đường luôn thông:

  | Map | 4 giây | 15 giây | 30 giây |
  |---|---|---|---|
  | Q01 | 704 | 714 | 715 (91 - 92%) |
  | Q03 | 791 | 824 | 821 (tối đa 88,5%) |

  Vậy Q03 không thể lên 90% kể cả khi không có tắc.

### 7.4. Phạt ô đường và chọn theo điểm hai ngày

| Cách | Kết quả |
|---|---|
| Phạt cố định ô sắp đông hoặc tắc (cùng một mức cho cả trận) | Không hơn, nằm trong nhiễu. |
| **Chọn theo điểm hai ngày** (`simulate_rollout`): mỗi ngày thử 6 mức phạt, mỗi mức lập thử ngày mai, giữ phương án có (U, D, Q) cao nhất sau hai ngày | **+20 - 30 suất mỗi lượt** ở Practice. Q01 / Q03 / Q08 một lượt: 616 / 686 / 707, so với 596 / 654 / 686 của cách cũ. |
| Phạt theo nhu cầu của các ngày sau (lặp: lấy ô đường ngày d+1, d+2 cần dùng từ lượt trước để phạt ngày d) | Lấy vòng tốt nhất được thêm 0 - 13 suất, nhưng tốn gấp 3 lần thời gian máy, ngang với chạy thêm seed. Không dùng. |

Mảng phạt được thêm vào trọng số Dijkstra trong `tour.Legs.tree` và **chỉ đổi đường được chọn**. Số bước và nhiên liệu vẫn tính theo chi phí thật.

### 7.5. Dò tham số (train trọng số) cho chọn theo điểm hai ngày

Ngày 28/10. Dò trên Q04, Q01, Q06, mỗi cấu hình 2 seed. Bảng ghi Q trung bình:

| Cấu hình | Q04 | Q01 | Q06 |
|---|---|---|---|
| gốc (3 + 2 giây, bộ phạt cũ, alpha 1,0) | 650 | 611 | 756 |
| **6 + 3 giây** | **657** | 616 | **772** |
| **bộ phạt nhẹ** | 649 | **620** | 758 |
| alpha 0,6 | 649 | 617 | 752 |
| alpha 1,5 / 2,0 | 648 | 605 - 610 | 750 - 764 |
| bộ phạt mạnh | 647 | 612 | 748 |

- Mặc định mới của `toi_uu_practice.py`: **6 + 3 giây** và **bộ phạt nhẹ**.
- Cấu hình này chưa vượt được các bài đã nộp ở Q04 và Q01. Các bài đó là những lượt may ở phần đuôi phân bố điểm.
- Chạy thêm 7 lượt cho mỗi câu theo cách hiện tại thường **không** vượt được điểm cũ. Cách này đã gần chạm trần của nó.

### 7.6. ILP (gợi ý của thầy)

Bộ giải: CP-SAT của OR-Tools 9.15 (có sẵn trên máy). Script ở thư mục tạm của phiên làm việc, không nằm trong repo; mô tả lại như sau.

| Mô hình | Kết quả |
|---|---|
| **ILP từng ngày, nới lỏng nhiên liệu.** Mỗi xe tuần tra một đường đi mở qua các điểm (`AddCircuit`), tổng bước không vượt số bước ngày, mỗi điểm không vượt tồn kho, mục tiêu 1000 x số loại + số suất. | Q01 đường thông: `tour` 713, ILP 734. ILP chứng minh `tour` đã tối ưu ở ngày 7, 8, 9. Q03 đường thông: `tour` 821, ILP 874, nhưng phần lớn chênh lệch là nhờ bỏ qua nhiên liệu (Q03 chỉ có 161). |
| **ILP đầy đủ:** thêm biến thời gian và nhiên liệu ở mỗi nút, xe tiếp tế chọn điểm hẹn, chỉ được đổ xăng khi đến sau xe tiếp tế. Đổi ra lệnh thật và chạy qua mô phỏng. | Trong 20 - 40 giây với 8 luồng, gần như không tìm được lời giải tốt hơn `tour`, thường kém nhiều (Q03 ngày 4: 80 so với 113). Kể cả xuất phát từ lời giải `tour` (`AddHint`), chỉ thắng 1/10 ngày. Cận chứng minh được là <= 128 suất mỗi ngày, gần như không có thông tin. |
| **ILP gọn:** chỉ ràng buộc tổng nhiên liệu, xe tiếp tế theo `tour`, dùng làm ứng viên thứ 7 - 8 trong chọn theo điểm hai ngày. | Trong 30 ngày của Q01, Q08, Q10, **không được chọn lần nào**. ILP tối ưu hôm nay nên tiêu xăng và dùng đường lớn, làm hỏng ngày mai. |
| **ILP cho Practice có tắc** | Không mô hình được việc hôm nay làm tắc đường ngày mai. Cộng cận ILP từng ngày của Q01 chỉ được 678/777, tức 87%. |

**Kết luận:** ILP không giúp lên 90%. Không nên dùng ILP làm planner lúc thi. Giá trị thật của ILP là **làm thước đo**: chứng minh `tour` gần tối ưu theo từng ngày, có thể dùng cho báo cáo, và có thể dùng để xây trần chặt hơn (mục 9).

### 7.7. RL và mạng nơ-ron

- Nhóm đã thử hai lần, ghi ở `docs/rl_branch_evaluation.md` và `docs/rl_policy_training.md`:
  - checkpoint MAPPO đạt (20, 57, 167) ở Q01, kém Greedy (245);
  - PPO train từ đầu cũng không thắng Greedy.
- `tour` hiện tại đạt khoảng 620 ở Q01, gấp gần 4 lần MAPPO.
- Torch trên máy này từng không nạp được (lỗi DLL cudnn), và CP-SAT không có bản GPU. Planner và simulator là Python có nhiều nhánh, nên GPU không giúp.
- Map Practice cố định và simulator khớp máy chủ, nên **tìm kiếm trực tiếp mạnh hơn học một policy**. "Train" hợp lý ở đây là dò tham số của planner (mục 7.5).

### 7.8. Giải đấu giả lập 50 đội (quan trọng cho ngày thi)

Đội mình đấu với 49 bot `tour` ngang sức, ngày 28/10. "Gốc" là đội mình dùng `tour` 6 giây. "Hai ngày" là `--rollout --our-seconds 12`, tức mỗi phương án cũng được 6 giây.

| Map | Một mình (gốc -> hai ngày) | 50 đội, gốc | 50 đội, hai ngày |
|---|---|---|---|
| M_Q01 | 715 (92,0%) -> 724 (93,2%) | 606 (78,0%), hạng 5 | **622 (80,1%), hạng 1** |
| M_Q03 | 815 (87,6%) -> 828 (89,0%) | 673 (72,4%), hạng 1 | **685 (73,7%), hạng 1** |
| M_Q05 | 926 (91,9%) -> 937 (93,0%) | 810 (80,4%), hạng 2 | **824 (81,7%), hạng 1** |
| M_Q18 | 290 (87,6%) -> 297 (89,7%) | (16, **111**, 273), **hạng 17** | (16, 112, 270), **hạng 3** |
| M_Q06 | 842 (88,3%) -> 853 (89,4%) | 750 (78,6%), hạng 2 | **762 (79,9%), hạng 1** |

Bài học:

1. **Kết quả khoảng 90% ở Mock quá lạc quan so với ngày thi.** Có 50 đội thì mỗi ngày có 15 - 60 ô đường đông hoặc tắc, và % trần giảm còn 72 - 82%.
2. **Các đội mạnh sát nút nhau.** Ở M_Q01, 42 đội đủ D chỉ cách nhau 35 suất (583 - 618).
3. **D quyết định hạng.**
   - 8 bot thiếu 1 loại trong 1 ngày rơi xuống cuối bảng, dù có bot được 609 suất.
   - Ở M_Q18 (nhiên liệu chỉ 68), bản gốc của đội mình thiếu D nên rơi xuống hạng 17. Bản hai ngày giữ đủ D và lên hạng 3.
4. **Thêm giây tính toán không giúp nhiều** (6 giây so với 2 giây của bot vẫn chỉ hạng 5). **Chọn theo điểm hai ngày thì giúp ổn định**: +12 đến +16 suất ở cả 5 map, hạng 1 ở 4 map và hạng 3 ở M_Q18 (nhờ giữ đủ D). Mỗi map mới chạy 1 seed, nên cần thêm seed để chắc chắn.
5. Khi đông đội, lượt của riêng đội mình chỉ khoảng 2% tổng lượt. Lợi thế của cách hai ngày đến từ việc kết thúc ngày ở vị trí tốt và còn đủ nhiên liệu cho ngày mai, chứ không phải né tự gây tắc. Phần nhìn trước giả định mặt đường ngày mai giống hôm nay.

### 7.9. Các ý tưởng đã thử và bỏ (từ trước 28/10)

- **Đi kèm (convoy, escort) cả đội:** từ cùng một điểm xuất phát, chia tuyến được 94 so với đi kèm 85. Cả trận cũng không hơn, kể cả Q18 (nhiên liệu 68).
- **Chạy 3 seed ngắn thay vì 1 lượt dài khi chỉ có 1 tiến trình:** bằng hoặc kém hơn ở 3/4 map.
- **Đội hình 0 hoặc 2 xe tiếp tế cho Practice Q03:** tốt nhất chỉ được 528, so với 693 của đội 1 xe tiếp tế.

---

## 8. Sự cố đã gặp và cách xử lý

### 8.1. Nộp đè lên lượt Practice đang chơi dở (Q02, 28/10)

- **Chuyện xảy ra:** `toi_uu_practice.py` reset và nộp đè lên một lượt Q02 đang ở trạng thái `in_progress` với điểm (20, 100, 285). Có thể đó là lượt của thành viên khác.
- **Nguyên nhân:** cơ chế "có lượt nộp trong 15 phút gần đây" (`recently_active`) dựa vào trường `last_submitted_at`, nhưng máy chủ **không trả** trường này. Kiểm tra vì vậy luôn ra "không hoạt động".
- **Sửa:** mặc định bỏ qua mọi câu đang chơi dở. Chỉ reset khi chạy với `--force`.

### 8.2. Runner treo khi chạy Practice ở chế độ thi tính giờ

- **Chuyện xảy ra:** `thi_dau.py` mặc định là `--mode timed`, nên runner chờ máy chủ tự sang ngày. Practice không bao giờ tự sang ngày.
- **Sửa:** mặc định `--mode auto`, có `game_mode()` tự nhận loại game (mục 4.1).

### 8.3. `--match` nhận UUID

- Ban đầu `--match` chỉ nhận số, nên dán UUID thì báo lỗi.
- Bản sửa đầu tiên hiểu sai ý người dùng: nó tự quét danh sách trận và chạy cả trận chứa UUID đó, nên đã chạy nhầm cả 8 câu Mock.
- Hiện tại: UUID thì chạy đúng game đó, không gọi API quản lý. Nhập trùng một game (khác hoa thường, hoặc có đuôi `:61`) chỉ chạy một runner.

### 8.4. Vào Mock giữa lượt

- Chạy `thi_dau.py` cho Mock mà không có `--wait-new` thì runner vào giữa lượt, lỡ bước chọn xe (`missed_selection`).
- Kết quả bị như Mock Q01: (20, 141, 243), chỉ nộp được 7 ngày.
- **Với Mock luôn dùng `--wait-new`.** Ngày thi không cần, vì trận thi không quay lại từ đầu.

### 8.5. Tiến trình mồ côi

- Bấm Ctrl+C khi `thi_dau.py` hoặc `toi_uu_practice.py` đang chạy có thể để lại các tiến trình con (`multiprocessing.spawn`) sau khi tiến trình cha đã thoát. Đã gặp 13 tiến trình như vậy và đã dọn.
- Kiểm tra bằng PowerShell:

  ```powershell
  Get-CimInstance Win32_Process -Filter "name='python.exe'" | Select ProcessId, ParentProcessId, CreationDate
  ```

  Chỉ tắt tiến trình có tiến trình cha không còn tồn tại.

### 8.6. Mock tự reset làm mất kết quả

- Đọc kết quả sau khi Mock đã reset sẽ không còn gì.
- Bộ điều phối vì vậy đọc điểm, hạng và đội hình **ngay khi** từng câu xong (`collect`), còn trần thì tính lúc tổng kết.

---

## 9. Việc còn dở và đề xuất tiếp theo

Xếp theo mức ưu tiên cho ngày thi.

1. **Đưa "chọn theo điểm hai ngày" vào runner thi (`live.py` / `thi_dau.py`).** Đây là việc quan trọng nhất.
   - Giải đấu 50 đội cho thấy cách này giúp +12 đến +16 suất, lên hạng 1 - 3, và giữ đủ D ở map ít nhiên liệu.
   - Cách làm đề xuất:
     - mỗi ngày chạy song song 6 phương án (6 mức phạt `ROAD_WEIGHTS`) trên 6 tiến trình, mỗi phương án khoảng 1/3 thời gian của ngày;
     - với mỗi phương án, lập thử ngày mai với giả định mặt đường giống hôm nay;
     - chọn theo (U, D, Q) sau hai ngày, nộp sớm, rồi nộp lại nếu có bài tốt hơn (giữ cơ chế hiện tại của `live.py`).
   - Phải giữ nộp sớm một bài an toàn trước, để không bao giờ trễ hạn.
   - Kiểm thử bắt buộc: chạy trên Mock thật nhiều vòng bằng `thi_dau.py --match 14 --wait-new --vong 3`, rồi so "% trần" với số liệu ở mục 6.1. Đồng thời chạy lại `experiments/tournament_sim.py` cho cả 8 map.
2. **Mở rộng kiểm chứng giải đấu.** Đã có 5 map, mỗi map 1 seed. Cần chạy thêm seed (đổi `seed` trong `play()`) và chạy thêm M_Q02, M_Q04, M_Q11.
3. **Ưu tiên D tuyệt đối khi đông đội.** Thêm kiểm tra: nếu phương án tốt nhất có nguy cơ thiếu loại trong ngày thì chọn phương án đủ loại dù ít suất hơn. Thứ tự (U, D, Q) đã làm điều này nếu nhìn trước đủ xa. Cần đo thêm ở các map ít nhiên liệu (M_Q18, M_Q03).
4. **Trần Practice có tính tắc đường** (vẫn phải là cận có chứng minh), để "% trần" phản ánh đúng mức có thể đạt. Hướng gợi ý:
   - ILP chính xác từng ngày (bài toán chọn lộ trình nhiều xe, chia chung tồn kho) với vị trí xuất phát tự do;
   - ràng buộc mỗi ô đường chỉ có thể thông lại sau 2 ngày không dùng.
   - Đây là việc nghiên cứu, không chắc làm được nhanh.
5. **Practice:** chạy thêm lượt bằng `toi_uu_practice.py` khi máy rảnh. Ưu tiên Q04 (còn thiếu 8 suất để đạt 85%), Q01, Q06. Kỳ vọng chỉ thêm vài suất mỗi câu.
6. **Commit** toàn bộ thay đổi sau khi người phụ trách duyệt. Hiện chưa có commit nào cho đợt này.

---

## 10. Lưu ý vận hành

- **Token** chỉ nằm trong `.env`. Không in ra, không đưa vào tài liệu hay log. Mã trong `live_api.py` đã thay token bằng `[TOKEN]` khi báo lỗi.
- **Không bao giờ reset trận thi chính thức.** `practice/reset` chỉ dùng cho Practice của chính đội mình. `thi_dau.py --reset` chặn khi `--mode timed`.
- **Thành viên khác có thể đang chơi cùng token.** Trước khi tối ưu Practice, kiểm tra trạng thái các câu. `toi_uu_practice.py` đã tự bỏ qua câu `in_progress`.
- **Mock:** luôn dùng `--wait-new`. Kết quả Mock không tính điểm thật, và bảng xếp hạng Mock luôn là 1/1.
- **Máy yếu:**
  - Thi thật mỗi câu khoảng 5,5 - 8,5 phút, nhiều câu chạy song song vẫn dưới 10 phút.
  - Đừng chạy `toi_uu_practice.py` hoặc `tournament_sim.py` cùng lúc với `thi_dau.py`, vì tranh CPU sẽ làm sàng lọc đội hình nhiễu (mục 7.1).
- **Dừng an toàn:**
  - `thi_dau.py` bắt Ctrl+C và in lệnh chạy tiếp (`--folder`).
  - Với vòng lặp shell chạy nhiều lệnh, phải dừng vòng lặp trước rồi mới tắt các tiến trình Python, nếu không vòng lặp sẽ mở câu tiếp theo.
- **API quản lý:**
  - `https://hexudon.hairbui76.id.vn/manager/api`, header `Authorization: <token>` (không có `Bearer`).
  - `GET /match`: danh sách trận và đội.
  - `GET /question?match[eq_id]=N`: danh sách câu; ID câu chính là game_id.

---

## 11. Vị trí dữ liệu, log và kết quả

| Đường dẫn | Nội dung |
|---|---|
| `results/thi_dau/<thời điểm>/[vong_n/]<câu>/runner.log` | Log runner từng câu. |
| `results/thi_dau/<thời điểm>/[vong_n/]tong_ket.json` | Điểm, hạng, đội hình, % trần từng câu. |
| `results/thi_dau/<thời điểm>/lich_su.json` | Lịch sử nhiều vòng. |
| `results/practice_best/<thời điểm>/` | `log.txt`, `tong_ket.json`, chuỗi lệnh tốt nhất `<câu>.json` của mỗi lần tối ưu Practice. |
| `results/tournament/`, `results/tournament/goc/`, `results/tournament/hai_ngay/` | Kết quả giải đấu giả lập (`tong_ket.json` có bảng xếp hạng đầy đủ). |
| `results/maps/<game_id>.json` | Config map lưu bởi `phan_tich_map.py`. |
| `experiments/data/maps/` | Config 9 map Practice (Qxx) và 8 map Mock (M_Qxx) cho thí nghiệm offline. |
| `huong_dan_setup/README.md` | Hướng dẫn cài đặt và chạy. |
| `docs/` | Tài liệu cũ của dự án (luật, planner `tour`, quy trình ngày thi, đánh giá RL). |
