# Luật và dữ liệu đã xác nhận

## Nguồn

- `Đề bài/2026_Procon_Problem VI.pdf`: luật chính thức, 6 trang.
- `Đề bài/giao diện chọn loại agent đầu game.png`: giao diện chọn loại và vị trí ban đầu.
- `Đề bài/giao diện nộp bài.png`: cách nhập lệnh mỗi ngày.
- `Đề bài/input_sample.json`, `Đề bài/output_sample.txt`: mẫu dữ liệu.

## Theo đề chính thức

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

## Bổ sung từ ảnh giao diện

- Mã loại xe: `0` = tuần tra, `1` = tiếp xăng.
- Vị trí xuất phát của từng xe được hiển thị trước khi chọn loại.
- Có thể gửi lại lựa chọn trong cửa sổ chọn loại.
- Nếu không chọn kịp, tất cả xe mặc định là tuần tra; vẫn được nộp kế hoạch mỗi ngày.
- Ảnh minh họa có 4 xe, lần lượt ở ô 558, 998, 130, 955.
  Đây là dữ liệu ví dụ, không phải cấu hình cố định.
- Mỗi xe có một mảng lệnh theo thứ tự xe: `0–5` là hướng đi, số âm là số bước chờ.
- Mỗi xe phải sử dụng đúng quỹ bước của ngày; ảnh nộp bài minh họa 228 bước.
- Chưa có mẫu payload gửi lựa chọn loại xe, dù ảnh đã xác nhận mã loại.

## Các điểm cần làm rõ trước khi nối máy chủ

- Ánh xạ mã địa hình trong `map.cells` và ánh xạ hướng `0–5`.
- Cấu trúc bản tin chứa vị trí xe, loại xe và trạng thái đầu mỗi ngày.
- Định dạng gửi lựa chọn loại xe và cách nhận trạng thái giao thông.
- Thứ tự chi tiết trong một step: trừ nhiên liệu, tiếp tế, đến ô và thu thập.
- Quy tắc khi nhiều xe cùng đến điểm có kho không đủ trong cùng step.
- Cách xử lý thu thập khi xe đã ở điểm đến ngay đầu ngày.

Mẫu JSON hiện có không chứa vị trí xuất phát của xe. Không tự gán các vị trí trong ảnh
cho mọi bản đồ. Những điểm chưa rõ sẽ được tách thành quy ước mô phỏng công khai,
không trình bày như luật đã được BTC xác nhận.
