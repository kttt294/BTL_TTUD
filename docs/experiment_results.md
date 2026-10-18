# Kết quả thực nghiệm

Thí nghiệm chạy trên Python 3.12.6, Windows-11-10.0.26200-SP0.
Bộ dữ liệu có 10 bản đồ cho mỗi kích thước, seed từ 2026, mỗi bản đồ có ba truy vấn tìm đường.
Ngân sách mỗi truy vấn và mỗi ngày lập kế hoạch là 0.25 giây.

## Tìm đường

| Cỡ | Thuật toán | Thành công | Dừng do hạn giờ | Thời gian TB ms | Trạng thái TB |
|---|---|---:|---:|---:|---:|
| 8 | dfs | 30/30 | 0 | 3.221 | 119.4 |
| 8 | bfs | 30/30 | 0 | 0.756 | 32.6 |
| 8 | dijkstra | 30/30 | 0 | 0.950 | 31.3 |
| 8 | greedy | 30/30 | 0 | 0.160 | 5.2 |
| 8 | astar | 30/30 | 0 | 0.598 | 18.4 |
| 16 | dfs | 28/30 | 2 | 37.958 | 1621.1 |
| 16 | bfs | 30/30 | 0 | 4.060 | 178.8 |
| 16 | dijkstra | 30/30 | 0 | 4.933 | 171.4 |
| 16 | greedy | 30/30 | 0 | 0.321 | 10.5 |
| 16 | astar | 30/30 | 0 | 2.447 | 86.6 |
| 32 | dfs | 20/30 | 10 | 129.034 | 5695.4 |
| 32 | bfs | 29/30 | 0 | 29.506 | 1151.0 |
| 32 | dijkstra | 29/30 | 0 | 29.667 | 971.0 |
| 32 | greedy | 29/30 | 1 | 9.277 | 322.8 |
| 32 | astar | 29/30 | 0 | 12.689 | 412.0 |

### Chi phí trên cùng truy vấn thành công

Bảng sau chỉ giữ truy vấn mà cả năm thuật toán đều tìm được đường trong hạn giờ.

| Cỡ | Số truy vấn chung | Thuật toán | Bước TB | Nhiên liệu TB | Số cạnh TB |
|---|---:|---|---:|---:|---:|
| 8 | 30 | dfs | 24.93 | 15.87 | 11.57 |
| 8 | 30 | bfs | 8.37 | 5.27 | 4.07 |
| 8 | 30 | dijkstra | 8.10 | 5.50 | 4.17 |
| 8 | 30 | greedy | 8.97 | 5.57 | 4.10 |
| 8 | 30 | astar | 8.10 | 5.50 | 4.17 |
| 16 | 28 | dfs | 59.21 | 36.18 | 26.79 |
| 16 | 28 | bfs | 19.64 | 12.11 | 9.43 |
| 16 | 28 | dijkstra | 18.79 | 12.57 | 9.75 |
| 16 | 28 | greedy | 21.89 | 13.61 | 9.71 |
| 16 | 28 | astar | 18.79 | 12.57 | 9.75 |
| 32 | 20 | dfs | 59.90 | 37.40 | 28.15 |
| 32 | 20 | bfs | 30.15 | 19.15 | 14.70 |
| 32 | 20 | dijkstra | 28.50 | 20.30 | 14.90 |
| 32 | 20 | greedy | 33.45 | 21.70 | 15.35 |
| 32 | 20 | astar | 28.50 | 20.30 | 14.90 |

## Kế hoạch toàn trận

Mỗi trận có bốn ngày, 80 step/ngày, nhiên liệu tối đa 40 và đội hình [0,0,0,1].

| Cỡ | Chiến lược | Loại toàn trận TB | Tổng loại ngày TB | Tổng phần TB | Thời gian trận TB s | Hợp lệ | Dự phòng |
|---|---|---:|---:|---:|---:|---:|---:|
| 8 | greedy | 8.00 | 32.00 | 138.70 | 0.527 | 10/10 | 0 |
| 8 | lookahead | 8.00 | 32.00 | 112.90 | 0.933 | 10/10 | 0 |
| 16 | greedy | 12.00 | 47.90 | 97.60 | 1.006 | 10/10 | 0 |
| 16 | lookahead | 12.00 | 44.70 | 57.00 | 1.006 | 10/10 | 0 |
| 32 | greedy | 10.40 | 23.60 | 24.20 | 1.007 | 10/10 | 0 |
| 32 | lookahead | 10.40 | 21.20 | 21.70 | 1.008 | 10/10 | 0 |

### So sánh theo cặp seed

Thắng/hòa/thua của Lookahead được tính theo bộ ba điểm, không theo riêng tổng phần.

| Cỡ | Lookahead thắng | Hòa | Lookahead thua |
|---|---:|---:|---:|
| 8 | 0 | 0 | 10 |
| 16 | 0 | 0 | 10 |
| 32 | 3 | 0 | 7 |

## Thời gian bộ kiểm tra

| Cỡ | Số kế hoạch | Trung vị ms | Lớn nhất ms | Hợp lệ |
|---|---:|---:|---:|---:|
| 8 | 80 | 1.154 | 2.806 | 80/80 |
| 16 | 80 | 1.144 | 4.039 | 80/80 |
| 32 | 80 | 1.495 | 3.135 | 80/80 |

### Phép đo bổ sung trên bản đồ 32×32

Mỗi cấu hình lặp 30 lần với kế hoạch chờ toàn ngày; phép đo này không đại diện mọi lộ trình.

| Số xe | Step/ngày | Trung vị ms | Lớn nhất ms |
|---|---:|---:|---:|
| 4 | 80 | 1.046 | 2.461 |
| 4 | 255 | 1.756 | 3.546 |
| 4 | 1000 | 6.605 | 13.438 |
| 8 | 80 | 1.916 | 2.632 |
| 8 | 255 | 3.032 | 4.746 |
| 8 | 1000 | 11.183 | 16.892 |

## Giới hạn của phép đo

Các trận chạy riêng cho từng chiến lược, không phải đối đầu nhiều đội có giao thông chung. Thời gian là đồng hồ thực trên một máy, có thể bị ảnh hưởng bởi tải hệ thống. Các seed được tái hiện nhưng quyết định sát hạn giờ có thể thay đổi. Thí nghiệm không bao gồm huấn luyện hoặc so sánh RL.
