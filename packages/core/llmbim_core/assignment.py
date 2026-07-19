"""Assign materials, parts, and BOM lines to model elements."""

from __future__ import annotations

from typing import Any

from llmbim_core.errors import ValidationError
from llmbim_core.materials import MATERIALS, get_material
from llmbim_core.model import Element, ProjectModel
from llmbim_core.parts_catalog import (  # noqa: F401 — PARTS used in auto_assign
    PARTS,
    get_part,
    part_unit_cost,
)


def assign_material(
    model: ProjectModel,
    element_id: str,
    material_id: str,
    *,
    role: str = "primary",
) -> dict[str, Any]:
    """Set primary (or named) material on an element."""
    if material_id not in MATERIALS:
        raise ValidationError("Unknown material_id", material_id=material_id)
    el = model.get_element(element_id)
    el.params["material_id"] = material_id
    el.params["material_role"] = role
    # keep list of assignments for multi-material elements
    assigns = list(el.params.get("material_assignments") or [])
    # replace same role
    assigns = [a for a in assigns if a.get("role") != role]
    assigns.append({"role": role, "material_id": material_id})
    el.params["material_assignments"] = assigns
    mat = get_material(material_id)
    return {
        "element_id": element_id,
        "material_id": material_id,
        "material_name": mat.name if mat else material_id,
        "role": role,
    }


def assign_part(
    model: ProjectModel,
    element_id: str,
    part_id: str,
    *,
    qty: float | None = None,
    apply_geometry: bool = False,
) -> dict[str, Any]:
    """Link element to a catalog part type; optional geometry defaults.

    If ``qty`` is omitted, preserves existing ``part_qty`` / ``length_m``
    (so auto_assign does not wipe steel/rebar lengths).
    """
    part = get_part(part_id)
    if not part:
        raise ValidationError("Unknown part_id", part_id=part_id)
    el = model.get_element(element_id)
    el.params["part_id"] = part_id
    if qty is not None:
        el.params["part_qty"] = float(qty)
    elif el.params.get("length_m") is not None and not el.params.get("part_qty"):
        el.params["part_qty"] = float(el.params["length_m"])
    elif "part_qty" not in el.params:
        el.params["part_qty"] = 1.0
    el.type_id = part_id
    if not el.params.get("material_id"):
        el.params["material_id"] = part.primary_material_id
    # instance BOM starts as part BOM copy
    if "bom" not in el.params:
        el.params["bom"] = [line.model_dump() for line in part.resolved_bom()]
    if apply_geometry and part.default_size_mm:
        el.params["size_mm"] = list(part.default_size_mm)
        el.params["shape"] = part.shape
        if part.shape == "cylinder" and "origin_mm" in el.params:
            # keep origin; update polygon from size
            o = el.params["origin_mm"]
            L, D = float(part.default_size_mm[0]), float(part.default_size_mm[1])
            x0, y0 = float(o[0]), float(o[1])
            r = D / 2
            el.params["polygon_mm"] = [
                [x0, y0 - r],
                [x0 + L, y0 - r],
                [x0 + L, y0 + r],
                [x0, y0 + r],
            ]
    return {
        "element_id": element_id,
        "part_id": part_id,
        "part_name": part.name,
        "qty": el.params.get("part_qty"),
        "unit_cost": part_unit_cost(part),
    }


def set_element_bom(
    model: ProjectModel,
    element_id: str,
    bom_lines: list[dict[str, Any]],
) -> dict[str, Any]:
    """Replace instance BOM (list of {material_id, qty, unit, ...})."""
    el = model.get_element(element_id)
    cleaned = []
    for line in bom_lines:
        mid = line.get("material_id")
        if not mid or mid not in MATERIALS:
            raise ValidationError("Invalid BOM material_id", material_id=mid)
        cleaned.append(
            {
                "material_id": mid,
                "qty": float(line.get("qty", 1)),
                "unit": line.get("unit", "ea"),
                "description": line.get("description", ""),
                "volume_m3": line.get("volume_m3"),
                "mass_kg": line.get("mass_kg"),
            }
        )
    el.params["bom"] = cleaned
    return {"element_id": element_id, "bom_lines": len(cleaned)}


def add_bom_line(
    model: ProjectModel,
    element_id: str,
    material_id: str,
    *,
    qty: float = 1.0,
    unit: str = "ea",
    description: str = "",
    mass_kg: float | None = None,
    volume_m3: float | None = None,
) -> dict[str, Any]:
    el = model.get_element(element_id)
    if material_id not in MATERIALS:
        raise ValidationError("Unknown material_id", material_id=material_id)
    bom = list(el.params.get("bom") or [])
    bom.append(
        {
            "material_id": material_id,
            "qty": qty,
            "unit": unit,
            "description": description,
            "mass_kg": mass_kg,
            "volume_m3": volume_m3,
        }
    )
    el.params["bom"] = bom
    return {"element_id": element_id, "bom_lines": len(bom)}


# kind → catalog part for Proto10 / process equipment auto-assign
_KIND_PART: dict[str, str] = {
    "shell": "PT-SEP-SHELL-320",
    "flange": "PT-SEP-FLANGE-380",
    "cartridge": "PT-SEP-CARTRIDGE-ULTEM",
    "magnet": "PT-SEP-MAGNET-N42",
    "yoke": "PT-SEP-YOKE-IRON",
    "pedestal": "PT-SEP-PEDESTAL",
    "separator_vessel_size_b": "PT-VESSEL-SIZE-B",
    "vessel": "PT-VESSEL-SIZE-B",
}


def auto_assign_from_type(model: ProjectModel, element_id: str) -> dict[str, Any]:
    """If element has type_id matching a part, assign part; walls use layer materials."""
    el = model.get_element(element_id)
    actions = []
    if el.type_id and el.type_id in PARTS:
        actions.append(assign_part(model, element_id, el.type_id))
    elif el.params.get("part_id") and el.params["part_id"] in PARTS:
        actions.append(assign_part(model, element_id, str(el.params["part_id"])))
    elif el.category == "wall" and el.type_id:
        from llmbim_core.types_catalog import DEFAULT_WALL_TYPES

        wt = DEFAULT_WALL_TYPES.get(el.type_id)
        if wt and wt.layers:
            # primary = first structural layer material
            primary = wt.layers[0].material
            if primary in MATERIALS:
                actions.append(assign_material(model, element_id, primary))
            # store full layer list as material_assignments
            el.params["material_assignments"] = [
                {
                    "role": layer.function,
                    "material_id": layer.material if layer.material in MATERIALS else primary,
                    "thickness_mm": layer.thickness_mm,
                }
                for layer in wt.layers
            ]
            actions.append({"layers": len(wt.layers)})
    elif el.category == "equipment":
        kind = str(el.params.get("kind") or "")
        if kind in _KIND_PART:
            actions.append(assign_part(model, element_id, _KIND_PART[kind]))
        elif el.name and "vessel" in el.name.lower() and "size" in el.name.lower():
            actions.append(assign_part(model, element_id, "PT-VESSEL-SIZE-B"))
    elif el.category == "door" and not el.params.get("part_id"):
        if el.type_id == "D-HM-36" or (el.params.get("width_mm") or 0) <= 1000:
            if "PT-DOOR-HM-900" in PARTS:
                actions.append(assign_part(model, element_id, "PT-DOOR-HM-900"))
    return {"element_id": element_id, "actions": actions}


def auto_assign_all(model: ProjectModel) -> dict[str, Any]:
    """Run auto_assign_from_type on every element; return counts."""
    results = []
    for el in list(model.elements):
        r = auto_assign_from_type(model, el.id)
        if r.get("actions"):
            results.append(r)
    return {"assigned": len(results), "details": results[:100]}


def place_part(
    model: ProjectModel,
    *,
    level: str,
    part_id: str | None = None,
    origin: tuple[float, float] | list[float] = (0.0, 0.0),
    name: str | None = None,
    qty: float = 1.0,
    length_m: float | None = None,
    kind: str | None = None,
    section: str | None = None,
    bar_size: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """Place any catalog part (toilet, TP dispenser, W10x33, rebar #5, …)."""
    from llmbim_core.ids import new_id
    from llmbim_core.parts_catalog import resolve_part_id

    pid = part_id or resolve_part_id(kind=kind, section=section, bar_size=bar_size)
    if not pid or not get_part(pid):
        raise ValidationError("Unknown part", part_id=part_id, kind=kind, section=section)
    part = get_part(pid)
    assert part is not None
    level_id = model.get_level(level).id
    sp = part.specs or {}
    q = float(length_m if length_m is not None else qty)
    cat = category or (
        "fixture"
        if part.category in ("fixture", "accessory")
        else ("rebar" if part.category == "rebar" else ("steel" if part.category == "structural_steel" else part.category))
    )
    el = Element(
        id=new_id(cat[:3] if len(cat) >= 3 else "prt"),
        category=cat,
        name=name or part.name,
        level_id=level_id,
        type_id=pid,
        params={
            "origin_mm": [float(origin[0]), float(origin[1])],
            "part_id": pid,
            "part_qty": q,
            "material_id": part.primary_material_id,
            "fitting_type": sp.get("fitting_type"),
            "nps": sp.get("nps"),
            "section": sp.get("section"),
            "bar_size": sp.get("bar_size"),
            "system": sp.get("system"),
            "size_mm": list(part.default_size_mm or [100, 100, 100]),
            "shape": part.shape,
            "length_m": length_m,
            "length_mm": (length_m * 1000.0) if length_m is not None else None,
        },
    )
    model.add_element(el)
    assign_part(model, el.id, pid, qty=q)
    return {"element_id": el.id, "part_id": pid, "part_name": part.name, "qty": q}


def place_column(
    model: ProjectModel,
    *,
    level: str,
    origin: tuple[float, float] | list[float] = (0.0, 0.0),
    section: str = "W10x33",
    height_mm: float = 3000.0,
    name: str | None = None,
    material_id: str = "steel_A36",
    rotation_deg: float = 0.0,
) -> dict[str, Any]:
    """Structural steel column (W/HSS section). Vertical, CSI 05 12 00."""
    from llmbim_core.ids import new_id
    from llmbim_core.parts_catalog import get_part, resolve_part_id

    pid = resolve_part_id(section=section) or f"PT-STL-{section.replace('×', 'x')}"
    part = get_part(pid)
    h = float(height_mm)
    if h < 100:
        raise ValidationError("Column height too small", height_mm=height_mm)
    # approximate plan size from section depth if catalog size available
    size = list(part.default_size_mm) if part and part.default_size_mm else [250.0, 250.0, h]
    if len(size) < 3:
        size = [size[0] if size else 250.0, size[1] if len(size) > 1 else 250.0, h]
    else:
        size[2] = h
    # for vertical column, size_mm is plan X, plan Y, height
    depth = float(size[0]) if size[0] > 10 else 250.0
    width = float(size[1]) if len(size) > 1 and size[1] > 10 else depth
    # W-shape presentation dims for glTF I-section (approx AISC; not mill cert)
    sec_u = str(section).upper().replace("×", "x").replace(" ", "")
    sec_dims: dict[str, float] = {}
    if sec_u.startswith("W") and "X" in sec_u:
        try:
            a, b = sec_u[1:].split("X", 1)
            d_in = float(a)
            wt = float(b.split("-")[0])
            d_mm = d_in * 25.4
            bf_mm = max(d_mm * 0.55, d_in * 20.0)
            tf_mm = max(d_mm * 0.045, 8.0) * (1.15 if wt > 40 else 1.0)
            tw_mm = max(d_mm * 0.028, 6.0) * (1.1 if wt > 40 else 1.0)
            sec_dims = {"d_mm": d_mm, "bf_mm": bf_mm, "tf_mm": tf_mm, "tw_mm": tw_mm}
            depth, width = d_mm, bf_mm
        except ValueError:
            sec_dims = {}
    level_id = model.get_level(level).id
    shape = "w_section" if sec_u.startswith("W") else "box"
    el = Element(
        id=new_id("col"),
        category="column",
        name=name or f"Col {section} H={h / 1000:.2f}m",
        level_id=level_id,
        type_id=pid if part else "COLUMN",
        params={
            "origin_mm": [float(origin[0]), float(origin[1])],
            "section": section,
            "section_dims_mm": sec_dims,
            "height_mm": h,
            "length_m": h / 1000.0,
            "length_mm": h,
            "size_mm": [depth, width, h],
            "shape": shape,
            "z0_mm": 0.0,
            "material_id": material_id,
            "part_id": pid if part else None,
            "part_qty": h / 1000.0,
            "rotation_deg": float(rotation_deg),
            "fitting_type": "column",
            "csi_code": "05 12 00",
            "system": "structural_steel",
        },
    )
    model.add_element(el)
    if part:
        try:
            assign_part(model, el.id, pid, qty=h / 1000.0)
        except Exception:  # noqa: BLE001
            pass
    return {
        "element_id": el.id,
        "section": section,
        "height_mm": h,
        "length_m": round(h / 1000.0, 3),
        "part_id": pid if part else None,
    }


def place_beam(
    model: ProjectModel,
    *,
    level: str,
    start: tuple[float, float] | list[float],
    end: tuple[float, float] | list[float],
    section: str = "W12x26",
    name: str | None = None,
    material_id: str = "steel_A36",
    z0_mm: float | None = None,
) -> dict[str, Any]:
    """Structural steel beam along plan start→end. CSI 05 12 00."""
    import math

    from llmbim_core.ids import new_id
    from llmbim_core.parts_catalog import get_part, resolve_part_id

    x0, y0 = float(start[0]), float(start[1])
    x1, y1 = float(end[0]), float(end[1])
    length_mm = math.hypot(x1 - x0, y1 - y0)
    if length_mm < 1:
        raise ValidationError("Beam length too small", start=start, end=end)
    length_m = length_mm / 1000.0
    pid = resolve_part_id(section=section) or f"PT-STL-{section.replace('×', 'x')}"
    part = get_part(pid)
    size = list(part.default_size_mm) if part and part.default_size_mm else [300.0, 150.0, 300.0]
    depth = float(size[0]) if size and size[0] > 10 else 300.0
    width = float(size[1]) if len(size) > 1 and size[1] > 10 else 150.0
    sec_u = str(section).upper().replace("×", "x").replace(" ", "")
    sec_dims: dict[str, float] = {}
    if sec_u.startswith("W") and "X" in sec_u:
        try:
            a, b = sec_u[1:].split("X", 1)
            d_in = float(a)
            wt = float(b.split("-")[0])
            d_mm = d_in * 25.4
            bf_mm = max(d_mm * 0.55, d_in * 20.0)
            tf_mm = max(d_mm * 0.045, 8.0) * (1.15 if wt > 40 else 1.0)
            tw_mm = max(d_mm * 0.028, 6.0) * (1.1 if wt > 40 else 1.0)
            sec_dims = {"d_mm": d_mm, "bf_mm": bf_mm, "tf_mm": tf_mm, "tw_mm": tw_mm}
            depth, width = d_mm, bf_mm
        except ValueError:
            sec_dims = {}
    # top of steel default near ceiling
    z = float(z0_mm) if z0_mm is not None else 3000.0 - depth
    level_id = model.get_level(level).id
    shape = "w_section" if sec_u.startswith("W") else "box"
    el = Element(
        id=new_id("bm"),
        category="beam",
        name=name or f"Beam {section} L={length_m:.2f}m",
        level_id=level_id,
        type_id=pid if part else "BEAM",
        params={
            "start_mm": [x0, y0],
            "end_mm": [x1, y1],
            "origin_mm": [x0, y0],
            "section": section,
            "section_dims_mm": sec_dims,
            "length_mm": length_mm,
            "length_m": length_m,
            "width_mm": width,
            "height_mm": depth,
            "depth_mm": depth,
            "size_mm": [length_mm, width, depth],
            "shape": shape,
            "z0_mm": z,
            "material_id": material_id,
            "part_id": pid if part else None,
            "part_qty": length_m,
            "fitting_type": "beam",
            "csi_code": "05 12 00",
            "system": "structural_steel",
        },
    )
    model.add_element(el)
    if part:
        try:
            assign_part(model, el.id, pid, qty=length_m)
        except Exception:  # noqa: BLE001
            pass
    return {
        "element_id": el.id,
        "section": section,
        "length_m": round(length_m, 3),
        "part_id": pid if part else None,
    }


def place_fitting(
    model: ProjectModel,
    *,
    level: str,
    fitting_type: str,
    nps: str,
    origin: tuple[float, float] | list[float],
    name: str | None = None,
    material: str = "copper",
    qty: float = 1.0,
    system_tag: str = "CW",  # cold water / HW / DWV / FP / process
) -> dict[str, Any]:
    """Create a pipe fitting element (copper / fire black steel / process SS)."""
    from llmbim_core.ids import new_id
    from llmbim_core.parts_catalog import resolve_fitting_part_id

    pid = resolve_fitting_part_id(fitting_type, nps, material=material)
    if not pid:
        raise ValidationError(
            "Unknown fitting",
            fitting_type=fitting_type,
            nps=nps,
            material=material,
        )
    part = get_part(pid)
    assert part is not None
    level_id = model.get_level(level).id
    el = Element(
        id=new_id("fit"),
        category="fitting",
        name=name or part.name,
        level_id=level_id,
        type_id=pid,
        params={
            "origin_mm": [float(origin[0]), float(origin[1])],
            "fitting_type": fitting_type,
            "nps": nps,
            "system": system_tag,
            "material_id": part.primary_material_id,
            "part_id": pid,
            "part_qty": float(qty),
            "size_mm": list(part.default_size_mm or [50, 50, 50]),
            "shape": part.shape,
        },
    )
    model.add_element(el)
    assign_part(model, el.id, pid, qty=qty)
    return {"element_id": el.id, "part_id": pid, "part_name": part.name, "qty": qty}


def place_pipe(
    model: ProjectModel,
    *,
    level: str,
    nps: str,
    start: tuple[float, float] | list[float],
    end: tuple[float, float] | list[float],
    name: str | None = None,
    material: str = "copper",
    system_tag: str = "CW",
    z0_mm: float = 0.0,
) -> dict[str, Any]:
    """Create a straight pipe run (copper / fire / process SS)."""
    import math

    from llmbim_core.ids import new_id
    from llmbim_core.parts_catalog import resolve_fitting_part_id

    pid = resolve_fitting_part_id("pipe", nps, material=material)
    if not pid:
        raise ValidationError("Unknown pipe", nps=nps, material=material)
    part = get_part(pid)
    assert part is not None
    x0, y0 = float(start[0]), float(start[1])
    x1, y1 = float(end[0]), float(end[1])
    length_mm = math.hypot(x1 - x0, y1 - y0)
    length_m = length_mm / 1000.0
    od = float((part.specs or {}).get("od_mm") or 28.6)
    level_id = model.get_level(level).id
    el = Element(
        id=new_id("pip"),
        category="pipe",
        name=name or f"{part.name} L={length_m:.2f}m",
        level_id=level_id,
        type_id=pid,
        params={
            "start_mm": [x0, y0],
            "end_mm": [x1, y1],
            "origin_mm": [x0, y0],
            "length_mm": length_mm,
            "length_m": length_m,
            "nps": nps,
            "system": system_tag,
            "material_id": part.primary_material_id,
            "part_id": pid,
            "part_qty": length_m,  # meters of pipe
            "size_mm": [length_mm, od, od],
            "shape": "cylinder",
            "z0_mm": z0_mm,
            "fitting_type": "pipe",
        },
    )
    model.add_element(el)
    assign_part(model, el.id, pid, qty=length_m)
    return {
        "element_id": el.id,
        "part_id": pid,
        "length_m": round(length_m, 3),
        "nps": nps,
    }


def place_riser(
    model: ProjectModel,
    *,
    level: str,
    nps: str,
    origin: tuple[float, float] | list[float],
    z0_mm: float | None = None,
    z1_mm: float | None = None,
    name: str | None = None,
    material: str = "copper",
    system_tag: str = "CW",
    to_level: str | None = None,
) -> dict[str, Any]:
    """Vertical pipe riser at fixed plan XY from z0_mm → z1_mm (on base level).

    Multi-storey: pass ``to_level`` (e.g. L2) to span from base level elevation to
    the top level elevation. Optional z0_mm/z1_mm offsets relative to each storey.
    """
    from llmbim_core.ids import new_id
    from llmbim_core.parts_catalog import resolve_fitting_part_id

    pid = resolve_fitting_part_id("pipe", nps, material=material)
    if not pid:
        raise ValidationError("Unknown pipe", nps=nps, material=material)
    part = get_part(pid)
    assert part is not None
    x, y = float(origin[0]), float(origin[1])
    base = model.get_level(level)
    if to_level:
        top = model.get_level(to_level)
        # heights relative to base storey elevation
        z0 = float(z0_mm if z0_mm is not None else 0.0)
        span = float(top.elevation_mm) - float(base.elevation_mm)
        z1 = float(z1_mm if z1_mm is not None else span)
        # if z1_mm given with to_level, treat as offset above top elevation
        if z1_mm is not None and to_level:
            z1 = span + float(z1_mm)
        to_level_name = top.name
    else:
        z0 = float(z0_mm if z0_mm is not None else 0.0)
        z1 = float(z1_mm if z1_mm is not None else 3000.0)
        to_level_name = None
    if abs(z1 - z0) < 1:
        raise ValidationError("Riser height too small", z0_mm=z0, z1_mm=z1)
    lo, hi = min(z0, z1), max(z0, z1)
    length_mm = hi - lo
    length_m = length_mm / 1000.0
    od = float((part.specs or {}).get("od_mm") or 28.6)
    level_id = base.id
    el = Element(
        id=new_id("ris"),
        category="pipe",
        name=name or f"{part.name} riser H={length_m:.2f}m",
        level_id=level_id,
        type_id=pid,
        params={
            "origin_mm": [x, y],
            "start_mm": [x, y],
            "end_mm": [x, y],  # plan footprint is a point
            "length_mm": length_mm,
            "length_m": length_m,
            "nps": nps,
            "system": system_tag,
            "material_id": part.primary_material_id,
            "part_id": pid,
            "part_qty": length_m,
            "size_mm": [od, od, length_mm],  # vertical extent in Z
            "shape": "cylinder",
            "vertical": True,
            "z0_mm": lo,
            "z1_mm": hi,
            "fitting_type": "pipe",
            "orientation": "vertical",
            "to_level": to_level_name,
            "base_level": base.name,
        },
    )
    model.add_element(el)
    assign_part(model, el.id, pid, qty=length_m)
    return {
        "element_id": el.id,
        "part_id": pid,
        "length_m": round(length_m, 3),
        "nps": nps,
        "z0_mm": lo,
        "z1_mm": hi,
        "vertical": True,
        "to_level": to_level_name,
        "base_level": base.name,
    }

def place_duct(
    model: ProjectModel,
    *,
    level: str,
    start: tuple[float, float] | list[float],
    end: tuple[float, float] | list[float],
    width_mm: float = 400.0,
    height_mm: float = 250.0,
    name: str | None = None,
    system_tag: str = "SA",
    z0_mm: float = 2700.0,
    material_id: str = "galv_steel",
) -> dict[str, Any]:
    """Rectangular HVAC duct run (coordination envelope). CSI 23 31 00."""
    import math

    from llmbim_core.ids import new_id

    x0, y0 = float(start[0]), float(start[1])
    x1, y1 = float(end[0]), float(end[1])
    length_mm = math.hypot(x1 - x0, y1 - y0)
    if length_mm < 1:
        raise ValidationError("Duct length too small", start=start, end=end)
    length_m = length_mm / 1000.0
    w, h = float(width_mm), float(height_mm)
    # surface area m2 for takeoff (4 sides, open ends)
    area_m2 = 2.0 * (w + h) * length_mm / 1_000_000.0
    level_id = model.get_level(level).id
    pid = "PT-HVAC-DUCT-RECT"
    el = Element(
        id=new_id("duct"),
        category="duct",
        name=name or f"Duct {w:.0f}x{h:.0f} L={length_m:.2f}m",
        level_id=level_id,
        type_id=pid,
        params={
            "start_mm": [x0, y0],
            "end_mm": [x1, y1],
            "origin_mm": [x0, y0],
            "length_mm": length_mm,
            "length_m": length_m,
            "width_mm": w,
            "height_mm": h,
            "system": system_tag,
            "material_id": material_id,
            "part_id": pid,
            "part_qty": round(area_m2, 3),
            "area_m2": round(area_m2, 3),
            "size_mm": [length_mm, w, h],
            "shape": "box",
            "z0_mm": float(z0_mm),
            "fitting_type": "duct",
            "csi_code": "23 31 00",
        },
    )
    model.add_element(el)
    try:
        assign_part(model, el.id, pid, qty=area_m2)
    except Exception:  # noqa: BLE001
        pass
    return {
        "element_id": el.id,
        "part_id": pid,
        "length_m": round(length_m, 3),
        "area_m2": round(area_m2, 3),
        "width_mm": w,
        "height_mm": h,
    }

def place_conduit(
    model: ProjectModel,
    *,
    level: str,
    start: tuple[float, float] | list[float],
    end: tuple[float, float] | list[float],
    trade_size: str = "3/4",
    name: str | None = None,
    system_tag: str = "P",
    z0_mm: float = 2800.0,
    material_id: str = "steel_A36",
) -> dict[str, Any]:
    """Electrical conduit run (EMT/RMC coordination). CSI 26 05 33."""
    import math

    from llmbim_core.ids import new_id

    x0, y0 = float(start[0]), float(start[1])
    x1, y1 = float(end[0]), float(end[1])
    length_mm = math.hypot(x1 - x0, y1 - y0)
    if length_mm < 1:
        raise ValidationError("Conduit length too small", start=start, end=end)
    length_m = length_mm / 1000.0
    # nominal OD mm from trade size (approx EMT)
    od_map = {
        "1/2": 17.9, "3/4": 23.4, "1": 29.5, "1-1/4": 38.4,
        "1-1/2": 44.5, "2": 55.8, "2-1/2": 73.0, "3": 88.9, "4": 114.3,
    }
    od = float(od_map.get(str(trade_size), 23.4))
    level_id = model.get_level(level).id
    el = Element(
        id=new_id("cnd"),
        category="conduit",
        name=name or f"Conduit {trade_size}\" L={length_m:.2f}m",
        level_id=level_id,
        type_id="PT-ELEC-CONDUIT",
        params={
            "start_mm": [x0, y0],
            "end_mm": [x1, y1],
            "origin_mm": [x0, y0],
            "length_mm": length_mm,
            "length_m": length_m,
            "nps": trade_size,
            "trade_size": trade_size,
            "system": system_tag,
            "material_id": material_id,
            "part_id": "PT-ELEC-CONDUIT",
            "part_qty": length_m,
            "size_mm": [length_mm, od, od],
            "shape": "cylinder",
            "z0_mm": float(z0_mm),
            "fitting_type": "conduit",
            "csi_code": "26 05 33",
        },
    )
    model.add_element(el)
    return {
        "element_id": el.id,
        "length_m": round(length_m, 3),
        "trade_size": trade_size,
        "nps": trade_size,
    }


def place_cable_tray(
    model: ProjectModel,
    *,
    level: str,
    start: tuple[float, float] | list[float],
    end: tuple[float, float] | list[float],
    width_mm: float = 300.0,
    height_mm: float = 100.0,
    name: str | None = None,
    system_tag: str = "PWR",
    z0_mm: float = 2900.0,
    material_id: str = "galv_steel",
) -> dict[str, Any]:
    """Cable tray run (ladder/solid bottom coordination). CSI 26 05 36."""
    import math

    from llmbim_core.ids import new_id

    x0, y0 = float(start[0]), float(start[1])
    x1, y1 = float(end[0]), float(end[1])
    length_mm = math.hypot(x1 - x0, y1 - y0)
    if length_mm < 1:
        raise ValidationError("Cable tray length too small", start=start, end=end)
    length_m = length_mm / 1000.0
    w, h = float(width_mm), float(height_mm)
    # takeoff: plan area of tray bottom (m2)
    area_m2 = (w * length_mm) / 1_000_000.0
    level_id = model.get_level(level).id
    pid = "PT-ELEC-CABLE-TRAY"
    el = Element(
        id=new_id("tray"),
        category="cable_tray",
        name=name or f"Cable tray {w:.0f}x{h:.0f} L={length_m:.2f}m",
        level_id=level_id,
        type_id=pid,
        params={
            "start_mm": [x0, y0],
            "end_mm": [x1, y1],
            "origin_mm": [x0, y0],
            "length_mm": length_mm,
            "length_m": length_m,
            "width_mm": w,
            "height_mm": h,
            "system": system_tag,
            "material_id": material_id,
            "part_id": pid,
            "part_qty": round(length_m, 3),
            "area_m2": round(area_m2, 3),
            "size_mm": [length_mm, w, h],
            "shape": "box",
            "z0_mm": float(z0_mm),
            "fitting_type": "cable_tray",
            "csi_code": "26 05 36",
        },
    )
    model.add_element(el)
    try:
        assign_part(model, el.id, pid, qty=length_m)
    except Exception:  # noqa: BLE001
        pass
    return {
        "element_id": el.id,
        "part_id": pid,
        "length_m": round(length_m, 3),
        "area_m2": round(area_m2, 3),
        "width_mm": w,
        "height_mm": h,
    }


def place_wire(
    model: ProjectModel,
    *,
    level: str,
    start: tuple[float, float] | list[float],
    end: tuple[float, float] | list[float],
    diameter_mm: float = 6.0,
    name: str | None = None,
    material_id: str = "copper",
    system_tag: str = "PWR",
    z0_mm: float = 2900.0,
) -> dict[str, Any]:
    """Thin conductor / control wire run (presentation cylinder). CSI 26 05 19."""
    import math

    from llmbim_core.ids import new_id

    x0, y0 = float(start[0]), float(start[1])
    x1, y1 = float(end[0]), float(end[1])
    length_mm = math.hypot(x1 - x0, y1 - y0)
    if length_mm < 1:
        raise ValidationError("Wire length too small", start=start, end=end)
    d = max(float(diameter_mm), 1.0)
    level_id = model.get_level(level).id
    mid = "copper_C12200" if "copper" in str(material_id).lower() else str(material_id)
    el = Element(
        id=new_id("wir"),
        category="wire",
        name=name or f"Wire Ø{d:.0f} L={length_mm / 1000:.2f}m",
        level_id=level_id,
        type_id="PT-ELEC-WIRE",
        params={
            "start_mm": [x0, y0],
            "end_mm": [x1, y1],
            "origin_mm": [x0, y0],
            "length_mm": length_mm,
            "length_m": length_mm / 1000.0,
            "diameter_mm": d,
            "wire_d_mm": d,
            "system": system_tag,
            "material_id": mid,
            "shape": "wire",
            "fitting_type": "wire",
            "z0_mm": float(z0_mm),
            "size_mm": [length_mm, d, d],
            "csi_code": "26 05 19",
        },
    )
    model.add_element(el)
    return {
        "element_id": el.id,
        "length_m": round(length_mm / 1000.0, 3),
        "diameter_mm": d,
    }


def place_coil(
    model: ProjectModel,
    *,
    level: str,
    origin: tuple[float, float] | list[float],
    coil_radius_mm: float = 80.0,
    tube_radius_mm: float = 8.0,
    turns: float = 6.0,
    pitch_mm: float = 24.0,
    name: str | None = None,
    material_id: str = "copper",
    system_tag: str = "PROC",
    z0_mm: float = 1000.0,
    orientation: str = "vertical",
) -> dict[str, Any]:
    """Helical coil / wound conductor (presentation helix). CSI 23 82 16."""
    from llmbim_core.ids import new_id

    x0, y0 = float(origin[0]), float(origin[1])
    level_id = model.get_level(level).id
    cr = max(float(coil_radius_mm), 10.0)
    tr = max(float(tube_radius_mm), 2.0)
    n_turns = max(1.0, float(turns))
    pitch = max(float(pitch_mm), 5.0)
    height = pitch * n_turns
    el = Element(
        id=new_id("coil"),
        category="coil",
        name=name or f"Coil R{cr:.0f}×{n_turns:.0f}t",
        level_id=level_id,
        type_id="PT-MECH-COIL",
        params={
            "origin_mm": [x0, y0],
            "coil_radius_mm": cr,
            "tube_radius_mm": tr,
            "turns": n_turns,
            "pitch_mm": pitch,
            "shape": "coil",
            "fitting_type": "coil",
            "orientation": orientation,
            "axis": orientation,
            "system": system_tag,
            "material_id": material_id,
            "z0_mm": float(z0_mm),
            "size_mm": [cr * 2, cr * 2, height],
            "csi_code": "23 82 16",
        },
    )
    model.add_element(el)
    return {
        "element_id": el.id,
        "coil_radius_mm": cr,
        "turns": n_turns,
        "height_mm": height,
    }


def place_bolt(
    model: ProjectModel,
    *,
    level: str,
    origin: tuple[float, float] | list[float],
    shank_d_mm: float = 20.0,
    shank_len_mm: float = 60.0,
    grade: str = "A325",
    name: str | None = None,
    z0_mm: float = 0.0,
    orientation: str = "vertical",
) -> dict[str, Any]:
    """Structural bolt (hex head + shank presentation). CSI 05 12 23."""
    from llmbim_core.ids import new_id

    x0, y0 = float(origin[0]), float(origin[1])
    level_id = model.get_level(level).id
    d = max(float(shank_d_mm), 4.0)
    L = max(float(shank_len_mm), 10.0)
    mid = "steel_A490" if "490" in str(grade).upper() else "steel_A325"
    el = Element(
        id=new_id("blt"),
        category="bolt",
        name=name or f"Bolt {grade} Ø{d:.0f}×{L:.0f}",
        level_id=level_id,
        type_id=f"PT-BOLT-{grade}",
        params={
            "origin_mm": [x0, y0],
            "shank_d_mm": d,
            "diameter_mm": d,
            "shank_len_mm": L,
            "length_mm": L,
            "head_af_mm": d * 1.5,
            "head_h_mm": d * 0.7,
            "grade": grade,
            "shape": "bolt",
            "fitting_type": "bolt",
            "orientation": orientation,
            "material_id": mid,
            "z0_mm": float(z0_mm),
            "size_mm": [d * 1.5, d * 1.5, L + d],
            "csi_code": "05 12 23",
            "part_qty": 1.0,
        },
    )
    model.add_element(el)
    return {"element_id": el.id, "grade": grade, "shank_d_mm": d, "shank_len_mm": L}


def place_flange(
    model: ProjectModel,
    *,
    level: str,
    origin: tuple[float, float] | list[float],
    od_mm: float = 150.0,
    thickness_mm: float = 18.0,
    name: str | None = None,
    material_id: str = "steel_A36",
    system_tag: str = "PROC",
    z0_mm: float = 1000.0,
) -> dict[str, Any]:
    """Joined material flange / ring section at a joint. CSI 40 05 13."""
    from llmbim_core.ids import new_id

    x0, y0 = float(origin[0]), float(origin[1])
    level_id = model.get_level(level).id
    od = max(float(od_mm), 20.0)
    th = max(float(thickness_mm), 4.0)
    el = Element(
        id=new_id("flg"),
        category="flange",
        name=name or f"Flange Ø{od:.0f}",
        level_id=level_id,
        type_id="PT-FLANGE",
        params={
            "origin_mm": [x0, y0],
            "od_mm": od,
            "diameter_mm": od,
            "thickness_mm": th,
            "shape": "flange",
            "fitting_type": "flange",
            "system": system_tag,
            "material_id": material_id,
            "z0_mm": float(z0_mm),
            "size_mm": [th, od, od],
            "csi_code": "40 05 13",
        },
    )
    model.add_element(el)
    return {"element_id": el.id, "od_mm": od, "thickness_mm": th}
