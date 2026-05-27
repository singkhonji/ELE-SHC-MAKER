"""
detect_boards.py — Step 3: Detect and split multiple boards from text rows

Usage (standalone):
    python scripts/detect_boards.py <input.xls>

Returns (when imported):
    detect_boards(rows) -> list[list[dict]]
    Each inner list = all text rows belonging to one board, sorted L→R by X.
"""

import re
import sys

# ─── Configuration ────────────────────────────────────────────────────────────
GAP_THRESHOLD   = 10_000   # min X gap (drawing units) to split boards
CIRCUIT_PATTERN = re.compile(r'^(P-\d+RYB|\d+RYB)$', re.IGNORECASE)


def detect_boards(rows: list[dict]) -> list[list[dict]]:
    """
    Split rows into per-board groups using X-coordinate gaps between
    circuit labels (e.g. P-1RYB, 2RYB … 8RYB).

    Returns a list of row-groups, one per board, ordered left→right.
    """
    # Find all circuit label X positions
    circuit_xs = sorted(
        r['x'] for r in rows if CIRCUIT_PATTERN.match(r['t'])
    )

    if not circuit_xs:
        # No circuit labels found — treat entire file as one board
        return [rows]

    # Find gaps between consecutive circuit labels
    # A gap > GAP_THRESHOLD signals a new board
    split_points = []
    for i in range(1, len(circuit_xs)):
        gap = circuit_xs[i] - circuit_xs[i - 1]
        if gap > GAP_THRESHOLD:
            midpoint = (circuit_xs[i - 1] + circuit_xs[i]) / 2
            split_points.append(midpoint)

    if not split_points:
        # Only one board
        return [rows]

    # Build X-range boundaries
    boundaries = [-float('inf')] + split_points + [float('inf')]
    boards = []
    for i in range(len(boundaries) - 1):
        lo, hi = boundaries[i], boundaries[i + 1]
        board_rows = [r for r in rows if lo < r['x'] <= hi]
        if board_rows:
            boards.append(board_rows)

    return boards


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
