"""
run_multi.py — Process multiple XLS files into one combined Load Schedule XLSX.

Usage:
    python scripts/run_multi.py <input1.xls> <input2.xls> ... [--output <output.xlsx>]

All boards from all input files are combined into a single workbook,
one worksheet per board.
"""

import os
import sys

# Allow running from skill root or scripts/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.parse_xls     import parse_xls
from scripts.detect_boards import detect_boards
from scripts.parse_board   import parse_board
from scripts.build_excel   import build_excel


def run_multi(input_paths: list, output_path: str = None) -> str:
    all_boards = []

    for path in input_paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Input not found: {path}")

        print(f"\n[Parse] {os.path.basename(path)}")

        rows = parse_xls(path)
        print(f"        {len(rows)} text rows extracted")
        if not rows:
            print(f"        WARNING: no text rows — skipping")
            continue

        board_groups = detect_boards(rows)
        print(f"        {len(board_groups)} board(s) detected")

        for i, brows in enumerate(board_groups):
            bdata = parse_board(brows)
            if not bdata['id']:
                bdata['id'] = f'BOARD_{len(all_boards)+1}'
            print(f"        Board: {bdata['id']}  ({len(bdata['circuits'])} circuits)")
            all_boards.append(bdata)

    if not all_boards:
        raise ValueError("No boards found across all input files.")

    # Determine output path
    if output_path is None:
        first_id = all_boards[0]['id']
        n_extra  = len(all_boards) - 1
        if n_extra == 0:
            name = f"{first_id}_LoadSchedule.xlsx"
        else:
            name = f"{first_id}_and_{n_extra}_more_LoadSchedule.xlsx"
        out_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'output'
        )
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, name)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"\n[Build] {len(all_boards)} sheet(s) → {os.path.basename(output_path)}")
    build_excel(all_boards, output_path)

    print(f"\n✅  Done: {output_path}")
    return output_path


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    # Parse --output flag
    out = None
    if '--output' in args:
        idx = args.index('--output')
        out = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    run_multi(args, out)
