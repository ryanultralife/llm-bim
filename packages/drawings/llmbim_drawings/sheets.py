"""Professional sheet frame: bordered CD sheet with zone ticks + title column.

``title_block_svg`` wraps a drawing body in a construction-document frame:

- outer border with margin-zone reference ticks (letters across top/bottom,
  numbers down the sides — standard CD-sheet zone referencing),
- a right-side vertical title block column (project, title, sheet number,
  scale/date, drawn/checked/approved, revision table, honesty stamp),
- an optional graphic scale bar (from the sheet's actual view scale) and an
  optional north-arrow glyph for plan sheets.
"""

from __future__ import annotations

import datetime as _dt
from xml.sax.saxutils import escape

from llmbim_drawings.svg_util import fmt

# Frame geometry (SVG user units). Exposed so callers can size views to fit.
SHEET_MARGIN = 20.0
TITLE_BLOCK_W = 180.0


def drawing_area(sheet_w: float = 1100, sheet_h: float = 850) -> tuple[float, float, float, float]:
    """(x, y, w, h) of the usable drawing area inside border + title column."""
    x = SHEET_MARGIN + 10
    y = SHEET_MARGIN + 10
    w = sheet_w - 2 * SHEET_MARGIN - TITLE_BLOCK_W - 20
    h = sheet_h - 2 * SHEET_MARGIN - 20
    return x, y, w, h


def graphic_scale_bar(
    px_per_mm: float,
    *,
    x: float = 0.0,
    y: float = 0.0,
    max_px: float = 140.0,
    segments: int = 4,
) -> str:
    """Alternating black/white graphic scale bar sized from real view scale.

    ``px_per_mm``: on-sheet SVG units per model millimetre. Picks a round
    real-world segment length so the whole bar fits inside ``max_px``.
    """
    if px_per_mm <= 0:
        return ""
    candidates = [
        50.0, 100.0, 200.0, 250.0, 500.0, 1000.0, 2000.0,
        2500.0, 5000.0, 10000.0, 20000.0, 25000.0, 50000.0,
    ]
    seg_mm = candidates[0]
    for c in candidates:
        if c * segments * px_per_mm <= max_px:
            seg_mm = c
    seg_px = seg_mm * px_per_mm
    bar_h = 6.0
    total_mm = seg_mm * segments
    use_m = total_mm >= 1000.0

    def _lab(mm: float) -> str:
        if use_m:
            v = mm / 1000.0
            return f"{v:g}"
        return f"{mm:g}"

    parts = ['<g class="scale-bar" font-family="sans-serif" font-size="7" fill="#111">']
    for i in range(segments):
        fill = "#111" if i % 2 == 0 else "#fff"
        parts.append(
            f'  <rect x="{fmt(x + i * seg_px)}" y="{fmt(y)}" width="{fmt(seg_px)}" '
            f'height="{fmt(bar_h)}" fill="{fill}" stroke="#111" stroke-width="0.8"/>'
        )
    # tick labels at 0, mid, end + unit
    for i in (0, segments // 2, segments):
        parts.append(
            f'  <text x="{fmt(x + i * seg_px)}" y="{fmt(y - 2.5)}" '
            f'text-anchor="middle">{_lab(i * seg_mm)}</text>'
        )
    unit = "m" if use_m else "mm"
    parts.append(
        f'  <text x="{fmt(x + segments * seg_px + 4)}" y="{fmt(y + bar_h)}" '
        f'text-anchor="start">{unit}</text>'
    )
    parts.append("</g>")
    return "\n".join(parts)


def north_arrow_glyph(x: float, y: float, r: float = 16.0) -> str:
    """North-arrow symbol: circle + solid half-needle + N."""
    return "\n".join(
        [
            '<g class="north-arrow" stroke="#111" fill="none" stroke-width="1.2">',
            f'  <circle cx="{fmt(x)}" cy="{fmt(y)}" r="{fmt(r)}"/>',
            f'  <polygon points="{fmt(x)},{fmt(y - r * 0.78)} {fmt(x + r * 0.3)},{fmt(y + r * 0.45)} '
            f'{fmt(x)},{fmt(y + r * 0.15)}" fill="#111" stroke="none"/>',
            f'  <polygon points="{fmt(x)},{fmt(y - r * 0.78)} {fmt(x - r * 0.3)},{fmt(y + r * 0.45)} '
            f'{fmt(x)},{fmt(y + r * 0.15)}" fill="#fff"/>',
            f'  <text x="{fmt(x)}" y="{fmt(y - r - 3)}" text-anchor="middle" font-size="9" '
            f'font-family="sans-serif" font-weight="bold" fill="#111" stroke="none">N</text>',
            "</g>",
        ]
    )


def _zone_ticks(sheet_w: float, sheet_h: float, margin: float) -> str:
    """Margin-zone reference grid: letters across top/bottom, numbers down sides."""
    inner_w = sheet_w - 2 * margin
    inner_h = sheet_h - 2 * margin
    cols = max(2, int(round(inner_w / 180.0)))
    rows = max(2, int(round(inner_h / 180.0)))
    parts = [
        '<g class="zone-ticks" stroke="#111" stroke-width="0.8" '
        'font-family="sans-serif" font-size="9" fill="#111">'
    ]
    # column boundaries + letters (top and bottom margin strips)
    for i in range(cols + 1):
        x = margin + inner_w * i / cols
        if 0 < i < cols:
            parts.append(f'  <line x1="{fmt(x)}" y1="0" x2="{fmt(x)}" y2="{fmt(margin)}"/>')
            parts.append(
                f'  <line x1="{fmt(x)}" y1="{fmt(sheet_h - margin)}" '
                f'x2="{fmt(x)}" y2="{fmt(sheet_h)}"/>'
            )
    for i in range(cols):
        cx = margin + inner_w * (i + 0.5) / cols
        letter = chr(ord("A") + (i % 26))
        parts.append(
            f'  <text x="{fmt(cx)}" y="{fmt(margin * 0.5 + 3)}" text-anchor="middle" '
            f'stroke="none">{letter}</text>'
        )
        parts.append(
            f'  <text x="{fmt(cx)}" y="{fmt(sheet_h - margin * 0.5 + 3)}" '
            f'text-anchor="middle" stroke="none">{letter}</text>'
        )
    # row boundaries + numbers (left and right margin strips)
    for j in range(rows + 1):
        y = margin + inner_h * j / rows
        if 0 < j < rows:
            parts.append(f'  <line x1="0" y1="{fmt(y)}" x2="{fmt(margin)}" y2="{fmt(y)}"/>')
            parts.append(
                f'  <line x1="{fmt(sheet_w - margin)}" y1="{fmt(y)}" '
                f'x2="{fmt(sheet_w)}" y2="{fmt(y)}"/>'
            )
    for j in range(rows):
        cy = margin + inner_h * (j + 0.5) / rows + 3
        parts.append(
            f'  <text x="{fmt(margin * 0.5)}" y="{fmt(cy)}" text-anchor="middle" '
            f'stroke="none">{j + 1}</text>'
        )
        parts.append(
            f'  <text x="{fmt(sheet_w - margin * 0.5)}" y="{fmt(cy)}" text-anchor="middle" '
            f'stroke="none">{j + 1}</text>'
        )
    parts.append("</g>")
    return "\n".join(parts)


def _trunc(text: str, n: int) -> str:
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


def title_block_svg(
    *,
    sheet_w: float = 1100,
    sheet_h: float = 850,
    project: str,
    sheet_title: str,
    sheet_no: str,
    scale_note: str = "NTS",
    notes: str = "",
    body: str,
    date: str | None = None,
    drawn_by: str = "LLM-BIM agent",
    checked_by: str = "—",
    approved_by: str = "—",
    revisions: list[tuple[str, str, str]] | None = None,
    px_per_mm: float | None = None,
    north_arrow: bool = False,
) -> str:
    """Wrap drawing body in a CD-style frame with right-side title column.

    Backward compatible with the legacy bottom-strip signature; the new
    keyword-only params are all optional. ``px_per_mm`` (on-sheet units per
    model mm, i.e. view scale × fit factor) enables the graphic scale bar.
    """
    margin = SHEET_MARGIN
    tb_w = TITLE_BLOCK_W
    if date is None:
        date = _dt.date.today().isoformat()
    if revisions is None:
        revisions = [("0", "ISSUED FOR REVIEW", date)]

    tb_x = sheet_w - margin - tb_w
    tb_y = margin
    tb_h = sheet_h - 2 * margin
    cx = tb_x + tb_w / 2  # centered text x within the column
    pad_x = tb_x + 8

    blocks: list[str] = ['<g class="title-column" font-family="sans-serif">']

    def hline(y: float, w_: float = 1.0) -> None:
        blocks.append(
            f'  <line x1="{fmt(tb_x)}" y1="{fmt(y)}" x2="{fmt(tb_x + tb_w)}" '
            f'y2="{fmt(y)}" stroke="#111" stroke-width="{fmt(w_)}"/>'
        )

    def caption(x: float, y: float, text: str) -> None:
        blocks.append(
            f'  <text x="{fmt(x)}" y="{fmt(y)}" font-size="6.5" fill="#555" '
            f'letter-spacing="0.5">{escape(text)}</text>'
        )

    y = tb_y
    # ── project / logo block
    y += 22
    blocks.append(
        f'  <text x="{fmt(cx)}" y="{fmt(y)}" text-anchor="middle" font-size="15" '
        f'font-weight="bold" letter-spacing="1.5">LLM·BIM</text>'
    )
    y += 12
    caption(pad_x, y, "PROJECT")
    y += 13
    blocks.append(
        f'  <text x="{fmt(cx)}" y="{fmt(y)}" text-anchor="middle" font-size="11" '
        f'font-weight="bold">{escape(_trunc(project, 28))}</text>'
    )
    y += 12
    hline(y)

    # ── sheet title block
    y += 11
    caption(pad_x, y, "TITLE")
    y += 15
    blocks.append(
        f'  <text x="{fmt(cx)}" y="{fmt(y)}" text-anchor="middle" font-size="12" '
        f'font-weight="bold">{escape(_trunc(sheet_title, 26))}</text>'
    )
    y += 10
    hline(y)

    # ── scale / date row (two cells)
    y_top = y
    y += 11
    caption(pad_x, y, "SCALE")
    caption(tb_x + tb_w / 2 + 6, y, "DATE")
    y += 14
    blocks.append(
        f'  <text x="{fmt(pad_x)}" y="{fmt(y)}" font-size="9.5">'
        f"{escape(_trunc(scale_note, 14))}</text>"
    )
    blocks.append(
        f'  <text x="{fmt(tb_x + tb_w / 2 + 6)}" y="{fmt(y)}" font-size="9.5">'
        f"{escape(date)}</text>"
    )
    y += 8
    blocks.append(
        f'  <line x1="{fmt(tb_x + tb_w / 2)}" y1="{fmt(y_top)}" x2="{fmt(tb_x + tb_w / 2)}" '
        f'y2="{fmt(y)}" stroke="#111" stroke-width="0.7"/>'
    )
    hline(y)

    # ── drawn / checked / approved rows
    for label, value in (
        ("DRAWN", drawn_by),
        ("CHECKED", checked_by),
        ("APPROVED", approved_by),
    ):
        y += 13
        caption(pad_x, y, label)
        blocks.append(
            f'  <text x="{fmt(tb_x + 66)}" y="{fmt(y)}" font-size="8.5">'
            f"{escape(_trunc(value, 20))}</text>"
        )
        y += 4
        hline(y, 0.5)
    hline(y)

    # ── revision table (header + 4 rows)
    y += 11
    caption(pad_x, y, "REVISIONS")
    y += 4
    hline(y, 0.5)
    rev_col1 = tb_x + 24
    rev_col2 = tb_x + tb_w - 52
    rev_rows: list[tuple[str, str, str]] = list(revisions[:4])
    while len(rev_rows) < 4:
        rev_rows.append(("", "", ""))
    rev_top = y
    blocks.append('  <g class="rev-table" font-size="7.5">')
    for rev, desc, rdate in rev_rows:
        y += 12
        blocks.append(
            f'    <text x="{fmt(tb_x + 12)}" y="{fmt(y)}" text-anchor="middle">'
            f"{escape(_trunc(rev, 3))}</text>"
        )
        blocks.append(
            f'    <text x="{fmt(rev_col1 + 4)}" y="{fmt(y)}">'
            f"{escape(_trunc(desc, 22))}</text>"
        )
        blocks.append(
            f'    <text x="{fmt(rev_col2 + 3)}" y="{fmt(y)}">'
            f"{escape(_trunc(rdate, 10))}</text>"
        )
        y += 3
        hline(y, 0.4)
    blocks.append("  </g>")
    for vx in (rev_col1, rev_col2):
        blocks.append(
            f'  <line x1="{fmt(vx)}" y1="{fmt(rev_top)}" x2="{fmt(vx)}" y2="{fmt(y)}" '
            f'stroke="#111" stroke-width="0.4"/>'
        )
    hline(y)

    # ── honesty stamp
    y += 8
    stamp_h = 46
    blocks.append(
        f'  <g class="honesty-stamp">'
        f'<rect x="{fmt(tb_x + 8)}" y="{fmt(y)}" width="{fmt(tb_w - 16)}" '
        f'height="{fmt(stamp_h)}" fill="none" stroke="#8a1a1a" stroke-width="1.4"/>'
    )
    blocks.append(
        f'  <text x="{fmt(cx)}" y="{fmt(y + 15)}" text-anchor="middle" font-size="9.5" '
        f'font-weight="bold" fill="#8a1a1a">ENGINEERING ESTIMATE</text>'
    )
    blocks.append(
        f'  <text x="{fmt(cx)}" y="{fmt(y + 27)}" text-anchor="middle" font-size="7.5" '
        f'fill="#8a1a1a">NOT FOR CONSTRUCTION</text>'
    )
    blocks.append(
        f'  <text x="{fmt(cx)}" y="{fmt(y + 38)}" text-anchor="middle" font-size="6.5" '
        f'fill="#8a1a1a">agent-derived — verify before use</text></g>'
    )
    y += stamp_h + 8
    hline(y)

    # ── graphics cell: scale bar + north arrow
    if px_per_mm or north_arrow:
        gy = y + 26
        if px_per_mm:
            blocks.append(
                graphic_scale_bar(
                    px_per_mm,
                    x=pad_x,
                    y=gy,
                    max_px=(tb_w - 60 if north_arrow else tb_w - 34),
                )
            )
        if north_arrow:
            blocks.append(north_arrow_glyph(tb_x + tb_w - 26, gy + 2, r=13.0))
        y += 52
        hline(y)

    # ── notes strip
    y += 11
    blocks.append(
        f'  <text x="{fmt(pad_x)}" y="{fmt(y)}" font-size="6.5" fill="#444">'
        f'{escape(_trunc(notes or "LLM-BIM · agent-derived model", 44))}</text>'
    )

    # ── big sheet number box (anchored to column bottom)
    no_h = 62.0
    no_y = tb_y + tb_h - no_h
    hline(no_y)
    blocks.append('  <g class="sheet-no-box">')
    caption(pad_x, no_y + 12, "SHEET NO")
    blocks.append(
        f'  <text x="{fmt(cx)}" y="{fmt(no_y + 42)}" text-anchor="middle" font-size="26" '
        f'font-weight="bold">{escape(sheet_no)}</text>'
    )
    blocks.append(
        f'  <text x="{fmt(cx)}" y="{fmt(no_y + 56)}" text-anchor="middle" font-size="7" '
        f'fill="#666">llm-bim</text></g>'
    )
    blocks.append("</g>")
    title_column = "\n".join(blocks)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(sheet_w)}" height="{fmt(sheet_h)}"
     viewBox="0 0 {fmt(sheet_w)} {fmt(sheet_h)}">
  <rect x="0" y="0" width="{fmt(sheet_w)}" height="{fmt(sheet_h)}" fill="#f5f5f0"/>
{_zone_ticks(sheet_w, sheet_h, margin)}
  <rect x="{fmt(margin)}" y="{fmt(margin)}" width="{fmt(sheet_w - 2 * margin)}"
        height="{fmt(sheet_h - 2 * margin)}" fill="#ffffff" stroke="#111" stroke-width="2"/>
  <g transform="translate({fmt(margin + 10)},{fmt(margin + 10)})">
{body}
  </g>
  <!-- title block column -->
  <rect x="{fmt(tb_x)}" y="{fmt(tb_y)}" width="{fmt(tb_w)}" height="{fmt(tb_h)}"
        fill="#ffffff" stroke="#111" stroke-width="1.5"/>
{title_column}
</svg>
"""
