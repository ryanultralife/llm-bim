"""Section and elevation SVG exporters."""

from __future__ import annotations

import math
import zlib
from pathlib import Path

from llmbim_core.errors import ValidationError
from llmbim_core.model import Element, ProjectModel
from llmbim_core.roofs import clip_segment_to_polygon, plane_coeffs

from llmbim_drawings.detail_ops import format_mm_feet_inches
from llmbim_drawings.svg_util import esc, fmt


def _check_units(units: str) -> bool:
    """Validate ``units`` and return True when imperial."""
    if units not in {"metric", "imperial"}:
        raise ValidationError("units must be 'metric' or 'imperial'", units=units)
    return units == "imperial"


def _datum_label(z_mm: float, imperial: bool) -> str:
    """Level datum text: ``EL. +3.500 m`` (metric) / ``EL. +11'-6"`` (imperial)."""
    if imperial:
        sign = "" if z_mm < 0 else "+"
        return f"EL. {sign}{format_mm_feet_inches(z_mm)}"
    return f"EL. {z_mm / 1000:+.3f} m"


def _height_label(dz_mm: float, imperial: bool) -> str:
    """Storey / overall height dimension text."""
    if imperial:
        return format_mm_feet_inches(dz_mm)
    return f"{dz_mm / 1000:.2f} m"


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


def _clip_cut_to_bbox(
    p0: tuple[float, float],
    p1: tuple[float, float],
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
) -> tuple[float, float] | None:
    """Liang-Barsky: parameter window (t0, t1) of segment p0→p1 inside a bbox."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    t0, t1 = 0.0, 1.0
    for p, q in (
        (-dx, p0[0] - minx),
        (dx, maxx - p0[0]),
        (-dy, p0[1] - miny),
        (dy, maxy - p0[1]),
    ):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    if t1 - t0 < 1e-9:
        return None
    return t0, t1


# ── WP-CD-ANATOMY slice B: line-weight hierarchy + material hatches ──────────
# Calibrated on the Sierra Star / Verseon reference sets
# (docs/CD_COMPLETENESS_STANDARD.md §1: line-weight hierarchy, material hatch,
# new/existing poché split). All opt-in; defaults leave output byte-stable.

_TIER_WIDTHS = {"heavy": 2.2, "medium": 1.1, "light": 0.5, "hidden": 0.9}

_WEIGHT_STYLE = (
    "  <style>"
    ".lw-heavy{stroke-width:2.2}"
    ".lw-medium{stroke-width:1.1}"
    ".lw-light{stroke-width:0.5}"
    ".lw-hidden{stroke-width:0.9;stroke-dasharray:5 3}"
    "</style>"
)

_HATCH_LABELS = {
    "concrete": "CONC.",
    "wood": "WD. FRMG.",
    "insulation": "BATT INSUL.",
    "earth": "EARTH",
}


def _line_legend(x: float, y: float) -> str:
    """Line legend block keyed to the 3-tier weight hierarchy (+ hidden)."""
    rows = [
        ("lw-heavy", "#000", None, "HEAVY — CUT / NEW"),
        ("lw-medium", "#333", None, "MEDIUM — BEYOND CUT"),
        ("lw-light", "#777", None, "LIGHT — REFERENCE"),
        ("lw-hidden", "#555", "5 3", "DASHED — HIDDEN / ABV."),
    ]
    w, h = 168.0, 14.0 * len(rows) + 22.0
    parts = [
        f'  <g class="line-legend" font-family="sans-serif" '
        f'transform="translate({fmt(x)},{fmt(y)})">',
        f'    <rect x="0" y="0" width="{fmt(w)}" height="{fmt(h)}" fill="#fff" '
        f'stroke="#111" stroke-width="0.8"/>',
        '    <text x="6" y="13" font-size="8" font-weight="bold" '
        'letter-spacing="0.8">LINE LEGEND</text>',
    ]
    yy = 26.0
    for cls, color, dash, label in rows:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        sw = _TIER_WIDTHS[cls.removeprefix("lw-")]
        parts.append(
            f'    <line class="{cls}" x1="6" y1="{fmt(yy)}" x2="34" y2="{fmt(yy)}" '
            f'stroke="{color}" stroke-width="{fmt(sw)}"{dash_attr}/>'
        )
        parts.append(
            f'    <text x="40" y="{fmt(yy + 3)}" font-size="7.5" '
            f'fill="#111">{esc(label)}</text>'
        )
        yy += 14.0
    parts.append("  </g>")
    return "\n".join(parts)


def _seed_from_id(eid: str, salt: int = 0) -> int:
    """Stable stipple seed from an element id (never Python's ``hash``)."""
    return (zlib.crc32(eid.encode("utf-8")) ^ (salt * 0x9E3779B9)) & 0x7FFFFFFF


def _stipple_circles(x: float, y: float, w: float, h: float, seed: int) -> list[str]:
    """Fine concrete/CMU stipple: deterministic LCG dots inside a screen rect."""
    state = seed or 1

    def rnd() -> float:
        nonlocal state
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        return state / float(0x7FFFFFFF)

    n = min(900, max(6, int(w * h / 28.0)))
    out: list[str] = []
    for _ in range(n):
        out.append(
            f'    <circle cx="{fmt(x + rnd() * w)}" cy="{fmt(y + rnd() * h)}" r="0.5"/>'
        )
    return out


def _diag_lines(x: float, y: float, w: float, h: float, step: float = 5.0) -> list[str]:
    """45° single-direction hatch clipped analytically to a screen rect."""
    out: list[str] = []
    o = step
    while o < w + h:
        if o <= w:
            ax, ay = x + o, y + h
        else:
            ax, ay = x + w, y + h - (o - w)
        if o <= h:
            bx, by = x, y + h - o
        else:
            bx, by = x + o - h, y
        out.append(
            f'    <line x1="{fmt(ax)}" y1="{fmt(ay)}" x2="{fmt(bx)}" y2="{fmt(by)}"/>'
        )
        o += step
    return out


def _batt_zigzag(x: float, y: float, w: float, h: float, step: float = 6.0) -> list[str]:
    """Batt insulation: running zigzag (diagonal-alternative batt loops)."""
    if w < step or h < 2:
        return []
    top, bot = y + h * 0.2, y + h * 0.8
    pts: list[str] = []
    xx, up = x, True
    while xx <= x + w:
        pts.append(f"{fmt(xx)},{fmt(top if up else bot)}")
        up = not up
        xx += step
    return [f'    <polyline points="{" ".join(pts)}" fill="none"/>']


def _earth_ticks(x0: float, x1: float, gy: float, step: float = 16.0) -> list[str]:
    """Standard earth hatch: clusters of diminishing 45° ticks below grade."""
    out: list[str] = []
    xx = x0 + 4.0
    while xx < x1 - 4.0:
        for k, ln in enumerate((9.0, 6.0, 3.0)):
            sx = xx + k * 3.0
            out.append(
                f'    <line x1="{fmt(sx)}" y1="{fmt(gy + 1)}" '
                f'x2="{fmt(sx + ln)}" y2="{fmt(gy + 1 + ln)}"/>'
            )
        xx += step
    return out


def _wall_hatch_kinds(el: Element) -> list[str]:
    """Ordered hatch kinds for a cut wall from its declared layer materials."""
    mats: list[tuple[str, str]] = []
    layers = el.params.get("wall_layers") or []
    if not layers and el.type_id:
        try:
            from llmbim_core.types_catalog import DEFAULT_WALL_TYPES

            wt = DEFAULT_WALL_TYPES.get(el.type_id)
            if wt and wt.layers:
                layers = [layer.model_dump() for layer in wt.layers]
        except Exception:  # noqa: BLE001
            layers = []
    for layer in layers or []:
        try:
            mats.append(
                (
                    str(layer.get("material") or "").lower(),
                    str(layer.get("function") or "").lower(),
                )
            )
        except AttributeError:
            continue
    if not mats:
        m = str(el.params.get("material") or el.params.get("material_id") or "").lower()
        if m:
            mats.append((m, "structure"))
    kinds: list[str] = []
    for m, fn in mats:
        if fn == "insulation" or "insul" in m:
            kind = "insulation"
        elif any(k in m for k in ("cmu", "conc", "masonry", "grout")):
            kind = "concrete"
        elif any(k in m for k in ("wood", "df_", "ply", "osb", "lumber", "timber")):
            kind = "wood"
        else:
            continue
        if kind not in kinds:
            kinds.append(kind)
    return kinds


def render_section_svg(
    model: ProjectModel,
    p0: tuple[float, float],
    p1: tuple[float, float],
    *,
    depth_mm: float = 500.0,  # noqa: ARG001
    scale: float = 0.05,
    margin_mm: float = 500.0,
    title: str | None = None,
    units: str = "metric",
    weights: bool = False,
    hatches: bool = False,
) -> str:
    """Vertical section along cut plane defined by plan segment p0→p1.

    Horizontal axis: distance along cut. Vertical axis: Z elevation.
    ``units="imperial"`` renders level datum labels and storey/overall
    height dimensions as feet-inches (nearest 1/2"; 1 ft = 304.8 mm).

    ``weights=True`` (WP-CD-ANATOMY) renders the CD 3-tier line-weight
    hierarchy: heavy = cut elements, medium = elements beyond the cut plane,
    light = reference (datums/ground); projected elements above the cut walls
    are dashed with an "ABV." label; cut walls with ``phase="existing"``
    render open/lighter poché (new = heavy solid). A line legend is emitted.

    ``hatches=True`` adds material hatches clipped to the cut polygons:
    concrete/CMU fine stipple (seeded from element id, deterministic), wood
    framing 45° diagonal, batt insulation zigzag, earth ticks below the grade
    line — each with a leader note on first appearance.

    Both default ``False`` → output is byte-identical to the legacy renderer.
    """
    imperial = _check_units(units)
    cut_len = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    if cut_len < 1:
        raise ValidationError("Section cut segment too short")

    # Collect wall hits as rectangles in (s, z) space
    rects: list[tuple[float, float, float, float]] = []  # s0, z0, s1, z1
    # WP-CD-ANATOMY: per-rect metadata in lockstep with ``rects`` —
    # (kind, cut-by-plane?, source element) — drives the weight tiers,
    # poché phase split and material hatches. Ignored unless opted in.
    rect_meta: list[tuple[str, bool, Element]] = []
    # WP-SCHAD-S3: foundation cuts (footings / stem walls / slabs-on-grade)
    # drawn as simple outlines below the level-0 datum in their own group
    foundation_rects: list[tuple[float, float, float, float]] = []  # s0, z0, s1, z1
    foundation_meta: list[Element] = []  # lockstep with foundation_rects
    pipe_marks: list[tuple[float, float, float, str]] = []  # s, z, r, stroke
    opening_rects: list[tuple[float, float, float, float, str, str]] = []  # s0,z0,s1,z1,fill,label
    roof_lines: list[tuple[float, float, float, float, float]] = []  # s0,z0,s1,z1,thickness
    roof_ext: list[tuple[float, float, float, float]] = []  # extents only (not drawn as rects)
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
            rect_meta.append(("wall", True, el))
        elif el.category == "roof":
            # Sloped cut lines derived from the STORED planes (llmbim_core.roofs)
            try:
                zlv = _level_elev(model, el.level_id)
                th = float(el.params.get("thickness_mm") or 150.0)
                for pl in el.params.get("planes") or []:
                    poly = pl.get("polygon_mm") or []
                    if len(poly) < 3:
                        continue
                    co = plane_coeffs(poly)
                    if co is None:
                        continue
                    win = clip_segment_to_polygon(p0, p1, poly)
                    if win is None:
                        continue
                    ta, tb = win
                    if tb - ta < 1e-6:
                        continue
                    a_c, b_c, c_c = co
                    pts_sz: list[tuple[float, float]] = []
                    for t in (ta, tb):
                        cx = p0[0] + t * (p1[0] - p0[0])
                        cy = p0[1] + t * (p1[1] - p0[1])
                        pts_sz.append((t * cut_len, zlv + a_c * cx + b_c * cy + c_c))
                    (s0r, zr0), (s1r, zr1) = pts_sz
                    roof_lines.append((s0r, zr0, s1r, zr1, th))
                    roof_ext.append(
                        (min(s0r, s1r), min(zr0, zr1) - th, max(s0r, s1r), max(zr0, zr1))
                    )
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        elif el.category in {"footing", "stem_wall"}:
            # WP-SCHAD-S3: below-datum cut rectangles from the STORED geometry
            try:
                zlv = _level_elev(model, el.level_id)
                if el.category == "stem_wall":
                    z_top = zlv + float(el.params.get("top_mm") or 0.0)
                    z_bot = z_top - float(el.params.get("height_mm") or 0.0)
                    half = max(float(el.params.get("thickness_mm") or 0.0) / 2.0, 60.0)
                else:
                    z_top = zlv + float(el.params.get("top_of_footing_mm") or 0.0)
                    z_bot = z_top - float(el.params.get("depth_mm") or 0.0)
                    half = max(float(el.params.get("width_mm") or 0.0) / 2.0, 60.0)
                if z_top - z_bot < 1.0:
                    continue
                if str(el.params.get("kind") or "") == "pad":
                    c = el.params.get("center_mm") or []
                    if len(c) < 2:
                        continue
                    cx, cy = float(c[0]), float(c[1])
                    hw = float(el.params.get("w_mm") or 0.0) / 2.0
                    hd = float(el.params.get("d_mm") or 0.0) / 2.0
                    ux, uy = (p1[0] - p0[0]) / cut_len, (p1[1] - p0[1]) / cut_len
                    nx, ny = -uy, ux
                    dist = abs((cx - p0[0]) * nx + (cy - p0[1]) * ny)
                    if dist > abs(nx) * hw + abs(ny) * hd:
                        continue  # cut line misses the pad
                    s = (cx - p0[0]) * ux + (cy - p0[1]) * uy
                    half_s = abs(ux) * hw + abs(uy) * hd
                    foundation_rects.append((s - half_s, z_bot, s + half_s, z_top))
                    foundation_meta.append(el)
                    continue
                path = el.params.get("path_mm") or []
                for i in range(len(path) - 1):
                    fx0, fy0 = float(path[i][0]), float(path[i][1])
                    fx1, fy1 = float(path[i + 1][0]), float(path[i + 1][1])
                    t = _segment_intersection_param(
                        fx0, fy0, fx1, fy1, p0[0], p0[1], p1[0], p1[1]
                    )
                    if t is None:
                        continue
                    ix = fx0 + t * (fx1 - fx0)
                    iy = fy0 + t * (fy1 - fy0)
                    s = math.hypot(ix - p0[0], iy - p0[1])
                    foundation_rects.append((s - half, z_bot, s + half, z_top))
                    foundation_meta.append(el)
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        elif el.category == "slab" and el.params.get("kind") == "slab_on_grade":
            # WP-SCHAD-S3: slab band where the cut crosses the polygon bbox
            try:
                poly = el.params.get("polygon_mm") or []
                if len(poly) < 3:
                    continue
                zlv = _level_elev(model, el.level_id)
                z_top = zlv + float(el.params.get("top_of_slab_mm") or 0.0)
                z_bot = z_top - float(el.params.get("thickness_mm") or 0.0)
                xs = [float(q[0]) for q in poly]
                ys = [float(q[1]) for q in poly]
                span = _clip_cut_to_bbox(p0, p1, min(xs), min(ys), max(xs), max(ys))
                if span is None:
                    continue
                t0, t1 = span
                foundation_rects.append((t0 * cut_len, z_bot, t1 * cut_len, z_top))
                foundation_meta.append(el)
            except (KeyError, TypeError, ValueError, IndexError):
                continue
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
                rect_meta.append(("opening", True, el))
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
                rect_meta.append(("column", False, el))
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
                rect_meta.append(("beam", t is not None, el))
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
                    rect_meta.append(("duct", False, el))
                    pipe_marks.append((s, z + h / 2, max(w / 6, 40.0), "#2e7d32"))  # green
                elif is_tray:
                    w = float(el.params.get("width_mm") or 300)
                    h = float(el.params.get("height_mm") or 100)
                    half_w = max(w / 4, 60.0)
                    rects.append((s - half_w, z, s + half_w, z + h))
                    rect_meta.append(("tray", False, el))
                    pipe_marks.append((s, z + h / 2, max(w / 6, 30.0), "#6a1b9a"))  # purple
                elif is_conduit:
                    od = 30.0
                    if el.params.get("size_mm") and len(el.params["size_mm"]) >= 2:
                        od = max(float(el.params["size_mm"][1]), 20.0)
                    pipe_marks.append((s, z + od / 2, od / 2, "#6a1b9a"))
                    rects.append((s - od, z, s + od, z + od))
                    rect_meta.append(("mep", False, el))
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
                    rect_meta.append(("mep", False, el))
            except (KeyError, TypeError, ValueError, IndexError):
                continue

    # Ground line extent (roof cut lines widen the canvas but are not drawn as rects)
    ext_rects = rects + roof_ext + foundation_rects
    if ext_rects:
        min_s = min(r[0] for r in ext_rects) - margin_mm
        max_s = max(r[2] for r in ext_rects) + margin_mm
        min_z = min(r[1] for r in ext_rects) - margin_mm * 0.2
        max_z = max(r[3] for r in ext_rects) + margin_mm * 0.2
    else:
        min_s, max_s, min_z, max_z = 0.0, cut_len, 0.0, 3000.0

    width = (max_s - min_s) * scale
    height = (max_z - min_z) * scale

    def project(s: float, z: float) -> tuple[float, float]:
        return (s - min_s) * scale, (max_z - z) * scale

    label = title or f"{model.name} — Section"
    # reveal the storey + overall dimension bands (anchored up to ~0.7*margin
    # left of the geometry) via a negative-origin viewBox so nothing clips.
    pad = max(16.0, 0.7 * margin_mm * scale + 16.0)
    vb_w, vb_h = width + 2 * pad, height + 2 * pad
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{fmt(-pad)} {fmt(-pad)} {fmt(vb_w)} {fmt(vb_h)}" '
        f'width="{fmt(vb_w)}" height="{fmt(vb_h)}">',
        f"  <title>{esc(label)}</title>",
        f'  <rect x="{fmt(-pad)}" y="{fmt(-pad)}" width="{fmt(vb_w)}" height="{fmt(vb_h)}" '
        f'fill="#fff"/>',
    ]
    if weights:
        parts.append(_WEIGHT_STYLE)
    if not weights:
        parts.append('  <g class="cut-walls" fill="#aaa" stroke="#111" stroke-width="1">')
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
            parts.append(
                f'    <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/>'
            )
        parts.append("  </g>")
    else:
        # WP-CD-ANATOMY: 3-tier weight hierarchy + new/existing poché split.
        # heavy = cut by the section plane; medium = beyond the cut plane
        # (projected within depth); dashed "ABV." = projected AND above the
        # cut walls' top; existing-phase cut walls render open/lighter.
        cut_top = max(
            (r[3] for r, m in zip(rects, rect_meta, strict=True) if m[0] == "wall" and m[1]),
            default=None,
        )
        heavy_new: list[str] = []
        heavy_exist: list[str] = []
        beyond: list[str] = []
        hidden_abv: list[str] = []
        for (s0, z0, s1, z1), (kind, cut, mel) in zip(rects, rect_meta, strict=True):
            if (s1 - s0) < 80 and (z1 - z0) < 80:
                continue  # tiny mep bbox rects drawn as circles instead
            if kind == "opening":
                continue  # drawn in openings-section
            x, y = project(s0, z1)
            w = (s1 - s0) * scale
            h = (z1 - z0) * scale
            rect = f'    <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/>'
            phase = str(mel.params.get("phase") or "new").lower()
            if cut and phase == "existing":
                heavy_exist.append(rect)
            elif cut:
                heavy_new.append(rect)
            elif cut_top is not None and z0 >= cut_top - 1.0:
                hidden_abv.append(rect)
                mx, my = project((s0 + s1) / 2, z1)
                hidden_abv.append(
                    f'    <text x="{fmt(mx)}" y="{fmt(my - 3)}" text-anchor="middle" '
                    f'font-family="sans-serif" font-size="7" fill="#555" '
                    f'stroke="none">ABV.</text>'
                )
            else:
                beyond.append(rect)
        parts.append(
            '  <g class="cut-walls lw-heavy" fill="#4d4d4d" stroke="#000" stroke-width="2.2">'
        )
        parts.extend(heavy_new)
        parts.append("  </g>")
        if heavy_exist:
            parts.append(
                '  <g class="cut-existing lw-medium" fill="#fff" stroke="#333" '
                'stroke-width="1.1">'
            )
            parts.extend(heavy_exist)
            parts.append("  </g>")
        if beyond:
            parts.append(
                '  <g class="beyond-section lw-medium" fill="#e6e6e6" stroke="#333" '
                'stroke-width="1.1">'
            )
            parts.extend(beyond)
            parts.append("  </g>")
        if hidden_abv:
            parts.append(
                '  <g class="hidden-above lw-hidden" fill="none" stroke="#555" '
                'stroke-width="0.9" stroke-dasharray="5 3">'
            )
            parts.extend(hidden_abv)
            parts.append("  </g>")
    if foundation_rects:
        # WP-SCHAD-S3: footings / stem walls / slabs-on-grade cut below the
        # level datum — simple hatch-free outlines
        f_cls = "foundation-section lw-heavy" if weights else "foundation-section"
        f_sw = "2.2" if weights else "1"
        parts.append(
            f'  <g class="{f_cls}" fill="#e3e0da" stroke="#111" stroke-width="{f_sw}">'
        )
        for s0, z0, s1, z1 in foundation_rects:
            x, y = project(s0, z1)
            w = (s1 - s0) * scale
            h = (z1 - z0) * scale
            if w < 0.1 or h < 0.1:
                continue
            parts.append(
                f'    <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/>'
            )
        parts.append("  </g>")
    if roof_lines:
        r_cls = "roof-section lw-heavy" if weights else "roof-section"
        parts.append(f'  <g class="{r_cls}" stroke="#333" stroke-width="2" fill="none">')
        for s0r, zr0, s1r, zr1, th in roof_lines:
            pa, pb = project(s0r, zr0), project(s1r, zr1)
            parts.append(
                f'    <line x1="{fmt(pa[0])}" y1="{fmt(pa[1])}" '
                f'x2="{fmt(pb[0])}" y2="{fmt(pb[1])}"/>'
            )
            # underside of the roof solid (thickness below, cut as parallel line)
            pc, pd = project(s0r, zr0 - th), project(s1r, zr1 - th)
            parts.append(
                f'    <line x1="{fmt(pc[0])}" y1="{fmt(pc[1])}" '
                f'x2="{fmt(pd[0])}" y2="{fmt(pd[1])}" stroke-width="1"/>'
            )
        parts.append("  </g>")
    if opening_rects:
        o_cls = "openings-section lw-medium" if weights else "openings-section"
        parts.append(
            f'  <g class="{o_cls}" stroke="#1565c0" stroke-width="1" '
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
    pi_cls = "pipes-section lw-medium" if weights else "pipes-section"
    parts.append(f'  <g class="{pi_cls}" fill="none" stroke-width="1.5">')
    for s, z, r, stroke in pipe_marks:
        cx, cy = project(s, z)
        parts.append(
            f'    <circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(max(2, r * scale))}" '
            f'stroke="{stroke}" fill="#fff8f0"/>'
        )
    parts.append("  </g>")
    # Ground line
    g_cls = "ground lw-light" if weights else "ground"
    gx0, gy = project(min_s, 0)
    gx1, _ = project(max_s, 0)
    parts.append(
        f'  <line class="{g_cls}" x1="{fmt(gx0)}" y1="{fmt(gy)}" '
        f'x2="{fmt(gx1)}" y2="{fmt(gy)}" stroke="#666" stroke-width="1.5"/>'
    )
    if hatches:
        # WP-CD-ANATOMY: material hatches, analytic clip to the cut polygons
        # (no SVG clipPath ids). Each distinct hatch gets one leader note.
        groups: dict[str, list[str]] = {"concrete": [], "wood": [], "insulation": []}
        notes: dict[str, tuple[float, float]] = {}
        for (s0, z0, s1, z1), (kind, cut, mel) in zip(rects, rect_meta, strict=True):
            if kind != "wall" or not cut:
                continue
            if str(mel.params.get("phase") or "new").lower() == "existing":
                continue  # existing poché stays open
            x, y = project(s0, z1)
            w = (s1 - s0) * scale
            h = (z1 - z0) * scale
            if w < 2 or h < 2:
                continue
            for hk in _wall_hatch_kinds(mel):
                if hk == "concrete":
                    groups[hk].extend(_stipple_circles(x, y, w, h, _seed_from_id(mel.id)))
                elif hk == "wood":
                    groups[hk].extend(_diag_lines(x, y, w, h))
                else:
                    groups[hk].extend(_batt_zigzag(x, y, w, h))
                notes.setdefault(hk, (x + w, y))
        for i, ((s0, z0, s1, z1), fel) in enumerate(
            zip(foundation_rects, foundation_meta, strict=True)
        ):
            x, y = project(s0, z1)
            w = (s1 - s0) * scale
            h = (z1 - z0) * scale
            if w < 2 or h < 2:
                continue
            groups["concrete"].extend(
                _stipple_circles(x, y, w, h, _seed_from_id(fel.id, salt=i + 1))
            )
            notes.setdefault("concrete", (x + w, y))
        if groups["concrete"]:
            parts.append('  <g class="hatch-concrete" fill="#333" stroke="none">')
            parts.extend(groups["concrete"])
            parts.append("  </g>")
        if groups["wood"]:
            parts.append('  <g class="hatch-wood" stroke="#555" stroke-width="0.6" fill="none">')
            parts.extend(groups["wood"])
            parts.append("  </g>")
        if groups["insulation"]:
            parts.append('  <g class="hatch-insul" stroke="#777" stroke-width="0.8" fill="none">')
            parts.extend(groups["insulation"])
            parts.append("  </g>")
        # standard earth hatch: ticks strictly below the grade line
        earth = _earth_ticks(gx0, gx1, gy)
        if earth:
            parts.append('  <g class="hatch-earth" stroke="#7a6a52" stroke-width="0.7">')
            parts.extend(earth)
            parts.append("  </g>")
            notes.setdefault("earth", (gx1, gy + 4))
        if notes:
            parts.append(
                '  <g class="hatch-notes" font-family="sans-serif" font-size="7" '
                'fill="#111" stroke="#111" stroke-width="0.5">'
            )
            for hk, (ax, ay) in notes.items():
                lx, ly = ax + 12, ay - 8
                parts.append(
                    f'    <line x1="{fmt(ax)}" y1="{fmt(ay)}" x2="{fmt(lx)}" y2="{fmt(ly)}"/>'
                )
                parts.append(
                    f'    <text x="{fmt(lx + 2)}" y="{fmt(ly)}" '
                    f'stroke="none">{esc(_HATCH_LABELS[hk])}</text>'
                )
            parts.append("  </g>")
    # Level lines + storey height dims (same as elevation)
    levels = sorted(model.levels, key=lambda lv: float(lv.elevation_mm))
    if levels:
        ld_cls = "level-dims lw-light" if weights else "level-dims"
        parts.append(f'  <g class="{ld_cls}" stroke="#555" fill="#333" font-family="sans-serif">')
        for lv in levels:
            z = float(lv.elevation_mm)
            pa, pb = project(min_s, z), project(max_s, z)
            parts.append(
                f'    <line x1="{fmt(pa[0])}" y1="{fmt(pa[1])}" '
                f'x2="{fmt(pb[0])}" y2="{fmt(pb[1])}" stroke-dasharray="4 3" '
                f'stroke-width="0.7" opacity="0.7"/>'
            )
            # datum label at the right sheet edge: "L2 · EL. +3.500 m"
            parts.append(
                f'    <text x="{fmt(pb[0] + pad - 2)}" y="{fmt(pb[1] - 2)}" '
                f'text-anchor="end" class="level-datum" '
                f'font-size="{fmt(max(7, 9))}" fill="#444">{esc(lv.name)} · '
                f"{esc(_datum_label(z, imperial))}</text>"
            )
        dim_s = min_s - margin_mm * 0.35
        z_top = max_z - margin_mm * 0.2
        for i, lv in enumerate(levels):
            z0 = float(lv.elevation_mm)
            if i + 1 < len(levels):
                z1 = float(levels[i + 1].elevation_mm)
            else:
                z1 = z_top if max_z > z0 + 500 else z0 + 3000
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
            lab = _height_label(z1 - z0, imperial)
            parts.append(
                f'    <text x="{fmt(p0[0] - 6)}" y="{fmt(mid_y)}" text-anchor="end" '
                f'font-size="{fmt(max(7, 9))}" class="storey-height">{esc(lab)}</text>'
            )
        # overall height dimension (lowest level → top) further left
        z_lo = float(levels[0].elevation_mm)
        if z_top - z_lo >= 100:
            dim_s2 = min_s - margin_mm * 0.7
            p0o, p1o = project(dim_s2, z_lo), project(dim_s2, z_top)
            parts.append(
                f'    <line x1="{fmt(p0o[0])}" y1="{fmt(p0o[1])}" '
                f'x2="{fmt(p1o[0])}" y2="{fmt(p1o[1])}" stroke-width="1.2"/>'
            )
            for pt in (p0o, p1o):
                parts.append(
                    f'    <line x1="{fmt(pt[0] - 4)}" y1="{fmt(pt[1])}" '
                    f'x2="{fmt(pt[0] + 4)}" y2="{fmt(pt[1])}" stroke-width="1.2"/>'
                )
            mid_y = (p0o[1] + p1o[1]) / 2
            parts.append(
                f'    <text x="{fmt(p0o[0] - 4)}" y="{fmt(mid_y)}" text-anchor="middle" '
                f'class="overall-height" font-size="{fmt(max(7, 9))}" '
                f'transform="rotate(-90 {fmt(p0o[0] - 4)} {fmt(mid_y)})">'
                f"{esc(_height_label(z_top - z_lo, imperial))}</text>"
            )
        parts.append("  </g>")
    if weights:
        parts.append(_line_legend(-pad + 4.0, -pad + 4.0))
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
    units: str = "metric",
    weights: bool = False,
) -> str:
    """Orthographic elevation. N looks toward +Y (from south), etc.

    ``units="imperial"`` renders level datum labels and storey/overall
    height dimensions as feet-inches (nearest 1/2"; 1 ft = 304.8 mm).

    ``weights=True`` (WP-CD-ANATOMY) applies the CD line-weight hierarchy:
    projected building fabric = medium, below-grade foundations = hidden
    (dashed), level datums = light reference; a line legend is emitted.
    Default ``False`` → output byte-identical to the legacy renderer.
    """
    imperial = _check_units(units)
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

    # wall faces parallel to the view plane, with their depth — used to hide
    # equipment standing behind a nearer facade (hidden-line treatment)
    wall_faces: list[tuple[float, float, float, float, float]] = []  # h0,h1,z0,z1,depth
    # equipment rendered in its own group (was drawn opaque inside the walls group)
    equip_rects: list[tuple[float, float, float, float, float]] = []  # h0,h1,z0,z1,depth
    # roof plane silhouettes: projected polygons [(h, z), ...] per stored plane
    roof_polys: list[list[tuple[float, float]]] = []
    # WP-SCHAD-S3: below-grade foundation outlines, drawn dashed
    found_rects: list[tuple[float, float, float, float]] = []  # h0, h1, z0, z1

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
                parallel = abs(x1 - x0) >= abs(y1 - y0)
                depth_c = (y0 + y1) / 2.0
            else:
                h0, h1 = y0, y1
                parallel = abs(y1 - y0) >= abs(x1 - x0)
                depth_c = (x0 + x1) / 2.0
            segs.append((min(h0, h1), max(h0, h1), z0, z1))
            if parallel:
                wall_faces.append((min(h0, h1), max(h0, h1), z0, z1, depth_c))
        elif el.category == "roof":
            # Sloped silhouettes straight from the STORED planes: gable
            # triangle on end views, eave-to-ridge band on side views.
            try:
                zlv = _level_elev(model, el.level_id)
                for pl in el.params.get("planes") or []:
                    poly = pl.get("polygon_mm") or []
                    if len(poly) < 3:
                        continue
                    pts: list[tuple[float, float]] = []
                    for q in poly:
                        h = float(q[0]) if d in {"N", "S"} else float(q[1])
                        pts.append((h, zlv + float(q[2])))
                    if max(p[0] for p in pts) - min(p[0] for p in pts) < 1.0:
                        continue  # edge-on sliver
                    roof_polys.append(pts)
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        elif el.category in {"footing", "stem_wall"} or (
            el.category == "slab" and el.params.get("kind") == "slab_on_grade"
        ):
            # WP-SCHAD-S3: dashed below-grade extents from the STORED geometry
            try:
                zlv = _level_elev(model, el.level_id)
                if el.category == "stem_wall":
                    z1 = zlv + float(el.params.get("top_mm") or 0.0)
                    z0 = z1 - float(el.params.get("height_mm") or 0.0)
                    pts_xy = el.params.get("path_mm") or []
                elif el.category == "footing":
                    z1 = zlv + float(el.params.get("top_of_footing_mm") or 0.0)
                    z0 = z1 - float(el.params.get("depth_mm") or 0.0)
                    pts_xy = (
                        el.params.get("polygon_mm")
                        if el.params.get("kind") == "pad"
                        else el.params.get("path_mm")
                    ) or []
                else:  # slab-on-grade
                    z1 = zlv + float(el.params.get("top_of_slab_mm") or 0.0)
                    z0 = z1 - float(el.params.get("thickness_mm") or 0.0)
                    pts_xy = el.params.get("polygon_mm") or []
                if not pts_xy or z1 - z0 < 1.0:
                    continue
                hs = [float(q[0]) if d in {"N", "S"} else float(q[1]) for q in pts_xy]
                h0, h1 = min(hs), max(hs)
                # widen strip/stem lines by their plan half-width across the view
                across = float(
                    el.params.get("width_mm") or el.params.get("thickness_mm") or 0.0
                )
                if h1 - h0 < 1.0 and across > 0:
                    h0 -= across / 2.0
                    h1 += across / 2.0
                found_rects.append((h0, h1, z0, z1))
            except (KeyError, TypeError, ValueError, IndexError):
                continue
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
                    eq_depth = y0
                else:
                    r = ly / 2
                    h0, h1 = y0 - r, y0 + r
                    eq_depth = x0 + lx / 2
            else:
                z1 = z0 + hz
                if d in {"N", "S"}:
                    h0, h1 = x0, x0 + lx
                    eq_depth = y0 + ly / 2
                else:
                    h0, h1 = y0, y0 + ly
                    eq_depth = x0 + lx / 2
            # extents only — rendering happens in the equipment group below with
            # hidden-line treatment, not as an opaque rect in the walls group
            equip_rects.append((min(h0, h1), max(h0, h1), z0, z1, eq_depth))
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
        wall_faces = [(-h1, -h0, z0, z1, dp) for (h0, h1, z0, z1, dp) in wall_faces]
        equip_rects = [(-h1, -h0, z0, z1, dp) for (h0, h1, z0, z1, dp) in equip_rects]
        roof_polys = [[(-h, z) for h, z in pts] for pts in roof_polys]
        found_rects = [(-h1, -h0, z0, z1) for (h0, h1, z0, z1) in found_rects]

    extent_rects = segs + [(h0, h1, z0, z1) for (h0, h1, z0, z1, _dp) in equip_rects]
    extent_rects += found_rects
    for pts in roof_polys:
        hs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        extent_rects.append((min(hs), max(hs), min(zs), max(zs)))
    if extent_rects:
        min_h = min(s[0] for s in extent_rects) - margin_mm
        max_h = max(s[1] for s in extent_rects) + margin_mm
        min_z = min(s[2] for s in extent_rects) - margin_mm * 0.1
        max_z = max(s[3] for s in extent_rects) + margin_mm * 0.1
    else:
        min_h, max_h, min_z, max_z = 0.0, 10000.0, 0.0, 3000.0

    width = (max_h - min_h) * scale
    height = (max_z - min_z) * scale

    def project(h: float, z: float) -> tuple[float, float]:
        return (h - min_h) * scale, (max_z - z) * scale

    label = title or f"{model.name} — Elevation {d}"
    # negative-origin viewBox reveals the storey + overall dim bands (left)
    pad = max(16.0, 0.7 * margin_mm * scale + 16.0)
    vb_w, vb_h = width + 2 * pad, height + 2 * pad
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{fmt(-pad)} {fmt(-pad)} {fmt(vb_w)} {fmt(vb_h)}" '
        f'width="{fmt(vb_w)}" height="{fmt(vb_h)}">',
        f"  <title>{esc(label)}</title>",
        f'  <rect x="{fmt(-pad)}" y="{fmt(-pad)}" width="{fmt(vb_w)}" height="{fmt(vb_h)}" '
        f'fill="#fff"/>',
    ]
    if weights:
        parts.append(_WEIGHT_STYLE)
    w_cls = "walls lw-medium" if weights else "walls"
    w_sw = "1.1" if weights else "1"
    parts.append(f'  <g class="{w_cls}" fill="#d0d0d0" stroke="#222" stroke-width="{w_sw}">')
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
    if roof_polys:
        # roof planes over the wall band: gable triangle / sloped eave lines
        re_cls = "roof-elev lw-medium" if weights else "roof-elev"
        parts.append(f'  <g class="{re_cls}" fill="#c9c2b8" stroke="#333" stroke-width="1">')
        for pts in roof_polys:
            pieces = []
            for h, z in pts:
                px, py = project(h, z)
                pieces.append(f"{fmt(px)},{fmt(py)}")
            parts.append(f'    <polygon points="{" ".join(pieces)}"/>')
        parts.append("  </g>")
    if found_rects:
        # WP-SCHAD-S3: foundations below grade shown as dashed hidden lines
        fe_cls = "foundation-elev lw-hidden" if weights else "foundation-elev"
        parts.append(
            f'  <g class="{fe_cls}" fill="none" stroke="#555" '
            'stroke-width="0.8" stroke-dasharray="5 3">'
        )
        for h0, h1, z0, z1 in found_rects:
            x, y = project(h0, z1)
            w = (h1 - h0) * scale
            h = (z1 - z0) * scale
            if w < 0.1 or h < 0.1:
                continue
            parts.append(
                f'    <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"/>'
            )
        parts.append("  </g>")
    if opening_rects:
        oe_cls = "openings-elev lw-medium" if weights else "openings-elev"
        parts.append(
            f'  <g class="{oe_cls}" stroke="#1565c0" stroke-width="1" '
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
    if equip_rects:
        # Hidden-line treatment: equipment standing behind a nearer parallel wall
        # is drawn dashed/unfilled (ghost); only equipment actually visible from
        # this side gets a solid rect. Previously interior equipment was painted
        # opaque on top of the exterior facade.
        near_low = d in {"S", "W"}
        parts.append('  <g class="equipment-elev" stroke="#555" stroke-width="1">')
        for h0, h1, z0, z1, eq_depth in equip_rects:
            hidden = False
            for wh0, wh1, wz0, wz1, w_depth in wall_faces:
                nearer = w_depth < eq_depth - 1.0 if near_low else w_depth > eq_depth + 1.0
                if not nearer:
                    continue
                h_overlap = min(h1, wh1) - max(h0, wh0)
                z_overlap = min(z1, wz1) - max(z0, wz0)
                if h_overlap >= 0.5 * (h1 - h0) and z_overlap >= 0.5 * (z1 - z0):
                    hidden = True
                    break
            x, y = project(h0, z1)
            w = (h1 - h0) * scale
            h = (z1 - z0) * scale
            if w < 0.1:
                continue
            if hidden:
                parts.append(
                    f'    <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" '
                    f'fill="none" stroke-dasharray="3 3" opacity="0.55"/>'
                )
            else:
                parts.append(
                    f'    <rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" '
                    f'fill="#b9c2c9"/>'
                )
        parts.append("  </g>")
    pe_cls = "pipes-elev lw-medium" if weights else "pipes-elev"
    parts.append(
        f'  <g class="{pe_cls}" stroke-width="{fmt(max(1.2, 20 * scale))}" fill="none">'
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
        ld_cls = "level-dims lw-light" if weights else "level-dims"
        parts.append(f'  <g class="{ld_cls}" stroke="#555" fill="#333" font-family="sans-serif">')
        # dashed level reference lines across elev
        for lv in levels:
            z = float(lv.elevation_mm)
            pa, pb = project(min_h, z), project(max_h, z)
            parts.append(
                f'    <line x1="{fmt(pa[0])}" y1="{fmt(pa[1])}" '
                f'x2="{fmt(pb[0])}" y2="{fmt(pb[1])}" stroke-dasharray="4 3" '
                f'stroke-width="0.7" opacity="0.7"/>'
            )
            # datum label at the right sheet edge: "L2 · EL. +3.500 m"
            parts.append(
                f'    <text x="{fmt(pb[0] + pad - 2)}" y="{fmt(pb[1] - 2)}" '
                f'text-anchor="end" class="level-datum" '
                f'font-size="{fmt(max(7, 9))}" fill="#444">{esc(lv.name)} · '
                f"{esc(_datum_label(z, imperial))}</text>"
            )
        # vertical dim between consecutive levels (and to top of highest wall if only one)
        dim_x = min_h - margin_mm * 0.35
        z_top = max_z - margin_mm * 0.1
        for i, lv in enumerate(levels):
            z0 = float(lv.elevation_mm)
            if i + 1 < len(levels):
                z1 = float(levels[i + 1].elevation_mm)
            else:
                # single storey: dim to max wall top on elev
                z1 = z_top if max_z > z0 + 500 else z0 + 3000
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
            lab = _height_label(z1 - z0, imperial)
            parts.append(
                f'    <text x="{fmt(p0[0] - 6)}" y="{fmt(mid_y)}" text-anchor="end" '
                f'font-size="{fmt(max(7, 9))}" class="storey-height">{esc(lab)}</text>'
            )
        # overall height dimension (lowest level → top) further left
        z_lo = float(levels[0].elevation_mm)
        if z_top - z_lo >= 100:
            dim_x2 = min_h - margin_mm * 0.7
            p0o, p1o = project(dim_x2, z_lo), project(dim_x2, z_top)
            parts.append(
                f'    <line x1="{fmt(p0o[0])}" y1="{fmt(p0o[1])}" '
                f'x2="{fmt(p1o[0])}" y2="{fmt(p1o[1])}" stroke-width="1.2"/>'
            )
            for pt in (p0o, p1o):
                parts.append(
                    f'    <line x1="{fmt(pt[0] - 4)}" y1="{fmt(pt[1])}" '
                    f'x2="{fmt(pt[0] + 4)}" y2="{fmt(pt[1])}" stroke-width="1.2"/>'
                )
            mid_y = (p0o[1] + p1o[1]) / 2
            parts.append(
                f'    <text x="{fmt(p0o[0] - 4)}" y="{fmt(mid_y)}" text-anchor="middle" '
                f'class="overall-height" font-size="{fmt(max(7, 9))}" '
                f'transform="rotate(-90 {fmt(p0o[0] - 4)} {fmt(mid_y)})">'
                f"{esc(_height_label(z_top - z_lo, imperial))}</text>"
            )
        parts.append("  </g>")

    if weights:
        parts.append(_line_legend(-pad + 4.0, -pad + 4.0))
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
