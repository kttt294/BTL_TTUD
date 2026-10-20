"""Chạy công cụ thực nghiệm từ một điểm vào chung."""

import argparse
from pathlib import Path
import runpy
import sys

FOLDER = Path(__file__).resolve().parent
COMMANDS = {
    path.stem: path
    for group in ("benchmark", "api", "rl")
    for path in (FOLDER / group).glob("*.py")
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS), help="Tên công cụ cần chạy")
    args = parser.parse_args(sys.argv[1:2])
    options = sys.argv[2:]
    path = COMMANDS[args.command]
    sys.path.insert(0, str(path.parent))
    sys.argv = [str(path), *options]
    runpy.run_path(str(path), run_name="__main__")


if __name__ == "__main__":
    main()
