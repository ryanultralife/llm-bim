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
        # prefer explicit qty; else length_m for linear parts (steel/rebar/studs)
        if el.params.get("part_qty") is not None:
            qty = float(el.params["part_qty"])
        elif el.params.get("length_m") is not None:
            qty = float(el.params["length_m"])
        else:
            qty = 1.0
        # catalog unit (m / m2 / ea); length-based takeoff for linear parts
        unit = str((part.specs or {}).get("unit") if part else "ea") or "ea"
        if unit in ("m", "m2") and el.params.get("length_m") is not None:
            if float(el.params.get("part_qty") or 1) == 1.0 and float(el.params["length_m"]) != 1.0:
                qty = float(el.params["length_m"])
        rows.append(
            {
                "element_id": el.id,
                "element_name": el.name,
                "category": el.category,
                "part_id": pid,
                "part_name": part.name if part else pid,
                "qty": qty,
                "unit": unit,
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
    system: str | None = None,
) -> list[dict[str, Any]]:
    """Count fittings by type + size (+ material / system).

    Answers: "how many 90° copper fittings of what size?"
    Also fire/process: system=\"fire\"|\"process\"|\"plumbing\".

    Returns one row per (fitting_type, nps, material, system).
    """
    buckets: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    pipe_systems = {"plumbing", "fire", "process", "process_piping", "fire_protection"}

    for el in model.elements:
        pid, part = _element_part_meta(el)
        if not part:
            continue
        sp = part.specs or {}
        sys = str(sp.get("system") or part.category or "")
        if system:
            if sys != system and part.category != system and system not in (sys, part.category):
                # aliases
                aliases = {
                    "fire": ("fire", "fire_protection"),
                    "process": ("process", "process_piping"),
                    "plumbing": ("plumbing",),
                }
                allowed = aliases.get(system, (system,))
                if sys not in allowed and part.category not in allowed:
                    continue
        ftype = sp.get("fitting_type") or el.params.get("fitting_type")
        if not ftype or ftype == "pipe":
            continue
        # discrete fixtures counted in system_takeoff; fittings are pipe fittings + heads
        size = str(sp.get("nps") or el.params.get("nps") or sp.get("size") or sp.get("bar_size") or "")
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
            ) and not (ml in ("ss", "ss316") and "ss316" in mat.lower()):
                continue

        qty = float(el.params.get("part_qty") or 1)
        # length-based for framing studs / rebar / steel sold per m
        unit = str(sp.get("unit") or "ea")
        if unit in ("m", "m2") and el.params.get("length_m") is not None:
            qty = float(el.params["length_m"])
        elif unit == "m" and el.params.get("length_mm") is not None:
            qty = float(el.params["length_mm"]) / 1000.0

        key = (str(ftype), size, mat, sys)
        if key not in buckets:
            buckets[key] = {
                "fitting_type": ftype,
                "nps": size,
                "nps_in": size,
                "size": size,
                "system": sys,
                "material_id": mat,
                "part_id": part.id,
                "part_name": part.name,
                "qty": 0.0,
                "unit": unit,
                "unit_cost": part_unit_cost(part),
                "est_cost": 0.0,
                "angle_deg": sp.get("angle_deg"),
                "csi_code": part.csi_code or sp.get("csi_code") or "",
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
        if r["unit"] == "ea" and r["qty"] == int(r["qty"]):
            r["qty"] = int(r["qty"])
        else:
            r["qty"] = round(float(r["qty"]), 3)
    nps_order = ["1/2", "3/4", "1", "1-1/4", "1-1/2", "2", "2-1/2", "3", "4", "6", "8"]

    def _sk(r: dict[str, Any]) -> tuple:
        try:
            ni = nps_order.index(r["nps"])
        except ValueError:
            ni = 99
        return (str(r.get("system")), str(r["fitting_type"]), ni, str(r["material_id"]))

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


def duct_takeoff(model: ProjectModel) -> list[dict[str, Any]]:
    """Rectangular duct runs: length_m + area_m2 by size/system."""
    rows: list[dict[str, Any]] = []
    for el in model.elements:
        if el.category not in {"duct", "hvac"} and el.params.get("fitting_type") != "duct":
            continue
        if el.params.get("fitting_type") in {"vav", "diffuser", "grille", "fire_damper", "smoke_damper"}:
            continue
        length_m = float(el.params.get("length_m") or 0)
        if not length_m and el.params.get("length_mm"):
            length_m = float(el.params["length_mm"]) / 1000.0
        if not length_m and el.params.get("start_mm") and el.params.get("end_mm"):
            import math

            s, e = el.params["start_mm"], el.params["end_mm"]
            length_m = math.hypot(float(e[0]) - float(s[0]), float(e[1]) - float(s[1])) / 1000.0
        area_m2 = float(el.params.get("area_m2") or el.params.get("part_qty") or 0)
        w = float(el.params.get("width_mm") or 0)
        h = float(el.params.get("height_mm") or 0)
        if not area_m2 and w and h and length_m:
            area_m2 = 2.0 * (w + h) * length_m * 1000.0 / 1_000_000.0
        rows.append(
            {
                "element_id": el.id,
                "name": el.name,
                "category": "duct",
                "width_mm": w or None,
                "height_mm": h or None,
                "size": f"{w:.0f}x{h:.0f}" if w and h else None,
                "length_m": round(length_m, 3),
                "area_m2": round(area_m2, 3),
                "system": el.params.get("system"),
                "material_id": el.params.get("material_id"),
                "part_id": el.params.get("part_id") or el.type_id,
                "csi_code": el.params.get("csi_code") or "23 31 00",
                "unit": "m2" if area_m2 else "m",
            }
        )
    return sorted(rows, key=lambda r: (str(r.get("size") or ""), r["element_id"]))


def conduit_takeoff(model: ProjectModel) -> list[dict[str, Any]]:
    """Electrical conduit length by trade size (m)."""
    buckets: dict[str, dict[str, Any]] = {}
    for el in model.elements:
        if el.category != "conduit" and el.params.get("fitting_type") != "conduit":
            continue
        size = str(el.params.get("nps") or el.params.get("trade_size") or "?")
        length_m = float(el.params.get("length_m") or 0)
        if not length_m and el.params.get("length_mm"):
            length_m = float(el.params["length_mm"]) / 1000.0
        if not length_m and el.params.get("start_mm") and el.params.get("end_mm"):
            import math

            s, e = el.params["start_mm"], el.params["end_mm"]
            length_m = math.hypot(float(e[0]) - float(s[0]), float(e[1]) - float(s[1])) / 1000.0
        if length_m <= 0:
            continue
        if size not in buckets:
            buckets[size] = {
                "trade_size": size,
                "nps": size,
                "length_m": 0.0,
                "segment_count": 0,
                "unit": "m",
                "csi_code": "26 05 33",
                "element_ids": [],
            }
        b = buckets[size]
        b["length_m"] += length_m
        b["segment_count"] += 1
        b["element_ids"].append(el.id)
    out = list(buckets.values())
    for r in out:
        r["length_m"] = round(r["length_m"], 3)
    return sorted(out, key=lambda x: str(x["trade_size"]))


def cable_tray_takeoff(model: ProjectModel) -> list[dict[str, Any]]:
    """Cable tray runs: length_m + area_m2 by width."""
    rows: list[dict[str, Any]] = []
    for el in model.elements:
        if el.category != "cable_tray" and el.params.get("fitting_type") != "cable_tray":
            continue
        length_m = float(el.params.get("length_m") or 0)
        if not length_m and el.params.get("length_mm"):
            length_m = float(el.params["length_mm"]) / 1000.0
        if not length_m and el.params.get("start_mm") and el.params.get("end_mm"):
            import math

            s, e = el.params["start_mm"], el.params["end_mm"]
            length_m = math.hypot(float(e[0]) - float(s[0]), float(e[1]) - float(s[1])) / 1000.0
        w = float(el.params.get("width_mm") or 0)
        h = float(el.params.get("height_mm") or 0)
        area_m2 = float(el.params.get("area_m2") or 0)
        if not area_m2 and w and length_m:
            area_m2 = (w * length_m) / 1000.0
        rows.append(
            {
                "element_id": el.id,
                "name": el.name,
                "category": "cable_tray",
                "width_mm": w or None,
                "height_mm": h or None,
                "size": f"{w:.0f}x{h:.0f}" if w and h else None,
                "length_m": round(length_m, 3),
                "area_m2": round(area_m2, 3),
                "system": el.params.get("system"),
                "material_id": el.params.get("material_id"),
                "part_id": el.params.get("part_id") or el.type_id,
                "csi_code": el.params.get("csi_code") or "26 05 36",
                "unit": "m",
            }
        )
    return sorted(rows, key=lambda r: (str(r.get("size") or ""), r["element_id"]))


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
                "unit": row.get("unit") or "ea",
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
        if row.get("unit") and b["unit"] == "ea" and row["unit"] != "ea":
            b["unit"] = row["unit"]
    return sorted(buckets.values(), key=lambda x: -float(x["est_cost"]))


def plumbing_schedule(model: ProjectModel) -> dict[str, Any]:
    """Full plumbing package answer for agents."""
    fittings = fitting_takeoff(model, system="plumbing")
    # also fixtures without system filter miss — include copper fittings from unfiltered
    all_fit = fitting_takeoff(model)
    fittings = [r for r in all_fit if r.get("system") in ("plumbing", "", None) or "copper" in str(r.get("material_id", "")).lower()]
    if not fittings:
        fittings = [r for r in all_fit if r.get("system") not in ("fire", "process", "structural_steel", "rebar", "framing")]
    pipes = pipe_takeoff(model)
    copper_90 = [
        r
        for r in all_fit
        if r["fitting_type"] == "elbow_90" and "copper" in str(r["material_id"]).lower()
    ]
    fixtures = [
        r
        for r in part_summary(model)
        if str(r.get("part_id", "")).startswith("PT-PLB") or str(r.get("part_id", "")).startswith("PT-ACC")
    ]
    return {
        "fittings": fittings,
        "pipe": pipes,
        "copper_90_elbows_by_size": copper_90,
        "fixtures_and_accessories": fixtures,
        "totals": {
            "fitting_pieces": sum(float(r["qty"]) for r in fittings if r.get("unit") == "ea"),
            "pipe_length_m": round(sum(float(r["length_m"]) for r in pipes), 3),
            "est_cost_fittings": round(sum(float(r["est_cost"]) for r in fittings), 2),
            "est_cost_pipe": round(sum(float(r["est_cost"]) for r in pipes), 2),
        },
    }


def system_takeoff(model: ProjectModel, system: str | None = None) -> list[dict[str, Any]]:
    """Rollup all assigned parts filtered by system (fire, process, rebar, …)."""
    rows = []
    for r in part_summary(model):
        part = get_part(str(r["part_id"]))
        if not part:
            continue
        sys = str((part.specs or {}).get("system") or part.category)
        if system and sys != system and part.category != system:
            aliases = {
                "fire": ("fire", "fire_protection"),
                "process": ("process", "process_piping"),
                "steel": ("structural_steel", "structural"),
                "structural_steel": ("structural_steel", "structural"),
                "fixture": ("plumbing_fixture", "fixture", "toilet_accessory", "accessory"),
            }
            allowed = aliases.get(system, (system,))
            if sys not in allowed and part.category not in allowed:
                continue
        rows.append(
            {
                **r,
                "system": sys,
                "fitting_type": (part.specs or {}).get("fitting_type"),
                "nps": (part.specs or {}).get("nps"),
                "section": (part.specs or {}).get("section"),
                "bar_size": (part.specs or {}).get("bar_size"),
                "csi_code": part.csi_code,
            }
        )
    return rows


def csi_takeoff(model: ProjectModel, *, division: str | None = None) -> list[dict[str, Any]]:
    """Aggregate by real MasterFormat CSI code; include instance locators."""
    from llmbim_core.csi import (
        CSI_DIVISIONS,
        CSI_SECTIONS,
        csi_for_element,
        csi_instance_schedule,
        normalize_csi_code,
        resolve_csi_code,
    )

    buckets: dict[str, dict[str, Any]] = {}
    for r in part_assignment_list(model):
        part = get_part(str(r["part_id"]))
        code = resolve_csi_code(
            csi_code=part.csi_code if part else None,
            category=str(r.get("category") or ""),
            part_id=str(r["part_id"]),
        )
        code = normalize_csi_code(code)
        if division and not code.startswith(division):
            continue
        qty = float(r.get("qty") or 1)
        cost = float(r.get("est_cost") or 0)
        b = buckets.setdefault(
            code,
            {
                "csi_code": code,
                "csi_number": code,
                "csi_section_name": CSI_SECTIONS.get(code, ""),
                "csi_division": code.split()[0],
                "csi_division_name": CSI_DIVISIONS.get(code.split()[0], ""),
                "qty_lines": 0,
                "est_cost": 0.0,
                "parts": {},
                "instances": [],
            },
        )
        b["qty_lines"] += 1
        b["est_cost"] += cost
        pid = str(r["part_id"])
        pb = b["parts"].setdefault(
            pid, {"part_id": pid, "part_name": r.get("part_name"), "qty": 0.0, "est_cost": 0.0}
        )
        pb["qty"] += qty
        pb["est_cost"] += cost
        # per-element locator if present
        eid = r.get("element_id")
        if eid:
            try:
                el = model.get_element(str(eid))
                inst = csi_for_element(model, el)
                b["instances"].append(
                    {
                        "element_id": eid,
                        "csi_instance": inst.get("csi_instance"),
                        "locator": inst.get("locator"),
                        "level": inst.get("level"),
                        "x_mm": inst.get("x_mm"),
                        "y_mm": inst.get("y_mm"),
                        "z_mm": inst.get("z_mm"),
                        "height_mm": inst.get("height_mm"),
                        "qty": qty,
                    }
                )
            except Exception:  # noqa: BLE001
                pass
    out = []
    for code, b in buckets.items():
        b["est_cost"] = round(b["est_cost"], 2)
        b["parts"] = sorted(b["parts"].values(), key=lambda x: -x["est_cost"])
        out.append(b)
    # always useful: flat instance schedule attached when empty parts model still has geometry
    if not out:
        for row in csi_instance_schedule(model):
            if division and not str(row.get("csi_code", "")).startswith(division):
                continue
            out.append(
                {
                    "csi_code": row["csi_code"],
                    "csi_number": row["csi_code"],
                    "csi_section_name": row.get("csi_section_name"),
                    "csi_division": row.get("csi_division"),
                    "csi_division_name": row.get("csi_division_name"),
                    "qty_lines": 1,
                    "est_cost": 0.0,
                    "parts": [],
                    "instances": [row],
                }
            )
    return sorted(out, key=lambda x: x["csi_code"])


def steel_takeoff(model: ProjectModel) -> list[dict[str, Any]]:
    """Structural steel by section (meters × weight)."""
    return system_takeoff(model, "structural_steel")


def rebar_takeoff(model: ProjectModel) -> list[dict[str, Any]]:
    """Rebar by bar size."""
    return system_takeoff(model, "rebar")


def fire_takeoff(model: ProjectModel) -> dict[str, Any]:
    """Fire protection: pipe + fittings + heads."""
    fits = fitting_takeoff(model, system="fire")
    heads = [r for r in fits if r["fitting_type"] == "sprinkler_head"]
    elbows = [r for r in fits if r["fitting_type"] == "elbow_90"]
    pipes = [
        r
        for r in pipe_takeoff(model)
        if "black" in str(r.get("material_id", "")).lower() or str(r.get("part_id", "")).startswith("PT-FP")
    ]
    # also pipe from fire parts with length
    return {
        "fittings": fits,
        "sprinkler_heads": heads,
        "elbow_90_by_size": elbows,
        "pipe": pipes,
        "devices": system_takeoff(model, "fire"),
    }


def full_trade_schedule(model: ProjectModel) -> dict[str, Any]:
    """Master schedule: all trades + CSI rollup."""
    return {
        "plumbing": plumbing_schedule(model),
        "fire": fire_takeoff(model),
        "process": {
            "fittings": fitting_takeoff(model, system="process"),
            "parts": system_takeoff(model, "process"),
        },
        "structural_steel": steel_takeoff(model),
        "rebar": rebar_takeoff(model),
        "framing": system_takeoff(model, "framing"),
        "fixtures": system_takeoff(model, "fixture"),
        "hvac": {
            "duct": duct_takeoff(model),
            "devices": system_takeoff(model, "hvac"),
        },
        "electrical": {
            "conduit": conduit_takeoff(model),
            "cable_tray": cable_tray_takeoff(model),
            "devices": system_takeoff(model, "electrical"),
        },
        "csi": csi_takeoff(model),
        "part_summary": part_summary(model),
        "material_summary": material_summary(exploded_material_bom(model)),
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


def connection_schedule(model: ProjectModel) -> list[dict[str, Any]]:
    """Module/equipment port connections with resolved element names for agents."""
    rows: list[dict[str, Any]] = []
    for c in list(model.meta.get("connections") or []):
        if not isinstance(c, dict):
            continue
        from_id = str(c.get("from_id") or "")
        to_id = str(c.get("to_id") or "")
        from_name = from_id
        to_name = to_id
        try:
            from_name = model.get_element(from_id).name or from_id
        except Exception:  # noqa: BLE001
            pass
        try:
            to_name = model.get_element(to_id).name or to_id
        except Exception:  # noqa: BLE001
            pass
        fport = str(c.get("from_port") or "")
        tport = str(c.get("to_port") or "")
        medium = str(c.get("medium") or "")
        rows.append(
            {
                "id": c.get("id"),
                "name": c.get("name") or f"{fport}→{tport}",
                "from_id": from_id,
                "from_name": from_name,
                "from_port": fport,
                "to_id": to_id,
                "to_name": to_name,
                "to_port": tport,
                "medium": medium,
                "locator": f"{from_name}.{fport} → {to_name}.{tport}"
                + (f" [{medium}]" if medium else ""),
            }
        )
    return rows


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
    ducts = duct_takeoff(model)
    conduits = conduit_takeoff(model)
    trays = cable_tray_takeoff(model)
    parts_sum = part_summary(model)
    plumbing = plumbing_schedule(model)
    fire = fire_takeoff(model)
    steel = steel_takeoff(model)
    rebar = rebar_takeoff(model)
    csi = csi_takeoff(model)
    from llmbim_core.csi import csi_instance_schedule

    csi_instances = csi_instance_schedule(model)
    trades = full_trade_schedule(model)
    connections = connection_schedule(model)

    files: dict[str, Any] = {
        "material_assignments": mat_assign,
        "part_assignments": part_assign,
        "material_bom_exploded": exploded,
        "material_summary": summary,
        "fitting_takeoff": fittings,
        "pipe_takeoff": pipes,
        "duct_takeoff": ducts,
        "conduit_takeoff": conduits,
        "cable_tray_takeoff": trays,
        "part_summary": parts_sum,
        "steel_takeoff": steel,
        "rebar_takeoff": rebar,
        "csi_takeoff": csi,
        "csi_instances": csi_instances,
        "connections": connections,
    }
    written: dict[str, str] = {}
    for name, rows in files.items():
        jp = out / f"{name}.json"
        cp = out / f"{name}.csv"
        jp.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        _write_csv(cp, rows if isinstance(rows, list) else [])
        written[name] = str(jp.name)

    for name, obj in (
        ("plumbing_schedule", plumbing),
        ("fire_takeoff", fire),
        ("trade_schedule", trades),
    ):
        (out / f"{name}.json").write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
        written[name] = f"{name}.json"

    from llmbim_core.parts_catalog import catalog_summary

    payload = {
        "material_assignments": mat_assign,
        "part_assignments": part_assign,
        "material_bom_exploded": exploded,
        "material_summary": summary,
        "fitting_takeoff": fittings,
        "pipe_takeoff": pipes,
        "part_summary": parts_sum,
        "plumbing": plumbing,
        "fire": fire,
        "steel": steel,
        "rebar": rebar,
        "csi": csi,
        "trades": trades,
        "catalog_materials": list(MATERIALS.keys()),
        "catalog": catalog_summary(),
    }
    (out / "MATERIALS_AND_PARTS.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    written["package"] = "MATERIALS_AND_PARTS.json"
    return written
