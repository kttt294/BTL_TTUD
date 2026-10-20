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

## Chọn vai trò

`select_types(..., strategy="tour")` mô phỏng các đội hình song song bằng nhiều tiến trình
(`select_types_parallel`), sàng lọc với ngân sách nhỏ rồi đánh giá lại tối đa bốn đội hình tốt
nhất. Nếu bản đồ quá lớn để chạy hết trận trong hạn, chọn theo số ngày đã mô phỏng rồi điểm.
`play_match.py --algorithm tour` mặc định dành 20 giây cho bước này.

## Kết quả offline (20/10/2026)

`experiments/compare_pipeline.py`, mô phỏng một đội, máy 16 nhân. Bản cũ: chọn vai trò bằng
Greedy 8 giây + Greedy. Bản mới: chọn vai trò bằng `tour` 20 giây + `tour` 5 giây/ngày.

| Case | Bản cũ (U, D, Q) | Bản mới (U, D, Q) | Đội hình mới | Cận (U, D, Q) theo đội hình mới |
|---|---|---|---|---|
| Q01 | (20, 101, 253) | (20, 200, 614) | 1 tiếp tế | (20, 200, 960) |
| Q03 | (20, 84, 137) | (20, 200, 675) | 1 tiếp tế | (20, 200, 1280) |
| Q04 | (20, 200, 518) | (20, 200, 641) | 1 tiếp tế | (20, 200, 900) |
| Q06 | (15, 72, 193) | (15, 150, 743) | 1 tiếp tế | (15, 150, 1500) |
| Q07 | (15, 75, 293) | (15, 150, 846) | 1 tiếp tế | (15, 150, 1200) |
| Q08 | (15, 104, 316) | (15, 150, 684) | 1 tiếp tế | (15, 150, 1200) |
| Q09 | (15, 72, 146) | (15, 150, 695) | 1 tiếp tế | (15, 150, 1200) |
| Q10 | (15, 82, 244) | (15, 149, 704) | 1 tiếp tế | (15, 150, 1200) |
| generated_8_2026 | (8, 32, 163) | (8, 32, 164) | 1 tiếp tế | (8, 32, 164) |
| generated_16_2026 | (12, 48, 145) | (12, 48, 173) | 1 tiếp tế | (12, 48, 228) |
| generated_32_2026 | (12, 45, 64) | (12, 48, 78) | 2 tiếp tế | (12, 48, 164) |
| generated_8_2027 | (8, 32, 155) | (8, 32, 156) | 1 tiếp tế | (8, 32, 156) |
| generated_16_2027 | (12, 48, 129) | (12, 48, 175) | 1 tiếp tế | (12, 48, 200) |
| generated_32_2027 | (12, 45, 65) | (12, 48, 65) | 2 tiếp tế | (12, 48, 152) |

Bản mới thắng cả 14 trường hợp theo thứ tự từ điển; không có lần nào phải dùng Greedy dự phòng.
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
