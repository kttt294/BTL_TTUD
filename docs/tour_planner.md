# Planner tuyến cả đội (`--algorithm tour`)

Mã nguồn: `src/hexudon/tour.py`. Gọi qua `plan_day(..., strategy="tour")`, `play_match.py --algorithm tour`
hoặc `src/main.py ... --strategy tour`. Chỉ dùng thư viện chuẩn, không dùng RL.

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


## Kết quả đã kiểm chứng

Xem [bảng điểm BTC](tour_server_results.md). Giới hạn U và D đã đạt trên tám bài Practice; Q chưa được chứng minh tối ưu.
