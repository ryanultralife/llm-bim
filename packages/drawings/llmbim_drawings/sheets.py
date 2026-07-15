"""Title block + multi-sheet SVG helpers."""

from __future__ import annotations

from xml.sax.saxutils import escape

from llmbim_drawings.svg_util import fmt


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
) -> str:
    """Wrap drawing body in an A-size-ish frame with title block."""
    tb_h = 70
    margin = 20
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(sheet_w)}" height="{fmt(sheet_h)}"
     viewBox="0 0 {fmt(sheet_w)} {fmt(sheet_h)}">
  <rect x="0" y="0" width="{fmt(sheet_w)}" height="{fmt(sheet_h)}" fill="#f5f5f0"/>
  <rect x="{fmt(margin)}" y="{fmt(margin)}" width="{fmt(sheet_w - 2 * margin)}"
        height="{fmt(sheet_h - 2 * margin - tb_h)}" fill="#ffffff" stroke="#111" stroke-width="1.5"/>
  <g transform="translate({fmt(margin + 10)},{fmt(margin + 10)})">
{body}
  </g>
  <!-- title block -->
  <rect x="{fmt(margin)}" y="{fmt(sheet_h - margin - tb_h)}" width="{fmt(sheet_w - 2 * margin)}"
        height="{fmt(tb_h)}" fill="#fff" stroke="#111" stroke-width="1.5"/>
  <line x1="{fmt(sheet_w - margin - 280)}" y1="{fmt(sheet_h - margin - tb_h)}"
        x2="{fmt(sheet_w - margin - 280)}" y2="{fmt(sheet_h - margin)}" stroke="#111"/>
  <line x1="{fmt(sheet_w - margin - 140)}" y1="{fmt(sheet_h - margin - tb_h)}"
        x2="{fmt(sheet_w - margin - 140)}" y2="{fmt(sheet_h - margin)}" stroke="#111"/>
  <text x="{fmt(margin + 12)}" y="{fmt(sheet_h - margin - 45)}" font-family="sans-serif"
        font-size="14" font-weight="bold">{escape(project)}</text>
  <text x="{fmt(margin + 12)}" y="{fmt(sheet_h - margin - 22)}" font-family="sans-serif"
        font-size="16">{escape(sheet_title)}</text>
  <text x="{fmt(margin + 12)}" y="{fmt(sheet_h - margin - 6)}" font-family="sans-serif"
        font-size="10" fill="#444">{escape(notes or "LLM-BIM · ENGINEERING ESTIMATE · agent-derived")}</text>
  <text x="{fmt(sheet_w - margin - 270)}" y="{fmt(sheet_h - margin - 30)}" font-family="sans-serif"
        font-size="11">SCALE: {escape(scale_note)}</text>
  <text x="{fmt(sheet_w - margin - 130)}" y="{fmt(sheet_h - margin - 30)}" font-family="sans-serif"
        font-size="18" font-weight="bold">{escape(sheet_no)}</text>
  <text x="{fmt(sheet_w - margin - 130)}" y="{fmt(sheet_h - margin - 10)}" font-family="sans-serif"
        font-size="9">llm-bim</text>
</svg>
"""
