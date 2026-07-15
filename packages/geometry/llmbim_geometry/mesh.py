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
    """Pipe run start→end as a thin box at z0 (coordination marker)."""
    try:
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
        od = 50.0
        if el.params.get("size_mm") and len(el.params["size_mm"]) >= 2:
            od = max(float(el.params["size_mm"][1]), 20.0)
        z0_off = float(el.params.get("z0_mm", 0))
        z0 = _level_z(model, el.level_id) + z0_off
        # centerline height ≈ z0 + od/2; box from z0 to z0+od
        return _wall_box_positions(x0, y0, x1, y1, od, z0, z0 + od)
    except (KeyError, TypeError, ValueError, IndexError):
        return []


def export_gltf_walls(model: ProjectModel, path: str | Path) -> Path:
    """Write glTF 2.0 JSON: walls + equipment + pipe/fitting/fixture/module boxes."""
    all_pos: list[float] = []
    all_idx: list[int] = []
    base = 0
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
        elif el.category == "equipment":
            pos = _box_from_origin_size(el, model)
        elif el.category in {"pipe", "plumbing_pipe"}:
            pos = _box_from_pipe(el, model)
        elif el.category in _PROXY_CATS:
            if el.params.get("start_mm") and el.params.get("end_mm"):
                pos = _box_from_pipe(el, model)
            else:
                pos = _box_from_origin_size(el, model)
        else:
            continue
        base = _append_box(all_pos, all_idx, base, pos)

    if not all_pos:
        all_pos = [0, 0, 0, 1, 0, 0, 1, 0, 1]
        all_idx = [0, 1, 2]

    # Encode as base64-less glTF with embedded buffer as raw component arrays via accessors
    # Use a simple approach: put data in a buffer as little-endian binary base64
    import base64
    import struct

    pos_bytes = b"".join(struct.pack("<f", float(v)) for v in all_pos)
    idx_bytes = b"".join(struct.pack("<H", int(i)) for i in all_idx)
    # pad idx to 4-byte align
    pad = (4 - (len(idx_bytes) % 4)) % 4
    idx_bytes_padded = idx_bytes + (b"\x00" * pad)
    blob = pos_bytes + idx_bytes_padded
    b64 = base64.b64encode(blob).decode("ascii")
    uri = f"data:application/octet-stream;base64,{b64}"

    n_verts = len(all_pos) // 3
    max_x = max(all_pos[0::3]) if all_pos else 1
    max_y = max(all_pos[1::3]) if all_pos else 1
    max_z = max(all_pos[2::3]) if all_pos else 1
    min_x = min(all_pos[0::3]) if all_pos else 0
    min_y = min(all_pos[1::3]) if all_pos else 0
    min_z = min(all_pos[2::3]) if all_pos else 0

    gltf = {
        "asset": {"version": "2.0", "generator": "llm-bim"},
        "buffers": [{"byteLength": len(blob), "uri": uri}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_bytes), "target": 34962},
            {
                "buffer": 0,
                "byteOffset": len(pos_bytes),
                "byteLength": len(idx_bytes),
                "target": 34963,
            },
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": n_verts,
                "type": "VEC3",
                "max": [max_x, max_y, max_z],
                "min": [min_x, min_y, min_z],
            },
            {
                "bufferView": 1,
                "componentType": 5123,
                "count": len(all_idx),
                "type": "SCALAR",
            },
        ],
        "meshes": [
            {
                "primitives": [
                    {"attributes": {"POSITION": 0}, "indices": 1, "mode": 4}
                ]
            }
        ],
        "nodes": [{"mesh": 0, "name": model.name}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(gltf, indent=2) + "\n", encoding="utf-8")
    return p
