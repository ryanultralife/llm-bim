"""Minimal DXF R12 export for plan handoff to AutoCAD / BricsCAD / LibreCAD."""

from __future__ import annotations

import math
from pathlib import Path

from llmbim_core.model import ProjectModel


def _header() -> list[str]:
    return [
        "0",
        "SECTION",
        "2",
        "HEADER",
        "9",
        "$ACADVER",
        "1",
        "AC1009",
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "TABLES",
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "ENTITIES",
    ]


def _footer() -> list[str]:
    return ["0", "ENDSEC", "0", "EOF"]


def _line(x1: float, y1: float, x2: float, y2: float, layer: str = "0") -> list[str]:
    return [
        "0",
        "LINE",
        "8",
        layer,
        "10",
        f"{x1:.4f}",
        "20",
        f"{y1:.4f}",
        "30",
        "0.0",
        "11",
        f"{x2:.4f}",
        "21",
        f"{y2:.4f}",
        "31",
        "0.0",
    ]


def _text(x: float, y: float, h: float, s: str, layer: str = "TEXT") -> list[str]:
    return [
        "0",
        "TEXT",
        "8",
        layer,
        "10",
        f"{x:.4f}",
        "20",
        f"{y:.4f}",
        "30",
        "0.0",
        "40",
        f"{h:.4f}",
        "1",
        s[:250],
    ]


def _circle(cx: float, cy: float, r: float, layer: str = "0") -> list[str]:
    """DXF R12 CIRCLE entity (plan-space, Z=0)."""
    return [
        "0",
        "CIRCLE",
        "8",
        layer,
        "10",
        f"{cx:.4f}",
        "20",
        f"{cy:.4f}",
        "30",
        "0.0",
        "40",
        f"{r:.4f}",
    ]


def _pipe_layer(el) -> str:
    mid = str(el.params.get("material_id") or "")
    if "black" in mid:
        return "PIPE-FP"
    if "ss316" in mid or (mid.startswith("ss") and "ss" in mid):
        return "PIPE-SS"
    return "PIPE-CU"


def export_plan_dxf(
    model: ProjectModel,
    level: str,
    path: str | Path,
) -> Path:
    """Export plan geometry in mm as DXF R12."""
    lvl = model.get_level(level)
    ents: list[str] = []

    for el in model.query(category="wall", level=lvl.name):
        try:
            s = el.params["start_mm"]
            e = el.params["end_mm"]
        except KeyError:
            continue
        ents += _line(float(s[0]), float(s[1]), float(e[0]), float(e[1]), "WALLS")

    for el in model.query(category="equipment", level=lvl.name):
        poly = el.params.get("polygon_mm") or []
        if len(poly) < 2:
            continue
        for i in range(len(poly)):
            a = poly[i]
            b = poly[(i + 1) % len(poly)]
            ents += _line(float(a[0]), float(a[1]), float(b[0]), float(b[1]), "EQUIP")
        if el.name:
            cx = sum(float(p[0]) for p in poly) / len(poly)
            cy = sum(float(p[1]) for p in poly) / len(poly)
            ents += _text(cx, cy, 100.0, el.name, "TEXT")

    for el in model.query(category="room", level=lvl.name):
        poly = el.params.get("boundary_mm") or []
        if len(poly) < 2:
            continue
        for i in range(len(poly)):
            a = poly[i]
            b = poly[(i + 1) % len(poly)]
            ents += _line(float(a[0]), float(a[1]), float(b[0]), float(b[1]), "ROOMS")
        if el.name:
            cx = sum(float(p[0]) for p in poly) / len(poly)
            cy = sum(float(p[1]) for p in poly) / len(poly)
            ents += _text(cx, cy, 150.0, el.name, "TEXT")

    # MEP pipes / fittings (same level)
    for el in model.elements:
        if el.level_id != lvl.id:
            continue
        if (
            el.category in {"pipe", "plumbing_pipe", "conduit"}
            or el.params.get("fitting_type") in {"pipe", "conduit"}
        ):
            is_conduit = el.category == "conduit" or el.params.get("fitting_type") == "conduit"
            layer = "CONDUIT" if is_conduit else _pipe_layer(el)
            nps = el.params.get("nps") or el.params.get("trade_size")
            # vertical riser: plan symbol = concentric circles + R label
            if el.params.get("vertical") or el.params.get("orientation") == "vertical":
                o = el.params.get("origin_mm") or el.params.get("start_mm")
                if not o:
                    continue
                ox, oy = float(o[0]), float(o[1])
                r_out = 80.0
                ents += _circle(ox, oy, r_out, layer)
                ents += _circle(ox, oy, r_out * 0.4, layer)
                tag = f'R{nps}"' if nps else "R"
                ents += _text(ox + r_out, oy + r_out, 80.0, tag, "PIPE-TEXT")
                continue
            try:
                s = el.params["start_mm"]
                e = el.params["end_mm"]
            except KeyError:
                continue
            x0, y0 = float(s[0]), float(s[1])
            x1, y1 = float(e[0]), float(e[1])
            # degenerate plan length → treat as riser-like point symbol
            if abs(x1 - x0) < 1 and abs(y1 - y0) < 1:
                o = el.params.get("origin_mm") or s
                ox, oy = float(o[0]), float(o[1])
                ents += _circle(ox, oy, 60.0, layer)
                tag = f'R{nps}"' if nps else "R"
                ents += _text(ox + 70.0, oy + 70.0, 80.0, tag, "PIPE-TEXT")
                continue
            ents += _line(x0, y0, x1, y1, layer)
            if nps:
                mx = (x0 + x1) / 2
                my = (y0 + y1) / 2
                ents += _text(mx, my, 80.0, f'{nps}"', "PIPE-TEXT")
        elif el.category in {"duct", "hvac"} or el.params.get("fitting_type") == "duct":
            try:
                s = el.params["start_mm"]
                e = el.params["end_mm"]
                x0, y0 = float(s[0]), float(s[1])
                x1, y1 = float(e[0]), float(e[1])
                w = float(el.params.get("width_mm") or 400)
                length = math.hypot(x1 - x0, y1 - y0)
                if length < 1:
                    continue
                nx, ny = -(y1 - y0) / length, (x1 - x0) / length
                half = w / 2
                for sign in (-1, 1):
                    ents += _line(
                        x0 + sign * half * nx,
                        y0 + sign * half * ny,
                        x1 + sign * half * nx,
                        y1 + sign * half * ny,
                        "DUCT",
                    )
                label = f"{w:.0f}x{float(el.params.get('height_mm') or 0):.0f}"
                ents += _text((x0 + x1) / 2, (y0 + y1) / 2, 90.0, label, "DUCT-TEXT")
            except (KeyError, TypeError, ValueError, IndexError):
                continue
        elif el.category in {"fitting", "fittings", "fixture", "accessory"}:
            o = el.params.get("origin_mm")
            if not o:
                continue
            ox, oy = float(o[0]), float(o[1])
            # small cross mark
            r = 50.0
            ents += _line(ox - r, oy, ox + r, oy, "FITTINGS")
            ents += _line(ox, oy - r, ox, oy + r, "FITTINGS")
            label = el.params.get("nps") or el.params.get("fitting_type") or el.name or "FIT"
            ents += _text(ox + r, oy + r, 70.0, str(label)[:20], "PIPE-TEXT")

    for g in model.grids:
        axis = g.params.get("axis", "U")
        positions = g.params.get("positions_mm") or []
        # draw finite segments
        span = 50000.0
        for pos in positions:
            p = float(pos)
            if axis == "U":
                ents += _line(p, -span / 2, p, span / 2, "GRIDS")
            else:
                ents += _line(-span / 2, p, span / 2, p, "GRIDS")

    lines = _header() + ents + _footer()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p

def _level_elev(model: ProjectModel, level_id: str | None) -> float:
    if not level_id:
        return 0.0
    for lv in model.levels:
        if lv.id == level_id:
            return float(lv.elevation_mm)
    return 0.0


def export_elevation_dxf(
    model: ProjectModel,
    direction: str,
    path: str | Path,
) -> Path:
    """Elevation DXF R12: X = plan axis, Y = elevation Z (mm). Layers WALLS, PIPE-*, LEVELS."""
    d = direction.upper()
    if d not in {"N", "S", "E", "W"}:
        d = "S"
    ents: list[str] = []

    def h_of(x: float, y: float) -> float:
        if d in {"N", "S"}:
            return x
        return y

    # walls as elev rectangles (outline)
    for el in model.query(category="wall"):
        try:
            s = el.params["start_mm"]
            e = el.params["end_mm"]
            ht = float(el.params.get("height_mm", 3000))
        except (KeyError, TypeError, ValueError):
            continue
        z0 = _level_elev(model, el.level_id)
        z1 = z0 + ht
        h0, h1 = h_of(float(s[0]), float(s[1])), h_of(float(e[0]), float(e[1]))
        lo, hi = min(h0, h1), max(h0, h1)
        # rectangle outline
        ents += _line(lo, z0, hi, z0, "WALLS")
        ents += _line(hi, z0, hi, z1, "WALLS")
        ents += _line(hi, z1, lo, z1, "WALLS")
        ents += _line(lo, z1, lo, z0, "WALLS")

    # horizontal pipes / ducts / conduits
    for el in model.elements:
        if el.category not in {
            "pipe",
            "plumbing_pipe",
            "duct",
            "hvac",
            "conduit",
            "fitting",
            "fittings",
            "fixture",
        } and el.params.get("fitting_type") not in {"pipe", "duct", "conduit"}:
            continue
        layer = "PIPE-CU"
        mid = str(el.params.get("material_id") or "")
        if "black" in mid:
            layer = "PIPE-FP"
        if "ss316" in mid:
            layer = "PIPE-SS"
        if el.category in {"duct", "hvac"} or el.params.get("fitting_type") == "duct":
            layer = "DUCT"
        if el.category == "conduit" or el.params.get("fitting_type") == "conduit":
            layer = "CONDUIT"
        base = _level_elev(model, el.level_id)
        if el.params.get("vertical") or el.params.get("orientation") == "vertical":
            o = el.params.get("origin_mm") or el.params.get("start_mm")
            if not o:
                continue
            hx = h_of(float(o[0]), float(o[1]))
            z_lo = base + float(el.params.get("z0_mm") or 0)
            z_hi = base + float(el.params.get("z1_mm") or (z_lo + 1000))
            ents += _line(hx, min(z_lo, z_hi), hx, max(z_lo, z_hi), layer)
            continue
        if "start_mm" in el.params and "end_mm" in el.params:
            try:
                s, e = el.params["start_mm"], el.params["end_mm"]
                h0 = h_of(float(s[0]), float(s[1]))
                h1 = h_of(float(e[0]), float(e[1]))
                z = base + float(el.params.get("z0_mm") or 0)
                elev_h = float(el.params.get("height_mm") or 50)
                if layer == "DUCT":
                    # duct as thin rectangle height
                    ents += _line(min(h0, h1), z, max(h0, h1), z, layer)
                    ents += _line(min(h0, h1), z + elev_h, max(h0, h1), z + elev_h, layer)
                else:
                    ents += _line(h0, z, h1, z, layer)
            except (TypeError, ValueError, IndexError, KeyError):
                continue
        elif el.params.get("origin_mm"):
            o = el.params["origin_mm"]
            hx = h_of(float(o[0]), float(o[1]))
            z = base + float(el.params.get("z0_mm") or 0)
            r = 40.0
            ents += _line(hx - r, z, hx + r, z, "FITTINGS")
            ents += _line(hx, z - r, hx, z + r, "FITTINGS")

    # level markers
    for lv in model.levels:
        z = float(lv.elevation_mm)
        ents += _line(-50000, z, 50000, z, "LEVELS")
        ents += _text(0, z + 50, 120.0, f"{lv.name} EL {z:.0f}", "LEVELS")

    lines = _header() + ents + _footer()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p
