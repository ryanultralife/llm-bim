"""Authoring contracts — explicit required detail so LLMs generate the envisioned product.

Agents should call ``authoring_checklist`` / ``validate_intent`` before large packs.
"""

from __future__ import annotations

from typing import Any

from llmbim_core.model import ProjectModel

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
    "deliverables_pack": {
        "description": "One-shot export users open in browser/CAD",
        "required": ["out_dir or default output/<slug>/"],
        "recommended": [
            "export_deliverables after meaningful edits",
            "verify_pack",
            "commit message for VCS",
            "tell user absolute path to index.html + viewer3d.html",
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
    stats = {
        "levels": len(model.levels),
        "walls": sum(1 for e in model.elements if e.category == "wall"),
        "doors": sum(1 for e in model.elements if e.category == "door"),
        "pipes": sum(1 for e in model.elements if e.category in {"pipe", "plumbing_pipe"}),
        "ducts": sum(1 for e in model.elements if e.category in {"duct", "hvac"}),
        "columns": sum(1 for e in model.elements if e.category == "column"),
        "fab_parts": sum(1 for e in model.elements if e.category == "fab_part"),
        "mep_graph": len(model.meta.get("mep_graph") or []),
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
    elif intent_k in {"openings"}:
        if stats["doors"] < 1 and sum(1 for e in model.elements if e.category == "window") < 1:
            missing.append("place_door/place_window on host wall")
    else:
        warnings.append(f"unknown intent '{intent}' — used generic stats only")

    ok = len(missing) == 0
    return {
        "ok": ok,
        "intent": intent_k,
        "missing": missing,
        "warnings": warnings,
        "stats": stats,
        "checklist": authoring_checklist(intent_k if intent_k in PRODUCT_REQUIREMENTS else None),
        "next": "export_deliverables + tell user path to viewer3d.html / index.html" if ok else "fill missing fields",
    }
