# Đối chứng bỏ thành phần và phân tích nguyên nhân

Lượt đo này bổ sung cho các thí nghiệm deadline đã có, không thay thế chúng. Mục tiêu là tách tác dụng của phối hợp mục tiêu, nhìn trước hai điểm và lựa chọn vai trò khi cùng dùng một bộ điều khiển. Phần chính của báo cáo trình bày giao thức ở mục 5.5, kết quả ở mục 6.7 và ví dụ giải thích ở mục 6.8. Phần RL được giữ nguyên.

## Cách đo

Bản `experiments/ablation_planner.py` được sao chép từ planner chính, giữ cùng A*, sáu đích ứng viên, ba đích nhìn trước, quy tắc tiếp tế và tiêu chí chọn. Nó bỏ ngắt theo thời gian để có thể đối chiếu quyết định xác định. Chế độ không phối hợp đặt lại kho và các loại udon dự kiến trước mỗi xe, vẫn giữ trạng thái thật đầu ngày. Bộ điều khiển chính và giao diện chạy bài không bị sửa.

Các biến thể gồm G0 độc lập/toàn tuần tra; G1 phối hợp/toàn tuần tra; L1 Lookahead phối hợp/toàn tuần tra; S1 Greedy phối hợp/xe cuối tiếp tế; S* Greedy phối hợp/chọn trong toàn tuần tra và bốn cách có một xe tiếp tế. S* dùng năm lần mô phỏng hoàn tất; nó không có cùng tổng chi phí với một cấu hình cố định. Việc S* không kém S1 là hệ quả của việc S1 nằm trong tập ứng viên và cùng luật một đội, không phải một bảo đảm trong trận nhiều đội.

Tập sinh có ba seed 42000–42002 ở mỗi kích thước 8, 16, 32; mỗi trận bốn ngày, 80 step/ngày, nhiên liệu 40 và bốn xe. Hai input minh họa được tách khỏi tổng hợp chín bản đồ sinh. Có bảy trận thực thi trên mỗi input: G0, G1, L1 và bốn cách chọn một xe tiếp tế. Các dòng S1 và S* dùng lại kết quả tương ứng, không đếm thành thêm mẫu độc lập. Tổng cộng có 77 trận và 294 kế hoạch ngày, đều hợp lệ và không dùng dự phòng.

## Kết quả

| Thay đổi | Thắng | Hòa | Thua |
|---|---:|---:|---:|
| G1 so với G0 | 8 | 0 | 1 |
| L1 so với G1 | 3 | 1 | 5 |
| S1 so với G1 | 8 | 0 | 1 |
| S* so với S1 | 5 | 4 | 0 |

Các cặp dùng thứ tự từ điển (U,D,Q). Chín input chưa đủ để kết luận tổng quát. Lượt đo không dùng deadline, do đó không được dùng các thời gian ở đây để khẳng định mọi input đáp ứng 30 giây.

## Dữ liệu và tái hiện

```text
python -X utf8 experiments/benchmark_ablation.py
python -X utf8 experiments/audit_ablation.py
python -X utf8 experiments/analyze_ablation.py
python -X utf8 experiments/plot_ablation.py
```

Ba lệnh đầu chỉ dùng thư viện chuẩn; lệnh vẽ cần Matplotlib. Thư mục `experiments/ablation_results` giữ input, kế hoạch, điểm từng ngày, metadata và kiểm chứng chấm lại. Chạy benchmark sẽ ghi đè số liệu trong thư mục. Không lệnh nào gọi API BTC.

Chỉ số ghé kho rỗng được tính lại từ vị trí xe trong từng frame và tồn kho thật. Mã phân tích kiểm tra các sự kiện thu được hàng khớp replay trước khi tính chỉ số. Các ví dụ được chọn sau đo để minh họa cả hai chiều tăng/giảm điểm; chúng không thay thế bảng tổng hợp.

Hai kiểm thử mới đối chiếu bản sao với planner gốc khi đủ thời gian và kiểm tra trường hợp chia sẻ kho làm thay đổi kết quả. Tổng bộ kiểm thử tại thời điểm bổ sung là 54 phương thức; các con số 47/50/52 trong phần mô tả các đợt cũ là số tại từng thời điểm đó.
