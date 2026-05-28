"""
run_loadschedule.py — Stage 2 entry point: clean .xlsx → Load Schedule workbook

Reads the (user-reviewed/edited) clean workbook from Stage 1 and produces the
final Load Schedule workbook: INDEX sheet + DIAGRAM sheet + one sheet per cabinet.

Usage:
    python scripts/run_loadschedule.py <clean.xlsx> [--output LoadSchedule.xlsx]
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from read_clean_xlsx    import read_clean_xlsx
from build_loadschedule import build_loadschedule


def run_loadschedule(clean_path: str, output_path: str = None) -> str:
    if not os.path.exists(clean_path):
        raise FileNotFoundError(f"Clean file not found: {clean_path}")

    print(f"[Read] {os.path.basename(clean_path)}")
    boards = read_clean_xlsx(clean_path)
    if not boards:
        raise ValueError("No cabinets found in clean file — check the layout/markers.")
    for b in boards:
        n_act = sum(1 for d in b['circuits'].values() if not d.get('spare'))
        print(f"       {b['id']:28} ({len(b['circuits'])} circuits, {n_act} active)")

    if output_path is None:
        first = boards[0]['id'] or 'LoadSchedule'
        extra = len(boards) - 1
        name = (f"{first}_LoadSchedule.xlsx" if extra == 0
                else f"{first}_and_{extra}_more_LoadSchedule.xlsx")
        name = re.sub(r'[\\/*?:\[\]]', '-', name)
        output_path = os.path.join(os.path.dirname(os.path.abspath(clean_path)), name)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    print(f"[Build] INDEX + DIAGRAM + {len(boards)} board sheet(s) → {os.path.basename(output_path)}")
    build_loadschedule(boards, output_path)
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

    run_loadschedule(args[0], out)
