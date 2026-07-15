"""Construction drawing set for facilities (multi-sheet SVG + index)."""

from __future__ import annotations

import json
from pathlib import Path

from llmbim_core.model import ProjectModel
from llmbim_drawings.plan import render_plan_svg
from llmbim_drawings.schedules import export_schedule_csv, schedule_rows
from llmbim_drawings.section import render_elevation_svg, render_section_svg
from llmbim_drawings.sheets import title_block_svg


def _embed_inner_svg(svg: str, max_w: float = 1040, max_h: float = 700) -> str:
    """Strip outer svg tag and wrap in scaled group if possible."""
    # crude: keep full svg nested
    return f'  <g class="viewport">\n    {svg}\n  </g>'


def _sheet(
    model: ProjectModel,
    *,
    sheet_no: str,
    title: str,
    body_svg: str,
    scale_note: str,
) -> str:
    return title_block_svg(
        project=model.name,
        sheet_title=title,
        sheet_no=sheet_no,
        scale_note=scale_note,
        body=_embed_inner_svg(body_svg),
    )


def export_construction_set(
    model: ProjectModel,
    out_dir: str | Path,
    *,
    plan_level: str | None = None,
    plan_scale: float = 0.02,
) -> dict:
    """Write a construction drawing package.

    Sheets:
      G-001 Cover / index
      A-101 Floor plan
      A-201..204 Elevations N/S/E/W
      A-301 Building section
      A-601 Room schedule sheet (table)
      A-602 Door / window / equipment schedules
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    level = plan_level or (model.levels[0].name if model.levels else "L1")

    sheets: list[dict] = []

    # Cover
    cover_body = f"""
    <text x="40" y="80" font-size="28" font-family="sans-serif" font-weight="bold">{model.name}</text>
    <text x="40" y="120" font-size="16" font-family="sans-serif">Construction Drawing Set (agent-derived)</text>
    <text x="40" y="160" font-size="12" font-family="sans-serif">BIM source: .llmbim.json · IFC · STEP · glTF co-exported</text>
    <text x="40" y="200" font-size="12" font-family="sans-serif">Classification: ENGINEERING ESTIMATE — not sealed CDs</text>
    <text x="40" y="260" font-size="14" font-family="sans-serif" font-weight="bold">Sheet index</text>
    """
    cover = _sheet(model, sheet_no="G-001", title="Cover & Index", body_svg=cover_body, scale_note="—")
    (out / "G-001_cover.svg").write_text(cover, encoding="utf-8")
    sheets.append({"no": "G-001", "title": "Cover & Index", "file": "G-001_cover.svg"})

    # Plan
    plan = render_plan_svg(model, level, scale=plan_scale)
    plan_sheet = _sheet(
        model,
        sheet_no="A-101",
        title=f"Floor Plan — {level}",
        body_svg=plan,
        scale_note=f"1:{int(1 / plan_scale) if plan_scale else 0} (approx SVG)",
    )
    (out / "A-101_plan.svg").write_text(plan_sheet, encoding="utf-8")
    sheets.append({"no": "A-101", "title": f"Floor Plan {level}", "file": "A-101_plan.svg"})

    # Elevations
    for i, direction in enumerate(["N", "S", "E", "W"], start=1):
        elev = render_elevation_svg(model, direction, scale=plan_scale)
        sn = f"A-20{i}"
        sh = _sheet(
            model,
            sheet_no=sn,
            title=f"Elevation {direction}",
            body_svg=elev,
            scale_note=f"elev {direction}",
        )
        fname = f"{sn}_elev_{direction}.svg"
        (out / fname).write_text(sh, encoding="utf-8")
        sheets.append({"no": sn, "title": f"Elevation {direction}", "file": fname})

    # Section through mid X
    xs: list[float] = []
    for el in model.elements:
        if el.category == "wall" and "start_mm" in el.params:
            xs.append(float(el.params["start_mm"][0]))
            xs.append(float(el.params["end_mm"][0]))
        if el.category == "equipment" and "origin_mm" in el.params:
            xs.append(float(el.params["origin_mm"][0]))
    mid_x = (min(xs) + max(xs)) / 2 if xs else 0.0
    ys: list[float] = []
    for el in model.elements:
        if el.category == "wall" and "start_mm" in el.params:
            ys += [float(el.params["start_mm"][1]), float(el.params["end_mm"][1])]
    y0 = (min(ys) - 2000) if ys else -5000
    y1 = (max(ys) + 2000) if ys else 5000
    sec = render_section_svg(model, (mid_x, y0), (mid_x, y1), scale=plan_scale)
    sec_sheet = _sheet(
        model, sheet_no="A-301", title="Building Section", body_svg=sec, scale_note="section"
    )
    (out / "A-301_section.svg").write_text(sec_sheet, encoding="utf-8")
    sheets.append({"no": "A-301", "title": "Building Section", "file": "A-301_section.svg"})

    # Schedule sheets as SVG tables
    def table_svg(title: str, rows: list[dict], sheet_no: str, fname: str) -> None:
        if not rows:
            rows = [{"note": "(none)"}]
        keys = list(rows[0].keys())
        y = 40
        lines = [
            f'<text x="20" y="{y}" font-size="16" font-family="sans-serif" font-weight="bold">{title}</text>'
        ]
        y += 30
        lines.append(
            f'<text x="20" y="{y}" font-size="11" font-family="monospace">'
            + " | ".join(keys)
            + "</text>"
        )
        y += 18
        for row in rows[:80]:
            line = " | ".join(str(row.get(k, ""))[:24] for k in keys)
            lines.append(
                f'<text x="20" y="{y}" font-size="10" font-family="monospace">{line}</text>'
            )
            y += 14
            if y > 700:
                lines.append(
                    f'<text x="20" y="{y}" font-size="10" font-family="sans-serif">'
                    f"… truncated</text>"
                )
                break
        body = "\n".join(lines)
        sh = _sheet(model, sheet_no=sheet_no, title=title, body_svg=body, scale_note="—")
        (out / fname).write_text(sh, encoding="utf-8")
        sheets.append({"no": sheet_no, "title": title, "file": fname})

    table_svg("Room Schedule", schedule_rows(model, "room"), "A-601", "A-601_rooms.svg")
    table_svg("Door Schedule", schedule_rows(model, "door"), "A-602", "A-602_doors.svg")
    table_svg("Window Schedule", schedule_rows(model, "window"), "A-603", "A-603_windows.svg")
    # equipment as wall-like schedule
    eq_rows = [
        {
            "id": el.id,
            "name": el.name,
            "kind": el.params.get("kind"),
            "size_mm": el.params.get("size_mm"),
        }
        for el in model.query(category="equipment")
    ]
    table_svg("Equipment Schedule", eq_rows or [{"note": "(none)"}], "A-604", "A-604_equipment.svg")

    # CSV companions
    sched = out / "schedules"
    sched.mkdir(exist_ok=True)
    for kind in ("room", "door", "window", "wall"):
        try:
            export_schedule_csv(model, kind, sched / f"{kind}.csv")
        except Exception:
            pass

    # Update cover with real index
    index_lines = "\n".join(
        f'<text x="40" y="{280 + 22 * i}" font-size="12" font-family="monospace">'
        f'{s["no"]}  {s["title"]}  ({s["file"]})</text>'
        for i, s in enumerate(sheets)
    )
    cover_body2 = f"""
    <text x="40" y="80" font-size="28" font-family="sans-serif" font-weight="bold">{model.name}</text>
    <text x="40" y="120" font-size="16" font-family="sans-serif">Construction Drawing Set</text>
    <text x="40" y="150" font-size="12" font-family="sans-serif">ENGINEERING ESTIMATE · LLM-BIM agent package</text>
    <text x="40" y="200" font-size="14" font-family="sans-serif" font-weight="bold">Sheet Index</text>
    {index_lines}
    """
    cover = _sheet(model, sheet_no="G-001", title="Cover & Index", body_svg=cover_body2, scale_note="—")
    (out / "G-001_cover.svg").write_text(cover, encoding="utf-8")

    manifest = {"project": model.name, "level": level, "sheets": sheets}
    (out / "SHEET_INDEX.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
