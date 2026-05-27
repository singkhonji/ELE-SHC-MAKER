"""
run.py — EE_SHC_EXTRACTOR main entry point

Usage:
    python scripts/run.py <input.xls> [output.xlsx]

Pipeline:
    Step 1: parse_xls     → clean text rows
    Step 2: detect_boards → split into per-board groups
    Step 3: parse_board   → extract structured data per board
    Step 4: build_excel   → write formatted .xlsx
    Step 5: recalc        → verify zero formula errors
"""

import os
import sys
import subprocess

# Allow running from skill root or scripts/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.parse_xls    import parse_xls
from scripts.detect_boards import detect_boards
from scripts.parse_board  import parse_board
from scripts.build_excel  import build_excel


def run(input_path: str, output_path: str = None) -> str:
    """
    Full pipeline: XLS → Load Schedule XLSX.
    Returns output file path.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")

    # ── Step 1: Parse ──────────────────────────────────────────────────────
    print(f"[1/5] Parsing {os.path.basename(input_path)} …")
    rows = parse_xls(input_path)
    print(f"      {len(rows)} text rows extracted")

    if not rows:
        raise ValueError("No text rows found. Check that the XLS contains Text/MText entities.")

    # ── Step 2: Detect boards ──────────────────────────────────────────────
    print("[2/5] Detecting board boundaries …")
    board_groups = detect_boards(rows)
    print(f"      {len(board_groups)} board(s) detected")

    # ── Step 3: Parse each board ───────────────────────────────────────────
    print("[3/5] Extracting board data …")
    boards_data = []
    for i, brows in enumerate(board_groups):
        bdata = parse_board(brows)
        # Fallback board ID if not found in text
        if not bdata['id']:
            bdata['id'] = f'BOARD_{i+1}'
        print(f"      Board {i+1}: {bdata['id']}  ({len(bdata['circuits'])} circuits)")
        boards_data.append(bdata)

    # ── Step 4: Build Excel ────────────────────────────────────────────────
    if output_path is None:
        base = os.path.splitext(os.path.basename(input_path))[0]
        if len(boards_data) == 1:
            out_name = f"{boards_data[0]['id']}_LoadSchedule.xlsx"
        else:
            out_name = f"{boards_data[0]['id']}_and_{len(boards_data)-1}_more_LoadSchedule.xlsx"
        output_path = os.path.join('/mnt/user-data/outputs', out_name)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"[4/5] Building Excel → {os.path.basename(output_path)} …")
    build_excel(boards_data, output_path)

    # ── Step 5: Recalculate & verify ──────────────────────────────────────
    print("[5/5] Verifying formula integrity …")
    recalc_script = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', '..', 'public', 'xlsx', 'scripts', 'recalc.py'
    )
    # Try standard skill recalc location
    if not os.path.exists(recalc_script):
        recalc_script = '/mnt/skills/public/xlsx/scripts/recalc.py'

    if os.path.exists(recalc_script):
        result = subprocess.run(
            ['python3', recalc_script, output_path, '30'],
            capture_output=True, text=True
        )
        print(f"      {result.stdout.strip()}")
    else:
        print("      (recalc.py not found — skipping formula check)")

    print(f"\n✅  Done: {output_path}")
    return output_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    run(inp, out)
