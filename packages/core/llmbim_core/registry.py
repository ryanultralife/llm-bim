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


@register("create_wall", description="Create wall start→end with optional fire_rating", mutates=True)
def _create_wall(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.commands import CreateWall
    from llmbim_core.units import parse_length, point_to_mm

    unit = p.get("unit") or "mm"
    start = p.get("start") or p.get("start_mm") or [0, 0]
    end = p.get("end") or p.get("end_mm") or [3000, 0]
    if unit != "mm":
        start = point_to_mm(start, unit)
        end = point_to_mm(end, unit)
    th = p.get("thickness_mm", p.get("thickness", 200))
    ht = p.get("height_mm", p.get("height", 3000))
    if unit != "mm" and p.get("thickness_mm") is None and p.get("thickness") is not None:
        th = parse_length(th, unit)
    if unit != "mm" and p.get("height_mm") is None and p.get("height") is not None:
        ht = parse_length(ht, unit)
    cmd = CreateWall(
        level=p.get("level") or model.levels[0].name,
        start=(float(start[0]), float(start[1])),
        end=(float(end[0]), float(end[1])),
        thickness_mm=float(th),
        height_mm=float(ht),
        name=str(p.get("name") or ""),
        fire_rating=str(p.get("fire_rating") or ""),
    )
    result = cmd.apply(model)
    type_id = p.get("type_id")
    if type_id:
        el = model.get_element(result["element_id"])
        el.type_id = str(type_id)
        el.params["type_id"] = str(type_id)
    return result


@register(
    "create_rect_shell",
    description="Create four walls of a rectangular shell (x,y,w,d,height_mm)",
    mutates=True,
)
def _create_rect_shell(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.commands import CreateWall

    level = p.get("level") or model.levels[0].name
    x = float(p.get("x") or 0)
    y = float(p.get("y") or 0)
    w = float(p.get("w") or p.get("width_mm") or p.get("width") or 10000)
    d = float(p.get("d") or p.get("depth_mm") or p.get("depth") or 8000)
    th = float(p.get("thickness_mm") or p.get("thickness") or 200)
    ht = float(p.get("height_mm") or p.get("height") or 3000)
    prefix = str(p.get("name_prefix") or p.get("prefix") or "W")
    corners = [
        ((x, y), (x + w, y), f"{prefix}-S"),
        ((x + w, y), (x + w, y + d), f"{prefix}-E"),
        ((x + w, y + d), (x, y + d), f"{prefix}-N"),
        ((x, y + d), (x, y), f"{prefix}-W"),
    ]
    ids: list[str] = []
    for start, end, nm in corners:
        r = CreateWall(
            level=level,
            start=start,
            end=end,
            thickness_mm=th,
            height_mm=ht,
            name=nm,
            fire_rating=str(p.get("fire_rating") or ""),
        ).apply(model)
        ids.append(str(r["element_id"]))
    return {"wall_ids": ids, "count": len(ids), "prefix": prefix}


@register("place_door", description="Place door on host wall (offset/width/height/fire_rating)", mutates=True)
def _place_door(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.commands import PlaceDoor

    host = p.get("host") or p.get("host_id") or p.get("wall")
    if not host:
        raise ValueError("place_door requires host wall element id")
    cmd = PlaceDoor(
        host=str(host),
        offset_mm=float(p.get("offset_mm") if p.get("offset_mm") is not None else p.get("offset") or 1000),
        width_mm=float(p.get("width_mm") if p.get("width_mm") is not None else p.get("width") or 900),
        height_mm=float(p.get("height_mm") if p.get("height_mm") is not None else p.get("height") or 2100),
        name=str(p.get("name") or ""),
        type_id=str(p.get("type_id") or ""),
        fire_rating=str(p.get("fire_rating") or ""),
    )
    return cmd.apply(model)


@register("place_window", description="Place window on host wall (offset/sill/width/height)", mutates=True)
def _place_window(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.commands import PlaceWindow

    host = p.get("host") or p.get("host_id") or p.get("wall")
    if not host:
        raise ValueError("place_window requires host wall element id")
    cmd = PlaceWindow(
        host=str(host),
        offset_mm=float(p.get("offset_mm") if p.get("offset_mm") is not None else p.get("offset") or 1000),
        width_mm=float(p.get("width_mm") if p.get("width_mm") is not None else p.get("width") or 1200),
        height_mm=float(p.get("height_mm") if p.get("height_mm") is not None else p.get("height") or 1200),
        sill_mm=float(p.get("sill_mm") if p.get("sill_mm") is not None else p.get("sill") or 900),
        name=str(p.get("name") or ""),
        type_id=str(p.get("type_id") or ""),
    )
    return cmd.apply(model)


@register("create_room", description="Create room space from boundary polygon (mm)", mutates=True)
def _create_room(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.commands import CreateRoom

    boundary = p.get("boundary") or p.get("boundary_mm") or p.get("polygon") or []
    if len(boundary) < 3:
        raise ValueError("create_room requires boundary with ≥3 points [[x,y],...]")
    pts = [(float(pt[0]), float(pt[1])) for pt in boundary]
    cmd = CreateRoom(
        level=p.get("level") or model.levels[0].name,
        name=str(p.get("name") or "Room"),
        boundary=pts,
        height_mm=float(p["height_mm"]) if p.get("height_mm") is not None else None,
        ceiling_height_mm=float(p["ceiling_height_mm"])
        if p.get("ceiling_height_mm") is not None
        else None,
    )
    return cmd.apply(model)


@register("create_slab", description="Create floor slab from polygon (mm) + thickness", mutates=True)
def _create_slab(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.commands import CreateSlab

    polygon = p.get("polygon") or p.get("polygon_mm") or p.get("boundary") or p.get("boundary_mm") or []
    if len(polygon) < 3:
        raise ValueError("create_slab requires polygon with ≥3 points [[x,y],...]")
    pts = [(float(pt[0]), float(pt[1])) for pt in polygon]
    th = p.get("thickness_mm") if p.get("thickness_mm") is not None else p.get("thickness", 200)
    cmd = CreateSlab(
        level=p.get("level") or model.levels[0].name,
        polygon=pts,
        thickness_mm=float(th),
        name=str(p.get("name") or ""),
    )
    return cmd.apply(model)


@register(
    "create_equipment_box",
    description="Place equipment envelope box/cylinder at origin with size_mm Lx,Ly,Hz",
    mutates=True,
)
def _create_equipment_box(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.commands import CreateEquipmentBox

    origin = p.get("origin") or p.get("origin_mm") or [0, 0]
    size = p.get("size") or p.get("size_mm") or [1000, 1000, 1000]
    if len(size) < 3:
        size = list(size) + [1000] * (3 - len(size))
    cmd = CreateEquipmentBox(
        level=p.get("level") or model.levels[0].name,
        origin=(float(origin[0]), float(origin[1])),
        size=(float(size[0]), float(size[1]), float(size[2])),
        name=str(p.get("name") or ""),
        kind=str(p.get("kind") or "equipment"),
        centered=bool(p.get("centered") or False),
        z0_mm=float(p.get("z0_mm") or 0),
        shape=str(p.get("shape") or "box"),
    )
    return cmd.apply(model)


@register(
    "add_grid",
    description="Add structural grid axis U (X) or V (Y) with positions_mm list",
    mutates=True,
)
def _add_grid(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.commands import AddGrid

    positions = p.get("positions_mm") or p.get("positions") or []
    if isinstance(positions, str):
        positions = [float(x.strip()) for x in positions.replace(";", ",").split(",") if x.strip()]
    if len(positions) < 2:
        raise ValueError("add_grid requires positions_mm with ≥2 values")
    labels = p.get("labels")
    if isinstance(labels, str):
        labels = [x.strip() for x in labels.replace(";", ",").split(",") if x.strip()]
    cmd = AddGrid(
        axis=str(p.get("axis") or "U"),
        positions_mm=[float(x) for x in positions],
        name=str(p.get("name") or ""),
        labels=list(labels) if labels else None,
    )
    return cmd.apply(model)


@register("create_note", description="Place plan text note at position_mm", mutates=True)
def _create_note(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.annotations import CreateNote

    pos = p.get("position") or p.get("position_mm") or p.get("origin") or [0, 0]
    text = p.get("text") or p.get("note") or ""
    if not str(text).strip():
        raise ValueError("create_note requires text")
    cmd = CreateNote(
        level=p.get("level") or model.levels[0].name,
        text=str(text),
        position=(float(pos[0]), float(pos[1])),
        name=str(p.get("name") or ""),
    )
    return cmd.apply(model)


@register("set_type", description="Set element type_id (wall/door marks; may sync thickness)", mutates=True)
def _set_type(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.annotations import SetElementType

    eid = p.get("id") or p.get("element_id") or p.get("host")
    type_id = p.get("type_id") or p.get("type")
    if not eid or not type_id:
        raise ValueError("set_type requires id + type_id")
    return SetElementType(element_id=str(eid), type_id=str(type_id)).apply(model)


@register(
    "set_phase",
    description="Set element phase new|existing|demo|temp (pack phase filters)",
    mutates=True,
)
def _set_phase(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.annotations import SetElementPhase

    eid = p.get("id") or p.get("element_id") or p.get("host")
    phase = p.get("phase") or "new"
    if not eid:
        raise ValueError("set_phase requires id")
    allowed = {"new", "existing", "demo", "temp"}
    if str(phase) not in allowed:
        raise ValueError(f"phase must be one of {sorted(allowed)}")
    return SetElementPhase(element_id=str(eid), phase=str(phase)).apply(model)


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


@register("assign_material", description="Assign material_id to element", mutates=True)
def _assign_material(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import assign_material

    return assign_material(model, p["element_id"], p["material_id"], role=p.get("role") or "primary")


@register("assign_part", description="Assign catalog part_id to element", mutates=True)
def _assign_part(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import assign_part

    qty = p.get("qty")
    return assign_part(
        model,
        p["element_id"],
        p["part_id"],
        qty=float(qty) if qty is not None else None,
        apply_geometry=bool(p.get("apply_geometry")),
    )


@register("auto_assign", description="Auto-assign materials/parts from type/kind", mutates=True)
def _auto_assign(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import auto_assign_all, auto_assign_from_type

    if p.get("element_id"):
        return auto_assign_from_type(model, p["element_id"])
    return auto_assign_all(model)


@register("place_fitting", description="Place plumbing fitting by type+NPS (copper/pvc)", mutates=True)
def _place_fitting(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_fitting

    origin = p.get("origin") or p.get("origin_mm") or [0, 0]
    return place_fitting(
        model,
        level=p.get("level") or model.levels[0].name,
        fitting_type=p["fitting_type"],
        nps=p["nps"],
        origin=origin,
        name=p.get("name"),
        material=p.get("material") or "copper",
        qty=float(p.get("qty") or 1),
        system_tag=p.get("system") or "CW",
    )


@register("place_pipe", description="Place pipe run start→end with NPS", mutates=True)
def _place_pipe(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_pipe

    return place_pipe(
        model,
        level=p.get("level") or model.levels[0].name,
        nps=p["nps"],
        start=p["start"],
        end=p["end"],
        name=p.get("name"),
        material=p.get("material") or "copper",
        system_tag=p.get("system") or "CW",
        z0_mm=float(p.get("z0_mm") or 0),
    )


@register("place_riser", description="Place vertical pipe riser at XY from z0→z1 (optional to_level)", mutates=True)
def _place_riser(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_riser

    origin = p.get("origin") or p.get("origin_mm") or [0, 0]
    z0 = p.get("z0_mm") if p.get("z0_mm") is not None else p.get("z0")
    z1 = p.get("z1_mm") if p.get("z1_mm") is not None else p.get("z1")
    return place_riser(
        model,
        level=p.get("level") or model.levels[0].name,
        nps=p["nps"],
        origin=origin,
        z0_mm=float(z0) if z0 is not None else None,
        z1_mm=float(z1) if z1 is not None else None,
        name=p.get("name"),
        material=p.get("material") or "copper",
        system_tag=p.get("system") or "CW",
        to_level=p.get("to_level"),
    )


@register("place_duct", description="Place rectangular HVAC duct run start→end", mutates=True)
def _place_duct(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_duct

    start = p.get("start") or p.get("start_mm") or [0, 0]
    end = p.get("end") or p.get("end_mm") or [1000, 0]
    return place_duct(
        model,
        level=p.get("level") or model.levels[0].name,
        start=start,
        end=end,
        width_mm=float(p.get("width_mm") or p.get("width") or 400),
        height_mm=float(p.get("height_mm") or p.get("height") or 250),
        name=p.get("name"),
        system_tag=p.get("system") or "SA",
        z0_mm=float(p.get("z0_mm") or 2700),
        material_id=p.get("material_id") or p.get("material") or "galv_steel",
    )


@register("place_conduit", description="Place electrical conduit run start→end", mutates=True)
def _place_conduit(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_conduit

    start = p.get("start") or p.get("start_mm") or [0, 0]
    end = p.get("end") or p.get("end_mm") or [1000, 0]
    return place_conduit(
        model,
        level=p.get("level") or model.levels[0].name,
        start=start,
        end=end,
        trade_size=str(p.get("trade_size") or p.get("nps") or "3/4"),
        name=p.get("name"),
        system_tag=p.get("system") or "P",
        z0_mm=float(p.get("z0_mm") or 2800),
        material_id=p.get("material_id") or p.get("material") or "steel_A36",
    )


@register("place_cable_tray", description="Place cable tray run start→end (CSI 26 05 36)", mutates=True)
def _place_cable_tray(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_cable_tray

    start = p.get("start") or p.get("start_mm") or [0, 0]
    end = p.get("end") or p.get("end_mm") or [1000, 0]
    return place_cable_tray(
        model,
        level=p.get("level") or model.levels[0].name,
        start=start,
        end=end,
        width_mm=float(p.get("width_mm") or p.get("width") or 300),
        height_mm=float(p.get("height_mm") or p.get("height") or 100),
        name=p.get("name"),
        system_tag=p.get("system") or "PWR",
        z0_mm=float(p.get("z0_mm") or 2900),
        material_id=p.get("material_id") or p.get("material") or "galv_steel",
    )


@register("place_wire", description="Place thin wire/conductor run start→end", mutates=True)
def _place_wire(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_wire

    start = p.get("start") or p.get("start_mm") or [0, 0]
    end = p.get("end") or p.get("end_mm") or [1000, 0]
    return place_wire(
        model,
        level=p.get("level") or model.levels[0].name,
        start=start,
        end=end,
        diameter_mm=float(p.get("diameter_mm") or p.get("wire_d_mm") or 6),
        name=p.get("name"),
        material_id=p.get("material_id") or p.get("material") or "copper",
        system_tag=p.get("system") or "PWR",
        z0_mm=float(p.get("z0_mm") or 2900),
    )


@register("place_coil", description="Place helical coil (wound conductor / spring)", mutates=True)
def _place_coil(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_coil

    origin = p.get("origin") or p.get("origin_mm") or [0, 0]
    return place_coil(
        model,
        level=p.get("level") or model.levels[0].name,
        origin=origin,
        coil_radius_mm=float(p.get("coil_radius_mm") or p.get("radius_mm") or 80),
        tube_radius_mm=float(p.get("tube_radius_mm") or 8),
        turns=float(p.get("turns") or 6),
        pitch_mm=float(p.get("pitch_mm") or 24),
        name=p.get("name"),
        material_id=p.get("material_id") or p.get("material") or "copper",
        system_tag=p.get("system") or "PROC",
        z0_mm=float(p.get("z0_mm") or 1000),
        orientation=str(p.get("orientation") or p.get("axis") or "vertical"),
    )


@register("place_bolt", description="Place structural bolt (hex head + shank)", mutates=True)
def _place_bolt(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_bolt

    origin = p.get("origin") or p.get("origin_mm") or [0, 0]
    return place_bolt(
        model,
        level=p.get("level") or model.levels[0].name,
        origin=origin,
        shank_d_mm=float(p.get("shank_d_mm") or p.get("diameter_mm") or 20),
        shank_len_mm=float(p.get("shank_len_mm") or p.get("length_mm") or 60),
        grade=str(p.get("grade") or "A325"),
        name=p.get("name"),
        z0_mm=float(p.get("z0_mm") or 0),
        orientation=str(p.get("orientation") or "vertical"),
    )


# --- Fab BREP + GD&T (CadQuery/OCP feature trees) ---------------------------------


@register("create_fab_part", description="Create fab-grade BREP part (feature tree + GD&T)", mutates=True)
def _create_fab_part(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import create_fab_part

    origin = p.get("origin_mm") or p.get("origin") or [0, 0, 0]
    return create_fab_part(
        model,
        name=str(p.get("name") or "FabPart"),
        material_id=str(p.get("material_id") or p.get("material") or "steel_A36"),
        level=p.get("level"),
        origin_mm=origin,
    )


@register("fab_box", description="Add box solid feature to fab_part", mutates=True)
def _fab_box(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_box

    size = p.get("size_mm") or p.get("size") or [50, 50, 20]
    origin = p.get("origin_mm") or p.get("origin") or [0, 0, 0]
    return fab_box(model, p["element_id"], size_mm=size, origin_mm=origin)


@register("fab_cylinder", description="Add cylinder solid feature to fab_part", mutates=True)
def _fab_cylinder(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_cylinder

    origin = p.get("origin_mm") or p.get("origin") or [0, 0, 0]
    return fab_cylinder(
        model,
        p["element_id"],
        diameter_mm=float(p.get("diameter_mm") or p.get("d_mm") or 20),
        height_mm=float(p.get("height_mm") or p.get("length_mm") or 40),
        origin_mm=origin,
        axis=str(p.get("axis") or "z"),
    )


@register("fab_hole", description="Drill hole feature in fab_part", mutates=True)
def _fab_hole(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_hole

    origin = p.get("origin_mm") or p.get("origin") or [0, 0, 0]
    return fab_hole(
        model,
        p["element_id"],
        diameter_mm=float(p.get("diameter_mm") or p.get("d_mm") or 6),
        depth_mm=float(p["depth_mm"]) if p.get("depth_mm") is not None else None,
        origin_mm=origin,
        direction=str(p.get("direction") or "down"),
    )


@register("fab_fillet", description="Fillet / ease edges on fab_part", mutates=True)
def _fab_fillet(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_fillet

    return fab_fillet(
        model,
        p["element_id"],
        radius_mm=float(p.get("radius_mm") or p.get("radius") or 1),
        selector=str(p.get("selector") or p.get("edges") or "|Z"),
    )


@register("fab_chamfer", description="Chamfer / break edges on fab_part", mutates=True)
def _fab_chamfer(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_chamfer

    return fab_chamfer(
        model,
        p["element_id"],
        distance_mm=float(p.get("distance_mm") or p.get("d_mm") or 1),
        selector=str(p.get("selector") or p.get("edges") or ">Z"),
    )


@register("fab_thread", description="Machine thread (ISO M / designation) on fab_part", mutates=True)
def _fab_thread(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_thread

    origin = p.get("origin_mm") or p.get("origin") or [0, 0, 0]
    return fab_thread(
        model,
        p["element_id"],
        designation=str(p.get("designation") or p.get("thread") or "M10x1.5"),
        length_mm=float(p.get("length_mm") or p.get("depth_mm") or 20),
        origin_mm=origin,
        internal=bool(p.get("internal") or p.get("female")),
        pitch_mm=float(p["pitch_mm"]) if p.get("pitch_mm") is not None else None,
        diameter_mm=float(p["diameter_mm"]) if p.get("diameter_mm") is not None else None,
    )


@register("fab_cut_box", description="Boolean cut box pocket from fab_part (optional rotate_z_deg)", mutates=True)
def _fab_cut_box(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_cut_box

    size = p.get("size_mm") or p.get("size") or [10, 10, 10]
    origin = p.get("origin_mm") or p.get("origin") or [0, 0, 0]
    rot = p.get("rotate_deg") or p.get("rotation_deg")
    return fab_cut_box(
        model,
        p["element_id"],
        size_mm=size,
        origin_mm=origin,
        rotate_z_deg=float(p.get("rotate_z_deg") or 0),
        rotate_deg=rot,
        center=p.get("center"),
    )


@register("gdt_datum", description="Add GD&T datum (A/B/C) to fab_part", mutates=True)
def _gdt_datum(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import gdt_add_datum

    return gdt_add_datum(
        model,
        p["element_id"],
        label=str(p.get("label") or "A"),
        face=str(p.get("face") or "bottom"),
        note=str(p.get("note") or ""),
    )


@register("gdt_fcf", description="Add GD&T feature control frame to fab_part", mutates=True)
def _gdt_fcf(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import gdt_add_fcf

    datums = p.get("datums") or []
    if isinstance(datums, str):
        datums = [d.strip() for d in datums.split("|") if d.strip()]
    return gdt_add_fcf(
        model,
        p["element_id"],
        symbol=str(p.get("symbol") or "position"),
        tolerance=float(p.get("tolerance") or p.get("tol") or 0.1),
        datums=list(datums),
        diameter=bool(p.get("diameter") or p.get("dia")),
        zone=str(p.get("zone") or ""),
        note=str(p.get("note") or ""),
        applies_to=str(p.get("applies_to") or ""),
    )


@register("gdt_size", description="Add size dimension ±tolerance to fab_part", mutates=True)
def _gdt_size(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import gdt_add_size

    return gdt_add_size(
        model,
        p["element_id"],
        dimension=str(p.get("dimension") or "size"),
        nominal=float(p.get("nominal") or 0),
        tol_plus=float(p.get("tol_plus") or p.get("tol") or 0.1),
        tol_minus=float(p["tol_minus"]) if p.get("tol_minus") is not None else None,
        unit=str(p.get("unit") or "mm"),
        note=str(p.get("note") or ""),
    )


@register("export_fab_step", description="Export fab_part feature tree as true OCC STEP BREP", mutates=False)
def _export_fab_step(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import export_fab_part_step

    path = p.get("path") or p.get("out") or "fab_part.step"
    return export_fab_part_step(model, p["element_id"], str(path))


@register("validate_fab", description="Rebuild fab_part BREP to validate feature tree", mutates=False)
def _validate_fab(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import validate_fab_part

    return validate_fab_part(model, p["element_id"])


@register("fab_revolve", description="Add lathe revolve (disk/tube) to fab_part", mutates=True)
def _fab_revolve(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_revolve

    origin = p.get("origin_mm") or p.get("origin") or [0, 0, 0]
    return fab_revolve(
        model,
        p["element_id"],
        radius_mm=float(p.get("radius_mm") or p.get("outer_radius_mm") or 20),
        height_mm=float(p.get("height_mm") or 30),
        inner_radius_mm=float(p.get("inner_radius_mm") or 0),
        origin_mm=origin,
    )


@register("fab_hole_pattern", description="Add rectangular hole pattern to fab_part", mutates=True)
def _fab_hole_pattern(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_hole_pattern

    origin = p.get("origin_mm") or p.get("origin") or [0, 0, 0]
    return fab_hole_pattern(
        model,
        p["element_id"],
        diameter_mm=float(p.get("diameter_mm") or 6),
        origin_mm=origin,
        count_x=int(p.get("count_x") or p.get("nx") or 2),
        count_y=int(p.get("count_y") or p.get("ny") or 1),
        spacing_x_mm=float(p.get("spacing_x_mm") or 20),
        spacing_y_mm=float(p.get("spacing_y_mm") or 20),
        depth_mm=float(p["depth_mm"]) if p.get("depth_mm") is not None else None,
    )


@register("create_fab_assembly", description="Create multi-body fab assembly", mutates=True)
def _create_fab_assembly(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import create_fab_assembly

    return create_fab_assembly(model, name=str(p.get("name") or "FabAssembly"), level=p.get("level"))


@register("fab_assembly_add", description="Add fab_part instance to assembly with placement", mutates=True)
def _fab_assembly_add(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_assembly_add

    origin = p.get("origin_mm") or p.get("origin") or [0, 0, 0]
    rot = p.get("rotation_deg") or p.get("rotation") or [0, 0, 0]
    return fab_assembly_add(
        model,
        p.get("assembly_id") or p["element_id"],
        p["part_id"],
        origin_mm=origin,
        rotation_deg=rot,
        instance_id=p.get("instance_id"),
    )


@register("export_fab_assembly_step", description="Export fab_assembly compound STEP", mutates=False)
def _export_fab_assembly_step(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import export_fab_assembly_step

    path = p.get("path") or p.get("out") or "fab_assembly.step"
    return export_fab_assembly_step(model, p.get("assembly_id") or p["element_id"], str(path))


@register("export_fab_ortho", description="Export fab_part top/front/right SVG views", mutates=False)
def _export_fab_ortho(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import export_fab_ortho_views

    out_dir = p.get("out_dir") or p.get("path") or "fab_views"
    return export_fab_ortho_views(model, p["element_id"], str(out_dir))


@register("fab_tag", description="Name edges/faces for later fillet (selector tag:name)", mutates=True)
def _fab_tag(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_tag

    return fab_tag(
        model,
        p["element_id"],
        name=str(p.get("name") or p.get("tag") or "named"),
        selector=str(p.get("selector") or "|Z"),
        kind=str(p.get("kind") or "edges"),
    )


@register("fab_mate", description="Mate assembly instances (coincident/concentric/offset)", mutates=True)
def _fab_mate(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_mate

    off = p.get("offset_mm") or p.get("offset")
    return fab_mate(
        model,
        p.get("assembly_id") or p["element_id"],
        mate_type=str(p.get("mate_type") or p.get("type") or "coincident"),
        a=str(p.get("a") or p.get("instance_a") or ""),
        b=str(p.get("b") or p.get("instance_b") or ""),
        a_face=str(p.get("a_face") or "top"),
        b_face=str(p.get("b_face") or "bottom"),
        gap_mm=float(p.get("gap_mm") or 0),
        offset_mm=off,
    )


@register(
    "fab_host_to_building",
    description="Knit fab_part into building level/host for glTF+STEP placement",
    mutates=True,
)
def _fab_host_to_building(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.fab import fab_host_to_building

    origin = p.get("origin_mm") or p.get("origin") or [0, 0, 0]
    rot = p.get("rotation_deg") or p.get("rotation") or [0, 0, 0]
    return fab_host_to_building(
        model,
        p["element_id"],
        level=p.get("level"),
        origin_mm=origin,
        z0_mm=float(p["z0_mm"]) if p.get("z0_mm") is not None else None,
        host_id=p.get("host_id") or p.get("host"),
        rotation_deg=rot,
    )


@register(
    "mep_route",
    description="Auto MEP run between two elements (pipe/duct/conduit + graph edge)",
    mutates=True,
)
def _mep_route(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.mep_route import mep_route

    return mep_route(
        model,
        str(p["from_id"]),
        str(p["to_id"]),
        kind=str(p.get("kind") or p.get("route_kind") or "pipe"),  # type: ignore[arg-type]
        nps=str(p.get("nps") or "2"),
        material=str(p.get("material") or "copper"),
        system=str(p.get("system") or "CW"),
        from_port=p.get("from_port"),
        to_port=p.get("to_port"),
        orthogonal=bool(p.get("orthogonal", True)),
        z0_mm=float(p["z0_mm"]) if p.get("z0_mm") is not None else None,
        width_mm=float(p.get("width_mm") or 400),
        height_mm=float(p.get("height_mm") or 250),
        trade_size=str(p.get("trade_size") or p.get("nps") or "3/4"),
        name=str(p.get("name") or ""),
    )


@register("mep_graph", description="List MEP connection graph edges", mutates=False)
def _mep_graph(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.mep_route import mep_graph

    return {"edges": mep_graph(model), "count": len(mep_graph(model))}


@register(
    "authoring_checklist",
    description="Required/recommended fields so LLM collects explicit detail before modeling",
    mutates=False,
)
def _authoring_checklist(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.authoring import authoring_checklist

    return authoring_checklist(p.get("product") or p.get("intent"))


@register(
    "validate_intent",
    description="Check model has enough detail for intent (building_shell|mep_run|fab_part|…)",
    mutates=False,
)
def _validate_intent(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.authoring import validate_intent

    return validate_intent(model, str(p.get("intent") or p.get("product") or "building_shell"))


@register("place_flange", description="Place flange / joined material ring at a joint", mutates=True)
def _place_flange(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_flange

    origin = p.get("origin") or p.get("origin_mm") or [0, 0]
    return place_flange(
        model,
        level=p.get("level") or model.levels[0].name,
        origin=origin,
        od_mm=float(p.get("od_mm") or p.get("diameter_mm") or 150),
        thickness_mm=float(p.get("thickness_mm") or 18),
        name=p.get("name"),
        material_id=p.get("material_id") or p.get("material") or "steel_A36",
        system_tag=p.get("system") or "PROC",
        z0_mm=float(p.get("z0_mm") or 1000),
    )


@register("place_column", description="Place structural steel column (W/HSS section)", mutates=True)
def _place_column(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_column

    origin = p.get("origin") or p.get("origin_mm") or [0, 0]
    return place_column(
        model,
        level=p.get("level") or model.levels[0].name,
        origin=origin,
        section=str(p.get("section") or "W10x33"),
        height_mm=float(p.get("height_mm") or p.get("height") or 3000),
        name=p.get("name"),
        material_id=p.get("material_id") or p.get("material") or "steel_A36",
        rotation_deg=float(p.get("rotation_deg") or p.get("rotation") or 0),
    )


@register("place_beam", description="Place structural steel beam start→end", mutates=True)
def _place_beam(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_beam

    start = p.get("start") or p.get("start_mm") or [0, 0]
    end = p.get("end") or p.get("end_mm") or [3000, 0]
    return place_beam(
        model,
        level=p.get("level") or model.levels[0].name,
        start=start,
        end=end,
        section=str(p.get("section") or "W12x26"),
        name=p.get("name"),
        material_id=p.get("material_id") or p.get("material") or "steel_A36",
        z0_mm=p.get("z0_mm") if p.get("z0_mm") is not None else None,
    )


@register("materials", description="Materials catalog", mutates=False)
def _materials(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.materials import materials_catalog

    return materials_catalog()


@register("parts", description="Parts catalog (filter: category, system, fitting_type, nps, csi)", mutates=False)
def _parts(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.parts_catalog import catalog_summary, list_parts, parts_catalog

    if p.get("filter") or p.get("category") or p.get("fitting_type") or p.get("nps") or p.get("system") or p.get("csi_prefix"):
        rows = list_parts(
            category=p.get("category"),
            fitting_type=p.get("fitting_type"),
            nps=p.get("nps"),
            material=p.get("material"),
            system=p.get("system"),
            csi_prefix=p.get("csi_prefix"),
            section=p.get("section"),
            bar_size=p.get("bar_size"),
        )
        return {"count": len(rows), "parts": [r.model_dump() for r in rows[:200]]}
    if p.get("full"):
        return parts_catalog()
    return catalog_summary()


@register(
    "fitting_takeoff",
    description="Count fittings by type+size+system (copper/fire/process 90° elbows)",
    mutates=False,
)
def _fitting_takeoff(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.material_lists import (
        fire_takeoff,
        fitting_takeoff,
        full_trade_schedule,
        pipe_takeoff,
        plumbing_schedule,
    )

    if p.get("full_schedule") or p.get("trades"):
        return full_trade_schedule(model)
    if p.get("fire"):
        return fire_takeoff(model)
    if p.get("plumbing_only"):
        return plumbing_schedule(model)
    rows = fitting_takeoff(
        model,
        fitting_type=p.get("fitting_type"),
        nps=p.get("nps"),
        material=p.get("material"),
        system=p.get("system"),  # None = all systems
    )
    pipes = pipe_takeoff(model, nps=p.get("nps"), material=p.get("material"))
    return {"fittings": rows, "pipe": pipes, "count_rows": len(rows)}


@register("place_part", description="Place catalog part: toilet, TP dispenser, W10x33, rebar #5", mutates=True)
def _place_part(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.assignment import place_part

    return place_part(
        model,
        level=p.get("level") or model.levels[0].name,
        part_id=p.get("part_id"),
        origin=p.get("origin") or [0, 0],
        name=p.get("name"),
        qty=float(p.get("qty") or 1),
        length_m=p.get("length_m"),
        kind=p.get("kind"),
        section=p.get("section"),
        bar_size=p.get("bar_size") or p.get("bar"),
        category=p.get("category"),
    )


@register("csi_takeoff", description="Cost rollup by CSI MasterFormat code", mutates=False)
def _csi_takeoff(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.csi import csi_catalog
    from llmbim_core.material_lists import csi_takeoff

    if p.get("catalog"):
        return csi_catalog()
    rows = csi_takeoff(model, division=p.get("division"))
    return {"rows": rows, "count": len(rows)}


@register("steel_takeoff", description="Structural steel by section (place_column/beam + catalog)", mutates=False)
def _steel_takeoff(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.material_lists import steel_takeoff

    rows = steel_takeoff(model)
    return {"steel": rows, "count": len(rows)}


@register("duct_takeoff", description="HVAC duct runs: length_m + area_m2 by size", mutates=False)
def _duct_takeoff(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.material_lists import duct_takeoff

    rows = duct_takeoff(model)
    return {"duct": rows, "count": len(rows)}


@register("conduit_takeoff", description="Electrical conduit length by trade size", mutates=False)
def _conduit_takeoff(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.material_lists import conduit_takeoff

    rows = conduit_takeoff(model)
    return {"conduit": rows, "count": len(rows)}


@register("cable_tray_takeoff", description="Cable tray runs: length_m + area by width", mutates=False)
def _cable_tray_takeoff(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.material_lists import cable_tray_takeoff

    rows = cable_tray_takeoff(model)
    return {"cable_tray": rows, "count": len(rows)}


@register(
    "system_takeoff",
    description="Takeoff by trade: fire|process|rebar|steel|duct|conduit|tray|framing|fixture",
    mutates=False,
)
def _system_takeoff(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.material_lists import (
        cable_tray_takeoff,
        conduit_takeoff,
        duct_takeoff,
        fire_takeoff,
        rebar_takeoff,
        steel_takeoff,
        system_takeoff,
    )

    sys = p.get("system") or "all"
    if sys == "fire":
        return fire_takeoff(model)
    if sys in ("steel", "structural_steel"):
        return {"rows": steel_takeoff(model)}
    if sys in ("duct", "hvac"):
        return {"duct": duct_takeoff(model)}
    if sys == "conduit":
        return {"conduit": conduit_takeoff(model)}
    if sys in ("cable_tray", "tray"):
        return {"cable_tray": cable_tray_takeoff(model)}
    if sys == "rebar":
        return {"rows": rebar_takeoff(model)}
    if sys == "all":
        return {"rows": system_takeoff(model, None)}
    return {"rows": system_takeoff(model, sys)}


@register("material_lists", description="Export material/part/fitting lists to folder", mutates=False)
def _material_lists(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.material_lists import export_lists

    out = p.get("out_dir") or p.get("out") or "out/materials"
    written = export_lists(model, out)
    return {"out": out, "files": written}


@register(
    "import_module",
    description="Import another project as block|native|linked module/machine",
    mutates=True,
)
def _import_module(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.modules import import_module

    origin = p.get("origin") or p.get("origin_mm") or [0, 0]
    return import_module(
        model,
        p["path"] if "path" in p else p.get("source"),
        level=p.get("level") or (model.levels[0].name if model.levels else "L1"),
        origin=origin,
        mode=p.get("mode") or "native",
        name=p.get("name"),
        rotation_deg=float(p.get("rotation_deg") or 0),
        z0_mm=float(p.get("z0_mm") or 0),
        kind=p.get("kind") or "fabrication",
    )


@register("export_module", description="Export project/selection as reusable module package", mutates=False)
def _export_module(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.modules import export_as_module

    return export_as_module(
        model,
        p["path"],
        name=p.get("name"),
        element_ids=p.get("element_ids"),
        kind=p.get("kind") or "fabrication",
        ports=p.get("ports"),
    )


@register("explode_block", description="Explode module_instance block to native elements", mutates=True)
def _explode_block(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.modules import explode_block

    return explode_block(model, p["instance_id"] if "instance_id" in p else p["id"])


@register("define_port", description="Define connection port on element (machine nozzle)", mutates=True)
def _define_port(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.modules import define_port

    return define_port(
        model,
        p["element_id"],
        p["name"],
        role=p.get("role") or "process",
        medium=p.get("medium") or "",
        position_mm=p.get("position_mm") or p.get("position"),
        direction=p.get("direction") or "",
    )


@register("connect", description="Connect two module/equipment ports", mutates=True)
def _connect(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.modules import connect

    return connect(
        model,
        p["from_id"],
        p["from_port"],
        p["to_id"],
        p["to_port"],
        medium=p.get("medium") or "process",
        name=p.get("name") or "",
    )


@register("list_modules", description="List module library definitions and instances", mutates=False)
def _list_modules(model: ProjectModel, p: dict[str, Any]) -> dict[str, Any]:
    from llmbim_core.modules import list_connections, list_modules

    data = list_modules(model)
    data["connections"] = list_connections(model)
    return data


# Note: commit/checkout/diff require Project.vcs — use SDK methods, not bare registry
