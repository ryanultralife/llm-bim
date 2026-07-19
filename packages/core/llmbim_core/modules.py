"""Reusable modules / blocks / machines nested into host models.

Modes when importing a drawing or project into another:

- **block** — single instance element + embedded definition (like a CAD block).
  Nested geometry is virtual until exploded or expanded for export.
- **native** — explode: all source elements copied into host with new ids
  (editable fabrication design in place).
- **linked** — block-like instance that also stores source path for re-sync.

Machines / fabrications can declare **ports** (process, power, drain, …)
and **connect** to other modules or host equipment.

Honesty: connections are semantic + schedule/graph data for agents — not a
full hydraulic/electrical solver.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Literal

from llmbim_core.errors import NotFoundError, ValidationError
from llmbim_core.ids import new_id
from llmbim_core.model import Assembly, Element, ProjectModel

ImportMode = Literal["block", "native", "linked"]


def _resolve_model_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_dir():
        cand = p / "model.llmbim.json"
        if cand.is_file():
            return cand
        # any .llmbim.json
        hits = list(p.glob("*.llmbim.json"))
        if hits:
            return hits[0]
        raise FileNotFoundError(f"No model.llmbim.json in {p}")
    if not p.is_file():
        raise FileNotFoundError(str(p))
    return p


def open_module_source(path: str | Path) -> ProjectModel:
    """Open a project file or pack directory as a module source model."""
    return ProjectModel.open(_resolve_model_path(path))


def _bbox_xy(model: ProjectModel) -> tuple[float, float, float, float]:
    """Rough plan bbox from walls/equipment/polygons."""
    xs: list[float] = []
    ys: list[float] = []
    for el in model.elements:
        p = el.params
        if "start_mm" in p and "end_mm" in p:
            xs += [float(p["start_mm"][0]), float(p["end_mm"][0])]
            ys += [float(p["start_mm"][1]), float(p["end_mm"][1])]
        if "origin_mm" in p:
            xs.append(float(p["origin_mm"][0]))
            ys.append(float(p["origin_mm"][1]))
            if "size_mm" in p:
                s = p["size_mm"]
                xs.append(float(p["origin_mm"][0]) + float(s[0]))
                ys.append(float(p["origin_mm"][1]) + float(s[1]))
        if "polygon_mm" in p:
            for pt in p["polygon_mm"]:
                xs.append(float(pt[0]))
                ys.append(float(pt[1]))
        if "position_mm" in p:
            xs.append(float(p["position_mm"][0]))
            ys.append(float(p["position_mm"][1]))
    if not xs:
        return 0.0, 0.0, 1000.0, 1000.0
    return min(xs), min(ys), max(xs), max(ys)


def module_envelope_mm(model: ProjectModel) -> list[float]:
    """Return [L, W, H] envelope for block display."""
    x0, y0, x1, y1 = _bbox_xy(model)
    L = max(x1 - x0, 100.0)
    W = max(y1 - y0, 100.0)
    H = 3000.0
    for el in model.elements:
        if el.params.get("height_mm"):
            H = max(H, float(el.params["height_mm"]))
        if el.params.get("size_mm") and len(el.params["size_mm"]) >= 3:
            H = max(H, float(el.params["size_mm"][2]))
    return [L, W, H]


def _rot(x: float, y: float, deg: float) -> tuple[float, float]:
    if not deg:
        return x, y
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return x * c - y * s, x * s + y * c


def transform_point(
    pt: list[float] | tuple[float, float],
    *,
    origin: tuple[float, float],
    rotation_deg: float = 0.0,
    source_origin: tuple[float, float] = (0.0, 0.0),
) -> list[float]:
    """Map a point from source local coords into host plan."""
    x = float(pt[0]) - source_origin[0]
    y = float(pt[1]) - source_origin[1]
    x, y = _rot(x, y, rotation_deg)
    return [x + origin[0], y + origin[1]]


def transform_element_params(
    params: dict[str, Any],
    *,
    origin: tuple[float, float],
    rotation_deg: float = 0.0,
    source_origin: tuple[float, float] = (0.0, 0.0),
    z0_delta: float = 0.0,
) -> dict[str, Any]:
    """Deep-copy and transform geometric params into host space."""
    p = copy.deepcopy(params)
    so = source_origin
    o = origin
    rot = rotation_deg

    def tp(pt: Any) -> list[float]:
        return transform_point(pt, origin=o, rotation_deg=rot, source_origin=so)

    for key in ("start_mm", "end_mm", "origin_mm", "position_mm"):
        if key in p and isinstance(p[key], (list, tuple)) and len(p[key]) >= 2:
            p[key] = tp(p[key])
    if "polygon_mm" in p and isinstance(p["polygon_mm"], list):
        p["polygon_mm"] = [tp(pt) for pt in p["polygon_mm"] if isinstance(pt, (list, tuple))]
    if "boundary" in p and isinstance(p["boundary"], list):
        p["boundary"] = [tp(pt) for pt in p["boundary"] if isinstance(pt, (list, tuple))]
    if z0_delta and "z0_mm" in p:
        p["z0_mm"] = float(p["z0_mm"]) + z0_delta
    elif z0_delta:
        p["z0_mm"] = z0_delta
    # length along plan for walls after transform
    if "start_mm" in p and "end_mm" in p:
        try:
            from llmbim_geometry.primitives import wall_length_mm

            p["length_mm"] = wall_length_mm(
                (float(p["start_mm"][0]), float(p["start_mm"][1])),
                (float(p["end_mm"][0]), float(p["end_mm"][1])),
            )
        except Exception:  # noqa: BLE001
            pass
    return p


def _ensure_level(host: ProjectModel, level: str) -> str:
    try:
        return host.get_level(level).id
    except NotFoundError:
        lv = host.add_level(level, 0.0)
        return lv.id


def _library(host: ProjectModel) -> dict[str, Any]:
    lib = host.meta.setdefault("module_library", {})
    if not isinstance(lib, dict):
        host.meta["module_library"] = {}
        lib = host.meta["module_library"]
    return lib


def _connections(host: ProjectModel) -> list[dict[str, Any]]:
    con = host.meta.setdefault("connections", [])
    if not isinstance(con, list):
        host.meta["connections"] = []
        con = host.meta["connections"]
    return con


def extract_ports(model: ProjectModel) -> list[dict[str, Any]]:
    """Collect ports from element params and model.meta."""
    ports: list[dict[str, Any]] = []
    for el in model.elements:
        for port in el.params.get("ports") or []:
            if isinstance(port, dict):
                ports.append(
                    {
                        **port,
                        "element_id": el.id,
                        "element_name": el.name,
                    }
                )
    for port in model.meta.get("ports") or []:
        if isinstance(port, dict):
            ports.append(dict(port))
    return ports


def define_port(
    model: ProjectModel,
    element_id: str,
    name: str,
    *,
    role: str = "process",  # process | power | drain | data | structural | other
    medium: str = "",
    position_mm: list[float] | tuple[float, float] | None = None,
    direction: str = "",
) -> dict[str, Any]:
    """Attach a named connection port to an element (machine nozzle, etc.)."""
    el = model.get_element(element_id)
    ports = list(el.params.get("ports") or [])
    ports = [p for p in ports if p.get("name") != name]
    port = {
        "name": name,
        "role": role,
        "medium": medium or role,
        "position_mm": list(position_mm) if position_mm is not None else el.params.get("origin_mm") or [0, 0],
        "direction": direction,
    }
    ports.append(port)
    el.params["ports"] = ports
    # also index at model meta for quick lookup
    meta_ports = list(model.meta.get("ports") or [])
    meta_ports = [p for p in meta_ports if not (p.get("element_id") == element_id and p.get("name") == name)]
    meta_ports.append({**port, "element_id": element_id})
    model.meta["ports"] = meta_ports
    return {"element_id": element_id, "port": port}


def export_as_module(
    model: ProjectModel,
    path: str | Path,
    *,
    name: str | None = None,
    element_ids: list[str] | None = None,
    kind: str = "fabrication",  # block | fabrication | machine
    ports: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Write a reusable module package (.llmbim.json or directory).

    If ``element_ids`` is set, only those elements (+ levels they use) are exported.
    """
    path = Path(path)
    subset = model
    if element_ids is not None:
        idset = set(element_ids)
        els = [el.model_copy(deep=True) for el in model.elements if el.id in idset]
        level_ids = {el.level_id for el in els if el.level_id}
        levels = [lv.model_copy(deep=True) for lv in model.levels if lv.id in level_ids]
        subset = ProjectModel(
            name=name or f"{model.name} module",
            units=model.units,
            levels=levels or [lv.model_copy(deep=True) for lv in model.levels[:1]],
            elements=els,
            assemblies=[],
            meta={
                "module": {
                    "kind": kind,
                    "source_project": model.name,
                    "source_id": model.id,
                },
                "ports": ports or extract_ports(model),
            },
        )
    else:
        subset = model.model_copy(deep=True)
        subset.name = name or model.name
        subset.meta = dict(subset.meta)
        subset.meta["module"] = {
            "kind": kind,
            "source_project": model.name,
            "source_id": model.id,
        }
        if ports is not None:
            subset.meta["ports"] = ports
        elif "ports" not in subset.meta:
            subset.meta["ports"] = extract_ports(model)

    if path.suffix.lower() in {".json", ".llmbim"} or path.name.endswith(".llmbim.json"):
        path.parent.mkdir(parents=True, exist_ok=True)
        subset.save(path)
        out_path = path
    else:
        path.mkdir(parents=True, exist_ok=True)
        out_path = path / "model.llmbim.json"
        subset.save(out_path)
        (path / "MODULE.json").write_text(
            json.dumps(
                {
                    "name": subset.name,
                    "kind": kind,
                    "envelope_mm": module_envelope_mm(subset),
                    "element_count": len(subset.elements),
                    "ports": subset.meta.get("ports") or [],
                    "honesty": "ENGINEERING ESTIMATE module package",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return {
        "path": str(out_path),
        "name": subset.name,
        "kind": kind,
        "elements": len(subset.elements),
        "envelope_mm": module_envelope_mm(subset),
        "ports": len(subset.meta.get("ports") or []),
    }


def register_module_definition(
    host: ProjectModel,
    source: ProjectModel | str | Path,
    *,
    module_id: str | None = None,
    name: str | None = None,
    kind: str = "fabrication",
) -> dict[str, Any]:
    """Store a module definition in host.meta.module_library for block instances."""
    if isinstance(source, (str, Path)):
        src = open_module_source(source)
        source_path = str(_resolve_model_path(source))
    else:
        src = source
        source_path = None
    mid = module_id or new_id("mod")
    lib = _library(host)
    snap = src.to_dict()
    entry = {
        "id": mid,
        "name": name or src.name,
        "kind": kind or (src.meta.get("module") or {}).get("kind") or "fabrication",
        "source_path": source_path,
        "envelope_mm": module_envelope_mm(src),
        "ports": src.meta.get("ports") or extract_ports(src),
        "element_count": len(src.elements),
        "definition": snap,
    }
    lib[mid] = entry
    return {"module_id": mid, "name": entry["name"], "envelope_mm": entry["envelope_mm"]}


def import_module(
    host: ProjectModel,
    source: ProjectModel | str | Path,
    *,
    level: str,
    origin: tuple[float, float] | list[float] = (0.0, 0.0),
    mode: ImportMode = "native",
    name: str | None = None,
    rotation_deg: float = 0.0,
    z0_mm: float = 0.0,
    kind: str = "fabrication",  # block | fabrication | machine
    module_id: str | None = None,
    source_origin: tuple[float, float] | list[float] | None = None,
) -> dict[str, Any]:
    """Import a project/module into the host model.

    - mode=native: copy elements (editable fabrication in host)
    - mode=block: single block instance + definition in library
    - mode=linked: block + retain source_path for re-sync
    """
    source_path: str | None = None
    if isinstance(source, (str, Path)):
        source_path = str(_resolve_model_path(source))
        src = open_module_source(source)
    else:
        src = source

    origin_t = (float(origin[0]), float(origin[1]))
    if source_origin is None:
        x0, y0, _, _ = _bbox_xy(src)
        so = (x0, y0)
    else:
        so = (float(source_origin[0]), float(source_origin[1]))

    level_id = _ensure_level(host, level)
    display_name = name or src.name
    env = module_envelope_mm(src)
    mid = module_id or new_id("mod")

    if mode in ("block", "linked"):
        _reg = register_module_definition(
            host,
            src,
            module_id=mid,
            name=display_name,
            kind=kind,
        )
        if mode == "linked" and source_path:
            _library(host)[mid]["source_path"] = source_path
            _library(host)[mid]["linked"] = True

        inst_id = new_id("blk")
        el = Element(
            id=inst_id,
            category="module_instance",
            name=display_name,
            level_id=level_id,
            type_id=mid,
            params={
                "module_id": mid,
                "module_name": display_name,
                "mode": mode,
                "kind": kind,
                "origin_mm": [origin_t[0], origin_t[1]],
                "rotation_deg": rotation_deg,
                "z0_mm": z0_mm,
                "size_mm": env,
                "shape": "box",
                "source_path": source_path,
                "source_origin_mm": [so[0], so[1]],
                "ports": _library(host)[mid].get("ports") or [],
                "element_count": len(src.elements),
                "polygon_mm": [
                    [origin_t[0], origin_t[1]],
                    [origin_t[0] + env[0], origin_t[1]],
                    [origin_t[0] + env[0], origin_t[1] + env[1]],
                    [origin_t[0], origin_t[1] + env[1]],
                ],
                "phase": "new",
            },
        )
        host.add_element(el)
        asm = Assembly(
            id=new_id("asm"),
            name=f"Block:{display_name}",
            element_ids=[inst_id],
            kind="module_instance",
            params={"module_id": mid, "mode": mode, "instance_id": inst_id},
        )
        host.assemblies.append(asm)
        return {
            "mode": mode,
            "instance_id": inst_id,
            "module_id": mid,
            "assembly_id": asm.id,
            "name": display_name,
            "envelope_mm": env,
            "ports": _library(host)[mid].get("ports") or [],
            "element_ids": [inst_id],
            "count": 1,
        }

    # --- native: explode copy into host ---
    id_map: dict[str, str] = {}
    level_map: dict[str, str] = {}
    # map source levels → host level (single target) unless names match
    for lv in src.levels:
        try:
            level_map[lv.id] = host.get_level(lv.name).id
        except NotFoundError:
            level_map[lv.id] = level_id

    new_ids: list[str] = []
    for el in src.elements:
        prefix = el.category[:3] if len(el.category) >= 3 else "el"
        nid = new_id(prefix)
        id_map[el.id] = nid
        ne = Element(
            id=nid,
            category=el.category,
            name=el.name,
            level_id=level_map.get(el.level_id or "", level_id),
            host_id=None,  # rewired below
            type_id=el.type_id,
            parent_id=None,
            params=transform_element_params(
                el.params,
                origin=origin_t,
                rotation_deg=rotation_deg,
                source_origin=so,
                z0_delta=z0_mm,
            ),
        )
        ne.params["imported_from_module"] = mid
        ne.params["module_source_element"] = el.id
        if source_path:
            ne.params["module_source_path"] = source_path
        host.add_element(ne)
        new_ids.append(nid)

    # rewire hosts / parents
    for old_id, new_id_ in id_map.items():
        el = host.get_element(new_id_)
        src_el = next(e for e in src.elements if e.id == old_id)
        if src_el.host_id and src_el.host_id in id_map:
            el.host_id = id_map[src_el.host_id]
        if src_el.parent_id and src_el.parent_id in id_map:
            el.parent_id = id_map[src_el.parent_id]
        # rewrite port element refs inside params
        if el.params.get("ports"):
            for port in el.params["ports"]:
                if isinstance(port.get("position_mm"), (list, tuple)):
                    # already transformed if it was in origin — ports often absolute in source
                    try:
                        port["position_mm"] = transform_point(
                            port["position_mm"],
                            origin=origin_t,
                            rotation_deg=rotation_deg,
                            source_origin=so,
                        )
                    except Exception:  # noqa: BLE001
                        pass

    # root marker for the imported fabrication package
    root_id = new_id("mod")
    root = Element(
        id=root_id,
        category="module_root",
        name=display_name,
        level_id=level_id,
        type_id=mid,
        params={
            "module_id": mid,
            "mode": "native",
            "kind": kind,
            "origin_mm": [origin_t[0], origin_t[1]],
            "rotation_deg": rotation_deg,
            "z0_mm": z0_mm,
            "size_mm": env,
            "shape": "box",
            "source_path": source_path,
            "member_ids": new_ids,
            "ports": extract_ports(src),
            "phase": "new",
        },
    )
    host.add_element(root)
    for nid in new_ids:
        el = host.get_element(nid)
        if not el.parent_id:
            el.parent_id = root_id

    # register definition for reference (without huge duplicate if already large — still store slim)
    _library(host)[mid] = {
        "id": mid,
        "name": display_name,
        "kind": kind,
        "source_path": source_path,
        "envelope_mm": env,
        "ports": extract_ports(src),
        "element_count": len(src.elements),
        "native_instance_root": root_id,
        "definition": None,  # native is exploded; definition optional
    }

    asm = Assembly(
        id=new_id("asm"),
        name=f"Module:{display_name}",
        element_ids=[root_id] + new_ids,
        kind="module_native",
        params={"module_id": mid, "mode": "native", "root_id": root_id},
    )
    host.assemblies.append(asm)

    return {
        "mode": "native",
        "instance_id": root_id,
        "module_id": mid,
        "assembly_id": asm.id,
        "name": display_name,
        "envelope_mm": env,
        "element_ids": new_ids,
        "count": len(new_ids),
        "ports": extract_ports(src),
    }


def explode_block(
    host: ProjectModel,
    instance_id: str,
) -> dict[str, Any]:
    """Convert a block/linked module_instance into native host elements."""
    inst = host.get_element(instance_id)
    if inst.category != "module_instance":
        raise ValidationError("Not a module_instance", id=instance_id)
    mid = inst.params.get("module_id")
    lib = _library(host)
    entry = lib.get(str(mid)) if mid else None
    if not entry:
        # try source path
        sp = inst.params.get("source_path")
        if not sp:
            raise ValidationError("No module definition for instance", id=instance_id)
        src = open_module_source(sp)
    else:
        if entry.get("definition"):
            src = ProjectModel.from_dict(entry["definition"])
        elif entry.get("source_path"):
            src = open_module_source(entry["source_path"])
        else:
            raise ValidationError("Module definition empty", module_id=mid)

    origin = inst.params.get("origin_mm") or [0, 0]
    rot = float(inst.params.get("rotation_deg") or 0)
    z0 = float(inst.params.get("z0_mm") or 0)
    so = inst.params.get("source_origin_mm") or None
    level_name = "L1"
    for lv in host.levels:
        if lv.id == inst.level_id:
            level_name = lv.name
            break

    result = import_module(
        host,
        src,
        level=level_name,
        origin=(float(origin[0]), float(origin[1])),
        mode="native",
        name=inst.name,
        rotation_deg=rot,
        z0_mm=z0,
        kind=str(inst.params.get("kind") or "fabrication"),
        module_id=str(mid) if mid else None,
        source_origin=tuple(so) if so else None,
    )
    # remove old block instance
    host.elements = [e for e in host.elements if e.id != instance_id]
    # clean assemblies that only referenced the block
    for a in host.assemblies:
        if instance_id in a.element_ids:
            a.element_ids = [i for i in a.element_ids if i != instance_id]
    result["exploded_from"] = instance_id
    return result


def expand_block_for_export(host: ProjectModel) -> ProjectModel:
    """Return a temporary model with block instances expanded to native geometry.

    Used by exporters that need real solids. Does not mutate host.
    """
    work = host.model_copy(deep=True)
    blocks = [el for el in list(work.elements) if el.category == "module_instance"]
    for inst in blocks:
        try:
            explode_block(work, inst.id)
        except Exception:  # noqa: BLE001
            # leave envelope box if expand fails
            continue
    return work


def connect(
    host: ProjectModel,
    from_id: str,
    from_port: str,
    to_id: str,
    to_port: str,
    *,
    medium: str = "process",
    name: str = "",
) -> dict[str, Any]:
    """Record a connection between two module/equipment ports."""
    # validate elements exist
    host.get_element(from_id)
    host.get_element(to_id)
    cid = new_id("con")
    row = {
        "id": cid,
        "name": name or f"{from_port}→{to_port}",
        "from_id": from_id,
        "from_port": from_port,
        "to_id": to_id,
        "to_port": to_port,
        "medium": medium,
    }
    _connections(host).append(row)
    return row


def list_modules(host: ProjectModel) -> dict[str, Any]:
    lib = _library(host)
    definitions = []
    for mid, e in lib.items():
        definitions.append(
            {
                "module_id": mid,
                "name": e.get("name"),
                "kind": e.get("kind"),
                "source_path": e.get("source_path"),
                "envelope_mm": e.get("envelope_mm"),
                "element_count": e.get("element_count"),
                "ports": len(e.get("ports") or []),
                "linked": bool(e.get("linked")),
            }
        )
    instances = []
    for el in host.elements:
        if el.category in {"module_instance", "module_root"}:
            instances.append(
                {
                    "instance_id": el.id,
                    "name": el.name,
                    "category": el.category,
                    "module_id": el.params.get("module_id"),
                    "mode": el.params.get("mode"),
                    "kind": el.params.get("kind"),
                }
            )
    return {"definitions": definitions, "instances": instances}


def list_connections(host: ProjectModel) -> list[dict[str, Any]]:
    return list(_connections(host))


def resync_linked_module(host: ProjectModel, instance_id: str) -> dict[str, Any]:
    """Re-load linked module definition from source_path (block stays; definition updates)."""
    inst = host.get_element(instance_id)
    path = inst.params.get("source_path")
    mid = inst.params.get("module_id")
    if not path:
        raise ValidationError("Instance is not linked to a source path", id=instance_id)
    src = open_module_source(path)
    if mid:
        register_module_definition(host, src, module_id=str(mid), name=inst.name)
        inst.params["element_count"] = len(src.elements)
        inst.params["size_mm"] = module_envelope_mm(src)
        inst.params["ports"] = extract_ports(src)
    return {"instance_id": instance_id, "module_id": mid, "elements": len(src.elements)}
