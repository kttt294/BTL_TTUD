# Bài tập lớn Thuật toán ứng dụng — HEXUDON

Đề tài nghiên cứu các thuật toán tìm đường và lập kế hoạch đội xe trên bản đồ lục giác của Procon Việt Nam 2026. Báo cáo chính thức: [bao_cao_hexudon.docx](output/docx/bao_cao_hexudon.docx).

## Chạy chương trình

Python 3.10 trở lên; thuật toán truyền thống chỉ dùng thư viện chuẩn. Không cần cài gói ngoài. Các lệnh dưới đây chạy tại thư mục gốc repo.

```powershell
python -X utf8 src/main.py --help
python -X utf8 play_match.py --help
python -X utf8 -m unittest discover -s tests -v
```

Để lấy đề và nộp tự động, tạo `.env` chứa `HEXUDON_TOKEN=token_cua_tai_khoan`. Token lấy từ nút sao chép token trên website BTC sau khi đăng nhập. Không đưa `.env` lên GitHub.

```powershell
python -X utf8 play_match.py --inspect --game-id ID_TRAN
python -X utf8 play_match.py --algorithm tour --mode practice ID_TRAN
```

Lệnh `--inspect` chỉ đọc. Lệnh thứ hai chọn vai trò nếu trận đang chờ chọn xe, sau đó lấy trạng thái đường/vị trí/nhiên liệu thật và nộp kế hoạch từng ngày; trận đang chơi được tiếp tục từ ngày máy chủ hiện tại. Script không tự reset trận đã kết thúc. Dùng ID Practice của chính tài khoản đăng nhập. Luồng trận tính giờ dùng `--mode timed`, chưa được kiểm chứng trong cuộc thi thật. Xem [hướng dẫn nộp bài](docs/auto_submit.md).

Các lựa chọn `--algorithm`: `tour` (khuyến nghị), `greedy`, `lookahead`. Phần nộp bài này không dùng RL. `-X utf8` giúp hiển thị tiếng Việt nhất quán trên Windows.

## Nội dung để kiểm tra bài

| Thành phần | Vị trí | Mục đích |
|---|---|---|
| Báo cáo hoàn chỉnh | `output/docx/bao_cao_hexudon.docx` | Trình bày bài toán, thuật toán, kết quả và giới hạn |
| Đề bài, input/output mẫu | `Đề bài/` | Đối chiếu quy tắc BTC |
| Mô hình và năm thuật toán tìm đường | `src/hexudon/model.py`, `search.py` | DFS, BFS, Greedy Best-First, Dijkstra, A* |
| Lập kế hoạch, chọn vai trò | `tour.py`, `planner.py`, `team_selection.py` trong `src/hexudon/` | Phối hợp đội xe, nhiên liệu và quỹ bước |
| Bộ mô phỏng và kiểm tra | `src/hexudon/simulator.py`, `tests/` | Kiểm tra kế hoạch và quy tắc chuyển trạng thái |
| Tự động lấy đề/nộp bài | `play_match.py`, `src/hexudon/live*.py` | Kết nối website BTC |
| Kết quả BTC hiện tại | `experiments/tour_api_evidence/summary.json` | Điểm, thời gian, đội hình và sai khác replay của 8 bài |
| Đặc tả API | `docs/api/openapi.json` | Kiểm tra request/response |
| Hướng dẫn kiểm chứng thủ công | `docs/api_manual_check.md` | Xem điểm và replay trên website |
| Thực nghiệm tìm đường | `experiments/benchmark.py`, `experiments/results/` | Chạy lại phép đo và xem số liệu gốc |
| RL trong phụ lục C | `experiments/rl_policy.py`, `train_rl_policy.py`, `evaluate_rl_policy.py` | Thí nghiệm mở rộng, cần PyTorch |

## Kết quả chính

Tour đã được BTC chấm trên 8 bản đồ Practice khác nhau: cả 8 bài đạt cận số loại toàn trận U và tổng số loại theo ngày D. Đối chiếu 12.155 khung trạng thái, 188.902 giá trị không phát hiện sai khác ở các trường được kiểm tra. Kết quả này chưa chứng minh tối ưu số suất Q hoặc đầy đủ mọi tình huống nhiều đội. Bảng điểm và điều kiện đo nằm trong [kết quả BTC](docs/tour_server_results.md).

```powershell
python -X utf8 experiments/benchmark.py --games 10 --sizes 8 16 32 --seconds 0.25
python -X utf8 experiments/summarize.py
```

Benchmark còn xuất các phép đo đối chứng Greedy/Lookahead; báo cáo chính sử dụng bảng tìm đường và bảng tour được BTC chấm. Các điểm offline không được coi là điểm máy chủ. Chạy lại có thể ghi đè số liệu benchmark; kết quả phụ thuộc máy và ngân sách thời gian.

`experiments/verify_tour_server.py` là công cụ tái hiện phép kiểm chứng, **có reset và nộp Practice riêng đội 62**; không chạy nếu chỉ muốn xem bảng điểm. Công cụ cần danh sách ID tại máy ở `docs/api/sample_games.json` và token hợp lệ. Các bản tổng hợp đã được đưa vào repo; phản hồi API, checkpoint và kế hoạch từng ngày không đưa lên GitHub.

## Phụ lục RL

```powershell
python -X utf8 experiments/train_rl_policy.py --episodes 1024 --seeds 71 72 73
python -X utf8 experiments/evaluate_rl_policy.py
```

Các lệnh RL cần PyTorch, cấu hình thử nghiệm và checkpoint tương ứng. Hướng dẫn đầy đủ ở [docs/rl_policy_training.md](docs/rl_policy_training.md). Dữ liệu tổng hợp phục vụ đối chiếu phụ lục được giữ; các thí nghiệm lai lịch sử cần snapshot và checkpoint ngoài repo theo mô tả trong báo cáo. Không cần các phụ thuộc RL để chạy thuật toán truyền thống hoặc nộp bài.
