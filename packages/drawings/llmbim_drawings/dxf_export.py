"""Minimal DXF R12 export for plan handoff to AutoCAD / BricsCAD / LibreCAD."""

from __future__ import annotations

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
            try:
                s = el.params["start_mm"]
                e = el.params["end_mm"]
            except KeyError:
                continue
            layer = "PIPE-CU"
            mid = str(el.params.get("material_id") or "")
            if "black" in mid:
                layer = "PIPE-FP"
            if "ss316" in mid or "ss" in mid:
                layer = "PIPE-SS"
            ents += _line(float(s[0]), float(s[1]), float(e[0]), float(e[1]), layer)
            nps = el.params.get("nps")
            if nps:
                mx = (float(s[0]) + float(e[0])) / 2
                my = (float(s[1]) + float(e[1])) / 2
                ents += _text(mx, my, 80.0, f'{nps}"', "PIPE-TEXT")
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
