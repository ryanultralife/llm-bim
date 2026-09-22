"""Authoring contracts — explicit required detail so LLMs generate the envisioned product.

Agents should call ``authoring_checklist`` / ``validate_intent`` before large packs.
"""

from __future__ import annotations

import re
from typing import Any

from llmbim_core.model import ProjectModel

# Distinct viewer-layer kinds that count as machine hardware (not envelopes).
# Frozen map lives in llmbim_geometry.mesh.EQUIP_KIND_MATERIAL — ADD only.
_HARDWARE_KINDS = frozenset({
    "bolt",
    "nut",
    "washer",
    "stud",
    "fastener",
    "tie_rod",
    "tierod",
    "flange",
    "gasket",
    "elbow",
    "tee",
    "union",
    "hinge",
    "latch",
    "handle",
    "door_leaf",
    "door_panel",
    "nameplate",
    "tag_plate",
    "handwheel",
    "stem",
    "clip",
    "grating",
    "kickplate",
    "louver",
    "vent",
    "gland",
    "gland_nut",
    "foot",
    "twistlock",
    "clamp",
})

_FITTING_KINDS = frozenset({"elbow", "tee", "union", "flange", "gasket"})
_RUN_CATEGORIES = frozenset({"pipe", "plumbing_pipe", "duct", "hvac", "cable_tray", "conduit"})
_PN_AS_NAME = re.compile(r"^MB-[A-Z0-9]+", re.IGNORECASE)
_DIAGONAL_TOL_MM = 5.0


def _xy_pair(el: Any) -> tuple[list[float], list[float]] | None:
    p = el.params or {}
    start = p.get("start_mm")
    end = p.get("end_mm")
    if (
        isinstance(start, (list, tuple))
        and isinstance(end, (list, tuple))
        and len(start) >= 2
        and len(end) >= 2
    ):
        return [float(start[0]), float(start[1])], [float(end[0]), float(end[1])]
    return None


def _is_diagonal_run(start: list[float], end: list[float], tol: float = _DIAGONAL_TOL_MM) -> bool:
    return abs(end[0] - start[0]) > tol and abs(end[1] - start[1]) > tol


def _count_diagonal_runs(model: ProjectModel) -> int:
    n = 0
    for el in model.elements:
        if el.category not in _RUN_CATEGORIES:
            continue
        pair = _xy_pair(el)
        if pair and _is_diagonal_run(*pair):
            n += 1
    return n

# What an agent must collect (or invent with stated defaults) for each product class
PRODUCT_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "building_shell": {
        "description": "Enclosed floor plate with levels and exterior walls",
        "required": [
            "project_name",
            "levels (name + elevation_mm)",
            "plan extents (LxW mm or wall loop)",
            "wall thickness_mm + height_mm (or wall type_id)",
            "units if not mm",
        ],
        "recommended": [
            "wall type_id (W-EXT-CMU | W-INT-GYP | W-SHIELD-CONC)",
            "fire_rating",
            "slab thickness",
            "grids",
            "phase (new|existing)",
        ],
        "ops": ["add_level", "create_rect_shell|create_wall", "create_slab", "set_type", "add_grid"],
    },
    "openings": {
        "description": "Doors/windows on host walls",
        "required": [
            "host wall id",
            "offset_mm along host",
            "width_mm + height_mm",
            "type_id (door/window)",
        ],
        "recommended": ["fire_rating", "sill_mm (windows)", "name"],
        "ops": ["place_door", "place_window"],
    },
    "mep_run": {
        "description": "Pipe/duct/conduit between points or fittings",
        "required": [
            "level",
            "start XY + end XY (or mep_route from_id/to_id)",
            "system tag (CW|HW|FP|SA|…)",
            "size: nps (pipe) | width_mm×height_mm (duct) | trade_size (conduit)",
        ],
        "recommended": [
            "material (copper|fire|process|pvc)",
            "z0_mm elevation of run",
            "vertical riser: origin + z0/z1 or to_level",
            "orthogonal dogleg via mep_route(orthogonal=true)",
        ],
        "ops": ["place_pipe", "place_duct", "place_conduit", "place_riser", "mep_route", "place_fitting"],
    },
    "structure": {
        "description": "Steel columns/beams",
        "required": ["level", "section (e.g. W10x33)", "column origin OR beam start→end"],
        "recommended": ["height_mm (column)", "z0_mm (beam TOS)", "material_id"],
        "ops": ["place_column", "place_beam"],
    },
    "fab_part": {
        "description": "Machine/fabrication BREP with optional GD&T",
        "required": [
            "name",
            "at least one solid feature (fab_box|cylinder|revolve|thread)",
            "feature sizes in mm",
        ],
        "recommended": [
            "material_id",
            "fillet/chamfer with selector (top_loop|tag:name|long)",
            "holes: diameter + origin + depth",
            "thread: designation M10x1.5 + length + internal?",
            "GD&T: datums A/B + FCF position/flatness + size ±tol",
            "knit: fab_host_to_building(level, host_id, origin)",
        ],
        "ops": [
            "create_fab_part",
            "fab_box",
            "fab_hole",
            "fab_fillet",
            "fab_thread",
            "gdt_datum",
            "gdt_fcf",
            "export_fab_step",
        ],
        "extra": "pip install 'llmbim[fab]' (CadQuery/OCP)",
    },
    "field_device_fab": {
        "description": (
            "Field-deployable / vehicle-array machine product: PN catalog SSOT, "
            "one viewer layer per component kind, dozens of parts, fab-intent sheets"
        ),
        "required": [
            "product_class (e.g. field_deployable_vehicle_array | modular_pod | skid)",
            "design-basis module or parts[] PN catalog (every number from basis — never retype)",
            "mission/host (UGV | light vehicle | trailer | bay | bench — state scale out loud)",
            "unique PN count target ≥ 20 for fab-intent; ≥ 40 preferred for release-class depth",
            "each PN: kind (viewer layer) + material_id + system tag + size/od/id/length mm",
            "coordination equipment solid per PN (create_equipment_box) for glTF layers + part sheets",
            "human product name on Project.create / meta.product — P/Ns stay document IDs",
            "connected services: headers/trays/cables land both ends; orthogonal doglegs; connect()/mep_route",
            "fitting at every pipe bend/nozzle (elbow/tee/union/flange) — no free-air corners or diagonals",
            "hardware families as distinct kinds (bolt, flange, door, hinge, nameplate, …)",
            "fab_part BREP for machined PNs (create_fab_part + features + gdt_*) when llmbim[fab]",
            "export_deliverables(mode='part') → machine_set GA + parts/drawings + fab/ + index.html",
            "honesty stamp: FAB-INTENT / ENGINEERING ESTIMATE — not PE-stamped shop traveler",
        ],
        "recommended": [
            "systems partition: STRUCT | RAIL/BORE | POWER | DIAG | ARRAY (or domain-equivalent)",
            "array: default N×M modular pods on vehicle tray; primary pod full detail; others instances",
            "BOM.json + BOM.csv + LAYERS.json in pack root",
            "params: pn, system, material_id, twin_fidelity=F1, product_class, verification",
            "process_notes on model.meta matching the design freeze",
            "equipment= + part= on every solid for GA collapse/leaders",
            "avoid industrial plant envelopes when product is personal/field/vehicle-scale",
            "avoid lab-benchtop packaging when product is field-deployable (and vice versa)",
            "hero product pipeline after pack; re-engage http://127.0.0.1:8766/<slug>/",
            "verify_pack ok; glTF mesh_count ≈ element count; layer_kinds ≥ 12",
            "bolt circles: prefer GD&T callouts if multi-hole CQ export hangs",
            "worked examples: examples/mineclean_component_apparatus.py · examples/pal_launcher.py",
        ],
        "ops": [
            "create_equipment_box",
            "create_fab_part",
            "fab_box",
            "fab_cylinder",
            "fab_hole",
            "gdt_datum",
            "gdt_fcf",
            "gdt_size",
            "create_fab_assembly",
            "fab_assembly_add",
            "assign_material",
            "place_pipe",
            "place_riser",
            "place_fitting",
            "place_cable_tray",
            "mep_route",
            "connect",
            "add_grid",
            "export_deliverables",
            "export_part_pack",
        ],
        "extra": (
            "Engineering bar: docs/MACHINE_ENGINEERING_BAR.md · "
            "PN/fab doctrine: docs/FIELD_DEVICE_FAB.md · "
            "Recipes: skills/llm-bim/recipes/field_device_fab.md · "
            "skills/llm-bim/recipes/machine_ga.md · "
            "Examples: examples/mineclean_component_apparatus.py · examples/pal_launcher.py"
        ),
    },
    "machine_fab_pack": {
        "description": "Alias of field_device_fab for bench/skid machines (same PN/layer/sheet bar)",
        "required": [
            "same as field_device_fab",
            "or device_pack JSON (llmbim.device_pack/v1) expanded to per-PN equipment + fab",
        ],
        "recommended": [
            "Proto-10 / MineClean / PAL depth: multi-kind layers, not single grey equipment box",
            "see docs/MACHINE_ENGINEERING_BAR.md + docs/EQUIPMENT_3D_AND_DEVICE_SSOT.md + docs/FIELD_DEVICE_FAB.md",
        ],
        "ops": ["create_equipment_box", "create_fab_part", "export_deliverables"],
        "extra": "Alias intent — validate_intent('machine_fab_pack') uses field_device_fab rules",
    },
    "deliverables_pack": {
        "description": "One-shot export users open in browser/CAD",
        "required": ["out_dir or default output/<slug>/"],
        "recommended": [
            "export_deliverables after meaningful edits",
            "verify_pack",
            "commit message for VCS",
            "tell user absolute path to index.html + viewer3d.html",
            "for machines: mode='part' so each PN gets a sheet",
        ],
        "ops": ["export_pack", "verify"],
    },
}


def authoring_checklist(product: str | None = None) -> dict[str, Any]:
    """Return required/recommended detail for one product class or all."""
    if product:
        key = product.strip().lower().replace(" ", "_").replace("-", "_")
        if key not in PRODUCT_REQUIREMENTS:
            return {
                "ok": False,
                "error": f"unknown product '{product}'",
                "known": sorted(PRODUCT_REQUIREMENTS.keys()),
            }
        return {"ok": True, "product": key, **PRODUCT_REQUIREMENTS[key]}
    return {
        "ok": True,
        "products": {k: v for k, v in PRODUCT_REQUIREMENTS.items()},
        "instruction": (
            "Before modeling, collect REQUIRED fields from the user (or state explicit defaults). "
            "Do not invent PE seals. Export pack and give open paths."
        ),
    }


def validate_intent(model: ProjectModel, intent: str = "building_shell") -> dict[str, Any]:
    """Score whether the current model has enough detail for a stated intent."""
    intent_k = intent.strip().lower().replace(" ", "_").replace("-", "_")
    missing: list[str] = []
    warnings: list[str] = []
    equip = [e for e in model.elements if e.category == "equipment"]
    kinds = {
        str(e.params.get("kind") or "equipment")
        for e in equip
        if e.params.get("kind")
    }
    pns = {
        str(e.params.get("pn") or e.params.get("part") or "")
        for e in equip
        if (e.params.get("pn") or e.params.get("part"))
    }
    pns.discard("")
    fittings = sum(1 for e in model.elements if e.category == "fitting")
    fittings += sum(
        1
        for e in equip
        if str(e.params.get("kind") or "") in _FITTING_KINDS
    )
    trays = sum(1 for e in model.elements if e.category == "cable_tray")
    connections = len(model.meta.get("mep_graph") or []) + len(
        model.meta.get("connections") or []
    )
    hardware_kinds = {k for k in kinds if k in _HARDWARE_KINDS}
    stats = {
        "levels": len(model.levels),
        "walls": sum(1 for e in model.elements if e.category == "wall"),
        "doors": sum(1 for e in model.elements if e.category == "door"),
        "pipes": sum(1 for e in model.elements if e.category in {"pipe", "plumbing_pipe"}),
        "ducts": sum(1 for e in model.elements if e.category in {"duct", "hvac"}),
        "trays": trays,
        "fittings": fittings,
        "columns": sum(1 for e in model.elements if e.category == "column"),
        "fab_parts": sum(1 for e in model.elements if e.category == "fab_part"),
        "equipment": len(equip),
        "equipment_kinds": len(kinds),
        "hardware_kinds": len(hardware_kinds),
        "unique_pns": len(pns),
        "mep_graph": len(model.meta.get("mep_graph") or []),
        "connections": connections,
        "diagonal_runs": _count_diagonal_runs(model),
        "grids": len(model.grids),
        "rooms": sum(1 for e in model.elements if e.category == "room"),
    }
    if intent_k in {"building_shell", "building", "facility"}:
        if stats["levels"] < 1:
            missing.append("add_level")
        if stats["walls"] < 3:
            missing.append("create walls or create_rect_shell (need closed loop)")
        walls = [e for e in model.elements if e.category == "wall"]
        if walls and not any(e.type_id or e.params.get("type_id") for e in walls):
            warnings.append("no wall type_id — layered assembly takeoff weak; set_type W-EXT-CMU etc.")
    elif intent_k in {"mep_run", "mep", "plumbing"}:
        if stats["pipes"] + stats["ducts"] + stats["mep_graph"] < 1:
            missing.append("place_pipe/duct or mep_route between fittings")
        if stats["mep_graph"] < 1 and stats["pipes"] >= 2:
            warnings.append("pipes exist but mep_graph empty — use mep_route for explicit connections")
    elif intent_k in {"structure", "steel"}:
        if stats["columns"] < 1:
            missing.append("place_column with section e.g. W10x33")
    elif intent_k in {"fab_part", "fab", "machine_part"}:
        if stats["fab_parts"] < 1:
            missing.append("create_fab_part + solid features")
        else:
            for e in model.elements:
                if e.category == "fab_part" and not e.params.get("features"):
                    missing.append(f"fab_part {e.id} has no features")
                if e.category == "fab_part" and not e.params.get("gdt"):
                    warnings.append(f"fab_part {e.id} has no GD&T — add gdt_datum/gdt_fcf if inspection intent")
    elif intent_k in {
        "field_device_fab",
        "machine_fab_pack",
        "field_device",
        "vehicle_array",
        "modular_pod",
        "machine_engineering",
    }:
        # PN/layer bar: docs/FIELD_DEVICE_FAB.md
        # Engineering + drawing bar: docs/MACHINE_ENGINEERING_BAR.md
        if stats["equipment"] < 20:
            missing.append(
                f"need ≥20 equipment solids for fab-intent (have {stats['equipment']}) — "
                "one solid per PN/instance, not a single grey box"
            )
        if stats["unique_pns"] < 15:
            missing.append(
                f"need ≥15 unique PN/part tags (have {stats['unique_pns']}) — "
                "parts[] catalog in design basis; set params.pn or part"
            )
        if stats["equipment_kinds"] < 8:
            missing.append(
                f"need ≥8 distinct equipment kinds for viewer layers (have {stats['equipment_kinds']}) — "
                "kind=rail|coil|magnet|flange|shell|… maps to glTF layers"
            )
        service_runs = stats["pipes"] + stats["trays"] + stats["ducts"]
        if service_runs >= 2 and stats["fittings"] < 1:
            missing.append(
                f"need fittings at bends/nozzles (have {stats['fittings']} fittings, "
                f"{service_runs} service runs) — place_fitting elbow/tee/union/flange; "
                "see docs/MACHINE_ENGINEERING_BAR.md"
            )
        if stats["diagonal_runs"] > 0:
            missing.append(
                f"{stats['diagonal_runs']} diagonal pipe/tray/duct run(s) — "
                "route orthogonal doglegs with a fitting at each corner"
            )
        if service_runs >= 2 and stats["connections"] < 1:
            missing.append(
                "service runs exist but mep_graph/connections empty — "
                "call connect() or mep_route so headers and trays land both ends"
            )
        if service_runs >= 2 and stats["hardware_kinds"] < 1:
            missing.append(
                "process machine has no hardware kinds (bolt/flange/door/hinge/nameplate/…) — "
                "envelope-only 3D fails docs/MACHINE_ENGINEERING_BAR.md"
            )
        if stats["fab_parts"] < 1:
            warnings.append(
                "no fab_part BREP — coordination sheets still valid; add create_fab_part + GD&T for fab-intent STEP"
            )
        elif stats["fab_parts"] < 10:
            warnings.append(
                f"only {stats['fab_parts']} fab_parts — prefer one BREP per machined PN for shop-depth packs"
            )
        for e in model.elements:
            if e.category == "fab_part" and not e.params.get("features"):
                missing.append(f"fab_part {e.id} has no features")
        if not any(
            e.params.get("system") for e in equip
        ):
            warnings.append("no params.system on equipment — tag STRUCT|POWER|DIAG|… for schedules")
        if not any(
            e.params.get("product_class") or e.params.get("twin_fidelity") for e in equip
        ):
            warnings.append(
                "set product_class + twin_fidelity=F1 on primary equipment (field_deployable_vehicle_array etc.)"
            )
        if stats["equipment"] >= 20 and stats["hardware_kinds"] < 1:
            warnings.append(
                "no hardware kinds (bolt/flange/door/hinge/nameplate/…) — "
                "envelope-only 3D fails docs/MACHINE_ENGINEERING_BAR.md"
            )
        if stats["equipment"] >= 20 and stats["walls"] == 0 and stats["grids"] < 1:
            warnings.append(
                "no grids on a wall-less machine — author bay grids or let machine_set synthesize"
            )
        if stats["equipment"] >= 20 and stats["walls"] == 0 and not model.meta.get("process_notes"):
            warnings.append(
                "no model.meta['process_notes'] — machine GA cover quotes the freeze"
            )
        display = str(model.meta.get("product") or "").strip()
        if _PN_AS_NAME.match((model.name or "").strip()) and not display:
            warnings.append(
                "project name looks like a P/N prefix — "
                "Project.create(<human product>) or set meta.product (P/Ns stay document IDs)"
            )
    elif intent_k in {"openings"}:
        if stats["doors"] < 1 and sum(1 for e in model.elements if e.category == "window") < 1:
            missing.append("place_door/place_window on host wall")
    else:
        warnings.append(f"unknown intent '{intent}' — used generic stats only")

    ok = len(missing) == 0
    checklist_key = intent_k
    if intent_k in {
        "field_device",
        "vehicle_array",
        "modular_pod",
        "machine_fab_pack",
        "machine_engineering",
    }:
        checklist_key = "field_device_fab" if intent_k != "machine_fab_pack" else "machine_fab_pack"
        if checklist_key not in PRODUCT_REQUIREMENTS:
            checklist_key = "field_device_fab"
    _machine_intents = {
        "field_device_fab",
        "machine_fab_pack",
        "field_device",
        "vehicle_array",
        "modular_pod",
        "machine_engineering",
    }
    return {
        "ok": ok,
        "intent": intent_k,
        "missing": missing,
        "warnings": warnings,
        "stats": stats,
        "checklist": authoring_checklist(
            checklist_key if checklist_key in PRODUCT_REQUIREMENTS else None
        ),
        "next": (
            "export_deliverables(mode='part') + machine_set GA + LAYERS.json/BOM + re-engage index.html"
            if ok and intent_k in _machine_intents
            else (
                "export_deliverables + tell user path to viewer3d.html / index.html"
                if ok
                else "fill missing fields — see docs/MACHINE_ENGINEERING_BAR.md + docs/FIELD_DEVICE_FAB.md"
            )
        ),
    }
