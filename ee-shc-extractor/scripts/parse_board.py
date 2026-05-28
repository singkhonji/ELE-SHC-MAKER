"""
parse_board.py -- Step 4: Extract structured data from one board's text rows

Usage (when imported):
    parse_board(rows, board_id_hint=None) -> dict

Returns a dict with keys:
    id, supply, incomer_cb, incomer_cable, busbar,
    spd, ct, cable_dc, circuits, acc
"""

import re

# --- Configuration -----------------------------------------------------------
CABLE_ROT     = '90'
CIRCUIT_ORDER = ['P-1RYB','2RYB','3RYB','4RYB','5RYB','6RYB','7RYB','8RYB']

# ── Circuit-label patterns ────────────────────────────────────────────────────
# Type A: RYB-grouped     e.g. P-1RYB, 2RYB, 3RYB
_PAT_RYB    = re.compile(r'^(P-\d+RYB|\d+RYB)$', re.IGNORECASE)
# Type B: R-phase anchor  e.g. L1-1R, 2R, P-1R, AC-1R, L-1R
_PAT_RPHASE = re.compile(r'^([A-Za-z][A-Za-z0-9]*-)?\d+R$', re.IGNORECASE)
# Type C: plain numeric   e.g. 1, 2, 3 … 20
_PAT_NUM    = re.compile(r'^\d{1,2}$')
# Backward-compatible alias — union of all three
CIRCUIT_PATTERN = re.compile(
    r'^(P-\d+RYB|\d+RYB|([A-Za-z][A-Za-z0-9]*-)?\d+R|\d{1,2})$',
    re.IGNORECASE,
)

# X-proximity tolerance for deduplicating circuit labels at the same column
_CMAP_DEDUP_TOL = 300

# Offsets relative to circuit_y (mean Y of circuit label rows in this board).
# All values are (min_delta, max_delta) measured ABOVE the circuit row.
BOARD_ID_OFFSET   = (13000, 18000)   # board title block
SUBBOARD_OFFSET   = (1800,  3200)    # sub-board / room description row
CB_OFFSET         = (7000,  9500)    # outgoing circuit CB rating row
CABLE_OFFSET      = (2000,  4000)    # cable size (rotated text)
INCOMER_CB_OFFSET = (10000, 16500)   # incomer CB info row

# Template column-header strings to skip when capturing sub-board names
_SKIP_SUBBOARD = {
    'ROOM / EQUIPMENT', 'NAME', 'INSTALLATED', 'INSTALLED',
    'CAPACITY  (KW)', 'CAPACITY (KW)', 'CIRCUIT NO:',
}


def _nearest(x, cmap, tol=1500):
    best, bd = None, tol
    for name, cx in cmap.items():
        d = abs(x - cx)
        if d < bd:
            bd, best = d, name
    return best


def _has(rows, keyword):
    return any(keyword in r['t'] for r in rows)


# ── Circuit format detection & cmap building ──────────────────────────────────

def _detect_circuit_fmt(rows):
    """Return 'ryb', 'rphase', 'numeric', or None.

    Only horizontal text (rot='0') is considered for all formats — rotated
    text belongs to cable annotations, not circuit labels.
    """
    horiz = [r for r in rows if r['rot'] == '0']
    if sum(1 for r in horiz if _PAT_RYB.match(r['t'])) >= 2:
        return 'ryb'
    if sum(1 for r in horiz if _PAT_RPHASE.match(r['t'])) >= 2:
        return 'rphase'
    nums = {int(r['t']) for r in horiz if _PAT_NUM.match(r['t'])}
    if len(nums) >= 2 and any(n + 1 in nums for n in nums):
        return 'numeric'
    return None


def _pat_for_fmt(fmt):
    if fmt == 'ryb':
        return _PAT_RYB
    if fmt == 'rphase':
        return _PAT_RPHASE
    if fmt == 'numeric':
        return _PAT_NUM
    return CIRCUIT_PATTERN


def _build_cmap_rphase(rows):
    """Build cmap for R-phase anchor boards.

    Each R-phase label (L1-1R, 2R, P-1R …) anchors one 3-phase circuit column.
    Duplicate base labels at clearly different X positions (e.g. '2R' appearing
    in the L1-group and again in the P-group) receive a numeric suffix:
    2R, 2R_2, 2R_3.  Only horizontal text (rot='0') is used.
    """
    rphase_rows = sorted(
        [r for r in rows if r['rot'] == '0' and _PAT_RPHASE.match(r['t'])],
        key=lambda r: r['x'],
    )
    cmap = {}
    seen = {}  # base_label -> count of occurrences placed in cmap
    for r in rphase_rows:
        label = r['t']
        if label not in seen:
            cmap[label] = r['x']
            seen[label] = 1
        else:
            # Already seen — only add if it's at a significantly different X
            if abs(cmap[label] - r['x']) > _CMAP_DEDUP_TOL:
                count = seen[label] + 1
                seen[label] = count
                cmap[f'{label}_{count}'] = r['x']
            # else: duplicate entity at same column — skip
    return cmap


def _build_cmap(rows, fmt):
    """Build {circuit_label: x_position} map for the given format."""
    if fmt == 'rphase':
        return _build_cmap_rphase(rows)
    pat = _pat_for_fmt(fmt)
    cmap = {}
    for r in rows:
        if r['rot'] == '0' and pat.match(r['t']):
            lbl = r['t']
            if lbl not in cmap:
                cmap[lbl] = r['x']
            elif abs(cmap[lbl] - r['x']) > _CMAP_DEDUP_TOL:
                n = 2
                while f'{lbl}_{n}' in cmap:
                    n += 1
                cmap[f'{lbl}_{n}'] = r['x']
    return cmap


def _circuit_y(rows, pat=None):
    """Return mean Y of horizontal circuit label rows, or None if none found."""
    if pat is None:
        pat = CIRCUIT_PATTERN
    ys = [r['y'] for r in rows if r['rot'] == '0' and pat.match(r['t'])]
    return sum(ys) / len(ys) if ys else None


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_board(rows, board_id_hint=None):
    fmt  = _detect_circuit_fmt(rows)
    cmap = _build_cmap(rows, fmt)
    pat  = _pat_for_fmt(fmt)

    # Compute relative Y reference from circuit labels
    cy = _circuit_y(rows, pat) or 0.0

    bid_y_lo = cy + BOARD_ID_OFFSET[0];   bid_y_hi = cy + BOARD_ID_OFFSET[1]
    sub_y_lo = cy + SUBBOARD_OFFSET[0];   sub_y_hi = cy + SUBBOARD_OFFSET[1]
    cb_y_lo  = cy + CB_OFFSET[0];         cb_y_hi  = cy + CB_OFFSET[1]
    cab_y_lo = cy + CABLE_OFFSET[0];      cab_y_hi = cy + CABLE_OFFSET[1]
    inc_y_lo = cy + INCOMER_CB_OFFSET[0]; inc_y_hi = cy + INCOMER_CB_OFFSET[1]

    info = {
        'id':            board_id_hint or '',
        'supply':        '',
        'incomer_cb':    '',
        'incomer_cable': '',
        'busbar':        '',
        'spd':           '',
        'ct':            '',
        'cable_dc':      False,
        'circuits':      {},
        'acc':           [],
    }

    # ── Phase 4: SPD detection ────────────────────────────────────────
    # The SPD description can be split across many adjacent entities
    # (e.g. "10/350" │ "µS" │ "TYPE 1, limp=12.5kA" │ "ACCORDING TO IEC61643").
    # Join all horizontal text above cy+8000 and search that combined string.
    _spd_text = ' '.join(
        r['t'] for r in rows if r['y'] > cy + 8000 and r['rot'] == '0'
    ).upper()
    if 'IEC61643' in _spd_text:
        if 'TYPE 1' in _spd_text:
            info['spd'] = '10/350µS TYPE 1, Iimp=12.5kA, IEC61643'
        elif 'TYPE 2' in _spd_text:
            info['spd'] = '8/20µS TYPE 2, In≥40kA, IEC61643'

    # ── Pre-scan: locate standalone "FROM" labels ─────────────────────────────
    # In many DXF drawings the supply label is split: one entity reads "FROM" and
    # the adjacent entity reads "D1-EMSB-BS1" (or similar).  We record X,Y of
    # every standalone FROM so that nearby board-ID patterns can be paired.
    _from_positions = [
        (r['x'], r['y'])
        for r in rows
        if r['t'].strip().upper() == 'FROM'
    ]

    # ── Pre-scan: collect incomer-zone text fragments ─────────────────────────
    # The incomer CB data often spans several adjacent TEXT entities at roughly
    # the same X column (e.g. "630AT" / "630AF" / "TPN MCCB" / "36kA L,S,I").
    # Collect them all now so we can cluster by X after the main loop.
    _inc_fragments = [
        r for r in rows
        if inc_y_lo < r['y'] < inc_y_hi and r['rot'] == '0'
    ]

    subboards, cb_texts, cables = {}, {}, {}

    for r in rows:
        t, x, y, rot = r['t'], r['x'], r['y'], r['rot']

        # Board ID (from title block Y-band above circuit area)
        if not info['id']:
            if bid_y_lo < y < bid_y_hi and re.match(r'^D\d+-(SB|MDB|DB)-', t):
                info['id'] = t

        # Supply source — Phase 2: two-entity proximity pairing
        # Case A: single entity containing both "FROM" and a board reference
        if 'FROM' in t.upper() and re.search(r'D\d+-(SB|MDB|DB|EMSB)-', t) and not info['supply']:
            info['supply'] = re.sub(r'(?i)from\s*', '', t).strip()
        # Case B: standalone board-ID entity near a "FROM" label
        elif re.match(r'^D\d+-(SB|MDB|DB|EMSB)-', t) and not info['supply']:
            for fx, fy in _from_positions:
                if abs(x - fx) < 1500 and abs(y - fy) < 1500:
                    info['supply'] = t
                    break

        # CABLE BY DC MEP flag
        if 'CABLE BY DC MEP' in t:
            info['cable_dc'] = True

        # Busbar rating
        if 'RATED' in t and 'BUSBAR' in t:
            info['busbar'] = t

        # SPD — Phase 4: now handled via pre-scan above; skip per-entity
        # (left as dead-path for safety: single-entity boards with full SPD text)
        if 'IEC61643' in t and not info['spd']:
            if 'TYPE 2' in t:
                info['spd'] = '8/20µS TYPE 2, In≥40kA, IEC61643'
            elif 'TYPE 1' in t:
                info['spd'] = '10/350µS TYPE 1, Iimp=12.5kA, IEC61643'

        # CT
        if re.search(r'\d+/5A', t):
            info['ct'] = t

        # Sub-board / load description (Y-band)
        if sub_y_lo < y < sub_y_hi:
            c = _nearest(x, cmap)
            if c:
                tu = t.upper().strip()
                if 'SPARE' in tu:
                    subboards[c] = 'SPARE'
                elif re.match(r'^D\d+-(SB|MDB|DB)-', t):
                    subboards[c] = t
                elif tu not in _SKIP_SUBBOARD and len(t) >= 3:
                    if c not in subboards:
                        subboards[c] = t

        # Outgoing CB rating (Y-band) - accumulate text fragments
        if cb_y_lo < y < cb_y_hi:
            c = _nearest(x, cmap)
            if c:
                cb_texts.setdefault(c, []).append(t)

        # Cable size (rotated text, Y-band)
        if rot == CABLE_ROT and cab_y_lo < y < cab_y_hi:
            c = _nearest(x, cmap)
            if c:
                cables[c] = t

    # Consolidate CB fragments
    cb_ratings = {c: ' '.join(texts) for c, texts in cb_texts.items()}

    # ── Phase 3: Incomer CB from fragmented entities ──────────────────────────
    # Cluster incomer-zone fragments by X position (tolerance 400 units),
    # then search for the cluster that contains a CB rating (AT/AF) pattern.
    if not info['incomer_cb'] and _inc_fragments:
        _X_CLUS_TOL = 400
        clusters: list[list[dict]] = []
        for frag in sorted(_inc_fragments, key=lambda r: r['x']):
            placed = False
            for cl in clusters:
                if abs(frag['x'] - cl[0]['x']) <= _X_CLUS_TOL:
                    cl.append(frag)
                    placed = True
                    break
            if not placed:
                clusters.append([frag])

        # Pick the cluster closest to x=0 (leftmost = incomer column)
        # that contains an amperage token
        for cl in sorted(clusters, key=lambda c: c[0]['x']):
            combined = ' '.join(r['t'] for r in cl)
            at = re.search(r'(\d+AT)', combined, re.I)
            af = re.search(r'(\d+AF)', combined, re.I)
            kA = re.search(r'(\d+kA)', combined, re.I)
            brk_type = 'MCB' if 'MCB' in combined.upper() and 'MCCB' not in combined.upper() else 'MCCB'
            poles = 'TPN' if 'TPN' in combined.upper() else ('SPN' if 'SPN' in combined.upper() else 'TPN')
            if at:
                af_str = f'/{af.group(1)}' if af else ''
                kA_str = f' {kA.group(1)}' if kA else ''
                info['incomer_cb'] = f"{at.group(1)}{af_str} {poles} {brk_type}{kA_str} (L,S,I)"
                break
            # Fallback: just an amperage without AT notation (e.g. "125A TPN MCCB")
            amp = re.search(r'(\d+A)\b', combined)
            if amp and ('MCCB' in combined.upper() or 'MCB' in combined.upper()):
                kA_str = f' {kA.group(1)}' if kA else ''
                info['incomer_cb'] = f"{amp.group(1)} {poles} {brk_type}{kA_str}"
                break
    _ic_pat = re.compile(r'\d+mm', re.IGNORECASE)
    ic_candidates = [
        r for r in rows
        if _ic_pat.search(r['t']) and 'CU' in r['t'] and r['rot'] == '0'
    ]
    if ic_candidates:
        ic = sorted(ic_candidates, key=lambda r: r['y'], reverse=True)[0]['t']
        info['incomer_cable'] = re.sub(r'\s+', ' ', ic).strip()

    # Build per-circuit dict
    ordered_ckts = sorted(cmap.keys(), key=lambda c: cmap[c])  # default: sort by X
    if fmt == 'numeric':
        # Sort by integer value, not string / X-position
        try:
            ordered_ckts = sorted(cmap.keys(), key=lambda c: int(c.split('_')[0]))
        except (ValueError, TypeError):
            pass
    std = [c for c in CIRCUIT_ORDER if c in cmap]
    circuit_order = std if std else ordered_ckts

    for ckt in circuit_order:
        sb   = subboards.get(ckt, 'SPARE')
        cb   = cb_ratings.get(ckt, '--')
        cb_a = re.search(r'(\d+A)', cb)
        cb_a = cb_a.group(1) if cb_a else '--'
        cb_brk = re.search(r'(\d+KA)', cb, re.I)
        cb_brk = cb_brk.group(1).upper() if cb_brk else '36kA'
        spare  = (sb == 'SPARE')
        cable  = cables.get(ckt, '--')

        info['circuits'][ckt] = {
            'desc':   sb,
            'cb_a':   cb_a,
            'cb_brk': cb_brk,
            'cable':  cable if not spare else '--',
            'route':  'Cable Ladder / Tray' if not spare else '--',
            'status': 'SPARE' if spare else 'ACTIVE',
            'spare':  spare,
        }

    # Accessories
    n = 1
    if info['spd']:
        info['acc'].append((str(n), 'Surge Protection Device (SPD)', info['spd'], '1 set', 'Via 6A MCB'))
        n += 1
    if info['ct']:
        info['acc'].append((str(n), 'Current Transformer (CT)', info['ct'], 'per phase', ''))
        n += 1
    if _has(rows, 'ELR'):
        info['acc'].append((str(n), 'Earth Leakage Relay (ELR)', '--', '1 no.', 'Connected to ZCT'))
        n += 1
    if _has(rows, 'ZCT'):
        info['acc'].append((str(n), 'Zero Core CT (ZCT)', '--', '1 no.', ''))
        n += 1
    if _has(rows, 'PM'):
        info['acc'].append((str(n), 'Power Meter (PM)', 'Class 0.5, BMS output', '1 no.', ''))
        n += 1
    if _has(rows, 'BMS'):
        info['acc'].append((str(n), 'BMS Interface / Transducer', 'Class 0.5', '1 set', ''))
        n += 1
    if info['busbar']:
        info['acc'].append((str(n), 'Insulated CU Busbar', info['busbar'], '1 set', ''))

    return info
