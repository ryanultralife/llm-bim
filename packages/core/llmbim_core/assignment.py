"""Assign materials, parts, and BOM lines to model elements."""

from __future__ import annotations

from typing import Any

from llmbim_core.errors import ValidationError
from llmbim_core.materials import MATERIALS, get_material
from llmbim_core.model import Element, ProjectModel
from llmbim_core.parts_catalog import PARTS, get_part, part_unit_cost  # noqa: F401 — PARTS used in auto_assign


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
    qty: float = 1.0,
    apply_geometry: bool = False,
) -> dict[str, Any]:
    """Link element to a catalog part type; optional geometry defaults."""
    part = get_part(part_id)
    if not part:
        raise ValidationError("Unknown part_id", part_id=part_id)
    el = model.get_element(element_id)
    el.params["part_id"] = part_id
    el.params["part_qty"] = float(qty)
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
        "qty": qty,
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
    system_tag: str = "CW",  # cold water / HW / DWV
) -> dict[str, Any]:
    """Create a plumbing fitting element linked to catalog part."""
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
    """Create a straight pipe run (plan 2D) with length and catalog part."""
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
