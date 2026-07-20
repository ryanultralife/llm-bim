"""Render Schad detail ops-list DSL → SVG.

Ops (detail-local feet, x right, y up):
  ('l', x1, y1, x2, y2)           line
  ('d', x1, y1, x2, y2)           dashed line
  ('r', x, y, w, h)               rectangle
  ('c', cx, cy, r)                circle
  ('h', x, y, w, h)               hatch rect
  ('t', x, y, wrap_w, 'text')     label (wrap_w in feet ≈ paper col)

Scale: 12 = 1\"=1'-0\", 8 = 1-1/2\"=1'-0\", 16 = 3/4\"=1'-0\" (approx as px/ft).
"""

from __future__ import annotations

import html
import textwrap
from typing import Any


def _scale_to_px_per_ft(scale: float) -> float:
    # Revit used paper scale integers; map to readable SVG density
    # Higher scale number → smaller drawing (more feet per inch)
    return max(18.0, 320.0 / max(scale, 1.0))


def _wrap_label(text: str, wrap_w_ft: float, px_per_ft: float) -> list[str]:
    # wrap_w is ~column width in feet paper-space from original DSL (~0.5)
    chars = max(28, int(wrap_w_ft * 80))
    return textwrap.wrap(text, width=chars) or [""]


def render_detail_svg(
    detail: dict[str, Any],
    *,
    sheet_w: float = 900.0,
    sheet_h: float = 700.0,
    margin: float = 40.0,
) -> str:
    """Return a full SVG document for one detail dict {id, title, scale, ops}."""
    ops: list[tuple] = list(detail.get("ops") or [])
    scale = float(detail.get("scale") or 12)
    px = _scale_to_px_per_ft(scale)

    # Bounds from geometry ops (skip pure text extent for first pass)
    xs: list[float] = []
    ys: list[float] = []
    for op in ops:
        kind = op[0]
        if kind in ("l", "d"):
            xs.extend([op[1], op[3]])
            ys.extend([op[2], op[4]])
        elif kind in ("r", "h"):
            xs.extend([op[1], op[1] + op[3]])
            ys.extend([op[2], op[2] + op[4]])
        elif kind == "c":
            xs.extend([op[1] - op[3], op[1] + op[3]])
            ys.extend([op[2] - op[3], op[2] + op[3]])
        elif kind == "t":
            xs.append(op[1])
            ys.append(op[2])
    if not xs:
        xs, ys = [0.0, 1.0], [0.0, 1.0]
    min_x, max_x = min(xs) - 0.5, max(xs) + 0.5
    min_y, max_y = min(ys) - 0.5, max(ys) + 0.5
    # Expand for text to the right
    max_x = max(max_x, min_x + 8.0)
    max_y = max(max_y, min_y + 4.0)

    world_w = max_x - min_x
    world_h = max_y - min_y
    draw_w = sheet_w - 2 * margin
    draw_h = sheet_h - 2 * margin - 50  # title bar
    fit = min(draw_w / (world_w * px), draw_h / (world_h * px), 1.5)
    s = px * fit

    def tx(x: float) -> float:
        return margin + (x - min_x) * s

    def ty(y: float) -> float:
        # flip Y for SVG
        return margin + 40 + (max_y - y) * s

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{sheet_w:.0f}" '
        f'height="{sheet_h:.0f}" viewBox="0 0 {sheet_w:.0f} {sheet_h:.0f}">',
        '<rect width="100%" height="100%" fill="#faf9f6"/>',
        f'<text x="{margin}" y="28" font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="16" font-weight="700" fill="#111">'
        f'{html.escape(detail.get("id", ""))} — {html.escape(detail.get("title", ""))}'
        f"</text>",
        f'<text x="{margin}" y="46" font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="11" fill="#555">Scale index {scale} · DESIGN SUPPORT · '
        f"NOT FOR CONSTRUCTION · basis-driven ops</text>",
        '<g stroke="#1a1a1a" stroke-width="1.2" fill="none" '
        'stroke-linecap="square" stroke-linejoin="miter">',
    ]

    for op in ops:
        kind = op[0]
        if kind == "l":
            parts.append(
                f'<line x1="{tx(op[1]):.2f}" y1="{ty(op[2]):.2f}" '
                f'x2="{tx(op[3]):.2f}" y2="{ty(op[4]):.2f}"/>'
            )
        elif kind == "d":
            parts.append(
                f'<line x1="{tx(op[1]):.2f}" y1="{ty(op[2]):.2f}" '
                f'x2="{tx(op[3]):.2f}" y2="{ty(op[4]):.2f}" '
                f'stroke-dasharray="6 4"/>'
            )
        elif kind == "r":
            x, y, w, h = op[1], op[2], op[3], op[4]
            parts.append(
                f'<rect x="{tx(x):.2f}" y="{ty(y + h):.2f}" '
                f'width="{abs(w) * s:.2f}" height="{abs(h) * s:.2f}" '
                f'fill="#fff" stroke="#1a1a1a"/>'
            )
        elif kind == "h":
            x, y, w, h = op[1], op[2], op[3], op[4]
            rx, ry = tx(x), ty(y + h)
            rw, rh = abs(w) * s, abs(h) * s
            parts.append(
                f'<rect x="{rx:.2f}" y="{ry:.2f}" width="{rw:.2f}" height="{rh:.2f}" '
                f'fill="#e8e4dc" stroke="#1a1a1a"/>'
            )
            # simple hatch
            step = 6.0
            i = 0.0
            while i < rw + rh:
                x1 = rx + max(0.0, i - rh)
                y1 = ry + min(rh, i)
                x2 = rx + min(rw, i)
                y2 = ry + max(0.0, i - rw)
                parts.append(
                    f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                    f'stroke="#888" stroke-width="0.6"/>'
                )
                i += step
        elif kind == "c":
            parts.append(
                f'<circle cx="{tx(op[1]):.2f}" cy="{ty(op[2]):.2f}" '
                f'r="{max(op[3] * s, 1.5):.2f}" fill="#333"/>'
            )
        elif kind == "t":
            x, y, wrap_w, text = op[1], op[2], op[3], op[4]
            lines = _wrap_label(str(text), float(wrap_w), s)
            for i, line in enumerate(lines):
                parts.append(
                    f'<text x="{tx(x):.2f}" y="{ty(y) + i * 12:.2f}" '
                    f'font-family="Segoe UI,Arial,sans-serif" font-size="10" '
                    f'fill="#222" stroke="none">{html.escape(line)}</text>'
                )

    parts.append("</g>")
    parts.append(
        f'<text x="{margin}" y="{sheet_h - 14}" font-family="Segoe UI,Arial,sans-serif" '
        f'font-size="10" fill="#666">SCHAD 2024-008 · Ledger Built · from schad_details ops · '
        f"EOR to verify connectors</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


def render_details_sheet(
    details: list[dict[str, Any]],
    *,
    title: str,
    sheet_no: str,
    cols: int = 2,
    rows: int = 2,
) -> str:
    """4-up (or N) composite sheet of detail SVGs inlined as groups."""
    cell_w, cell_h = 520.0, 420.0
    pad = 16.0
    tb_h = 70.0
    n = cols * rows
    chunk = details[:n]
    sheet_w = cols * cell_w + (cols + 1) * pad
    sheet_h = rows * cell_h + (rows + 1) * pad + tb_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{sheet_w:.0f}" '
        f'height="{sheet_h:.0f}" viewBox="0 0 {sheet_w:.0f} {sheet_h:.0f}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text x="{pad}" y="28" font-family="Segoe UI,Arial,sans-serif" font-size="18" '
        f'font-weight="700">{html.escape(sheet_no)} — {html.escape(title)}</text>',
        f'<text x="{pad}" y="48" font-family="Segoe UI,Arial,sans-serif" font-size="11" '
        f'fill="#555">SCHAD 2024-008 · Structural details · NOT FOR CONSTRUCTION</text>',
    ]
    for i, d in enumerate(chunk):
        c, r = i % cols, i // cols
        ox = pad + c * (cell_w + pad)
        oy = tb_h + pad + r * (cell_h + pad)
        parts.append(
            f'<rect x="{ox}" y="{oy}" width="{cell_w}" height="{cell_h}" '
            f'fill="#faf9f6" stroke="#333" stroke-width="1"/>'
        )
        # mini render with smaller sheet
        mini = render_detail_svg(d, sheet_w=cell_w - 8, sheet_h=cell_h - 8, margin=20)
        # extract inner content roughly
        body = mini
        if "<svg" in body:
            start = body.find(">") + 1
            end = body.rfind("</svg>")
            body = body[start:end]
        parts.append(f'<g transform="translate({ox + 4},{oy + 4})">{body}</g>')

    parts.append("</svg>")
    return "\n".join(parts)
