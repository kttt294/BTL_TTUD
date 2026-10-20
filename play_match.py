"""Chạy trận từ ID: python play_match.py ID --algorithm greedy."""

from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from hexudon.live import main

if __name__=='__main__':
    main()
