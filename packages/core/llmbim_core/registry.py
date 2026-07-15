"""Extensible command registry — agents can invoke any registered op by name."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from llmbim_core.model import ProjectModel

Handler = Callable[[ProjectModel, dict[str, Any]], dict[str, Any]]


@dataclass
class OpSpec:
    name: str
    handler: Handler
    description: str = ""
    mutates: bool = True


_OPS: dict[str, OpSpec] = {}


def register(name: str, *, description: str = "", mutates: bool = True):
    def deco(fn: Handler) -> Handler:
        _OPS[name] = OpSpec(name=name, handler=fn, description=description, mutates=mutates)
        return fn

    return deco


def list_ops() -> list[dict[str, Any]]:
    return [
        {"name": s.name, "description": s.description, "mutates": s.mutates}
        for s in sorted(_OPS.values(), key=lambda x: x.name)
    ]


def ops_schema() -> dict[str, Any]:
    """JSON Schema-ish catalog for LLM tool calling (any client)."""
    # Ensure builtins registered
    _ = _OPS
    props_common = {
        "type": "object",
        "additionalProperties": True,
        "description": "Op-specific parameters (see description)",
    }
    tools = []
    for s in sorted(_OPS.values(), key=lambda x: x.name):
        tools.append(
            {
                "name": s.name,
                "description": s.description or s.name,
                "mutates": s.mutates,
                "parameters": props_common,
            }
        )
    # High-level façade ops (not all are registry-only)
    facade = [
        {
            "name": "project.create",
            "description": "Create empty project (SDK: Project.create)",
            "mutates": True,
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "units": {"type": "string"}},
            },
        },
        {
            "name": "project.export_deliverables",
            "description": "Full pack IFC/STEP/glTF/PDF/BOQ/DXF",
            "mutates": False,
            "parameters": {
                "type": "object",
                "properties": {
                    "out_dir": {"type": "string"},
                    "mode": {"type": "string", "enum": ["auto", "facility", "part", "both"]},
                },
                "required": ["out_dir"],
            },
        },
        {
            "name": "project.from_template",
            "description": "office_bay|warehouse|hot_cell_bay|lab_bench",
            "mutates": True,
            "parameters": {
                "type": "object",
                "properties": {"template_id": {"type": "string"}},
                "required": ["template_id"],
            },
        },
        {
            "name": "project.import_file",
            "description": "Import by extension: dxf/ifc/step/csv/json",
            "mutates": True,
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "level": {"type": "string"}},
                "required": ["path"],
            },
        },
    ]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "llm-bim agent tools",
        "version": "0.1.0a0",
        "skill": "skills/llm-bim/SKILL.md",
        "tools": facade + tools,
    }


def write_ops_schema(path: str) -> str:
    import json
    from pathlib import Path

    data = ops_schema()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return str(p)


def dispatch(model: ProjectModel, op: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if op not in _OPS:
        raise KeyError(f"Unknown op {op!r}. Available: {sorted(_OPS)}")
    return _OPS[op].handler(model, params or {})


# --- built-in ops registered at import ----------------------------------------


@register("stats", description="Element counts", mutates=False)
def _stats(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    return model.stats()


@register("query", description="Filter elements", mutates=False)
def _query(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    els = model.query(
        category=p.get("category"),
        level=p.get("level"),
        host_id=p.get("host_id"),
    )
    return {"count": len(els), "elements": [e.model_dump() for e in els]}


@register("validate", description="Run integrity validation", mutates=False)
def _validate(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.validate import validate_model

    issues = [i.to_dict() for i in validate_model(model)]
    return {"issues": issues, "ok": not any(i["severity"] == "error" for i in issues)}


@register("set_param", description="Set arbitrary param on element", mutates=True)
def _set_param(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    el = model.get_element(p["id"])
    key = p["key"]
    el.params[key] = p["value"]
    return {"id": el.id, "key": key, "value": p["value"]}


@register("create_generic", description="Create element of any category", mutates=True)
def _create_generic(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.ids import new_id
    from llmbim_core.model import Element

    cat = p.get("category") or "custom"
    level_id = None
    if p.get("level"):
        level_id = model.get_level(p["level"]).id
    el = Element(
        id=p.get("id") or new_id(cat[:3] if len(cat) >= 3 else "el"),
        category=cat,
        name=p.get("name") or "",
        level_id=level_id,
        host_id=p.get("host_id"),
        type_id=p.get("type_id"),
        params=dict(p.get("params") or {}),
    )
    model.add_element(el)
    return {"id": el.id, "category": cat}


@register("delete", description="Delete element (cascade hosted)", mutates=True)
def _delete(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.commands import DeleteElement

    cmd = DeleteElement(element_id=p["id"], cascade=p.get("cascade", True))
    return cmd.apply(model)


@register("boq", description="Bill of quantities", mutates=False)
def _boq(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.quantities import boq_summary, compute_boq

    rows = compute_boq(model)
    return {"summary": boq_summary(rows), "lines": rows if p.get("full") else rows[:50]}


@register("clash", description="AABB clashes", mutates=False)
def _clash(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.clash import find_clashes

    c = find_clashes(model)
    return {"count": len(c), "clashes": c}


@register("rules", description="Design rules", mutates=False)
def _rules(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.rules import rules_summary, run_design_rules

    f = run_design_rules(model)
    return {"summary": rules_summary(f), "findings": f}


@register("repair", description="Auto-repair common model issues", mutates=True)
def _repair(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.repair import repair_model

    return repair_model(model)


@register("ql", description="Query language string", mutates=False)
def _ql(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.query_lang import run_query

    els = run_query(model, p.get("q") or "")
    return {"count": len(els), "elements": [e.model_dump() for e in els[:200]]}


@register("add_level", description="Add building level", mutates=True)
def _add_level(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.units import parse_length

    elev = p.get("elevation_mm", p.get("elevation", 0))
    elev_mm = parse_length(elev, p.get("unit", "mm"))
    lv = model.add_level(p["name"], elev_mm)
    return {"level_id": lv.id, "name": lv.name, "elevation_mm": lv.elevation_mm}


@register("create_assembly", description="Group elements into named assembly", mutates=True)
def _create_assembly(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.ids import new_id
    from llmbim_core.model import Assembly

    a = Assembly(
        id=new_id("asm"),
        name=p.get("name") or "Assembly",
        element_ids=list(p.get("element_ids") or []),
        kind=p.get("kind") or "group",
        params=dict(p.get("params") or {}),
    )
    model.assemblies.append(a)
    return {"assembly_id": a.id, "name": a.name, "count": len(a.element_ids)}


@register("list_assemblies", description="List assemblies", mutates=False)
def _list_assemblies(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    return {
        "assemblies": [
            {"id": a.id, "name": a.name, "kind": a.kind, "count": len(a.element_ids)}
            for a in model.assemblies
        ]
    }


@register("export_pack", description="Write deliverables pack to out_dir", mutates=False)
def _export_pack(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_drawings.deliverables import export_deliverables

    out = p.get("out_dir") or p.get("out") or "out/pack"
    man = export_deliverables(
        model,
        out,
        mode=p.get("mode") or "auto",
        plan_level=p.get("level"),
        plan_scale=p.get("scale"),
    )
    return {"out": out, "ok": man.get("ok"), "stats": man.get("stats")}


@register("catalog", description="Type catalog wall/door/window", mutates=False)
def _catalog(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.types_catalog import catalog_dict

    return catalog_dict()


@register("design_option", description="Clone elements into a design option assembly", mutates=True)
def _design_option(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.options import create_design_option

    return create_design_option(
        model,
        name=p.get("name") or "Option",
        element_ids=p.get("element_ids"),
        clone=p.get("clone", True),
    )


# Note: commit/checkout/diff require Project.vcs — use SDK methods, not bare registry
