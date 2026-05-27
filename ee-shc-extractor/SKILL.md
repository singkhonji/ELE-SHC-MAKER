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
  exact skill name.
---

# EE_SHC_EXTRACTOR — Electrical Switchboard Schedule Extractor

Converts DWG Data Extraction XLS files (from AutoCAD electrical schematics)
into formatted Load Schedule Excel workbooks. Supports **one or multiple
boards** in a single XLS — each board becomes its own worksheet.

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
- `references/mtext_cleaning.md` — MText formatting code stripping rules
- `scripts/parse_xls.py` — Step 2: read & clean XLS
- `scripts/detect_boards.py` — Step 3: multi-board detection
- `scripts/parse_board.py` — Step 4: per-board data extraction
- `scripts/build_excel.py` — Step 5: Excel output builder
