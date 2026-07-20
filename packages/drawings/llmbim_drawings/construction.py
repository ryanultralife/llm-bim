"""Construction drawing set for facilities (multi-sheet SVG + index)."""

from __future__ import annotations

import datetime as _dt
import json
import math
from pathlib import Path
from typing import Any

from llmbim_core.model import Element, ProjectModel

from llmbim_drawings.layout import compose_sheet, table_view
from llmbim_drawings.plan import render_plan_view
from llmbim_drawings.schedules import export_schedule_csv, schedule_rows
from llmbim_drawings.section import render_elevation_svg, render_section_svg
from llmbim_drawings.sheets import drawing_area, title_block_svg
from llmbim_drawings.view import DrawingView

# rows per schedule sheet before paginating to A-601B, A-601C, …
SCHEDULE_ROWS_PER_SHEET = 28


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
    px_per_mm: float | None = None,
    north_arrow: bool = False,
    date: str | None = None,
) -> str:
    _ax, _ay, aw, ah = drawing_area(sheet_w, sheet_h)
    # true scaled drawing views (px_per_mm known) may upscale to fill the sheet;
    # tables / diagrams only get a modest bump so short schedules stay legible
    s, body = view.scaled_to_fit(aw, ah, pad=5, max_scale=2.5 if px_per_mm else 1.5)
    return title_block_svg(
        sheet_w=sheet_w,
        sheet_h=sheet_h,
        project=model.name,
        sheet_title=title,
        sheet_no=sheet_no,
        scale_note=scale_note,
        body=body,
        px_per_mm=(px_per_mm * s) if px_per_mm else None,
        north_arrow=north_arrow,
        date=date,
    )


def _multi_sheet(
    model: ProjectModel,
    *,
    sheet_no: str,
    title: str,
    cells: list[tuple],
    date: str | None,
    scale_note: str = "AS NOTED",
    arrange: str | None = None,
    weights: list[float] | None = None,
    north_arrow: bool = False,
) -> str:
    """Compose 1–4 view cells into the drawing area and frame the sheet."""
    _ax, _ay, aw, ah = drawing_area()
    composed = compose_sheet(
        cells, width=aw - 10, height=ah - 10, arrange=arrange, weights=weights
    )
    return _sheet_from_view(
        model,
        sheet_no=sheet_no,
        title=title,
        view=composed,
        scale_note=scale_note,
        north_arrow=north_arrow,
        date=date,
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


def _discipline_legend(disc: str, els: list[Element]) -> list[tuple[str, str, int]]:
    """(label, swatch color, count) rows for a discipline sheet legend."""

    def _ft(el: Element) -> str:
        return str(el.params.get("fitting_type") or "")

    entries: list[tuple[str, str, int]] = []
    if disc == "S":
        n_col = sum(1 for e in els if _is_column(e))
        n_beam = sum(1 for e in els if _is_beam(e))
        if n_col:
            entries.append(("Columns", "#37474f", n_col))
        if n_beam:
            entries.append(("Beams", "#546e7a", n_beam))
    elif disc == "M":
        n_duct = sum(
            1
            for e in els
            if e.category in {"duct", "hvac"} or _ft(e) in {"duct", "flex_duct"}
        )
        n_dev = sum(
            1
            for e in els
            if _ft(e) in {"vav", "fire_damper", "smoke_damper", "diffuser", "grille"}
        )
        n_ahu = sum(
            1
            for e in els
            if e.category == "equipment"
            and str(e.params.get("kind") or "").lower() in {"duct", "hvac", "ahu"}
        )
        if n_duct:
            entries.append(("Duct runs", "#2e7d32", n_duct))
        if n_dev:
            entries.append(("HVAC devices", "#b71c1c", n_dev))
        if n_ahu:
            entries.append(("AHU / equipment", "#0b5cab", n_ahu))
    elif disc == "P":
        by_mat: dict[str, int] = {}
        n_fit = 0
        n_fix = 0
        for e in els:
            if e.category in {"pipe", "plumbing_pipe"} or _ft(e) == "pipe":
                mid = str(e.params.get("material_id") or "pipe")
                by_mat[mid] = by_mat.get(mid, 0) + 1
            elif e.category in {"fitting", "fittings"} or _ft(e) in {
                "elbow_90",
                "elbow_45",
                "tee",
            }:
                n_fit += 1
            elif e.category in {"fixture", "accessory"} or _ft(e) in {
                "toilet",
                "lavatory",
                "urinal",
            }:
                n_fix += 1
        mat_colors = {"black": "#333333", "ss316": "#6b7c8a", "pvc": "#e6d84a"}
        for mid, n in sorted(by_mat.items()):
            color = "#c45c26"
            for key, c in mat_colors.items():
                if key in mid:
                    color = c
            entries.append((f"Pipe — {mid}", color, n))
        if n_fit:
            entries.append(("Fittings", "#c45c26", n_fit))
        if n_fix:
            entries.append(("Fixtures", "#5c4d7a", n_fix))
    elif disc == "E":
        n_cond = sum(1 for e in els if e.category == "conduit" or _ft(e) == "conduit")
        n_tray = sum(1 for e in els if e.category == "cable_tray" or _ft(e) == "cable_tray")
        if n_cond:
            entries.append(("Conduit", "#6a1b9a", n_cond))
        if n_tray:
            entries.append(("Cable tray", "#7b1fa2", n_tray))
    return entries


def _legend_view(entries: list[tuple[str, str, int]]) -> DrawingView:
    """Right-hand legend cell: color swatch + system label + count."""
    lines = [
        '<g class="legend" font-family="sans-serif">',
        '<text x="0" y="14" font-size="13" font-weight="bold" '
        'letter-spacing="1">SYSTEMS</text>',
        '<line x1="0" y1="20" x2="190" y2="20" stroke="#111" stroke-width="1"/>',
    ]
    y = 40
    if not entries:
        lines.append(
            f'<text x="0" y="{y}" font-size="10" fill="#666">(none on this level)</text>'
        )
        y += 20
    for label, color, count in entries:
        lines.append(
            f'<rect x="0" y="{y - 9}" width="20" height="11" fill="{color}" '
            f'stroke="#333" stroke-width="0.7"/>'
        )
        lines.append(f'<text x="27" y="{y}" font-size="10.5">{label[:22]}</text>')
        lines.append(
            f'<text x="190" y="{y}" font-size="10.5" text-anchor="end" '
            f'fill="#333">× {count}</text>'
        )
        y += 20
    lines.append("</g>")
    return DrawingView(width=200, height=max(y + 4, 70), body="\n".join(lines), title="Legend")


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


def _fmt_cell(value: Any) -> Any:
    """Schedule cell: lists → readable strings; None passthrough."""
    if isinstance(value, (list, tuple)):
        try:
            return " × ".join(f"{float(v):g}" for v in value)
        except (TypeError, ValueError):
            return ", ".join(str(v) for v in value)
    return value


def export_construction_set(
    model: ProjectModel,
    out_dir: str | Path,
    *,
    plan_level: str | None = None,
    plan_scale: float = 0.02,
    set_type: str = "construction",
    date: str | None = None,
) -> dict:
    """Write a drawing package with proper view fitting.

    ``set_type``:
      - ``"plan"``: permit-level sheets only — cover, floor plans per level,
        elevations, sections, room/door/window schedules.
      - ``"construction"`` (default): plan set plus content-driven discipline
        sheets (S/M/P/E), wall types (A-401) and equipment schedule (A-501).

    ``date``: issue date stamped in every title block (default: today, ISO).
    """
    if set_type not in {"plan", "construction"}:
        raise ValueError(f"unknown set_type: {set_type!r} (use 'plan' or 'construction')")
    if date is None:
        date = _dt.date.today().isoformat()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # drop stale sheets from a previous export (e.g. re-pack construction → plan),
    # including paginated schedule pages (A-601B_…)
    for pattern in (
        "[GASMPE]-[0-9][0-9][0-9]_*.svg",
        "[GASMPE]-[0-9][0-9][0-9][A-Z]_*.svg",
    ):
        for stale in out.glob(pattern):
            stale.unlink()

    nominal_scale = f"1:{max(1, round(1 / plan_scale))}"
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

    # ── building extents + the two A-301 section cuts (marked on floor plans)
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
    mid_y = (min(ys) + max(ys)) / 2 if ys else 0.0
    x0 = (min(xs) - 2000) if xs else -5000
    x1 = (max(xs) + 2000) if xs else 5000
    y0 = (min(ys) - 2000) if ys else -5000
    y1 = (max(ys) + 2000) if ys else 5000
    # A-A: transverse cut (through mid X, looking along Y extent)
    cut_a = ((mid_x, y0), (mid_x, y1))
    # B-B: longitudinal cut (through mid Y, along the X extent)
    cut_b = ((x0, mid_y), (x1, mid_y))
    section_marks = [
        {"p0": cut_a[0], "p1": cut_a[1], "label": "A", "sheet": "A-301"},
        {"p0": cut_b[0], "p1": cut_b[1], "label": "B", "sheet": "A-301"},
    ]

    # ── A-1xx floor plans (grid dim chains, room tags, section markers)
    for i, lname in enumerate(plan_levels, start=1):
        sn = f"A-1{i:02d}"
        plan_view = render_plan_view(
            model,
            lname,
            scale=plan_scale,
            show_dimensions=True,
            grid_dims=True,
            room_tags=True,
            section_marks=section_marks,
        )
        plan_sheet = _sheet_from_view(
            model,
            sheet_no=sn,
            title=f"Floor Plan — {lname}",
            view=plan_view,
            scale_note=nominal_scale,
            px_per_mm=plan_scale,
            north_arrow=True,
            date=date,
        )
        fname = f"{sn}_plan.svg"
        (out / fname).write_text(plan_sheet, encoding="utf-8")
        sheets.append(
            {"no": sn, "title": f"Floor Plan {lname}", "file": fname, "discipline": "A"}
        )

    # ── A-201/A-202: paired elevations (two views per sheet)
    elev_pairs = [
        ("A-201", "Elevations I", [("N", "North Elevation"), ("S", "South Elevation")]),
        ("A-202", "Elevations II", [("E", "East Elevation"), ("W", "West Elevation")]),
    ]
    for sn, sheet_title, pair in elev_pairs:
        cells: list[tuple] = []
        for direction, cell_title in pair:
            elev_svg = render_elevation_svg(model, direction, scale=plan_scale)
            view = _view_from_full_svg(elev_svg, cell_title)
            cells.append((view, cell_title, nominal_scale, plan_scale))
        sh = _multi_sheet(
            model, sheet_no=sn, title=sheet_title, cells=cells, date=date
        )
        fname = f"{sn}_elevations.svg"
        (out / fname).write_text(sh, encoding="utf-8")
        sheets.append({"no": sn, "title": sheet_title, "file": fname, "discipline": "A"})

    # ── A-301: two building sections (transverse A-A + longitudinal B-B)
    sec_cells: list[tuple] = []
    for (p0, p1), lab in ((cut_a, "A"), (cut_b, "B")):
        sec_svg = render_section_svg(
            model, p0, p1, scale=plan_scale, title=f"{model.name} — Section {lab}-{lab}"
        )
        sec_view = _view_from_full_svg(sec_svg, f"Section {lab}-{lab}")
        sec_cells.append((sec_view, f"Section {lab}-{lab}", nominal_scale, plan_scale))
    sec_sheet = _multi_sheet(
        model, sheet_no="A-301", title="Building Sections", cells=sec_cells, date=date
    )
    (out / "A-301_sections.svg").write_text(sec_sheet, encoding="utf-8")
    sheets.append(
        {
            "no": "A-301",
            "title": "Building Sections",
            "file": "A-301_sections.svg",
            "discipline": "A",
        }
    )

    def table_sheets(
        title: str,
        headers: list[str],
        rows: list[list[Any]],
        base_no: str,
        slug: str,
        discipline: str = "A",
    ) -> None:
        """Ruled schedule table sheet(s), paginated at SCHEDULE_ROWS_PER_SHEET."""
        rows = [[_fmt_cell(v) for v in r] for r in rows]
        n_pages = max(1, math.ceil(len(rows) / SCHEDULE_ROWS_PER_SHEET))
        for pi in range(n_pages):
            page = rows[pi * SCHEDULE_ROWS_PER_SHEET : (pi + 1) * SCHEDULE_ROWS_PER_SHEET]
            sn = base_no if pi == 0 else f"{base_no}{chr(ord('A') + pi)}"
            page_title = title if n_pages == 1 else f"{title} ({pi + 1}/{n_pages})"
            view = table_view(headers, page, title=page_title)
            sh = _sheet_from_view(
                model,
                sheet_no=sn,
                title=page_title,
                view=view,
                scale_note="NTS",
                date=date,
            )
            fname = f"{sn}_{slug}.svg"
            (out / fname).write_text(sh, encoding="utf-8")
            sheets.append(
                {"no": sn, "title": page_title, "file": fname, "discipline": discipline}
            )

    if set_type == "construction":
        # A-401 wall types: one row per used type, layer bands with thicknesses
        wt_view = _wall_types_view(model)
        wt_sheet = _sheet_from_view(
            model, sheet_no="A-401", title="Wall Types", view=wt_view, scale_note="NTS",
            date=date,
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
            [
                el.name,
                el.params.get("kind"),
                el.params.get("size_mm"),
                level_name_by_id.get(el.level_id or "", ""),
                el.params.get("origin_mm"),
            ]
            for el in model.query(category="equipment")
        ]
        table_sheets(
            "Equipment Schedule",
            ["NAME", "KIND", "SIZE mm", "LEVEL", "LOCATION mm"],
            eq_rows,
            "A-501",
            "equipment",
        )

    room_rows = [
        [r.get("name"), r.get("level"), r.get("area_m2"), r.get("height_mm"),
         r.get("volume_m3"), r.get("phase")]
        for r in schedule_rows(model, "room")
    ]
    table_sheets(
        "Room Schedule",
        ["NAME", "LEVEL", "AREA m²", "HEIGHT mm", "VOLUME m³", "PHASE"],
        room_rows,
        "A-601",
        "rooms",
    )
    door_rows = [
        [r.get("mark"), r.get("name"), r.get("width_mm"), r.get("height_mm"),
         r.get("type_id"), r.get("fire_rating"), r.get("locator")]
        for r in schedule_rows(model, "door")
    ]
    table_sheets(
        "Door Schedule",
        ["MARK", "NAME", "W mm", "H mm", "TYPE", "FIRE", "LOCATION"],
        door_rows,
        "A-602",
        "doors",
    )
    window_rows = [
        [r.get("name"), r.get("width_mm"), r.get("height_mm"), r.get("sill_mm"),
         r.get("type_id"), r.get("locator")]
        for r in schedule_rows(model, "window")
    ]
    table_sheets(
        "Window Schedule",
        ["NAME", "W mm", "H mm", "SILL mm", "TYPE", "LOCATION"],
        window_rows,
        "A-603",
        "windows",
    )

    if set_type == "construction":
        # Content-driven discipline plan sheets, per level (plan + legend cell)
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
                legend = _legend_view(_discipline_legend(disc, lvl_els))
                sh = _multi_sheet(
                    model,
                    sheet_no=sn,
                    title=f"{disc_title} — {lname}",
                    cells=[
                        (view, f"{disc_title} {lname}", nominal_scale, plan_scale),
                        (legend, "Legend", ""),
                    ],
                    date=date,
                    scale_note=nominal_scale,
                    arrange="row",
                    weights=[0.76, 0.24],
                    north_arrow=True,
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

                to_rows: list[list[Any]] = []
                for r in pipe_takeoff(model):
                    to_rows.append(
                        ["pipe", r.get("nps"), r.get("material_id"), r.get("length_m"),
                         "m", r.get("est_cost")]
                    )
                for r in fitting_takeoff(model):
                    to_rows.append(
                        [r.get("fitting_type"), r.get("nps"), r.get("material_id"),
                         r.get("qty"), r.get("unit"), r.get("est_cost")]
                    )
                table_sheets(
                    "Pipe & Fitting Takeoff",
                    ["ITEM", "NPS", "MATERIAL", "QTY", "UNIT", "EST COST"],
                    to_rows,
                    "P-601",
                    "takeoff",
                    discipline="P",
                )

    sched = out / "schedules"
    sched.mkdir(exist_ok=True)
    for kind in ("room", "door", "window", "wall"):
        try:
            export_schedule_csv(model, kind, sched / f"{kind}.csv")
        except Exception:
            pass

    # Cover with index (sheet number + discipline + title) as a ruled table
    set_label = (
        "Construction Drawing Set" if set_type == "construction" else "Permit Plan Set"
    )
    index_view = table_view(
        ["SHEET", "DISC", "TITLE"],
        [[s["no"], s.get("discipline", "A"), s["title"]] for s in sheets],
        title="Sheet Index",
    )
    head = (
        f'<text x="0" y="34" font-size="26" font-family="sans-serif" '
        f'font-weight="bold">{model.name}</text>\n'
        f'<text x="0" y="58" font-size="14" font-family="sans-serif">{set_label}</text>\n'
        f'<text x="0" y="76" font-size="10" font-family="sans-serif" fill="#8a1a1a">'
        f"ENGINEERING ESTIMATE · LLM-BIM · issued {date}</text>\n"
        f'<g transform="translate(0,96)">\n{index_view.body}\n</g>'
    )
    cover_view = DrawingView(
        width=max(index_view.width, 560), height=96 + index_view.height, body=head
    )
    cover = _sheet_from_view(
        model, sheet_no="G-001", title="Cover & Index", view=cover_view,
        scale_note="NTS", date=date,
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
        "date": date,
        "sheets": sheets,
    }
    (out / "SHEET_INDEX.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
