"""Multi-format import: IFC (subset), DXF, CSV points, JSON batch ops."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from llmbim_core.ids import new_id
from llmbim_core.model import Element, Level, ProjectModel
from llmbim_core.units import parse_length, to_mm


def import_json_batch(model: ProjectModel, path: str | Path) -> dict[str, Any]:
    """Apply a JSON list of ops: [{op, ...params}].

    Supported ops mirror registry + create_wall shorthand.
    """
    from llmbim_core.registry import dispatch

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "ops" in data:
        ops = data["ops"]
    elif isinstance(data, list):
        ops = data
    else:
        raise ValueError("JSON batch must be a list of ops or {ops: [...]}")

    results = []
    for i, op in enumerate(ops):
        name = op.get("op") or op.get("action")
        if not name:
            raise ValueError(f"op[{i}] missing 'op' field")
        params = {k: v for k, v in op.items() if k not in ("op", "action")}
        # shorthands
        if name == "add_level":
            lv = model.add_level(params["name"], parse_length(params.get("elevation", params.get("elevation_mm", 0))))
            results.append({"op": name, "level_id": lv.id})
            continue
        if name == "create_wall":
            from llmbim_geometry.primitives import wall_length_mm

            unit = params.get("unit", model.units)
            start = params["start"]
            end = params["end"]
            s = (parse_length(start[0], unit), parse_length(start[1], unit))
            e = (parse_length(end[0], unit), parse_length(end[1], unit))
            lv = model.get_level(params["level"])
            length = wall_length_mm(s, e)
            el = Element(
                id=new_id("wal"),
                category="wall",
                name=params.get("name") or "",
                level_id=lv.id,
                type_id=params.get("type_id"),
                params={
                    "start_mm": [s[0], s[1]],
                    "end_mm": [e[0], e[1]],
                    "thickness_mm": parse_length(params.get("thickness", params.get("thickness_mm", 200)), unit),
                    "height_mm": parse_length(params.get("height", params.get("height_mm", 3000)), unit),
                    "length_mm": length,
                    "phase": params.get("phase", "new"),
                },
            )
            model.add_element(el)
            results.append({"op": name, "element_id": el.id})
            continue
        results.append({"op": name, "result": dispatch(model, name, params)})
    return {"applied": len(results), "results": results}


def import_csv_points(model: ProjectModel, path: str | Path, *, level: str, as_category: str = "equipment") -> dict[str, Any]:
    """CSV with columns x,y[,z][,name][,kind] — place points as equipment boxes or markers."""
    lv = model.get_level(level)
    created = []
    with Path(path).open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            x = parse_length(row.get("x") or row.get("X") or 0)
            y = parse_length(row.get("y") or row.get("Y") or 0)
            z = parse_length(row.get("z") or row.get("Z") or 0)
            name = row.get("name") or row.get("Name") or ""
            kind = row.get("kind") or "marker"
            size = parse_length(row.get("size") or 500)
            el = Element(
                id=new_id("eqp"),
                category=as_category,
                name=name,
                level_id=lv.id,
                params={
                    "kind": kind,
                    "shape": "box",
                    "origin_mm": [x - size / 2, y - size / 2],
                    "size_mm": [size, size, size],
                    "z0_mm": z,
                    "polygon_mm": [
                        [x - size / 2, y - size / 2],
                        [x + size / 2, y - size / 2],
                        [x + size / 2, y + size / 2],
                        [x - size / 2, y + size / 2],
                    ],
                    "phase": "new",
                },
            )
            model.add_element(el)
            created.append(el.id)
    return {"created": len(created), "ids": created}


def import_dxf_lines(model: ProjectModel, path: str | Path, *, level: str, as_walls: bool = True) -> dict[str, Any]:
    """Very small DXF LINE importer → walls or generic lines."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    # pair group code / value
    pairs = []
    i = 0
    while i < len(lines) - 1:
        try:
            code = int(lines[i].strip())
            val = lines[i + 1].strip()
            pairs.append((code, val))
        except ValueError:
            pass
        i += 2

    entities = []
    cur = None
    for code, val in pairs:
        if code == 0:
            if cur and cur.get("type") == "LINE":
                entities.append(cur)
            cur = {"type": val}
        elif cur is not None:
            if code == 10:
                cur["x1"] = float(val)
            elif code == 20:
                cur["y1"] = float(val)
            elif code == 11:
                cur["x2"] = float(val)
            elif code == 21:
                cur["y2"] = float(val)
            elif code == 8:
                cur["layer"] = val
    if cur and cur.get("type") == "LINE":
        entities.append(cur)

    lv = model.get_level(level)
    created = []
    for ent in entities:
        if "x1" not in ent or "x2" not in ent:
            continue
        if as_walls:
            from llmbim_geometry.primitives import wall_length_mm

            s = (ent["x1"], ent["y1"])
            e = (ent["x2"], ent["y2"])
            try:
                length = wall_length_mm(s, e)
            except Exception:
                continue
            el = Element(
                id=new_id("wal"),
                category="wall",
                name=ent.get("layer") or "",
                level_id=lv.id,
                params={
                    "start_mm": [s[0], s[1]],
                    "end_mm": [e[0], e[1]],
                    "thickness_mm": 200.0,
                    "height_mm": 3000.0,
                    "length_mm": length,
                    "phase": "existing",
                    "source": "dxf",
                },
            )
        else:
            el = Element(
                id=new_id("lin"),
                category="line",
                name=ent.get("layer") or "",
                level_id=lv.id,
                params={
                    "start_mm": [ent["x1"], ent["y1"]],
                    "end_mm": [ent["x2"], ent["y2"]],
                    "source": "dxf",
                },
            )
        model.add_element(el)
        created.append(el.id)
    return {"created": len(created), "ids": created}


def import_ifc_subset(model: ProjectModel, path: str | Path) -> dict[str, Any]:
    """Import a subset of IFC4 SPF: storeys, walls (extruded if simple), spaces by name.

    Not a full IFC kernel — extracts usable placement/name for coordination.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    # IfcBuildingStorey names + elevation
    storeys = re.findall(
        r"IFCBUILDINGSTOREY\('([^']*)'.*?,'(.*?)'.*?,\.ELEMENT\.,([-+eE0-9.]+)\)",
        text,
        re.IGNORECASE,
    )
    # fallback simpler
    if not storeys:
        storeys = re.findall(
            r"IFCBUILDINGSTOREY\([^;]*?'([^']+)'[^;]*?([-+eE0-9.]+)\)",
            text,
            re.IGNORECASE,
        )
        storeys = [( "", n, e) for n, e in storeys] if storeys and len(storeys[0]) == 2 else storeys

    created_levels = 0
    for s in storeys:
        if len(s) == 3:
            _guid, name, elev = s
        else:
            continue
        name = name or f"Storey_{created_levels+1}"
        try:
            elev_f = float(elev)
        except ValueError:
            elev_f = 0.0
        # IFC often uses metres
        elev_mm = elev_f * 1000 if abs(elev_f) < 500 else elev_f
        if not any(lv.name == name for lv in model.levels):
            model.add_level(name, elev_mm)
            created_levels += 1

    if not model.levels:
        model.add_level("L1", 0)
        created_levels = 1

    # Wall names
    walls = re.findall(r"IFCWALL(?:STANDARDCASE)?\('([^']*)',\s*#[0-9]+,\s*'([^']*)'", text, re.I)
    created_walls = 0
    lv = model.levels[0]
    for i, (_g, name) in enumerate(walls[:500]):
        # placeholder wall segment along X — user can edit; mark source ifc
        x0 = i * 1000.0
        el = Element(
            id=new_id("wal"),
            category="wall",
            name=name or f"IFC-Wall-{i}",
            level_id=lv.id,
            params={
                "start_mm": [x0, 0.0],
                "end_mm": [x0 + 1000.0, 0.0],
                "thickness_mm": 200.0,
                "height_mm": 3000.0,
                "length_mm": 1000.0,
                "phase": "existing",
                "source": "ifc",
                "ifc_placeholder": True,
            },
        )
        model.add_element(el)
        created_walls += 1

    spaces = re.findall(r"IFCSPACE\('([^']*)',\s*#[0-9]+,\s*'([^']*)'", text, re.I)
    created_spaces = 0
    for i, (_g, name) in enumerate(spaces[:200]):
        x0 = (i % 10) * 5000.0
        y0 = (i // 10) * 5000.0
        el = Element(
            id=new_id("rom"),
            category="room",
            name=name or f"Space-{i}",
            level_id=lv.id,
            params={
                "boundary_mm": [
                    [x0, y0],
                    [x0 + 4000, y0],
                    [x0 + 4000, y0 + 4000],
                    [x0, y0 + 4000],
                ],
                "area_mm2": 16_000_000.0,
                "source": "ifc",
                "ifc_placeholder": True,
            },
        )
        model.add_element(el)
        created_spaces += 1

    return {
        "levels": created_levels,
        "walls": created_walls,
        "spaces": created_spaces,
        "note": "IFC import is coordination-grade; walls/spaces may be placeholders if geometry not extruded in SPF text",
    }


def auto_import(model: ProjectModel, path: str | Path, **kwargs: Any) -> dict[str, Any]:
    """Dispatch import by file extension."""
    p = Path(path)
    # Directory pack / module package
    if p.is_dir():
        mode = kwargs.get("mode")
        if mode in ("block", "native", "linked") or (p / "MODULE.json").is_file():
            from llmbim_core.modules import import_module

            level = kwargs.get("level") or (model.levels[0].name if model.levels else None)
            if not level:
                model.add_level("L1", 0)
                level = "L1"
            origin = kwargs.get("origin") or kwargs.get("origin_mm") or (0.0, 0.0)
            return import_module(
                model,
                p,
                level=level,
                origin=origin,
                mode=mode or "native",
                name=kwargs.get("name"),
                rotation_deg=float(kwargs.get("rotation_deg") or 0),
                z0_mm=float(kwargs.get("z0_mm") or 0),
                kind=kwargs.get("kind") or "fabrication",
            )
        other = ProjectModel.open(_resolve_dir_model(p))
        return merge_project(model, other)

    ext = p.suffix.lower()
    if ext in {".json"}:
        # project file or batch
        data = json.loads(p.read_text(encoding="utf-8"))
        if "schema_version" in data or ("elements" in data and "levels" in data):
            # full project merge
            other = ProjectModel.from_dict(data)
            return merge_project(model, other)
        return import_json_batch(model, p)
    if ext in {".csv", ".tsv"}:
        level = kwargs.get("level") or (model.levels[0].name if model.levels else None)
        if not level:
            model.add_level("L1", 0)
            level = "L1"
        return import_csv_points(model, p, level=level)
    if ext == ".dxf":
        level = kwargs.get("level") or (model.levels[0].name if model.levels else None)
        if not level:
            model.add_level("L1", 0)
            level = "L1"
        return import_dxf_lines(model, p, level=level)
    if ext in {".ifc", ".ifczip"}:
        return import_ifc_subset(model, p)
    if ext in {".step", ".stp"}:
        from llmbim_geometry.step_import import import_step_as_equipment

        level = kwargs.get("level") or (model.levels[0].name if model.levels else None)
        if not level:
            model.add_level("L1", 0)
            level = "L1"
        el = import_step_as_equipment(model, p, level=level, name=kwargs.get("name"))
        return {"equipment_id": el.id, "name": el.name}
    if ext == ".llmbim.json" or p.name.endswith(".llmbim.json"):
        mode = kwargs.get("mode")  # block | native | linked — optional
        if mode in ("block", "native", "linked"):
            from llmbim_core.modules import import_module

            level = kwargs.get("level") or (model.levels[0].name if model.levels else None)
            if not level:
                model.add_level("L1", 0)
                level = "L1"
            origin = kwargs.get("origin") or kwargs.get("origin_mm") or (0.0, 0.0)
            return import_module(
                model,
                p,
                level=level,
                origin=origin,
                mode=mode,
                name=kwargs.get("name"),
                rotation_deg=float(kwargs.get("rotation_deg") or 0),
                z0_mm=float(kwargs.get("z0_mm") or 0),
                kind=kwargs.get("kind") or "fabrication",
            )
        other = ProjectModel.open(p)
        return merge_project(model, other)
    raise ValueError(f"Unsupported import type: {ext}")


def _resolve_dir_model(path: Path) -> Path:
    cand = path / "model.llmbim.json"
    if cand.is_file():
        return cand
    hits = list(path.glob("*.llmbim.json"))
    if hits:
        return hits[0]
    raise FileNotFoundError(f"No model in {path}")


def merge_project(target: ProjectModel, source: ProjectModel) -> dict[str, Any]:
    """Merge source elements into target (new ids if collision)."""
    id_map: dict[str, str] = {}
    # levels by name
    for lv in source.levels:
        existing = next((x for x in target.levels if x.name == lv.name), None)
        if existing:
            id_map[lv.id] = existing.id
        else:
            nl = target.add_level(lv.name, lv.elevation_mm)
            id_map[lv.id] = nl.id
    added = 0
    for el in source.elements:
        new_id = el.id if not any(e.id == el.id for e in target.elements) else new_id_for(el.category)
        id_map[el.id] = new_id
        ne = el.model_copy(deep=True)
        ne.id = new_id
        if ne.level_id and ne.level_id in id_map:
            ne.level_id = id_map[ne.level_id]
        if ne.host_id and ne.host_id in id_map:
            ne.host_id = id_map[ne.host_id]
        target.add_element(ne)
        added += 1
    return {"merged_elements": added, "levels": len(target.levels)}


def new_id_for(category: str) -> str:
    prefix = {
        "wall": "wal",
        "slab": "slb",
        "door": "dor",
        "window": "wnd",
        "room": "rom",
        "equipment": "eqp",
        "note": "nte",
    }.get(category, "el")
    return new_id(prefix)
