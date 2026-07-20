"""Construction drawing set for facilities (multi-sheet SVG + index)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmbim_core.model import Element, ProjectModel

from llmbim_drawings.plan import render_plan_view
from llmbim_drawings.schedules import export_schedule_csv, schedule_rows
from llmbim_drawings.section import render_elevation_svg, render_section_svg
from llmbim_drawings.sheets import title_block_svg
from llmbim_drawings.view import DrawingView


def _view_from_full_svg(svg: str, title: str = "") -> DrawingView:
    """Best-effort parse width/height from a full svg string; use body as-is nested carefully."""
    # Prefer not nesting full SVG — extract content between first > of svg and </svg>
    import re

    w, h, pad = 800.0, 600.0, 0.0
    m = re.search(
        r'viewBox="(-?[0-9.]+) (-?[0-9.]+) ([0-9.]+) ([0-9.]+)"', svg
    )
    if m:
        vx, vy, vw, vh = (float(g) for g in m.groups())
        # a negative-origin viewBox encodes a screen-space pad around the geometry
        # (dimension band); recover geometry size + pad so the sheet fit accounts for it
        pad = max(-vx, -vy, 0.0)
        w, h = vw - 2 * pad, vh - 2 * pad
    body_m = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.DOTALL | re.IGNORECASE)
    body = body_m.group(1) if body_m else svg
    return DrawingView(width=w, height=h, body=body, title=title, pad=pad)


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


def _is_column(el: Element) -> bool:
    return bool(el.category == "column" or el.params.get("fitting_type") == "column")


def _is_beam(el: Element) -> bool:
    return bool(el.category == "beam" or el.params.get("fitting_type") == "beam")


def _is_mech(el: Element) -> bool:
    ft = str(el.params.get("fitting_type") or "")
    if el.category in {"duct", "hvac"} or ft in {"duct", "flex_duct"}:
        return True
    if ft in {"vav", "fire_damper", "smoke_damper", "diffuser", "grille"}:
        return True
    # HVAC equipment (AHU / duct / hvac kinds)
    return el.category == "equipment" and str(el.params.get("kind") or "").lower() in {
        "duct",
        "hvac",
        "ahu",
    }


def _is_piping(el: Element) -> bool:
    if el.category in {"pipe", "plumbing_pipe", "fitting", "fittings", "fixture", "accessory"}:
        return True
    ft = str(el.params.get("fitting_type") or "")
    return ft in {"pipe", "elbow_90", "elbow_45", "tee", "toilet", "lavatory", "urinal"}


def _is_raceway(el: Element) -> bool:
    return bool(
        el.category in {"conduit", "cable_tray"}
        or el.params.get("fitting_type") in {"conduit", "cable_tray"}
    )


def _wall_types_view(model: ProjectModel) -> DrawingView:
    """A-401 body: one row per wall type actually used — layer bands + thickness."""
    from llmbim_core.types_catalog import DEFAULT_WALL_TYPES

    layer_fills = {
        "structure": "#b0b0b0",
        "insulation": "#f0e68c",
        "finish": "#e8e8e8",
        "membrane": "#4a5568",
    }
    used: dict[str, int] = {}
    for el in model.elements:
        if el.category != "wall":
            continue
        tid = str(el.type_id or el.params.get("type_id") or "")
        if tid:
            used[tid] = used.get(tid, 0) + 1

    lines: list[str] = [
        '<text x="20" y="34" font-size="16" font-family="sans-serif" font-weight="bold">'
        "Wall Types</text>"
    ]
    y = 70
    if not used:
        lines.append(
            f'<text x="20" y="{y}" font-size="11" font-family="sans-serif">'
            "(no typed walls in model)</text>"
        )
        y += 20
    band_scale = 0.5  # px per mm of layer thickness
    for tid in sorted(used):
        wt = DEFAULT_WALL_TYPES.get(tid)
        name = wt.name if wt else "(not in catalog)"
        lines.append(
            f'<text x="20" y="{y}" font-size="12" font-family="monospace" font-weight="bold">'
            f"{tid}</text>"
        )
        lines.append(
            f'<text x="180" y="{y}" font-size="11" font-family="sans-serif">'
            f"{name} — {used[tid]} wall(s)</text>"
        )
        y += 10
        x = 20.0
        layers = wt.layers if wt else []
        for layer in layers:
            w = max(6.0, layer.thickness_mm * band_scale)
            fill = layer_fills.get(layer.function, "#c8c8c8")
            lines.append(
                f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="26" '
                f'fill="{fill}" stroke="#333" stroke-width="0.8"/>'
            )
            lines.append(
                f'<text x="{x + w / 2:.1f}" y="{y + 40}" text-anchor="middle" font-size="9" '
                f'font-family="sans-serif" fill="#333">{layer.thickness_mm:.0f}</text>'
            )
            lines.append(
                f'<text x="{x + w / 2:.1f}" y="{y + 52}" text-anchor="middle" font-size="8" '
                f'font-family="sans-serif" fill="#666">{layer.material[:14]}</text>'
            )
            x += w
        if not layers:
            lines.append(
                f'<text x="20" y="{y + 18}" font-size="10" font-family="sans-serif" '
                'fill="#666">(no layer data)</text>'
            )
        total = sum(layer.thickness_mm for layer in layers)
        if total:
            lines.append(
                f'<text x="{x + 14:.1f}" y="{y + 18}" font-size="10" font-family="sans-serif">'
                f"total {total:.0f} mm</text>"
            )
        y += 78
    return DrawingView(width=1000, height=max(y + 10, 200), body="\n".join(lines), title="Wall Types")


def export_construction_set(
    model: ProjectModel,
    out_dir: str | Path,
    *,
    plan_level: str | None = None,
    plan_scale: float = 0.02,
    set_type: str = "construction",
) -> dict:
    """Write a drawing package with proper view fitting.

    ``set_type``:
      - ``"plan"``: permit-level sheets only — cover, floor plans per level,
        elevations, section, room/door/window schedules.
      - ``"construction"`` (default): plan set plus content-driven discipline
        sheets (S/M/P/E), wall types (A-401) and equipment schedule (A-501).
    """
    if set_type not in {"plan", "construction"}:
        raise ValueError(f"unknown set_type: {set_type!r} (use 'plan' or 'construction')")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # drop stale sheets from a previous export (e.g. re-pack construction → plan)
    for stale in out.glob("[GASMPE]-[0-9][0-9][0-9]_*.svg"):
        stale.unlink()

    level_ids = {lvl.name: lvl.id for lvl in model.levels}
    plan_levels = [
        lvl.name
        for lvl in model.levels
        if any(el.level_id == lvl.id for el in model.elements)
    ]
    if not plan_levels:
        plan_levels = [plan_level or (model.levels[0].name if model.levels else "L1")]
    level = plan_level or plan_levels[0]
    sheets: list[dict] = []

    def _level_els(lname: str) -> list[Element]:
        lid = level_ids.get(lname)
        return [el for el in model.elements if el.level_id == lid]

    for i, lname in enumerate(plan_levels, start=1):
        sn = f"A-1{i:02d}"
        plan_view = render_plan_view(model, lname, scale=plan_scale, show_dimensions=True)
        plan_sheet = _sheet_from_view(
            model,
            sheet_no=sn,
            title=f"Floor Plan — {lname}",
            view=plan_view,
            scale_note=f"plan scale {plan_scale}",
        )
        fname = f"{sn}_plan.svg"
        (out / fname).write_text(plan_sheet, encoding="utf-8")
        sheets.append(
            {"no": sn, "title": f"Floor Plan {lname}", "file": fname, "discipline": "A"}
        )

    for i, direction in enumerate(["N", "S", "E", "W"], start=1):
        elev_svg = render_elevation_svg(model, direction, scale=plan_scale)
        view = _view_from_full_svg(elev_svg, f"Elevation {direction}")
        sn = f"A-20{i}"
        sh = _sheet_from_view(
            model, sheet_no=sn, title=f"Elevation {direction}", view=view, scale_note=f"elev {direction}"
        )
        fname = f"{sn}_elev_{direction}.svg"
        (out / fname).write_text(sh, encoding="utf-8")
        sheets.append(
            {"no": sn, "title": f"Elevation {direction}", "file": fname, "discipline": "A"}
        )

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
    sheets.append(
        {
            "no": "A-301",
            "title": "Building Section",
            "file": "A-301_section.svg",
            "discipline": "A",
        }
    )

    def table_svg(
        title: str, rows: list[dict], sheet_no: str, fname: str, discipline: str = "A"
    ) -> None:
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
        sheets.append({"no": sheet_no, "title": title, "file": fname, "discipline": discipline})

    if set_type == "construction":
        # A-401 wall types: one row per used type, layer bands with thicknesses
        wt_view = _wall_types_view(model)
        wt_sheet = _sheet_from_view(
            model, sheet_no="A-401", title="Wall Types", view=wt_view, scale_note="—"
        )
        (out / "A-401_wall_types.svg").write_text(wt_sheet, encoding="utf-8")
        sheets.append(
            {
                "no": "A-401",
                "title": "Wall Types",
                "file": "A-401_wall_types.svg",
                "discipline": "A",
            }
        )

        level_name_by_id = {lvl.id: lvl.name for lvl in model.levels}
        eq_rows = [
            {
                "name": el.name,
                "kind": el.params.get("kind"),
                "size_mm": el.params.get("size_mm"),
                "level": level_name_by_id.get(el.level_id or "", ""),
                "location_mm": el.params.get("origin_mm"),
            }
            for el in model.query(category="equipment")
        ]
        table_svg(
            "Equipment Schedule",
            eq_rows or [{"note": "(none)"}],
            "A-501",
            "A-501_equipment.svg",
        )

    table_svg("Room Schedule", schedule_rows(model, "room"), "A-601", "A-601_rooms.svg")
    table_svg("Door Schedule", schedule_rows(model, "door"), "A-602", "A-602_doors.svg")
    table_svg("Window Schedule", schedule_rows(model, "window"), "A-603", "A-603_windows.svg")

    if set_type == "construction":
        # Content-driven discipline plan sheets, per level
        disciplines: list[tuple[str, str, str, Any, set[str]]] = [
            ("S", "structural", "Structural Plan", _is_column, {"grids", "columns", "beams"}),
            ("M", "mechanical", "Mechanical Plan", _is_mech, {"grids", "ducts"}),
            ("P", "piping", "Piping Plan", _is_piping, {"pipes"}),
            ("E", "raceway", "Raceway Plan", _is_raceway, {"conduit", "cable_tray"}),
        ]
        emitted_p = False
        for disc, slug, disc_title, pred, include in disciplines:
            n = 0
            for lname in plan_levels:
                lvl_els = _level_els(lname)
                if disc == "S":
                    match = any(_is_column(el) or _is_beam(el) for el in lvl_els)
                else:
                    match = any(pred(el) for el in lvl_els)
                if not match:
                    continue
                n += 1
                sn = f"{disc}-1{n:02d}"
                view = render_plan_view(
                    model,
                    lname,
                    scale=plan_scale,
                    show_dimensions=True,
                    include=include,
                    ghost_walls=True,
                    title=f"{model.name} — {disc_title} {lname}",
                )
                sh = _sheet_from_view(
                    model,
                    sheet_no=sn,
                    title=f"{disc_title} — {lname}",
                    view=view,
                    scale_note=f"plan scale {plan_scale}",
                )
                fname = f"{sn}_{slug}.svg"
                (out / fname).write_text(sh, encoding="utf-8")
                sheets.append(
                    {
                        "no": sn,
                        "title": f"{disc_title} {lname}",
                        "file": fname,
                        "discipline": disc,
                    }
                )
                if disc == "P":
                    emitted_p = True

            if disc == "P" and emitted_p:
                # P-601: pipe + fitting takeoff table
                from llmbim_core.material_lists import fitting_takeoff, pipe_takeoff

                to_rows: list[dict] = []
                for r in pipe_takeoff(model):
                    to_rows.append(
                        {
                            "item": "pipe",
                            "nps": r.get("nps"),
                            "material": r.get("material_id"),
                            "qty": r.get("length_m"),
                            "unit": "m",
                            "est_cost": r.get("est_cost"),
                        }
                    )
                for r in fitting_takeoff(model):
                    to_rows.append(
                        {
                            "item": r.get("fitting_type"),
                            "nps": r.get("nps"),
                            "material": r.get("material_id"),
                            "qty": r.get("qty"),
                            "unit": r.get("unit"),
                            "est_cost": r.get("est_cost"),
                        }
                    )
                table_svg(
                    "Pipe & Fitting Takeoff",
                    to_rows or [{"note": "(none)"}],
                    "P-601",
                    "P-601_takeoff.svg",
                    discipline="P",
                )

    sched = out / "schedules"
    sched.mkdir(exist_ok=True)
    for kind in ("room", "door", "window", "wall"):
        try:
            export_schedule_csv(model, kind, sched / f"{kind}.csv")
        except Exception:
            pass

    # Cover with index (sheet number + discipline + title)
    set_label = (
        "Construction Drawing Set" if set_type == "construction" else "Permit Plan Set"
    )
    index_lines = "\n".join(
        f'<text x="40" y="{280 + 20 * i}" font-size="12" font-family="monospace">'
        f'{s["no"]}  [{s.get("discipline", "A")}]  {s["title"]}</text>'
        for i, s in enumerate(sheets)
    )
    cover_body = f"""
    <text x="40" y="80" font-size="28" font-family="sans-serif" font-weight="bold">{model.name}</text>
    <text x="40" y="120" font-size="16" font-family="sans-serif">{set_label}</text>
    <text x="40" y="150" font-size="12" font-family="sans-serif">ENGINEERING ESTIMATE · LLM-BIM</text>
    <text x="40" y="200" font-size="14" font-family="sans-serif" font-weight="bold">Sheet Index</text>
    {index_lines}
    """
    cover_view = DrawingView(width=900, height=280 + 20 * len(sheets) + 40, body=cover_body)
    cover = _sheet_from_view(
        model, sheet_no="G-001", title="Cover & Index", view=cover_view, scale_note="—"
    )
    (out / "G-001_cover.svg").write_text(cover, encoding="utf-8")
    sheets.insert(
        0,
        {"no": "G-001", "title": "Cover & Index", "file": "G-001_cover.svg", "discipline": "G"},
    )

    manifest = {
        "project": model.name,
        "level": level,
        "levels": plan_levels,
        "set_type": set_type,
        "sheets": sheets,
    }
    (out / "SHEET_INDEX.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
