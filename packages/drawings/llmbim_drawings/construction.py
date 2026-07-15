"""Construction drawing set for facilities (multi-sheet SVG + index)."""

from __future__ import annotations

import json
from pathlib import Path

from llmbim_core.model import ProjectModel
from llmbim_drawings.plan import render_plan_view
from llmbim_drawings.schedules import export_schedule_csv, schedule_rows
from llmbim_drawings.section import render_elevation_svg, render_section_svg
from llmbim_drawings.sheets import title_block_svg
from llmbim_drawings.view import DrawingView


def _view_from_full_svg(svg: str, title: str = "") -> DrawingView:
    """Best-effort parse width/height from a full svg string; use body as-is nested carefully."""
    # Prefer not nesting full SVG — extract content between first > of svg and </svg>
    import re

    w, h = 800.0, 600.0
    m = re.search(r'viewBox="0 0 ([0-9.]+) ([0-9.]+)"', svg)
    if m:
        w, h = float(m.group(1)), float(m.group(2))
    body_m = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.DOTALL | re.IGNORECASE)
    body = body_m.group(1) if body_m else svg
    return DrawingView(width=w, height=h, body=body, title=title)


def _sheet_from_view(
    model: ProjectModel,
    *,
    sheet_no: str,
    title: str,
    view: DrawingView,
    scale_note: str,
    sheet_w: float = 1100,
    sheet_h: float = 850,
) -> str:
    margin = 20
    tb_h = 70
    max_w = sheet_w - 2 * margin - 20
    max_h = sheet_h - 2 * margin - tb_h - 20
    _s, body = view.scaled_to_fit(max_w, max_h, pad=5)
    return title_block_svg(
        sheet_w=sheet_w,
        sheet_h=sheet_h,
        project=model.name,
        sheet_title=title,
        sheet_no=sheet_no,
        scale_note=scale_note,
        body=body,
    )


def export_construction_set(
    model: ProjectModel,
    out_dir: str | Path,
    *,
    plan_level: str | None = None,
    plan_scale: float = 0.02,
) -> dict:
    """Write construction drawing package with proper view fitting."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    level = plan_level or (model.levels[0].name if model.levels else "L1")
    sheets: list[dict] = []

    plan_view = render_plan_view(model, level, scale=plan_scale, show_dimensions=True)
    plan_sheet = _sheet_from_view(
        model,
        sheet_no="A-101",
        title=f"Floor Plan — {level}",
        view=plan_view,
        scale_note=f"plan scale {plan_scale}",
    )
    (out / "A-101_plan.svg").write_text(plan_sheet, encoding="utf-8")
    sheets.append({"no": "A-101", "title": f"Floor Plan {level}", "file": "A-101_plan.svg"})

    for i, direction in enumerate(["N", "S", "E", "W"], start=1):
        elev_svg = render_elevation_svg(model, direction, scale=plan_scale)
        view = _view_from_full_svg(elev_svg, f"Elevation {direction}")
        sn = f"A-20{i}"
        sh = _sheet_from_view(
            model, sheet_no=sn, title=f"Elevation {direction}", view=view, scale_note=f"elev {direction}"
        )
        fname = f"{sn}_elev_{direction}.svg"
        (out / fname).write_text(sh, encoding="utf-8")
        sheets.append({"no": sn, "title": f"Elevation {direction}", "file": fname})

    xs: list[float] = []
    ys: list[float] = []
    for el in model.elements:
        if el.category == "wall" and "start_mm" in el.params:
            xs += [float(el.params["start_mm"][0]), float(el.params["end_mm"][0])]
            ys += [float(el.params["start_mm"][1]), float(el.params["end_mm"][1])]
        if el.category == "equipment" and "origin_mm" in el.params:
            xs.append(float(el.params["origin_mm"][0]))
            ys.append(float(el.params["origin_mm"][1]))
    mid_x = (min(xs) + max(xs)) / 2 if xs else 0.0
    y0 = (min(ys) - 2000) if ys else -5000
    y1 = (max(ys) + 2000) if ys else 5000
    sec_svg = render_section_svg(model, (mid_x, y0), (mid_x, y1), scale=plan_scale)
    sec_view = _view_from_full_svg(sec_svg, "Section")
    sec_sheet = _sheet_from_view(
        model, sheet_no="A-301", title="Building Section", view=sec_view, scale_note="section"
    )
    (out / "A-301_section.svg").write_text(sec_sheet, encoding="utf-8")
    sheets.append({"no": "A-301", "title": "Building Section", "file": "A-301_section.svg"})

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
            + " | ".join(str(k) for k in keys)
            + "</text>"
        )
        y += 18
        for row in rows[:100]:
            line = " | ".join(str(row.get(k, ""))[:28] for k in keys)
            # escape minimal
            line = line.replace("&", "&amp;").replace("<", "&lt;")
            lines.append(
                f'<text x="20" y="{y}" font-size="10" font-family="monospace">{line}</text>'
            )
            y += 14
            if y > 700:
                lines.append(
                    f'<text x="20" y="{y}" font-size="10">… truncated ({len(rows)} rows)</text>'
                )
                break
        view = DrawingView(width=1000, height=max(y + 20, 200), body="\n".join(lines), title=title)
        sh = _sheet_from_view(model, sheet_no=sheet_no, title=title, view=view, scale_note="—")
        (out / fname).write_text(sh, encoding="utf-8")
        sheets.append({"no": sheet_no, "title": title, "file": fname})

    table_svg("Room Schedule", schedule_rows(model, "room"), "A-601", "A-601_rooms.svg")
    table_svg("Door Schedule", schedule_rows(model, "door"), "A-602", "A-602_doors.svg")
    table_svg("Window Schedule", schedule_rows(model, "window"), "A-603", "A-603_windows.svg")
    eq_rows = [
        {
            "id": el.id[:12],
            "name": el.name,
            "kind": el.params.get("kind"),
            "shape": el.params.get("shape", "box"),
            "size_mm": el.params.get("size_mm"),
        }
        for el in model.query(category="equipment")
    ]
    table_svg("Equipment Schedule", eq_rows or [{"note": "(none)"}], "A-604", "A-604_equipment.svg")

    sched = out / "schedules"
    sched.mkdir(exist_ok=True)
    for kind in ("room", "door", "window", "wall"):
        try:
            export_schedule_csv(model, kind, sched / f"{kind}.csv")
        except Exception:
            pass

    # Cover with index
    index_lines = "\n".join(
        f'<text x="40" y="{280 + 20 * i}" font-size="12" font-family="monospace">'
        f'{s["no"]}  {s["title"]}</text>'
        for i, s in enumerate(sheets)
    )
    cover_body = f"""
    <text x="40" y="80" font-size="28" font-family="sans-serif" font-weight="bold">{model.name}</text>
    <text x="40" y="120" font-size="16" font-family="sans-serif">Construction Drawing Set</text>
    <text x="40" y="150" font-size="12" font-family="sans-serif">ENGINEERING ESTIMATE · LLM-BIM</text>
    <text x="40" y="200" font-size="14" font-family="sans-serif" font-weight="bold">Sheet Index</text>
    {index_lines}
    """
    cover_view = DrawingView(width=900, height=280 + 20 * len(sheets) + 40, body=cover_body)
    cover = _sheet_from_view(
        model, sheet_no="G-001", title="Cover & Index", view=cover_view, scale_note="—"
    )
    (out / "G-001_cover.svg").write_text(cover, encoding="utf-8")
    sheets.insert(0, {"no": "G-001", "title": "Cover & Index", "file": "G-001_cover.svg"})

    manifest = {"project": model.name, "level": level, "sheets": sheets}
    (out / "SHEET_INDEX.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
