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
        elif el.category in {"pipe", "plumbing_pipe", "fitting", "fittings", "fixture"}:
            try:
                hit = _project_point_to_cut(model, el, p0, p1, cut_len, depth_mm=depth_mm)
                if hit is None:
                    continue
                s, z = hit
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
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(width)} {fmt(height)}" '
        f'width="{fmt(width)}" height="{fmt(height)}">',
        f"  <title>{esc(label)}</title>",
        f'  <rect x="0" y="0" width="{fmt(width)}" height="{fmt(height)}" fill="#fff"/>',
        '  <g class="cut-walls" fill="#aaa" stroke="#111" stroke-width="1">',
    ]
    for s0, z0, s1, z1 in rects:
        # skip tiny mep bbox rects drawn as circles instead — only wall-sized
        if (s1 - s0) < 80 and (z1 - z0) < 80:
            continue
        x, y = project(s0, z1)
        w = (s1 - s0) * scale
        h = (z1 - z0) * scale
        parts.append(f'    <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/>')
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
    pipe_segs: list[tuple[float, float, float, str]] = []  # h0, h1, z, stroke (horizontal)
    riser_segs: list[tuple[float, float, float, str]] = []  # h, z0, z1, stroke (vertical)
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
        elif el.category in {"pipe", "plumbing_pipe"} or el.params.get("fitting_type") == "pipe":
            try:
                mid = str(el.params.get("material_id") or "")
                stroke = "#c45c26"
                if "black" in mid:
                    stroke = "#222"
                if "ss316" in mid:
                    stroke = "#6b7c8a"
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
                pipe_segs.append((min(h0, h1), max(h0, h1), z, stroke))
                segs.append((min(h0, h1), max(h0, h1), z, z + 50))  # bbox
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
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(width)} {fmt(height)}" '
        f'width="{fmt(width)}" height="{fmt(height)}">',
        f"  <title>{esc(label)}</title>",
        f'  <rect width="{fmt(width)}" height="{fmt(height)}" fill="#fff"/>',
        '  <g class="walls" fill="#d0d0d0" stroke="#222" stroke-width="1">',
    ]
    for h0, h1, z0, z1 in segs:
        if (z1 - z0) <= 60 and (h1 - h0) < 500:
            continue  # skip tiny pipe bbox placeholders
        x, y = project(h0, z1)
        w = (h1 - h0) * scale
        h = (z1 - z0) * scale
        if w < 0.1:
            continue
        parts.append(f'    <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/>')
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
    parts.append("  </g></svg>")
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
