"""Quantity takeoff / BOQ for builders."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from llmbim_core.model import ProjectModel
from llmbim_core.types_catalog import DEFAULT_DOOR_TYPES, DEFAULT_WALL_TYPES, DEFAULT_WINDOW_TYPES


def _wall_length_m(el) -> float:
    return float(el.params.get("length_mm") or 0) / 1000.0


def _wall_height_m(el) -> float:
    return float(el.params.get("height_mm") or 0) / 1000.0


def _wall_thickness_m(el) -> float:
    return float(el.params.get("thickness_mm") or 200) / 1000.0


def wall_area_m2(el) -> float:
    return _wall_length_m(el) * _wall_height_m(el)


def wall_volume_m3(el) -> float:
    return wall_area_m2(el) * _wall_thickness_m(el)


def slab_area_m2(el) -> float:
    area_mm2 = float(el.params.get("area_mm2") or 0)
    return area_mm2 / 1e6


def equipment_volume_m3(el) -> float:
    try:
        s = el.params["size_mm"]
        return (float(s[0]) * float(s[1]) * float(s[2])) / 1e9
    except (KeyError, TypeError, ValueError, IndexError):
        return 0.0


def compute_boq(model: ProjectModel) -> list[dict[str, Any]]:
    """Bill of quantities with optional catalog costs + CSI codes."""
    from llmbim_core.csi import annotate_boq_with_csi, boq_by_csi_division
    from llmbim_core.parts_catalog import get_part, part_unit_cost

    rows: list[dict[str, Any]] = []

    for el in model.query(category="wall"):
        tid = el.type_id or "W-GENERIC-200"
        wt = DEFAULT_WALL_TYPES.get(tid)
        area = wall_area_m2(el)
        vol = wall_volume_m3(el)
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
                "secondary_qty": round(vol, 4),
                "secondary_unit": "m3",
                "est_cost": round(cost, 2),
                "phase": el.params.get("phase", "new"),
                "materials": materials,
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
        wt = DEFAULT_WINDOW_TYPES.get(tid)
        cost = wt.unit_cost if wt else 800.0
        rows.append(
            {
                "category": "window",
                "id": el.id,
                "name": el.name,
                "type_id": tid,
                "type_name": wt.name if wt else "",
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
        if el.category != "column" and el.params.get("fitting_type") != "column":
            continue
        length_m = float(el.params.get("length_m") or 0)
        if not length_m and el.params.get("height_mm"):
            length_m = float(el.params["height_mm"]) / 1000.0
        pid = el.params.get("part_id") or el.type_id
        part = get_part(str(pid)) if pid else None
        unit_cost = part_unit_cost(part) if part else 45.0
        rows.append(
            {
                "category": "column",
                "id": el.id,
                "name": el.name,
                "type_id": str(pid or el.params.get("section") or "COLUMN"),
                "type_name": part.name if part else str(el.params.get("section") or "column"),
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

    def _qty_and_unit(el, part) -> tuple[float, str]:
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
            secondary = (
                el.params.get("section")
                or (part.specs or {}).get("section")
                or el.params.get("bar_size")
                or (part.specs or {}).get("bar_size")
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

    return annotate_boq_with_csi(rows, model=model)


def boq_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from llmbim_core.csi import boq_by_csi_division

    by_cat: dict[str, float] = {}
    total = 0.0
    for r in rows:
        c = float(r.get("est_cost") or 0)
        total += c
        by_cat[r["category"]] = by_cat.get(r["category"], 0.0) + c
    return {
        "line_items": len(rows),
        "est_cost_total": round(total, 2),
        "est_cost_by_category": {k: round(v, 2) for k, v in by_cat.items()},
        "est_cost_by_csi_division": boq_by_csi_division(rows),
        "currency_note": "ENGINEERING ESTIMATE unit costs — not a bid",
    }


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
    payload = {"summary": boq_summary(rows), "lines": rows}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return p
