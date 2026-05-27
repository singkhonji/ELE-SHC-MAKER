# Load Schedule — 14-Column Output Specification

## Column Layout

| # | Header | Width | Align | Notes |
|---|---|---|---|---|
| 1 | Circuit No. | 11 | Center | e.g. P-1RYB, 2RYB |
| 2 | Description / Load Name | 36 | Left | Sub-board ID or SPARE |
| 3 | CB Rating (A) | 10 | Center | e.g. 63A, 160A |
| 4 | CB Type | 14 | Center | MCCB / MCCB (L,S,I) |
| 5 | No. of Poles | 9 | Center | 3P+N |
| 6 | Breaking Cap. | 10 | Center | e.g. 36kA, 50kA |
| 7 | Connected Load (kW) | 14 | Center | Blank — M&E to fill |
| 8 | Demand Factor | 11 | Center | Blank — M&E to fill |
| 9 | Max Demand (kW) | 12 | Center | Blank — M&E to fill |
| 10 | Current (A) | 10 | Center | Blank — M&E to fill |
| 11 | Cable Size | 32 | Left | Full cable spec string |
| 12 | Cable Route | 22 | Left | Cable Ladder/Tray or Trunking/Conduit |
| 13 | Remarks | 22 | Left | Flags, incomer tag, etc. |
| 14 | Status | 9 | Center | ACTIVE or SPARE |

## Section Structure (rows)

```
Row 1   : Title bar (merged A1:N1) — dark blue bg, white text, size 13
Row 2   : Subtitle (merged A2:N2) — mid blue bg, white text, size 9
Row 3-5 : Board info (6-cell pairs: Label | Value×4 | Label | Value×8)
Row 6   : Separator (solid mid-blue, height 5)
Row 7   : "SECTION A — INCOMER" (merged, mid-blue)
Row 8   : Column headers (dark blue bg, white text, wrap)
Row 9   : Incomer row (orange bg)
Row 10  : "SECTION B — OUTGOING CIRCUITS" (merged, mid-blue)
Row 11  : Column headers (repeat)
Row 12+ : One row per circuit (8 rows for 8-way board)
Next    : "SECTION C — PANEL ACCESSORIES & METERING"
Next+1  : Accessory headers
Next+2+ : One row per accessory
Last-1  : "NOTES" header (mid-blue)
Last+   : Note rows
```

## Colour Palette

| Name | Hex | Usage |
|---|---|---|
| DARK_BLUE | `1F3864` | Title bar, column headers |
| MID_BLUE | `2E75B6` | Section headers, subtitle |
| LIGHT_BLUE | `D6E4F0` | Alternating data rows (even) |
| ORANGE_BG | `FCE4D6` | Incomer row |
| SPARE_BG | `E2EFDA` | SPARE circuit rows |
| YELLOW_BG | `FFF2CC` | Warning/⚠️ note rows |
| GREY_BG | `F2F2F2` | Alternating note rows (even) |
| WHITE | `FFFFFF` | Alternating data rows (odd) |

## Font

- Font: **Arial**, size 9 throughout
- Title: size 13, bold, white
- Column headers: bold, white
- First column of each circuit row: bold
- SPARE rows: italic, grey text (`7F7F7F`)

## Page Setup

- Orientation: Landscape
- Fit to 1 page wide
- Freeze panes at A12 (below incomer + section B header)
- Tab colour: first sheet `1F3864`, additional sheets `2E75B6`
