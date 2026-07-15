"""Generate material lists, part lists, fitting takeoffs, and exploded BOMs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from llmbim_core.materials import MATERIALS, get_material, material_cost, material_mass_kg
from llmbim_core.model import ProjectModel
from llmbim_core.parts_catalog import PARTS, explode_part_bom, get_part, part_unit_cost
from llmbim_core.quantities import slab_area_m2, wall_area_m2, wall_volume_m3


def material_assignment_list(model: ProjectModel) -> list[dict[str, Any]]:
    """Per-element material assignment schedule."""
    rows = []
    for el in model.elements:
        mid = el.params.get("material_id")
        assigns = el.params.get("material_assignments") or []
        if mid and not assigns:
            assigns = [{"role": "primary", "material_id": mid}]
        if not assigns:
            continue
        for a in assigns:
            mat = get_material(str(a.get("material_id", "")))
            rows.append(
                {
                    "element_id": el.id,
                    "element_name": el.name,
                    "category": el.category,
                    "role": a.get("role", "primary"),
                    "material_id": a.get("material_id"),
                    "material_name": mat.name if mat else a.get("material_id"),
                    "thickness_mm": a.get("thickness_mm"),
                    "part_id": el.params.get("part_id"),
                }
            )
    return rows


def part_assignment_list(model: ProjectModel) -> list[dict[str, Any]]:
    """Per-element part type assignment."""
    rows = []
    for el in model.elements:
        pid = el.params.get("part_id") or (
            el.type_id if el.type_id and el.type_id in PARTS else None
        )
        if not pid:
            continue
        part = get_part(str(pid))
        qty = float(el.params.get("part_qty") or 1)
        rows.append(
            {
                "element_id": el.id,
                "element_name": el.name,
                "category": el.category,
                "part_id": pid,
                "part_name": part.name if part else pid,
                "qty": qty,
                "unit": "ea",
                "primary_material_id": part.primary_material_id if part else None,
                "unit_cost": part_unit_cost(part) if part else 0,
                "est_cost": (part_unit_cost(part) if part else 0) * qty,
                "csi_code": part.csi_code if part else "",
                "manufacturer": part.manufacturer if part else "",
            }
        )
    return rows


def exploded_material_bom(model: ProjectModel) -> list[dict[str, Any]]:
    """Full material takeoff: wall layers + element BOM + part BOM explosion."""
    rows: list[dict[str, Any]] = []

    # Walls by type layers × area
    from llmbim_core.types_catalog import DEFAULT_WALL_TYPES

    for el in model.query(category="wall"):
        area = wall_area_m2(el)
        tid = el.type_id or ""
        wt = DEFAULT_WALL_TYPES.get(tid)
        if wt:
            for layer in wt.layers:
                vol = area * (layer.thickness_mm / 1000.0)
                mid = layer.material
                # map legacy names
                if mid not in MATERIALS and mid == "reinforced_concrete":
                    mid = "concrete_4000psi"
                if mid not in MATERIALS and mid == "SS316L_liner":
                    mid = "ss316L"
                if mid not in MATERIALS and mid == "metal_stud":
                    mid = "steel_A36"
                mat = get_material(mid)
                rows.append(
                    {
                        "source": "wall_layer",
                        "element_id": el.id,
                        "element_name": el.name,
                        "material_id": mid,
                        "material_name": mat.name if mat else mid,
                        "qty": round(vol, 6),
                        "unit": "m3",
                        "volume_m3": round(vol, 6),
                        "mass_kg": round(material_mass_kg(mid, vol), 3),
                        "est_cost": round(material_cost(mid, vol), 2),
                        "csi_hint": mat.csi_hint if mat else "",
                    }
                )
        else:
            vol = wall_volume_m3(el)
            mid = el.params.get("material_id") or "generic"
            mat = get_material(str(mid))
            rows.append(
                {
                    "source": "wall_volume",
                    "element_id": el.id,
                    "element_name": el.name,
                    "material_id": mid,
                    "material_name": mat.name if mat else mid,
                    "qty": round(vol, 6),
                    "unit": "m3",
                    "volume_m3": round(vol, 6),
                    "mass_kg": round(material_mass_kg(str(mid), vol), 3),
                    "est_cost": round(material_cost(str(mid), vol), 2),
                    "csi_hint": mat.csi_hint if mat else "",
                }
            )

    for el in model.query(category="slab"):
        area = slab_area_m2(el)
        th = float(el.params.get("thickness_mm") or 200) / 1000.0
        vol = area * th
        mid = el.params.get("material_id") or "concrete_4000psi"
        mat = get_material(str(mid))
        rows.append(
            {
                "source": "slab",
                "element_id": el.id,
                "element_name": el.name,
                "material_id": mid,
                "material_name": mat.name if mat else mid,
                "qty": round(vol, 6),
                "unit": "m3",
                "volume_m3": round(vol, 6),
                "mass_kg": round(material_mass_kg(str(mid), vol), 3),
                "est_cost": round(material_cost(str(mid), vol), 2),
                "csi_hint": mat.csi_hint if mat else "03 30 00",
            }
        )

    # Instance BOM or part explosion
    for el in model.elements:
        qty = float(el.params.get("part_qty") or 1)
        pid = el.params.get("part_id")
        if pid and get_part(str(pid)):
            for line in explode_part_bom(get_part(str(pid)), qty):  # type: ignore[arg-type]
                line["source"] = "part_bom"
                line["element_id"] = el.id
                line["element_name"] = el.name
                rows.append(line)
            continue
        bom = el.params.get("bom") or []
        for line in bom:
            mid = str(line.get("material_id", ""))
            mat = get_material(mid)
            mass = line.get("mass_kg")
            vol = line.get("volume_m3")
            if mass is None and vol is not None:
                mass = material_mass_kg(mid, float(vol))
            cost = 0.0
            if mass is not None and mat and mat.unit_cost_per_kg:
                cost = float(mass) * mat.unit_cost_per_kg * float(line.get("qty", 1))
            elif vol is not None:
                cost = material_cost(mid, float(vol)) * float(line.get("qty", 1))
            rows.append(
                {
                    "source": "element_bom",
                    "element_id": el.id,
                    "element_name": el.name,
                    "material_id": mid,
                    "material_name": mat.name if mat else mid,
                    "description": line.get("description", ""),
                    "qty": float(line.get("qty", 1)) * qty,
                    "unit": line.get("unit", "ea"),
                    "volume_m3": vol,
                    "mass_kg": mass,
                    "est_cost": round(cost, 2),
                    "csi_hint": mat.csi_hint if mat else "",
                }
            )

    return rows


def material_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate exploded BOM by material_id."""
    agg: dict[str, dict[str, Any]] = {}
    for r in rows:
        mid = str(r.get("material_id") or "unknown")
        bucket = agg.setdefault(
            mid,
            {
                "material_id": mid,
                "material_name": r.get("material_name") or mid,
                "total_mass_kg": 0.0,
                "total_volume_m3": 0.0,
                "est_cost": 0.0,
                "line_count": 0,
                "csi_hint": r.get("csi_hint") or "",
            },
        )
        if r.get("mass_kg") is not None:
            bucket["total_mass_kg"] += float(r["mass_kg"])
        if r.get("volume_m3") is not None:
            bucket["total_volume_m3"] += float(r["volume_m3"])
        bucket["est_cost"] += float(r.get("est_cost") or 0)
        bucket["line_count"] += 1
    out = []
    for b in agg.values():
        b["total_mass_kg"] = round(b["total_mass_kg"], 3)
        b["total_volume_m3"] = round(b["total_volume_m3"], 6)
        b["est_cost"] = round(b["est_cost"], 2)
        out.append(b)
    return sorted(out, key=lambda x: -x["est_cost"])


def _element_part_meta(el) -> tuple[str | None, Any]:
    """Return (part_id, PartType|None) for an element."""
    pid = el.params.get("part_id") or (
        el.type_id if el.type_id and el.type_id in PARTS else None
    )
    if not pid:
        return None, None
    return str(pid), get_part(str(pid))


def fitting_takeoff(
    model: ProjectModel,
    *,
    fitting_type: str | None = None,
    nps: str | None = None,
    material: str | None = None,
    system: str = "plumbing",
) -> list[dict[str, Any]]:
    """Count fittings by type + size (+ material).

    Answers: "how many 90° copper fittings of what size?"

    Returns one row per (fitting_type, nps, material) with qty and element ids.
    Filters:
      - fitting_type: elbow_90 | elbow_45 | tee | coupling | ...
      - nps: "1/2", "3/4", "1", ...
      - material: copper | pvc | copper_fitting | copper_C12200
    """
    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}

    for el in model.elements:
        pid, part = _element_part_meta(el)
        if not part:
            continue
        sp = part.specs or {}
        if system and sp.get("system") != system and part.category != "plumbing":
            # still allow plumbing category without system tag
            if part.category != "plumbing":
                continue
        ftype = sp.get("fitting_type") or el.params.get("fitting_type")
        if not ftype or ftype == "pipe":
            continue
        size = str(sp.get("nps") or el.params.get("nps") or "")
        mat = str(
            sp.get("material")
            or part.primary_material_id
            or el.params.get("material_id")
            or ""
        )
        if fitting_type and ftype != fitting_type:
            continue
        if nps and size != nps:
            continue
        if material:
            ml = material.lower()
            if ml not in mat.lower() and not (
                ml in ("copper", "cu") and "copper" in mat.lower()
            ):
                continue

        qty = float(el.params.get("part_qty") or 1)
        key = (str(ftype), size, mat)
        if key not in buckets:
            buckets[key] = {
                "fitting_type": ftype,
                "nps": size,
                "nps_in": size,
                "material_id": mat,
                "part_id": part.id,
                "part_name": part.name,
                "qty": 0.0,
                "unit": "ea",
                "unit_cost": part_unit_cost(part),
                "est_cost": 0.0,
                "angle_deg": sp.get("angle_deg"),
                "csi_code": part.csi_code,
                "element_ids": [],
                "element_names": [],
            }
        b = buckets[key]
        b["qty"] += qty
        b["est_cost"] = round(b["qty"] * b["unit_cost"], 2)
        b["element_ids"].append(el.id)
        if el.name:
            b["element_names"].append(el.name)

    rows = list(buckets.values())
    for r in rows:
        r["qty"] = int(r["qty"]) if r["qty"] == int(r["qty"]) else round(r["qty"], 2)
    # sort: fitting type then size
    nps_order = ["1/2", "3/4", "1", "1-1/4", "1-1/2", "2", "2-1/2", "3", "4"]

    def _sk(r: dict[str, Any]) -> tuple:
        try:
            ni = nps_order.index(r["nps"])
        except ValueError:
            ni = 99
        return (str(r["fitting_type"]), ni, str(r["material_id"]))

    return sorted(rows, key=_sk)


def pipe_takeoff(
    model: ProjectModel,
    *,
    nps: str | None = None,
    material: str | None = None,
) -> list[dict[str, Any]]:
    """Total pipe length by NPS and material (m)."""
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for el in model.elements:
        pid, part = _element_part_meta(el)
        length_m = None
        size = None
        mat = None
        part_id = pid
        name = part.name if part else el.name

        if part and (part.specs or {}).get("fitting_type") == "pipe":
            size = str(part.specs.get("nps") or "")
            mat = str(part.specs.get("material") or part.primary_material_id)
            # length from params or geometry
            if el.params.get("length_m") is not None:
                length_m = float(el.params["length_m"])
            elif el.params.get("length_mm") is not None:
                length_m = float(el.params["length_mm"]) / 1000.0
            elif el.params.get("size_mm"):
                try:
                    length_m = float(el.params["size_mm"][0]) / 1000.0
                except (TypeError, IndexError, ValueError):
                    length_m = float(el.params.get("part_qty") or 1.0)
            else:
                length_m = float(el.params.get("part_qty") or 1.0)
        elif el.category in {"pipe", "plumbing_pipe"}:
            size = str(el.params.get("nps") or "")
            mat = str(el.params.get("material_id") or "copper_C12200")
            if el.params.get("length_m") is not None:
                length_m = float(el.params["length_m"])
            elif el.params.get("length_mm") is not None:
                length_m = float(el.params["length_mm"]) / 1000.0
            else:
                length_m = float(el.params.get("part_qty") or 0)

        if length_m is None or length_m <= 0:
            continue
        if nps and size != nps:
            continue
        if material:
            ml = material.lower()
            if mat and ml not in mat.lower() and not (ml in ("copper", "cu") and "copper" in mat.lower()):
                continue

        key = (size or "?", mat or "?")
        if key not in buckets:
            unit_cost = part_unit_cost(part) if part else 0.0
            buckets[key] = {
                "fitting_type": "pipe",
                "nps": size,
                "material_id": mat,
                "part_id": part_id,
                "part_name": name,
                "length_m": 0.0,
                "unit": "m",
                "unit_cost_per_m": unit_cost,
                "est_cost": 0.0,
                "segment_count": 0,
                "element_ids": [],
            }
        b = buckets[key]
        b["length_m"] += length_m
        b["segment_count"] += 1
        b["est_cost"] = round(b["length_m"] * b["unit_cost_per_m"], 2)
        b["element_ids"].append(el.id)

    out = list(buckets.values())
    for r in out:
        r["length_m"] = round(r["length_m"], 3)
    return sorted(out, key=lambda x: (str(x["nps"]), str(x["material_id"])))


def part_summary(model: ProjectModel) -> list[dict[str, Any]]:
    """Aggregate assigned parts by part_id (qty × unit cost)."""
    buckets: dict[str, dict[str, Any]] = {}
    for row in part_assignment_list(model):
        pid = str(row["part_id"])
        if pid not in buckets:
            buckets[pid] = {
                "part_id": pid,
                "part_name": row.get("part_name"),
                "qty": 0.0,
                "unit": "ea",
                "unit_cost": row.get("unit_cost") or 0,
                "est_cost": 0.0,
                "csi_code": row.get("csi_code") or "",
                "primary_material_id": row.get("primary_material_id"),
                "instance_count": 0,
            }
        b = buckets[pid]
        q = float(row.get("qty") or 1)
        b["qty"] += q
        b["instance_count"] += 1
        b["est_cost"] = round(b["qty"] * float(b["unit_cost"] or 0), 2)
    return sorted(buckets.values(), key=lambda x: -float(x["est_cost"]))


def plumbing_schedule(model: ProjectModel) -> dict[str, Any]:
    """Full plumbing package answer for agents."""
    fittings = fitting_takeoff(model)
    pipes = pipe_takeoff(model)
    copper_90 = [r for r in fittings if r["fitting_type"] == "elbow_90" and "copper" in str(r["material_id"]).lower()]
    return {
        "fittings": fittings,
        "pipe": pipes,
        "copper_90_elbows_by_size": copper_90,
        "totals": {
            "fitting_pieces": sum(int(r["qty"]) if isinstance(r["qty"], (int, float)) else 0 for r in fittings),
            "pipe_length_m": round(sum(float(r["length_m"]) for r in pipes), 3),
            "est_cost_fittings": round(sum(float(r["est_cost"]) for r in fittings), 2),
            "est_cost_pipe": round(sum(float(r["est_cost"]) for r in pipes), 2),
        },
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys and not isinstance(r[k], (list, dict)):
                keys.append(k)
    # include list fields as joined strings for CSV
    list_keys = set()
    for r in rows:
        for k, v in r.items():
            if isinstance(v, list) and k not in keys:
                list_keys.add(k)
                keys.append(k)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            row = dict(r)
            for k in list_keys:
                if isinstance(row.get(k), list):
                    row[k] = ";".join(str(x) for x in row[k])
            w.writerow(row)


def export_lists(model: ProjectModel, out_dir: str | Path) -> dict[str, str]:
    """Write assignment + BOM + fitting takeoff lists to a directory."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    mat_assign = material_assignment_list(model)
    part_assign = part_assignment_list(model)
    exploded = exploded_material_bom(model)
    summary = material_summary(exploded)
    fittings = fitting_takeoff(model)
    pipes = pipe_takeoff(model)
    parts_sum = part_summary(model)
    plumbing = plumbing_schedule(model)

    files: dict[str, Any] = {
        "material_assignments": mat_assign,
        "part_assignments": part_assign,
        "material_bom_exploded": exploded,
        "material_summary": summary,
        "fitting_takeoff": fittings,
        "pipe_takeoff": pipes,
        "part_summary": parts_sum,
    }
    written: dict[str, str] = {}
    for name, rows in files.items():
        jp = out / f"{name}.json"
        cp = out / f"{name}.csv"
        jp.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        _write_csv(cp, rows if isinstance(rows, list) else [])
        written[name] = str(jp.name)

    (out / "plumbing_schedule.json").write_text(
        json.dumps(plumbing, indent=2) + "\n", encoding="utf-8"
    )
    written["plumbing_schedule"] = "plumbing_schedule.json"

    payload = {
        "material_assignments": mat_assign,
        "part_assignments": part_assign,
        "material_bom_exploded": exploded,
        "material_summary": summary,
        "fitting_takeoff": fittings,
        "pipe_takeoff": pipes,
        "part_summary": parts_sum,
        "plumbing": plumbing,
        "catalog_materials": list(MATERIALS.keys()),
        "catalog_parts_count": len(PARTS),
        "catalog_plumbing_parts": [k for k, v in PARTS.items() if v.category == "plumbing"],
    }
    (out / "MATERIALS_AND_PARTS.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    written["package"] = "MATERIALS_AND_PARTS.json"
    return written
