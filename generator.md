
Mô tả [src/hexudon/generator.py](src/hexudon/generator.py). Hàm `generate_config(seed, profile)` sinh một đề mô phỏng có đúng định dạng config JSON của BTC, gồm bản đồ, vị trí xe, điểm bán udon và số suất, `daySteps`, `fuelLimits`, ngưỡng tắc đường, `daySeconds`, `agent_selection_time_limit`. Cùng `seed` thì luôn ra cùng một đề.

Có 3 loại đề:

- **`btc`:** giống các bài Practice, bản đồ 30–32 ô, 4–6 xe, 10 ngày.
- **`wide`:** trải rộng phạm vi luật, bản đồ 8–32 ô, 3–8 xe, 4–10 ngày.
- **`mix`:** như `wide`, nhưng tỷ lệ địa hình, mật độ điểm bán và số loại udon cũng ngẫu nhiên.

File này là thư viện, không có lệnh chạy riêng. Muốn xuất một đề ra file JSON:

```
python -c "import sys,json; sys.path.insert(0,'src'); from hexudon.generator import generate_config; json.dump(generate_config(12345,'btc'), open('de_12345.json','w'))"
```

Các script đang dùng đề mô phỏng:

- [experiments/suite.py](experiments/suite.py): chạy bộ 300 đề (dev 200, test 100) để so các biến thể thuật toán.
- [experiments/composition_labels.py](experiments/composition_labels.py) và [experiments/composition_eval.py](experiments/composition_eval.py): tạo nhãn chọn đội hình. Hơn 2.400 đề vừa rồi sinh bằng cách này.
- [experiments/selector_check.py](experiments/selector_check.py): phép đo bộ chọn đội hình đang chạy.

Muốn diễn tập thi tính giờ trên một đề mô phỏng thì dùng [experiments/rehearse_timed.py](experiments/rehearse_timed.py). Script này đọc đề từ `output/team_selection/<TÊN>/config.json`, nên chỉ cần lưu file JSON trên vào `output/team_selection/SIM1/config.json` rồi chạy `python -X utf8 experiments/rehearse_timed.py --case SIM1`.
