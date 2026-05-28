"""
parse_dxf.py — Read & clean a DWG-derived DXF (replaces parse_xls.py for DXF input)

Usage (standalone):
    python scripts/parse_dxf.py <input.dxf>

Returns (when imported):
    parse_dxf(path) -> list[dict]
    Each dict: {t: str, x: float, y: float, rot: str, layer: str, type: str}

Notes:
    ezdxf's MTEXT.plain_text() strips MText formatting codes natively, so the
    regex cleaner in parse_xls.clean_mtext() is not needed for DXF input.
    The {t, x, y, rot} keys are kept identical to parse_xls so the downstream
    parse_board.py works unchanged.
"""

import math
import re
import sys

# AutoCAD special-character codes that appear in TEXT (not MTEXT) entities
_ACAD_CODE = re.compile(r'%%[uUoO]')                    # underline / overline toggles
_ACAD_DEG  = re.compile(r'%%[dD]')
_ACAD_PM   = re.compile(r'%%[pP]')
_ACAD_DIA  = re.compile(r'%%[cC]')
_ACAD_MISC = re.compile(r'%%\d{3}')                    # numeric code fallback

# MText stacking: \S<numerator>^<denominator>; becomes "<numerator>^<denominator>"
# after plain_text(). For superscripts the denominator is blank/space, so we
# see patterns like "2^ " → convert to Unicode superscript "²".
_STACKING_CARET = re.compile(r'(\d+)\^\s?')
_SUPERSCRIPT_MAP = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')


def _fix_superscripts(text: str) -> str:
    """Convert MText stacking remnants (e.g. '2^ ') to Unicode superscripts ('²')."""
    return _STACKING_CARET.sub(lambda m: m.group(1).translate(_SUPERSCRIPT_MAP), text)


def _strip_acad_codes(text: str) -> str:
    """Remove AutoCAD inline formatting codes from a raw TEXT entity value."""
    text = _ACAD_CODE.sub('', text)     # drop %%U / %%O
    text = _ACAD_DEG.sub('°', text)
    text = _ACAD_PM.sub('±', text)
    text = _ACAD_DIA.sub('Ø', text)
    text = _ACAD_MISC.sub('', text)
    return text.strip()

# ─── Configuration ────────────────────────────────────────────────────────────
NOISE_MAX_LEN  = 1          # rows with text this short are dropped …
NOISE_LAYERS   = {'0'}      # … when they also sit on these symbol layers
ROT_TOL        = 1.0        # degrees; snap rotation to nearest of {0, 90, 180, 270}


def _norm_rot(angle: float) -> str:
    """Snap a rotation angle to '0' / '90' / '180' / '270' (string) for matching."""
    a = round(float(angle)) % 360
    for ref in (0, 90, 180, 270, 360):
        if abs(a - ref) <= ROT_TOL:
            return str(ref % 360)
    return str(a)


def _mtext_angle(e) -> float:
    """Effective MTEXT rotation in degrees.

    An MTEXT text-direction vector (DXF group 11/21/31) overrides the plain
    rotation attribute (group 50).  AutoCAD's Data Extraction reports this
    effective angle, so we must resolve it the same way — otherwise rotated
    cable annotations look horizontal and downstream matching fails.
    """
    if e.dxf.hasattr('text_direction'):
        d = e.dxf.text_direction
        return math.degrees(math.atan2(d.y, d.x))
    return float(e.dxf.rotation)


def parse_dxf(path: str) -> list[dict]:
    try:
        import ezdxf
    except ImportError:
        raise ImportError("ezdxf is required: pip install ezdxf")

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    results = []
    for e in msp:
        dt = e.dxftype()
        if dt == 'TEXT':
            text  = _strip_acad_codes(e.dxf.text or '')
            ins   = e.dxf.insert
            rot   = _norm_rot(e.dxf.rotation)
            layer = e.dxf.layer
        elif dt == 'MTEXT':
            text  = e.plain_text().replace('\n', ' ').replace('\r', ' ')
            text  = _fix_superscripts(text)
            text  = ' '.join(text.split()).strip()
            ins   = e.dxf.insert
            rot   = _norm_rot(_mtext_angle(e))
            layer = e.dxf.layer
        else:
            continue

        if not text:
            continue
        # Drop single-character symbol noise (e.g. O, E, C, F on layer "0")
        if len(text) <= NOISE_MAX_LEN and layer in NOISE_LAYERS:
            continue

        results.append({
            't':     text,
            'x':     float(ins.x),
            'y':     float(ins.y),
            'rot':   rot,
            'layer': layer,
            'type':  dt,
        })

    return results


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/parse_dxf.py <input.dxf>")
        sys.exit(1)

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    rows = parse_dxf(sys.argv[1])
    rows.sort(key=lambda r: (-r['y'], r['x']))
    print(f"Parsed {len(rows)} text rows\n")
    print(f"{'Y':>12}  {'X':>12}  {'ROT':>4}  {'LAYER':<18}  TEXT")
    print('-' * 96)
    for row in rows:
        print(f"{row['y']:12.1f}  {row['x']:12.1f}  {row['rot']:>4}  "
              f"{row['layer'][:18]:<18}  {row['t'][:54]}")
