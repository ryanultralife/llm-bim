"""Plan-view SVG derivation from the semantic model."""

from __future__ import annotations

import math
from pathlib import Path

from llmbim_core.model import Element, ProjectModel
from llmbim_drawings.svg_util import esc, fmt
from llmbim_drawings.view import DrawingView
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
) -> DrawingView:
    """Build a plan DrawingView (inner body + size)."""
    lvl = model.get_level(level)
    walls = [
        (el, wp)
        for el in model.query(category="wall", level=lvl.name)
        if (wp := _wall_endpoints(el)) is not None
    ]
    doors = model.query(category="door", level=lvl.name)
    windows = model.query(category="window", level=lvl.name)
    rooms = model.query(category="room", level=lvl.name)
    equipment = model.query(category="equipment", level=lvl.name)
    notes = model.query(category="note", level=lvl.name)
    # MEP + catalog proxies on this level
    mep_els = [
        el
        for el in model.elements
        if el.level_id == lvl.id
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
        }
    ]

    xs: list[float] = []
    ys: list[float] = []
    for _el, (x0, y0, x1, y1, t) in walls:
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

    if xs and ys:
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
        f'  <g class="walls" fill="#c8c8c8" stroke="#1a1a1a" stroke-width="{fmt(sw)}" '
        f'stroke-linejoin="round">',
    ]
    for _el, (x0, y0, x1, y1, t) in walls:
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
    wall_by_id = {el.id: el for el, _ in walls}
    for _el, (x0, y0, x1, y1, _t) in walls:
        px0, py0 = project(x0, y0)
        px1, py1 = project(x1, y1)
        parts.append(
            f'    <line x1="{fmt(px0)}" y1="{fmt(py0)}" x2="{fmt(px1)}" y2="{fmt(py1)}"/>'
        )
    parts.append("  </g>")

    parts.append(
        f'  <g class="openings" stroke="#0066aa" stroke-width="{fmt(max(0.4, 10 * scale))}">'
    )
    door_num = 0
    win_num = 0
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
        # door / window tags
        if opening.category == "door":
            door_num += 1
            tag = f"D{door_num}"
            r = max(6.0, 80 * scale)
            parts.append(
                f'    <circle cx="{fmt(pm[0])}" cy="{fmt(pm[1])}" r="{fmt(r)}" '
                f'fill="#e8ffe8" stroke="#228822" stroke-width="1"/>'
            )
            parts.append(
                f'    <text x="{fmt(pm[0])}" y="{fmt(pm[1] + r * 0.35)}" text-anchor="middle" '
                f'font-size="{fmt(max(7, r))}" fill="#145214" font-family="sans-serif">{tag}</text>'
            )
        else:
            win_num += 1
            tag = f"W{win_num}"
            r = max(5.0, 70 * scale)
            parts.append(
                f'    <rect x="{fmt(pm[0] - r)}" y="{fmt(pm[1] - r * 0.6)}" '
                f'width="{fmt(2 * r)}" height="{fmt(1.2 * r)}" fill="#e8f0ff" stroke="#0066aa"/>'
            )
            parts.append(
                f'    <text x="{fmt(pm[0])}" y="{fmt(pm[1] + r * 0.25)}" text-anchor="middle" '
                f'font-size="{fmt(max(6, r * 0.9))}" fill="#003366" font-family="sans-serif">{tag}</text>'
            )
    parts.append("  </g>")

    # Equipment
    parts.append(
        f'  <g class="equipment" fill="#cfe8ff" fill-opacity="0.55" '
        f'stroke="#0b5cab" stroke-width="{fmt(max(0.4, 8 * scale))}">'
    )
    for eq in equipment:
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

    # MEP: pipes (lines) + fittings/fixtures (markers)
    pipe_sw = max(1.2, 25 * scale)
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
    parts.append("  </g>")

    # HVAC ducts as parallel plan lines (width)
    parts.append(
        f'  <g class="ducts" stroke="#2e7d32" stroke-width="{fmt(max(0.8, 12 * scale))}" '
        f'fill="none" stroke-linecap="butt">'
    )
    for el in mep_els:
        if el.category not in {"duct", "hvac"} and el.params.get("fitting_type") != "duct":
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
    parts.append("  </g>")

    parts.append(
        f'  <g class="fittings" fill="#fff3e0" stroke="#c45c26" '
        f'stroke-width="{fmt(max(0.5, 8 * scale))}">'
    )
    for el in mep_els:
        if el.category in {"pipe", "plumbing_pipe", "duct", "hvac", "conduit"}:
            continue
        if el.params.get("fitting_type") == "pipe":
            continue
        if el.params.get("fitting_type") == "duct":
            continue
        try:
            o = el.params.get("origin_mm")
            if not o:
                continue
            ox, oy = float(o[0]), float(o[1])
            px, py = project(ox, oy)
            ftype = str(el.params.get("fitting_type") or el.category)
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
    parts.append("  </g>")

    font = max(8.0, min(28.0, 350 * scale))
    parts.append(
        f'  <g class="labels" fill="#333" font-size="{fmt(font)}" '
        f'font-family="sans-serif" text-anchor="middle">'
    )
    for room in rooms:
        boundary = room.params.get("boundary_mm") or []
        if len(boundary) < 3:
            continue
        cx = sum(float(p[0]) for p in boundary) / len(boundary)
        cy = sum(float(p[1]) for p in boundary) / len(boundary)
        px, py = project(cx, cy)
        parts.append(f'    <text x="{fmt(px)}" y="{fmt(py)}">{esc(room.name or "Room")}</text>')
    for eq in equipment:
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

    if show_dimensions and walls:
        parts.append('  <g class="dimensions">')
        ranked = sorted(
            walls,
            key=lambda t: math.hypot(t[1][2] - t[1][0], t[1][3] - t[1][1]),
            reverse=True,
        )
        for el, (x0, y0, x1, y1, _t) in ranked[:max_dimensions]:
            length = math.hypot(x1 - x0, y1 - y0)
            if length < 500:
                continue
            if length >= 1000:
                lab = f"{length / 1000:.2f} m"
            else:
                lab = f"{length:.0f} mm"
            parts.extend(_dim_line(x0, y0, x1, y1, project, scale, lab))
        parts.append("  </g>")

    # Grid bubbles
    parts.append('  <g class="grids" stroke="#888" stroke-width="0.6" fill="none">')
    for g in model.grids:
        axis = g.params.get("axis", "U")
        for pos in g.params.get("positions_mm") or []:
            p = float(pos)
            if axis == "U":
                px0, py0 = project(p, min_y)
                px1, py1 = project(p, max_y)
            else:
                px0, py0 = project(min_x, p)
                px1, py1 = project(max_x, p)
            parts.append(
                f'    <line x1="{fmt(px0)}" y1="{fmt(py0)}" x2="{fmt(px1)}" y2="{fmt(py1)}" '
                f'stroke-dasharray="4 4"/>'
            )
    parts.append("  </g>")

    # Notes
    parts.append('  <g class="notes" fill="#a30" font-family="sans-serif" font-size="10">')
    for note in notes:
        try:
            pos = note.params["position_mm"]
            text = str(note.params.get("text", ""))
            px, py = project(float(pos[0]), float(pos[1]))
            parts.append(f'    <circle cx="{fmt(px)}" cy="{fmt(py)}" r="3" fill="#a30"/>')
            parts.append(f'    <text x="{fmt(px + 6)}" y="{fmt(py)}">{esc(text[:80])}</text>')
        except (KeyError, TypeError, ValueError):
            continue
    parts.append("  </g>")

    return DrawingView(width=width, height=height, body="\n".join(parts), title=label)


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
