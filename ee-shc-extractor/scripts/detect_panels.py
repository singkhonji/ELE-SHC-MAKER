"""
detect_panels.py — Split a DXF into per-cabinet groups using the real panel
                   border rectangles (replaces detect_boards.py for DXF input).

Each switchboard single-line diagram is drawn inside a large rectangular
LWPOLYLINE frame.  We detect those frames and assign every text row to the
frame whose bounding box contains it — far more robust than X-gap clustering.

Usage (standalone):
    python scripts/detect_panels.py <input.dxf>

Returns (when imported):
    detect_panels(dxf_path, rows) -> list[dict]
    Each dict: {'bbox': (x0, y0, x1, y1), 'rows': [row, ...]}
    Order: left-to-right (x0), then top-to-bottom (y1).
"""

import sys
import os

# ─── Configuration ────────────────────────────────────────────────────────────
FRAME_MIN_HEIGHT_FRAC = 0.60   # frame height must exceed this fraction of total drawing height
FRAME_MIN_WIDTH       = 2_000  # ignore tiny rectangles (symbols, cells)
ASSIGN_MARGIN         = 200     # tolerance (drawing units) when testing containment


def _lwpolyline_bboxes(dxf_path: str):
    """Return [(x0, y0, x1, y1), ...] bounding boxes of every LWPOLYLINE."""
    import ezdxf
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    boxes = []
    for e in msp:
        if e.dxftype() != 'LWPOLYLINE':
            continue
        pts = [(p[0], p[1]) for p in e.get_points()]
        if len(pts) < 2:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    return boxes


def _total_height(boxes, rows):
    ys = []
    for (x0, y0, x1, y1) in boxes:
        ys += [y0, y1]
    ys += [r['y'] for r in rows]
    if not ys:
        return 0.0
    return max(ys) - min(ys)


def _contains(outer, inner) -> bool:
    """True if box `outer` fully contains box `inner`."""
    ox0, oy0, ox1, oy1 = outer
    ix0, iy0, ix1, iy1 = inner
    return ox0 <= ix0 and oy0 <= iy0 and ox1 >= ix1 and oy1 >= iy1


def _detect_frames(boxes, total_h):
    """Pick the panel border rectangles from all LWPOLYLINE bboxes."""
    min_h = FRAME_MIN_HEIGHT_FRAC * total_h
    cands = [
        b for b in boxes
        if (b[3] - b[1]) >= min_h and (b[2] - b[0]) >= FRAME_MIN_WIDTH
    ]
    # Drop any candidate that fully wraps another candidate (outer title border).
    frames = []
    for b in cands:
        wraps_other = any(
            other is not b and _contains(b, other) and other != b
            for other in cands
        )
        if not wraps_other:
            frames.append(b)
    # De-duplicate near-identical boxes.
    uniq = []
    for b in frames:
        if not any(
            abs(b[0] - u[0]) < 1 and abs(b[1] - u[1]) < 1 and
            abs(b[2] - u[2]) < 1 and abs(b[3] - u[3]) < 1
            for u in uniq
        ):
            uniq.append(b)
    # Order: left-to-right, then top-to-bottom.
    uniq.sort(key=lambda b: (round(b[0], -3), -round(b[3], -3)))
    return uniq


def detect_panels(dxf_path: str, rows: list[dict]) -> list[dict]:
    boxes   = _lwpolyline_bboxes(dxf_path)
    total_h = _total_height(boxes, rows)
    frames  = _detect_frames(boxes, total_h) if total_h else []

    # ── Fallback: no frames found → reuse legacy X-gap clustering ────────────
    if not frames:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from detect_boards import detect_boards
        return [{'bbox': None, 'rows': g} for g in detect_boards(rows)]

    panels = [{'bbox': f, 'rows': []} for f in frames]

    def _inside(f, x, y):
        x0, y0, x1, y1 = f
        return (x0 - ASSIGN_MARGIN <= x <= x1 + ASSIGN_MARGIN and
                y0 - ASSIGN_MARGIN <= y <= y1 + ASSIGN_MARGIN)

    for r in rows:
        x, y = r['x'], r['y']
        hits = [i for i, p in enumerate(panels) if _inside(p['bbox'], x, y)]
        if len(hits) == 1:
            panels[hits[0]]['rows'].append(r)
        else:
            # Outside all frames, or ambiguous: assign to nearest frame center.
            def _d(p):
                x0, y0, x1, y1 = p['bbox']
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                return (x - cx) ** 2 + (y - cy) ** 2
            best = min(panels, key=_d)
            best['rows'].append(r)

    return [p for p in panels if p['rows']]


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from parse_dxf import parse_dxf
    import re

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    if len(sys.argv) < 2:
        print("Usage: python scripts/detect_panels.py <input.dxf>")
        sys.exit(1)

    rows   = parse_dxf(sys.argv[1])
    panels = detect_panels(sys.argv[1], rows)

    ckt = re.compile(
        r'^(P-\d+RYB|\d+RYB|([A-Za-z][A-Za-z0-9]*-)?\d+R|\d{1,2})$',
        re.IGNORECASE,
    )
    print(f"Detected {len(panels)} panel(s)\n")
    for i, p in enumerate(panels, 1):
        b = p['bbox']
        bs = f"X[{b[0]:.0f},{b[2]:.0f}] Y[{b[1]:.0f},{b[3]:.0f}]" if b else "(fallback)"
        ckts = sorted({r['t'] for r in p['rows'] if ckt.match(r['t'])})
        print(f"  Panel {i}: {len(p['rows'])} rows  {bs}")
        print(f"           Circuits: {ckts}")
