"""Fabrication parts: feature-tree BREP + GD&T (agent-authored).

Solids are rebuilt by ``llmbim_geometry.fab_brep`` (CadQuery/OCP) on export.
The model stores only parametric features + GD&T — fully LLM-editable, undo-friendly.
"""

from __future__ import annotations

from typing import Any

from llmbim_core.errors import NotFoundError, ValidationError
from llmbim_core.ids import new_id
from llmbim_core.model import Element, ProjectModel


def create_fab_part(
    model: ProjectModel,
    *,
    name: str = "FabPart",
    material_id: str = "steel_A36",
    level: str | None = None,
    origin_mm: list[float] | tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> dict[str, Any]:
    """Create empty fab part with feature tree + GD&T slots."""
    level_id = model.get_level(level).id if level else (model.levels[0].id if model.levels else None)
    el = Element(
        id=new_id("fab"),
        category="fab_part",
        name=name,
        level_id=level_id,
        type_id="FAB-BREP",
        params={
            "origin_mm": [float(origin_mm[0]), float(origin_mm[1]), float(origin_mm[2] if len(origin_mm) > 2 else 0)],
            "material_id": material_id,
            "features": [],
            "gdt": [],
            "fidelity": "brep_cadquery",
            "shape": "feature_tree",
            "csi_code": "05 05 23",  # metal fabrications / misc metals proxy
        },
    )
    model.add_element(el)
    return {"element_id": el.id, "name": name, "fidelity": "brep_cadquery"}


def _fab(model: ProjectModel, element_id: str) -> Element:
    el = model.get_element(element_id)
    if el.category != "fab_part":
        raise ValidationError("Not a fab_part", element_id=element_id, category=el.category)
    el.params.setdefault("features", [])
    el.params.setdefault("gdt", [])
    return el


def fab_add_feature(model: ProjectModel, element_id: str, feature: dict[str, Any]) -> dict[str, Any]:
    el = _fab(model, element_id)
    op = str(feature.get("op") or "").lower()
    if not op:
        raise ValidationError("feature.op required")
    feats: list = el.params["features"]
    feats.append(dict(feature))
    el.params["features"] = feats
    return {"element_id": element_id, "feature_index": len(feats) - 1, "op": op, "n_features": len(feats)}


def fab_box(
    model: ProjectModel,
    element_id: str,
    *,
    size_mm: list[float] | tuple[float, float, float],
    origin_mm: list[float] | tuple[float, float, float] = (0, 0, 0),
) -> dict[str, Any]:
    return fab_add_feature(
        model,
        element_id,
        {"op": "box", "size_mm": [float(x) for x in size_mm], "origin_mm": [float(x) for x in origin_mm]},
    )


def fab_cylinder(
    model: ProjectModel,
    element_id: str,
    *,
    diameter_mm: float,
    height_mm: float,
    origin_mm: list[float] | tuple[float, float, float] = (0, 0, 0),
    axis: str = "z",
) -> dict[str, Any]:
    return fab_add_feature(
        model,
        element_id,
        {
            "op": "cylinder",
            "diameter_mm": float(diameter_mm),
            "height_mm": float(height_mm),
            "origin_mm": [float(x) for x in origin_mm],
            "axis": axis,
        },
    )


def fab_hole(
    model: ProjectModel,
    element_id: str,
    *,
    diameter_mm: float,
    depth_mm: float | None = None,
    origin_mm: list[float] | tuple[float, float, float],
    direction: str = "down",
) -> dict[str, Any]:
    feat: dict[str, Any] = {
        "op": "hole",
        "diameter_mm": float(diameter_mm),
        "origin_mm": [float(x) for x in origin_mm],
        "direction": direction,
    }
    if depth_mm is not None:
        feat["depth_mm"] = float(depth_mm)
    return fab_add_feature(model, element_id, feat)


def fab_fillet(
    model: ProjectModel,
    element_id: str,
    *,
    radius_mm: float,
    selector: str = "|Z",
) -> dict[str, Any]:
    """Ease edges (fillet). selector e.g. |Z, all, >Z."""
    return fab_add_feature(
        model,
        element_id,
        {"op": "fillet", "radius_mm": float(radius_mm), "selector": selector},
    )


def fab_chamfer(
    model: ProjectModel,
    element_id: str,
    *,
    distance_mm: float,
    selector: str = ">Z",
) -> dict[str, Any]:
    return fab_add_feature(
        model,
        element_id,
        {"op": "chamfer", "distance_mm": float(distance_mm), "selector": selector},
    )


def fab_thread(
    model: ProjectModel,
    element_id: str,
    *,
    designation: str = "M10x1.5",
    length_mm: float = 20.0,
    origin_mm: list[float] | tuple[float, float, float] = (0, 0, 0),
    internal: bool = False,
    pitch_mm: float | None = None,
    diameter_mm: float | None = None,
) -> dict[str, Any]:
    """Machine thread (ISO metric or recorded imperial designation)."""
    feat: dict[str, Any] = {
        "op": "thread",
        "designation": designation,
        "length_mm": float(length_mm),
        "origin_mm": [float(x) for x in origin_mm],
        "internal": bool(internal),
    }
    if pitch_mm is not None:
        feat["pitch_mm"] = float(pitch_mm)
    if diameter_mm is not None:
        feat["diameter_mm"] = float(diameter_mm)
    return fab_add_feature(model, element_id, feat)


def fab_cut_box(
    model: ProjectModel,
    element_id: str,
    *,
    size_mm: list[float] | tuple[float, float, float],
    origin_mm: list[float] | tuple[float, float, float],
) -> dict[str, Any]:
    return fab_add_feature(
        model,
        element_id,
        {
            "op": "cut_box",
            "size_mm": [float(x) for x in size_mm],
            "origin_mm": [float(x) for x in origin_mm],
        },
    )


def gdt_add_datum(
    model: ProjectModel,
    element_id: str,
    *,
    label: str,
    face: str = "bottom",
    note: str = "",
) -> dict[str, Any]:
    """GD&T datum feature (A/B/C…)."""
    el = _fab(model, element_id)
    lab = str(label).strip().upper()[:2]
    if not lab:
        raise ValidationError("datum label required")
    entry = {"kind": "datum", "label": lab, "face": face, "note": note}
    el.params["gdt"].append(entry)
    return {"element_id": element_id, "gdt": entry}


def gdt_add_fcf(
    model: ProjectModel,
    element_id: str,
    *,
    symbol: str,
    tolerance: float,
    datums: list[str] | None = None,
    diameter: bool = False,
    zone: str = "",
    note: str = "",
    applies_to: str = "",
) -> dict[str, Any]:
    """Feature control frame (position, flatness, perpendicularity, …).

    symbol: position|flatness|perpendicularity|parallelism|circularity|
            cylindricity|profile|runout|total_runout|straightness|angularity|concentricity
    """
    el = _fab(model, element_id)
    sym = str(symbol).lower().strip()
    allowed = {
        "position",
        "flatness",
        "perpendicularity",
        "parallelism",
        "circularity",
        "cylindricity",
        "profile",
        "profile_surface",
        "runout",
        "total_runout",
        "straightness",
        "angularity",
        "concentricity",
        "symmetry",
    }
    if sym not in allowed:
        raise ValidationError("unknown GD&T symbol", symbol=symbol, allowed=sorted(allowed))
    entry = {
        "kind": "fcf",
        "symbol": sym,
        "tolerance": float(tolerance),
        "datums": [str(d).upper() for d in (datums or [])],
        "diameter": bool(diameter),
        "zone": zone,
        "note": note,
        "applies_to": applies_to,
    }
    el.params["gdt"].append(entry)
    return {"element_id": element_id, "gdt": entry}


def gdt_add_size(
    model: ProjectModel,
    element_id: str,
    *,
    dimension: str,
    nominal: float,
    tol_plus: float,
    tol_minus: float | None = None,
    unit: str = "mm",
    note: str = "",
) -> dict[str, Any]:
    """Plus/minus or limit size dimension (e.g. Ø10.00 +0.05/−0.00)."""
    el = _fab(model, element_id)
    tm = float(tol_minus) if tol_minus is not None else float(tol_plus)
    entry = {
        "kind": "size",
        "dimension": dimension,
        "nominal": float(nominal),
        "tol_plus": float(tol_plus),
        "tol_minus": tm,
        "unit": unit,
        "note": note,
    }
    el.params["gdt"].append(entry)
    return {"element_id": element_id, "gdt": entry}


def fab_features(model: ProjectModel, element_id: str) -> list[dict[str, Any]]:
    return list(_fab(model, element_id).params.get("features") or [])


def fab_gdt(model: ProjectModel, element_id: str) -> list[dict[str, Any]]:
    return list(_fab(model, element_id).params.get("gdt") or [])


def export_fab_part_step(model: ProjectModel, element_id: str, path: str) -> dict[str, Any]:
    from pathlib import Path

    from llmbim_geometry.fab_brep import export_fab_step, solid_volume_mm3

    el = _fab(model, element_id)
    feats = list(el.params.get("features") or [])
    if not feats:
        raise ValidationError("fab_part has no features", element_id=element_id)
    out = export_fab_step(feats, path)
    vol = solid_volume_mm3(feats)
    el.params["volume_mm3"] = vol
    el.params["step_path"] = str(Path(path).as_posix())
    return {
        "element_id": element_id,
        "path": str(out),
        "volume_mm3": vol,
        "n_features": len(feats),
        "n_gdt": len(el.params.get("gdt") or []),
        "fidelity": "brep_cadquery",
    }


def validate_fab_part(model: ProjectModel, element_id: str) -> dict[str, Any]:
    """Rebuild solid to prove feature tree is valid BREP."""
    from llmbim_geometry.fab_brep import HAS_CADQUERY, FabBrepError, solid_volume_mm3

    el = _fab(model, element_id)
    feats = list(el.params.get("features") or [])
    if not HAS_CADQUERY:
        return {"ok": False, "error": "cadquery_not_installed", "element_id": element_id}
    try:
        vol = solid_volume_mm3(feats)
        el.params["volume_mm3"] = vol
        return {"ok": True, "element_id": element_id, "volume_mm3": vol, "n_features": len(feats)}
    except FabBrepError as exc:
        return {"ok": False, "element_id": element_id, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "element_id": element_id, "error": str(exc)}
