"""Thi tự động mọi câu của một trận: python thi_dau.py --match 14 (hoặc game_id một câu) [--wait-new]."""

from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from hexudon.orchestrator import main

if __name__=='__main__':
    main()
