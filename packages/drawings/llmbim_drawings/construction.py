"""Construction drawing set for facilities (multi-sheet SVG + index)."""

from __future__ import annotations

import datetime as _dt
import inspect
import json
import math
import re
import textwrap
from pathlib import Path
from typing import Any

from llmbim_core.errors import ValidationError
from llmbim_core.model import Element, ProjectModel

from llmbim_drawings.detail_ops import imperial_scale_note, render_detail_sheet
from llmbim_drawings.layout import compose_sheet, table_view
from llmbim_drawings.plan import render_plan_view
from llmbim_drawings.schedules import export_schedule_csv, schedule_rows
from llmbim_drawings.section import render_elevation_svg, render_section_svg
from llmbim_drawings.sheets import drawing_area, title_block_svg
from llmbim_drawings.svg_util import esc
from llmbim_drawings.view import DrawingView

# rows per schedule sheet before paginating to A-601B, A-601C, …
SCHEDULE_ROWS_PER_SHEET = 28

# EQ series cap: per-room equipment arrangement sheets beyond this get a cover note
MAX_EQ_SHEETS = 20

# N-series wall fills: shield concrete red-brown, CMU grey, gyp light;
# any other type renders with a diagonal hatch (see render_plan_view)
SHIELD_WALL_FILLS = {
    "W-SHIELD-CONC": "#8d4a3b",
    "W-EXT-CMU": "#9e9e9e",
    "W-INT-GYP": "#eceff1",
}


def _scale_note_for(plan_scale: float, units: str) -> str:
    """Title-block scale note: ``1:50`` (metric) or the architectural note
    (``1/4" = 1'-0"``) when imperial AND the ratio maps cleanly; otherwise the
    numeric note is kept (correctness over cosmetics)."""
    numeric = f"1:{max(1, round(1 / plan_scale))}"
    if units == "imperial":
        note = imperial_scale_note(1.0 / plan_scale)
        if note:
            return note
    return numeric


def _check_set_units(units: str) -> str:
    if units not in {"metric", "imperial"}:
        raise ValidationError("units must be 'metric' or 'imperial'", units=units)
    return units


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
    stamp_block: bool = False,
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
        stamp_block=stamp_block,
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
    stamp_block: bool = False,
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
        stamp_block=stamp_block,
    )


def _building_cuts(
    model: ProjectModel,
) -> tuple[tuple[tuple[float, float], tuple[float, float]],
           tuple[tuple[float, float], tuple[float, float]]]:
    """Two default section cuts from building extents: (A-A transverse, B-B longitudinal)."""
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
    return cut_a, cut_b


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


def _is_duct_run(el: Element) -> bool:
    ft = str(el.params.get("fitting_type") or "")
    return el.category in {"duct", "hvac"} or ft in {"duct", "flex_duct"}


def _hvac_h_system(el: Element) -> str | None:
    """H-series bucket: ``"HVS"`` (supply) / ``"HVE"`` (exhaust/return) / None.

    Ducts route by system tag (HVS* / HVE*) or by name (supply / exhaust /
    return); HVAC riser equipment (kind ``hvs_*_riser`` / ``hve_*_riser``)
    rides along on the matching sheet.
    """
    name = str(el.name or "").lower()
    if _is_duct_run(el):
        system = str(el.params.get("system") or "").upper()
        if system.startswith("HVS") or "supply" in name:
            return "HVS"
        if system.startswith("HVE") or "exhaust" in name or "return" in name:
            return "HVE"
        return None
    if el.category == "equipment":
        kind = str(el.params.get("kind") or "").lower()
        if kind.endswith("_riser"):
            if kind.startswith("hvs"):
                return "HVS"
            if kind.startswith("hve"):
                return "HVE"
    return None


def _point_in_poly(x: float, y: float, poly: list) -> bool:
    """Ray-cast point-in-polygon (plan mm)."""
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = float(poly[i][0]), float(poly[i][1])
        x2, y2 = float(poly[(i + 1) % n][0]), float(poly[(i + 1) % n][1])
        if (y1 > y) != (y2 > y):
            xt = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xt:
                inside = not inside
    return inside


def _is_underground(el: Element) -> bool:
    if el.category != "equipment":
        return False
    kind = str(el.params.get("kind") or "").lower()
    return "underground" in kind or bool(el.params.get("underground"))


def _room_suggests_shielding(el: Element) -> bool:
    name = str(el.name or "").upper()
    if any(key in name for key in ("SHIELD", "HOT CELL", "CONFINE")):
        return True
    return bool(el.params.get("shielded"))


def _shield_legend_view(walls: list[Element]) -> DrawingView:
    """N-sheet legend: wall type → color swatch → count → total length."""
    stats: dict[str, tuple[int, float]] = {}
    for el in walls:
        tid = str(el.type_id or el.params.get("type_id") or "") or "(untyped)"
        length = 0.0
        try:
            s, e = el.params["start_mm"], el.params["end_mm"]
            length = math.hypot(float(e[0]) - float(s[0]), float(e[1]) - float(s[1]))
        except (KeyError, TypeError, ValueError, IndexError):
            pass
        n, tot = stats.get(tid, (0, 0.0))
        stats[tid] = (n + 1, tot + length)
    lines = [
        '<g class="legend legend-shield" font-family="sans-serif">',
        '<text x="0" y="14" font-size="13" font-weight="bold" '
        'letter-spacing="1">WALL SHIELDING</text>',
        '<line x1="0" y1="20" x2="230" y2="20" stroke="#111" stroke-width="1"/>',
    ]
    y = 40
    for tid in sorted(stats):
        count, tot = stats[tid]
        color = SHIELD_WALL_FILLS.get(tid)
        if color:
            lines.append(
                f'<rect x="0" y="{y - 9}" width="20" height="11" fill="{color}" '
                f'stroke="#333" stroke-width="0.7"/>'
            )
        else:
            # unknown type: hatched swatch
            lines.append(
                f'<rect x="0" y="{y - 9}" width="20" height="11" fill="#f7f7f7" '
                f'stroke="#333" stroke-width="0.7"/>'
            )
            lines.append(
                f'<line x1="3" y1="{y + 2}" x2="10" y2="{y - 9}" '
                f'stroke="#777" stroke-width="1"/>'
            )
            lines.append(
                f'<line x1="10" y1="{y + 2}" x2="17" y2="{y - 9}" '
                f'stroke="#777" stroke-width="1"/>'
            )
        lines.append(f'<text x="27" y="{y}" font-size="10">{esc(tid[:18])}</text>')
        lines.append(
            f'<text x="185" y="{y}" font-size="10" text-anchor="end" '
            f'fill="#333">× {count}</text>'
        )
        lines.append(
            f'<text x="230" y="{y}" font-size="10" text-anchor="end" '
            f'fill="#333">{tot / 1000:.1f} m</text>'
        )
        y += 20
    lines.append("</g>")
    return DrawingView(width=240, height=max(y + 4, 70), body="\n".join(lines), title="Legend")


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
    units: str = "metric",
    dim_tiers: bool = False,
    fractional_grids: bool = False,
    key_plan: bool = False,
    room_areas: bool = False,
    line_weights: bool = False,
    hatches: bool = False,
    stamp_block: bool = False,
    sheets: list[dict] | None = None,
) -> dict:
    """Write a drawing package with proper view fitting.

    ``set_type``:
      - ``"plan"``: permit-level sheets only — cover, floor plans per level,
        elevations, sections, room/door/window schedules.
      - ``"construction"`` (default): plan set plus content-driven discipline
        sheets (S/M/P/E), wall types (A-401), equipment schedule (A-501),
        HVAC supply/exhaust splits (H-1xx), per-room equipment arrangements
        (EQ-1xx), shielding & confinement (N-1xx) and site/underground
        (C-1xx) — each emitted only when matching elements exist.

    ``date``: issue date stamped in every title block (default: today, ISO).

    ``units``: ``"metric"`` (default — output unchanged) or ``"imperial"``:
    plan/section/elevation dimension text renders as feet-inches to the
    nearest 1/2" (``24'-0"``; 1 ft = 304.8 mm) and plan scale notes become
    architectural (``1/4" = 1'-0"``) when the ratio maps cleanly. Applies to
    the default register and is the fallback for custom register entries.

    CD anatomy options (WP-CD-ANATOMY slice A — all default off; applied to
    the default-register floor plans and the fallback for custom ``plan``
    entries): ``dim_tiers`` (three-tier dimension chains outside the plan),
    ``fractional_grids`` (fractional intermediate grid bubbles, skip-I
    lettering), ``key_plan`` (reduced building outline block per plan sheet),
    ``room_areas`` (room name / boxed number / area tag anatomy).

    CD anatomy options (WP-CD-ANATOMY slice B — all default off):
    ``line_weights`` (3-tier cut/projection/reference stroke hierarchy +
    "ABV." dashed + line legend in sections/elevations), ``hatches``
    (section material hatches: concrete stipple, wood diagonal, batt
    insulation, earth below grade), ``stamp_block`` (reserved PE/SE stamp
    square on S-discipline sheets). Custom register: per-sheet
    ``line_weights``/``hatches`` opts on ``elevations``/``sections`` entries
    and ``stamp_block`` on any entry override the export-level defaults.

    ``sheets``: optional custom sheet register. When provided it REPLACES the
    default register entirely — one entry per sheet, in order::

        {"no": "A1.1", "title": "FLOOR PLAN", "kind": "plan", ...opts}

    Common keys: ``no``/``title``/``kind`` (required), ``scale_note`` (title
    block text), ``discipline`` (default: alpha prefix of ``no``), ``scale``
    (per-sheet plan scale override, px/mm), ``units`` (per-sheet
    ``"metric"``/``"imperial"`` override of the export-level default; honored
    by ``plan``/``elevations``/``sections``). Kinds + kind options:

    - ``"cover"``     — cover with the index of THIS register.
                        opts: ``notes`` (list[str]), ``subtitle``.
    - ``"plan"``      — floor plan. opts: ``level``, ``include`` (category
                        groups), ``crop`` ((x0, y0, x1, y1) mm),
                        ``ghost_walls``, ``room_tags``, ``tags`` (marked
                        door/window tag bubbles + wall-type diamonds +
                        equipment leader tags), ``dimensions``, ``dim_tiers``,
                        ``fractional_grids``, ``key_plan``, ``room_areas``
                        (each overriding the export-level default).
    - ``"elevations"``— paired elevations. opts: ``pair`` e.g. ``["S", "N"]``.
    - ``"sections"``  — the two default building sections (A-A / B-B).
    - ``"schedule"``  — ruled schedule table(s). opts: ``schedule`` — a
                        schedule kind (see ``schedule_rows``) or list of
                        kinds composed onto one sheet.
    - ``"details"``   — up to 4 detail-ops dicts 4-up. opts: ``details``
                        (list of ``{id, title, scale, ops}``, see
                        ``llmbim_drawings.detail_ops``).
    - ``"custom_svg"``— pre-rendered content. opts: ``view`` (DrawingView or
                        full SVG string) or ``provider`` (callable, optionally
                        taking the model, returning either).
    - ``"doc"``       — markdown-ish text sheet (calc/spec placeholders).
                        opts: ``text``.

    Filenames come from the sanitized sheet no (``A0.1`` -> ``A0-1_cover.svg``)
    and ``SHEET_INDEX.json`` + the cover reflect the custom register.
    """
    if set_type not in {"plan", "construction"}:
        raise ValueError(f"unknown set_type: {set_type!r} (use 'plan' or 'construction')")
    units = _check_set_units(units)
    if date is None:
        date = _dt.date.today().isoformat()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # drop stale sheets from a previous export (e.g. re-pack construction → plan),
    # including paginated schedule pages (A-601B_…), two-letter disciplines (EQ-…)
    # and custom-register names (A0-1_…, S3-1B_…, MEP-101_…)
    for pattern in (
        "[A-Z]-[0-9][0-9][0-9]_*.svg",
        "[A-Z]-[0-9][0-9][0-9][A-Z]_*.svg",
        "[A-Z][A-Z]-[0-9][0-9][0-9]_*.svg",
        "[A-Z][A-Z]-[0-9][0-9][0-9][A-Z]_*.svg",
        "[A-Z][0-9]-[0-9]_*.svg",
        "[A-Z][0-9]-[0-9][A-Z]_*.svg",
        "[A-Z][0-9][0-9]-[0-9]_*.svg",
        "[A-Z][A-Z][A-Z]-[0-9][0-9][0-9]_*.svg",
        "[A-Z][A-Z][A-Z]-[0-9][0-9][0-9][A-Z]_*.svg",
    ):
        for stale in out.glob(pattern):
            stale.unlink()

    if sheets is not None:
        return _export_custom_register(
            model,
            out,
            register=sheets,
            plan_level=plan_level,
            plan_scale=plan_scale,
            set_type=set_type,
            date=date,
            units=units,
            dim_tiers=dim_tiers,
            fractional_grids=fractional_grids,
            key_plan=key_plan,
            room_areas=room_areas,
            line_weights=line_weights,
            hatches=hatches,
            stamp_block=stamp_block,
        )

    nominal_scale = _scale_note_for(plan_scale, units)
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
    cover_notes: list[str] = []

    def _level_els(lname: str) -> list[Element]:
        lid = level_ids.get(lname)
        return [el for el in model.elements if el.level_id == lid]

    # ── building extents + the two A-301 section cuts (marked on floor plans)
    cut_a, cut_b = _building_cuts(model)
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
            units=units,
            section_marks=section_marks,
            dim_tiers=dim_tiers,
            fractional_grids=fractional_grids,
            key_plan=key_plan,
            room_areas=room_areas,
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
            elev_svg = render_elevation_svg(
                model, direction, scale=plan_scale, units=units, weights=line_weights
            )
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
            model, p0, p1, scale=plan_scale, units=units,
            weights=line_weights, hatches=hatches,
            title=f"{model.name} — Section {lab}-{lab}",
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
        # H-series assignment: which elements split out of M onto HVAC sheets.
        # Tagged supply (HVS* / "supply") and exhaust/return (HVE* / "exhaust" /
        # "return") ducts + hvs_/hve_ riser equipment. If no duct carries any
        # system tag at all, fall back to all ducts on H-101 (no H-102 split).
        h_assign: dict[str, str] = {}
        for el in model.elements:
            h_tag = _hvac_h_system(el)
            if h_tag:
                h_assign[el.id] = h_tag
        if not h_assign:
            all_ducts = [el for el in model.elements if _is_duct_run(el)]
            if all_ducts and all(
                not str(el.params.get("system") or "").strip() for el in all_ducts
            ):
                h_assign = {el.id: "HVS" for el in all_ducts}

        # Content-driven discipline plan sheets, per level (plan + legend cell)
        disciplines: list[tuple[str, str, str, Any, set[str]]] = [
            ("S", "structural", "Structural Plan", _is_column, {"grids", "columns", "beams"}),
            ("M", "mechanical", "Mechanical Plan", _is_mech, {"grids", "ducts"}),
            ("P", "piping", "Piping Plan", _is_piping, {"pipes"}),
            ("E", "raceway", "Raceway Plan", _is_raceway, {"conduit", "cable_tray"}),
        ]
        emitted_p = False
        for disc, slug, disc_title, pred, include in disciplines:
            # M keeps only non-H mechanical: HVS/HVE ducts + risers move to H-1xx
            render_model = model
            if disc == "M" and h_assign:
                render_model = model.model_copy(
                    update={
                        "elements": [
                            el for el in model.elements if el.id not in h_assign
                        ]
                    }
                )
            n = 0
            for lname in plan_levels:
                lvl_els = _level_els(lname)
                if disc == "M":
                    lvl_els = [el for el in lvl_els if el.id not in h_assign]
                if disc == "S":
                    match = any(_is_column(el) or _is_beam(el) for el in lvl_els)
                else:
                    match = any(pred(el) for el in lvl_els)
                if not match:
                    continue
                n += 1
                sn = f"{disc}-1{n:02d}"
                view = render_plan_view(
                    render_model,
                    lname,
                    scale=plan_scale,
                    show_dimensions=True,
                    include=include,
                    ghost_walls=True,
                    units=units,
                    title=f"{model.name} — {disc_title} {lname}",
                )
                legend = _legend_view(_discipline_legend(disc, lvl_els))
                sh = _multi_sheet(
                    model,
                    sheet_no=sn,
                    stamp_block=stamp_block and disc == "S",
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

        # ── H-1xx: HVAC supply / exhaust plans split out of M, per level
        if h_assign:
            h_titles = {"HVS": "HVAC Supply Plan", "HVE": "HVAC Exhaust / Return Plan"}
            hn = 0
            for lname in plan_levels:
                lvl_els = _level_els(lname)
                for h_tag in ("HVS", "HVE"):
                    sel = [el for el in lvl_els if h_assign.get(el.id) == h_tag]
                    if not sel:
                        continue
                    hn += 1
                    sn = f"H-1{hn:02d}"
                    sel_ids = {el.id for el in sel}
                    sub = model.model_copy(
                        update={
                            "elements": [
                                el
                                for el in model.elements
                                if el.id in sel_ids or el.category == "wall"
                            ]
                        }
                    )
                    view = render_plan_view(
                        sub,
                        lname,
                        scale=plan_scale,
                        show_dimensions=True,
                        include={"grids", "ducts", "equipment"},
                        ghost_walls=True,
                        units=units,
                        title=f"{model.name} — {h_titles[h_tag]} {lname}",
                    )
                    n_ducts = sum(1 for e in sel if _is_duct_run(e))
                    n_risers = len(sel) - n_ducts
                    h_entries: list[tuple[str, str, int]] = []
                    duct_color = "#2e7d32" if h_tag == "HVS" else "#b71c1c"
                    if n_ducts:
                        h_entries.append((f"{h_tag} duct runs", duct_color, n_ducts))
                    if n_risers:
                        h_entries.append((f"{h_tag} risers", "#0b5cab", n_risers))
                    legend = _legend_view(h_entries)
                    sh = _multi_sheet(
                        model,
                        sheet_no=sn,
                        title=f"{h_titles[h_tag]} — {lname}",
                        cells=[
                            (view, f"{h_titles[h_tag]} {lname}", nominal_scale, plan_scale),
                            (legend, "Legend", ""),
                        ],
                        date=date,
                        scale_note=nominal_scale,
                        arrange="row",
                        weights=[0.76, 0.24],
                        north_arrow=True,
                    )
                    fname = f"{sn}_hvac.svg"
                    (out / fname).write_text(sh, encoding="utf-8")
                    sheets.append(
                        {
                            "no": sn,
                            "title": f"{h_titles[h_tag]} {lname}",
                            "file": fname,
                            "discipline": "H",
                        }
                    )

        # ── EQ-1xx: per-room equipment arrangements (enlarged, cropped plans)
        eq_rooms: list[tuple[str, Element, list[Element]]] = []
        for lname in plan_levels:
            lid = level_ids.get(lname)
            lvl_rooms = [
                el for el in model.elements if el.category == "room" and el.level_id == lid
            ]
            lvl_eq = [
                el
                for el in model.elements
                if el.category == "equipment" and el.level_id == lid
            ]
            for room in lvl_rooms:
                boundary = room.params.get("boundary_mm") or []
                if len(boundary) < 3:
                    continue
                contained = []
                for eq in lvl_eq:
                    o = eq.params.get("origin_mm")
                    try:
                        if o is not None and _point_in_poly(
                            float(o[0]), float(o[1]), boundary
                        ):
                            contained.append(eq)
                    except (TypeError, ValueError, IndexError):
                        continue
                if contained:
                    eq_rooms.append((lname, room, contained))
        for eq_i, (lname, room, contained) in enumerate(
            eq_rooms[:MAX_EQ_SHEETS], start=1
        ):
            boundary = room.params.get("boundary_mm") or []
            bxs = [float(p[0]) for p in boundary]
            bys = [float(p[1]) for p in boundary]
            crop = (
                min(bxs) - 1000.0,
                min(bys) - 1000.0,
                max(bxs) + 1000.0,
                max(bys) + 1000.0,
            )
            room_name = room.name or "Room"
            view = render_plan_view(
                model,
                lname,
                scale=plan_scale,
                show_dimensions=False,
                include={"equipment"},
                ghost_walls=True,
                crop_mm=crop,
                units=units,
                title=f"{model.name} — Equipment Arrangement {room_name}",
            )
            eq_tbl_rows = [
                [
                    _fmt_cell(eq.name),
                    _fmt_cell(eq.params.get("kind")),
                    _fmt_cell(eq.params.get("size_mm")),
                    _fmt_cell(eq.params.get("z0_mm")),
                ]
                for eq in contained
            ]
            tbl = table_view(
                ["NAME", "KIND", "W×D×H mm", "Z0 mm"],
                eq_tbl_rows,
                title=f"Equipment — {room_name}",
            )
            sn = f"EQ-1{eq_i:02d}"
            sh = _multi_sheet(
                model,
                sheet_no=sn,
                title=f"Equipment Arrangement — {room_name}",
                cells=[
                    (view, f"Equipment Arrangement {room_name}", nominal_scale, plan_scale),
                    (tbl, "Room Equipment", "NTS"),
                ],
                date=date,
                scale_note=nominal_scale,
                arrange="row",
                weights=[0.64, 0.36],
                north_arrow=True,
            )
            fname = f"{sn}_equipment_arrangement.svg"
            (out / fname).write_text(sh, encoding="utf-8")
            sheets.append(
                {
                    "no": sn,
                    "title": f"Equipment Arrangement {room_name}",
                    "file": fname,
                    "discipline": "EQ",
                }
            )
        if len(eq_rooms) > MAX_EQ_SHEETS:
            cover_notes.append(
                f"NOTE: {len(eq_rooms) - MAX_EQ_SHEETS} additional equipment room(s) "
                f"beyond the {MAX_EQ_SHEETS}-sheet EQ series cap — not sheeted."
            )

        # ── N-1xx: shielding & confinement plan (walls color-coded by type)
        has_shield_walls = any(
            el.category == "wall"
            and "SHIELD" in str(el.type_id or el.params.get("type_id") or "").upper()
            for el in model.elements
        )
        has_shield_rooms = any(
            el.category == "room" and _room_suggests_shielding(el)
            for el in model.elements
        )
        if has_shield_walls or has_shield_rooms:
            nn = 0
            for lname in plan_levels:
                lvl_walls = [el for el in _level_els(lname) if el.category == "wall"]
                if not lvl_walls:
                    continue
                nn += 1
                sn = f"N-1{nn:02d}"
                view = render_plan_view(
                    model,
                    lname,
                    scale=plan_scale,
                    show_dimensions=True,
                    include={"walls", "rooms", "grids"},
                    room_tags=True,
                    wall_fill_by_type=SHIELD_WALL_FILLS,
                    units=units,
                    title=f"{model.name} — Shielding & Confinement {lname}",
                )
                legend = _shield_legend_view(lvl_walls)
                sh = _multi_sheet(
                    model,
                    sheet_no=sn,
                    title=f"Shielding & Confinement Plan — {lname}",
                    cells=[
                        (
                            view,
                            f"Shielding & Confinement {lname}",
                            nominal_scale,
                            plan_scale,
                        ),
                        (legend, "Legend", ""),
                    ],
                    date=date,
                    scale_note=nominal_scale,
                    arrange="row",
                    weights=[0.74, 0.26],
                    north_arrow=True,
                )
                fname = f"{sn}_shielding.svg"
                (out / fname).write_text(sh, encoding="utf-8")
                sheets.append(
                    {
                        "no": sn,
                        "title": f"Shielding & Confinement Plan {lname}",
                        "file": fname,
                        "discipline": "N",
                    }
                )

        # ── C-1xx: site / underground plan (underground equipment + ghost shell)
        underground = [el for el in model.elements if _is_underground(el)]
        if underground:
            cn = 0
            for lname in plan_levels:
                lid = level_ids.get(lname)
                sel = [el for el in underground if el.level_id == lid]
                if not sel:
                    continue
                cn += 1
                sn = f"C-1{cn:02d}"
                sel_ids = {el.id for el in sel}
                sub = model.model_copy(
                    update={
                        "elements": [
                            el
                            for el in model.elements
                            if el.id in sel_ids or el.category in {"wall", "slab"}
                        ]
                    }
                )
                view = render_plan_view(
                    sub,
                    lname,
                    scale=plan_scale,
                    show_dimensions=True,
                    include={"equipment", "slabs"},
                    ghost_walls=True,
                    units=units,
                    title=f"{model.name} — Site / Underground {lname}",
                )
                ug_by_name: dict[str, int] = {}
                for el in sel:
                    key = el.name or "(structure)"
                    ug_by_name[key] = ug_by_name.get(key, 0) + 1
                legend = _legend_view(
                    [(nm, "#6d4c41", ct) for nm, ct in sorted(ug_by_name.items())]
                )
                sh = _multi_sheet(
                    model,
                    sheet_no=sn,
                    title=f"Site / Underground Plan — {lname}",
                    cells=[
                        (view, f"Site / Underground {lname}", nominal_scale, plan_scale),
                        (legend, "Legend", ""),
                    ],
                    date=date,
                    scale_note=nominal_scale,
                    arrange="row",
                    weights=[0.76, 0.24],
                    north_arrow=True,
                )
                fname = f"{sn}_site_underground.svg"
                (out / fname).write_text(sh, encoding="utf-8")
                sheets.append(
                    {
                        "no": sn,
                        "title": f"Site / Underground Plan {lname}",
                        "file": fname,
                        "discipline": "C",
                    }
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
    note_lines = "".join(
        f'<text x="0" y="{92 + 14 * i}" font-size="10" font-family="sans-serif" '
        f'fill="#555">{esc(note)}</text>\n'
        for i, note in enumerate(cover_notes)
    )
    index_y = 96 + 14 * len(cover_notes)
    head = (
        f'<text x="0" y="34" font-size="26" font-family="sans-serif" '
        f'font-weight="bold">{model.name}</text>\n'
        f'<text x="0" y="58" font-size="14" font-family="sans-serif">{set_label}</text>\n'
        f'<text x="0" y="76" font-size="10" font-family="sans-serif" fill="#8a1a1a">'
        f"ENGINEERING ESTIMATE · LLM-BIM · issued {date}</text>\n"
        f"{note_lines}"
        f'<g transform="translate(0,{index_y})">\n{index_view.body}\n</g>'
    )
    cover_view = DrawingView(
        width=max(index_view.width, 560), height=index_y + index_view.height, body=head
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


# ── configurable sheet register ──────────────────────────────────────────────

SHEET_KINDS = (
    "cover", "plan", "elevations", "sections", "schedule", "details", "custom_svg", "doc",
)

_ELEV_NAMES = {"N": "North Elevation", "S": "South Elevation",
               "E": "East Elevation", "W": "West Elevation"}


def _sanitize_no(no: str) -> str:
    """Sheet number → filename stem: ``A0.1`` → ``A0-1``, ``MEP-101`` → ``MEP-101``."""
    stem = re.sub(r"[^A-Za-z0-9]+", "-", str(no).strip()).strip("-")
    if not stem:
        raise ValidationError("sheet 'no' must contain letters/digits", no=no)
    return stem


def _discipline_of(spec: dict) -> str:
    """Explicit ``discipline`` or the alpha prefix of the sheet no (``A0.1`` → ``A``)."""
    disc = spec.get("discipline")
    if disc:
        return str(disc)
    m = re.match(r"[A-Za-z]+", str(spec.get("no") or ""))
    return m.group(0).upper() if m else "A"


def _require_register_entry(spec: Any) -> dict:
    if not isinstance(spec, dict):
        raise ValidationError("each sheets[] entry must be a dict", entry=repr(spec)[:80])
    for key in ("no", "title", "kind"):
        if not spec.get(key):
            raise ValidationError(f"sheets[] entry missing required key {key!r}", entry=spec)
    kind = str(spec["kind"])
    if kind not in SHEET_KINDS:
        raise ValidationError(
            f"unknown sheet kind {kind!r}; supported kinds: {', '.join(SHEET_KINDS)}",
            kind=kind,
            supported_kinds=list(SHEET_KINDS),
        )
    return spec


def _generic_schedule_view(model: ProjectModel, kind: str, title: str) -> DrawingView:
    """Ruled table for any ``schedule_rows`` kind — columns from the row keys."""
    rows = schedule_rows(model, kind)
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    cols = [c for c in cols if c not in {"id", "level_id"}][:8]
    if not cols:
        return table_view([kind.upper()], [["(none in model)"]], title=title)
    data = [[_fmt_cell(r.get(c)) for c in cols] for r in rows]
    headers = [c.replace("_", " ").upper() for c in cols]
    return table_view(headers, data, title=title)


def _doc_view(text: str, title: str) -> DrawingView:
    """Markdown-ish text → simple text sheet (headings, bullets, wrapped body)."""
    width = 900.0
    parts: list[str] = ['<g class="doc-sheet" font-family="sans-serif" fill="#111">']
    y = 30.0
    parts.append(
        f'<text x="0" y="{y:.1f}" font-size="20" font-weight="bold">{esc(title)}</text>'
    )
    y += 28.0
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            y += 8.0
            continue
        stripped = line.lstrip("#").strip()
        if line.startswith("## "):
            y += 8.0
            parts.append(
                f'<text x="0" y="{y:.1f}" font-size="13" font-weight="bold">'
                f"{esc(stripped)}</text>"
            )
            y += 18.0
            continue
        if line.startswith("# "):
            y += 10.0
            parts.append(
                f'<text x="0" y="{y:.1f}" font-size="16" font-weight="bold">'
                f"{esc(stripped)}</text>"
            )
            y += 20.0
            continue
        indent = 14.0 if line.lstrip().startswith(("-", "*")) else 0.0
        body_text = line.lstrip()
        if indent:
            body_text = "• " + body_text[1:].lstrip()
        for wrapped in textwrap.wrap(body_text, width=100) or [""]:
            parts.append(
                f'<text x="{indent:.0f}" y="{y:.1f}" font-size="10.5">{esc(wrapped)}</text>'
            )
            y += 15.0
    parts.append("</g>")
    return DrawingView(width=width, height=max(y + 10.0, 120.0), body="\n".join(parts),
                       title=title)


def _custom_cover_view(
    model: ProjectModel, register: list[dict], spec: dict, date: str
) -> DrawingView:
    """Cover body: project head + honesty note + index of the CUSTOM register."""
    rows = [[str(s["no"]), _discipline_of(s), str(s["title"])] for s in register]
    index_view = table_view(["SHEET", "DISC", "TITLE"], rows, title="Sheet Index")
    subtitle = str(spec.get("subtitle") or "Construction Drawing Set")
    notes = [str(n) for n in (spec.get("notes") or [])]
    note_lines = "".join(
        f'<text x="0" y="{92 + 14 * i}" font-size="10" font-family="sans-serif" '
        f'fill="#555">{esc(note)}</text>\n'
        for i, note in enumerate(notes)
    )
    index_y = 96 + 14 * len(notes)
    head = (
        f'<text x="0" y="34" font-size="26" font-family="sans-serif" '
        f'font-weight="bold">{esc(model.name)}</text>\n'
        f'<text x="0" y="58" font-size="14" font-family="sans-serif">{esc(subtitle)}</text>\n'
        f'<text x="0" y="76" font-size="10" font-family="sans-serif" fill="#8a1a1a">'
        f"ENGINEERING ESTIMATE · LLM-BIM · issued {esc(date)}</text>\n"
        f"{note_lines}"
        f'<g transform="translate(0,{index_y})">\n{index_view.body}\n</g>'
    )
    return DrawingView(
        width=max(index_view.width, 560), height=index_y + index_view.height, body=head
    )


def _custom_svg_view(model: ProjectModel, spec: dict) -> DrawingView:
    """Resolve a custom_svg entry: DrawingView / full-SVG string / provider callback."""
    source: Any = spec.get("view")
    provider = spec.get("provider")
    if source is None and provider is not None:
        if not callable(provider):
            raise ValidationError("custom_svg 'provider' must be callable", no=spec.get("no"))
        try:
            sig = inspect.signature(provider)
            takes_arg = any(
                p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL)
                for p in sig.parameters.values()
            )
        except (TypeError, ValueError):
            takes_arg = True
        source = provider(model) if takes_arg else provider()
    if isinstance(source, DrawingView):
        return source
    if isinstance(source, str) and source.strip():
        return _view_from_full_svg(source, str(spec.get("title") or ""))
    raise ValidationError(
        "custom_svg sheet needs a 'view' (DrawingView or SVG string) or a "
        "'provider' callback returning one",
        no=spec.get("no"),
    )


def _export_custom_register(
    model: ProjectModel,
    out: Path,
    *,
    register: list[dict],
    plan_level: str | None,
    plan_scale: float,
    set_type: str,
    date: str,
    units: str = "metric",
    dim_tiers: bool = False,
    fractional_grids: bool = False,
    key_plan: bool = False,
    room_areas: bool = False,
    line_weights: bool = False,
    hatches: bool = False,
    stamp_block: bool = False,
) -> dict:
    """Emit a caller-defined sheet register (replaces the default A-1xx… set).

    ``units`` is the export-level default; each entry may override it with a
    per-sheet ``units`` opt (``"metric"``/``"imperial"``). Likewise the CD
    anatomy defaults ``dim_tiers`` / ``fractional_grids`` / ``key_plan`` /
    ``room_areas`` may be overridden per ``plan`` entry, ``line_weights`` /
    ``hatches`` per ``elevations``/``sections`` entry, and ``stamp_block``
    per any entry (export default applies it to S-discipline sheets).
    """
    specs = [_require_register_entry(s) for s in register]
    level_ids = {lvl.name: lvl.id for lvl in model.levels}
    plan_levels = [
        lvl.name
        for lvl in model.levels
        if any(el.level_id == lvl.id for el in model.elements)
    ]
    if not plan_levels:
        plan_levels = [plan_level or (model.levels[0].name if model.levels else "L1")]
    default_level = plan_level or plan_levels[0]
    _ax, _ay, aw, ah = drawing_area()
    emitted: list[dict] = []

    def _emit(spec: dict, svg: str, *, no: str | None = None, title: str | None = None) -> None:
        sheet_no = no if no is not None else str(spec["no"])
        slug = "custom" if spec["kind"] == "custom_svg" else str(spec["kind"])
        fname = f"{_sanitize_no(sheet_no)}_{slug}.svg"
        (out / fname).write_text(svg, encoding="utf-8")
        emitted.append(
            {
                "no": sheet_no,
                "title": title if title is not None else str(spec["title"]),
                "file": fname,
                "discipline": _discipline_of(spec),
                "kind": str(spec["kind"]),
            }
        )

    def _spec_stamp(spec: dict) -> bool:
        # per-sheet override wins; the export-level default applies the
        # reserved PE/SE stamp square to S-discipline sheets only
        if "stamp_block" in spec:
            return bool(spec["stamp_block"])
        return stamp_block and _discipline_of(spec) == "S"

    for spec in specs:
        kind = str(spec["kind"])
        no = str(spec["no"])
        title = str(spec["title"])
        sc = float(spec.get("scale") or plan_scale)
        sheet_units = _check_set_units(str(spec.get("units") or units))
        nominal = _scale_note_for(sc, sheet_units)

        if kind == "cover":
            view = _custom_cover_view(model, specs, spec, date)
            svg = _sheet_from_view(
                model, sheet_no=no, title=title, view=view,
                scale_note=str(spec.get("scale_note") or "NTS"), date=date,
                stamp_block=_spec_stamp(spec),
            )
            _emit(spec, svg)

        elif kind == "plan":
            lvl = str(spec.get("level") or default_level)
            if lvl not in level_ids:
                raise ValidationError("plan sheet references unknown level", no=no, level=lvl)
            include = set(spec["include"]) if spec.get("include") else None
            crop_raw = spec.get("crop")
            crop = tuple(float(v) for v in crop_raw) if crop_raw else None
            if crop is not None and len(crop) != 4:
                raise ValidationError("plan 'crop' must be (x0, y0, x1, y1) mm", no=no)
            view = render_plan_view(
                model,
                lvl,
                scale=sc,
                show_dimensions=bool(spec.get("dimensions", True)),
                grid_dims=include is None,
                room_tags=bool(spec.get("room_tags", include is None)),
                tags=bool(spec.get("tags", False)),
                units=sheet_units,
                include=include,
                ghost_walls=bool(spec.get("ghost_walls", False)),
                crop_mm=crop,  # type: ignore[arg-type]
                dim_tiers=bool(spec.get("dim_tiers", dim_tiers)),
                fractional_grids=bool(spec.get("fractional_grids", fractional_grids)),
                key_plan=bool(spec.get("key_plan", key_plan)),
                room_areas=bool(spec.get("room_areas", room_areas)),
                title=f"{model.name} — {title}",
            )
            svg = _sheet_from_view(
                model, sheet_no=no, title=title, view=view,
                scale_note=str(spec.get("scale_note") or nominal),
                px_per_mm=sc, north_arrow=True, date=date,
                stamp_block=_spec_stamp(spec),
            )
            _emit(spec, svg)

        elif kind == "elevations":
            pair = [str(d).upper() for d in (spec.get("pair") or ["N", "S"])]
            bad = [d for d in pair if d not in _ELEV_NAMES]
            if bad:
                raise ValidationError("elevations 'pair' must use N|S|E|W", no=no, pair=pair)
            sheet_lw = bool(spec.get("line_weights", line_weights))
            cells: list[tuple] = []
            for direction in pair:
                cell_title = _ELEV_NAMES[direction]
                elev_svg = render_elevation_svg(
                    model, direction, scale=sc, units=sheet_units, weights=sheet_lw
                )
                cells.append((_view_from_full_svg(elev_svg, cell_title), cell_title,
                              str(spec.get("scale_note") or nominal), sc))
            svg = _multi_sheet(
                model, sheet_no=no, title=title, cells=cells, date=date,
                scale_note=str(spec.get("scale_note") or nominal),
                stamp_block=_spec_stamp(spec),
            )
            _emit(spec, svg)

        elif kind == "sections":
            sheet_lw = bool(spec.get("line_weights", line_weights))
            sheet_hatch = bool(spec.get("hatches", hatches))
            cut_a, cut_b = _building_cuts(model)
            sec_cells: list[tuple] = []
            for (p0, p1), lab in ((cut_a, "A"), (cut_b, "B")):
                sec_svg = render_section_svg(
                    model, p0, p1, scale=sc, units=sheet_units,
                    weights=sheet_lw, hatches=sheet_hatch,
                    title=f"{model.name} — Section {lab}-{lab}",
                )
                sec_cells.append(
                    (_view_from_full_svg(sec_svg, f"Section {lab}-{lab}"),
                     f"Section {lab}-{lab}", str(spec.get("scale_note") or nominal), sc)
                )
            svg = _multi_sheet(
                model, sheet_no=no, title=title, cells=sec_cells, date=date,
                scale_note=str(spec.get("scale_note") or nominal),
                stamp_block=_spec_stamp(spec),
            )
            _emit(spec, svg)

        elif kind == "schedule":
            kinds_raw = spec.get("schedule") or spec.get("schedule_kind")
            if not kinds_raw:
                raise ValidationError(
                    "schedule sheet needs a 'schedule' kind (or list of kinds)", no=no
                )
            kinds = [str(k) for k in kinds_raw] if isinstance(kinds_raw, (list, tuple)) \
                else [str(kinds_raw)]
            note = str(spec.get("scale_note") or "NTS")
            if len(kinds) == 1:
                rows = schedule_rows(model, kinds[0])
                n_pages = max(1, math.ceil(len(rows) / SCHEDULE_ROWS_PER_SHEET))
                cols: list[str] = []
                for r in rows:
                    for k in r:
                        if k not in cols:
                            cols.append(k)
                cols = [c for c in cols if c not in {"id", "level_id"}][:8]
                for pi in range(n_pages):
                    page_no = no if pi == 0 else f"{no}{chr(ord('A') + pi)}"
                    page_title = title if n_pages == 1 else f"{title} ({pi + 1}/{n_pages})"
                    page_rows = rows[
                        pi * SCHEDULE_ROWS_PER_SHEET : (pi + 1) * SCHEDULE_ROWS_PER_SHEET
                    ]
                    if cols:
                        view = table_view(
                            [c.replace("_", " ").upper() for c in cols],
                            [[_fmt_cell(r.get(c)) for c in cols] for r in page_rows],
                            title=page_title,
                        )
                    else:
                        view = table_view([kinds[0].upper()], [["(none in model)"]],
                                          title=page_title)
                    svg = _sheet_from_view(
                        model, sheet_no=page_no, title=page_title, view=view,
                        scale_note=note, date=date,
                        stamp_block=_spec_stamp(spec),
                    )
                    _emit(spec, svg, no=page_no, title=page_title)
            else:
                tbl_cells: list[tuple] = [
                    (_generic_schedule_view(model, k, f"{k.title()} Schedule"),
                     f"{k.title()} Schedule", "NTS")
                    for k in kinds[:4]
                ]
                svg = _multi_sheet(
                    model, sheet_no=no, title=title, cells=tbl_cells, date=date,
                    scale_note=note,
                    stamp_block=_spec_stamp(spec),
                )
                _emit(spec, svg)

        elif kind == "details":
            det_specs = spec.get("details")
            if not det_specs:
                raise ValidationError(
                    "details sheet needs 'details': list of {id, title, scale, ops}", no=no
                )
            view = render_detail_sheet(det_specs, width=aw - 10, height=ah - 10)
            svg = _sheet_from_view(
                model, sheet_no=no, title=title, view=view,
                scale_note=str(spec.get("scale_note") or "AS NOTED"), date=date,
                stamp_block=_spec_stamp(spec),
            )
            _emit(spec, svg)

        elif kind == "custom_svg":
            view = _custom_svg_view(model, spec)
            svg = _sheet_from_view(
                model, sheet_no=no, title=title, view=view,
                scale_note=str(spec.get("scale_note") or "NTS"), date=date,
                stamp_block=_spec_stamp(spec),
            )
            _emit(spec, svg)

        else:  # kind == "doc"
            view = _doc_view(str(spec.get("text") or spec.get("markdown") or ""), title)
            svg = _sheet_from_view(
                model, sheet_no=no, title=title, view=view,
                scale_note=str(spec.get("scale_note") or "NTS"), date=date,
                stamp_block=_spec_stamp(spec),
            )
            _emit(spec, svg)

    sched = out / "schedules"
    sched.mkdir(exist_ok=True)
    for csv_kind in ("room", "door", "window", "wall"):
        try:
            export_schedule_csv(model, csv_kind, sched / f"{csv_kind}.csv")
        except Exception:
            pass

    manifest = {
        "project": model.name,
        "level": default_level,
        "levels": plan_levels,
        "set_type": set_type,
        "register": "custom",
        "date": date,
        "sheets": emitted,
    }
    (out / "SHEET_INDEX.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
