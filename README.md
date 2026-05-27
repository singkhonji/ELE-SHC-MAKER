# ELE-SHC-MAKER

A collection of Claude Code skills for electrical engineering document workflows.

---

## Skills

### `ee-shc-extractor` — Electrical Switchboard Schedule Extractor

Converts **DWG Data Extraction XLS files** (exported from AutoCAD electrical schematics) into formatted **Load Schedule Excel workbooks** (`.xlsx`), one worksheet per distribution board.

#### Trigger phrases

Use `/ee-shc-extractor` or say any of:

- "สร้าง load schedule" / "ทำ load schedule"
- "แปลง data extraction เป็น load schedule"
- "extract panel schedule" / "panel schedule จาก DWG"
- "load schedule จาก XLS" / "แปลง xls ไฟล์ไฟฟ้า"
- Upload an `.xls` file described as a DWG Data Extraction of electrical drawings

#### What it does

| Step | Script | Action |
|---|---|---|
| 1 | `parse_xls.py` | Reads `.xls`, strips MText formatting codes, returns clean `{t, x, y, rot}` rows |
| 2 | `detect_boards.py` | Clusters circuit labels by X-coordinate gaps to split multi-board drawings |
| 3 | `parse_board.py` | Extracts board ID, supply source, incomer CB, cable sizes, accessories per board |
| 4 | `build_excel.py` | Writes a formatted 14-column Load Schedule `.xlsx` (one sheet per board) |
| 5 | `recalc.py` (xlsx skill) | Verifies formula integrity before delivery |

#### Input format

An `.xls` file from AutoCAD's **Data Extraction** wizard, filtered to `Text` and `MText` entity types, with these 8 columns:

| Column | Description |
|---|---|
| `Name` | Entity type (`Text` or `MText`) |
| `Contents` | MText body (raw, with formatting codes) |
| `Position X / Y` | Coordinates for MText rows |
| `Position X1 / Y1` | Coordinates for Text rows |
| `Rotation` | 0 = horizontal, 90 = vertical |
| `Value` | Text body for single-line Text rows |

#### Output

A formatted `.xlsx` workbook with:
- **One worksheet per board**, tab colour dark blue (first) / mid blue (subsequent)
- 14-column Load Schedule table: Circuit No., Description, CB Rating, CB Type, Poles, Breaking Cap., Connected Load, Demand Factor, Max Demand, Current, Cable Size, Cable Route, Remarks, Status
- Section A (Incomer), Section B (Outgoing Circuits), Section C (Accessories & Metering), Notes
- Auto-flagging of `CABLE BY DC MEP` scope conflicts and missing ELR/ZCT

Output naming:
- Single board: `{BOARD_ID}_LoadSchedule.xlsx`
- Multiple boards: `{BOARD_ID}_and_{N-1}_more_LoadSchedule.xlsx`

#### File structure

```
ee-shc-extractor/
├── SKILL.md                        ← Skill definition & workflow instructions
├── references/
│   ├── column_spec.md              ← 14-column output spec + colour palette
│   └── mtext_cleaning.md           ← MText formatting code stripping rules
└── scripts/
    ├── run.py                      ← Main entry point (full pipeline)
    ├── parse_xls.py                ← Step 1: read & clean XLS
    ├── detect_boards.py            ← Step 2: multi-board detection
    ├── parse_board.py              ← Step 3: per-board data extraction
    └── build_excel.py              ← Step 4: Excel output builder
```

#### Dependencies

```
xlrd       # read .xls files
openpyxl   # write .xlsx files
```

Install with:
```bash
pip install xlrd openpyxl
```

#### Tunable parameters

All configuration constants are at the top of each script:

| Parameter | Default | Purpose |
|---|---|---|
| `GAP_THRESHOLD` | `10000` | Min X gap (drawing units) to split boards |
| `Y_TOLERANCE` | `400` | Y-band ± for row matching |
| `CB_Y_BAND` | `(205790, 205870)` | Y range for CB rating rows |
| `SUBBOARD_Y_BAND` | `(199800, 200400)` | Y range for sub-board name rows |
| `CIRCUIT_PATTERN` | `^(P-\d+RYB\|\d+RYB)$` | Regex for circuit label detection |
| `CABLE_ROT` | `90` | Rotation value for cable size rows |

> If the drawing uses a non-standard coordinate system or scale, adjust `CB_Y_BAND` and `SUBBOARD_Y_BAND` to match actual Y values in the XLS.
