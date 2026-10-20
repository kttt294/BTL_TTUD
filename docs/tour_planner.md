# Planner tuyến cả đội (`--algorithm tour`)

Mã nguồn: `src/hexudon/tour.py`. Gọi qua `plan_day(..., strategy="tour")`, `play_match.py --algorithm tour`
hoặc `src/main.py ... --strategy tour`. Chỉ dùng thư viện chuẩn, không dùng RL.

## Vì sao cần planner mới

Greedy cũ lập kế hoạch từng ngày như thể không có ngày sau. Trên Q01, toàn tuần tra, ba ngày
đầu thu đủ 20/20 loại nhưng tiêu khoảng 230 nhiên liệu mỗi xe mỗi ngày; từ ngày 4 xe gần cạn
và chỉ còn 4 loại/ngày. Simulator tái hiện đúng điểm máy chủ của lượt Practice đã nộp,
`(20, 101, 253)`. Đội hình có xe tiếp tế của Greedy cũ đạt D gần tối đa nhưng xe tiếp tế chỉ
đứng ở một điểm trung tâm cố định và xe tuần tra chỉ rẽ vào khi hết điểm để đi.

U thường đạt cận trên (số chuỗi trong config) với cả hai planner. Khi D cũng đạt cận trên
(số chuỗi × số ngày), thứ tự thắng thua nằm ở Q.

## Mô hình một ngày

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

## Tìm kiếm

1. Với mỗi phương án điểm hẹn, dựng nhanh bằng chèn tham lam: ưu tiên điểm cho loại mới toàn
   trận, rồi loại mới trong ngày, rồi thêm suất; trong cùng lớp chọn chỗ chèn tăng chi phí ít
   nhất. Phương án đầu luôn được dựng trọn, kể cả khi ngân sách nhỏ.
2. Giữ phương án điểm hẹn tốt nhất, dùng phần thời gian còn lại cho phá và dựng lại: bỏ ngẫu
   nhiên vài điểm hoặc một đoạn tuyến, đôi khi đổi kiểu đường của một xe, chèn lại có nhiễu,
   nhận nếu điểm ngày không giảm.
3. Chuyển thành lệnh, kiểm tra bằng simulator. Nếu lỗi thì dùng Greedy cũ với thời gian còn lại
   thay vì đứng chờ cả ngày.

## Bảo vệ D ở ngày ngắn

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

## Chọn vai trò

`select_types(..., strategy="tour")` mô phỏng các đội hình song song bằng nhiều tiến trình
(`select_types_parallel`), sàng lọc với ngân sách nhỏ rồi đánh giá lại tối đa bốn đội hình tốt
nhất. Nếu bản đồ quá lớn để chạy hết trận trong hạn, chọn theo số ngày đã mô phỏng rồi điểm.
`play_match.py --algorithm tour` mặc định dành 20 giây cho bước này.

## Kết quả offline (20/10/2026, sau khi thêm bảo vệ D)

`experiments/compare_pipeline.py`, mô phỏng một đội, máy 16 nhân. Bản cũ: chọn vai trò bằng
Greedy 8 giây + Greedy. Bản mới: chọn vai trò bằng `tour` 20 giây + `tour` 5 giây/ngày.

| Case | Bản cũ (U, D, Q) | Bản mới (U, D, Q) | Đội hình mới | Đội 57, BTC chấm |
|---|---|---|---|---|
| Q01 | (20, 101, 253) | (20, 200, 597) | 1 tiếp tế | (20, 200, 532) |
| Q03 | (20, 84, 137) | (20, 200, 656) | 1 tiếp tế | (20, 200, 530) |
| Q04 | (20, 72, 131) | (20, 200, 643) | 1 tiếp tế | (20, 200, 481) |
| Q06 | (15, 82, 194) | (15, 150, 727) | 1 tiếp tế | (15, 150, 454) |
| Q07 | (15, 82, 301) | (15, 150, 837) | 1 tiếp tế | (15, 150, 760) |
| Q08 | (15, 93, 307) | (15, 150, 684) | 1 tiếp tế | (15, 150, 620) |
| Q09 | (15, 72, 146) | (15, 150, 701) | 1 tiếp tế | (15, 150, 523) |
| Q10 | (15, 90, 246) | (15, 150, 698) | 1 tiếp tế | (15, 150, 551) |

Bản đồ tự sinh (chạy trước khi thêm cơ chế bảo vệ D, commit `f7eac58`): bản mới thắng hoặc hòa
cả 6 bản đồ; xem `experiments/tour_results/pipeline.json`.

Điểm đội 57 là điểm máy chủ BTC, do người dùng đọc từ tài khoản đội đó; điểm của ta là simulator
một đội. Simulator đã tái hiện đúng điểm máy chủ `(20, 101, 253)` của lượt Practice Q01 bằng Greedy.
Bản mới đạt cận trên U và D ở cả 8 bài BTC; không có lần nào phải dùng Greedy dự phòng.
Cận Q là `Σ min(kho, số xe tuần tra) × số ngày`, bỏ qua giới hạn step nên không đạt được ở ngày ngắn.
Q01 và Q02 cùng cấu hình nên chỉ chạy Q01. Một lượt chạy cho mỗi case; kết quả dao động theo đồng hồ.

## Tham số đã thử nhưng không bật

- β (giá trị vị trí cuối ngày theo số điểm ghé được hôm sau): kết quả trong biên độ nhiễu,
  đôi khi mất 1 điểm D, nên mặc định β = 0.
- α khác 1 với đội toàn tuần tra: 0,7, 1,5 và 2,5 đều không tốt hơn 1 trên Q01.

## Giới hạn

- Điểm đo là offline một đội; giao thông tương lai chỉ do đội mình tạo. Khi thi nhiều đội,
  lưu lượng được chia cho số đội.
- Tìm kiếm cục bộ phụ thuộc đồng hồ nên kết quả dao động khoảng ±15 suất giữa các lần chạy.
- Xe tiếp tế chỉ có một điểm hẹn mỗi ngày; chưa có lịch hẹn nhiều điểm hay đi kèm xe tuần tra.
- Lượt dựng đầu tiên không bị cắt theo hạn giờ: 32×32, 8 xe, 110 điểm mất khoảng 2,4 giây.

## Kiểm chứng máy chủ ngày 20/10/2026

Sau bảng offline, nhóm đã nộp thật 8 bản đồ khác nhau vào Practice riêng của đội 62. Đội hình lấy từ pipeline đã lưu, không chạy lại bộ chọn vai trò; planner dùng 5 giây/ngày và lấy giao thông thật mỗi ngày. Q02 trùng Q01, không tính thành mẫu độc lập.

| Bài | Greedy cũ, BTC | Tour mới, BTC | Đội 57, BTC |
|---|---|---|---|
| Q01 | (20, 101, 253) | (20, 200, 614) | (20, 200, 532) |
| Q03 | (20, 84, 137) | (20, 200, 659) | (20, 200, 530) |
| Q04 | (20, 72, 131) | (20, 200, 636) | (20, 200, 481) |
| Q06 | (15, 72, 193) | (15, 150, 735) | (15, 150, 454) |
| Q07 | (15, 75, 293) | (15, 150, 820) | (15, 150, 760) |
| Q08 | (15, 104, 316) | (15, 150, 685) | (15, 150, 620) |
| Q09 | (15, 72, 146) | (15, 150, 701) | (15, 150, 523) |
| Q10 | (15, 82, 244) | (15, 150, 698) | (15, 150, 551) |

Tổng cộng 80 kế hoạch ngày được nhận, 12155 frame và 188902 giá trị đối chiếu, không có sai khác. Các điểm mới là điểm BTC; bảng offline phía trên chỉ là lịch sử thử nghiệm. Đội 57 là mốc tham khảo từ điểm máy chủ đã đọc, không biết thuật toán/ngân sách của họ. Đạt cận U và D không chứng minh tối ưu Q.

Bản tổng hợp: `experiments/tour_api_evidence/summary.json`. Script `experiments/verify_tour_server.py` có reset/nộp Practice riêng đội 62 và sao lưu lịch sử trước reset; không dùng như lệnh chỉ đọc. Replay và kế hoạch chi tiết giữ tại máy, bị Git ignore.
