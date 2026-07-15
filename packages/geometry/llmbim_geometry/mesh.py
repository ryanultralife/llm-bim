"""Minimal mesh / glTF export for review (wall boxes only)."""

from __future__ import annotations

import json
import math
from pathlib import Path

from llmbim_core.model import ProjectModel


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


def export_gltf_walls(model: ProjectModel, path: str | Path) -> Path:
    """Write a glTF 2.0 JSON with one mesh per wall (box approximation)."""
    all_pos: list[float] = []
    all_idx: list[int] = []
    base = 0
    for el in model.elements:
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
            if not pos:
                continue
            all_pos.extend(pos)
            for i in _BOX_INDICES:
                all_idx.append(base + i)
            base += 8
        elif el.category == "equipment":
            try:
                origin = el.params["origin_mm"]
                size = el.params["size_mm"]
                z0_off = float(el.params.get("z0_mm", 0))
            except (KeyError, TypeError, ValueError):
                continue
            x0, y0 = float(origin[0]), float(origin[1])
            lx, ly, hz = float(size[0]), float(size[1]), float(size[2])
            z0 = _level_z(model, el.level_id) + z0_off
            z1 = z0 + hz
            # Represent box as degenerate "wall" along +X with thickness = ly
            pos = _wall_box_positions(x0, y0 + ly / 2, x0 + lx, y0 + ly / 2, ly, z0, z1)
            if not pos:
                continue
            all_pos.extend(pos)
            for i in _BOX_INDICES:
                all_idx.append(base + i)
            base += 8

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
