"""Generic engineering-dataset importer: primitive lists → semantic elements.

External engineering repos (parametric CAD generators, physics codes) commonly
emit JSON primitive lists of the shape::

    {"prim": "box"|"pipe", "x": .., "y": .., "z": ..,
     "w"/"d"/"h" | "axis"/"len"/"r", "name": .., "sys": .., "attrs": {...}}

in metres, grouped under top-level keys such as ``placements``, ``steel``,
``doors``, ``utilities``, ``underground``, ``equipment`` (or any custom key).
``import_primitives`` ingests such data directly — no hand-written bridge
script — by translating every entry into the closest semantic op
(place_column/place_beam/place_door/place_pipe/place_riser/place_duct/
place_cable_tray/create_equipment_box) and falling back to ``create_generic``
so no source geometry is dropped. Import is deterministic and never fatal:
entries that cannot be translated are reported in the returned summary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from llmbim_core.model import Element, ProjectModel

# Known group keys (informational — any key whose value is a primitive list is
# imported; these are the conventional names emitted by engineering repos).
KNOWN_LIST_KEYS: tuple[str, ...] = (
    "placements",
    "steel",
    "doors",
    "utilities",
    "underground",
    "equipment",
)

# nominal size (mm) → catalog NPS label (nearest match wins)
DEFAULT_NPS_BY_MM: dict[float, str] = {
    15.0: "1/2",
    20.0: "3/4",
    25.0: "1",
    32.0: "1-1/4",
    40.0: "1-1/2",
    50.0: "2",
    65.0: "2-1/2",
    80.0: "3",
    100.0: "4",
    150.0: "6",
    200.0: "8",
}

# wall kind tag → catalog wall type id (thickness heuristics fill the gaps)
DEFAULT_WALL_TYPES: dict[str, str] = {
    "shield": "W-SHIELD-CONC",
    "bioshield": "W-SHIELD-CONC",
    "exterior": "W-EXT-CMU",
    "partition": "W-INT-GYP",
}

# media → utility kind (mapping["services"] overrides per service tag)
_PIPE_MEDIA = frozenset(
    {
        "water",
        "gas",
        "steam",
        "oil",
        "chemical",
        "liquid",
        "vacuum",
        "argon",
        "nitrogen",
        "helium",
        "drain",
        "condensate",
        "fuel",
        "glycol",
        "brine",
    }
)
_DUCT_MEDIA = frozenset({"air", "exhaust", "supply", "ventilation"})
_TRAY_MEDIA = frozenset({"power", "signal", "electrical", "data", "control", "instrument"})

# pipe material fallback chain — copper tops out at 4", fire (A53) carries 8"
_PIPE_MATERIAL_FALLBACK: tuple[str, ...] = ("fire", "process")

_BEAM_MEMBERS = ("beam", "girder", "runway", "joist", "purlin", "brace", "rafter", "header")


def _f(entry: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    v = entry.get(key)
    if v is None:
        return default
    return float(v)


def _attrs(entry: Mapping[str, Any]) -> dict[str, Any]:
    a = entry.get("attrs")
    return dict(a) if isinstance(a, Mapping) else {}


def _nps_for(size_mm: float, table: Mapping[float, str]) -> str:
    best = min(table, key=lambda k: abs(k - size_mm))
    return table[best]


def _nearest_wall(model: ProjectModel, cx: float, cy: float) -> tuple[Element | None, float]:
    """Nearest wall element + offset (mm) of the projected point from its start.

    Same projection logic every bridge script re-invents: project the door
    centre onto each wall centreline, keep the closest within 1.2 m.
    """
    best: tuple[float, Element, float] | None = None
    for el in model.elements:
        if el.category != "wall":
            continue
        s = el.params.get("start_mm")
        e = el.params.get("end_mm")
        if not s or not e:
            continue
        x0, y0, x1, y1 = float(s[0]), float(s[1]), float(e[0]), float(e[1])
        dx, dy = x1 - x0, y1 - y0
        length_sq = dx * dx + dy * dy
        if length_sq < 1:
            continue
        t = max(0.0, min(1.0, ((cx - x0) * dx + (cy - y0) * dy) / length_sq))
        px, py = x0 + t * dx, y0 + t * dy
        dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
        if best is None or dist < best[0]:
            best = (dist, el, t * (length_sq**0.5))
    if best is None or best[0] > 1200.0:  # no wall within 1.2 m — cannot host
        return None, 0.0
    return best[1], best[2]


def _collect_groups(
    data: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> tuple[list[tuple[str, list[Mapping[str, Any]]]], str | None]:
    """(group name, primitive entries) pairs + the data's own units key."""

    def is_prim(item: object) -> bool:
        return isinstance(item, Mapping) and ("prim" in item or ("x" in item and "y" in item))

    if isinstance(data, Mapping):
        units = data.get("units")
        groups: list[tuple[str, list[Mapping[str, Any]]]] = []
        for key, value in data.items():
            if not isinstance(value, list):
                continue
            entries = [item for item in value if is_prim(item)]
            if entries and (len(entries) == len(value) or key in KNOWN_LIST_KEYS):
                groups.append((str(key), entries))
        return groups, str(units) if isinstance(units, str) else None
    return [("items", [item for item in data if is_prim(item)])], None


def _scale_for(units: str) -> float | None:
    u = units.strip().lower()
    if u in {"m", "meter", "meters", "metre", "metres"}:
        return 1000.0
    if u in {"mm", "millimeter", "millimeters", "millimetre", "millimetres"}:
        return 1.0
    return None


def import_primitives(
    model: ProjectModel,
    data: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    mapping: Mapping[str, Any] | None = None,
    level: str | None = None,
    units: str = "m",
) -> dict[str, Any]:
    """Ingest an engineering primitive dataset into the model.

    ``data``: dict whose list-valued keys hold primitive entries (``placements``,
    ``steel``, ``doors``, ``utilities``, ``underground``, ``equipment``, or any
    custom key), or a bare list of primitives. A ``units`` key in the data
    overrides the ``units`` argument ("m" scales ×1000 to mm, "mm" passes
    through).

    ``mapping`` (all keys optional):
      - ``services``: service tag → {kind: pipe|duct|tray, material, system}
      - ``nps_by_mm``: size mm → NPS label (defaults to DEFAULT_NPS_BY_MM)
      - ``wall_types``: wall kind tag → wall type_id
      - ``door_types``: attrs.door_type tag → door type_id

    Returns a summary: created counts per category, skipped entries with
    reasons, warnings. Deterministic; never raises for unknown entries.
    """
    from llmbim_core.parts_catalog import resolve_fitting_part_id
    from llmbim_core.registry import dispatch

    cfg: dict[str, Any] = dict(mapping or {})
    services: Mapping[str, Any] = cfg.get("services") or {}
    nps_raw: Mapping[Any, Any] = cfg.get("nps_by_mm") or DEFAULT_NPS_BY_MM
    nps_table: dict[float, str] = {float(k): str(v) for k, v in nps_raw.items()}
    wall_types: Mapping[str, str] = cfg.get("wall_types") or DEFAULT_WALL_TYPES
    door_types: Mapping[str, str] = cfg.get("door_types") or {}

    groups, data_units = _collect_groups(data)
    units_used = data_units or units
    warnings: list[str] = []
    scale = _scale_for(units_used)
    if scale is None:
        warnings.append(f"unknown units {units_used!r} — treating coordinates as mm")
        scale = 1.0

    if level is None:
        level = model.levels[0].name if model.levels else None
    if level is None:
        model.add_level("L1", 0)
        level = "L1"
    lvl: str = level

    created: dict[str, int] = {}
    skipped: list[dict[str, str]] = []
    warned: set[str] = set()

    def made(key: str) -> None:
        created[key] = created.get(key, 0) + 1

    def skip(group: str, name: str, reason: str) -> None:
        skipped.append({"group": group, "name": name, "reason": reason})

    def warn(msg: str) -> None:
        if msg not in warned:
            warned.add(msg)
            warnings.append(msg)

    def pipe_op_with_fallback(
        op: str, npsv: str, material: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        chain = [material] + [m for m in _PIPE_MATERIAL_FALLBACK if m != material]
        for mat in chain:
            if resolve_fitting_part_id("pipe", npsv, material=mat):
                if mat != material:
                    warn(f"NPS {npsv} not in {material!r} catalog — using {mat!r}")
                return dispatch(model, op, {**params, "nps": npsv, "material": mat})
        raise ValueError(f"no pipe catalog material accepts NPS {npsv}")

    def do_door(group: str, e: Mapping[str, Any], attrs: dict[str, Any]) -> None:
        w, d = _f(e, "w"), _f(e, "d")
        cx = (_f(e, "x") + w / 2.0) * scale
        cy = (_f(e, "y") + d / 2.0) * scale
        width_mm = _f(e, "width", max(w, d)) * scale
        if width_mm <= 0:
            skip(group, str(e.get("name") or "door"), "door has no width")
            return
        height_mm = _f(e, "h", _f(e, "height", 2.1 if scale > 1 else 2100.0)) * scale
        host, offset = _nearest_wall(model, cx, cy)
        if host is None:
            skip(group, str(e.get("name") or "door"), "no host wall within 1200 mm")
            return
        wall_len = float(host.params.get("length_mm") or 0)
        if wall_len < width_mm + 100.0:
            skip(group, str(e.get("name") or "door"), "door wider than nearest host wall")
            return
        off = max(50.0, min(offset - width_mm / 2.0, wall_len - width_mm - 50.0))
        tag = str(attrs.get("door_type") or "")
        type_id = door_types.get(tag) or ""
        if not type_id:
            if "shield" in tag.lower() or "plug" in tag.lower():
                type_id = "D-SHIELD-PLUG"
            elif width_mm >= 1500.0:
                type_id = "D-HM-72"
            else:
                type_id = "D-HM-36"
        dispatch(
            model,
            "place_door",
            {
                "host": host.id,
                "offset_mm": off,
                "width_mm": width_mm,
                "height_mm": height_mm,
                "type_id": type_id,
                "fire_rating": str(attrs.get("rating") or ""),
                "name": str(e.get("name") or tag or "door"),
            },
        )
        made("doors")

    def do_wall(e: Mapping[str, Any], attrs: dict[str, Any]) -> None:
        x, y = _f(e, "x") * scale, _f(e, "y") * scale
        w, d = _f(e, "w") * scale, _f(e, "d") * scale
        if w >= d:
            start, end, thick = (x, y + d / 2.0), (x + w, y + d / 2.0), d
        else:
            start, end, thick = (x + w / 2.0, y), (x + w / 2.0, y + d), w
        kind = str(attrs.get("kind") or e.get("kind") or "").lower()
        type_id = wall_types.get(kind)
        if type_id is None:
            if thick >= 1000.0:
                type_id = wall_types.get("shield", "W-SHIELD-CONC")
            elif thick <= 220.0:
                type_id = wall_types.get("partition", "W-INT-GYP")
        dispatch(
            model,
            "create_wall",
            {
                "level": lvl,
                "start": list(start),
                "end": list(end),
                "thickness_mm": max(thick, 25.0),
                "height_mm": max(_f(e, "h") * scale, 100.0),
                "name": str(e.get("name") or "wall"),
                "type_id": type_id,
            },
        )
        made("walls")

    def do_steel(e: Mapping[str, Any], attrs: dict[str, Any], member: str) -> bool:
        section = str(attrs.get("section") or "W10x33")
        x, y = _f(e, "x") * scale, _f(e, "y") * scale
        w, d = _f(e, "w") * scale, _f(e, "d") * scale
        name = str(e.get("name") or member)
        m = member.lower()
        if "column" in m or m == "col":
            dispatch(
                model,
                "place_column",
                {
                    "level": lvl,
                    "origin": [x + w / 2.0, y + d / 2.0],
                    "section": section,
                    "height_mm": _f(e, "h") * scale,
                    "name": name,
                },
            )
            made("columns")
            return True
        sys_tag = str(e.get("sys") or "").upper()
        if any(t in m for t in _BEAM_MEMBERS) or sys_tag == "STEEL":
            if w >= d:
                start, end = (x, y + d / 2.0), (x + w, y + d / 2.0)
            else:
                start, end = (x + w / 2.0, y), (x + w / 2.0, y + d)
            dispatch(
                model,
                "place_beam",
                {
                    "level": lvl,
                    "start": list(start),
                    "end": list(end),
                    "section": section,
                    "z0_mm": _f(e, "z") * scale,
                    "name": name,
                },
            )
            made("beams")
            return True
        return False

    def do_equipment(e: Mapping[str, Any], attrs: dict[str, Any]) -> None:
        name = str(
            attrs.get("equip")
            or attrs.get("machine")
            or e.get("name")
            or attrs.get("structure")
            or "equipment"
        )
        kind = str(attrs.get("kind") or e.get("sys") or "equipment").lower()
        x, y, z = _f(e, "x") * scale, _f(e, "y") * scale, _f(e, "z") * scale
        if str(e.get("prim") or "box") == "pipe":
            dia = 2.0 * _f(e, "r", 0.05 if scale > 1 else 50.0) * scale
            length = _f(e, "len", 0.5 if scale > 1 else 500.0) * scale
            axis = str(e.get("axis") or "x")
            size = {
                "x": [length, dia, dia],
                "y": [dia, length, dia],
                "z": [dia, dia, length],
            }.get(axis, [length, dia, dia])
            params: dict[str, Any] = {
                "level": lvl,
                "origin": [x, y],
                "size": size,
                "name": name,
                "kind": kind,
                "shape": "cylinder",
                "centered": True,
                "z0_mm": z,
            }
        else:
            params = {
                "level": lvl,
                "origin": [x, y],
                "size": [_f(e, "w") * scale, _f(e, "d") * scale, _f(e, "h") * scale],
                "name": name,
                "kind": kind,
                "z0_mm": z,
            }
        dispatch(model, "create_equipment_box", params)
        made("equipment")

    def resolve_service(
        e: Mapping[str, Any], attrs: dict[str, Any]
    ) -> tuple[str | None, str, str | None]:
        """(kind, system tag, material) for the utility path; kind None = not a utility."""
        sys_tag = str(e.get("sys") or "")
        service = str(attrs.get("service") or "") or (sys_tag if sys_tag in services else "")
        svc = services.get(service)
        kind: str | None = None
        material: str | None = None
        if isinstance(svc, Mapping):
            kind = str(svc.get("kind")) if svc.get("kind") else None
            material = str(svc.get("material")) if svc.get("material") else None
            service = str(svc.get("system") or service)
        if kind is None:
            medium = str(attrs.get("medium") or "").lower()
            if medium in _PIPE_MEDIA:
                kind = "pipe"
            elif medium in _DUCT_MEDIA:
                kind = "duct"
            elif medium in _TRAY_MEDIA:
                kind = "tray"
            elif service or str(e.get("prim") or "") == "pipe":
                kind = "pipe"
        system = service or sys_tag or "GEN"
        return kind, system, material

    def do_utility(
        e: Mapping[str, Any],
        attrs: dict[str, Any],
        kind: str,
        system: str,
        material: str | None,
    ) -> None:
        x, y, z = _f(e, "x") * scale, _f(e, "y") * scale, _f(e, "z") * scale
        name = str(e.get("name") or attrs.get("line") or system)
        if str(e.get("prim") or "box") == "pipe":
            axis = str(e.get("axis") or "x")
            length = _f(e, "len") * scale
            size_mm = float(attrs.get("size_mm") or 0) or (
                2.0 * _f(e, "r", 0.025 if scale > 1 else 25.0) * scale
            )
            if kind == "pipe":
                npsv = _nps_for(size_mm, nps_table)
                if axis == "z":
                    pipe_op_with_fallback(
                        "place_riser",
                        npsv,
                        material or "copper",
                        {
                            "level": lvl,
                            "origin": [x, y],
                            "z0_mm": z,
                            "z1_mm": z + length,
                            "system": system,
                            "name": name,
                        },
                    )
                    made("risers")
                else:
                    end = [x + length, y] if axis == "x" else [x, y + length]
                    pipe_op_with_fallback(
                        "place_pipe",
                        npsv,
                        material or "copper",
                        {
                            "level": lvl,
                            "start": [x, y],
                            "end": end,
                            "system": system,
                            "z0_mm": z,
                            "name": name,
                        },
                    )
                    made("pipes")
            elif axis == "z":
                # vertical duct/tray: no vertical primitive — coordination box
                s = max(size_mm, 100.0)
                dispatch(
                    model,
                    "create_equipment_box",
                    {
                        "level": lvl,
                        "origin": [x, y],
                        "size": [s, s, length],
                        "name": name,
                        "kind": f"{system.lower()}_riser",
                        "centered": True,
                        "z0_mm": z,
                    },
                )
                made("riser_boxes")
            elif kind == "duct":
                end = [x + length, y] if axis == "x" else [x, y + length]
                dispatch(
                    model,
                    "place_duct",
                    {
                        "level": lvl,
                        "start": [x, y],
                        "end": end,
                        "width_mm": size_mm,
                        "height_mm": size_mm,
                        "system": system,
                        "z0_mm": z,
                        "name": name,
                        "material": material or "galv_steel",
                    },
                )
                made("ducts")
            else:  # tray
                end = [x + length, y] if axis == "x" else [x, y + length]
                dispatch(
                    model,
                    "place_cable_tray",
                    {
                        "level": lvl,
                        "start": [x, y],
                        "end": end,
                        "width_mm": size_mm,
                        "system": system,
                        "z0_mm": z,
                        "name": name,
                        "material": material or "galv_steel",
                    },
                )
                made("trays")
        else:  # box primitive: run along the long plan axis
            w = _f(e, "w", 0.3 if scale > 1 else 300.0) * scale
            d = _f(e, "d", 0.3 if scale > 1 else 300.0) * scale
            h = _f(e, "h", 0.3 if scale > 1 else 300.0) * scale
            if w >= d:
                start, end, across, depth = [x, y + d / 2.0], [x + w, y + d / 2.0], d, h
            else:
                start, end, across, depth = [x + w / 2.0, y], [x + w / 2.0, y + d], w, h
            if kind == "duct":
                dispatch(
                    model,
                    "place_duct",
                    {
                        "level": lvl,
                        "start": start,
                        "end": end,
                        "width_mm": across,
                        "height_mm": depth,
                        "system": system,
                        "z0_mm": z,
                        "name": name,
                        "material": material or "galv_steel",
                    },
                )
                made("ducts")
            elif kind == "tray":
                dispatch(
                    model,
                    "place_cable_tray",
                    {
                        "level": lvl,
                        "start": start,
                        "end": end,
                        "width_mm": across,
                        "system": system,
                        "z0_mm": z,
                        "name": name,
                        "material": material or "galv_steel",
                    },
                )
                made("trays")
            else:  # pipe bank box: pipe along long axis, size from cross-section
                npsv = _nps_for(float(attrs.get("size_mm") or min(across, depth)), nps_table)
                pipe_op_with_fallback(
                    "place_pipe",
                    npsv,
                    material or "copper",
                    {
                        "level": lvl,
                        "start": start,
                        "end": end,
                        "system": system,
                        "z0_mm": z,
                        "name": name,
                    },
                )
                made("pipes")

    def do_generic(e: Mapping[str, Any], attrs: dict[str, Any], category: str) -> None:
        prim = str(e.get("prim") or "box")
        x, y, z = _f(e, "x") * scale, _f(e, "y") * scale, _f(e, "z") * scale
        if prim == "pipe":
            dia = 2.0 * _f(e, "r", 0.05 if scale > 1 else 50.0) * scale
            length = _f(e, "len", 0.5 if scale > 1 else 500.0) * scale
            axis = str(e.get("axis") or "x")
            size = {
                "x": [length, dia, dia],
                "y": [dia, length, dia],
                "z": [dia, dia, length],
            }.get(axis, [length, dia, dia])
            shape = "cylinder"
        else:
            size = [_f(e, "w") * scale, _f(e, "d") * scale, _f(e, "h") * scale]
            shape = "box"
        extra = {
            k: v
            for k, v in e.items()
            if k not in {"prim", "x", "y", "z", "w", "d", "h", "axis", "len", "r", "attrs", "name"}
        }
        dispatch(
            model,
            "create_generic",
            {
                "category": category,
                "level": lvl,
                "name": str(e.get("name") or category),
                "params": {
                    "prim": prim,
                    "origin_mm": [x, y],
                    "size_mm": size,
                    "z0_mm": z,
                    "shape": shape,
                    "polygon_mm": [
                        [x, y],
                        [x + size[0], y],
                        [x + size[0], y + size[1]],
                        [x, y + size[1]],
                    ],
                    "attrs": attrs,
                    "source": "primitives",
                    **extra,
                },
            },
        )
        made("zones" if category == "zone" else "generic")

    def handle(group: str, e: Mapping[str, Any]) -> None:
        attrs = _attrs(e)
        sys_tag = str(e.get("sys") or "").upper()
        prim = e.get("prim")
        # 1. doors (group hint, sys tag, or typed attrs)
        if group == "doors" or sys_tag == "DOOR" or attrs.get("door_type"):
            do_door(group, e, attrs)
            return
        # 2. walls (explicit only — building walls normally come from CAD wall lists)
        if sys_tag == "WALL" or str(attrs.get("member") or "") == "wall":
            do_wall(e, attrs)
            return
        # 3. structural steel boxes → column / beam
        member = str(attrs.get("member") or "")
        if prim == "box" and member and do_steel(e, attrs, member):
            return
        # 4. tagged equipment / machines / structures
        if attrs.get("equip") or attrs.get("machine") or attrs.get("structure"):
            do_equipment(e, attrs)
            return
        # 5. utility runs (service tag / medium / bare pipe prims)
        kind, system, material = resolve_service(e, attrs)
        if prim == "pipe" and (member or attrs.get("part")) and not attrs.get("service"):
            # mechanism internals (crane ropes, hooks) — keep as cylinders
            do_equipment(e, attrs)
            return
        if kind is not None and prim is not None:
            do_utility(e, attrs, kind, system, material)
            return
        # 6. placements / untyped boxes → generic zone geometry, params preserved
        if prim is None:
            do_generic(e, attrs, "zone")
            return
        do_generic(e, attrs, "generic")

    total_entries = 0
    for group, entries in groups:
        for e in entries:
            total_entries += 1
            try:
                handle(group, e)
            except Exception as exc:
                skip(group, str(e.get("name") or e.get("id") or "?"), f"{type(exc).__name__}: {exc}")

    return {
        "ok": True,
        "created": created,
        "created_total": sum(created.values()),
        "entries": total_entries,
        "skipped": skipped,
        "warnings": warnings,
        "units": units_used,
        "scale": scale,
        "level": lvl,
    }


def looks_like_primitives(data: object) -> bool:
    """True when a parsed JSON payload is an engineering primitive dataset."""

    def has_prims(value: object) -> bool:
        return isinstance(value, list) and any(
            isinstance(item, dict) and "prim" in item for item in value
        )

    if isinstance(data, list):
        return has_prims(data)
    if isinstance(data, dict):
        if "ops" in data:
            return False
        for key, value in data.items():
            if has_prims(value):
                return True
            if (
                str(key) in KNOWN_LIST_KEYS
                and isinstance(value, list)
                and value
                and all(isinstance(i, dict) and "x" in i and "y" in i for i in value)
            ):
                return True
    return False
