"""Section and elevation SVG exporters."""

from __future__ import annotations

import math
from pathlib import Path

from llmbim_core.errors import ValidationError
from llmbim_core.model import Element, ProjectModel

from llmbim_drawings.svg_util import esc, fmt


def _wall_endpoints(el: Element) -> tuple[float, float, float, float, float, float] | None:
    """x0,y0,x1,y1,thickness,height."""
    try:
        start = el.params["start_mm"]
        end = el.params["end_mm"]
        thickness = float(el.params.get("thickness_mm", 200))
        height = float(el.params.get("height_mm", 3000))
    except (KeyError, TypeError):
        return None
    return float(start[0]), float(start[1]), float(end[0]), float(end[1]), thickness, height


def _level_elev(model: ProjectModel | None, level_id: str | None) -> float:
    if not level_id or model is None:
        return 0.0
    for lv in model.levels:
        if lv.id == level_id:
            return lv.elevation_mm
    return 0.0


def _segment_intersection_param(
    ax: float, ay: float, bx: float, by: float,
    cx: float, cy: float, dx: float, dy: float,
) -> float | None:
    """Return t along AB where AB meets infinite line CD, if within AB segment."""
    abx, aby = bx - ax, by - ay
    cdx, cdy = dx - cx, dy - cy
    den = abx * cdy - aby * cdx
    if abs(den) < 1e-9:
        return None
    t = ((cx - ax) * cdy - (cy - ay) * cdx) / den
    if t < -1e-6 or t > 1 + 1e-6:
        return None
    return max(0.0, min(1.0, t))


def render_section_svg(
    model: ProjectModel,
    p0: tuple[float, float],
    p1: tuple[float, float],
    *,
    depth_mm: float = 500.0,  # noqa: ARG001
    scale: float = 0.05,
    margin_mm: float = 500.0,
    title: str | None = None,
) -> str:
    """Vertical section along cut plane defined by plan segment p0→p1.

    Horizontal axis: distance along cut. Vertical axis: Z elevation.
    """
    cut_len = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    if cut_len < 1:
        raise ValidationError("Section cut segment too short")

    # Collect wall hits as rectangles in (s, z) space
    rects: list[tuple[float, float, float, float]] = []  # s0, z0, s1, z1
    pipe_marks: list[tuple[float, float, float, str]] = []  # s, z, r, stroke
    opening_rects: list[tuple[float, float, float, float, str, str]] = []  # s0,z0,s1,z1,fill,label
    wall_by_id = {el.id: el for el in model.elements if el.category == "wall"}
    for el in model.elements:
        if el.category == "wall":
            ep = _wall_endpoints(el)
            if not ep:
                continue
            x0, y0, x1, y1, _t, height = ep
            t = _segment_intersection_param(x0, y0, x1, y1, p0[0], p0[1], p1[0], p1[1])
            if t is None:
                t2 = _segment_intersection_param(p0[0], p0[1], p1[0], p1[1], x0, y0, x1, y1)
                if t2 is None:
                    continue
                s = t2 * cut_len
            else:
                wx = x0 + t * (x1 - x0)
                wy = y0 + t * (y1 - y0)
                s = math.hypot(wx - p0[0], wy - p0[1])
            z0 = _level_elev(model, el.level_id)
            z1 = z0 + height
            half = 100.0
            rects.append((s - half, z0, s + half, z1))
        elif el.category in {"door", "window"}:
            host = wall_by_id.get(el.host_id or "")
            if not host:
                continue
            ep = _wall_endpoints(host)
            if not ep:
                continue
            try:
                hx0, hy0, hx1, hy1, _t, _wh = ep
                wlen = math.hypot(hx1 - hx0, hy1 - hy0)
                if wlen < 1:
                    continue
                off = float(el.params.get("offset_mm") or 0)
                width_o = float(el.params.get("width_mm") or 900)
                oh = float(el.params.get("height_mm") or (2100 if el.category == "door" else 1200))
                sill = float(el.params.get("sill_mm") or 0)
                wux, wuy = (hx1 - hx0) / wlen, (hy1 - hy0) / wlen
                mx = hx0 + wux * (off + width_o / 2)
                my = hy0 + wuy * (off + width_o / 2)
                # host wall near or crossing cut
                t_host = _segment_intersection_param(
                    hx0, hy0, hx1, hy1, p0[0], p0[1], p1[0], p1[1]
                )
                abx, aby = p1[0] - p0[0], p1[1] - p0[1]
                L = math.hypot(abx, aby) or 1.0
                nx, ny = -aby / L, abx / L
                dist = abs((mx - p0[0]) * nx + (my - p0[1]) * ny)
                if t_host is None and dist > max(depth_mm, 800.0):
                    continue
                # s along cut at opening center (or host intersection)
                if t_host is not None:
                    ix = hx0 + t_host * (hx1 - hx0)
                    iy = hy0 + t_host * (hy1 - hy0)
                    s = math.hypot(ix - p0[0], iy - p0[1])
                else:
                    abx, aby = p1[0] - p0[0], p1[1] - p0[1]
                    L2 = abx * abx + aby * aby
                    t_proj = ((mx - p0[0]) * abx + (my - p0[1]) * aby) / L2 if L2 > 1 else 0.0
                    s = t_proj * cut_len
                if s < -500 or s > cut_len + 500:
                    continue
                base = _level_elev(model, host.level_id)
                z_bot = base + sill
                z_top = z_bot + oh
                half = max(width_o / 4, 100.0)
                fill = "#c8e6c9" if el.category == "door" else "#bbdefb"
                tid = str(el.type_id or el.params.get("type_id") or el.category)[:14]
                fr = el.params.get("fire_rating") or ""
                lab = tid
                if fr:
                    fr_s = str(fr).replace(" min", "m").replace("-hr", "HR")
                    lab = f"{tid} {fr_s}"
                opening_rects.append((s - half, z_bot, s + half, z_top, fill, lab))
                rects.append((s - half, z_bot, s + half, z_top))  # bbox extent
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        elif el.category == "column" or el.params.get("fitting_type") == "column":
            try:
                hit = _project_point_to_cut(model, el, p0, p1, cut_len, depth_mm=depth_mm)
                if hit is None:
                    continue
                s, z0 = hit
                # z0 from helper includes z0_mm; rebuild full height from level
                base = _level_elev(model, el.level_id)
                z_base = base + float(el.params.get("z0_mm") or 0)
                sz = el.params.get("size_mm") or [250.0, 250.0, 3000.0]
                half = float(sz[0]) / 2
                ht = float(el.params.get("height_mm") or (sz[2] if len(sz) > 2 else 3000.0))
                rects.append((s - half, z_base, s + half, z_base + ht))
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        elif el.category == "beam" or el.params.get("fitting_type") == "beam":
            try:
                if "start_mm" not in el.params or "end_mm" not in el.params:
                    continue
                s0, e0 = el.params["start_mm"], el.params["end_mm"]
                t = _segment_intersection_param(
                    float(s0[0]), float(s0[1]), float(e0[0]), float(e0[1]),
                    p0[0], p0[1], p1[0], p1[1],
                )
                if t is None:
                    hit = _project_point_to_cut(model, el, p0, p1, cut_len, depth_mm=depth_mm)
                    if hit is None:
                        continue
                    s = hit[0]
                else:
                    ix = float(s0[0]) + t * (float(e0[0]) - float(s0[0]))
                    iy = float(s0[1]) + t * (float(e0[1]) - float(s0[1]))
                    s = math.hypot(ix - p0[0], iy - p0[1])
                base = _level_elev(model, el.level_id)
                z = base + float(el.params.get("z0_mm") or 0)
                depth = float(el.params.get("height_mm") or el.params.get("depth_mm") or 300)
                half = float(el.params.get("width_mm") or 150) / 2
                rects.append((s - half, z, s + half, z + depth))
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        elif el.category in {
            "pipe",
            "plumbing_pipe",
            "fitting",
            "fittings",
            "fixture",
            "duct",
            "hvac",
            "conduit",
            "cable_tray",
        }:
            try:
                hit = _project_point_to_cut(model, el, p0, p1, cut_len, depth_mm=depth_mm)
                if hit is None:
                    continue
                s, z = hit
                cat = el.category or ""
                ftype = str(el.params.get("fitting_type") or "")
                is_duct = cat in {"duct", "hvac"} or ftype == "duct"
                is_conduit = cat == "conduit" or ftype == "conduit"
                is_tray = cat == "cable_tray" or ftype == "cable_tray"
                if is_duct:
                    w = float(el.params.get("width_mm") or 400)
                    h = float(el.params.get("height_mm") or 250)
                    half_w = max(w / 4, 80.0)
                    rects.append((s - half_w, z, s + half_w, z + h))
                    pipe_marks.append((s, z + h / 2, max(w / 6, 40.0), "#2e7d32"))  # green
                elif is_tray:
                    w = float(el.params.get("width_mm") or 300)
                    h = float(el.params.get("height_mm") or 100)
                    half_w = max(w / 4, 60.0)
                    rects.append((s - half_w, z, s + half_w, z + h))
                    pipe_marks.append((s, z + h / 2, max(w / 6, 30.0), "#6a1b9a"))  # purple
                elif is_conduit:
                    od = 30.0
                    if el.params.get("size_mm") and len(el.params["size_mm"]) >= 2:
                        od = max(float(el.params["size_mm"][1]), 20.0)
                    pipe_marks.append((s, z + od / 2, od / 2, "#6a1b9a"))
                    rects.append((s - od, z, s + od, z + od))
                else:
                    od = 40.0
                    if el.params.get("size_mm") and len(el.params["size_mm"]) >= 2:
                        od = max(float(el.params["size_mm"][1]), 20.0)
                    mid = str(el.params.get("material_id") or "")
                    stroke = "#c45c26"
                    if "black" in mid:
                        stroke = "#222"
                    if "ss316" in mid:
                        stroke = "#6b7c8a"
                    pipe_marks.append((s, z + od / 2, od / 2, stroke))
                    rects.append((s - od, z, s + od, z + od))
            except (KeyError, TypeError, ValueError, IndexError):
                continue

    # Ground line extent
    if rects:
        min_s = min(r[0] for r in rects) - margin_mm
        max_s = max(r[2] for r in rects) + margin_mm
        min_z = min(r[1] for r in rects) - margin_mm * 0.2
        max_z = max(r[3] for r in rects) + margin_mm * 0.2
    else:
        min_s, max_s, min_z, max_z = 0.0, cut_len, 0.0, 3000.0

    width = (max_s - min_s) * scale
    height = (max_z - min_z) * scale

    def project(s: float, z: float) -> tuple[float, float]:
        return (s - min_s) * scale, (max_z - z) * scale

    label = title or f"{model.name} — Section"
    # reveal the storey-dimension band (anchored ~0.35*margin left of the geometry)
    # via a negative-origin viewBox so it is not clipped off the left edge.
    pad = max(16.0, 0.4 * margin_mm * scale + 12.0)
    vb_w, vb_h = width + 2 * pad, height + 2 * pad
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{fmt(-pad)} {fmt(-pad)} {fmt(vb_w)} {fmt(vb_h)}" '
        f'width="{fmt(vb_w)}" height="{fmt(vb_h)}">',
        f"  <title>{esc(label)}</title>",
        f'  <rect x="{fmt(-pad)}" y="{fmt(-pad)}" width="{fmt(vb_w)}" height="{fmt(vb_h)}" '
        f'fill="#fff"/>',
        '  <g class="cut-walls" fill="#aaa" stroke="#111" stroke-width="1">',
    ]
    for s0, z0, s1, z1 in rects:
        # skip tiny mep bbox rects drawn as circles instead — only wall-sized
        if (s1 - s0) < 80 and (z1 - z0) < 80:
            continue
        # skip openings — drawn in openings-section
        if any(
            abs(s0 - os0) < 1 and abs(s1 - os1) < 1 and abs(z0 - oz0) < 1 and abs(z1 - oz1) < 1
            for os0, oz0, os1, oz1, _f, _l in opening_rects
        ):
            continue
        x, y = project(s0, z1)
        w = (s1 - s0) * scale
        h = (z1 - z0) * scale
        parts.append(f'    <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/>')
    parts.append("  </g>")
    if opening_rects:
        parts.append(
            '  <g class="openings-section" stroke="#1565c0" stroke-width="1" '
            'font-family="sans-serif" text-anchor="middle">'
        )
        for s0, z0, s1, z1, fill, lab in opening_rects:
            x, y = project(s0, z1)
            w = (s1 - s0) * scale
            h = (z1 - z0) * scale
            if w < 0.1:
                continue
            parts.append(
                f'    <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" '
                f'fill="{fill}"/>'
            )
            mx, my = project((s0 + s1) / 2, z1)
            parts.append(
                f'    <text x="{fmt(mx)}" y="{fmt(my - 2)}" font-size="{fmt(max(6, 9))}" '
                f'fill="#0d47a1">{esc(lab[:18])}</text>'
            )
        parts.append("  </g>")
    parts.append('  <g class="pipes-section" fill="none" stroke-width="1.5">')
    for s, z, r, stroke in pipe_marks:
        cx, cy = project(s, z)
        parts.append(
            f'    <circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(max(2, r * scale))}" '
            f'stroke="{stroke}" fill="#fff8f0"/>'
        )
    parts.append("  </g>")
    # Ground line
    gx0, gy = project(min_s, 0)
    gx1, _ = project(max_s, 0)
    parts.append(
        f'  <line class="ground" x1="{fmt(gx0)}" y1="{fmt(gy)}" '
        f'x2="{fmt(gx1)}" y2="{fmt(gy)}" stroke="#666" stroke-width="1.5"/>'
    )
    # Level lines + storey height dims (same as elevation)
    levels = sorted(model.levels, key=lambda lv: float(lv.elevation_mm))
    if levels:
        parts.append('  <g class="level-dims" stroke="#555" fill="#333" font-family="sans-serif">')
        for lv in levels:
            z = float(lv.elevation_mm)
            pa, pb = project(min_s, z), project(max_s, z)
            parts.append(
                f'    <line x1="{fmt(pa[0])}" y1="{fmt(pa[1])}" '
                f'x2="{fmt(pb[0])}" y2="{fmt(pb[1])}" stroke-dasharray="4 3" '
                f'stroke-width="0.7" opacity="0.7"/>'
            )
            parts.append(
                f'    <text x="{fmt(pa[0] + 2)}" y="{fmt(pa[1] - 2)}" '
                f'font-size="{fmt(max(7, 9))}" fill="#444">{esc(lv.name)} '
                f"EL {z / 1000:.2f}m</text>"
            )
        dim_s = min_s - margin_mm * 0.35
        for i, lv in enumerate(levels):
            z0 = float(lv.elevation_mm)
            if i + 1 < len(levels):
                z1 = float(levels[i + 1].elevation_mm)
            else:
                z1 = max_z - margin_mm * 0.2 if max_z > z0 + 500 else z0 + 3000
            if z1 - z0 < 100:
                continue
            p0, p1 = project(dim_s, z0), project(dim_s, z1)
            parts.append(
                f'    <line x1="{fmt(p0[0])}" y1="{fmt(p0[1])}" '
                f'x2="{fmt(p1[0])}" y2="{fmt(p1[1])}" stroke-width="1"/>'
            )
            for pt in (p0, p1):
                parts.append(
                    f'    <line x1="{fmt(pt[0] - 4)}" y1="{fmt(pt[1])}" '
                    f'x2="{fmt(pt[0] + 4)}" y2="{fmt(pt[1])}" stroke-width="1"/>'
                )
            mid_y = (p0[1] + p1[1]) / 2
            lab = f"{(z1 - z0) / 1000:.2f} m"
            parts.append(
                f'    <text x="{fmt(p0[0] - 6)}" y="{fmt(mid_y)}" text-anchor="end" '
                f'font-size="{fmt(max(7, 9))}" class="storey-height">{esc(lab)}</text>'
            )
        parts.append("  </g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _project_point_to_cut(
    model: ProjectModel,
    el: Element,
    p0: tuple[float, float],
    p1: tuple[float, float],
    cut_len: float,
    *,
    depth_mm: float = 500.0,
) -> tuple[float, float] | None:
    """Map element center to (s along cut, z elev) if within depth of cut plane."""
    if el.params.get("origin_mm"):
        ox, oy = float(el.params["origin_mm"][0]), float(el.params["origin_mm"][1])
    elif el.params.get("start_mm") and el.params.get("end_mm"):
        s, e = el.params["start_mm"], el.params["end_mm"]
        ox = (float(s[0]) + float(e[0])) / 2
        oy = (float(s[1]) + float(e[1])) / 2
    else:
        return None
    ax, ay = p0
    bx, by = p1
    abx, aby = bx - ax, by - ay
    L2 = abx * abx + aby * aby
    if L2 < 1:
        return None
    t = ((ox - ax) * abx + (oy - ay) * aby) / L2
    if t < -0.05 or t > 1.05:
        return None
    closest = (ax + t * abx, ay + t * aby)
    dist = math.hypot(ox - closest[0], oy - closest[1])
    if dist > depth_mm:
        return None
    s = t * cut_len
    z = _level_elev(model, el.level_id) + float(el.params.get("z0_mm") or 0)
    return s, z


def render_elevation_svg(
    model: ProjectModel,
    direction: str,
    *,
    scale: float = 0.05,
    margin_mm: float = 500.0,
    title: str | None = None,
) -> str:
    """Orthographic elevation. N looks toward +Y (from south), etc."""
    d = direction.upper()
    if d not in {"N", "S", "E", "W"}:
        raise ValidationError("direction must be N|S|E|W", direction=direction)

    # Project walls/equipment to (horizontal, z); pipes as horizontal lines at z0
    segs: list[tuple[float, float, float, float]] = []  # h0, h1, z0, z1
    opening_rects: list[tuple[float, float, float, float, str, str]] = []  # h0,h1,z0,z1,fill,label
    pipe_segs: list[tuple[float, float, float, str]] = []  # h0, h1, z, stroke (horizontal)
    riser_segs: list[tuple[float, float, float, str]] = []  # h, z0, z1, stroke (vertical)
    wall_by_id = {el.id: el for el in model.elements if el.category == "wall"}

    # building extent along the view's DEPTH axis (Y for N/S, X for E/W) — used to
    # decide which face an opening is on so opposite elevations differ.
    _wxs: list[float] = []
    _wys: list[float] = []
    for _w in wall_by_id.values():
        _ep = _wall_endpoints(_w)
        if _ep:
            _wxs += [_ep[0], _ep[2]]
            _wys += [_ep[1], _ep[3]]
    depth_vals = _wys if d in {"N", "S"} else _wxs
    depth_mid = (min(depth_vals) + max(depth_vals)) / 2.0 if depth_vals else 0.0

    for el in model.elements:
        if el.category == "wall":
            ep = _wall_endpoints(el)
            if not ep:
                continue
            x0, y0, x1, y1, _t, height = ep
            z0 = _level_elev(model, el.level_id)
            z1 = z0 + height
            if d in {"N", "S"}:
                h0, h1 = x0, x1
            else:
                h0, h1 = y0, y1
            segs.append((min(h0, h1), max(h0, h1), z0, z1))
        elif el.category in {"door", "window"}:
            host = wall_by_id.get(el.host_id or "")
            if not host:
                continue
            ep = _wall_endpoints(host)
            if not ep:
                continue
            try:
                x0, y0, x1, y1, _t, _wh = ep
                length = math.hypot(x1 - x0, y1 - y0)
                if length < 1:
                    continue
                off = float(el.params.get("offset_mm") or 0)
                width_o = float(el.params.get("width_mm") or 900)
                oh = float(el.params.get("height_mm") or (2100 if el.category == "door" else 1200))
                sill = float(el.params.get("sill_mm") or 0)
                ux, uy = (x1 - x0) / length, (y1 - y0) / length
                # Face culling: show this opening only on the elevation that looks
                # at its host wall's near face. A wall running parallel to the view
                # would project the opening as a meaningless sliver -> skip it.
                if d in {"N", "S"}:
                    perpendicular = abs(ux) >= abs(uy)
                    depth_c = (y0 + y1) / 2.0
                else:
                    perpendicular = abs(uy) >= abs(ux)
                    depth_c = (x0 + x1) / 2.0
                if not perpendicular:
                    continue
                near_low = d in {"S", "W"}  # near face is the low-coord side
                if near_low and depth_c > depth_mid + 1.0:
                    continue
                if not near_low and depth_c < depth_mid - 1.0:
                    continue
                ax, ay = x0 + ux * off, y0 + uy * off
                bx, by = x0 + ux * (off + width_o), y0 + uy * (off + width_o)
                if d in {"N", "S"}:
                    h0, h1 = ax, bx
                else:
                    h0, h1 = ay, by
                base = _level_elev(model, host.level_id)
                z_bot = base + sill
                z_top = z_bot + oh
                fill = "#c8e6c9" if el.category == "door" else "#bbdefb"
                tid = str(el.type_id or el.params.get("type_id") or el.category)[:14]
                fr = el.params.get("fire_rating") or ""
                label = tid
                if fr:
                    fr_s = str(fr).replace(" min", "m").replace("-hr", "HR")
                    label = f"{tid} {fr_s}"
                opening_rects.append(
                    (min(h0, h1), max(h0, h1), z_bot, z_top, fill, label)
                )
                segs.append((min(h0, h1), max(h0, h1), z_bot, z_top))  # bbox extent
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        elif el.category == "equipment":
            try:
                o = el.params["origin_mm"]
                s = el.params["size_mm"]
                z0_off = float(el.params.get("z0_mm", 0))
                shape = el.params.get("shape", "box")
            except (KeyError, TypeError, ValueError):
                continue
            x0, y0 = float(o[0]), float(o[1])
            lx, ly, hz = float(s[0]), float(s[1]), float(s[2])
            z0 = _level_elev(model, el.level_id) + z0_off
            if shape == "cylinder":
                z1 = z0 + ly
                if d in {"N", "S"}:
                    h0, h1 = x0, x0 + lx
                else:
                    r = ly / 2
                    h0, h1 = y0 - r, y0 + r
            else:
                z1 = z0 + hz
                if d in {"N", "S"}:
                    h0, h1 = x0, x0 + lx
                else:
                    h0, h1 = y0, y0 + ly
            segs.append((min(h0, h1), max(h0, h1), z0, z1))
        elif el.category == "column" or el.params.get("fitting_type") == "column":
            try:
                o = el.params.get("origin_mm")
                if not o:
                    continue
                sz = el.params.get("size_mm") or [250.0, 250.0, 3000.0]
                half = float(sz[0]) / 2
                ht = float(
                    el.params.get("height_mm")
                    or (sz[2] if len(sz) > 2 else 3000.0)
                )
                z0 = _level_elev(model, el.level_id) + float(el.params.get("z0_mm") or 0)
                ox, oy = float(o[0]), float(o[1])
                h = ox if d in {"N", "S"} else oy
                segs.append((h - half, h + half, z0, z0 + ht))
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        elif (
            el.category
            in {"pipe", "plumbing_pipe", "conduit", "duct", "hvac", "cable_tray", "beam"}
            or el.params.get("fitting_type")
            in {"pipe", "conduit", "duct", "cable_tray", "beam"}
        ):
            try:
                mid = str(el.params.get("material_id") or "")
                stroke = "#c45c26"
                if "black" in mid:
                    stroke = "#222"
                if "ss316" in mid:
                    stroke = "#6b7c8a"
                if el.category in {"duct", "hvac"} or el.params.get("fitting_type") == "duct":
                    stroke = "#2e7d32"
                if el.category == "conduit" or el.params.get("fitting_type") == "conduit":
                    stroke = "#6a1b9a"
                if el.category == "beam" or el.params.get("fitting_type") == "beam":
                    stroke = "#546e7a"
                if el.category == "cable_tray" or el.params.get("fitting_type") == "cable_tray":
                    stroke = "#6a1b9a"
                base = _level_elev(model, el.level_id)
                if el.params.get("vertical") or el.params.get("orientation") == "vertical":
                    o = el.params.get("origin_mm") or el.params.get("start_mm")
                    if not o:
                        continue
                    ox, oy = float(o[0]), float(o[1])
                    h = ox if d in {"N", "S"} else oy
                    z0 = base + float(el.params.get("z0_mm") or 0)
                    z1 = base + float(el.params.get("z1_mm") or (z0 + 1000))
                    lo, hi = min(z0, z1), max(z0, z1)
                    riser_segs.append((h, lo, hi, stroke))
                    segs.append((h - 20, h + 20, lo, hi))
                    continue
                if "start_mm" in el.params and "end_mm" in el.params:
                    s, e = el.params["start_mm"], el.params["end_mm"]
                    x0, y0 = float(s[0]), float(s[1])
                    x1, y1 = float(e[0]), float(e[1])
                else:
                    continue
                z = base + float(el.params.get("z0_mm") or 0)
                if d in {"N", "S"}:
                    h0, h1 = x0, x1
                else:
                    h0, h1 = y0, y1
                # duct/beam: thicker elev bar using height_mm
                elev_h = 50.0
                if el.category in {"duct", "hvac"} or el.params.get("fitting_type") == "duct":
                    elev_h = float(el.params.get("height_mm") or 250)
                if el.category == "beam" or el.params.get("fitting_type") == "beam":
                    elev_h = float(el.params.get("height_mm") or el.params.get("depth_mm") or 300)
                if el.category == "cable_tray" or el.params.get("fitting_type") == "cable_tray":
                    elev_h = float(el.params.get("height_mm") or 100)
                pipe_segs.append((min(h0, h1), max(h0, h1), z, stroke))
                segs.append((min(h0, h1), max(h0, h1), z, z + elev_h))  # bbox
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        elif el.category in {"fitting", "fittings", "fixture"} and el.params.get("origin_mm"):
            try:
                o = el.params["origin_mm"]
                ox, oy = float(o[0]), float(o[1])
                z = _level_elev(model, el.level_id) + float(el.params.get("z0_mm") or 0)
                h = ox if d in {"N", "S"} else oy
                pipe_segs.append((h - 30, h + 30, z, "#c45c26"))
                segs.append((h - 30, h + 30, z, z + 50))
            except (KeyError, TypeError, ValueError, IndexError):
                continue

    # collect column labels for elev annotation
    col_labels: list[tuple[float, float, str]] = []  # h, z_top, section
    for el in model.elements:
        if el.category != "column" and el.params.get("fitting_type") != "column":
            continue
        o = el.params.get("origin_mm")
        if not o:
            continue
        sz = el.params.get("size_mm") or [250, 250, 3000]
        ht = float(el.params.get("height_mm") or (sz[2] if len(sz) > 2 else 3000))
        z0 = _level_elev(model, el.level_id) + float(el.params.get("z0_mm") or 0)
        h = float(o[0]) if d in {"N", "S"} else float(o[1])
        col_labels.append((h, z0 + ht, str(el.params.get("section") or "COL")))

    # N and W are viewed from the opposite side of S and E, so their horizontal
    # axis is mirrored. Flip every collected h so opposite elevations are proper
    # mirror images (previously N was byte-identical to S).
    if d in {"N", "W"}:
        segs = [(-h1, -h0, z0, z1) for (h0, h1, z0, z1) in segs]
        opening_rects = [
            (-h1, -h0, zb, zt, f, lab) for (h0, h1, zb, zt, f, lab) in opening_rects
        ]
        pipe_segs = [(-h1, -h0, z, st) for (h0, h1, z, st) in pipe_segs]
        riser_segs = [(-h, z0, z1, st) for (h, z0, z1, st) in riser_segs]
        col_labels = [(-h, zt, s) for (h, zt, s) in col_labels]

    if segs:
        min_h = min(s[0] for s in segs) - margin_mm
        max_h = max(s[1] for s in segs) + margin_mm
        min_z = min(s[2] for s in segs) - margin_mm * 0.1
        max_z = max(s[3] for s in segs) + margin_mm * 0.1
    else:
        min_h, max_h, min_z, max_z = 0.0, 10000.0, 0.0, 3000.0

    width = (max_h - min_h) * scale
    height = (max_z - min_z) * scale

    def project(h: float, z: float) -> tuple[float, float]:
        return (h - min_h) * scale, (max_z - z) * scale

    label = title or f"{model.name} — Elevation {d}"
    # negative-origin viewBox reveals the storey-dimension band on the left
    pad = max(16.0, 0.4 * margin_mm * scale + 12.0)
    vb_w, vb_h = width + 2 * pad, height + 2 * pad
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{fmt(-pad)} {fmt(-pad)} {fmt(vb_w)} {fmt(vb_h)}" '
        f'width="{fmt(vb_w)}" height="{fmt(vb_h)}">',
        f"  <title>{esc(label)}</title>",
        f'  <rect x="{fmt(-pad)}" y="{fmt(-pad)}" width="{fmt(vb_w)}" height="{fmt(vb_h)}" '
        f'fill="#fff"/>',
        '  <g class="walls" fill="#d0d0d0" stroke="#222" stroke-width="1">',
    ]
    for h0, h1, z0, z1 in segs:
        if (z1 - z0) <= 60 and (h1 - h0) < 500:
            continue  # skip tiny pipe bbox placeholders
        # skip opening-sized rects here — drawn in openings-elev
        if any(
            abs(h0 - oh0) < 1 and abs(h1 - oh1) < 1 and abs(z0 - oz0) < 1 and abs(z1 - oz1) < 1
            for oh0, oh1, oz0, oz1, _f, _l in opening_rects
        ):
            continue
        x, y = project(h0, z1)
        w = (h1 - h0) * scale
        h = (z1 - z0) * scale
        if w < 0.1:
            continue
        parts.append(f'    <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/>')
    parts.append("  </g>")
    if opening_rects:
        parts.append(
            '  <g class="openings-elev" stroke="#1565c0" stroke-width="1" '
            'font-family="sans-serif" text-anchor="middle">'
        )
        for h0, h1, z0, z1, fill, lab in opening_rects:
            x, y = project(h0, z1)
            w = (h1 - h0) * scale
            h = (z1 - z0) * scale
            if w < 0.1:
                continue
            parts.append(
                f'    <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" '
                f'fill="{fill}"/>'
            )
            mx, my = project((h0 + h1) / 2, z1)
            parts.append(
                f'    <text x="{fmt(mx)}" y="{fmt(my - 2)}" font-size="{fmt(max(6, 9))}" '
                f'fill="#0d47a1">{esc(lab[:18])}</text>'
            )
        parts.append("  </g>")
    parts.append(
        f'  <g class="pipes-elev" stroke-width="{fmt(max(1.2, 20 * scale))}" fill="none">'
    )
    for h0, h1, z, stroke in pipe_segs:
        pa, pb = project(h0, z), project(h1, z)
        parts.append(
            f'    <line x1="{fmt(pa[0])}" y1="{fmt(pa[1])}" '
            f'x2="{fmt(pb[0])}" y2="{fmt(pb[1])}" stroke="{stroke}"/>'
        )
    for h, z0, z1, stroke in riser_segs:
        pa, pb = project(h, z0), project(h, z1)
        parts.append(
            f'    <line x1="{fmt(pa[0])}" y1="{fmt(pa[1])}" '
            f'x2="{fmt(pb[0])}" y2="{fmt(pb[1])}" stroke="{stroke}"/>'
        )
    parts.append("  </g>")

    # Column section tags at top of elev
    if col_labels:
        parts.append(
            '  <g class="columns-elev" fill="#37474f" font-family="sans-serif" '
            f'font-size="{fmt(max(7, 10))}" text-anchor="middle">'
        )
        for h, z_top, sec in col_labels:
            px, py = project(h, z_top)
            parts.append(
                f'    <text x="{fmt(px)}" y="{fmt(py - 4)}">{esc(str(sec)[:16])}</text>'
            )
        parts.append("  </g>")

    # Level lines + storey height dimensions (left edge)
    levels = sorted(model.levels, key=lambda lv: float(lv.elevation_mm))
    if levels:
        parts.append('  <g class="level-dims" stroke="#555" fill="#333" font-family="sans-serif">')
        # dashed level reference lines across elev
        for lv in levels:
            z = float(lv.elevation_mm)
            pa, pb = project(min_h, z), project(max_h, z)
            parts.append(
                f'    <line x1="{fmt(pa[0])}" y1="{fmt(pa[1])}" '
                f'x2="{fmt(pb[0])}" y2="{fmt(pb[1])}" stroke-dasharray="4 3" '
                f'stroke-width="0.7" opacity="0.7"/>'
            )
            parts.append(
                f'    <text x="{fmt(pa[0] + 2)}" y="{fmt(pa[1] - 2)}" '
                f'font-size="{fmt(max(7, 9))}" fill="#444">{esc(lv.name)} '
                f"EL {z / 1000:.2f}m</text>"
            )
        # vertical dim between consecutive levels (and to top of highest wall if only one)
        dim_x = min_h - margin_mm * 0.35
        for i, lv in enumerate(levels):
            z0 = float(lv.elevation_mm)
            if i + 1 < len(levels):
                z1 = float(levels[i + 1].elevation_mm)
            else:
                # single storey: dim to max wall top on elev
                z1 = max_z - margin_mm * 0.1 if max_z > z0 + 500 else z0 + 3000
            if z1 - z0 < 100:
                continue
            p0, p1 = project(dim_x, z0), project(dim_x, z1)
            parts.append(
                f'    <line x1="{fmt(p0[0])}" y1="{fmt(p0[1])}" '
                f'x2="{fmt(p1[0])}" y2="{fmt(p1[1])}" stroke-width="1"/>'
            )
            # ticks
            for pt in (p0, p1):
                parts.append(
                    f'    <line x1="{fmt(pt[0] - 4)}" y1="{fmt(pt[1])}" '
                    f'x2="{fmt(pt[0] + 4)}" y2="{fmt(pt[1])}" stroke-width="1"/>'
                )
            mid_y = (p0[1] + p1[1]) / 2
            lab = f"{(z1 - z0) / 1000:.2f} m"
            parts.append(
                f'    <text x="{fmt(p0[0] - 6)}" y="{fmt(mid_y)}" text-anchor="end" '
                f'font-size="{fmt(max(7, 9))}" class="storey-height">{esc(lab)}</text>'
            )
        parts.append("  </g>")

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def write_section_svg(
    model: ProjectModel,
    p0: tuple[float, float],
    p1: tuple[float, float],
    path: str | Path,
    **opts: object,
) -> Path:
    svg = render_section_svg(model, p0, p1, **opts)  # type: ignore[arg-type]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(svg, encoding="utf-8")
    return p


def write_elevation_svg(
    model: ProjectModel, direction: str, path: str | Path, **opts: object
) -> Path:
    svg = render_elevation_svg(model, direction, **opts)  # type: ignore[arg-type]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(svg, encoding="utf-8")
    return p
