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
        if el.category in {"pipe", "plumbing_pipe"} or el.params.get("fitting_type") == "pipe":
            layer = _pipe_layer(el)
            nps = el.params.get("nps")
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
