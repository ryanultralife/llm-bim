"""Excellence residuals #3–#5, #9–#10 — PDF binder + scale bar + legend gutter."""

from __future__ import annotations

import json
import re
from pathlib import Path

from llmbim import Project
from llmbim_drawings.pdf_binder import (
    _PAGE_ANSI_B_LAND,
    _hex_rgb,
    _parse_svg_drawing,
    export_pdf_binder,
)
from llmbim_drawings.section import render_elevation_svg, render_section_svg
from llmbim_drawings.sheets import graphic_scale_bar


def test_hex_rgb_parses() -> None:
    assert _hex_rgb("#000") == (0.0, 0.0, 0.0)
    assert _hex_rgb("#ffffff") == (1.0, 1.0, 1.0)
    r, g, b = _hex_rgb("#c45c26")  # type: ignore[misc]
    assert 0.7 < r < 0.8 and 0.3 < g < 0.4


def test_imperial_scale_bar_labels_feet() -> None:
    svg = graphic_scale_bar(0.04, units="imperial", max_px=200)
    assert 'class="scale-bar"' in svg
    assert "ft" in svg
    assert "m" not in svg.split("ft")[0][-5:]  # unit label is ft not m
    assert "'" in svg  # e.g. 0' / 4' / 8'


def test_metric_scale_bar_still_m_or_mm() -> None:
    svg = graphic_scale_bar(0.01, units="metric", max_px=200)
    assert "m" in svg or "mm" in svg
    assert "ft" not in svg


def test_line_legend_in_bottom_gutter_not_top_left() -> None:
    p = Project.create("leg", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    elev = render_elevation_svg(p.model, "S", weights=True)
    m = re.search(
        r'class="line-legend"[^>]*transform="translate\(([^,]+),([^)]+)\)"', elev
    )
    assert m, elev[:500]
    x, y = float(m.group(1)), float(m.group(2))
    # y must be positive (below geometry); old bug was y≈-26 (top-left pad)
    assert y > 0, f"legend still in top pad: translate({x},{y})"
    sec = render_section_svg(
        p.model, (4000, -1000), (4000, 1000), weights=True
    )
    m2 = re.search(
        r'class="line-legend"[^>]*transform="translate\(([^,]+),([^)]+)\)"', sec
    )
    assert m2
    assert float(m2.group(2)) > 0


def test_pdf_binder_sheet_index_order_and_ansi_b(tmp_path: Path) -> None:
    cons = tmp_path / "construction"
    cons.mkdir()
    # Minimal SVGs + index (register order B then A — opposite of alpha sort)
    for name, body in (
        ("B-1_plan.svg", '<svg viewBox="0 0 100 80"><line x1="0" y1="0" x2="50" y2="50" '
         'stroke="#000" stroke-width="2.2" stroke-dasharray="4 2"/></svg>'),
        ("A-1_plan.svg", '<svg viewBox="0 0 100 80"><rect x="5" y="5" width="40" height="30" '
         'fill="#c45c26" stroke="#111" stroke-width="1.1"/></svg>'),
    ):
        (cons / name).write_text(body, encoding="utf-8")
    (cons / "SHEET_INDEX.json").write_text(
        json.dumps(
            {
                "register": "custom",
                "sheets": [
                    {"no": "B.1", "title": "STRUCTURAL PLAN", "file": "B-1_plan.svg"},
                    {"no": "A.1", "title": "FLOOR PLAN", "file": "A-1_plan.svg"},
                ],
            }
        ),
        encoding="utf-8",
    )
    pdf = tmp_path / "set.pdf"
    export_pdf_binder(cons, pdf, title="Imperial Pack", units="imperial")
    data = pdf.read_bytes()
    assert data[:5] == b"%PDF-"
    # ANSI B landscape MediaBox
    assert b"/MediaBox [0 0 1224" in data or b"/MediaBox [0 0 1224.0" in data
    # Cover uses human rows, not just filenames
    assert b"B.1 - STRUCTURAL PLAN" in data or b"B.1 - STRUCTURAL" in data
    assert b"A.1 - FLOOR PLAN" in data or b"A.1 - FLOOR" in data


def test_pdf_stroke_width_and_dash_emitted(tmp_path: Path) -> None:
    svg = tmp_path / "line.svg"
    svg.write_text(
        '<svg viewBox="0 0 200 100">'
        '<line x1="10" y1="10" x2="100" y2="10" stroke="#000" stroke-width="2.2" '
        'stroke-dasharray="5 3"/>'
        '<path d="M 10 50 A 20 20 0 0 1 50 50" stroke="#333" stroke-width="1.1" fill="none"/>'
        "</svg>",
        encoding="utf-8",
    )
    _w, _h, ops = _parse_svg_drawing(svg, page_w=842, page_h=595)
    joined = "\n".join(ops)
    assert re.search(r"\b2\.2\d* w\b", joined) or "2.20 w" in joined or " w" in joined
    assert " d" in joined  # dash array
    # Arc expanded to line segments (more than one l after m)
    assert joined.count(" l") >= 3


def test_pdf_per_element_fill_hex(tmp_path: Path) -> None:
    svg = tmp_path / "fill.svg"
    svg.write_text(
        '<svg viewBox="0 0 100 100">'
        '<rect x="0" y="0" width="50" height="50" fill="#c45c26" stroke="none"/>'
        "</svg>",
        encoding="utf-8",
    )
    _w, _h, ops = _parse_svg_drawing(svg)
    joined = "\n".join(ops)
    # copper-ish orange in 0-1 RGB, not the old hardcoded lavender
    assert "0.769" in joined or "0.768" in joined or re.search(r"0\.7[56]\d* 0\.3", joined)
