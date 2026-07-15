"""Simple schedule exporters (CSV / JSON) with CSI + location locators."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from llmbim_core.model import ProjectModel


def _annotate_csi(model: ProjectModel, el, row: dict[str, Any]) -> dict[str, Any]:
    """Attach MasterFormat CSI + level/XY/Z locator to a schedule row."""
    try:
        from llmbim_core.csi import csi_for_element

        info = csi_for_element(model, el)
        row["csi_code"] = info.get("csi_code")
        row["csi_number"] = info.get("csi_number")
        row["csi_section_name"] = info.get("csi_section_name")
        row["csi_instance"] = info.get("csi_instance")
        row["locator"] = info.get("locator")
        row["level"] = info.get("level")
        row["room"] = info.get("room")
        row["x_mm"] = info.get("x_mm")
        row["y_mm"] = info.get("y_mm")
        row["z_mm"] = info.get("z_mm")
        row["height_mm"] = info.get("height_mm") or row.get("height_mm")
        row["nps"] = info.get("nps") or row.get("nps")
    except Exception:  # noqa: BLE001
        pass
    return row


def schedule_rows(model: ProjectModel, kind: str) -> list[dict[str, Any]]:
    kind = kind.lower()
    if kind == "door":
        return [
            _annotate_csi(
                model,
                el,
                {
                    "id": el.id,
                    "name": el.name,
                    "host_id": el.host_id,
                    "width_mm": el.params.get("width_mm"),
                    "height_mm": el.params.get("height_mm"),
                    "type_id": el.type_id,
                },
            )
            for el in model.query(category="door")
        ]
    if kind == "window":
        return [
            _annotate_csi(
                model,
                el,
                {
                    "id": el.id,
                    "name": el.name,
                    "host_id": el.host_id,
                    "width_mm": el.params.get("width_mm"),
                    "height_mm": el.params.get("height_mm"),
                    "sill_mm": el.params.get("sill_mm"),
                    "type_id": el.type_id,
                },
            )
            for el in model.query(category="window")
        ]
    if kind in {"room", "zone", "area", "areas"}:
        # Zone / area schedule: rooms with level name, clear height, volume estimate
        level_names = {lv.id: lv.name for lv in model.levels}
        rows = []
        for el in model.query(category="room"):
            area_mm2 = el.params.get("area_mm2")
            area_m2 = (float(area_mm2) / 1e6) if area_mm2 is not None else None
            h = el.params.get("height_mm") or el.params.get("ceiling_height_mm")
            vol = None
            if area_m2 is not None and h is not None:
                vol = round(area_m2 * (float(h) / 1000.0), 3)
            rows.append(
                {
                    "id": el.id,
                    "name": el.name,
                    "level": level_names.get(el.level_id or "", el.level_id),
                    "level_id": el.level_id,
                    "area_mm2": area_mm2,
                    "area_m2": round(area_m2, 3) if area_m2 is not None else None,
                    "height_mm": h,
                    "ceiling_height_mm": el.params.get("ceiling_height_mm")
                    or el.params.get("height_mm"),
                    "volume_m3": vol,
                    "phase": el.params.get("phase", "new"),
                }
            )
        # optional assembly zones (kind=zone)
        if kind in {"zone", "area", "areas"}:
            for a in model.assemblies:
                if (a.kind or "").lower() not in {"zone", "area", "group"}:
                    continue
                # sum room areas linked to assembly if any
                room_ids = set(a.element_ids)
                linked = [r for r in rows if r["id"] in room_ids]
                if not linked and a.kind != "zone":
                    continue
                if linked:
                    rows.append(
                        {
                            "id": a.id,
                            "name": a.name,
                            "level": linked[0].get("level"),
                            "level_id": linked[0].get("level_id"),
                            "area_mm2": sum(float(x["area_mm2"] or 0) for x in linked) or None,
                            "area_m2": round(sum(float(x["area_m2"] or 0) for x in linked), 3),
                            "height_mm": linked[0].get("height_mm"),
                            "ceiling_height_mm": linked[0].get("ceiling_height_mm"),
                            "volume_m3": round(sum(float(x["volume_m3"] or 0) for x in linked), 3)
                            if any(x.get("volume_m3") is not None for x in linked)
                            else None,
                            "phase": "new",
                            "assembly_kind": a.kind,
                            "room_count": len(linked),
                        }
                    )
        return rows
    if kind == "wall":
        return [
            _annotate_csi(
                model,
                el,
                {
                    "id": el.id,
                    "name": el.name,
                    "length_mm": el.params.get("length_mm"),
                    "thickness_mm": el.params.get("thickness_mm"),
                    "height_mm": el.params.get("height_mm"),
                    "type_id": el.type_id,
                },
            )
            for el in model.query(category="wall")
        ]
    if kind in {"equipment", "equip"}:
        return [
            _annotate_csi(
                model,
                el,
                {
                    "id": el.id,
                    "name": el.name,
                    "kind": el.params.get("kind"),
                    "shape": el.params.get("shape", "box"),
                    "size_mm": el.params.get("size_mm"),
                    "z0_mm": el.params.get("z0_mm"),
                    "part_id": el.params.get("part_id"),
                    "material_id": el.params.get("material_id"),
                },
            )
            for el in model.query(category="equipment")
        ]
    if kind in {"fitting", "fittings"}:
        return [
            _annotate_csi(
                model,
                el,
                {
                    "id": el.id,
                    "name": el.name,
                    "fitting_type": el.params.get("fitting_type"),
                    "nps": el.params.get("nps"),
                    "part_id": el.params.get("part_id") or el.type_id,
                    "material_id": el.params.get("material_id"),
                    "qty": el.params.get("part_qty", 1),
                    "system": el.params.get("system"),
                },
            )
            for el in model.elements
            if el.category in {"fitting", "fittings"}
            or (el.params.get("fitting_type") and el.params.get("fitting_type") != "pipe")
        ]
    if kind in {"pipe", "pipes", "plumbing_pipe"}:
        return [
            _annotate_csi(
                model,
                el,
                {
                    "id": el.id,
                    "name": el.name,
                    "nps": el.params.get("nps"),
                    "length_m": el.params.get("length_m"),
                    "length_mm": el.params.get("length_mm"),
                    "part_id": el.params.get("part_id") or el.type_id,
                    "material_id": el.params.get("material_id"),
                    "system": el.params.get("system"),
                    "vertical": el.params.get("vertical"),
                    "z0_mm": el.params.get("z0_mm"),
                    "z1_mm": el.params.get("z1_mm"),
                },
            )
            for el in model.elements
            if el.category in {"pipe", "plumbing_pipe"}
            or el.params.get("fitting_type") == "pipe"
        ]
    if kind in {"part", "parts"}:
        from llmbim_core.material_lists import part_assignment_list

        rows = part_assignment_list(model)
        # enrich with CSI from element when possible
        out = []
        for r in rows:
            eid = r.get("element_id")
            if eid:
                try:
                    el = model.get_element(str(eid))
                    out.append(_annotate_csi(model, el, dict(r)))
                    continue
                except Exception:  # noqa: BLE001
                    pass
            out.append(r)
        return out
    if kind in {"material", "materials"}:
        from llmbim_core.material_lists import material_assignment_list

        return material_assignment_list(model)
    if kind in {"csi", "locator", "locators"}:
        from llmbim_core.csi import csi_instance_schedule

        return csi_instance_schedule(model)
    raise ValueError(f"Unknown schedule kind: {kind}")


def export_schedule_csv(model: ProjectModel, kind: str, path: str | Path) -> None:
    rows = schedule_rows(model, kind)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("", encoding="utf-8")
        return
    # flatten list/dict cells for CSV
    flat = []
    keys: list[str] = []
    for r in rows:
        fr = {}
        for k, v in r.items():
            if isinstance(v, (list, dict)):
                fr[k] = json.dumps(v, default=str)
            else:
                fr[k] = v
            if k not in keys:
                keys.append(k)
        flat.append(fr)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(flat)


def export_schedule_json(model: ProjectModel, kind: str, path: str | Path) -> None:
    rows = schedule_rows(model, kind)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
