"""Multi-view sheet composition + ruled schedule tables.

``compose_sheet`` arranges 1, 2 or 4 ``DrawingView`` cells inside a target
box, adding a drafting-style view label bubble ("1" circle + "SECTION A-A —
1:100") and an optional per-view graphic scale bar to each cell.

``table_view`` renders a proper ruled schedule table (header band, zebra
striping, column separators, right-aligned numerics) as a ``DrawingView``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from llmbim_drawings.sheets import graphic_scale_bar, revision_cloud
from llmbim_drawings.svg_util import esc, fmt
from llmbim_drawings.view import DrawingView

# cell = (view, title, scale_note) or (view, title, scale_note, px_per_mm)
# optional 5th: max_scale (1.0 = drawn at the declared scale, no blow-up)
Cell = tuple

_LABEL_H = 28.0
# scaled drawing views (px_per_mm known) may be magnified this much to fill
# their cell; legends/tables never upscale
_MAX_UPSCALE = 2.5


def _cell_parts(cell: Cell) -> tuple[DrawingView, str, str, float | None, float]:
    view, title, scale_note = cell[0], str(cell[1]), str(cell[2])
    px_per_mm = float(cell[3]) if len(cell) > 3 and cell[3] else None
    cap = float(cell[4]) if len(cell) > 4 and cell[4] is not None else (
        _MAX_UPSCALE if px_per_mm else 1.0
    )
    return view, title, scale_note, px_per_mm, cap


def _fit_scale(view: DrawingView, w: float, h: float, cap: float) -> float:
    cw = view.width + 2 * view.pad
    ch = view.height + 2 * view.pad
    if cw <= 0 or ch <= 0:
        return 1.0
    return min(w / cw, h / ch, cap)


def _grid_for(n: int, cells: Sequence[Cell], width: float, height: float, gutter: float,
              arrange: str | None) -> tuple[int, int]:
    """(ncols, nrows) for the cell count; 2 cells pick the tighter fit."""
    if n <= 1:
        return 1, 1
    if n == 2:
        if arrange == "row":
            return 2, 1
        if arrange == "column":
            return 1, 2
        # choose orientation maximizing the worst-fitted view scale (same
        # per-cell upscale cap the renderer uses, so the choice is consistent)
        parsed = [_cell_parts(c) for c in cells]
        caps = [p[4] for p in parsed]
        row_s = min(
            _fit_scale(p[0], (width - gutter) / 2, height - _LABEL_H, cap)
            for p, cap in zip(parsed, caps, strict=True)
        )
        col_s = min(
            _fit_scale(p[0], width, (height - gutter) / 2 - _LABEL_H, cap)
            for p, cap in zip(parsed, caps, strict=True)
        )
        return (2, 1) if row_s >= col_s else (1, 2)
    return 2, 2


def _num(v: object, default: float = 0.0) -> float:
    if isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return default
    return default


def compose_sheet(
    cells: Sequence[Cell],
    *,
    width: float,
    height: float,
    gutter: float = 16.0,
    arrange: str | None = None,
    weights: Sequence[float] | None = None,
    clouds: Sequence[Mapping[str, object]] | None = None,
) -> DrawingView:
    """Arrange 1–4 view cells in a grid; label bubble + scale bar per cell.

    ``arrange``: force ``"row"`` / ``"column"`` for 2 cells (default: auto by
    aspect). ``weights``: relative sizes along the primary axis of a single
    row or column (e.g. ``[0.72, 0.28]`` for plan + legend).

    ``clouds`` (WP-CD-ANATOMY): revision annotations drawn on top of the
    composed sheet — each mapping gives ``x``/``y``/``w``/``h`` (sheet
    coordinates) and an optional ``number`` (default ``"1"``); rendered as a
    scalloped revision cloud with a numbered Δ triangle. Default ``None`` →
    output unchanged.
    """
    if not cells:
        raise ValueError("compose_sheet needs at least one cell")
    if len(cells) > 4:
        cells = list(cells)[:4]
    n = len(cells)
    ncols, nrows = _grid_for(n, cells, width, height, gutter, arrange)

    # cell rectangles
    rects: list[tuple[float, float, float, float]] = []
    if weights is not None and (ncols == 1 or nrows == 1) and len(weights) == n:
        total = sum(weights) or 1.0
        fr = [wt / total for wt in weights]
        if nrows == 1:
            avail = width - gutter * (n - 1)
            x = 0.0
            for f in fr:
                w = avail * f
                rects.append((x, 0.0, w, height))
                x += w + gutter
        else:
            avail = height - gutter * (n - 1)
            y = 0.0
            for f in fr:
                h = avail * f
                rects.append((0.0, y, width, h))
                y += h + gutter
    else:
        cell_w = (width - gutter * (ncols - 1)) / ncols
        cell_h = (height - gutter * (nrows - 1)) / nrows
        for i in range(n):
            r, c = divmod(i, ncols)
            rects.append((c * (cell_w + gutter), r * (cell_h + gutter), cell_w, cell_h))

    parts: list[str] = []
    for i, (cell, (cx, cy, cw, ch)) in enumerate(zip(cells, rects, strict=True), start=1):
        view, title, scale_note, px_per_mm, cap = _cell_parts(cell)
        # scaled drawing views may upscale to fill the cell unless the cell
        # already declared its own scale (EQ arrangements: max_scale=1).
        s, body = view.scaled_to_fit(
            cw - 4, ch - _LABEL_H, pad=4, max_scale=cap
        )
        parts.append(f'<g class="view-cell" transform="translate({fmt(cx)},{fmt(cy)})">')
        parts.append(body)
        # view label bubble bottom-left
        by = ch - 13
        label = title.upper()
        if scale_note:
            label = f"{label} — {scale_note}"
        parts.append('  <g class="view-label" font-family="sans-serif">')
        parts.append(
            f'    <circle cx="14" cy="{fmt(by)}" r="11" fill="#fff" stroke="#111" '
            f'stroke-width="1.6"/>'
        )
        parts.append(
            f'    <text x="14" y="{fmt(by + 4)}" text-anchor="middle" font-size="12" '
            f'font-weight="bold">{i}</text>'
        )
        parts.append(
            f'    <text x="32" y="{fmt(by + 3)}" font-size="11" font-weight="bold" '
            f'letter-spacing="0.6">{esc(label)}</text>'
        )
        parts.append(
            f'    <line x1="28" y1="{fmt(by + 9)}" x2="{fmt(min(cw - 4, 32 + 7.2 * len(label)))}" '
            f'y2="{fmt(by + 9)}" stroke="#111" stroke-width="1.4"/>'
        )
        parts.append("  </g>")
        if px_per_mm:
            # Infer imperial from scale note (e.g. 1/4" = 1'-0") so multi-view
            # elev/section cells get ft bars without a units plumb-through.
            sn_l = scale_note.lower()
            cell_units = (
                "imperial"
                if ("'" in scale_note or "ft" in sn_l or '="' in sn_l or "in" in sn_l)
                else "metric"
            )
            parts.append(
                graphic_scale_bar(
                    px_per_mm * s,
                    x=cw - 160,
                    y=by - 2,
                    max_px=140.0,
                    units=cell_units,
                )
            )
        parts.append("</g>")
    for cloud in clouds or []:
        parts.append(
            revision_cloud(
                _num(cloud.get("x")),
                _num(cloud.get("y")),
                _num(cloud.get("w"), 60.0),
                _num(cloud.get("h"), 40.0),
                number=str(cloud.get("number") or "1"),
            )
        )
    return DrawingView(width=width, height=height, body="\n".join(parts))


def legend_view(
    rows: Sequence[tuple[str, str]],
    *,
    title: str = "LEGEND",
    row_h: float = 18.0,
    symbol_w: float = 36.0,
    width: float = 230.0,
    font_size: float = 9.5,
) -> DrawingView:
    """Legend block: bordered box of symbol + label rows (WP-CD-ANATOMY).

    Each row is ``(symbol_svg, label)`` where ``symbol_svg`` is a raw SVG
    snippet drawn in a local cell space of roughly ``0..symbol_w`` wide by
    ``0..row_h`` tall (e.g. ``'<circle cx="12" cy="9" r="6" fill="none"
    stroke="#111"/>'``). Returns a ``DrawingView`` usable as a
    ``compose_sheet`` cell by any sheet register.
    """
    title_h = 22.0 if title else 0.0
    h = title_h + row_h * max(1, len(rows)) + 8.0
    parts = [
        '<g class="legend-block" font-family="sans-serif">',
        f'  <rect x="0" y="0" width="{fmt(width)}" height="{fmt(h)}" fill="#fff" '
        f'stroke="#111" stroke-width="1.2"/>',
    ]
    if title:
        parts.append(
            f'  <text x="8" y="15" font-size="10" font-weight="bold" '
            f'letter-spacing="0.8">{esc(title)}</text>'
        )
        parts.append(
            f'  <line x1="0" y1="{fmt(title_h)}" x2="{fmt(width)}" y2="{fmt(title_h)}" '
            f'stroke="#111" stroke-width="0.8"/>'
        )
    y = title_h + 4.0
    for symbol, label in rows:
        parts.append(
            f'  <g class="legend-symbol" transform="translate(8,{fmt(y)})">{symbol}</g>'
        )
        parts.append(
            f'  <text x="{fmt(symbol_w + 16)}" y="{fmt(y + row_h / 2 + font_size * 0.35)}" '
            f'font-size="{fmt(font_size)}">{esc(label)}</text>'
        )
        y += row_h
    parts.append("</g>")
    return DrawingView(width=width, height=h, body="\n".join(parts), title=title)


def _is_num(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        float(str(value).replace(",", ""))
        return True
    except ValueError:
        return False


def _cell_text(value: object) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


# Verseon schedule (MB-INT-SHEET-TABLE-001): Arch-E 42" → 1100 SVG units.
_VERSEON_PX_PER_IN = 1100.0 / 42.0
_VERSEON_ROW = 0.200 * _VERSEON_PX_PER_IN
_VERSEON_HDR = 1.050 * _VERSEON_PX_PER_IN
_VERSEON_TITLE = 0.280 * _VERSEON_PX_PER_IN
_VERSEON_FS = (1.0 / 16.0) * _VERSEON_PX_PER_IN  # 1/16″
_VERSEON_INK = "#2c2c2a"
_VERSEON_FONT = "Century Gothic, CenturyGothic, Questrial, sans-serif"


def verseon_table_view(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    *,
    title: str = "",
    width_px: float = 340.0,
) -> DrawingView:
    """Verseon schedule: rotated headers, no fill, no zebra, no stretch.

    Row pitch and header height are plotted inches (0.200″ / 1.050″).
    Height follows row count — never scaled to fill the cell.
    """
    ncols = max(len(headers), 1)
    texts: list[list[str]] = [[_cell_text(v) for v in row[:ncols]] for row in rows]
    for t in texts:
        while len(t) < ncols:
            t.append("—")
    scores: list[float] = []
    for c in range(ncols):
        mx = 4
        for t in texts[:80]:
            mx = max(mx, len(t[c]))
        if c == 0:
            mx = min(mx, 16)
        scores.append(max(5.0, float(mx)))
    total = sum(scores) or 1.0
    shares = [s / total for s in scores]
    widths = [width_px * s for s in shares]
    x_edges = [0.0]
    for w in widths:
        x_edges.append(x_edges[-1] + w)
    title_h = _VERSEON_TITLE if title else 0.0
    n = max(len(texts), 1)
    total_h = title_h + _VERSEON_HDR + n * _VERSEON_ROW
    parts: list[str] = [
        f'<g class="verseon-table" font-family="{_VERSEON_FONT}" '
        f'fill="{_VERSEON_INK}" stroke="{_VERSEON_INK}">'
    ]
    if title:
        parts.append(
            f'  <text x="{fmt(width_px / 2)}" y="{fmt(title_h * 0.72)}" '
            f'text-anchor="middle" font-size="{fmt(_VERSEON_FS * 1.5)}">'
            f"{esc(str(title)[:72].upper())}</text>"
        )
    y0 = title_h
    # rotated headers — no filled band
    x = 0.0
    for c, htxt in enumerate(headers):
        cx = x + widths[c] / 2.0
        hy = y0 + _VERSEON_HDR - 4.0
        label = str(htxt).replace("\n", " ").strip().upper()
        parts.append(
            f'  <text transform="translate({fmt(cx)},{fmt(hy)}) rotate(-90)" '
            f'text-anchor="start" dominant-baseline="middle" '
            f'font-size="{fmt(_VERSEON_FS)}">{esc(label[:28])}</text>'
        )
        x += widths[c]
    # body rows at fixed pitch
    yr = y0 + _VERSEON_HDR
    for t in texts:
        for c in range(ncols):
            char_w = _VERSEON_FS * 0.62
            max_chars = max(3, int((widths[c] - 4) / max(char_w, 0.4)))
            text = t[c]
            if len(text) > max_chars:
                text = text[: max_chars - 1] + "…"
            hdr = str(headers[c]).upper()
            left = c == 0 or any(
                k in hdr for k in ("NAME", "ROOM", "DESC", "REMARK", "NOTE",
                                   "DUTY", "TITLE", "MODULE", "BASIS")
            )
            if left:
                tx, anchor = x_edges[c] + 2.0, "start"
            else:
                tx, anchor = x_edges[c] + widths[c] / 2.0, "middle"
            parts.append(
                f'  <text x="{fmt(tx)}" y="{fmt(yr + _VERSEON_ROW * 0.72)}" '
                f'text-anchor="{anchor}" font-size="{fmt(_VERSEON_FS)}">'
                f"{esc(text)}</text>"
            )
        yr += _VERSEON_ROW
        parts.append(
            f'  <line x1="0" y1="{fmt(yr)}" x2="{fmt(width_px)}" y2="{fmt(yr)}" '
            f'stroke-width="0.35" fill="none"/>'
        )
    # column rules + outer box (hairline, no fill)
    for xe in x_edges[1:-1]:
        parts.append(
            f'  <line x1="{fmt(xe)}" y1="{fmt(y0)}" x2="{fmt(xe)}" y2="{fmt(yr)}" '
            f'stroke-width="0.35" fill="none"/>'
        )
    parts.append(
        f'  <line x1="0" y1="{fmt(y0 + _VERSEON_HDR)}" x2="{fmt(width_px)}" '
        f'y2="{fmt(y0 + _VERSEON_HDR)}" stroke-width="0.7" fill="none"/>'
    )
    parts.append(
        f'  <rect x="0" y="{fmt(y0)}" width="{fmt(width_px)}" '
        f'height="{fmt(yr - y0)}" fill="none" stroke-width="0.7"/>'
    )
    parts.append("</g>")
    return DrawingView(
        width=width_px + 4, height=total_h + 4, body="\n".join(parts), title=title
    )


def table_view(
    headers: Sequence[str],
    rows: Sequence[Sequence[object]],
    col_widths: Sequence[float] | None = None,
    *,
    title: str = "",
    font_size: float = 9.5,
    row_h: float = 16.0,
) -> DrawingView:
    """Ruled schedule table: header band, zebra rows, right-aligned numerics."""
    ncols = len(headers)
    char_w = font_size * 0.62
    texts: list[list[str]] = [[_cell_text(v) for v in row[:ncols]] for row in rows]
    for t in texts:
        while len(t) < ncols:
            t.append("—")
    if col_widths is None:
        widths = []
        for c in range(ncols):
            longest = max([len(str(headers[c]))] + [len(t[c]) for t in texts] or [4])
            widths.append(min(260.0, max(48.0, longest * char_w + 14.0)))
    else:
        widths = [float(w) for w in col_widths[:ncols]]
        while len(widths) < ncols:
            widths.append(80.0)
    # right-align columns whose data is (mostly) numeric
    num_col = [
        bool(texts) and all(_is_num(t[c]) or t[c] == "—" for t in texts)
        and any(_is_num(t[c]) for t in texts)
        for c in range(ncols)
    ]

    total_w = sum(widths)
    header_h = row_h + 4
    title_h = 26.0 if title else 0.0
    total_h = title_h + header_h + row_h * max(1, len(texts))

    x_edges = [0.0]
    for w in widths:
        x_edges.append(x_edges[-1] + w)

    parts: list[str] = ['<g class="schedule-table" font-family="sans-serif">']
    y0 = title_h
    if title:
        parts.append(
            f'  <text x="0" y="16" font-size="14" font-weight="bold">{esc(title)}</text>'
        )
    # header band
    parts.append(
        f'  <rect x="0" y="{fmt(y0)}" width="{fmt(total_w)}" height="{fmt(header_h)}" '
        f'fill="#dfe3e8" stroke="none"/>'
    )
    for c, htxt in enumerate(headers):
        if num_col[c]:
            tx, anchor = x_edges[c + 1] - 6, "end"
        else:
            tx, anchor = x_edges[c] + 6, "start"
        parts.append(
            f'  <text x="{fmt(tx)}" y="{fmt(y0 + header_h - 6)}" text-anchor="{anchor}" '
            f'font-size="{fmt(font_size)}" font-weight="bold">{esc(str(htxt))}</text>'
        )
    # zebra rows + cell text
    yr = y0 + header_h
    for r, t in enumerate(texts):
        if r % 2 == 1:
            parts.append(
                f'  <rect x="0" y="{fmt(yr)}" width="{fmt(total_w)}" height="{fmt(row_h)}" '
                f'fill="#f2f5f7" stroke="none"/>'
            )
        for c in range(ncols):
            max_chars = max(3, int((widths[c] - 12) / char_w))
            text = t[c]
            if len(text) > max_chars:
                text = text[: max_chars - 1] + "…"
            if num_col[c]:
                tx, anchor = x_edges[c + 1] - 6, "end"
            else:
                tx, anchor = x_edges[c] + 6, "start"
            parts.append(
                f'  <text x="{fmt(tx)}" y="{fmt(yr + row_h - 4.5)}" text-anchor="{anchor}" '
                f'font-size="{fmt(font_size)}">{esc(text)}</text>'
            )
        yr += row_h
        parts.append(
            f'  <line x1="0" y1="{fmt(yr)}" x2="{fmt(total_w)}" y2="{fmt(yr)}" '
            f'stroke="#c3c9cf" stroke-width="0.5"/>'
        )
    # column separators
    for xe in x_edges[1:-1]:
        parts.append(
            f'  <line x1="{fmt(xe)}" y1="{fmt(y0)}" x2="{fmt(xe)}" y2="{fmt(yr)}" '
            f'stroke="#aab2ba" stroke-width="0.6"/>'
        )
    # header rule + outer border
    parts.append(
        f'  <line x1="0" y1="{fmt(y0 + header_h)}" x2="{fmt(total_w)}" '
        f'y2="{fmt(y0 + header_h)}" stroke="#111" stroke-width="1.2"/>'
    )
    parts.append(
        f'  <rect x="0" y="{fmt(y0)}" width="{fmt(total_w)}" height="{fmt(yr - y0)}" '
        f'fill="none" stroke="#111" stroke-width="1.2"/>'
    )
    parts.append("</g>")
    return DrawingView(
        width=total_w + 4, height=total_h + 6, body="\n".join(parts), title=title
    )
