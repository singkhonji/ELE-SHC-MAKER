# MText Formatting Code — Stripping Rules

AutoCAD MText entities embed RTF-like formatting codes in the `Contents`
column. These must be stripped to recover plain text.

## Cleaning Order (apply in sequence)

```python
import re

def clean_mtext(raw: str) -> str:
    s = str(raw)

    # 1. Calibri font block with size modifier: {\fCalibri|...; \H0.9x; TEXT}
    #    → keep TEXT only
    s = re.sub(r'\{\\fCalibri[^;]+;\\H[^;]+;([^}]+)\}', r'\1', s)

    # 2. Arial superscript² reference: {\fArial|b0|i0|c134|p32;² \Fromans.shx|c0;
    #    → replace with literal ²
    s = re.sub(
        r'\{\\fArial\|b0\|i0\|c134\|p32;² \\Fromans\.shx\|c0;',
        '² ', s
    )

    # 3. Generic font blocks: {\fFontName|...} → strip
    s = re.sub(r'\{\\f[^}]*\}', '', s)

    # 4. Width scaling block: {\W1.0; TEXT} → keep TEXT
    s = re.sub(r'\{\\W[\d.]+;([^}]*)\}', r'\1', s)

    # 5. Remaining brace blocks → strip
    s = re.sub(r'\{[^{}]*\}', '', s)

    # 6. Paragraph/positioning codes: \pxsa0.78,qc; etc. → strip
    s = re.sub(r'\\px[^;]+;', '', s)

    # 7. Height/width/alignment codes: \H0.9x; \W0.7; \A1; → strip
    s = re.sub(r'\\[HWA]\d*[.\dx]*;?', '', s)

    # 8. Paragraph breaks: \\P and \P → single space
    s = re.sub(r'\\\\P|\\P', ' ', s)

    # 9. Remaining backslash codes → strip
    s = re.sub(r'\\[a-zA-Z*]+;?', '', s)

    # 10. Orphan font file remnants: .shx|c0; → strip
    s = re.sub(r'\.shx\|c0;', '', s)

    # 11. Orphan closing braces → strip
    s = re.sub(r'\}', '', s)

    # 12. Normalise whitespace
    s = re.sub(r'\s+', ' ', s).strip()

    return s
```

## Known Patterns & Expected Output

| Raw Contents | Expected Output |
|---|---|
| `63A\\PTPN  MCCB\\P36KA` | `63A TPN MCCB 36KA` |
| `{\\fCalibri\|b0\|i0\|c0\|p34;\\H0.91667x;D1-MDB-COM-FOH1A-A}` | `D1-MDB-COM-FOH1A-A` |
| `\\A1;4 x 1C 70mm{\\fArial\|b0\|i0\|c134\|p32;² \\Fromans.shx\|c0;XLPE/LSZH CU + }...` | `4 x 1C 70mm² XLPE/LSZH CU + 1C 35mm² CU CPC ON CABLE LADDER / TRAY` |
| `{\\W1;\\fArial\|b0\|i0\|c0\|p34;8/20\\H1.08333x;µS...TYPE 2, In≥40KA...IEC61643}` | `8/20µS TYPE 2, In≥40KA ACCORDING TO IEC61643` |
| `\\pxsa0.78,qc;{\\L400AT\\P}400AF\\P\\ps*;TPN MCCB\\P50kA L,S,I` | `400AT 400AF TPN MCCB 50kA L,S,I` |
| `\\pxqc;L1` | `L1` |
| `\\pxsm0.8,ql;ZCT` | `ZCT` |

## Noise Filtering

After cleaning, discard any row where `len(text.strip()) <= 1`.  
This removes single-character artifacts from electrical symbol blocks
(e.g. letters `E`, `F`, `C`, `O` that form part of a graphical CB symbol).

## Unicode Superscript ²

The superscript ² character (U+00B2) is embedded via a special font
substitution block. After applying rule #2, it appears as `²` inline with
the cable size text. Verify output contains `mm²` not `mm2` or `mm`.
