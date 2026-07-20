"""Plan-view SVG derivation from the semantic model."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any

from llmbim_core.model import Element, ProjectModel
from llmbim_geometry.primitives import point_along_segment

from llmbim_drawings.svg_util import esc, fmt
from llmbim_drawings.view import DrawingView


def _wall_endpoints(el: Element) -> tuple[float, float, float, float, float] | None:
    try:
        start = el.params["start_mm"]
        end = el.params["end_mm"]
        thickness = float(el.params.get("thickness_mm", 0.0))
    except (KeyError, TypeError):
        return None
    if len(start) < 2 or len(end) < 2:
        return None
    return float(start[0]), float(start[1]), float(end[0]), float(end[1]), thickness


def _wall_band(
    x0: float, y0: float, x1: float, y1: float, thickness: float
) -> list[tuple[float, float]]:
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length == 0:
        return []
    nx, ny = -dy / length, dx / length
    h = thickness / 2.0
    return [
        (x0 + nx * h, y0 + ny * h),
        (x1 + nx * h, y1 + ny * h),
        (x1 - nx * h, y1 - ny * h),
        (x0 - nx * h, y0 - ny * h),
    ]


def _wall_join_extensions_plan(
    walls: list[tuple[Element, tuple[float, float, float, float, float]]],
) -> dict[str, tuple[float, float]]:
    """Extend wall endpoints at shared corners (half of adjacent thickness)."""
    ext: dict[str, list[float]] = {el.id: [0.0, 0.0] for el, _ in walls}
    tol = 25.0
    for i, (el_a, a) in enumerate(walls):
        ax0, ay0, ax1, ay1, ath = a
        for el_b, b in walls[i + 1 :]:
            bx0, by0, bx1, by1, bth = b
            for end_i, pa, pb, oth in (
                (0, (ax0, ay0), (bx0, by0), bth),
                (0, (ax0, ay0), (bx1, by1), bth),
                (1, (ax1, ay1), (bx0, by0), bth),
                (1, (ax1, ay1), (bx1, by1), bth),
            ):
                if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) <= tol:
                    ext[el_a.id][end_i] = max(ext[el_a.id][end_i], oth / 2.0)
            for end_i, pb, pa, oth in (
                (0, (bx0, by0), (ax0, ay0), ath),
                (0, (bx0, by0), (ax1, ay1), ath),
                (1, (bx1, by1), (ax0, ay0), ath),
                (1, (bx1, by1), (ax1, ay1), ath),
            ):
                if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) <= tol:
                    ext[el_b.id][end_i] = max(ext[el_b.id][end_i], oth / 2.0)
    return {k: (v[0], v[1]) for k, v in ext.items()}


# Point-placed HVAC device fitting types (drawn in the fittings pass)
_HVAC_DEVICE_TYPES = {"vav", "fire_damper", "smoke_damper", "diffuser", "grille"}


def _plan_group(el: Element) -> str:
    """Category group an MEP-ish element belongs to for ``include`` filtering."""
    ft = str(el.params.get("fitting_type") or "")
    if el.category == "conduit" or ft == "conduit":
        return "conduit"
    if el.category == "cable_tray" or ft == "cable_tray":
        return "cable_tray"
    if el.category == "beam" or ft == "beam":
        return "beams"
    if el.category in {"duct", "hvac"} or ft in {"duct", "flex_duct"} or ft in _HVAC_DEVICE_TYPES:
        return "ducts"
    return "pipes"


def _room_centroid_area(room: Element) -> tuple[float, float, float] | None:
    """(cx, cy, area_mm2) of a room boundary; shoelace fallback for area."""
    boundary = room.params.get("boundary_mm") or []
    if len(boundary) < 3:
        return None
    cx = sum(float(p[0]) for p in boundary) / len(boundary)
    cy = sum(float(p[1]) for p in boundary) / len(boundary)
    area_mm2 = room.params.get("area_mm2")
    if area_mm2 is None:
        a = 0.0
        n = len(boundary)
        for i in range(n):
            x1, y1 = float(boundary[i][0]), float(boundary[i][1])
            x2, y2 = float(boundary[(i + 1) % n][0]), float(boundary[(i + 1) % n][1])
            a += x1 * y2 - x2 * y1
        area_mm2 = abs(a) / 2.0
    return cx, cy, float(area_mm2)


def _dim_line(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    project,
    scale: float,
    label: str,
) -> list[str]:
    """Simple dimension annotation between two plan points."""
    px0, py0 = project(x0, y0)
    px1, py1 = project(x1, y1)
    mx, my = (px0 + px1) / 2, (py0 + py1) / 2
    # offset perpendicular in screen space
    dx, dy = px1 - px0, py1 - py0
    L = math.hypot(dx, dy) or 1.0
    ox, oy = -dy / L * 12, dx / L * 12
    return [
        f'<line x1="{fmt(px0 + ox)}" y1="{fmt(py0 + oy)}" x2="{fmt(px1 + ox)}" '
        f'y2="{fmt(py1 + oy)}" stroke="#666" stroke-width="0.8"/>',
        f'<line x1="{fmt(px0)}" y1="{fmt(py0)}" x2="{fmt(px0 + ox)}" y2="{fmt(py0 + oy)}" '
        f'stroke="#666" stroke-width="0.6"/>',
        f'<line x1="{fmt(px1)}" y1="{fmt(py1)}" x2="{fmt(px1 + ox)}" y2="{fmt(py1 + oy)}" '
        f'stroke="#666" stroke-width="0.6"/>',
        f'<text x="{fmt(mx + ox)}" y="{fmt(my + oy - 2)}" text-anchor="middle" '
        f'font-size="{fmt(max(8, 10))}" fill="#444" font-family="sans-serif">{esc(label)}</text>',
    ]


def render_plan_view(
    model: ProjectModel,
    level: str,
    *,
    margin_mm: float = 500.0,
    scale: float = 0.05,
    view_range_mm: float = 1200.0,  # noqa: ARG001
    title: str | None = None,
    show_dimensions: bool = True,
    max_dimensions: int = 24,
    include: set[str] | None = None,
    ghost_walls: bool = False,
    grid_dims: bool = False,
    room_tags: bool = False,
    section_marks: Sequence[Mapping[str, Any]] | None = None,
    crop_mm: tuple[float, float, float, float] | None = None,
    wall_fill_by_type: dict[str, str] | None = None,
) -> DrawingView:
    """Build a plan DrawingView (inner body + size).

    ``include``: optional set of category groups to draw — any of
    ``walls, openings, rooms, equipment, columns, beams, grids, notes,
    pipes, ducts, conduit, cable_tray, slabs`` (``slabs`` is opt-in only:
    it never draws with ``include=None``). ``None`` (default) draws
    everything exactly as before. ``ghost_walls`` draws wall outlines light
    grey with no fill (context for discipline plans) regardless of
    ``include``.

    ``crop_mm``: optional ``(x0, y0, x1, y1)`` plan window — the view extents
    clip to this box (enlarged room views), elements wholly outside are
    skipped and partially-inside geometry is clipped at the window edge.

    ``wall_fill_by_type``: optional ``type_id → fill color`` map for solid
    walls (shielding plans); walls whose type is not in the map render with
    a diagonal hatch. Replaces the per-layer band fills.

    Drafting extras (all additive, default off so existing output is
    unchanged): ``grid_dims`` draws running dimension chains between grid
    positions (top for the U axis, left for the V axis) plus the overall
    dimension; ``room_tags`` replaces plain room labels with boxed
    name + area tags; ``section_marks`` draws section cut markers — each item
    a mapping with ``p0``/``p1`` plan points (mm), ``label`` (e.g. ``"A"``)
    and ``sheet`` reference (e.g. ``"A-301"``).
    """

    def _on(group: str) -> bool:
        return include is None or group in include

    def _eq_on(eq: Element) -> bool:
        """Equipment filter: mechanical plans keep HVAC equipment only."""
        if include is None or "equipment" in include:
            return True
        if "ducts" in include:
            return str(eq.params.get("kind") or "").lower() in {"duct", "hvac", "ahu"}
        return False

    def _mep_on(el: Element) -> bool:
        return include is None or _plan_group(el) in include

    def _el_bbox(el: Element) -> tuple[float, float, float, float] | None:
        """Plan-space bbox of an element's stored geometry, or None."""
        pts: list[tuple[float, float]] = []
        for key in ("polygon_mm", "boundary_mm"):
            for pt in el.params.get(key) or []:
                try:
                    pts.append((float(pt[0]), float(pt[1])))
                except (TypeError, ValueError, IndexError):
                    continue
        for key in ("start_mm", "end_mm", "origin_mm", "position_mm"):
            v = el.params.get(key)
            try:
                if v is not None and len(v) >= 2:
                    pts.append((float(v[0]), float(v[1])))
            except (TypeError, ValueError):
                continue
        if not pts:
            return None
        return (
            min(p[0] for p in pts),
            min(p[1] for p in pts),
            max(p[0] for p in pts),
            max(p[1] for p in pts),
        )

    def _in_crop(el: Element) -> bool:
        """Keep elements overlapping the crop window; wholly-outside skipped."""
        if crop_mm is None:
            return True
        bb = _el_bbox(el)
        if bb is None:
            return False
        cx0, cy0, cx1, cy1 = crop_mm
        return not (bb[2] < cx0 or bb[0] > cx1 or bb[3] < cy0 or bb[1] > cy1)

    lvl = model.get_level(level)
    walls = [
        (el, wp)
        for el in model.query(category="wall", level=lvl.name)
        if (wp := _wall_endpoints(el)) is not None and _in_crop(el)
    ]
    # Corner joins: extend wall bands so L/T meetings don't leave gaps
    _w_ext = _wall_join_extensions_plan(walls)
    walls_draw: list[tuple[Element, tuple[float, float, float, float, float]]] = []
    for el, (x0, y0, x1, y1, t) in walls:
        ex0, ex1 = _w_ext.get(el.id, (0.0, 0.0))
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        if L > 1e-3 and (ex0 > 0 or ex1 > 0):
            ux, uy = dx / L, dy / L
            x0e, y0e = x0 - ux * ex0, y0 - uy * ex0
            x1e, y1e = x1 + ux * ex1, y1 + uy * ex1
            walls_draw.append((el, (x0e, y0e, x1e, y1e, t)))
        else:
            walls_draw.append((el, (x0, y0, x1, y1, t)))
    doors = model.query(category="door", level=lvl.name)
    windows = model.query(category="window", level=lvl.name)
    rooms = [el for el in model.query(category="room", level=lvl.name) if _in_crop(el)]
    equipment = [
        el for el in model.query(category="equipment", level=lvl.name) if _in_crop(el)
    ]
    slabs = (
        [el for el in model.query(category="slab", level=lvl.name) if _in_crop(el)]
        if include is not None and "slabs" in include
        else []
    )
    columns = [
        el
        for el in model.elements
        if el.level_id == lvl.id
        and (el.category == "column" or el.params.get("fitting_type") == "column")
        and _in_crop(el)
    ]
    notes = [el for el in model.query(category="note", level=lvl.name) if _in_crop(el)]
    # MEP + catalog proxies on this level
    mep_els = [
        el
        for el in model.elements
        if el.level_id == lvl.id
        and _in_crop(el)
        and el.category
        in {
            "pipe",
            "plumbing_pipe",
            "fitting",
            "fittings",
            "fixture",
            "accessory",
            "module_instance",
            "module_root",
            "duct",
            "hvac",
            "conduit",
            "cable_tray",
            "beam",
        }
    ]

    xs: list[float] = []
    ys: list[float] = []
    for _el, (x0, y0, x1, y1, t) in walls_draw:
        for px, py in _wall_band(x0, y0, x1, y1, t) or [(x0, y0), (x1, y1)]:
            xs.append(px)
            ys.append(py)
    for room in rooms:
        for pt in room.params.get("boundary_mm", []):
            xs.append(float(pt[0]))
            ys.append(float(pt[1]))
    for eq in equipment:
        for pt in eq.params.get("polygon_mm", []):
            xs.append(float(pt[0]))
            ys.append(float(pt[1]))
        # cylinders: include radius circle
        if eq.params.get("shape") == "cylinder":
            try:
                o = eq.params["origin_mm"]
                s = eq.params["size_mm"]
                # size L along axis, D, D for cylinder along X stored as Lx,D,D
                r = max(float(s[1]), float(s[2])) / 2
                xs += [float(o[0]) - r, float(o[0]) + float(s[0]) + r]
                ys += [float(o[1]) - r, float(o[1]) + r]
            except (KeyError, TypeError, ValueError, IndexError):
                pass
    for el in mep_els:
        if el.params.get("start_mm") and el.params.get("end_mm"):
            s, e = el.params["start_mm"], el.params["end_mm"]
            xs += [float(s[0]), float(e[0])]
            ys += [float(s[1]), float(e[1])]
        elif el.params.get("origin_mm"):
            o = el.params["origin_mm"]
            xs.append(float(o[0]))
            ys.append(float(o[1]))
            if el.params.get("size_mm"):
                sz = el.params["size_mm"]
                xs.append(float(o[0]) + float(sz[0]))
                ys.append(float(o[1]) + float(sz[1] if len(sz) > 1 else 100))
        for pt in el.params.get("polygon_mm") or []:
            xs.append(float(pt[0]))
            ys.append(float(pt[1]))
    for slab in slabs:
        for pt in slab.params.get("polygon_mm") or []:
            xs.append(float(pt[0]))
            ys.append(float(pt[1]))

    if crop_mm is not None:
        min_x, min_y, max_x, max_y = (float(v) for v in crop_mm)
    elif xs and ys:
        min_x, max_x = min(xs) - margin_mm, max(xs) + margin_mm
        min_y, max_y = min(ys) - margin_mm, max(ys) + margin_mm
    else:
        min_x, min_y, max_x, max_y = 0.0, 0.0, 1000.0, 1000.0

    width = (max_x - min_x) * scale
    height = (max_y - min_y) * scale

    def project(x: float, y: float) -> tuple[float, float]:
        return (x - min_x) * scale, (max_y - y) * scale

    label = title if title is not None else f"{model.name} — Plan {lvl.name}"
    sw = max(0.5, 15 * scale)
    parts: list[str] = [
        f'  <title>{esc(label)}</title>',
        f'  <rect x="0" y="0" width="{fmt(width)}" height="{fmt(height)}" fill="#ffffff"/>',
    ]
    wall_by_id = {el.id: el for el, _ in walls}
    if ghost_walls:
        # context-only walls: light grey outline, no fill, no annotations
        parts.append(
            f'  <g class="walls walls-ghost" fill="none" stroke="#c9c9c9" '
            f'stroke-width="{fmt(sw)}" stroke-linejoin="round">'
        )
        for _el, (x0, y0, x1, y1, t) in walls_draw:
            band = _wall_band(x0, y0, x1, y1, t)
            if not band:
                continue
            pts = " ".join(f"{fmt(px)},{fmt(py)}" for px, py in (project(x, y) for x, y in band))
            parts.append(f'    <polygon points="{pts}"/>')
        parts.append("  </g>")
    elif _on("walls"):
        if wall_fill_by_type is not None:
            # diagonal-hatch pattern for wall types not in the color map
            parts.append(
                '  <defs><pattern id="llmbim-wall-hatch" width="7" height="7" '
                'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                '<rect width="7" height="7" fill="#f7f7f7"/>'
                '<line x1="0" y1="0" x2="0" y2="7" stroke="#777" stroke-width="1.6"/>'
                "</pattern></defs>"
            )
        parts.append(
            f'  <g class="walls" fill="#c8c8c8" stroke="#1a1a1a" stroke-width="{fmt(sw)}" '
            f'stroke-linejoin="round">'
        )
        layer_fills = {
            "structure": "#b0b0b0",
            "insulation": "#f0e68c",
            "finish": "#e8e8e8",
            "membrane": "#4a5568",
        }
        for el, (x0, y0, x1, y1, t) in walls_draw:
            if wall_fill_by_type is not None:
                band = _wall_band(x0, y0, x1, y1, t)
                if not band:
                    continue
                tid = str(el.type_id or el.params.get("type_id") or "")
                fill = wall_fill_by_type.get(tid, "url(#llmbim-wall-hatch)")
                pts = " ".join(
                    f"{fmt(px)},{fmt(py)}" for px, py in (project(x, y) for x, y in band)
                )
                parts.append(f'    <polygon points="{pts}" fill="{fill}"/>')
                continue
            layers = el.params.get("wall_layers")
            if not layers and el.type_id:
                try:
                    from llmbim_core.types_catalog import DEFAULT_WALL_TYPES

                    wt = DEFAULT_WALL_TYPES.get(el.type_id)
                    if wt and wt.layers:
                        layers = [L.model_dump() for L in wt.layers]
                except Exception:  # noqa: BLE001
                    layers = None
            if layers and len(layers) >= 2:
                total = sum(float(L.get("thickness_mm") or 0) for L in layers) or t
                dx, dy = x1 - x0, y1 - y0
                length = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / length, dx / length
                cursor = -total / 2.0
                for L in layers:
                    lt = float(L.get("thickness_mm") or 0)
                    if lt < 1:
                        continue
                    mid = cursor + lt / 2.0
                    ox, oy = nx * mid, ny * mid
                    band = _wall_band(x0 + ox, y0 + oy, x1 + ox, y1 + oy, lt)
                    if not band:
                        continue
                    fill = layer_fills.get(str(L.get("function") or "structure"), "#c8c8c8")
                    pts = " ".join(
                        f"{fmt(px)},{fmt(py)}" for px, py in (project(x, y) for x, y in band)
                    )
                    parts.append(f'    <polygon points="{pts}" fill="{fill}"/>')
                    cursor += lt
            else:
                band = _wall_band(x0, y0, x1, y1, t)
                if not band:
                    continue
                pts = " ".join(
                    f"{fmt(px)},{fmt(py)}" for px, py in (project(x, y) for x, y in band)
                )
                parts.append(f'    <polygon points="{pts}"/>')
        parts.append("  </g>")

    if _on("walls") and not ghost_walls:
        parts.append(
            f'  <g class="centerlines" stroke="#8a1a1a" stroke-width="{fmt(max(0.3, 8 * scale))}" '
            f'stroke-dasharray="{fmt(60 * scale)} {fmt(40 * scale)}" fill="none">'
        )
        for _el, (x0, y0, x1, y1, _t) in walls_draw:
            px0, py0 = project(x0, y0)
            px1, py1 = project(x1, y1)
            parts.append(
                f'    <line x1="{fmt(px0)}" y1="{fmt(py0)}" x2="{fmt(px1)}" y2="{fmt(py1)}"/>'
            )
        parts.append("  </g>")

        # Wall type marks (type_id) + optional fire_rating at midspan
        parts.append(
            '  <g class="wall-types" fill="#333" font-family="sans-serif" '
            f'font-size="{fmt(max(6, 9))}">'
        )
        for el, (x0, y0, x1, y1, _t) in walls:
            tid = el.type_id or el.params.get("type_id") or ""
            fr = el.params.get("fire_rating") or ""
            if not tid and not fr:
                continue
            # short mark e.g. W-EXT-CMU → EXT or last token
            short = str(tid) if tid else ""
            if short.startswith("W-") and len(short) > 4:
                short = short[2:]  # drop W-
            if len(short) > 12:
                short = short[:12]
            if fr:
                fr_s = str(fr).replace(" min", "m").replace("-hr", "HR").replace(" hr", "HR")
                if len(fr_s) > 8:
                    fr_s = fr_s[:8]
                short = f"{short} {fr_s}".strip() if short else fr_s
            mx, my = project((x0 + x1) / 2, (y0 + y1) / 2)
            parts.append(
                f'    <text class="wall-type" x="{fmt(mx)}" y="{fmt(my - 4)}" text-anchor="middle" '
                f'fill="#1a1a1a">{esc(short)}</text>'
            )
        parts.append("  </g>")

    parts.append(
        f'  <g class="openings" stroke="#0066aa" stroke-width="{fmt(max(0.4, 10 * scale))}">'
    )
    door_num = 0
    win_num = 0
    openings_src = (list(doors) + list(windows)) if _on("openings") else []
    for opening in openings_src:
        host = wall_by_id.get(opening.host_id or "")
        if not host:
            continue
        ep = _wall_endpoints(host)
        if not ep:
            continue
        x0, y0, x1, y1, _t = ep
        off = float(opening.params.get("offset_mm", 0))
        width_o = float(opening.params.get("width_mm", 900))
        try:
            a = point_along_segment((x0, y0), (x1, y1), off)
            b = point_along_segment((x0, y0), (x1, y1), off + width_o)
            mid = point_along_segment((x0, y0), (x1, y1), off + width_o / 2)
        except Exception:
            continue
        pa, pb = project(*a), project(*b)
        pm = project(*mid)
        color = "#228822" if opening.category == "door" else "#0066aa"
        parts.append(
            f'    <line x1="{fmt(pa[0])}" y1="{fmt(pa[1])}" '
            f'x2="{fmt(pb[0])}" y2="{fmt(pb[1])}" stroke="{color}"/>'
        )
        # door / window tags: mark (D1/W1) + type_id short mark when present
        def _opening_type_short(el) -> str:
            tid = str(el.type_id or el.params.get("type_id") or "")
            if not tid:
                return ""
            # D-HM-36 → HM-36; keep WIN-VIEW… readable
            if tid.startswith("D-"):
                return tid[2:][:14]
            if tid.startswith("W-") and not tid.startswith("WIN"):
                return tid[2:][:14]
            return tid[:14]

        if opening.category == "door":
            door_num += 1
            tag = f"D{door_num}"
            tshort = _opening_type_short(opening)
            fr = opening.params.get("fire_rating") or ""
            if fr:
                fr_s = str(fr).replace(" min", "m").replace("-hr", "HR").replace(" hr", "HR")
                tshort = f"{tshort} {fr_s}".strip() if tshort else fr_s
            r = max(6.0, 80 * scale)
            parts.append(
                f'    <circle cx="{fmt(pm[0])}" cy="{fmt(pm[1])}" r="{fmt(r)}" '
                f'fill="#e8ffe8" stroke="#228822" stroke-width="1"/>'
            )
            parts.append(
                f'    <text x="{fmt(pm[0])}" y="{fmt(pm[1] + r * 0.35)}" text-anchor="middle" '
                f'font-size="{fmt(max(7, r))}" fill="#145214" font-family="sans-serif">{tag}</text>'
            )
            if tshort:
                parts.append(
                    f'    <text class="opening-type" x="{fmt(pm[0])}" y="{fmt(pm[1] + r * 1.55)}" '
                    f'text-anchor="middle" font-size="{fmt(max(5, r * 0.65))}" '
                    f'fill="#145214" font-family="sans-serif">{esc(tshort[:18])}</text>'
                )
        else:
            win_num += 1
            tag = f"W{win_num}"
            tshort = _opening_type_short(opening)
            r = max(5.0, 70 * scale)
            parts.append(
                f'    <rect x="{fmt(pm[0] - r)}" y="{fmt(pm[1] - r * 0.6)}" '
                f'width="{fmt(2 * r)}" height="{fmt(1.2 * r)}" fill="#e8f0ff" stroke="#0066aa"/>'
            )
            parts.append(
                f'    <text x="{fmt(pm[0])}" y="{fmt(pm[1] + r * 0.25)}" text-anchor="middle" '
                f'font-size="{fmt(max(6, r * 0.9))}" fill="#003366" font-family="sans-serif">{tag}</text>'
            )
            if tshort:
                parts.append(
                    f'    <text class="opening-type" x="{fmt(pm[0])}" y="{fmt(pm[1] + r * 1.4)}" '
                    f'text-anchor="middle" font-size="{fmt(max(5, r * 0.65))}" '
                    f'fill="#003366" font-family="sans-serif">{esc(tshort)}</text>'
                )
    parts.append("  </g>")

    # Slab outlines (opt-in via include={"slabs"} — site / underground plans)
    if slabs:
        parts.append(
            f'  <g class="slabs" fill="none" stroke="#8d6e63" '
            f'stroke-width="{fmt(max(0.8, 12 * scale))}" '
            f'stroke-dasharray="{fmt(max(3, 80 * scale))} {fmt(max(2, 40 * scale))}">'
        )
        for slab in slabs:
            poly = slab.params.get("polygon_mm") or []
            if len(poly) < 3:
                continue
            pts = " ".join(
                f"{fmt(px)},{fmt(py)}"
                for px, py in (project(float(p[0]), float(p[1])) for p in poly)
            )
            parts.append(f'    <polygon points="{pts}"/>')
        parts.append("  </g>")

    # Equipment
    parts.append(
        f'  <g class="equipment" fill="#cfe8ff" fill-opacity="0.55" '
        f'stroke="#0b5cab" stroke-width="{fmt(max(0.4, 8 * scale))}">'
    )
    for eq in equipment:
        if not _eq_on(eq):
            continue
        if eq.params.get("shape") == "cylinder":
            try:
                o = eq.params["origin_mm"]
                s = eq.params["size_mm"]
                # along X: length s[0], diameter s[1]
                x0, y0 = float(o[0]), float(o[1])
                L, D = float(s[0]), float(s[1])
                # rectangle envelope + centerline
                r = D / 2
                poly = [(x0, y0 - r), (x0 + L, y0 - r), (x0 + L, y0 + r), (x0, y0 + r)]
                pts = " ".join(
                    f"{fmt(px)},{fmt(py)}"
                    for px, py in (project(float(p[0]), float(p[1])) for p in poly)
                )
                parts.append(f'    <polygon points="{pts}" fill="#b8d4f0"/>')
                # end circles
                for cx in (x0, x0 + L):
                    pcx, pcy = project(cx, y0)
                    parts.append(
                        f'    <circle cx="{fmt(pcx)}" cy="{fmt(pcy)}" r="{fmt(r * scale)}" '
                        f'fill="none" stroke="#0b5cab"/>'
                    )
            except (KeyError, TypeError, ValueError, IndexError):
                pass
            continue
        poly = eq.params.get("polygon_mm") or []
        if len(poly) < 3:
            continue
        pts = " ".join(
            f"{fmt(px)},{fmt(py)}" for px, py in (project(float(p[0]), float(p[1])) for p in poly)
        )
        parts.append(f'    <polygon points="{pts}"/>')
    parts.append("  </g>")

    # Structural columns as plan crosses / squares
    if _on("columns"):
        parts.append(
            f'  <g class="columns" fill="none" stroke="#37474f" '
            f'stroke-width="{fmt(max(0.6, 10 * scale))}">'
        )
    for col in columns if _on("columns") else []:
        try:
            o = col.params.get("origin_mm")
            if not o:
                continue
            ox, oy = float(o[0]), float(o[1])
            sz = col.params.get("size_mm") or [250, 250, 3000]
            dims = col.params.get("section_dims_mm") or {}
            d = float(dims.get("d_mm") or sz[0])
            bf = float(dims.get("bf_mm") or (sz[1] if len(sz) > 1 else sz[0]))
            tw = float(dims.get("tw_mm") or max(d * 0.03, 6))
            tf = float(dims.get("tf_mm") or max(d * 0.05, 8))
            half_d, half_bf = d / 2, bf / 2
            sec = str(col.params.get("section") or col.name or "COL")
            # W-section I footprint when available
            if sec.upper().replace("×", "x").startswith("W") or col.params.get("shape") == "w_section":
                # bottom flange, web, top flange as plan polys (depth = Y, flange = X)
                bands = [
                    # bottom flange
                    [
                        (ox - half_bf, oy - half_d),
                        (ox + half_bf, oy - half_d),
                        (ox + half_bf, oy - half_d + tf),
                        (ox - half_bf, oy - half_d + tf),
                    ],
                    # top flange
                    [
                        (ox - half_bf, oy + half_d - tf),
                        (ox + half_bf, oy + half_d - tf),
                        (ox + half_bf, oy + half_d),
                        (ox - half_bf, oy + half_d),
                    ],
                    # web
                    [
                        (ox - tw / 2, oy - half_d + tf),
                        (ox + tw / 2, oy - half_d + tf),
                        (ox + tw / 2, oy + half_d - tf),
                        (ox - tw / 2, oy + half_d - tf),
                    ],
                ]
                for corners in bands:
                    pts = " ".join(
                        f"{fmt(px)},{fmt(py)}"
                        for px, py in (project(float(p[0]), float(p[1])) for p in corners)
                    )
                    parts.append(f'    <polygon points="{pts}" fill="#cfd8dc"/>')
            else:
                half_x = float(sz[0]) / 2
                half_y = float(sz[1]) / 2 if len(sz) > 1 else half_x
                corners = [
                    (ox - half_x, oy - half_y),
                    (ox + half_x, oy - half_y),
                    (ox + half_x, oy + half_y),
                    (ox - half_x, oy + half_y),
                ]
                pts = " ".join(
                    f"{fmt(px)},{fmt(py)}"
                    for px, py in (project(float(p[0]), float(p[1])) for p in corners)
                )
                parts.append(f'    <polygon points="{pts}" fill="#eceff1"/>')
                a = project(ox - half_x * 0.6, oy - half_y * 0.6)
                b = project(ox + half_x * 0.6, oy + half_y * 0.6)
                c = project(ox - half_x * 0.6, oy + half_y * 0.6)
                dpt = project(ox + half_x * 0.6, oy - half_y * 0.6)
                parts.append(
                    f'    <line x1="{fmt(a[0])}" y1="{fmt(a[1])}" x2="{fmt(b[0])}" y2="{fmt(b[1])}"/>'
                )
                parts.append(
                    f'    <line x1="{fmt(c[0])}" y1="{fmt(c[1])}" x2="{fmt(dpt[0])}" y2="{fmt(dpt[1])}"/>'
                )
            mx, my = project(ox, oy - half_d - 80)
            parts.append(
                f'    <text x="{fmt(mx)}" y="{fmt(my)}" text-anchor="middle" '
                f'font-size="{fmt(max(6, 9))}" fill="#263238" font-family="sans-serif">'
                f"{esc(str(sec)[:16])}</text>"
            )
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    if _on("columns"):
        parts.append("  </g>")

    # Structural beams as centerlines
    if _on("beams"):
        parts.append(
            f'  <g class="beams" stroke="#546e7a" stroke-width="{fmt(max(1.0, 18 * scale))}" '
            f'fill="none" stroke-linecap="butt">'
        )
    for el in mep_els:
        if el.category != "beam" and el.params.get("fitting_type") != "beam":
            continue
        if not _on("beams"):
            continue
        try:
            s, e = el.params["start_mm"], el.params["end_mm"]
            a = project(float(s[0]), float(s[1]))
            b = project(float(e[0]), float(e[1]))
            parts.append(
                f'    <line x1="{fmt(a[0])}" y1="{fmt(a[1])}" '
                f'x2="{fmt(b[0])}" y2="{fmt(b[1])}" stroke="#546e7a"/>'
            )
            mx, my = project(
                (float(s[0]) + float(e[0])) / 2,
                (float(s[1]) + float(e[1])) / 2,
            )
            sec = el.params.get("section") or "BM"
            parts.append(
                f'    <text x="{fmt(mx)}" y="{fmt(my - 4)}" text-anchor="middle" '
                f'font-size="{fmt(max(6, 9))}" fill="#37474f" font-family="sans-serif">'
                f"{esc(str(sec)[:16])}</text>"
            )
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    if _on("beams"):
        parts.append("  </g>")

    # MEP: pipes (lines) + fittings/fixtures (markers)
    pipe_sw = max(1.2, 25 * scale)
    pipes_group = include is None or bool({"pipes", "conduit"} & include)
    if pipes_group:
        parts.append(
            f'  <g class="pipes" stroke="#c45c26" stroke-width="{fmt(pipe_sw)}" '
            f'fill="none" stroke-linecap="round">'
        )
    for el in mep_els:
        is_conduit = el.category == "conduit" or el.params.get("fitting_type") == "conduit"
        if (
            el.category not in {"pipe", "plumbing_pipe", "conduit"}
            and el.params.get("fitting_type") not in {"pipe", "conduit"}
        ):
            continue
        if not _mep_on(el):
            continue
        try:
            mid = str(el.params.get("material_id") or "")
            stroke = "#c45c26"
            if is_conduit:
                stroke = "#6a1b9a"
            if "black" in mid or el.params.get("system") in ("FP", "fire"):
                stroke = "#333333"
            if "ss316" in mid or el.params.get("system") in ("PROC", "process"):
                stroke = "#6b7c8a"
            if "pvc" in mid:
                stroke = "#e6d84a"
            nps = el.params.get("nps")
            # vertical riser: plan symbol = concentric circles
            if el.params.get("vertical") or el.params.get("orientation") == "vertical":
                o = el.params.get("origin_mm") or el.params.get("start_mm")
                if not o:
                    continue
                px, py = project(float(o[0]), float(o[1]))
                r = max(3.0, 40 * scale)
                parts.append(
                    f'    <circle cx="{fmt(px)}" cy="{fmt(py)}" r="{fmt(r)}" '
                    f'stroke="{stroke}" fill="none"/>'
                )
                parts.append(
                    f'    <circle cx="{fmt(px)}" cy="{fmt(py)}" r="{fmt(r * 0.4)}" '
                    f'stroke="{stroke}" fill="{stroke}"/>'
                )
                tag = f'R{nps}"' if nps else "R"
                parts.append(
                    f'    <text x="{fmt(px + r * 1.5)}" y="{fmt(py)}" '
                    f'font-size="{fmt(max(6, 9))}" fill="{stroke}" font-family="sans-serif">'
                    f"{esc(tag)}</text>"
                )
                continue
            if "start_mm" in el.params and "end_mm" in el.params:
                s, e = el.params["start_mm"], el.params["end_mm"]
                x0, y0 = float(s[0]), float(s[1])
                x1, y1 = float(e[0]), float(e[1])
            else:
                continue
            if abs(x1 - x0) < 1 and abs(y1 - y0) < 1:
                continue  # pure riser without vertical flag
            pa, pb = project(x0, y0), project(x1, y1)
            parts.append(
                f'    <line x1="{fmt(pa[0])}" y1="{fmt(pa[1])}" '
                f'x2="{fmt(pb[0])}" y2="{fmt(pb[1])}" stroke="{stroke}"/>'
            )
            if nps:
                mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
                parts.append(
                    f'    <text x="{fmt(mx)}" y="{fmt(my - 3)}" text-anchor="middle" '
                    f'font-size="{fmt(max(6, 9))}" fill="{stroke}" font-family="sans-serif">'
                    f"{esc(str(nps))}\"</text>"
                )
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    if pipes_group:
        parts.append("  </g>")

    # HVAC ducts as parallel plan lines (width)
    if _on("ducts"):
        parts.append(
            f'  <g class="ducts" stroke="#2e7d32" stroke-width="{fmt(max(0.8, 12 * scale))}" '
            f'fill="none" stroke-linecap="butt">'
        )
    for el in mep_els:
        if el.category not in {"duct", "hvac"} and el.params.get("fitting_type") != "duct":
            continue
        if not _on("ducts"):
            continue
        try:
            s, e = el.params["start_mm"], el.params["end_mm"]
            x0, y0 = float(s[0]), float(s[1])
            x1, y1 = float(e[0]), float(e[1])
            w = float(el.params.get("width_mm") or 400)
            length = math.hypot(x1 - x0, y1 - y0)
            if length < 1:
                continue
            nx, ny = -(y1 - y0) / length, (x1 - x0) / length
            half = w / 2
            # two parallel edges
            for sign in (-1, 1):
                a = project(x0 + sign * half * nx, y0 + sign * half * ny)
                b = project(x1 + sign * half * nx, y1 + sign * half * ny)
                parts.append(
                    f'    <line x1="{fmt(a[0])}" y1="{fmt(a[1])}" '
                    f'x2="{fmt(b[0])}" y2="{fmt(b[1])}" stroke="#2e7d32"/>'
                )
            # end caps
            for pt in ((x0, y0), (x1, y1)):
                a = project(pt[0] - half * nx, pt[1] - half * ny)
                b = project(pt[0] + half * nx, pt[1] + half * ny)
                parts.append(
                    f'    <line x1="{fmt(a[0])}" y1="{fmt(a[1])}" '
                    f'x2="{fmt(b[0])}" y2="{fmt(b[1])}" stroke="#2e7d32"/>'
                )
            mx, my = project((x0 + x1) / 2, (y0 + y1) / 2)
            label = f"{w:.0f}x{float(el.params.get('height_mm') or 0):.0f}"
            parts.append(
                f'    <text x="{fmt(mx)}" y="{fmt(my - 4)}" text-anchor="middle" '
                f'font-size="{fmt(max(6, 9))}" fill="#1b5e20" font-family="sans-serif">'
                f"{esc(label)}</text>"
            )
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    if _on("ducts"):
        parts.append("  </g>")

    # Cable trays as dashed parallel plan lines
    if _on("cable_tray"):
        parts.append(
            f'  <g class="cable-trays" stroke="#6a1b9a" stroke-width="{fmt(max(0.8, 10 * scale))}" '
            f'fill="none" stroke-dasharray="{fmt(max(2, 40 * scale))},{fmt(max(1, 20 * scale))}">'
        )
    for el in mep_els:
        if el.category != "cable_tray" and el.params.get("fitting_type") != "cable_tray":
            continue
        if not _on("cable_tray"):
            continue
        try:
            s, e = el.params["start_mm"], el.params["end_mm"]
            x0, y0 = float(s[0]), float(s[1])
            x1, y1 = float(e[0]), float(e[1])
            w = float(el.params.get("width_mm") or 300)
            length = math.hypot(x1 - x0, y1 - y0)
            if length < 1:
                continue
            nx, ny = -(y1 - y0) / length, (x1 - x0) / length
            half = w / 2
            for sign in (-1, 1):
                a = project(x0 + sign * half * nx, y0 + sign * half * ny)
                b = project(x1 + sign * half * nx, y1 + sign * half * ny)
                parts.append(
                    f'    <line x1="{fmt(a[0])}" y1="{fmt(a[1])}" '
                    f'x2="{fmt(b[0])}" y2="{fmt(b[1])}" stroke="#6a1b9a"/>'
                )
            mx, my = project((x0 + x1) / 2, (y0 + y1) / 2)
            label = f"CT {w:.0f}"
            parts.append(
                f'    <text x="{fmt(mx)}" y="{fmt(my - 4)}" text-anchor="middle" '
                f'font-size="{fmt(max(6, 9))}" fill="#4a148c" font-family="sans-serif">'
                f"{esc(label)}</text>"
            )
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    if _on("cable_tray"):
        parts.append("  </g>")

    fittings_group = include is None or bool({"pipes", "ducts"} & include)
    if fittings_group:
        parts.append(
            f'  <g class="fittings" fill="#fff3e0" stroke="#c45c26" '
            f'stroke-width="{fmt(max(0.5, 8 * scale))}">'
        )
    for el in mep_els:
        ftype0 = str(el.params.get("fitting_type") or "")
        # linear runs drawn elsewhere; keep point-placed HVAC devices (VAV, dampers)
        if el.category in {"pipe", "plumbing_pipe", "conduit", "cable_tray"}:
            continue
        if not _mep_on(el):
            continue
        if el.category in {"duct"} or ftype0 in {"pipe", "duct", "flex_duct", "cable_tray"}:
            continue
        if el.category == "hvac" and ftype0 in {"duct", "flex_duct", ""}:
            # bare linear duct category without device type
            if el.params.get("start_mm") and el.params.get("end_mm"):
                continue
        try:
            o = el.params.get("origin_mm")
            if not o:
                continue
            ox, oy = float(o[0]), float(o[1])
            px, py = project(ox, oy)
            ftype = ftype0 or str(el.category)
            nps = el.params.get("nps") or ""
            mid = str(el.params.get("material_id") or "")
            stroke = "#c45c26"
            if "black" in mid or "fire" in str(el.params.get("system", "")):
                stroke = "#222"
            if el.category in {"fixture", "accessory"}:
                stroke = "#5c4d7a"
                fill = "#ede7f6"
            else:
                fill = "#fff3e0"
            r = max(4.0, 55 * scale)
            if ftype in ("elbow_90", "elbow_45"):
                # L-shaped tick
                parts.append(
                    f'    <circle cx="{fmt(px)}" cy="{fmt(py)}" r="{fmt(r)}" '
                    f'fill="{fill}" stroke="{stroke}"/>'
                )
                parts.append(
                    f'    <text x="{fmt(px)}" y="{fmt(py + r * 0.35)}" text-anchor="middle" '
                    f'font-size="{fmt(max(5, r * 0.9))}" fill="{stroke}" font-family="sans-serif">'
                    f"{'90' if '90' in ftype else '45'}</text>"
                )
            elif ftype == "tee":
                parts.append(
                    f'    <rect x="{fmt(px - r)}" y="{fmt(py - r)}" width="{fmt(2 * r)}" '
                    f'height="{fmt(2 * r)}" fill="{fill}" stroke="{stroke}"/>'
                )
                parts.append(
                    f'    <text x="{fmt(px)}" y="{fmt(py + r * 0.35)}" text-anchor="middle" '
                    f'font-size="{fmt(max(5, r * 0.85))}" fill="{stroke}" font-family="sans-serif">T</text>'
                )
            elif el.category in {"fixture", "accessory"} or ftype in (
                "toilet",
                "lavatory",
                "tp_dispenser",
                "urinal",
            ):
                parts.append(
                    f'    <rect x="{fmt(px - r * 1.2)}" y="{fmt(py - r)}" width="{fmt(2.4 * r)}" '
                    f'height="{fmt(2 * r)}" fill="{fill}" stroke="{stroke}" rx="2"/>'
                )
                tag = (el.name or ftype)[:6]
                parts.append(
                    f'    <text x="{fmt(px)}" y="{fmt(py + r * 0.3)}" text-anchor="middle" '
                    f'font-size="{fmt(max(5, r * 0.7))}" fill="{stroke}" font-family="sans-serif">'
                    f"{esc(tag)}</text>"
                )
            elif ftype in ("vav", "fire_damper", "smoke_damper", "diffuser", "grille") or el.category == "hvac":
                # HVAC terminal / damper / VAV
                stroke = "#1b5e20"
                fill = "#e8f5e9"
                if "damper" in ftype or "fire" in ftype:
                    stroke = "#b71c1c"
                    fill = "#ffebee"
                rw = r * 1.6
                rh = r * 1.1
                parts.append(
                    f'    <rect x="{fmt(px - rw)}" y="{fmt(py - rh)}" width="{fmt(2 * rw)}" '
                    f'height="{fmt(2 * rh)}" fill="{fill}" stroke="{stroke}" class="hvac-device"/>'
                )
                tag = {
                    "vav": "VAV",
                    "fire_damper": "FD",
                    "smoke_damper": "SD",
                    "diffuser": "CD",
                    "grille": "RG",
                }.get(ftype, (ftype or "HVAC")[:4].upper())
                parts.append(
                    f'    <text x="{fmt(px)}" y="{fmt(py + r * 0.35)}" text-anchor="middle" '
                    f'font-size="{fmt(max(5, r * 0.75))}" fill="{stroke}" font-family="sans-serif">'
                    f"{esc(tag)}</text>"
                )
            else:
                parts.append(
                    f'    <circle cx="{fmt(px)}" cy="{fmt(py)}" r="{fmt(r * 0.8)}" '
                    f'fill="{fill}" stroke="{stroke}"/>'
                )
            if nps and ftype not in ("toilet", "lavatory"):
                parts.append(
                    f'    <text x="{fmt(px + r * 1.4)}" y="{fmt(py)}" '
                    f'font-size="{fmt(max(5, 8))}" fill="{stroke}" font-family="sans-serif">'
                    f"{esc(str(nps))}\"</text>"
                )
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    if fittings_group:
        parts.append("  </g>")

    font = max(8.0, min(28.0, 350 * scale))
    parts.append(
        f'  <g class="labels" fill="#333" font-size="{fmt(font)}" '
        f'font-family="sans-serif" text-anchor="middle">'
    )
    for room in rooms if (_on("rooms") and not room_tags) else []:
        boundary = room.params.get("boundary_mm") or []
        if len(boundary) < 3:
            continue
        cx = sum(float(p[0]) for p in boundary) / len(boundary)
        cy = sum(float(p[1]) for p in boundary) / len(boundary)
        px, py = project(cx, cy)
        name = room.name or "Room"
        area_mm2 = room.params.get("area_mm2")
        if area_mm2 is None and len(boundary) >= 3:
            # shoelace fallback
            a = 0.0
            n = len(boundary)
            for i in range(n):
                x1, y1 = float(boundary[i][0]), float(boundary[i][1])
                x2, y2 = float(boundary[(i + 1) % n][0]), float(boundary[(i + 1) % n][1])
                a += x1 * y2 - x2 * y1
            area_mm2 = abs(a) / 2.0
        area_txt = ""
        if area_mm2 is not None and float(area_mm2) > 0:
            area_txt = f" {float(area_mm2) / 1e6:.1f}m²"
        h_mm = room.params.get("height_mm") or room.params.get("ceiling_height_mm")
        h_txt = f" H{float(h_mm):.0f}" if h_mm else ""
        label = f"{name}{area_txt}{h_txt}"
        parts.append(
            f'    <text class="room-label" x="{fmt(px)}" y="{fmt(py)}">{esc(label)}</text>'
        )
    for eq in equipment:
        if not _eq_on(eq):
            continue
        poly = eq.params.get("polygon_mm") or []
        if not eq.name:
            continue
        if poly:
            cx = sum(float(p[0]) for p in poly) / len(poly)
            cy = sum(float(p[1]) for p in poly) / len(poly)
        else:
            continue
        px, py = project(cx, cy)
        parts.append(
            f'    <text x="{fmt(px)}" y="{fmt(py)}" fill="#0b5cab" font-size="{fmt(font * 0.75)}">'
            f"{esc(eq.name)}</text>"
        )
    parts.append("  </g>")

    # Boxed room tags: NAME / area m² centered in the boundary
    if room_tags and _on("rooms"):
        tag_font = max(8.0, min(14.0, 300 * scale))
        parts.append(
            f'  <g class="room-tags" font-family="sans-serif" font-size="{fmt(tag_font)}" '
            f'text-anchor="middle">'
        )
        for room in rooms:
            ca = _room_centroid_area(room)
            if ca is None:
                continue
            cx, cy, area_mm2 = ca
            px, py = project(cx, cy)
            name = (room.name or "ROOM").upper()
            area_txt = f"{area_mm2 / 1e6:.1f} m²"
            box_w = max(len(name), len(area_txt)) * tag_font * 0.62 + 14
            box_h = 2 * tag_font + 12
            parts.append(
                f'    <rect x="{fmt(px - box_w / 2)}" y="{fmt(py - box_h / 2)}" '
                f'width="{fmt(box_w)}" height="{fmt(box_h)}" fill="#ffffff" '
                f'fill-opacity="0.85" stroke="#1a1a1a" stroke-width="1"/>'
            )
            parts.append(
                f'    <line x1="{fmt(px - box_w / 2)}" y1="{fmt(py)}" '
                f'x2="{fmt(px + box_w / 2)}" y2="{fmt(py)}" stroke="#1a1a1a" '
                f'stroke-width="0.5"/>'
            )
            parts.append(
                f'    <text x="{fmt(px)}" y="{fmt(py - 4)}" font-weight="bold">'
                f"{esc(name)}</text>"
            )
            parts.append(
                f'    <text x="{fmt(px)}" y="{fmt(py + tag_font + 2)}">'
                f"{esc(area_txt)}</text>"
            )
        parts.append("  </g>")

    if show_dimensions:
        parts.append('  <g class="dimensions">')
        dim_budget = max_dimensions
        # grid dim chains carry the wall/overall dims — skip the per-wall
        # midspan dims then (they collide with section markers and chains)
        _has_grid_chains = grid_dims and _on("grids") and bool(model.grids)
        if walls and _on("walls") and not ghost_walls and not _has_grid_chains:
            ranked = sorted(
                walls,
                key=lambda t: math.hypot(t[1][2] - t[1][0], t[1][3] - t[1][1]),
                reverse=True,
            )
            wall_budget = max(1, dim_budget * 2 // 3)
            for _el, (x0, y0, x1, y1, _t) in ranked[:wall_budget]:
                length = math.hypot(x1 - x0, y1 - y0)
                if length < 500:
                    continue
                if length >= 1000:
                    lab = f"{length / 1000:.2f} m"
                else:
                    lab = f"{length:.0f} mm"
                parts.extend(_dim_line(x0, y0, x1, y1, project, scale, lab))
                dim_budget -= 1
                if dim_budget <= 0:
                    break
        # MEP run lengths (pipe / duct / conduit) — longest first
        mep_runs: list[tuple[float, float, float, float, float, str]] = []
        for el in mep_els:
            if not _mep_on(el):
                continue
            if el.params.get("vertical") or el.params.get("orientation") == "vertical":
                continue
            if "start_mm" not in el.params or "end_mm" not in el.params:
                continue
            if el.category not in {
                "pipe",
                "plumbing_pipe",
                "duct",
                "hvac",
                "conduit",
            } and el.params.get("fitting_type") not in {"pipe", "duct", "conduit"}:
                continue
            try:
                s, e = el.params["start_mm"], el.params["end_mm"]
                x0, y0 = float(s[0]), float(s[1])
                x1, y1 = float(e[0]), float(e[1])
            except (TypeError, ValueError, IndexError, KeyError):
                continue
            length = math.hypot(x1 - x0, y1 - y0)
            if length < 800:
                continue
            prefix = ""
            if el.category == "conduit" or el.params.get("fitting_type") == "conduit":
                prefix = "C "
            elif el.category in {"duct", "hvac"} or el.params.get("fitting_type") == "duct":
                prefix = "D "
            else:
                nps = el.params.get("nps")
                prefix = f'{nps}" ' if nps else "P "
            mep_runs.append((length, x0, y0, x1, y1, prefix))
        mep_runs.sort(key=lambda t: t[0], reverse=True)
        for length, x0, y0, x1, y1, prefix in mep_runs[: max(0, dim_budget)]:
            if length >= 1000:
                lab = f"{prefix}{length / 1000:.2f} m"
            else:
                lab = f"{prefix}{length:.0f} mm"
            parts.extend(_dim_line(x0, y0, x1, y1, project, scale, lab))
        parts.append("  </g>")

    # Grid lines + bubble labels (A,B,C… / 1,2,3…)
    parts.append('  <g class="grids" stroke="#888" stroke-width="0.6" fill="none">')
    for g in model.grids if _on("grids") else []:
        axis = g.params.get("axis", "U")
        labels = g.params.get("labels") or []
        positions = g.params.get("positions_mm") or []
        for i, pos in enumerate(positions):
            p = float(pos)
            if axis == "U":
                px0, py0 = project(p, min_y)
                px1, py1 = project(p, max_y)
                # default U-axis labels: 1, 2, 3…
                lab = str(labels[i]) if i < len(labels) else str(i + 1)
            else:
                px0, py0 = project(min_x, p)
                px1, py1 = project(max_x, p)
                # default V-axis labels: A, B, C…
                lab = str(labels[i]) if i < len(labels) else chr(ord("A") + (i % 26))
            parts.append(
                f'    <line x1="{fmt(px0)}" y1="{fmt(py0)}" x2="{fmt(px1)}" y2="{fmt(py1)}" '
                f'stroke-dasharray="4 4"/>'
            )
            # bubble at both ends
            br = max(8.0, 120 * scale)
            for bx, by in ((px0, py0), (px1, py1)):
                parts.append(
                    f'    <circle cx="{fmt(bx)}" cy="{fmt(by)}" r="{fmt(br)}" '
                    f'fill="#fff" stroke="#555" stroke-width="1"/>'
                )
                parts.append(
                    f'    <text x="{fmt(bx)}" y="{fmt(by + br * 0.35)}" text-anchor="middle" '
                    f'font-size="{fmt(max(7, br * 0.9))}" fill="#333" font-family="sans-serif">'
                    f"{esc(lab)}</text>"
                )
    parts.append("  </g>")

    # Grid dimension chains: running dims between consecutive grid positions
    # (top band for the U axis, left band for the V axis) + overall dimension.
    _gd_br = max(8.0, 120 * scale)  # grid bubble radius (chains sit outside it)
    if grid_dims and _on("grids") and model.grids:
        u_pos = sorted(
            float(p)
            for g in model.grids
            if g.params.get("axis", "U") == "U"
            for p in (g.params.get("positions_mm") or [])
        )
        v_pos = sorted(
            float(p)
            for g in model.grids
            if g.params.get("axis", "U") == "V"
            for p in (g.params.get("positions_mm") or [])
        )
        parts.append(
            '  <g class="grid-dims" stroke="#333" stroke-width="0.8" fill="#111" '
            'font-family="sans-serif" font-size="9">'
        )

        def _tick(x: float, y: float) -> str:
            return (
                f'    <line x1="{fmt(x - 3)}" y1="{fmt(y + 3)}" '
                f'x2="{fmt(x + 3)}" y2="{fmt(y - 3)}" stroke-width="1.1"/>'
            )

        if len(u_pos) >= 2:
            y_run = -(_gd_br + 12)
            y_all = -(_gd_br + 28)
            px_of = {p: project(p, max_y)[0] for p in u_pos}
            for p in u_pos:  # extension lines up through both chains
                parts.append(
                    f'    <line x1="{fmt(px_of[p])}" y1="{fmt(-_gd_br)}" '
                    f'x2="{fmt(px_of[p])}" y2="{fmt(y_all - 3)}" '
                    f'stroke-width="0.5" opacity="0.6"/>'
                )
            for a, b in pairwise(u_pos):
                xa, xb = px_of[a], px_of[b]
                parts.append(
                    f'    <line x1="{fmt(xa)}" y1="{fmt(y_run)}" '
                    f'x2="{fmt(xb)}" y2="{fmt(y_run)}"/>'
                )
                parts.append(_tick(xa, y_run))
                parts.append(_tick(xb, y_run))
                parts.append(
                    f'    <text x="{fmt((xa + xb) / 2)}" y="{fmt(y_run - 3)}" '
                    f'text-anchor="middle">{b - a:.0f}</text>'
                )
            x0, x1 = px_of[u_pos[0]], px_of[u_pos[-1]]
            parts.append(
                f'    <line x1="{fmt(x0)}" y1="{fmt(y_all)}" x2="{fmt(x1)}" y2="{fmt(y_all)}"/>'
            )
            parts.append(_tick(x0, y_all))
            parts.append(_tick(x1, y_all))
            parts.append(
                f'    <text x="{fmt((x0 + x1) / 2)}" y="{fmt(y_all - 3)}" '
                f'text-anchor="middle" font-weight="bold">{u_pos[-1] - u_pos[0]:.0f}</text>'
            )
        if len(v_pos) >= 2:
            x_run = -(_gd_br + 12)
            x_all = -(_gd_br + 28)
            py_of = {p: project(min_x, p)[1] for p in v_pos}
            for p in v_pos:
                parts.append(
                    f'    <line x1="{fmt(-_gd_br)}" y1="{fmt(py_of[p])}" '
                    f'x2="{fmt(x_all - 3)}" y2="{fmt(py_of[p])}" '
                    f'stroke-width="0.5" opacity="0.6"/>'
                )
            for a, b in pairwise(v_pos):
                ya, yb = py_of[a], py_of[b]
                parts.append(
                    f'    <line x1="{fmt(x_run)}" y1="{fmt(ya)}" '
                    f'x2="{fmt(x_run)}" y2="{fmt(yb)}"/>'
                )
                parts.append(_tick(x_run, ya))
                parts.append(_tick(x_run, yb))
                my = (ya + yb) / 2
                parts.append(
                    f'    <text x="{fmt(x_run - 3)}" y="{fmt(my)}" text-anchor="middle" '
                    f'transform="rotate(-90 {fmt(x_run - 3)} {fmt(my)})">{b - a:.0f}</text>'
                )
            y0p, y1p = py_of[v_pos[0]], py_of[v_pos[-1]]
            parts.append(
                f'    <line x1="{fmt(x_all)}" y1="{fmt(y0p)}" x2="{fmt(x_all)}" y2="{fmt(y1p)}"/>'
            )
            parts.append(_tick(x_all, y0p))
            parts.append(_tick(x_all, y1p))
            my = (y0p + y1p) / 2
            parts.append(
                f'    <text x="{fmt(x_all - 3)}" y="{fmt(my)}" text-anchor="middle" '
                f'font-weight="bold" transform="rotate(-90 {fmt(x_all - 3)} {fmt(my)})">'
                f"{v_pos[-1] - v_pos[0]:.0f}</text>"
            )
        parts.append("  </g>")

    # Section cut markers (flag symbols with sheet reference at the cut ends)
    if section_marks:
        parts.append('  <g class="section-marks" font-family="sans-serif">')
        for mark in section_marks:
            mp0 = mark.get("p0")
            mp1 = mark.get("p1")
            if not mp0 or not mp1:
                continue
            ax, ay = project(float(mp0[0]), float(mp0[1]))
            bx, by = project(float(mp1[0]), float(mp1[1]))
            # clamp the cut line onto the content box (cuts extend past extents)
            ax = min(max(ax, 0.0), width)
            bx = min(max(bx, 0.0), width)
            ay = min(max(ay, 0.0), height)
            by = min(max(by, 0.0), height)
            lab = str(mark.get("label") or "A")
            ref = str(mark.get("sheet") or "")
            parts.append(
                f'    <line x1="{fmt(ax)}" y1="{fmt(ay)}" x2="{fmt(bx)}" y2="{fmt(by)}" '
                f'stroke="#1a1a1a" stroke-width="1.3" stroke-dasharray="14 5 3 5"/>'
            )
            dx, dy = bx - ax, by - ay
            dl = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / dl, dx / dl  # viewing direction (perpendicular)
            r = 12.0
            for cx_, cy_ in ((ax, ay), (bx, by)):
                parts.append(
                    f'    <polygon points="{fmt(cx_ + nx * r * 1.9)},{fmt(cy_ + ny * r * 1.9)} '
                    f'{fmt(cx_ + nx * r * 0.9 - dx / dl * r * 0.55)},'
                    f'{fmt(cy_ + ny * r * 0.9 - dy / dl * r * 0.55)} '
                    f'{fmt(cx_ + nx * r * 0.9 + dx / dl * r * 0.55)},'
                    f'{fmt(cy_ + ny * r * 0.9 + dy / dl * r * 0.55)}" fill="#1a1a1a"/>'
                )
                parts.append(
                    f'    <circle cx="{fmt(cx_)}" cy="{fmt(cy_)}" r="{fmt(r)}" '
                    f'fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>'
                )
                parts.append(
                    f'    <line x1="{fmt(cx_ - r)}" y1="{fmt(cy_)}" x2="{fmt(cx_ + r)}" '
                    f'y2="{fmt(cy_)}" stroke="#1a1a1a" stroke-width="0.8"/>'
                )
                parts.append(
                    f'    <text x="{fmt(cx_)}" y="{fmt(cy_ - 2.5)}" text-anchor="middle" '
                    f'font-size="8.5" font-weight="bold">{esc(lab)}</text>'
                )
                parts.append(
                    f'    <text x="{fmt(cx_)}" y="{fmt(cy_ + 8.5)}" text-anchor="middle" '
                    f'font-size="6">{esc(ref)}</text>'
                )
        parts.append("  </g>")

    # Notes
    parts.append('  <g class="notes" fill="#a30" font-family="sans-serif" font-size="10">')
    for note in notes if _on("notes") else []:
        try:
            pos = note.params["position_mm"]
            text = str(note.params.get("text", ""))
            px, py = project(float(pos[0]), float(pos[1]))
            parts.append(f'    <circle cx="{fmt(px)}" cy="{fmt(py)}" r="3" fill="#a30"/>')
            parts.append(f'    <text x="{fmt(px + 6)}" y="{fmt(py)}">{esc(text[:80])}</text>')
        except (KeyError, TypeError, ValueError):
            continue
    parts.append("  </g>")

    # reveal the dimension band (offset 12 + text) and grid bubbles (radius br),
    # which sit just outside the geometry extents, so they render on-canvas.
    dim_pad = max(30.0, 130.0 * scale) if show_dimensions else max(4.0, 130.0 * scale)
    if grid_dims and _on("grids") and model.grids:
        # grid dim chains sit outside the grid bubbles: bubble radius + 2 chains
        dim_pad = max(dim_pad, _gd_br + 44.0)
    body = "\n".join(parts)
    if crop_mm is not None:
        # clip partially-inside geometry at the crop window (+ pad reveal)
        cid = "planclip-" + "-".join(str(int(v)) for v in crop_mm)
        body = (
            f'<defs><clipPath id="{cid}">'
            f'<rect x="{fmt(-dim_pad)}" y="{fmt(-dim_pad)}" '
            f'width="{fmt(width + 2 * dim_pad)}" height="{fmt(height + 2 * dim_pad)}"/>'
            f"</clipPath></defs>\n"
            f'<g clip-path="url(#{cid})">\n{body}\n</g>'
        )
    return DrawingView(width=width, height=height, body=body, title=label, pad=dim_pad)


def render_plan_svg(
    model: ProjectModel,
    level: str,
    *,
    margin_mm: float = 500.0,
    scale: float = 0.05,
    view_range_mm: float = 1200.0,
    title: str | None = None,
    show_dimensions: bool = True,
) -> str:
    view = render_plan_view(
        model,
        level,
        margin_mm=margin_mm,
        scale=scale,
        view_range_mm=view_range_mm,
        title=title,
        show_dimensions=show_dimensions,
    )
    return view.to_svg()


def write_plan_svg(model: ProjectModel, level: str, path: str | Path, **opts: object) -> Path:
    svg = render_plan_svg(model, level, **opts)  # type: ignore[arg-type]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(svg, encoding="utf-8")
    return p
