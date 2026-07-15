"""Simple schedule exporters (CSV / JSON)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from llmbim_core.model import ProjectModel


def schedule_rows(model: ProjectModel, kind: str) -> list[dict[str, Any]]:
    kind = kind.lower()
    if kind == "door":
        return [
            {
                "id": el.id,
                "name": el.name,
                "host_id": el.host_id,
                "width_mm": el.params.get("width_mm"),
                "height_mm": el.params.get("height_mm"),
            }
            for el in model.query(category="door")
        ]
    if kind == "window":
        return [
            {
                "id": el.id,
                "name": el.name,
                "host_id": el.host_id,
                "width_mm": el.params.get("width_mm"),
                "height_mm": el.params.get("height_mm"),
                "sill_mm": el.params.get("sill_mm"),
            }
            for el in model.query(category="window")
        ]
    if kind == "room":
        return [
            {
                "id": el.id,
                "name": el.name,
                "area_mm2": el.params.get("area_mm2"),
                "area_m2": (float(el.params["area_mm2"]) / 1e6)
                if el.params.get("area_mm2") is not None
                else None,
            }
            for el in model.query(category="room")
        ]
    if kind == "wall":
        return [
            {
                "id": el.id,
                "name": el.name,
                "length_mm": el.params.get("length_mm"),
                "thickness_mm": el.params.get("thickness_mm"),
                "height_mm": el.params.get("height_mm"),
            }
            for el in model.query(category="wall")
        ]
    if kind in {"equipment", "equip"}:
        return [
            {
                "id": el.id,
                "name": el.name,
                "kind": el.params.get("kind"),
                "shape": el.params.get("shape", "box"),
                "size_mm": el.params.get("size_mm"),
                "z0_mm": el.params.get("z0_mm"),
                "part_id": el.params.get("part_id"),
                "material_id": el.params.get("material_id"),
            }
            for el in model.query(category="equipment")
        ]
    if kind in {"fitting", "fittings"}:
        return [
            {
                "id": el.id,
                "name": el.name,
                "fitting_type": el.params.get("fitting_type"),
                "nps": el.params.get("nps"),
                "part_id": el.params.get("part_id") or el.type_id,
                "material_id": el.params.get("material_id"),
                "qty": el.params.get("part_qty", 1),
                "system": el.params.get("system"),
            }
            for el in model.elements
            if el.category in {"fitting", "fittings"}
            or (el.params.get("fitting_type") and el.params.get("fitting_type") != "pipe")
        ]
    if kind in {"pipe", "pipes", "plumbing_pipe"}:
        return [
            {
                "id": el.id,
                "name": el.name,
                "nps": el.params.get("nps"),
                "length_m": el.params.get("length_m"),
                "length_mm": el.params.get("length_mm"),
                "part_id": el.params.get("part_id") or el.type_id,
                "material_id": el.params.get("material_id"),
                "system": el.params.get("system"),
            }
            for el in model.elements
            if el.category in {"pipe", "plumbing_pipe"}
            or el.params.get("fitting_type") == "pipe"
        ]
    if kind in {"part", "parts"}:
        from llmbim_core.material_lists import part_assignment_list

        return part_assignment_list(model)
    if kind in {"material", "materials"}:
        from llmbim_core.material_lists import material_assignment_list

        return material_assignment_list(model)
    raise ValueError(f"Unknown schedule kind: {kind}")


def export_schedule_csv(model: ProjectModel, kind: str, path: str | Path) -> None:
    rows = schedule_rows(model, kind)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("", encoding="utf-8")
        return
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def export_schedule_json(model: ProjectModel, kind: str, path: str | Path) -> None:
    rows = schedule_rows(model, kind)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
