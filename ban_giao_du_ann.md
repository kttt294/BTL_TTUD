# Bàn giao dự án HEXUDON – Procon 2026

## 1. Bối cảnh và mục tiêu

Đội đang giải bài tối ưu lộ trình HEXUDON của Procon Việt Nam 2026. Website BTC là https://hexudon.hairbui76.id.vn/ và cũng là nền tảng dự kiến dùng khi thi. Mục tiêu tiếp theo là cải thiện thành tích thi, không chỉ hoàn thiện báo cáo môn học. Nhánh `src_procon` được tạo từ `ttud_clean`; tại thời điểm bàn giao, workspace có nhiều thay đổi chưa commit, cần giữ nguyên.

Bản đồ lục giác có chiều rộng/cao từ 8 đến 32; xe xuất phát tại các vị trí cố định và được chọn vai trò tuần tra hoặc tiếp tế. Xe tuần tra ghé điểm bán để thu udon, xe tiếp tế hỗ trợ nhiên liệu. Quỹ step được cấp **riêng cho từng xe, từng ngày**; nhiên liệu còn lại được mang sang ngày sau. Chi phí di chuyển phụ thuộc địa hình và trạng thái đường, tính theo ô nguồn. Kho udon được bổ sung mỗi ngày.

Điểm được so theo thứ tự từ điển `(U, D, Q)`: số loại thu được toàn trận, tổng số loại thu được theo từng ngày, rồi tổng số suất. Không cộng ba thành phần thành một điểm. Số loại khác nhau và tổng kho trong config cho các cận trên, không bảo đảm có lộ trình đạt được chúng.

Output là một mảng lệnh cho mỗi xe: `0..5` chỉ hướng sang ô kề, số âm là chờ tương ứng số step. Một lần di chuyển có thể tốn nhiều step; mỗi xe phải dùng đủ quỹ ngày và không được bắt đầu di chuyển khi không đủ step.

## 2. Những hướng đã triển khai

| Thành phần | Cách làm hiện tại |
|---|---|
| **Planner tuyến (`tour`, mặc định khuyến nghị)** | `src/hexudon/tour.py`: chèn tham lam + phá/dựng lại cho cả đội, ba kiểu đường step/nhiên liệu, chia nhiên liệu theo tỷ lệ step còn lại khi không có tiếp tế, điểm hẹn tiếp tế chọn lại mỗi ngày. Chọn vai trò song song nhiều tiến trình. Xem `docs/tour_planner.md`. |
| Tìm đường | So sánh DFS, BFS, Dijkstra, Greedy Best-First và A*. Planner mặc định dùng A* trên trạng thái có step/nhiên liệu, giữ các nhãn tài nguyên không bị trội. |
| Greedy lập kế hoạch | Ưu tiên loại mới toàn trận, loại mới trong ngày, suất thu được, rồi đường ít step. Mỗi lượt sàng lọc tối đa 6 điểm theo độ mới và khoảng cách lục giác; chưa bù ứng viên thứ 7 nếu điểm trong top 6 không tới được. |
| Lookahead hai điểm | Xét điểm đầu và tối đa 3 điểm tiếp theo, đánh giá lợi ích cặp rồi thực hiện chặng đầu và tính lại. Tốn nhiều tìm đường hơn và chưa ổn định tốt hơn Greedy khi giới hạn thời gian. |
| Phối hợp xe | Chia sẻ kho dự kiến và các loại đã được phân công; xe tiếp tế đến điểm trung tâm rồi chờ. Đây là phối hợp heuristic đơn giản, chưa tối ưu lịch hẹn toàn cục. |
| Chọn đội hình | Thử một số cấu hình toàn tuần tra, một xe tiếp tế và một số cấu hình hai xe tiếp tế; dùng mô phỏng toàn trận để chọn. Vị trí xuất phát không được hoán đổi. |
| Simulator/validator | Mô phỏng thu udon, nhiên liệu, tiếp tế, step và giao thông; kiểm tra output trước khi gửi. Có engine nhiều đội nhưng phần nhiều đội chưa được kiểm chứng trên máy chủ. |
| Rollout | So kế hoạch ngày hiện tại bằng kết quả mô phỏng tiếp đến cuối trận. Giao thông tương lai dự đoán từ một đội; ngày thật luôn lấy lại từ BTC. |
| Nghiệm chính xác | Quy hoạch động cho bài thu nhỏ một xe, không đường/tiếp tế; làm mốc tối ưu để đánh giá heuristic, không giải nguyên bản 32×32. |

Greedy chọn **đích**, A* chọn **đường**; Greedy lập kế hoạch khác Greedy Best-First tìm đường. Luồng nộp hiện tại chưa dùng RL.

## 3. Kết quả và giới hạn bằng chứng

- **Planner `tour` (20/10/2026, offline một đội):** trên 8 config BTC đạt cận trên U và D, Q 597–837; cao hơn điểm BTC của đội 57 ở cả 8 bài (ví dụ Q01 597 so với 532, Q10 698 so với 551). Có cơ chế bảo vệ D ở ngày ngắn (phủ loại nhiều lần, ô neo cho ngày mai); cần ngân sách ≥ 5 giây/ngày. Bảng trong `docs/tour_planner.md`. Chưa nộp thử trên máy chủ.
- Nguyên nhân chính của bản cũ: Greedy tiêu hết nhiên liệu trong 3 ngày đầu; khi U, D đã tối đa thì Q quyết định thắng thua.

- Thí nghiệm offline ban đầu: 30 cặp toàn trận ở ngân sách 0,25 giây/ngày, Lookahead thắng 3 và thua 27 so với Greedy. Đây không phải kết luận cho mọi ngân sách hay mọi input.
- Bộ chọn đội hình tốt hơn toàn tuần tra ở 3/9 nhãn bài BTC chạy offline, bằng ở 6/9. Q01 và Q02 trùng cấu hình, không phải hai bản đồ độc lập.
- Hai cấu hình Q04/Q06 được đối chiếu máy chủ qua 2.807 frame; không phát hiện sai khác ở các giá trị kiểm tra. Đây là kiểm chứng hữu hạn, không phải chứng minh simulator đúng mọi trường hợp.
- Runner đã nộp thật đủ 10 ngày Practice `c57bfe4b-55ef-416f-893f-1ccaf86a8b87`, đội 62, toàn tuần tra, Greedy: máy chủ trả `(20, 101, 253)`. Đây là một lượt chạy, không phải kỷ lục tốt nhất của mọi thuật toán.
- Bộ dữ liệu Practice đã khảo sát có bản đồ 30×30/32×32; cần input tự sinh để thử thêm kích thước. Practice quan sát phù hợp mô hình một đội; chưa chứng minh đóng góp của đối thủ vào giao thông. Replay thấy đối thủ không đồng nghĩa họ ảnh hưởng lượt tự luyện của ta.
- Bộ kiểm thử tại lần chỉnh gần nhất có 80 test đạt. Luồng nộp trận tính giờ mới kiểm thử giả lập, chưa chạy trọn trận tính giờ thật.

## 4. RL đã làm và hướng RL/DL tiếp theo

Đã đánh giá checkpoint RL cũ của nhánh `Procon2026` và thử kết hợp RL với heuristic/rollout. Một số cải thiện của bản kết hợp đến từ heuristic được chọn thay RL, nên **không được ghi nhận toàn bộ là thành tích RL**.

Sau đó đã xây dựng PPO chọn điểm đích, với MLP hai tầng 64 nút, 18 đặc trưng/ứng viên và tối đa 65 hành động có padding/mask. Dijkstra thực thi đường đi cố định; không fallback sang Greedy/Lookahead khi chọn đích. Đã train 3 seed, mỗi seed 1.024 episode trên 48 bản đồ, bằng CPU. Policy argmax bị suy biến chọn chờ và đạt 0; policy lấy mẫu có tiến bộ so với chưa train nhưng chưa vượt đối chứng gần nhất ổn định. Trên 27 lượt official-label theo 3 seed, bản lấy mẫu đã train thắng/hòa/thua đối chứng gần nhất là 6/0/21. Chưa nộp policy RL thuần này lên máy chủ. Không kết luận RL tốt hơn baseline hiện tại.

Hướng đề xuất cho agent tiếp theo:

1. Giữ Greedy+A* làm baseline tái lập được; chia train/validation/test theo bản đồ, không chọn checkpoint bằng điểm test BTC.
2. Ưu tiên sửa RL chọn đích: phân tích hành động chờ, chuẩn hóa đặc trưng, reward và mask, đánh giá nhiều seed. Reward hiện tại `10ΔU + ΔD + 0,05ΔQ` chỉ xấp xỉ ưu tiên từ điển, chưa tương đương tuyệt đối.
3. Thử mô hình biểu diễn không gian tốt hơn MLP, như GNN trên đồ thị lục giác hoặc attention trên xe/điểm bán. So sánh với cùng ngân sách và cùng bộ thực thi đường đi.
4. Có thể thử imitation learning từ lời giải heuristic/DP để khởi tạo rồi fine-tune RL. Phải phân biệt số liệu imitation, RL và hybrid.
5. Nếu nghiên cứu RL tìm đường, tách thành thí nghiệm riêng: hành động hướng đi/chờ, quan sát tài nguyên và giao thông, so với A* cùng điều kiện. RL chọn đích chưa tốt không chứng minh rằng bắt buộc phải dùng RL tìm đường.
6. Có thể thử RL phân vai xe hoặc điều phối tiếp tế; đánh giá riêng từng thành phần trước khi gộp. Chỉ mở rộng huấn luyện nhiều đội sau khi simulator nhiều đội được kiểm chứng thêm.

Yêu cầu quan trọng: kết quả mang tên RL phải thật sự do policy đưa ra. Nếu dùng fallback, rollout hay chọn tốt nhất giữa RL và heuristic, phải ghi là hybrid và thống kê tỷ lệ từng nhánh được chọn.

## 5. Chạy và đọc code

```powershell
# Practice tự luyện; dùng rõ chế độ để tránh nhận diện nhầm đồng hồ 0.
python -X utf8 play_match.py --algorithm tour --mode practice ID_TRAN

# Chỉ đọc dữ liệu, không chọn xe/nộp bài.
python -X utf8 play_match.py --inspect --game-id ID_TRAN

# Kiểm thử cục bộ.
python -X utf8 -m unittest discover -s tests
```

Runner tự lấy config, chọn xe nếu cần, lấy trạng thái ngày và nộp tiếp. Không tự reset; checkpoint giữ khi bị ngắt và tự dọn sau khi đọc được kết quả cuối trận. Không chạy đồng thời hai client cho cùng đội/trận. Competitive Practice dùng timeline chung chưa được hỗ trợ. Trận tính giờ dùng `--mode timed` và cần kiểm chứng thật trước khi thi.

| File/thư mục | Nội dung cần đọc |
|---|---|
| `src/hexudon/planner.py`, `search.py` | Greedy/Lookahead, A* và các đối chứng tìm đường |
| `src/hexudon/team_selection.py` | Chọn vai trò bằng mô phỏng |
| `src/hexudon/model.py`, `simulator.py`, `bounds.py`, `exact.py` | Luật, engine, cận trên, DP thu nhỏ |
| `src/hexudon/live.py` | Điều khiển trận; gọi thuật toán và kiểm tra/nộp output |
| `src/hexudon/live_api.py`, `live_storage.py` | HTTP/token; checkpoint/khóa/tự dọn |
| `experiments/rl_policy.py`, `train_rl_policy.py`, `evaluate_rl_policy.py`, `audit_rl_policy.py` | Policy PPO, train, đánh giá và kiểm tra không fallback |
| `experiments/rl_policy_results/`, `docs/rl_policy_training.md` | Metadata, kết quả và phạm vi RL thuần |
| `experiments/rl_extension.py`, `docs/ablation_experiment.md` | Hybrid/rollout và thí nghiệm tách thành phần |
| `docs/rules.md`, `docs/simulation_conventions.md`, `docs/auto_submit.md` | Quy tắc và hướng dẫn vận hành |
| `docs/api/openapi.json` | Đặc tả API BTC đã lưu |
| `Đề bài/` | Đề chính thức tiếng Việt và tài liệu BTC |
| `output/docx/bao_cao_hexudon.docx` | Báo cáo môn học; RL ở phụ lục C |

API runner dùng: `GET /api/game/config`, `/state`, `/day`, `/result`; `POST /api/game/agent-types`, `/practice/actions` hoặc `/actions`. GET truyền `game_id` qua query; POST truyền trong JSON. `/day` cung cấp `agents` và `traffics` thật, dùng lại mỗi ngày thay dự báo. API replay là công cụ luyện tập/đối chiếu, không mặc định là input được phép dùng khi thi.

Token nằm trong `.env`, không đưa vào tài liệu/code/Git. Checkpoint mô hình và dữ liệu chạy lớn có thể bị Git ignore; cần kiểm tra sự tồn tại trước khi tái lập. Không ghi đè DOCX bằng builder nếu chưa kiểm tra vì có chỉnh sửa thủ công; hiện chỉ cập nhật DOCX khi được yêu cầu, không cần PDF.
