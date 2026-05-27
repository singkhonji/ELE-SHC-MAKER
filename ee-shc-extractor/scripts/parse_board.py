"""
parse_board.py — Step 4: Extract structured data from one board's text rows

Usage (when imported):
    parse_board(rows, board_id_hint=None) -> dict

Returns a dict with keys:
    id, supply, incomer_cb, incomer_cable, busbar,
    spd, ct, cable_dc, circuits, acc
"""

import re

# ─── Configuration ────────────────────────────────────────────────────────────
Y_TOLERANCE     = 400       # ± drawing units for Y-band matching
CB_Y_BAND       = (205790, 205870)
SUBBOARD_Y_BAND = (199800, 200400)
CABLE_ROT       = '90'
CIRCUIT_ORDER   = ['P-1RYB','2RYB','3RYB','4RYB','5RYB','6RYB','7RYB','8RYB']
CIRCUIT_PATTERN = re.compile(r'^(P-\d+RYB|\d+RYB)$', re.IGNORECASE)


def _nearest(x: float, cmap: dict, tol: float = 1500) -> str | None:
    best, bd = None, tol
    for name, cx in cmap.items():
        d = abs(x - cx)
        if d < bd:
            bd, best = d, name
    return best


def _has(rows: list, keyword: str) -> bool:
    return any(keyword in r['t'] for r in rows)


def parse_board(rows: list[dict], board_id_hint: str = None) -> dict:
    # Build circuit X map from this board's rows
    cmap = {
        r['t']: r['x']
        for r in rows
        if CIRCUIT_PATTERN.match(r['t'])
    }

    info = {
        'id':             board_id_hint or '',
        'supply':         '',
        'incomer_cb':     '',
        'incomer_cable':  '',
        'busbar':         '',
        'spd':            '',
        'ct':             '',
        'cable_dc':       False,
        'circuits':       {},
        'acc':            [],
    }

    subboards, cb_ratings, cables = {}, {}, {}

    for r in rows:
        t, x, y, rot = r['t'], r['x'], r['y'], r['rot']

        # ── Board-level info ───────────────────────────────────────────────
        if not info['id']:
            if re.match(r'^D\d+-(SB|MDB|DB)-', t):
                info['id'] = t

        if 'FROM D' in t and not info['supply']:
            info['supply'] = t.replace('FROM ', '').strip()

        if 'CABLE BY DC MEP' in t:
            info['cable_dc'] = True

        if re.search(r'\d+A[TF]', t) and 'TPN MCCB' in t and re.search(r'\d+kA', t, re.I):
            if not info['incomer_cb']:
                # Clean up to: "400AT/400AF TPN MCCB 50kA (L,S,I)"
                at = re.search(r'(\d+AT)', t)
                af = re.search(r'(\d+AF)', t)
                kA = re.search(r'(\d+kA)', t, re.I)
                if at and af and kA:
                    info['incomer_cb'] = f"{at.group(1)}/{af.group(1)} TPN MCCB {kA.group(1)} (L,S,I)"
                else:
                    info['incomer_cb'] = re.sub(r'\s+', ' ', t).strip()

        if 'RATED' in t and 'BUSBAR' in t:
            info['busbar'] = t

        if 'TYPE 2' in t and 'IEC61643' in t:
            info['spd'] = '8/20µS TYPE 2, In≥40KA, IEC61643'

        if re.search(r'\d+/5A', t):
            info['ct'] = t

        # ── Sub-board name (Y-band) ────────────────────────────────────────
        if SUBBOARD_Y_BAND[0] < y < SUBBOARD_Y_BAND[1]:
            c = _nearest(x, cmap)
            if c:
                if 'SPARE' in t:
                    subboards[c] = 'SPARE'
                elif re.match(r'^D\d+-(SB|MDB|DB)-', t):
                    subboards[c] = t

        # ── CB rating (Y-band) ─────────────────────────────────────────────
        if CB_Y_BAND[0] < y < CB_Y_BAND[1]:
            c = _nearest(x, cmap)
            if c:
                cb_ratings[c] = t

        # ── Cable size (rotated text) ──────────────────────────────────────
        if rot == CABLE_ROT and 200100 < y < 200350:
            c = _nearest(x, cmap)
            if c:
                cables[c] = t

    # ── Incomer cable from horizontal annotation ──────────────────────────
    ic_candidates = [r for r in rows if '70mm' in r['t'] and r['rot'] == '0']
    if ic_candidates:
        ic = sorted(ic_candidates, key=lambda r: r['y'], reverse=True)[0]['t']
        info['incomer_cable'] = re.sub(r'\s+', ' ', ic).strip()

    # ── Build per-circuit dict ────────────────────────────────────────────
    # Determine actual circuit order from cmap (sorted by X)
    ordered_ckts = sorted(cmap.keys(), key=lambda c: cmap[c])

    # If standard order applies, use it; otherwise use X-sorted order
    std = [c for c in CIRCUIT_ORDER if c in cmap]
    circuit_order = std if std else ordered_ckts

    for ckt in circuit_order:
        sb    = subboards.get(ckt, 'SPARE')
        cb    = cb_ratings.get(ckt, '—')
        cable = cables.get(ckt, '—')

        cb_a   = re.search(r'(\d+A)', cb)
        cb_a   = cb_a.group(1) if cb_a else '—'
        cb_brk = re.search(r'(\d+KA)', cb, re.I)
        cb_brk = cb_brk.group(1).upper() if cb_brk else '36kA'
        spare  = sb == 'SPARE'

        info['circuits'][ckt] = {
            'desc':   sb,
            'cb_a':   cb_a,
            'cb_brk': cb_brk,
            'cable':  cable if not spare else '—',
            'route':  'Cable Ladder / Tray' if not spare else '—',
            'status': 'SPARE' if spare else 'ACTIVE',
            'spare':  spare,
        }

    # ── Accessories ───────────────────────────────────────────────────────
    n = 1
    if info['spd']:
        info['acc'].append((str(n), 'Surge Protection Device (SPD)', info['spd'], '1 set', 'Via 6A MCB'))
        n += 1
    if info['ct']:
        info['acc'].append((str(n), 'Current Transformer (CT)', info['ct'], 'per phase', ''))
        n += 1
    if _has(rows, 'ELR'):
        info['acc'].append((str(n), 'Earth Leakage Relay (ELR)', '—', '1 no.', 'Connected to ZCT'))
        n += 1
    if _has(rows, 'ZCT'):
        info['acc'].append((str(n), 'Zero Core CT (ZCT)', '—', '1 no.', ''))
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
