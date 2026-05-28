"""
detect_boards.py — Step 3: Detect and split multiple boards from text rows

Supports single-row layouts (one row of boards side-by-side) and
multi-row grid layouts (boards arranged in both X and Y directions).

Usage (standalone):
    python scripts/detect_boards.py <input.xls>

Returns (when imported):
    detect_boards(rows) -> list[list[dict]]
    Each inner list = all text rows belonging to one board.
    Order: top-to-bottom Y-band, then left-to-right X within each band.
"""

import re
import sys

# ─── Configuration ────────────────────────────────────────────────────────────
X_GAP_THRESHOLD = 9_000    # min X gap (drawing units) to split boards horizontally
Y_GAP_THRESHOLD = 10_000   # min Y gap (drawing units) to split boards vertically
X_MARGIN        = 6_000    # units added left/right of circuit X range for row capture
CIRCUIT_PATTERN = re.compile(r'^(P-\d+RYB|\d+RYB)$', re.IGNORECASE)

# Board diagrams extend much further ABOVE their circuit row (title block,
# info rows, incomer details) than below.  This asymmetry shifts the Y-band
# boundary upward so that a board's header is captured by the correct band.
# Empirically: header ≈ 15 000 units above circuits; lower extent ≈ 2 000 below.
BOARD_DIAGRAM_ASYMMETRY = 13_000   # = header_above − lower_below


def _band_boundaries(centers: list[float]) -> list[float]:
    """
    Given Y-band center values (sorted descending = top-to-bottom),
    return boundary values between adjacent bands.
    Boundary is shifted UPWARD by BOARD_DIAGRAM_ASYMMETRY/2 vs the plain midpoint.
    """
    boundaries = []
    for i in range(len(centers) - 1):
        mid = (centers[i] + centers[i + 1]) / 2
        boundaries.append(mid + BOARD_DIAGRAM_ASYMMETRY / 2)
    return boundaries


def _x_split(circuit_xs: list[float]) -> list[float]:
    """Return X-split midpoints where adjacent circuit Xs gap > X_GAP_THRESHOLD."""
    sorted_xs = sorted(circuit_xs)
    splits = []
    for i in range(1, len(sorted_xs)):
        gap = sorted_xs[i] - sorted_xs[i - 1]
        if gap > X_GAP_THRESHOLD:
            splits.append((sorted_xs[i - 1] + sorted_xs[i]) / 2)
    return splits


def detect_boards(rows: list[dict]) -> list[list[dict]]:
    """
    Split rows into per-board groups using a 2-D grid approach:
      1. Group circuit labels into Y-bands (vertical rows of boards).
      2. Within each Y-band, split by X gaps (horizontal columns).
      3. Assign every text row to its (Y-band, X-column) cell.

    Falls back to single-board if no circuit labels are found.
    Returns a list of row-groups ordered: top Y-band first, left X first.
    """
    circuit_rows = [r for r in rows if CIRCUIT_PATTERN.match(r['t'])]

    if not circuit_rows:
        return [rows]

    # ── Step 1: find distinct Y-bands ────────────────────────────────────────
    circuit_ys = sorted({r['y'] for r in circuit_rows}, reverse=True)  # high→low

    y_band_centers = [circuit_ys[0]]
    for y in circuit_ys[1:]:
        if y_band_centers[-1] - y > Y_GAP_THRESHOLD:
            y_band_centers.append(y)
        else:
            # Average into existing band center
            y_band_centers[-1] = (y_band_centers[-1] + y) / 2

    # Compute Y boundaries between adjacent bands (shifted upward)
    y_bounds = _band_boundaries(y_band_centers)   # len = n_bands - 1
    # Full band slices: [+inf, b0], (b0, b1], ..., (b_n, -inf]
    y_slices = (
        [float('inf')] + y_bounds + [-float('inf')]
    )  # n_bands + 1 values → n_bands intervals

    # ── Step 2: for each Y-band find X-columns ─────────────────────────────
    boards = []   # list of (y_hi, y_lo, ckt_x_min, ckt_x_max) tuples

    for band_idx in range(len(y_band_centers)):
        y_hi = y_slices[band_idx]
        y_lo = y_slices[band_idx + 1]

        band_circuits = [
            r for r in circuit_rows
            if y_lo < r['y'] <= y_hi
        ]
        if not band_circuits:
            continue

        band_circuits.sort(key=lambda r: r['x'])
        band_xs = [r['x'] for r in band_circuits]

        # Split into X-clusters
        clusters = [[band_circuits[0]]]
        for r in band_circuits[1:]:
            if r['x'] - clusters[-1][-1]['x'] > X_GAP_THRESHOLD:
                clusters.append([r])
            else:
                clusters[-1].append(r)

        for cluster in clusters:
            ckt_x_min = min(r['x'] for r in cluster)
            ckt_x_max = max(r['x'] for r in cluster)
            boards.append((y_hi, y_lo, ckt_x_min, ckt_x_max))

    if not boards:
        return [rows]

    # ── Step 3: assign all rows to board cells using X margin ────────────
    result = []
    for (y_hi, y_lo, ckt_x_min, ckt_x_max) in boards:
        x_lo_b = ckt_x_min - X_MARGIN
        x_hi_b = ckt_x_max + X_MARGIN
        cell_rows = [
            r for r in rows
            if y_lo < r['y'] <= y_hi and x_lo_b <= r['x'] <= x_hi_b
        ]
        if cell_rows:
            result.append(cell_rows)

    return result if result else [rows]


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from scripts.parse_xls import parse_xls

    if len(sys.argv) < 2:
        print("Usage: python scripts/detect_boards.py <input.xls>")
        sys.exit(1)

    rows  = parse_xls(sys.argv[1])
    boards = detect_boards(rows)

    print(f"Detected {len(boards)} board(s)\n")
    for i, brows in enumerate(boards):
        xs = [r['x'] for r in brows]
        print(f"  Board {i+1}: {len(brows)} rows  X=[{min(xs):.0f} … {max(xs):.0f}]")
        # Show circuit labels found in this board
        ckts = sorted(
            {r['t'] for r in brows if CIRCUIT_PATTERN.match(r['t'])},
            key=lambda t: float('inf') if 'P' in t else int(re.search(r'\d+', t).group())
        )
        print(f"           Circuits: {ckts}")
