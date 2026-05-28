# ELE-SHC-MAKER

A collection of Claude Code skills for electrical engineering document workflows.

---

## Skills

### `ee-shc-extractor` — Electrical Switchboard Schedule Extractor

Converts **DWG Data Extraction XLS files** (exported from AutoCAD electrical schematics) into formatted **Load Schedule Excel workbooks** (`.xlsx`), one worksheet per distribution board.

#### Two input paths

| Path | Source | Stage 1 | Stage 2 |
|---|---|---|---|
| **DXF** (preferred) | Save DWG → `.dxf` (all panels in one file) | `run_clean.py` → **clean review `.xlsx`** | `run_loadschedule.py` → **Load Schedule workbook** |
| **XLS** (legacy) | AutoCAD Data Extraction `.xls` per panel | — | `run.py` / `run_multi.py` → Load Schedule |

The **DXF path** removes the manual, per-panel Data Extraction step: it reads one
DXF, splits cabinets by their **real border rectangles**, and writes a single
**clean review workbook** — a per-circuit summary table per cabinet, separated by
cabinet headers — so the cabinet split can be verified before the Load Schedule is
built.

##### clean `.xlsx` → Load Schedule workbook (Stage 2)

```bash
python scripts/run_loadschedule.py <clean.xlsx> [--output LoadSchedule.xlsx]
```

Reads the **(user-reviewed/edited)** clean workbook from Stage 1 and produces the
final workbook. Stage 2 is **round-trippable**: it never invents data — whatever
the user fills into the clean file (load names, Connected Load kW, Demand Factor)
flows straight through; anything missing stays blank/flagged `⚠️`.

| Step | Script | Action |
|---|---|---|
| 1 | `read_clean_xlsx.py` | Parses the clean workbook back into board dicts (keys off the `CABINET:` markers + labelled header cells + fixed circuit columns) |
| 2 | `build_loadschedule.py` | Builds the workbook: **INDEX** sheet (clickable list of cabinets) + **DIAGRAM** sheet (clickable box tree of the supply hierarchy) + **one Load Schedule sheet per cabinet** (reuses `build_excel._build_sheet`, adds `=G*H` Max-Demand formulas and ← INDEX nav) |

Output: `INDEX` and `DIAGRAM` first, then one tab per board; every Board ID /
diagram box is an internal hyperlink, and each board title bar links back to `INDEX`.

##### DXF → clean `.xlsx` (Stage 1)

```bash
python scripts/run_clean.py <input.dxf> [more.dxf ...] [--output out.xlsx]
```

| Step | Script | Action |
|---|---|---|
| 1 | `parse_dxf.py` | Reads DXF via **ezdxf**; `MTEXT.plain_text()` strips formatting codes natively; resolves the effective MTEXT rotation from its `text_direction` vector; drops single-char symbol noise (layer `0`) |
| 2 | `detect_panels.py` | Detects each cabinet's **border rectangle** (large `LWPOLYLINE`) and assigns every text entity to the frame that contains it (falls back to legacy X-gap clustering if no frame is found) |
| 3 | `parse_board.py` | (reused) extracts board ID, supply, incomer, CB ratings, cable sizes, accessories per cabinet |
| 4 | `build_clean_xlsx.py` | Writes **one sheet**: per-cabinet header bar + info line, then a per-circuit table; SPARE rows flagged; blank spacer between cabinets |

Requires `ezdxf` (`pip install ezdxf`).

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
    ├── run_clean.py                ← Stage 1 entry: DXF → clean review .xlsx
    ├── parse_dxf.py                ← Stage 1: read & clean DXF via ezdxf
    ├── detect_panels.py            ← Stage 1: cabinet split by border rectangle
    ├── build_clean_xlsx.py         ← Stage 1: clean review workbook (round-trippable)
    ├── run_loadschedule.py         ← Stage 2 entry: clean .xlsx → Load Schedule workbook
    ├── read_clean_xlsx.py          ← Stage 2: parse clean .xlsx → board dicts
    ├── build_loadschedule.py       ← Stage 2: INDEX + DIAGRAM + per-board sheets
    ├── run.py                      ← XLS path entry (full Load Schedule pipeline)
    ├── run_multi.py                ← XLS path: combine multiple XLS into one workbook
    ├── parse_xls.py                ← XLS: read & clean
    ├── detect_boards.py            ← XLS: X-gap multi-board detection
    ├── parse_board.py              ← shared: per-board data extraction
    └── build_excel.py              ← shared: per-board sheet + sheet_name() helper
```

#### Dependencies

```
ezdxf      # read .dxf files (DXF path)
xlrd       # read .xls files (legacy XLS path)
openpyxl   # write .xlsx files
```

Install with:
```bash
pip install ezdxf xlrd openpyxl
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
