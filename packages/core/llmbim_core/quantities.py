"""Quantity takeoff / BOQ for builders."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from llmbim_core.model import Element, ProjectModel

if TYPE_CHECKING:
    from llmbim_core.parts_catalog import PartType
from llmbim_core.types_catalog import (
    DEFAULT_DOOR_TYPES,
    DEFAULT_ROOF_TYPES,
    DEFAULT_WALL_TYPES,
    DEFAULT_WINDOW_TYPES,
)


def _wall_length_m(el: Element) -> float:
    return float(el.params.get("length_mm") or 0) / 1000.0


def _wall_height_m(el: Element) -> float:
    return float(el.params.get("height_mm") or 0) / 1000.0


def _wall_thickness_m(el: Element) -> float:
    return float(el.params.get("thickness_mm") or 200) / 1000.0


def wall_area_m2(el: Element) -> float:
    return _wall_length_m(el) * _wall_height_m(el)


def wall_volume_m3(el: Element) -> float:
    return wall_area_m2(el) * _wall_thickness_m(el)


def wall_opening_area_m2(el: Element, model: ProjectModel | None) -> float:
    """Elevational area of the doors and windows hosted by this wall."""
    if model is None:
        return 0.0
    total = 0.0
    for o in model.elements:
        if o.category not in {"door", "window"} or o.host_id != el.id:
            continue
        try:
            w = float(o.params.get("width_mm") or 0.0)
            h = float(o.params.get("height_mm")
                      or (2100 if o.category == "door" else 1200))
        except (TypeError, ValueError):
            continue
        if w > 0 and h > 0:
            total += (w / 1000.0) * (h / 1000.0)
    return total


def wall_net_area_m2(el: Element, model: ProjectModel | None = None) -> float:
    """Wall area with its openings deducted, floored at zero.

    Gross area bills a 16 ft garage door as if it were wall: on the Schad
    set that overstated individual walls by up to 3x. Estimators take
    sheathing, insulation and finish off the NET area.
    """
    return max(0.0, wall_area_m2(el) - wall_opening_area_m2(el, model))


def polygon_area_3d_m2(pts: Sequence[Sequence[float]]) -> float:
    """Area of a planar polygon in 3D (mm) -> m2, via the cross-product sum."""
    n = len(pts)
    if n < 3:
        return 0.0
    cx = cy = cz = 0.0
    for i in range(n):
        ax, ay, az = (float(c) for c in pts[i][:3])
        bx, by, bz = (float(c) for c in pts[(i + 1) % n][:3])
        cx += ay * bz - az * by
        cy += az * bx - ax * bz
        cz += ax * by - ay * bx
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz) / 1e6


def roof_planes_mm(el: Element) -> list[list[Any]]:
    """Normalise a roof's plane polygons across representations.

    Kernel roofs store `planes` as a list of dicts ({polygon_mm, slope, ...});
    an older form stored `planes_mm` as a bare list of polygons. Return a
    plain list of [[x,y,z],...] polygons either way.
    """
    planes = el.params.get("planes")
    if planes:
        out = []
        for p in planes:
            if isinstance(p, dict):
                poly = p.get("polygon_mm") or p.get("polygon") or []
            else:
                poly = p
            if poly:
                out.append(poly)
        return out
    return el.params.get("planes_mm") or []


def roof_area_m2(el: Element) -> float:
    """True area ALONG THE SLOPE, summed over the roof's planes.

    Plan-projected area under-reports a pitched roof by cos(pitch) — 11% at
    6:12 — which is exactly the number shingles and sheathing are bought by.
    """
    return sum(polygon_area_3d_m2(p) for p in roof_planes_mm(el))


def footing_volume_m3(el: Element) -> float:
    """Concrete volume; prefers the value the command already computed."""
    v = el.params.get("concrete_m3")
    if v is not None:
        try:
            return float(v)
        except (TypeError, ValueError):
            pass
    try:
        return (float(el.params.get("width_mm") or 0)
                * float(el.params.get("length_mm") or 0)
                * float(el.params.get("depth_mm") or 0)) / 1e9
    except (TypeError, ValueError):
        return 0.0


def _wall_footprint(el: Element) -> tuple[list[tuple[float, float]], float, float] | None:
    """Oriented wall footprint polygon (mm) + [z0, z1] height band.

    The rectangle is the centreline swept +/- half-thickness, from start to
    end. Used to measure how much two abutting walls overlap at a corner.
    """
    try:
        s, e = el.params["start_mm"], el.params["end_mm"]
        th = float(el.params.get("thickness_mm") or 200.0)
        h = float(el.params.get("height_mm") or 3000.0)
    except (KeyError, TypeError, ValueError):
        return None
    x0, y0, x1, y1 = float(s[0]), float(s[1]), float(e[0]), float(e[1])
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-6 or th <= 0 or h <= 0:
        return None
    nx, ny = -dy / length * th / 2.0, dx / length * th / 2.0
    poly = [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
            (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]
    return poly, 0.0, h          # z band is height-relative; only overlap matters


def _ccw(poly: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return the polygon wound counter-clockwise (positive signed area)."""
    a = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        a += x0 * y1 - x1 * y0
    return poly if a >= 0 else list(reversed(poly))


def _poly_clip_area(subject: list[tuple[float, float]],
                    clip: list[tuple[float, float]]) -> float:
    """Area of the intersection of two convex polygons (Sutherland-Hodgman).

    Both polygons are normalised to CCW first: the half-plane test below
    assumes a CCW clip, and the wall footprints are wound clockwise.
    """
    subject = _ccw(subject)
    clip = _ccw(clip)
    _P = tuple[float, float]

    def inside(p: _P, a: _P, b: _P) -> bool:
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-9

    def isect(p1: _P, p2: _P, a: _P, b: _P) -> _P:
        r = (p2[0] - p1[0], p2[1] - p1[1])
        s = (b[0] - a[0], b[1] - a[1])
        den = r[0] * s[1] - r[1] * s[0]
        if abs(den) < 1e-12:
            return p2
        t = ((a[0] - p1[0]) * s[1] - (a[1] - p1[1]) * s[0]) / den
        return (p1[0] + t * r[0], p1[1] + t * r[1])

    out = list(subject)
    n = len(clip)
    for i in range(n):
        a, b = clip[i], clip[(i + 1) % n]
        inp, out = out, []
        for j in range(len(inp)):
            cur, prev = inp[j], inp[j - 1]
            if inside(cur, a, b):
                if not inside(prev, a, b):
                    out.append(isect(prev, cur, a, b))
                out.append(cur)
            elif inside(prev, a, b):
                out.append(isect(prev, cur, a, b))
        if not out:
            return 0.0
    area = 0.0
    for i in range(len(out)):
        x0, y0 = out[i]
        x1, y1 = out[(i + 1) % len(out)]
        area += x0 * y1 - x1 * y0
    return abs(area) / 2.0


def wall_corner_overlap_m3(model: ProjectModel) -> float:
    """Volume double-counted where wall prisms overlap at shared corners.

    Summing each wall's length x thickness x height counts the corner block
    where two walls meet once per wall. Standard estimating deducts it. The
    overlap is computed EXACTLY as the intersection of the two oriented
    footprints times the shared height, so collinear wall splits (which
    only touch at an edge) contribute nothing and tees/crosses are handled
    on their true geometry rather than a t x t guess.
    """
    fps: list[tuple[list[tuple[float, float]], float, float]] = []
    for el in model.elements:
        if el.category != "wall":
            continue
        fp = _wall_footprint(el)
        if fp is not None:
            fps.append(fp)
    total = 0.0
    for i in range(len(fps)):
        pa, za0, za1 = fps[i]
        for j in range(i + 1, len(fps)):
            pb, zb0, zb1 = fps[j]
            area_mm2 = _poly_clip_area(pa, pb)
            if area_mm2 <= 1.0:
                continue
            h = min(za1, zb1) - max(za0, zb0)
            if h <= 0:
                continue
            total += area_mm2 * h / 1e9
    return total


def slab_area_m2(el: Element) -> float:
    area_mm2 = float(el.params.get("area_mm2") or 0)
    return area_mm2 / 1e6


def equipment_volume_m3(el: Element) -> float:
    try:
        s = el.params["size_mm"]
        return (float(s[0]) * float(s[1]) * float(s[2])) / 1e9
    except (KeyError, TypeError, ValueError, IndexError):
        return 0.0


def compute_boq(model: ProjectModel) -> list[dict[str, Any]]:
    """Bill of quantities with optional catalog costs + CSI codes."""
    from llmbim_core.csi import annotate_boq_with_csi
    from llmbim_core.parts_catalog import get_part, part_unit_cost

    rows: list[dict[str, Any]] = []

    for el in model.query(category="wall"):
        tid = el.type_id or "W-GENERIC-200"
        wt = DEFAULT_WALL_TYPES.get(tid)
        gross = wall_area_m2(el)
        opening = wall_opening_area_m2(el, model)
        area = max(0.0, gross - opening)          # estimators bill net
        vol = area * _wall_thickness_m(el)
        cost = 0.0
        materials = []
        if wt:
            from llmbim_core.materials import get_material, material_cost, material_mass_kg

            for layer in wt.layers:
                layer_vol = area * (layer.thickness_mm / 1000.0)
                mat = get_material(layer.material)
                if mat:
                    layer_cost = material_cost(layer.material, layer_vol)
                    mass = material_mass_kg(layer.material, layer_vol)
                else:
                    layer_cost = layer_vol * layer.unit_cost_per_m3
                    mass = layer_vol * (layer.density_kg_m3 or 0)
                cost += layer_cost
                materials.append(
                    {
                        "material": layer.material,
                        "thickness_mm": layer.thickness_mm,
                        "volume_m3": round(layer_vol, 4),
                        "mass_kg": round(mass, 2),
                        "cost": round(layer_cost, 2),
                    }
                )
        rows.append(
            {
                "category": "wall",
                "id": el.id,
                "name": el.name,
                "type_id": tid,
                "type_name": wt.name if wt else "",
                "qty": round(area, 3),
                "unit": "m2",
                "gross_qty": round(gross, 3),
                "opening_deduction_m2": round(opening, 3),
                "secondary_qty": round(vol, 4),
                "secondary_unit": "m3",
                "est_cost": round(cost, 2),
                "phase": el.params.get("phase", "new"),
                "materials": materials,
            }
        )

    for el in model.query(category="roof"):
        # Roofs had no BOQ line at all — the same closed-dispatch omission
        # that kept them out of the IFC and STEP exporters.
        tid = el.type_id or "R-GENERIC-200"
        rt = DEFAULT_ROOF_TYPES.get(tid)
        area = roof_area_m2(el)
        th = float(el.params.get("thickness_mm") or 0) / 1000.0
        cost = 0.0
        materials = []
        if rt:
            from llmbim_core.materials import get_material, material_cost, material_mass_kg

            for layer in rt.layers:
                layer_vol = area * (layer.thickness_mm / 1000.0)
                if get_material(layer.material):
                    layer_cost = material_cost(layer.material, layer_vol)
                    mass = material_mass_kg(layer.material, layer_vol)
                else:
                    layer_cost = layer_vol * layer.unit_cost_per_m3
                    mass = layer_vol * (layer.density_kg_m3 or 0)
                cost += layer_cost
                materials.append(
                    {
                        "material": layer.material,
                        "thickness_mm": layer.thickness_mm,
                        "volume_m3": round(layer_vol, 4),
                        "mass_kg": round(mass, 2),
                        "cost": round(layer_cost, 2),
                    }
                )
        rows.append(
            {
                "category": "roof",
                "id": el.id,
                "name": el.name,
                "type_id": tid,
                "type_name": rt.name if rt else "",
                "qty": round(area, 3),
                "unit": "m2",
                "secondary_qty": round(area * th, 4),
                "secondary_unit": "m3",
                "est_cost": round(cost, 2),
                "phase": el.params.get("phase", "new"),
                "materials": materials,
                "pitch": el.params.get("pitch"),
                "roof_kind": el.params.get("kind"),
            }
        )

    for el in model.query(category="footing"):
        vol = footing_volume_m3(el)
        length_m = float(el.params.get("length_mm") or 0) / 1000.0
        cost = vol * 420.0                       # concrete in place, formed
        rows.append(
            {
                "category": "footing",
                "id": el.id,
                "name": el.name,
                "type_id": el.type_id or str(el.params.get("mark") or "FTG"),
                "type_name": f"{el.params.get('kind', 'strip')} footing",
                "qty": round(vol, 4),
                "unit": "m3",
                "secondary_qty": round(length_m, 3),
                "secondary_unit": "m",
                "est_cost": round(cost, 2),
                "phase": el.params.get("phase", "new"),
                "materials": [
                    {"material": "concrete", "volume_m3": round(vol, 4),
                     "cost": round(cost, 2)}
                ],
                # kernel footings carry rebar as a spec string, not a count
                "rebar": el.params.get("rebar") or "",
                "mark": el.params.get("mark") or "",
            }
        )

    for el in model.query(category="stem_wall"):
        # Concrete stem wall on the footing: length x thickness x height.
        length_m = float(el.params.get("length_mm") or 0) / 1000.0
        th = float(el.params.get("thickness_mm") or 0) / 1000.0
        h = float(el.params.get("height_mm") or 0) / 1000.0
        vol = length_m * th * h
        cost = vol * 460.0                       # formed concrete wall
        rows.append(
            {
                "category": "stem_wall",
                "id": el.id,
                "name": el.name,
                "type_id": el.type_id or str(el.params.get("mark") or "STEM"),
                "type_name": "concrete stem wall",
                "qty": round(vol, 4),
                "unit": "m3",
                "secondary_qty": round(length_m, 3),
                "secondary_unit": "m",
                "est_cost": round(cost, 2),
                "phase": el.params.get("phase", "new"),
                "materials": [
                    {"material": "concrete", "volume_m3": round(vol, 4),
                     "cost": round(cost, 2)}
                ],
                "anchor_bolts": el.params.get("anchor_bolts") or "",
                "mark": el.params.get("mark") or "",
            }
        )

    for el in model.query(category="slab"):
        area = slab_area_m2(el)
        th = float(el.params.get("thickness_mm") or 200) / 1000.0
        vol = area * th
        # default concrete cost
        cost = vol * 350.0
        rows.append(
            {
                "category": "slab",
                "id": el.id,
                "name": el.name,
                "type_id": el.type_id or "SLAB-CONC",
                "type_name": "Concrete slab",
                "qty": round(area, 3),
                "unit": "m2",
                "secondary_qty": round(vol, 4),
                "secondary_unit": "m3",
                "est_cost": round(cost, 2),
                "phase": el.params.get("phase", "new"),
                "materials": [{"material": "concrete", "volume_m3": round(vol, 4), "cost": round(cost, 2)}],
            }
        )

    for el in model.query(category="door"):
        tid = el.type_id or "D-HM-36"
        dt = DEFAULT_DOOR_TYPES.get(tid)
        cost = dt.unit_cost if dt else 1500.0
        rows.append(
            {
                "category": "door",
                "id": el.id,
                "name": el.name,
                "type_id": tid,
                "type_name": dt.name if dt else "",
                "qty": 1,
                "unit": "ea",
                "secondary_qty": float(el.params.get("width_mm") or 0),
                "secondary_unit": "width_mm",
                "est_cost": cost,
                "phase": el.params.get("phase", "new"),
                "materials": [],
            }
        )

    for el in model.query(category="window"):
        tid = el.type_id or "WIN-STD-48x48"
        win_t = DEFAULT_WINDOW_TYPES.get(tid)
        cost = win_t.unit_cost if win_t else 800.0
        rows.append(
            {
                "category": "window",
                "id": el.id,
                "name": el.name,
                "type_id": tid,
                "type_name": win_t.name if win_t else "",
                "qty": 1,
                "unit": "ea",
                "secondary_qty": 0,
                "secondary_unit": "",
                "est_cost": cost,
                "phase": el.params.get("phase", "new"),
                "materials": [],
            }
        )

    for el in model.query(category="room"):
        area = float(el.params.get("area_mm2") or 0) / 1e6
        rows.append(
            {
                "category": "room",
                "id": el.id,
                "name": el.name,
                "type_id": "",
                "type_name": "space",
                "qty": round(area, 3),
                "unit": "m2",
                "secondary_qty": 0,
                "secondary_unit": "",
                "est_cost": 0,
                "phase": el.params.get("phase", "new"),
                "materials": [],
            }
        )

    for el in model.elements:
        is_col = el.category == "column" or el.params.get("fitting_type") == "column"
        is_beam = el.category == "beam" or el.params.get("fitting_type") == "beam"
        if not is_col and not is_beam:
            continue
        length_m = float(el.params.get("length_m") or 0)
        if not length_m and el.params.get("height_mm"):
            length_m = float(el.params["height_mm"]) / 1000.0
        if not length_m and el.params.get("length_mm"):
            length_m = float(el.params["length_mm"]) / 1000.0
        pid = el.params.get("part_id") or el.type_id
        part = get_part(str(pid)) if pid else None
        unit_cost = part_unit_cost(part) if part else 45.0
        cat = "column" if is_col else "beam"
        rows.append(
            {
                "category": cat,
                "id": el.id,
                "name": el.name,
                "type_id": str(pid or el.params.get("section") or cat.upper()),
                "type_name": part.name if part else str(el.params.get("section") or cat),
                "qty": round(length_m, 3),
                "unit": "m",
                "secondary_qty": el.params.get("section"),
                "secondary_unit": "section",
                "est_cost": round(length_m * unit_cost, 2),
                "phase": el.params.get("phase", "new"),
                "csi_code": el.params.get("csi_code") or (part.csi_code if part else "05 12 00"),
                "materials": [
                    {
                        "material": el.params.get("material_id") or "steel_A36",
                        "section": el.params.get("section"),
                    }
                ],
            }
        )

    for el in model.query(category="equipment"):
        vol = equipment_volume_m3(el)
        part_cost = 0.0
        mid = el.params.get("material_id")
        pid = el.params.get("part_id")
        if pid:
            from llmbim_core.parts_catalog import get_part, part_unit_cost

            part = get_part(str(pid))
            if part:
                part_cost = part_unit_cost(part) * float(el.params.get("part_qty") or 1)
        rows.append(
            {
                "category": "equipment",
                "id": el.id,
                "name": el.name,
                "type_id": el.params.get("kind", "") or el.type_id or "",
                "type_name": el.params.get("shape", "box"),
                "qty": 1,
                "unit": "ea",
                "secondary_qty": round(vol, 5),
                "secondary_unit": "envelope_m3",
                "est_cost": round(part_cost, 2),
                "phase": el.params.get("phase", "new"),
                "materials": [{"material": mid, "part_id": pid}] if mid or pid else [],
            }
        )

    # Pipe, fittings, steel, rebar, framing, fixtures — any element with catalog part
    from llmbim_core.parts_catalog import PARTS, get_part, part_unit_cost

    _PIPE_FIT_TYPES = {
        "elbow_90",
        "elbow_45",
        "tee",
        "coupling",
        "cap",
        "union",
        "ball_valve",
        "gate_valve",
        "check_valve",
        "flange",
        "reducer",
        "grooved_coupling",
        "sprinkler_head",
        "diaphragm_valve",
        "sample_valve",
        "strainer",
        "gasket",
        "instrument",
    }
    seen_ids = {r["id"] for r in rows}

    def _qty_and_unit(el: Element, part: PartType | None) -> tuple[float, str]:
        unit = "ea"
        if part and (part.specs or {}).get("unit"):
            unit = str(part.specs["unit"])
        qty = float(el.params.get("part_qty") or 1)
        if unit in ("m", "m2"):
            if el.params.get("length_m") is not None:
                lm = float(el.params["length_m"])
                # prefer geometric length when part_qty was left at 1
                if qty == 1.0 and lm != 1.0:
                    qty = lm
                elif el.params.get("length_m") is not None and unit == "m":
                    # trust part_qty if it matches linear assignment
                    pass
            elif el.params.get("length_mm") is not None:
                qty = float(el.params["length_mm"]) / 1000.0
        return qty, unit

    for el in model.elements:
        if el.id in seen_ids:
            continue
        pid = el.params.get("part_id") or (
            el.type_id if el.type_id and el.type_id in PARTS else None
        )
        part = get_part(str(pid)) if pid else None
        ftype = el.params.get("fitting_type") or (
            (part.specs or {}).get("fitting_type") if part else None
        )
        is_pipe = el.category in {"pipe", "plumbing_pipe"} or ftype == "pipe"
        is_conduit = el.category == "conduit" or ftype == "conduit"
        is_duct = el.category in {"duct", "hvac"} or ftype == "duct"
        is_tray = el.category == "cable_tray" or ftype == "cable_tray"
        is_pipe_fitting = el.category in {"fitting", "fittings"} or (
            ftype in _PIPE_FIT_TYPES
        )
        is_catalog = part is not None and el.category not in {
            "wall",
            "slab",
            "door",
            "window",
            "room",
            "note",
            "grid",
            "equipment",  # already emitted above
        }
        if (
            not is_pipe
            and not is_pipe_fitting
            and not is_catalog
            and not is_duct
            and not is_conduit
            and not is_tray
        ):
            continue

        if is_tray:
            length_m = float(el.params.get("length_m") or 0)
            if not length_m and el.params.get("length_mm"):
                length_m = float(el.params["length_mm"]) / 1000.0
            unit_cost = part_unit_cost(part) if part else 28.0
            rows.append(
                {
                    "category": "cable_tray",
                    "id": el.id,
                    "name": el.name,
                    "type_id": str(pid or "PT-ELEC-CABLE-TRAY"),
                    "type_name": part.name if part else "cable tray",
                    "qty": round(length_m, 3),
                    "unit": "m",
                    "secondary_qty": el.params.get("width_mm"),
                    "secondary_unit": "width_mm",
                    "est_cost": round(length_m * unit_cost, 2),
                    "phase": el.params.get("phase", "new"),
                    "csi_code": el.params.get("csi_code")
                    or (part.csi_code if part else "26 05 36"),
                    "materials": [
                        {
                            "material": el.params.get("material_id") or "galv_steel",
                            "width_mm": el.params.get("width_mm"),
                        }
                    ],
                }
            )
            seen_ids.add(el.id)
            continue

        if is_duct:
            length_m = float(el.params.get("length_m") or 0)
            area_m2 = float(el.params.get("area_m2") or el.params.get("part_qty") or 0)
            unit_cost = part_unit_cost(part) if part else 55.0  # $/m2 galv default
            rows.append(
                {
                    "category": "duct",
                    "id": el.id,
                    "name": el.name,
                    "type_id": str(pid or "PT-HVAC-DUCT-RECT"),
                    "type_name": part.name if part else "rect duct",
                    "qty": round(area_m2 or length_m, 3),
                    "unit": "m2" if area_m2 else "m",
                    "secondary_qty": round(length_m, 3),
                    "secondary_unit": "m",
                    "est_cost": round((area_m2 or length_m) * unit_cost, 2),
                    "phase": el.params.get("phase", "new"),
                    "csi_code": el.params.get("csi_code") or (part.csi_code if part else "23 31 00"),
                    "materials": [
                        {
                            "material": el.params.get("material_id") or "galv_steel",
                            "width_mm": el.params.get("width_mm"),
                            "height_mm": el.params.get("height_mm"),
                        }
                    ],
                }
            )
            seen_ids.add(el.id)
            continue

        if is_conduit:
            length_m = float(el.params.get("length_m") or 0)
            if not length_m and el.params.get("length_mm"):
                length_m = float(el.params["length_mm"]) / 1000.0
            unit_cost = part_unit_cost(part) if part else 4.5
            nps = el.params.get("nps") or el.params.get("trade_size") or ""
            rows.append(
                {
                    "category": "conduit",
                    "id": el.id,
                    "name": el.name,
                    "type_id": str(pid or "PT-ELEC-CONDUIT"),
                    "type_name": part.name if part else "conduit",
                    "qty": round(length_m, 3),
                    "unit": "m",
                    "secondary_qty": nps,
                    "secondary_unit": "trade_size",
                    "est_cost": round(length_m * unit_cost, 2),
                    "phase": el.params.get("phase", "new"),
                    "csi_code": el.params.get("csi_code") or (part.csi_code if part else "26 05 33"),
                    "materials": [
                        {
                            "material": el.params.get("material_id"),
                            "nps": nps,
                        }
                    ],
                }
            )
            seen_ids.add(el.id)
            continue

        if is_pipe:
            length_m = float(el.params.get("length_m") or 0)
            if not length_m and el.params.get("length_mm"):
                length_m = float(el.params["length_mm"]) / 1000.0
            if not length_m:
                length_m = float(el.params.get("part_qty") or 0)
            unit_cost = part_unit_cost(part) if part else 0.0
            nps = el.params.get("nps") or ((part.specs or {}).get("nps") if part else "")
            rows.append(
                {
                    "category": "pipe",
                    "id": el.id,
                    "name": el.name,
                    "type_id": str(pid or ""),
                    "type_name": part.name if part else "pipe",
                    "qty": round(length_m, 3),
                    "unit": "m",
                    "secondary_qty": nps,
                    "secondary_unit": "nps_in",
                    "est_cost": round(length_m * unit_cost, 2),
                    "phase": el.params.get("phase", "new"),
                    "csi_code": part.csi_code if part else "",
                    "materials": [
                        {
                            "material": (part.primary_material_id if part else el.params.get("material_id")),
                            "nps": nps,
                        }
                    ],
                }
            )
            seen_ids.add(el.id)
            continue

        qty, unit = _qty_and_unit(el, part)
        unit_cost = part_unit_cost(part) if part else 0.0
        if is_pipe_fitting and unit == "ea":
            cat = "fitting"
            secondary = el.params.get("nps") or ((part.specs or {}).get("nps") if part else "")
            secondary_unit = "nps_in"
        else:
            cat = (part.category if part else el.category) or "part"
            specs = (part.specs or {}) if part else {}
            secondary = (
                el.params.get("section")
                or specs.get("section")
                or el.params.get("bar_size")
                or specs.get("bar_size")
                or el.params.get("nps")
                or ""
            )
            secondary_unit = "section" if secondary else ""
        rows.append(
            {
                "category": cat,
                "id": el.id,
                "name": el.name,
                "type_id": str(pid or ""),
                "type_name": part.name if part else str(ftype or cat),
                "qty": round(qty, 3) if unit in ("m", "m2") else qty,
                "unit": unit,
                "secondary_qty": secondary,
                "secondary_unit": secondary_unit,
                "est_cost": round(float(qty) * unit_cost, 2),
                "phase": el.params.get("phase", "new"),
                "csi_code": part.csi_code if part else "",
                "materials": [
                    {
                        "material": (part.primary_material_id if part else el.params.get("material_id")),
                        "fitting_type": ftype,
                        "nps": el.params.get("nps"),
                        "section": el.params.get("section") or ((part.specs or {}).get("section") if part else None),
                    }
                ],
            }
        )
        seen_ids.add(el.id)

    # Machined BREP parts (fab_part): quantity = each, with solid volume and
    # mass from the feature tree so a fab pack produces a real BOQ instead of
    # an empty file.
    for el in model.query(category="fab_part"):
        if el.id in seen_ids or not el.params.get("features"):
            continue
        vol_mm3 = 0.0
        try:
            from llmbim_geometry.fab_brep import HAS_CADQUERY, solid_volume_mm3

            if HAS_CADQUERY:
                vol_mm3 = float(solid_volume_mm3(list(el.params.get("features") or [])))
        except Exception:  # noqa: BLE001
            vol_mm3 = 0.0
        mat_id = str(el.params.get("material_id") or "")
        mass_kg = 0.0
        if vol_mm3:
            try:
                from llmbim_core.materials import material_mass_kg

                mass_kg = float(material_mass_kg(mat_id, vol_mm3 / 1.0e9) or 0.0)
            except Exception:  # noqa: BLE001
                mass_kg = 0.0
        rows.append(
            {
                "category": "fab_part",
                "id": el.id,
                "name": el.name,
                "type_id": mat_id,
                "type_name": mat_id or "machined part",
                "qty": 1,
                "unit": "ea",
                "secondary_qty": round(vol_mm3 / 1.0e9, 6),
                "secondary_unit": "m3",
                "est_cost": 0.0,
                "phase": el.params.get("phase", "new"),
                "csi_code": str(el.params.get("csi_code") or ""),
                "materials": [
                    {
                        "material": mat_id,
                        "mass_kg": round(mass_kg, 3) if mass_kg else None,
                        "volume_mm3": round(vol_mm3, 1) if vol_mm3 else None,
                    }
                ],
            }
        )
        seen_ids.add(el.id)

    return annotate_boq_with_csi(rows, model=model)


def boq_summary(
    rows: list[dict[str, Any]], model: ProjectModel | None = None
) -> dict[str, Any]:
    from llmbim_core.csi import boq_by_csi_division

    by_cat: dict[str, float] = {}
    total = 0.0
    for r in rows:
        c = float(r.get("est_cost") or 0)
        total += c
        by_cat[r["category"]] = by_cat.get(r["category"], 0.0) + c
    out = {
        "line_items": len(rows),
        "est_cost_total": round(total, 2),
        "est_cost_by_category": {k: round(v, 2) for k, v in by_cat.items()},
        "est_cost_by_csi_division": boq_by_csi_division(rows),
        "currency_note": "ENGINEERING ESTIMATE unit costs — not a bid",
    }
    if model is not None:
        # Per-wall volumes are honest as measured; the corner blocks where
        # walls meet are counted once per wall, so the summary carries the
        # deduction rather than silently trimming individual lines.
        gross = sum(float(r.get("secondary_qty") or 0)
                    for r in rows if r["category"] == "wall")
        overlap = wall_corner_overlap_m3(model)
        out["wall_volume_gross_m3"] = round(gross, 4)
        out["wall_corner_deduction_m3"] = round(overlap, 4)
        out["wall_volume_net_m3"] = round(max(0.0, gross - overlap), 4)
        out["wall_volume_note"] = (
            "net = gross - corner overlaps (each wall billed to its own "
            "endpoints; shared corner blocks removed once)"
        )
    return out


def export_boq_csv(model: ProjectModel, path: str | Path) -> Path:
    rows = compute_boq(model)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("", encoding="utf-8")
        return p
    flat = []
    for r in rows:
        flat.append(
            {
                "csi_code": r.get("csi_code", ""),
                "csi_division": r.get("csi_division", ""),
                "category": r["category"],
                "id": r["id"],
                "name": r["name"],
                "type_id": r["type_id"],
                "qty": r["qty"],
                "unit": r["unit"],
                "secondary_qty": r["secondary_qty"],
                "secondary_unit": r["secondary_unit"],
                "est_cost": r["est_cost"],
                "phase": r["phase"],
            }
        )
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
        w.writeheader()
        w.writerows(flat)
    return p


def export_boq_json(model: ProjectModel, path: str | Path) -> Path:
    rows = compute_boq(model)
    payload = {"summary": boq_summary(rows, model), "lines": rows}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return p
