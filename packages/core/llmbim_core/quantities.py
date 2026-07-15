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

    rows: list[dict[str, Any]] = []

    for el in model.query(category="wall"):
        tid = el.type_id or "W-GENERIC-200"
        wt = DEFAULT_WALL_TYPES.get(tid)
        area = wall_area_m2(el)
        vol = wall_volume_m3(el)
        cost = 0.0
        materials = []
        if wt:
            for layer in wt.layers:
                layer_vol = area * (layer.thickness_mm / 1000.0)
                layer_cost = layer_vol * layer.unit_cost_per_m3
                cost += layer_cost
                materials.append(
                    {
                        "material": layer.material,
                        "thickness_mm": layer.thickness_mm,
                        "volume_m3": round(layer_vol, 4),
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

    for el in model.query(category="equipment"):
        vol = equipment_volume_m3(el)
        rows.append(
            {
                "category": "equipment",
                "id": el.id,
                "name": el.name,
                "type_id": el.params.get("kind", ""),
                "type_name": el.params.get("shape", "box"),
                "qty": 1,
                "unit": "ea",
                "secondary_qty": round(vol, 5),
                "secondary_unit": "envelope_m3",
                "est_cost": 0,
                "phase": el.params.get("phase", "new"),
                "materials": [],
            }
        )

    return annotate_boq_with_csi(rows)


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
