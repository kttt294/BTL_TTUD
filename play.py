"""Chạy trận thi: python play.py ID_TRAN (mặc định trận tính giờ, planner tour C++).

Practice: python play.py ID_CAU_HOI:ID_DOI. Kiểm tra trước trận: python play.py ID_TRAN --preflight.
Xem mọi tham số: python play.py --help.
"""

from pathlib import Path
import sys

# Không cần "python -X utf8": thông báo tiếng Việt vẫn in/ghi log được trên Windows.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from hexudon.live import main

if __name__ == "__main__":
    main()
