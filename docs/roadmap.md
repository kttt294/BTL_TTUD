# Lộ trình phát triển HEXUDON đến kỳ thi

Cập nhật: 20/10/2026. Còn hơn một tháng; có GPU nếu cần huấn luyện. Mục tiêu: vô địch kỳ thi
thật (trận tính giờ, nhiều đội, bản đồ chưa biết), không phải tối đa điểm Practice.

## Nguyên tắc

1. **Thứ tự chấm điểm quyết định ưu tiên.** U → D → Q → tổng thời gian phản hồi của bài hợp lệ
   cuối cùng mỗi ngày → xúc xắc/hòa. Các đội mạnh đều đạt tối đa U và D trên Practice, nên:
   - U, D là điều kiện phải giữ chắc: mất 1 D là thua dù Q cao hơn nhiều.
   - Q là chiến trường chính.
   - Thời gian phản hồi chỉ quyết định khi hòa Q (dễ xảy ra trên bản đồ nhỏ, Q chạm trần).
     Không bao giờ đổi Q lấy thời gian: chỉ nộp lại khi bài mới tốt hơn; dừng sớm khi đã chạm
     cận trên của ngày.
2. **Luôn giữ script thi an toàn**: `play_match.py` chỉ chạy phần đã kiểm chứng. Mọi hướng mới
   nằm sau công tắc mặc định tắt, chỉ bật mặc định khi đã đo và thống nhất; hướng đã đo mà không
   tốt hơn thì xóa khỏi code (21/10 đã xóa LOOKAHEAD, ROLLOUT, TOPUP, β, chọn vai trò nhiều kịch bản). Mọi kế hoạch qua simulator trước khi gửi; lỗi
   planner phải chuyển sang phương án dự phòng, không bỏ trống ngày.
3. **Đánh giá trên phân bố của đề thi**, không chỉ 8 config Practice: bản đồ 8–32 ô, 3–8 xe,
   4–10 ngày, kho 1..số xe; có kịch bản nhiều đội; đúng ngân sách thời gian thi. Chia bản đồ
   phát triển / kiểm tra; báo cáo tỷ lệ mất D, Q trung bình, thời gian phản hồi, số lần dự phòng.
4. Kết quả gắn tên thuật toán nào phải do thuật toán đó tạo ra; hybrid ghi rõ là hybrid.

## Trạng thái hiện tại

- Planner `tour` (tuyến cả đội + phá/dựng lại + 14 seed song song + bảo vệ D bằng phủ loại và ô
  neo). Practice BTC chấm, dùng gần hết thời hạn: đứng đầu cả 9 bài (ví dụ Q01 634 so với 566,
  Q03 682 so với CTU_1 670).
- Runner: ngân sách theo config (daySeconds − 4 giây), chọn vai trò theo
  agent_selection_time_limit − 4 giây; trận tính giờ nộp nhanh sau 2–5 giây rồi chỉ nộp lại khi
  tốt hơn (anytime, 14 tiến trình), dừng sớm khi chạm cận trên ngày; kiểm tra hạn token; dự
  phòng khi planner/nhóm tiến trình lỗi. 89 test.
- Mô phỏng nhiều đội vòng kín (`experiments/multi_team_sim.py`): nhiều đội không làm đường tắc
  hơn chơi một mình (lưu lượng chia trung bình); ba chế độ nhìn trước ngang nhau → giữ
  `persistence`. Mất D còn khoảng 3–6% trận ở 3 giây/ngày, luôn ở ngày ngắn.
- Các hướng đã đo và loại (giữ công tắc tắt): nhìn trước nhiều kịch bản, xe tiếp tế di động,
  rollout 2 ngày, chọn vai trò nhiều kịch bản, nạp sẵn nhiên liệu trước ngày ngắn. Q của `tour` sát giới hạn thực tế: thêm thời
  gian, nạp nhiên liệu hoàn hảo hay nhìn trước 2 ngày đều chỉ đổi khoảng ±2%.

## Giai đoạn 0 — An toàn khi thi (làm ngay)

- [ ] Tập dượt trận tính giờ trên máy chủ giả đồng hồ thật (`experiments/rehearse_timed.py`):
      không ngày nào trống bài, không nộp muộn, đo thời gian phản hồi; thêm độ trễ, lỗi 5xx,
      tắt runner giữa chừng rồi chạy lại.
      - 20/10: lần tập dượt đầu tìm ra lỗi runner thoát cuối ngày 1 (GET /day sát hạn ném
        TimeoutError không được bắt). Đã sửa + test hồi quy; bản rút gọn 12 giây/ngày chạy đủ
        10 ngày, không ngày trống bài.
      - 20/10, đủ thời hạn 30 giây/ngày: Q01 (20, 200, 627), nộp nhanh 2,6–3,3 giây, nộp lại
        3/10 ngày ở ~25 giây, phản hồi lũy kế 96 giây; Q03 có trễ mạng ≤0,3 giây và 5% lỗi 503:
        (20, 200, 684), không ngày trống bài. Lưu ý: chạy việc khác trên máy thi làm Q01 tụt
        còn 577 → ngày thi không chạy gì khác.
      - 20/10, tắt runner (như Ctrl+C) ở ngày 3 giây 24,9 rồi chạy lại sau 5 giây cùng checkpoint:
        ngày 3 giữ bài nộp nhanh lúc 3,0 giây, runner mới tiếp tục từ ngày 4, không nộp trùng,
        không ngày trống bài, (20, 200, 622). Cách xử lý khi runner chết: chạy lại đúng lệnh cũ.
- [x] Lệnh kiểm tra trước trận `play_match.py --preflight --game-id ID` (chỉ GET): token, độ trễ,
      config, CPU, khởi động tiến trình, thư mục checkpoint, thử lập kế hoạch ngày 1. Chạy trên
      máy chủ thật 20/10: sẵn sàng, không cảnh báo.
- [ ] Thử Competitive Practice (nếu BTC mở) để kiểm chứng trận nhiều đội thật.
- [x] Hướng dẫn vận hành ngày thi: `docs/contest_day.md`.

## Giai đoạn 1 — Hạ tầng đánh giá

- [x] Bộ sinh bản đồ giống phân bố đề (`generator.generate_config`, profile `btc`/`wide`).
      Địa hình BTC rải ngẫu nhiên độc lập theo tỷ lệ cố định 21/34/20/25% (đồng bằng/đường/
      núi/ao), không có cụm; bộ sinh làm y vậy và giữ liên thông.
- [ ] Chế độ số vòng lặp cố định để A/B tái lập được (cùng seed → cùng kết quả).
- [x] Bộ đo chuẩn (`experiments/benchmark_generated.py`, dev seed 1000+, test seed 9000+).
      - 20/10, 2 giây/ngày: `btc` 24 bản đồ: U, D tối đa 24/24, Q/cận 0,60. `wide` 24 bản đồ:
        U 24/24, mất D 3/24 (seed 1011 ngày 1 chỉ 31 step: không đội hình nào đủ loại → không
        tránh được; seed 1012, 1013 ngày 33/41 step: ở 8 giây/ngày thì đủ D), Q chạm cận ở 5/24
        bản đồ nhỏ → tiêu chí 4 quyết định ở đó. Không lần nào dự phòng, ngày lâu nhất 1,83 giây.

## Giai đoạn 2 — Giữ chắc U, D (tiêu chí 1–2)

- [ ] Loại mất D ở ngày ngắn: bộ giải phủ loại mạnh hơn (tìm kiếm chính xác/nhánh cận cho
      bài phủ loại khi ngày ngắn), ô neo theo kế hoạch hai ngày.
- [ ] Kiểm tra D trên bản đồ khó: kho ít (tranh kho), nhiên liệu rất nhỏ, nhiều ngày ngắn,
      8 xe/nhiều điểm (thời gian dựng tuyến).
- [x] Mặt đường 0/1/2 (`experiments/traffic_robustness.py`, 22/10): ép mặt đường cố định (thông
      thoáng / đông / ùn tắc / ngẫu nhiên / tắc quanh mọi điểm) trên 6 bài: 30/30 trận không kế hoạch
      lỗi, U luôn tối đa, Q luôn vượt Greedy. Mất D chỉ khi đường tắc ở ngày ngắn; ở 10 giây/ngày ×
      14 tiến trình còn 3/8: 2 ca không thể tránh (bộ giải chính xác/cận xác nhận), 1 ca thật.
- [x] Ô neo trước ngày ngắn khi đường tắc: Q01 `hotspot` ngày 6 (69 step) chỉ 15–16/20 loại do vị
      trí cuối ngày 5 (hai xe đứng gần nhau). Sửa 22/10: `find_anchors` thêm 3 bộ khởi đầu rải đều
      (`spread_anchors`, bán kính 35/50/70% step ngày mai), khởi động lại khi kẹt, dành 40% thời gian
      khi ngày mai ngắn hơn. Kết quả 17/20; tự do đặt xe ở bất kỳ đâu với bình đầy cũng chỉ tìm được
      19/20 → gần như không thể đủ. Hồi quy: mặt đường thật Q01 623, Q03 692, Q07 823, Q10 704 (trong
      biên cũ); 30 trận ép mặt đường 23/30 đủ U, D (trước 22/30), 0 kế hoạch lỗi.
- [ ] Đội không có xe tiếp tế: chia nhiên liệu theo nhu cầu phủ loại các ngày sau.

## Giai đoạn 3 — Tăng Q (tiêu chí 3)

- [x] ~~Xe tiếp tế di động~~: không đáng làm. Cận trên đo bằng nhiên liệu vô hạn trên 14 bản
      đồ `btc` chỉ +1,6% Q trung bình (tối đa +5,7% khi nhiên liệu 160).
- [x] ~~Rollout 2 ngày (`tour.ROLLOUT`)~~: lần đo đầu làm hỏng Q07 do quá hạn; sau khi sửa
      quá hạn, đo lại 8 bài: chênh Q trung bình −0,9 (−15…+15,5), có ngày vượt ngân sách
      (5,2/5 giây). Không lợi, giữ tắt.
- [x] ~~Nạp sẵn nhiên liệu trước ngày ngắn (`tour.TOPUP`)~~ (ý tưởng người dùng 21/10): BTC 8
      bài kém hơn 7/8 (−31…+2 Q, TB −15); `wide` 24 bản đồ thắng/hòa/thua 8/6/10, Q ±0, D lợi ở 2
      bản đồ nhiên liệu thấp nhưng mất 1 D ở 1 bản đồ khác. Nạp sớm tốn chắc vài suất hôm nay,
      lợi ngày mai nhỏ vì tổng chi phí tiếp nhiên liệu chỉ ~1,6–2,5% Q. Giữ tắt.
- [x] Dự phòng khi tiến trình song song không kịp: lượt dựng đầu giới hạn max(ngân sách, 0,5
      giây); chạy song song dùng cơ chế anytime nên có kế hoạch tạm ở nửa ngân sách. 16 trận
      đo lại không lần nào phải dự phòng.
- [x] Toán tử tìm kiếm mới (đảo đoạn 2-opt, đổi điểm giữa hai xe, bỏ điểm tốn kém nhất), 30% số
      vòng. Bộ đo mức ngày (`experiments/benchmark_day.py`, 160 trạng thái đầu ngày, 3 seed):
      +0,6–0,8% suất ở 1 giây, +0,16% ở 3 giây, không mất loại → giữ làm mặc định (giúp nhất
      khi ngân sách nhỏ, ví dụ sàng lọc đội hình).
- Khoảng cách tới tham chiếu mạnh (40 trạng thái, tốt nhất của 3 seed × 20 giây): 1 seed × 3
  giây kém 3,5% Q, tốt nhất của 3 seed × 3 giây kém 1,8%, không thiếu loại. Khi thi chạy 14 seed
  × ~25 giây nên tìm kiếm trong ngày đã gần bão hòa so với chính `tour`; muốn tăng Q đáng kể phải
  tìm ở chỗ khác (bộ giải ngày mạnh hơn về chất, vị trí giữa các ngày, đội hình).
- Khoảng cách tới tối ưu thật (`experiments/optimality_gap.py`, bộ giải chính xác Held-Karp, 40 bản
  đồ nhỏ 10–13 điểm, 1–2 xe, nhiên liệu dư, ngày bị ràng buộc thời gian): tốt nhất của 3 seed × 3
  giây đạt đúng tối ưu 39/40, không thiếu loại, Q kém TB 0,4%; 1 seed × 1 giây đạt 34/40 (kém 1,7%).
  Kết luận: bài tối ưu một ngày gần như đã giải xong; không cần bộ giải ngày mạnh hơn.
- [x] ~~Chọn vai trò nhiều kịch bản~~ (`SELECTION_SCENARIOS`, `compare_selection_scenarios.py`):
      20/10, 8 bài BTC, 26 giây: chọn khác ở 3/8 bài; Q01, Q10 ngang nhau, Q07 chọn nhầm 2 xe tiếp
      tế (mất ~200 Q) vì mỗi kịch bản chỉ còn nửa thời gian sàng lọc. Giữ `("solo",)`.
- [x] Độ ổn định bộ chọn vai trò (`experiments/selection_stability.py`, 22/10): vòng hai đã chạy mỗi
      đội hình 3 seed, nhưng 4 lần chọn vẫn ra 2–4 đội hình khác nhau (luôn 1 xe tiếp tế, khác vị
      trí). `experiments/compare_compositions.py` (mọi vị trí xe tiếp tế × 3 seed × 8 bài): chênh Q
      trung bình giữa vị trí tốt nhất và kém nhất chỉ 5–12, cỡ độ lệch chuẩn một đội hình → các vị
      trí gần như tương đương, chọn ngẫu nhiên mất TB ~3–6 Q (<1%). Không đáng tối ưu thêm.
- [ ] Mở rộng ứng viên chọn vai trò cho 7–8 xe trên bản đồ `wide` (2 xe tiếp tế có thể đáng hơn).
- Lưu ý cạnh tranh: trên bản đồ Q01/Q02 Q của ta dao động 600–634, CTU_1 đạt 610 (thiếu 1 D) và
  621 → gần như ngang nhau; thắng thua ở dao động Q hoặc tiêu chí 4.

## Giai đoạn 4 — Thời gian phản hồi (tiêu chí 4)

- [x] Nộp nhanh 2–5 giây rồi chỉ nộp lại khi tốt hơn; dừng khi chạm cận trên ngày.
- [x] Cận trên ngày chặt hơn: mỗi điểm chỉ tính cho xe tuần tra tới kịp trong số step của ngày.
- [x] Nộp lại ngay khi có bài tốt hơn (kiểm tra mỗi 2 giây, cách nhau ≥ 5 giây, tối đa 3 lần giữa
      ngày + bài cuối; tổng ≤ 5 lần/ngày) và ngủ tới sát giờ chuyển ngày rồi hỏi mỗi 0,1 giây.
      Tập dượt 21/10 (máy chủ giả, đồng hồ thật): Q01 (20, 200, 624) phản hồi lũy kế 45,9 giây (cơ
      chế cũ 96–209); Q03 có trễ mạng + 5% lỗi 503: (20, 200, 678), 82,3 giây (cũ 186); Q07 ngày 45
      giây: (15, 150, 845), 83,9 giây (ước tính cũ 159,5). Không ngày trống bài, ≤ 3 lần nộp/ngày.
- [ ] Hỏi BTC giới hạn số lần nộp/ngày được coi là "quá nhiều" để nới MIN_GAP/MID_SUBMITS nếu được.
- [ ] Đo thời gian phản hồi trên Competitive Practice (Practice tự luyện trả 0).

## Giai đoạn 5 — Học máy (tùy chọn, sau khi giai đoạn 1–3 ổn định)

Chỉ làm khi có bộ đo chuẩn để chứng minh lợi ích; luôn có `tour` làm dự phòng.
- [ ] Học có giám sát: giá trị vị trí cuối ngày (số loại/suất ngày mai) thay ước lượng tham lam.
- [ ] Xếp hạng đội hình nhanh từ đặc trưng bản đồ.
- [ ] Học chọn toán tử/điểm phá cho tìm kiếm.
- [ ] RL (GPU) chỉ khi các thành phần trên cho thấy còn khoảng cách lớn tới cận trên.
