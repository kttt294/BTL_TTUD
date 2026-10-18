# Đặc tả simulator và phạm vi đã kiểm chứng

## Cơ sở và ngày xác minh

Bản simulator này được điều chỉnh bằng replay từ API BTC ngày 19/10/2026.
Nguồn chính thức và cách kiểm tra thủ công nằm trong `api_manual_check.md`.
Kết quả theo từng bộ replay nằm trong `api_validation_results.md`.
Các mô tả dưới đây tách hành vi đã quan sát với trường hợp mới chỉ có kiểm thử nội bộ.

## Thứ tự trong một step

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

## Giao thông và hành vi biên

Simulator cộng lịch sử hai ngày của mọi đội, chia số đội và áp dụng ngưỡng đông đúc/ùn tắc.
Giao thông cố định trong ngày. Hàm một đội dùng cùng engine, với mẫu số bằng 1.

Thông thường, simulator đếm theo vị trí hiển thị sau mỗi step. Tuy nhiên, API có hành vi biên:
khoảng chuyển tiếp rời vị trí đầu ngày trên đường không được đếm như khi xe đã đến một ô
trong ngày. Chờ tại vị trí đầu ngày vẫn được đếm. Sau lần hoàn thành di chuyển đầu tiên,
những khoảng chuyển tiếp sau được tính theo vị trí hiển thị.

Hai biến thể Q10 và ca Q02 xác minh khác biệt này. Biến `arrived_today` mô hình hóa hành vi
đã quan sát. Đây là một quy tắc tương thích máy chủ tại thời điểm thử, không phải điều luật
được tự bổ sung vào đề chính thức. Nếu BTC sửa engine, cần chạy lại đối chiếu trước khi cập nhật.

## Kho, thu thập và nhiều đội

Mỗi đội có kho riêng, bổ sung đầu ngày. Mỗi xe chỉ thu tối đa một phần tại mỗi điểm mỗi ngày.
Nếu kho không đủ khi nhiều xe cùng đến, simulator ưu tiên chỉ số xe nhỏ hơn.
Thứ tự ưu tiên này mới được kiểm thử nội bộ; các bản mẫu đã thử chưa tạo thiếu kho cùng lúc.

`simulate_match_day` dùng timeline chung, kho riêng và tiếp tế trong cùng đội.
Các phép thử về nhiều đội được tính tay, chưa được so với replay BTC nhiều đội.
Nếu một kế hoạch sai, hàm trả lỗi và không sửa bất kỳ trạng thái đầu vào nào. Đây là cơ chế
kiểm tra giao dịch của thư viện; lớp điều phối chịu trách nhiệm thay kế hoạch lỗi bằng chờ nếu cần.

## Mức độ tin cậy

Sáu tập đối chiếu có 6.331 frame và 97.345 giá trị được kiểm tra với 0 sai khác ở bản cuối.
Hai biến thể Q10 trùng ngày đầu nên không được xem mọi frame là mẫu độc lập.
Không được dùng kết quả này để khẳng định tương đương tuyệt đối trên tất cả cấu hình.

## Giới hạn của chiến lược

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
