"""Lấy nguyên hình màu từ đề BTC, cắt phần chú thích tiếng Anh ở chân hình."""

from pathlib import Path
from io import BytesIO
from pypdf import PdfReader
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
reader = PdfReader(ROOT / 'Đề bài/2026_Procon_Problem VI.pdf')
folder = ROOT / 'docs/figures'
for page, name, bottom in [(0, 'btc_map.png', 390), (2, 'btc_spots.png', 440),
                           (3, 'btc_agents.png', 350)]:
    image = Image.open(BytesIO(reader.pages[page].images[0].data))
    image.crop((0, 0, image.width, bottom)).save(folder / name)
print('Đã trích ba hình màu từ trang 1, 3, 4 của đề BTC; không đổi màu ảnh.')
