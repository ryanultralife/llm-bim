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
