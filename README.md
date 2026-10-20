# Bài tập lớn Thuật toán ứng dụng

## Tối ưu hóa lập kế hoạch đa tác tử trên bản đồ lục giác có ràng buộc tài nguyên

Đề tài được xây dựng từ bài toán **HEXUDON** của cuộc thi Procon Việt Nam 2026. Nhóm nghiên cứu và so sánh các thuật toán tìm đường, đồng thời xây dựng phương pháp lập kế hoạch cho đội xe thu thập udon trong giới hạn thời gian và nhiên liệu.

**Giảng viên hướng dẫn:** TS. Trần Đình Tân

**Sinh viên thực hiện:** Kiều Thị Thu Trang - 24100093; Trần Minh Sang - 24100012.

[Báo cáo đầy đủ (DOCX)](bao_cao_hexudon.docx) · [Đề bài và dữ liệu mẫu](Đề%20bài/) · [Kết quả được Ban tổ chức chấm](docs/huong_dan.md#ket-qua)

## Nội dung chính

- So sánh DFS, BFS, Greedy Best-First, Dijkstra và A* trên bài toán tìm đường có ràng buộc tài nguyên.
- Lập tuyến cho đội xe bằng Dijkstra, chèn tham lam và tìm kiếm cục bộ; phối hợp tiếp tế và lựa chọn vai trò xe.
- Xây dựng bộ mô phỏng, bộ kiểm tra kế hoạch và công cụ lấy đề, nộp bài qua API của Ban tổ chức.

Phương pháp đã được chấm trên **8 bản đồ Practice**, đều đạt cận trên về số loại udon toàn trận và tổng số loại theo ngày. Bộ mô phỏng được đối chiếu qua **12.155 khung trạng thái**, không phát hiện sai khác ở các trường kiểm tra. Số suất thu thập chưa được chứng minh tối ưu. Thí nghiệm học tăng cường được trình bày riêng trong phụ lục C của báo cáo.

## Hướng dẫn chạy

Chương trình yêu cầu **Python 3.10 trở lên**. Phần thuật toán truyền thống sử dụng thư viện chuẩn; PyTorch chỉ cần cho thí nghiệm học tăng cường. Chạy các lệnh tại thư mục gốc dự án:

```powershell
# Chạy thử trên bản đồ sinh tự động, không cần kết nối website
python -X utf8 src/main.py demo --size 8 --strategy tour --seconds 2

# Chạy bộ kiểm thử
python -X utf8 -m unittest discover -s tests -v
```

Để nộp Practice trên [website Ban tổ chức](https://hexudon.hairbui76.id.vn/), tạo file `.env` chứa `HEXUDON_TOKEN=token_cua_tai_khoan`, sau đó chạy:

```powershell
python -X utf8 play_match.py --algorithm tour --mode practice ID_TRAN
```

Script tự chọn vai trò khi cần, lấy trạng thái thực tế và nộp kế hoạch từng ngày. Dùng `--inspect` để chỉ xem trạng thái trận. Hướng dẫn chi tiết nằm tại [tài liệu hướng dẫn](docs/huong_dan.md#su-dung).

## Cấu trúc dự án

| Thư mục | Nội dung |
|---|---|
| `src/hexudon/` | Mô hình bài toán, thuật toán, bộ mô phỏng và kết nối API |
| `tests/` | Kiểm thử thuật toán và quy tắc trò chơi |
| `experiments/` | Các nhóm `benchmark/`, `api/`, `rl/` và dữ liệu trong `data/`; chạy qua `run.py` |
| `docs/` | Đặc tả, hướng dẫn sử dụng và kiểm chứng kết quả |
| `Đề bài/` | Đề bài gốc và input/output mẫu |
| `bao_cao_hexudon.docx` | Báo cáo bài tập lớn |

Bộ đối chứng bổ sung cho `tour` có thể được kiểm tra bằng `python -X utf8 experiments/run.py tour_study --audit-only`. Xem [hướng dẫn thực nghiệm](docs/huong_dan.md#thuc-nghiem-tour).

Đánh giá trên 30 bản đồ tự sinh và tách thành phần ở hai ngân sách: [dữ liệu và cách tái hiện](docs/huong_dan.md#do-ben-vung). Greedy được giữ làm đối chứng offline; luồng nộp bài chỉ sử dụng `tour`.
