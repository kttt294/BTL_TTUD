"""Lưu checkpoint, khóa lượt chạy và dọn dữ liệu tạm."""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re


def cleanup_run(folder):
    """Chỉ xóa các tệp do runner tạo, giữ nguyên dữ liệu khác trong thư mục."""
    folder = Path(folder)
    names = {'checkpoint.json', 'preview_checkpoint.json', 'config.json',
             'server_state.json', 'result.json', 'types.json', 'runner.lock'}
    for path in folder.iterdir():
        if path.is_file() and (path.name in names or
                re.fullmatch(r'day_\d+_(state\.json|output\.txt)', path.name)):
            path.unlink()
    if not any(folder.iterdir()):
        folder.rmdir()


@contextmanager
def run_lock(folder):
    """Khóa được hệ điều hành tự nhả nếu chương trình bị tắt giữa chừng."""
    path = Path(folder)/'runner.lock'
    handle = path.open('a+b')
    if path.stat().st_size == 0:
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    locked = False
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
