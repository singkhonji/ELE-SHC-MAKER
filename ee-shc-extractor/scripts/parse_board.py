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
CABLE_ROT       = '90'
CIRCUIT_ORDER   = ['P-1RYB','2RYB','3RYB','4RYB','5RYB','6RYB','7RYB','8RYB']
CIRCUIT_PATTERN = re.compile(r'^(P-\d+RYB|\d+RYB)$', re.IGNORECASE)

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


def _circuit_y(rows):
    """Return mean Y of all circuit label rows, or None if none found."""
    ys = [r['y'] for r in rows if CIRCUIT_PATTERN.match(r['t'])]
    return sum(ys) / len(ys) if ys else None


def parse_board(rows, board_id_hint=None):
    # Build circuit X map
    cmap = {r['t']: r['x'] for r in rows if CIRCUIT_PATTERN.match(r['t'])}

    # Compute relative Y reference from circuit labels
    cy = _circuit_y(rows) or 0.0

    bid_y_lo = cy + BOARD_ID_OFFSET[0];   bid_y_hi = cy + BOARD_ID_OFFSET[1]
    sub_y_lo = cy + SUBBOARD_OFFSET[0];   sub_y_hi = cy + SUBBOARD_OFFSET[1]
    cb_y_lo  = cy + CB_OFFSET[0];         cb_y_hi  = cy + CB_OFFSET[1]
    cab_y_lo = cy + CABLE_OFFSET[0];      cab_y_hi = cy + CABLE_OFFSET[1]

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

    subboards, cb_texts, cables = {}, {}, {}

    for r in rows:
        t, x, y, rot = r['t'], r['x'], r['y'], r['rot']

        # Board ID (from title block Y-band above circuit area)
        if not info['id']:
            if bid_y_lo < y < bid_y_hi and re.match(r'^D\d+-(SB|MDB|DB)-', t):
                info['id'] = t

        # Supply source
        if 'FROM D' in t and not info['supply']:
            info['supply'] = t.replace('FROM ', '').strip()

        # CABLE BY DC MEP flag
        if 'CABLE BY DC MEP' in t:
            info['cable_dc'] = True

        # Incomer CB (text-pattern match)
        if (re.search(r'\d+A[TF]', t) and 'TPN MCCB' in t
                and re.search(r'\d+kA', t, re.I)):
            if not info['incomer_cb']:
                at = re.search(r'(\d+AT)', t)
                af = re.search(r'(\d+AF)', t)
                kA = re.search(r'(\d+kA)', t, re.I)
                if at and af and kA:
                    info['incomer_cb'] = (
                        f"{at.group(1)}/{af.group(1)} TPN MCCB {kA.group(1)} (L,S,I)"
                    )
                else:
                    info['incomer_cb'] = re.sub(r'\s+', ' ', t).strip()

        # Busbar rating
        if 'RATED' in t and 'BUSBAR' in t:
            info['busbar'] = t

        # SPD
        if 'TYPE 2' in t and 'IEC61643' in t:
            info['spd'] = '8/20us TYPE 2, In>=40KA, IEC61643'

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

    # Incomer cable from horizontal annotation
    ic_candidates = [r for r in rows if '70mm' in r['t'] and r['rot'] == '0']
    if ic_candidates:
        ic = sorted(ic_candidates, key=lambda r: r['y'], reverse=True)[0]['t']
        info['incomer_cable'] = re.sub(r'\s+', ' ', ic).strip()

    # Build per-circuit dict
    ordered_ckts = sorted(cmap.keys(), key=lambda c: cmap[c])
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
