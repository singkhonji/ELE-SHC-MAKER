"""
run_clean.py — DXF → clean .xlsx pipeline (Stage 1 of the workflow)

Reads one or more DXF files (saved from DWG), splits each into cabinets by their
real border rectangles, extracts per-circuit data, and writes ONE review
workbook: a per-circuit summary table per cabinet, separated by cabinet headers.

Usage:
    python scripts/run_clean.py <input.dxf> [more.dxf ...] [--output out.xlsx]

Pipeline:
    parse_dxf      → clean {t, x, y, rot, layer} rows
    detect_panels  → split into per-cabinet groups by border rectangles
    parse_board    → extract structured data per cabinet
    build_clean_xlsx → write single-sheet review workbook
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parse_dxf        import parse_dxf
from detect_panels    import detect_panels
from parse_board      import parse_board
from build_clean_xlsx import build_clean_xlsx


def run_clean(input_paths: list, output_path: str = None) -> str:
    all_boards = []

    for path in input_paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Input not found: {path}")

        print(f"\n[Parse] {os.path.basename(path)}")
        rows = parse_dxf(path)
        print(f"        {len(rows)} text entities extracted")
        if not rows:
            print("        WARNING: no text found — skipping")
            continue

        panels = detect_panels(path, rows)
        print(f"        {len(panels)} cabinet(s) detected by border")

        for p in panels:
            bdata = parse_board(p['rows'])
            if not bdata['id']:
                bdata['id'] = f'CABINET_{len(all_boards) + 1}'
            print(f"        {bdata['id']:28} ({len(bdata['circuits'])} circuits)")
            all_boards.append(bdata)

    if not all_boards:
        raise ValueError("No cabinets found across all input files.")

    if output_path is None:
        first = all_boards[0]['id']
        extra = len(all_boards) - 1
        name = (f"{first}_CleanSummary.xlsx" if extra == 0
                else f"{first}_and_{extra}_more_CleanSummary.xlsx")
        name = re.sub(r'[\\/*?:\[\]]', '-', name)
        out_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'output'
        )
        os.makedirs(out_dir, exist_ok=True)
        output_path = os.path.join(out_dir, name)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    print(f"\n[Build] {len(all_boards)} cabinet(s) → {os.path.basename(output_path)}")
    build_clean_xlsx(all_boards, output_path)
    print(f"\n✅  Done: {output_path}")
    return output_path


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    out = None
    if '--output' in args:
        idx = args.index('--output')
        out = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    run_clean(args, out)
