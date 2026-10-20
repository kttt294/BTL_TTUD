# Huấn luyện và đánh giá RL không chọn thay bằng heuristic

## Mục đích

Thí nghiệm này thay cách chọn ứng viên ở `rl_extension.py` bằng một chính sách PPO được huấn luyện từ đầu. Mỗi khi xe cần chọn đích mới, mạng chấm tất cả đích khả thi và hành động chờ. Khi đánh giá, hệ thống lấy hành động có xác suất lớn nhất. Hệ thống không so điểm với Greedy, không dùng Lookahead và không giữ kế hoạch Greedy dự phòng. Nếu kế hoạch không hợp lệ, phép đo dừng và báo lỗi, thay vì tự thay bài nộp.

Đây là **RL chọn mục tiêu kết hợp bộ tìm đường cố định**, không phải RL học từng hướng 0–5. Bộ thực thi dùng Dijkstra để xác định một đường ít step tới mỗi đích. Nó chỉ biến mục tiêu mạng chọn thành lệnh, cắt tiền tố liên tục khi hết quỹ ngày và thêm thời gian chờ còn thiếu. Mặt nạ loại đích nếu đường cố định vượt nhiên liệu còn lại. Nó có thể loại một đích mà một đường khác ít nhiên liệu hơn vẫn tới được; thí nghiệm không tuyên bố bộ thực thi đã xét mọi đường khả thi. Những hạn chế này được áp dụng như nhau cho tất cả đối chứng.

## Học và phân chia dữ liệu

- Mạng chia sẻ cho mọi xe: 18 đặc trưng cho mỗi ứng viên, hai tầng 64 nút Tanh, actor chấm từng ứng viên và critic lấy trung bình biểu diễn ứng viên hợp lệ.
- Hành động gồm tất cả điểm còn hàng, chưa được xe thăm trong ngày, có đường cố định phù hợp nhiên liệu, cùng một hành động chờ. Không cắt danh sách theo điểm Greedy.
- Huấn luyện từ khởi tạo ngẫu nhiên với ba seed 71, 72, 73. Không dùng checkpoint cũ, nhãn Greedy hoặc học bắt chước.
- Tập học có 48 bản đồ sinh trước, seed 61000–61047, kích thước 8, 12, 16 luân phiên; mỗi trận sáu ngày, 80 step/ngày, nhiên liệu 100, toàn xe tuần tra.
- Reward tại cuối ngày lấy từ **simulator TTUD thực thi cả đội**, bằng `10 ΔU + ΔD + 0,05 ΔQ`. Phép đặt chỗ tạm khi tạo tuyến không trực tiếp tạo reward. Tổng có trọng số này là mục tiêu học gần đúng, không tương đương thứ tự từ điển trong mọi trường hợp.
- PPO dùng learning rate 0,0003; gamma 0,99; GAE lambda 0,95; clip 0,2; bốn lượt cập nhật mỗi nhóm tám trận; minibatch 256; entropy 0,01; hệ số value loss 0,001; giới hạn norm gradient 0,5.
- Lưu checkpoint sau đúng số trận quy định. Không chọn checkpoint hoặc seed tốt nhất theo điểm chín bài BTC. Báo cáo đủ cả ba seed.
- Tập kiểm tra gồm các cấu hình BTC đã lưu và bản đồ sinh riêng có seed 91000 trở đi ở kích thước 8, 16, 32. Bản đồ kiểm tra 32×32 và bản đồ BTC khác phân phối kích thước/horizon của tập học. Q01/Q02 trùng cấu hình nên không được xem là hai mẫu độc lập.

## Đối chứng

Tất cả biến thể dùng cùng Dijkstra, mặt nạ, quy tắc đặt chỗ và mã mô phỏng:

1. `trained`: trọng số sau PPO, chọn argmax, không chọn theo điểm rollout.
2. `untrained`: cùng mạng tại thời điểm khởi tạo trước PPO, chọn argmax.
3. `random`: chọn đều trong các ứng viên hợp lệ và chờ, không dùng mạng.
4. `nearest`: luôn chọn đích gần nhất theo step trong bộ thực thi. Đây là một đối chứng riêng, không được gọi từ `trained`.
5. `trained_sampled` và `untrained_sampled`: lấy đúng một mẫu cho mỗi quyết định từ phân phối tương ứng sau/trước học, cùng seed đo. Không lấy nhiều kế hoạch rồi chọn điểm cao nhất. Hai biến thể này được bổ sung sau khi chẩn đoán argmax chọn chờ trên Q04 và bản đồ sinh 8×8 seed 91000; không thay đổi quá trình học hoặc chọn checkpoint theo điểm chẩn đoán. Đây là phân tích bổ sung sau quan sát, không phải giao thức hoàn toàn định trước.

Điểm số của cả bốn biến thể đều được tính bằng thực thi và chấm lại toàn bộ kế hoạch. Điều kiện `fallback_calls=0` có ý nghĩa đi cùng cấu trúc mã: đường thực thi không nhập hay gọi planner Greedy/Lookahead. Đối chứng mạng ban đầu giúp đo hiệu quả huấn luyện; đối chứng ngẫu nhiên và gần nhất giúp đánh giá chính sách trong cùng không gian hành động. Kết quả này không chứng minh mạng tự học tìm đường.

## Tái hiện

```text
python -X utf8 experiments/train_rl_policy.py --episodes 1024 --seeds 71 72 73
python -X utf8 experiments/evaluate_rl_policy.py
python -X utf8 -m unittest discover -s tests
```

PyTorch là phụ thuộc tùy chọn cho phần mở rộng, không phải yêu cầu của thuật toán lõi. CPU được đặt một luồng để giảm nhiễu. Không cần gửi dữ liệu hay thông tin đăng nhập Kaggle nếu phép đo tốc độ cho thấy CPU đủ phù hợp. Checkpoint và kế hoạch chi tiết chỉ lưu tại máy; metadata và bảng tổng hợp được giữ trong repository. Máy chủ BTC không được dùng trong vòng huấn luyện. Những điểm chưa nộp máy chủ phải được ghi rõ là điểm simulator offline.

Nguồn phương pháp PPO: Schulman và cộng sự (2017), *Proximal Policy Optimization Algorithms*, https://arxiv.org/abs/1707.06347. Simulator và bộ sinh bản đồ là mã của nhóm, không phải thư viện chấm chính thức của BTC.
