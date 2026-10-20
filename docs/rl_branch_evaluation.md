# Thử nghiệm checkpoint RL của nhánh Procon2026

Thí nghiệm này được thực hiện sau khi lấy bản mới nhất của nhánh `Procon2026` từ GitHub vào ngày 19/10/2026. Bản được đánh giá là commit `b6df084c253503b5673721c126ff261430cd0021`. Checkpoint được lấy cùng nhánh có đường dẫn `runs/pilot_reserved_001/seed_20042/episode_256.pt`. Mã nhánh `ttud_clean` và bằng chứng của lượt Greedy/Lookahead trước đó được giữ lại.

## Phương pháp

Chương trình nạp checkpoint bằng phương thức `MAPPOTrainer.load` của nhánh, chuyển mô hình sang chế độ đánh giá và chọn hành động xác định. RL chọn điểm đích cho từng xe tuần tra, còn A* và bộ tạo đường đi của nhánh chuyển lựa chọn đó thành lệnh di chuyển. Các tùy chọn masking, tuyến phụ và giữ chỗ tồn kho được lấy từ chính checkpoint, không tự bật hoặc tắt để cải thiện điểm. Tệp `model_metadata.json` lưu cấu hình được nạp, số episode và mã SHA-256 của checkpoint.

Thí nghiệm giữ cơ chế lựa chọn ứng viên trong `run_play` của nhánh: Greedy tạo phương án cơ sở, sau đó phương án RL chỉ được chọn khi hợp lệ và có bộ điểm dự đoán tốt hơn theo simulator của nhánh. Vì vậy, kết quả phải được gọi là **RL kết hợp Greedy và bộ chọn theo điểm dự đoán**, không phải điểm RL thuần. Nhật ký lưu cả đích do RL chọn, ứng viên RL và phương pháp thực sự được nộp trong từng ngày. Nếu RL không được chọn trong một ngày thì điểm ngày đó không được quy hoàn toàn cho RL.

Adapter `experiments/evaluate_legacy_branch.py --rl` chuyển cấu trúc API Việt Nam sang cấu trúc dữ liệu của nhánh. Adapter lấy vị trí, nhiên liệu, giao thông và lịch sử thu thập từ máy chủ vào mỗi ngày. Các thuật toán của nhánh được nhập trực tiếp từ bản chụp tại commit nói trên. Adapter nộp một phương án cuối cùng cho mỗi ngày, thay vì nộp Greedy tạm thời rồi nộp cải thiện như client mạng gốc. Toàn bộ xe được chọn là xe tuần tra theo mặc định của `run_play`; thí nghiệm không tối ưu lại cách chọn loại xe.

Mỗi ngày có ngân sách lập kế hoạch danh nghĩa 30 giây. Thời gian tính toán được lưu riêng và không bao gồm truyền mạng hoặc tải replay. Chế độ luyện tập không xác nhận khả năng đáp ứng hạn nộp trong trận thi thật. Nếu xảy ra lỗi RL, adapter ghi lỗi và dừng bài tương ứng, không âm thầm báo điểm fallback là điểm RL.

## Nguồn kết quả và kiểm chứng

Chương trình nộp vào trận luyện tập riêng của đội 62 qua API BTC. Điểm được đọc trực tiếp từ `/api/game/result`, gồm số loại udon toàn trận, tổng số loại theo ngày và tổng số suất. Thứ tự ưu tiên này được giữ nguyên khi so sánh; chúng ta không cộng ba thành phần thành một điểm tùy ý. Thư mục `experiments/rl_branch_evidence` lưu config, kế hoạch trước/sau, phản hồi nộp bài, replay, trạng thái cuối và kết quả máy chủ. Thí nghiệm không lấy điểm mô phỏng nội bộ làm kết quả chính thức.

Website hiện hiển thị chín bài Q01, Q02, Q03, Q04, Q06, Q07, Q08, Q09 và Q10; Q05 không có trong danh sách quan sát được. Q01 và Q02 có config giống hệt nhau, do đó chúng không đại diện cho hai input độc lập. Mỗi tệp `Qxx_output.txt` gồm mười dòng tương ứng mười ngày. API nhận từng ngày riêng kèm chỉ số ngày; tệp này là bản lưu toàn trận, không phải một yêu cầu nộp duy nhất.

Giảng viên có thể kiểm tra các phản hồi JSON đã lưu hoặc truy cập các nguồn của BTC bằng tài khoản có quyền:

- Danh sách Practice Match: https://hexudon.hairbui76.id.vn/tournament/1/round/1/match/11/questions
- Tài liệu API: https://hexudon.hairbui76.id.vn/docs
- Đặc tả API: https://hexudon.hairbui76.id.vn/openapi.json

Các API được sử dụng gồm `/api/game/config`, `/api/game/day`, `/api/game/agent-types`, `/api/game/practice/reset`, `/api/game/practice/actions`, `/api/game/actions`, `/api/game/replay`, `/api/game/state` và `/api/game/result`. Bằng chứng không chứa token xác thực.

## Kết quả máy chủ

| Bài | Loại toàn trận | Tổng loại theo ngày | Tổng suất |
|---|---:|---:|---:|
| Q01 | 20 | 57 | 167 |
| Q02 | 20 | 57 | 167 |
| Q03 | 19 | 59 | 121 |
| Q04 | 15 | 42 | 96 |
| Q05 | Không có trong danh sách | — | — |
| Q06 | 15 | 55 | 143 |
| Q07 | 15 | 61 | 236 |
| Q08 | 15 | 61 | 215 |
| Q09 | 14 | 47 | 129 |
| Q10 | 15 | 64 | 192 |

Máy chủ đã nhận và lưu đúng 90 kế hoạch ngày. Thời gian lập kế hoạch lớn nhất: 2.250 giây, không gồm truyền mạng.

## So sánh với lượt Greedy/Lookahead trước đó

| Bài | Greedy/Lookahead | RL kết hợp Greedy | So sánh |
|---|---|---|---|
| Q01 | (20, 92, 245) | (20, 57, 167) | Kém hơn |
| Q02 | (20, 92, 245) | (20, 57, 167) | Kém hơn |
| Q03 | (20, 67, 132) | (19, 59, 121) | Kém hơn |
| Q04 | (20, 70, 145) | (15, 42, 96) | Kém hơn |
| Q06 | (15, 75, 189) | (15, 55, 143) | Kém hơn |
| Q07 | (15, 71, 344) | (15, 61, 236) | Kém hơn |
| Q08 | (15, 101, 308) | (15, 61, 215) | Kém hơn |
| Q09 | (15, 85, 201) | (14, 47, 129) | Kém hơn |
| Q10 | (15, 92, 266) | (15, 64, 192) | Kém hơn |

Trong 90 ngày, mô hình đã tạo 90 ứng viên; bộ chọn đã dùng RL cho 43 ngày. Các ngày còn lại dùng Greedy.

Theo thứ tự ưu tiên ba thành phần điểm, lượt RL kết hợp Greedy tốt hơn ở 0 bài, kém hơn ở 9 bài và bằng nhau ở 0 bài. Thống kê này bao gồm hai nhãn Q01/Q02 có input trùng nhau. Đây là so sánh hai cấu hình hoàn chỉnh, không tách riêng tác động của chính sách RL và các heuristic hỗ trợ.
