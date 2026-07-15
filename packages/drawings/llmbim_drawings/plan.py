"""Plan-view SVG derivation from the semantic model."""

from __future__ import annotations

import math
from pathlib import Path

from llmbim_core.model import Element, ProjectModel
from llmbim_drawings.svg_util import esc, fmt
from llmbim_geometry.primitives import point_along_segment


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


def render_plan_svg(
    model: ProjectModel,
    level: str,
    *,
    margin_mm: float = 500.0,
    scale: float = 0.05,
    view_range_mm: float = 1200.0,  # noqa: ARG001 — reserved for future cut filter
    title: str | None = None,
) -> str:
    """Render a plan of one level to an SVG string.

    Model space is Y-up (mm). SVG is Y-down; Y is flipped in the bbox.
    ``scale`` multiplies mm → SVG user units (default 0.05 → 20m fits ~1000 units).
    """
    lvl = model.get_level(level)
    walls = [
        wp
        for el in model.query(category="wall", level=lvl.name)
        if (wp := _wall_endpoints(el)) is not None
    ]
    doors = model.query(category="door", level=lvl.name)
    windows = model.query(category="window", level=lvl.name)
    rooms = model.query(category="room", level=lvl.name)

    xs: list[float] = []
    ys: list[float] = []
    for x0, y0, x1, y1, t in walls:
        for px, py in _wall_band(x0, y0, x1, y1, t) or [(x0, y0), (x1, y1)]:
            xs.append(px)
            ys.append(py)
    for room in rooms:
        for pt in room.params.get("boundary_mm", []):
            xs.append(float(pt[0]))
            ys.append(float(pt[1]))
    if xs and ys:
        min_x, max_x = min(xs) - margin_mm, max(xs) + margin_mm
        min_y, max_y = min(ys) - margin_mm, max(ys) + margin_mm
    else:
        min_x, min_y, max_x, max_y = 0.0, 0.0, 1000.0, 1000.0

    width_mm = max_x - min_x
    height_mm = max_y - min_y
    width = width_mm * scale
    height = height_mm * scale

    def project(x: float, y: float) -> tuple[float, float]:
        return (x - min_x) * scale, (max_y - y) * scale

    label = title if title is not None else f"{model.name} — Plan {lvl.name}"
    sw = max(0.5, 15 * scale)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {fmt(width)} {fmt(height)}" '
        f'width="{fmt(width)}" height="{fmt(height)}">',
        f"  <title>{esc(label)}</title>",
        f'  <rect x="0" y="0" width="{fmt(width)}" height="{fmt(height)}" fill="#ffffff"/>',
        f'  <g class="walls" fill="#c8c8c8" stroke="#1a1a1a" stroke-width="{fmt(sw)}" '
        f'stroke-linejoin="round">',
    ]
    for x0, y0, x1, y1, t in walls:
        band = _wall_band(x0, y0, x1, y1, t)
        if not band:
            continue
        pts = " ".join(f"{fmt(px)},{fmt(py)}" for px, py in (project(x, y) for x, y in band))
        parts.append(f'    <polygon points="{pts}"/>')
    parts.append("  </g>")

    parts.append(
        f'  <g class="centerlines" stroke="#8a1a1a" stroke-width="{fmt(max(0.3, 8 * scale))}" '
        f'stroke-dasharray="{fmt(60 * scale)} {fmt(40 * scale)}" fill="none">'
    )
    wall_by_id = {el.id: el for el in model.query(category="wall", level=lvl.name)}
    for x0, y0, x1, y1, _t in walls:
        px0, py0 = project(x0, y0)
        px1, py1 = project(x1, y1)
        parts.append(
            f'    <line x1="{fmt(px0)}" y1="{fmt(py0)}" x2="{fmt(px1)}" y2="{fmt(py1)}"/>'
        )
    parts.append("  </g>")

    # Doors / windows as ticks on host walls
    parts.append(f'  <g class="openings" stroke="#0066aa" stroke-width="{fmt(max(0.4, 10 * scale))}">')
    for opening in list(doors) + list(windows):
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
        except Exception:
            continue
        pa, pb = project(*a), project(*b)
        color = "#228822" if opening.category == "door" else "#0066aa"
        parts.append(
            f'    <line x1="{fmt(pa[0])}" y1="{fmt(pa[1])}" '
            f'x2="{fmt(pb[0])}" y2="{fmt(pb[1])}" stroke="{color}"/>'
        )
    parts.append("  </g>")

    # Room labels at centroid
    parts.append(f'  <g class="rooms" fill="#333" font-size="{fmt(max(8, 200 * scale))}" '
                 f'font-family="sans-serif" text-anchor="middle">')
    for room in rooms:
        boundary = room.params.get("boundary_mm") or []
        if len(boundary) < 3:
            continue
        cx = sum(float(p[0]) for p in boundary) / len(boundary)
        cy = sum(float(p[1]) for p in boundary) / len(boundary)
        px, py = project(cx, cy)
        parts.append(f'    <text x="{fmt(px)}" y="{fmt(py)}">{esc(room.name or "Room")}</text>')
    parts.append("  </g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def write_plan_svg(model: ProjectModel, level: str, path: str | Path, **opts: object) -> Path:
    svg = render_plan_svg(model, level, **opts)  # type: ignore[arg-type]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(svg, encoding="utf-8")
    return p
