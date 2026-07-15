"""Minimal mesh / glTF export for review (walls + equipment + MEP proxies)."""

from __future__ import annotations

import json
import math
from pathlib import Path

from llmbim_core.model import Element, ProjectModel


def _level_z(model: ProjectModel, level_id: str | None) -> float:
    if not level_id:
        return 0.0
    for lv in model.levels:
        if lv.id == level_id:
            return float(lv.elevation_mm)
    return 0.0


def _wall_box_positions(
    x0: float, y0: float, x1: float, y1: float, thickness: float, z0: float, z1: float
) -> list[float]:
    """8 corners as flat xyz list for a wall extruded as a box along centerline."""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return []
    nx, ny = -dy / length, dx / length
    h = thickness / 2.0
    # bottom 4 then top 4
    corners_2d = [
        (x0 + nx * h, y0 + ny * h),
        (x1 + nx * h, y1 + ny * h),
        (x1 - nx * h, y1 - ny * h),
        (x0 - nx * h, y0 - ny * h),
    ]
    pos: list[float] = []
    for z in (z0, z1):
        for x, y in corners_2d:
            # glTF: Y-up; we map plan Y → glTF Z, elevation → glTF Y (mm → m)
            pos.extend([x / 1000.0, z / 1000.0, y / 1000.0])
    return pos


# Two tris per face, 6 faces
_BOX_INDICES = [
    0, 1, 5, 0, 5, 4,  # +n
    2, 3, 7, 2, 7, 6,  # -n
    1, 2, 6, 1, 6, 5,  # end1
    3, 0, 4, 3, 4, 7,  # end0
    4, 5, 6, 4, 6, 7,  # top
    0, 3, 2, 0, 2, 1,  # bottom
]

_PROXY_CATS = {
    "fitting",
    "fittings",
    "fixture",
    "accessory",
    "module_instance",
    "module_root",
    "steel",
    "rebar",
    "framing",
    "fire_protection",
    "process_piping",
}

# System / category → glTF baseColorFactor (RGBA) for coordination review
_MATERIAL_RGBA: dict[str, list[float]] = {
    "wall": [0.72, 0.72, 0.72, 1.0],
    "equipment": [0.42, 0.62, 0.88, 1.0],
    "pipe_copper": [0.77, 0.36, 0.15, 1.0],  # plan SVG orange
    "pipe_fire": [0.2, 0.2, 0.2, 1.0],
    "pipe_process": [0.42, 0.49, 0.54, 1.0],
    "pipe_pvc": [0.9, 0.85, 0.29, 1.0],
    "duct": [0.18, 0.49, 0.2, 1.0],  # green
    "conduit": [0.42, 0.11, 0.6, 1.0],  # purple
    "cable_tray": [0.55, 0.15, 0.7, 1.0],  # deep purple
    "column": [0.35, 0.4, 0.45, 1.0],  # steel gray
    "beam": [0.4, 0.45, 0.5, 1.0],
    "door": [0.55, 0.78, 0.55, 1.0],  # light green (matches plan SVG)
    "window": [0.55, 0.75, 0.95, 1.0],  # light blue
    "fitting": [0.95, 0.6, 0.2, 1.0],
    "fixture": [0.45, 0.35, 0.65, 1.0],
    "module": [0.55, 0.55, 0.7, 1.0],
    "default": [0.6, 0.6, 0.6, 1.0],
}


def _append_box(
    all_pos: list[float],
    all_idx: list[int],
    base: int,
    pos: list[float],
) -> int:
    if not pos:
        return base
    all_pos.extend(pos)
    for i in _BOX_INDICES:
        all_idx.append(base + i)
    return base + 8


def _box_from_origin_size(el: Element, model: ProjectModel) -> list[float]:
    try:
        origin = el.params.get("origin_mm")
        size = el.params.get("size_mm") or [100, 100, 100]
        if not origin:
            return []
        z0_off = float(el.params.get("z0_mm", 0))
        shape = el.params.get("shape", "box")
        x0, y0 = float(origin[0]), float(origin[1])
        lx = float(size[0]) if len(size) > 0 else 100.0
        ly = float(size[1]) if len(size) > 1 else 100.0
        hz = float(size[2]) if len(size) > 2 else ly
        z0 = _level_z(model, el.level_id) + z0_off
        if shape == "cylinder" or el.params.get("fitting_type") == "pipe":
            # horizontal cylinder envelope along +X length
            return _wall_box_positions(x0, y0, x0 + max(lx, 50), y0, max(ly, 30), z0, z0 + max(hz, ly, 30))
        return _wall_box_positions(x0, y0 + ly / 2, x0 + max(lx, 50), y0 + ly / 2, max(ly, 30), z0, z0 + max(hz, 30))
    except (KeyError, TypeError, ValueError, IndexError):
        return []


def _box_from_pipe(el: Element, model: ProjectModel) -> list[float]:
    """Pipe run start→end or vertical riser as coordination box."""
    try:
        od = 50.0
        if el.params.get("size_mm") and len(el.params["size_mm"]) >= 2:
            od = max(float(el.params["size_mm"][1]), 20.0)
        is_duct = el.category in {"duct", "hvac"} or el.params.get("fitting_type") == "duct"
        is_tray = el.category == "cable_tray" or el.params.get("fitting_type") == "cable_tray"
        if is_duct or is_tray:
            od = float(el.params.get("width_mm") or od)
        # vertical riser: box at XY spanning z0→z1
        if el.params.get("vertical") or el.params.get("orientation") == "vertical":
            o = el.params.get("origin_mm") or el.params.get("start_mm") or [0, 0]
            x, y = float(o[0]), float(o[1])
            z_lo = _level_z(model, el.level_id) + float(el.params.get("z0_mm") or 0)
            z_hi = _level_z(model, el.level_id) + float(
                el.params.get("z1_mm") or (float(el.params.get("z0_mm") or 0) + 1000)
            )
            r = od / 2
            # short plan segment so box has thickness, height is z
            return _wall_box_positions(x - r, y, x + r, y, od, min(z_lo, z_hi), max(z_lo, z_hi))
        if "start_mm" in el.params and "end_mm" in el.params:
            s, e = el.params["start_mm"], el.params["end_mm"]
            x0, y0 = float(s[0]), float(s[1])
            x1, y1 = float(e[0]), float(e[1])
        elif "origin_mm" in el.params and "size_mm" in el.params:
            o, sz = el.params["origin_mm"], el.params["size_mm"]
            x0, y0 = float(o[0]), float(o[1])
            x1, y1 = x0 + float(sz[0]), y0
        else:
            return []
        z0_off = float(el.params.get("z0_mm", 0))
        z0 = _level_z(model, el.level_id) + z0_off
        elev_h = od
        if is_duct:
            elev_h = float(el.params.get("height_mm") or 250)
        elif is_tray:
            elev_h = float(el.params.get("height_mm") or 100)
        return _wall_box_positions(x0, y0, x1, y1, od, z0, z0 + elev_h)
    except (KeyError, TypeError, ValueError, IndexError):
        return []


def _box_from_opening(el: Element, model: ProjectModel, wall_by_id: dict) -> list[float]:
    """Door/window box along host wall baseline at offset + sill."""
    try:
        host = wall_by_id.get(el.host_id or "")
        if not host:
            return []
        s = host.params.get("start_mm")
        e = host.params.get("end_mm")
        if not s or not e:
            return []
        hx0, hy0 = float(s[0]), float(s[1])
        hx1, hy1 = float(e[0]), float(e[1])
        wlen = math.hypot(hx1 - hx0, hy1 - hy0)
        if wlen < 1:
            return []
        off = float(el.params.get("offset_mm") or 0)
        width_o = float(el.params.get("width_mm") or 900)
        oh = float(el.params.get("height_mm") or (2100 if el.category == "door" else 1200))
        sill = float(el.params.get("sill_mm") or 0)
        th = float(host.params.get("thickness_mm") or 100)
        ux, uy = (hx1 - hx0) / wlen, (hy1 - hy0) / wlen
        ax, ay = hx0 + ux * off, hy0 + uy * off
        bx, by = hx0 + ux * (off + width_o), hy0 + uy * (off + width_o)
        z0 = _level_z(model, host.level_id) + sill
        z1 = z0 + oh
        return _wall_box_positions(ax, ay, bx, by, th, z0, z1)
    except (KeyError, TypeError, ValueError, IndexError):
        return []


def _gltf_material_key(el: Element) -> str:
    """Pick coordination material bucket for multi-trade glTF colors."""
    cat = el.category or ""
    if cat == "wall":
        return "wall"
    if cat == "door":
        return "door"
    if cat == "window":
        return "window"
    if cat == "equipment":
        return "equipment"
    if cat in {"duct", "hvac"} or el.params.get("fitting_type") == "duct":
        return "duct"
    if cat == "conduit" or el.params.get("fitting_type") == "conduit":
        return "conduit"
    if cat == "cable_tray" or el.params.get("fitting_type") == "cable_tray":
        return "cable_tray"
    if cat == "column" or el.params.get("fitting_type") == "column":
        return "column"
    if cat == "beam" or el.params.get("fitting_type") == "beam":
        return "beam"
    if cat in {"fixture", "accessory"}:
        return "fixture"
    if cat in {"module_instance", "module_root"}:
        return "module"
    if cat in {"fitting", "fittings"}:
        return "fitting"
    if cat in {"pipe", "plumbing_pipe"} or el.params.get("fitting_type") == "pipe":
        mid = str(el.params.get("material_id") or "").lower()
        sys = str(el.params.get("system") or "").lower()
        if "black" in mid or sys in ("fp", "fire", "fire_protection"):
            return "pipe_fire"
        if "ss316" in mid or sys in ("proc", "process"):
            return "pipe_process"
        if "pvc" in mid:
            return "pipe_pvc"
        return "pipe_copper"
    if cat in _PROXY_CATS:
        return "default"
    return "default"


def export_gltf_walls(model: ProjectModel, path: str | Path) -> Path:
    """Write glTF 2.0 JSON: walls + equipment + MEP with system-colored materials."""
    # bucket → positions + local indices
    buckets: dict[str, dict] = {}

    def _ensure(key: str) -> dict:
        if key not in buckets:
            buckets[key] = {"pos": [], "idx": [], "base": 0}
        return buckets[key]

    wall_by_id = {el.id: el for el in model.elements if el.category == "wall"}

    for el in model.elements:
        pos: list[float] = []
        if el.category == "wall":
            try:
                s = el.params["start_mm"]
                e = el.params["end_mm"]
                th = float(el.params.get("thickness_mm", 200))
                ht = float(el.params.get("height_mm", 3000))
            except (KeyError, TypeError, ValueError):
                continue
            z0 = _level_z(model, el.level_id)
            z1 = z0 + ht
            pos = _wall_box_positions(
                float(s[0]), float(s[1]), float(e[0]), float(e[1]), th, z0, z1
            )
        elif el.category in {"door", "window"}:
            pos = _box_from_opening(el, model, wall_by_id)
        elif el.category == "equipment":
            pos = _box_from_origin_size(el, model)
        elif el.category == "column" or el.params.get("fitting_type") == "column":
            pos = _box_from_origin_size(el, model)
        elif el.category == "beam" or el.params.get("fitting_type") == "beam":
            pos = _box_from_pipe(el, model)
        elif el.category in {"pipe", "plumbing_pipe", "conduit", "duct", "hvac", "cable_tray"}:
            pos = _box_from_pipe(el, model)
        elif el.category in _PROXY_CATS:
            if el.params.get("start_mm") and el.params.get("end_mm"):
                pos = _box_from_pipe(el, model)
            else:
                pos = _box_from_origin_size(el, model)
        else:
            continue
        if not pos:
            continue
        key = _gltf_material_key(el)
        b = _ensure(key)
        b["base"] = _append_box(b["pos"], b["idx"], b["base"], pos)

    if not buckets:
        buckets["default"] = {
            "pos": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0],
            "idx": [0, 1, 2],
            "base": 3,
        }

    import base64
    import struct

    all_pos: list[float] = []
    all_idx: list[int] = []
    # (mat_key, pos_float_offset, n_verts, idx_start, n_idx)
    prim_meta: list[tuple[str, int, int, int, int]] = []
    vert_base = 0
    for key, b in buckets.items():
        pos = b["pos"]
        idx = b["idx"]
        if not pos or not idx:
            continue
        pos_start = len(all_pos)
        n_verts = len(pos) // 3
        all_pos.extend(pos)
        idx_start = len(all_idx)
        for i in idx:
            all_idx.append(vert_base + i)
        prim_meta.append((key, pos_start, n_verts, idx_start, len(idx)))
        vert_base += n_verts

    pos_bytes = b"".join(struct.pack("<f", float(v)) for v in all_pos)
    idx_bytes = b"".join(struct.pack("<H", int(i)) for i in all_idx)
    pad = (4 - (len(idx_bytes) % 4)) % 4
    idx_bytes_padded = idx_bytes + (b"\x00" * pad)
    blob = pos_bytes + idx_bytes_padded
    b64 = base64.b64encode(blob).decode("ascii")
    uri = f"data:application/octet-stream;base64,{b64}"

    n_verts_total = len(all_pos) // 3
    max_x = max(all_pos[0::3]) if all_pos else 1.0
    max_y = max(all_pos[1::3]) if all_pos else 1.0
    max_z = max(all_pos[2::3]) if all_pos else 1.0
    min_x = min(all_pos[0::3]) if all_pos else 0.0
    min_y = min(all_pos[1::3]) if all_pos else 0.0
    min_z = min(all_pos[2::3]) if all_pos else 0.0

    mat_keys: list[str] = []
    for key, *_ in prim_meta:
        if key not in mat_keys:
            mat_keys.append(key)
    materials = []
    for key in mat_keys:
        rgba = _MATERIAL_RGBA.get(key, _MATERIAL_RGBA["default"])
        materials.append(
            {
                "name": key,
                "pbrMetallicRoughness": {
                    "baseColorFactor": rgba,
                    "metallicFactor": 0.1,
                    "roughnessFactor": 0.85,
                },
            }
        )
    mat_index = {k: i for i, k in enumerate(mat_keys)}

    buffer_views = [
        {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_bytes), "target": 34962},
        {
            "buffer": 0,
            "byteOffset": len(pos_bytes),
            "byteLength": len(idx_bytes),
            "target": 34963,
        },
    ]

    # accessors[0] always = full vertex count (tests + simple clients)
    accessors: list[dict] = [
        {
            "bufferView": 0,
            "byteOffset": 0,
            "componentType": 5126,
            "count": n_verts_total,
            "type": "VEC3",
            "max": [max_x, max_y, max_z],
            "min": [min_x, min_y, min_z],
        }
    ]
    primitives: list[dict] = []
    for key, pos_start, n_verts, idx_start, n_idx in prim_meta:
        pslice = all_pos[pos_start : pos_start + n_verts * 3]
        pos_acc = len(accessors)
        accessors.append(
            {
                "bufferView": 0,
                "byteOffset": pos_start * 4,
                "componentType": 5126,
                "count": n_verts,
                "type": "VEC3",
                "max": [max(pslice[0::3]), max(pslice[1::3]), max(pslice[2::3])],
                "min": [min(pslice[0::3]), min(pslice[1::3]), min(pslice[2::3])],
            }
        )
        idx_acc = len(accessors)
        accessors.append(
            {
                "bufferView": 1,
                "byteOffset": idx_start * 2,
                "componentType": 5123,
                "count": n_idx,
                "type": "SCALAR",
            }
        )
        primitives.append(
            {
                "attributes": {"POSITION": pos_acc},
                "indices": idx_acc,
                "mode": 4,
                "material": mat_index[key],
            }
        )

    gltf = {
        "asset": {"version": "2.0", "generator": "llm-bim"},
        "buffers": [{"byteLength": len(blob), "uri": uri}],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "materials": materials,
        "meshes": [{"name": "llm-bim-model", "primitives": primitives}],
        "nodes": [{"mesh": 0, "name": model.name}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
        "extras": {
            "material_legend": {k: _MATERIAL_RGBA.get(k) for k in mat_keys},
            "honesty": "ENGINEERING ESTIMATE coordination colors — not fabrication materials",
        },
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(gltf, indent=2) + "\n", encoding="utf-8")
    return p
