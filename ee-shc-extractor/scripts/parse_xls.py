"""
parse_xls.py — Step 2: Read and clean DWG Data Extraction XLS

Usage (standalone):
    python scripts/parse_xls.py <input.xls>

Returns (when imported):
    parse_xls(path) -> list[dict]
    Each dict: {t: str, x: float, y: float, rot: str}
"""

import re
import sys


# ─── Configuration ────────────────────────────────────────────────────────────
NOISE_MAX_LEN = 1          # rows with text this short are dropped
REQUIRED_COLS = {'Name', 'Contents', 'Value', 'Rotation'}
COORD_COLS_MTEXT = ('Position X', 'Position Y')
COORD_COLS_TEXT  = ('Position X1', 'Position Y1')


# ─── MText cleaner ────────────────────────────────────────────────────────────
def clean_mtext(raw: str) -> str:
    s = str(raw)
    s = re.sub(r'\{\\fCalibri[^;]+;\\H[^;]+;([^}]+)\}', r'\1', s)
    s = re.sub(r'\{\\fArial\|b0\|i0\|c134\|p32;² \\Fromans\.shx\|c0;', '² ', s)
    s = re.sub(r'\{\\f[^}]*\}', '', s)
    s = re.sub(r'\{\\W[\d.]+;([^}]*)\}', r'\1', s)
    s = re.sub(r'\{[^{}]*\}', '', s)
    s = re.sub(r'\\px[^;]+;', '', s)
    s = re.sub(r'\\[HWA]\d*[.\dx]*;?', '', s)
    s = re.sub(r'\\\\P|\\P', ' ', s)
    s = re.sub(r'\\[a-zA-Z*]+;?', '', s)
    s = re.sub(r'\.shx\|c0;', '', s)
    s = re.sub(r'\}', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# ─── Main parser ──────────────────────────────────────────────────────────────
def parse_xls(path: str) -> list[dict]:
    try:
        import xlrd
    except ImportError:
        raise ImportError("xlrd is required: pip install xlrd --break-system-packages")

    wb = xlrd.open_workbook(path)
    sh = wb.sheet_by_index(0)

    # Build header map
    H = {sh.cell_value(0, c): c for c in range(sh.ncols)}

    # Validate columns
    missing = REQUIRED_COLS - set(H.keys())
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Check coordinate columns
    has_mtext_coords = COORD_COLS_MTEXT[0] in H and COORD_COLS_MTEXT[1] in H
    has_text_coords  = COORD_COLS_TEXT[0]  in H and COORD_COLS_TEXT[1]  in H

    results = []
    for r in range(1, sh.nrows):
        name = sh.cell_value(r, H['Name'])
        rot  = str(sh.cell_value(r, H['Rotation']))

        if name == 'MText':
            raw = sh.cell_value(r, H['Contents'])
            text = clean_mtext(raw)
            if has_mtext_coords:
                x = float(sh.cell_value(r, H[COORD_COLS_MTEXT[0]]) or 0)
                y = float(sh.cell_value(r, H[COORD_COLS_MTEXT[1]]) or 0)
            else:
                x = y = 0.0

        elif name == 'Text':
            raw = sh.cell_value(r, H['Value'])
            text = str(raw).strip()
            if has_text_coords:
                x = float(sh.cell_value(r, H[COORD_COLS_TEXT[0]]) or 0)
                y = float(sh.cell_value(r, H[COORD_COLS_TEXT[1]]) or 0)
            else:
                x = y = 0.0
        else:
            continue  # skip non-text entities

        # Drop noise
        if len(text) <= NOISE_MAX_LEN:
            continue

        results.append({'t': text, 'x': x, 'y': y, 'rot': rot})

    return results


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/parse_xls.py <input.xls>")
        sys.exit(1)

    rows = parse_xls(sys.argv[1])
    rows.sort(key=lambda r: (-r['y'], r['x']))
    print(f"Parsed {len(rows)} text rows\n")
    print(f"{'Y':>12}  {'X':>12}  {'ROT':>4}  TEXT")
    print('-' * 80)
    for row in rows:
        print(f"{row['y']:12.0f}  {row['x']:12.0f}  {row['rot']:>4}  {row['t'][:60]}")
