"""Tính udon tối đa và đề xuất đội hình: python phan_tich_map.py ID_TRAN [--select 26]."""

from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from hexudon.map_analysis import main

if __name__=='__main__':
    main()
