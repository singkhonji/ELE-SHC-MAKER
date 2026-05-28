---
name: ee-shc-extractor
description: >
  Extract electrical panel schedule data from DWG Data Extraction XLS files
  and produce a formatted Load Schedule Excel workbook (.xlsx), one sheet per
  distribution board. Use this skill whenever the user has a DWG Data
  Extraction file (.xls) from AutoCAD containing electrical switchboard or
  distribution board schematic data and wants to convert it into a structured
  Load Schedule table. Trigger on: "สร้าง load schedule", "ทำ load schedule",
  "แปลง data extraction เป็น load schedule", "EE_SHC_EXTRACTOR",
  "/ee-shc", "extract panel schedule", "ทำตาราง load", "panel schedule จาก
  DWG", "load schedule จาก XLS", "แปลง xls ไฟล์ไฟฟ้า", or whenever the user
  uploads an .xls file described as coming from DWG Data Extraction of
  electrical drawings. Also trigger when the user says they have extracted data
  from AutoCAD and wants a load schedule output, even if they do not use the
  exact skill name. Additionally trigger on the DXF path: "แปลง dxf เป็น clean",
  "clean dxf", "dxf to xlsx", "dxf to clean", "อ่าน dxf ทำตารางตู้", or whenever
  the user uploads a `.dxf` saved from a DWG of electrical switchboard schematics
  and wants the cabinets split and summarised. Trigger Stage 2 (Load Schedule
  workbook) on: "สร้าง load schedule จาก clean", "ทำตารางโหลดจาก clean",
  "clean to load schedule", "สร้างตารางโหลด แยก sheet", "ทำ index + diagram",
  or when the user has a reviewed clean `.xlsx` and wants the final per-cabinet
  Load Schedule workbook with an index page and a power-distribution diagram.
---

# EE_SHC_EXTRACTOR — Electrical Switchboard Schedule Extractor

Converts AutoCAD electrical switchboard schematics into structured Excel
output. Two input paths:

- **DXF path (Stage 1, preferred)** — read a DXF saved from the DWG, split
  cabinets by their **real border rectangles**, and write a single **clean
  review `.xlsx`** (per-circuit summary table per cabinet, separated by cabinet
  headers). This replaces the manual, per-panel AutoCAD Data Extraction step.
- **XLS path (legacy)** — read a per-panel Data Extraction `.xls` and build the
  formatted Load Schedule workbook directly.

Both paths support **one or multiple cabinets** in a single input file.

---

## DXF Path — Stage 1: DXF → clean `.xlsx`

Entry point:

```bash
python scripts/run_clean.py <input.dxf> [more.dxf ...] [--output out.xlsx]
```

Pipeline:

| Step | Script | Action |
|---|---|---|
| 1 | `parse_dxf.py` | Read DXF with **ezdxf**. `TEXT` → `e.dxf.text`; `MTEXT` → `e.plain_text()` (strips formatting codes natively — no regex needed). Resolve effective MTEXT rotation from its `text_direction` vector (group 11/21) so rotated cable annotations are detected. Drop single-char symbol noise on layer `0`. Returns `{t, x, y, rot, layer, type}` — `{t,x,y,rot}` are identical to `parse_xls`. |
| 2 | `detect_panels.py` | Find each cabinet's **border rectangle**: a `LWPOLYLINE` whose bbox height exceeds 60% of the total drawing height. Assign every text row to the frame that contains it. Order left-to-right, then top-to-bottom. **Fallback** to `detect_boards.detect_boards()` (X-gap) if no frame is found. |
| 3 | `parse_board.py` | **Reused unchanged** — extract board ID, supply, incomer CB, busbar, SPD/CT, cable sizes, accessories, and per-circuit data from each cabinet's rows. |
| 4 | `build_clean_xlsx.py` | Write **one worksheet** (`Clean Summary`): for each cabinet, a dark-blue title bar (`ตู้ / CABINET: {id}`), an info line (Incomer / Busbar / Accessories / ⚠️ CABLE BY DC MEP), then a 10-column per-circuit table. SPARE circuits flagged; one blank spacer row between cabinets. |

> The clean `.xlsx` is a **review artifact**: the user verifies the cabinet
> split and per-circuit data before Stage 2 (Load Schedule) is run. Wiring the
> clean output into the Load Schedule builder is planned for a later iteration.

Why DXF over the legacy Data Extraction XLS:
- One DXF for all cabinets vs. one manual export per cabinet.
- Cabinet boundaries come from the **drawn border**, not a coordinate-gap
  heuristic — robust regardless of drawing scale.
- `MTEXT.plain_text()` is more reliable than the `parse_xls` regex cleaner.

---

## DXF Path — Stage 2: clean `.xlsx` → Load Schedule workbook

Entry point:

```bash
python scripts/run_loadschedule.py <clean.xlsx> [--output LoadSchedule.xlsx]
```

Reads the **clean workbook from Stage 1 after the user has reviewed/edited it**
and builds the final deliverable. The clean file is the single source of truth —
**Stage 2 never invents data**: load names, Connected Load (kW) and Demand Factor
that the user typed into the clean file flow straight through; anything left blank
stays blank and is flagged `⚠️` for the M&E Engineer.

| Step | Script | Action |
|---|---|---|
| 1 | `read_clean_xlsx.py` | Parse the (possibly edited) clean workbook back into board dicts. Keys off the stable `CABINET:` markers, the labelled header cells (`Supply Source:`, `Incomer CB:`, `Incomer Cable:`, `Busbar:`, `Accessories:`, `Flags:`) and the fixed 12-column circuit table. Tolerant of edited values + blank spacer rows. |
| 2 | `build_loadschedule.py` | Build a multi-sheet workbook: **`INDEX`** (clickable list: Board ID, type, supply, circuit/active/spare counts, incomer, flags) → **`DIAGRAM`** (clickable box tree of the supply hierarchy, coloured by board type, ref-only nodes greyed) → **one Load Schedule sheet per cabinet** (reuses `build_excel._build_sheet` with `with_demand_formula=True` so Max Demand = `=G*H`). Every Board ID / diagram box is an internal `location` hyperlink; each board title bar links back to `INDEX`. |

**Round-trip contract**: the user may edit *values* in the clean file but must keep
the `CABINET:` markers, the header labels, the circuit-table columns, and the blank
spacer rows intact (these are how `read_clean_xlsx.py` finds the structure).

Hierarchy for the diagram is derived from `board['supply']` (parent) and any outgoing
circuit whose Description matches `^D\d+-(SB|MDB|DB|EMSB)-` (child). Boards present
as sheets are clickable; referenced-only boards (e.g. downstream DBs not in the DXF)
are shown as greyed `(ref)` boxes.

---

## XLS Path (legacy) — DWG Data Extraction XLS → Load Schedule

---

## Expected Input

An `.xls` file produced by AutoCAD's **Data Extraction** wizard, filtered to
`Text` and `MText` entity types only, with **exactly these 8 columns**:

| Column | Entity Type |
|---|---|
| `Name` | `Text` or `MText` |
| `Contents` | MText body (raw, with formatting codes) |
| `Position X` | X coordinate for **MText** rows |
| `Position Y` | Y coordinate for **MText** rows |
| `Rotation` | Rotation angle (0 = horizontal, 90 = vertical) |
| `Position X1` | X coordinate for **Text** rows |
| `Position Y1` | Y coordinate for **Text** rows |
| `Value` | Text body for single-line **Text** rows |

> ⚠️ **Coordinate column swap**: `MText` uses `Position X/Y`; `Text` uses
> `Position X1/Y1`. The script handles this automatically.

If the user's file has extra columns (e.g. `Count`, `ContentsRTF`), the
script ignores them gracefully.

---

## Workflow

### Step 1 — Read & validate input

```
view /mnt/skills/public/xlsx/SKILL.md          ← always read first
```

Load the XLS with `xlrd`. Confirm the 8 required columns exist. Warn if
extra/missing columns are detected but continue where possible.

### Step 2 — Clean and collect text rows

Use `scripts/parse_xls.py` (see below) to:
- Detect coordinate column per entity type (MText vs Text swap)
- Strip MText formatting codes → plain text
- Drop noise rows: single characters, empty strings
- Return a flat list: `[{t, x, y, rot}, ...]`

### Step 3 — Detect board boundaries

Boards are identified by clustering **circuit label** X positions
(labels matching `P-1RYB`, `2RYB` … `8RYB`, or any `*RYB` pattern).

Use `scripts/detect_boards.py`:
- Sort circuit labels by X
- Find natural gaps > `GAP_THRESHOLD` (default 10,000 drawing units)
- Each cluster = one board
- Assign all text rows to the nearest board based on X range

> For a single board, no splitting is needed.

### Step 4 — Parse each board

Use `scripts/parse_board.py` to extract:

| Data point | Method |
|---|---|
| Board ID | Text matching `D*-SB-*` or `D*-MDB-*` or `D*-DB-*` near top-Y |
| Supply source | Text containing `FROM D*` |
| Incomer CB | Text containing `AT` + `TPN MCCB` + `kA` |
| Busbar | Text containing `RATED` + `BUSBAR` |
| SPD spec | Text containing `TYPE 2` + `IEC61643` |
| CT spec | Text matching `\d+/5A` pattern |
| CABLE BY DC MEP | Flag if present |
| Sub-board names | MText at Y-band ~±300 of ROOM/EQUIPMENT row, matched to nearest circuit X |
| CB ratings per circuit | MText at Y-band ~205800 (adjust if needed), matched to nearest circuit X |
| Cable sizes | MText with `Rotation=90`, matched to nearest circuit X |
| Accessories | Presence check: ELR, ZCT, SPD, PM, BMS |

**Y-band tolerance**: ±400 drawing units. If a board's coordinate system
differs (non-standard scale), adjust `Y_TOLERANCE` in the script config.

### Step 5 — Build Excel output

Use `scripts/build_excel.py` to write a formatted `.xlsx`:
- **One worksheet per board**, tab named with board ID
- Tab colours: first board dark blue (`1F3864`), subsequent boards medium
  blue (`2E75B6`), cycle if more than 2
- Sections: Title → Board Info → Section A (Incomer) → Section B
  (Outgoing Circuits) → Section C (Accessories) → Notes
- Column structure: 14 columns per the Load Schedule format
  (see `references/column_spec.md`)
- ⚠️ Flags in Notes: `CABLE BY DC MEP`, missing ELR/ZCT

### Step 6 — Recalculate & verify

```bash
python scripts/recalc.py <output.xlsx> 30
```

Check `status == "success"` and `total_errors == 0` before presenting.

### Step 7 — Present output

Call `present_files` with the output `.xlsx` path.

---

## Configuration (adjustable per project)

All tunable parameters live at the top of each script as constants:

| Parameter | Default | Purpose |
|---|---|---|
| `GAP_THRESHOLD` | `10000` | Min X gap to split boards |
| `Y_TOLERANCE` | `400` | Y-band ± for row matching |
| `CIRCUIT_PATTERN` | `r'^(P-\d+RYB\|\dRYB)$'` | Regex for circuit label detection |
| `CB_Y_BAND` | `(205790, 205870)` | Y range for CB rating rows |
| `SUBBOARD_Y_BAND` | `(199800, 200400)` | Y range for sub-board name rows |
| `CABLE_ROT` | `'90'` | Rotation value for cable size rows |
| `NOISE_MAX_LEN` | `1` | Max char length to treat as noise |

> If the drawing uses a different coordinate system or scale, adjust
> `CB_Y_BAND` and `SUBBOARD_Y_BAND` to match actual Y values in the XLS.

---

## Output Format

Refer to `references/column_spec.md` for the full 14-column Load Schedule
spec and colour coding.

Output file naming convention:
- Single board: `{BOARD_ID}_LoadSchedule.xlsx`
- Multiple boards: `{FIRST_BOARD_ID}_and_{N-1}_more_LoadSchedule.xlsx`
  (e.g. `D1-SB-COM-FOH-BS1-A_and_1_more_LoadSchedule.xlsx`)

---

## Edge Cases & Warnings

- **No circuit labels found**: Abort with message — file may be wrong type
- **Single-character noise** (E, F, C, O from symbol blocks): auto-filtered
- **INSTALLED CAPACITY (kW) blank**: Expected — designer rarely fills this;
  note in output that M&E Engineer must populate
- **ELR/ZCT missing**: Flag in Notes — may be inside a block, not standalone text
- **Incomer CB not parseable**: Write `— (refer drawing)` and flag in Notes
- **`CABLE BY DC MEP` present**: Always flag as ⚠️ SCOPE CONFLICT in Notes
- **ContentsRTF column present**: Ignored — `Contents` is used exclusively
- **`Count` column present**: Ignored

---

## References

- `references/column_spec.md` — 14-column output spec + colour codes
- `references/mtext_cleaning.md` — MText formatting code stripping rules (legacy XLS path only)
- `scripts/run_clean.py` — Stage 1 entry: DXF → clean review `.xlsx`
- `scripts/parse_dxf.py` — Stage 1: read & clean via ezdxf
- `scripts/detect_panels.py` — Stage 1: cabinet split by border rectangle
- `scripts/build_clean_xlsx.py` — Stage 1: clean review workbook (round-trippable)
- `scripts/run_loadschedule.py` — Stage 2 entry: clean `.xlsx` → Load Schedule workbook
- `scripts/read_clean_xlsx.py` — Stage 2: parse clean `.xlsx` → board dicts
- `scripts/build_loadschedule.py` — Stage 2: INDEX + DIAGRAM + per-board sheets
- `scripts/parse_xls.py` — XLS: read & clean
- `scripts/detect_boards.py` — XLS: multi-board detection (X-gap)
- `scripts/parse_board.py` — shared: per-board data extraction
- `scripts/build_excel.py` — Load Schedule output builder
