"""Practice: chạy nhiều lượt offline song song, nộp lượt tốt nhất: python toi_uu_practice.py [Q04 ...]."""

from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from hexudon.practice_best import main

if __name__=='__main__':
    main()
