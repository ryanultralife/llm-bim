"""Mesh / glTF export for presentation-grade 3D review (walls, MEP, structure).

Coordinates: millimetres in model → metres in glTF.
glTF Y-up: plan X → X, elevation → Y, plan Y → Z.
"""

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


def _mm_to_gltf(x_mm: float, y_mm: float, z_mm: float) -> tuple[float, float, float]:
    """Plan X, plan Y, elevation mm → glTF X,Y,Z metres."""
    return x_mm / 1000.0, z_mm / 1000.0, y_mm / 1000.0


# System / category → baseColor + metallic + roughness
_MATERIAL_PBR: dict[str, tuple[list[float], float, float]] = {
    "wall": ([0.78, 0.76, 0.72, 1.0], 0.02, 0.88),
    "slab": ([0.55, 0.55, 0.58, 1.0], 0.05, 0.82),
    "equipment": ([0.28, 0.52, 0.82, 1.0], 0.35, 0.45),
    "pipe_copper": ([0.85, 0.42, 0.18, 1.0], 0.85, 0.28),
    "pipe_fire": ([0.12, 0.12, 0.14, 1.0], 0.7, 0.4),
    "pipe_process": ([0.55, 0.6, 0.65, 1.0], 0.9, 0.25),
    "pipe_pvc": ([0.92, 0.88, 0.35, 1.0], 0.05, 0.55),
    "duct": ([0.22, 0.55, 0.32, 1.0], 0.4, 0.5),
    "conduit": ([0.5, 0.18, 0.72, 1.0], 0.55, 0.4),
    "cable_tray": ([0.62, 0.22, 0.75, 1.0], 0.5, 0.45),
    "column": ([0.45, 0.48, 0.52, 1.0], 0.82, 0.32),
    "beam": ([0.5, 0.52, 0.56, 1.0], 0.8, 0.35),
    "door": ([0.42, 0.55, 0.38, 1.0], 0.15, 0.65),
    "window": ([0.55, 0.78, 0.92, 0.55], 0.05, 0.08),  # glass-like
    "fitting": ([0.95, 0.55, 0.15, 1.0], 0.7, 0.35),
    "fixture": ([0.55, 0.42, 0.75, 1.0], 0.2, 0.5),
    "module": ([0.5, 0.55, 0.7, 1.0], 0.25, 0.55),
    "default": ([0.62, 0.62, 0.65, 1.0], 0.2, 0.7),
}

# Back-compat alias for tests / legend
_MATERIAL_RGBA: dict[str, list[float]] = {k: list(v[0]) for k, v in _MATERIAL_PBR.items()}

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


def _append_mesh(
    bucket: dict,
    positions: list[float],
    normals: list[float],
    indices: list[int],
) -> None:
    """Append a solid (local 0-based indices) into a layer bucket."""
    if not positions or not indices:
        return
    base = bucket["base"]
    bucket["pos"].extend(positions)
    bucket["nrm"].extend(normals)
    for i in indices:
        bucket["idx"].append(base + i)
    bucket["base"] += len(positions) // 3


def _box_solid(
    corners: list[tuple[float, float, float]],
) -> tuple[list[float], list[float], list[int]]:
    """8 corners (plan_x, plan_y, elev) → glTF mesh with per-face normals.

    Corner order bottom: 0-1-2-3, top: 4-5-6-7 matching previous wall layout:
    0 = start +n, 1 = end +n, 2 = end -n, 3 = start -n
    """
    # Convert to glTF XYZ
    c = [_mm_to_gltf(x, y, z) for x, y, z in corners]
    # Faces as quads (corner indices)
    faces = [
        (0, 1, 5, 4),  # +n side
        (2, 3, 7, 6),  # -n side
        (1, 2, 6, 5),  # end1
        (3, 0, 4, 7),  # end0
        (4, 5, 6, 7),  # top
        (0, 3, 2, 1),  # bottom
    ]
    pos: list[float] = []
    nrm: list[float] = []
    idx: list[int] = []
    vi = 0
    for a, b, c2, d in faces:
        p0, p1, p2, p3 = c[a], c[b], c[c2], c[d]
        # normal from triangle p0-p1-p2
        ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        nx, ny, nz = nx / ln, ny / ln, nz / ln
        for p in (p0, p1, p2, p3):
            pos.extend(p)
            nrm.extend([nx, ny, nz])
        # two tris
        idx.extend([vi, vi + 1, vi + 2, vi, vi + 2, vi + 3])
        vi += 4
    return pos, nrm, idx


def _wall_box_mesh(
    x0: float, y0: float, x1: float, y1: float, thickness: float, z0: float, z1: float
) -> tuple[list[float], list[float], list[int]]:
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return [], [], []
    nx, ny = -dy / length, dx / length
    h = thickness / 2.0
    # bottom 4 then top 4 in plan+elev
    b = [
        (x0 + nx * h, y0 + ny * h, z0),
        (x1 + nx * h, y1 + ny * h, z0),
        (x1 - nx * h, y1 - ny * h, z0),
        (x0 - nx * h, y0 - ny * h, z0),
        (x0 + nx * h, y0 + ny * h, z1),
        (x1 + nx * h, y1 + ny * h, z1),
        (x1 - nx * h, y1 - ny * h, z1),
        (x0 - nx * h, y0 - ny * h, z1),
    ]
    return _box_solid(b)


# Legacy helper used by older call sites / tests that only need positions
def _wall_box_positions(
    x0: float, y0: float, x1: float, y1: float, thickness: float, z0: float, z1: float
) -> list[float]:
    pos, _n, _i = _wall_box_mesh(x0, y0, x1, y1, thickness, z0, z1)
    # return unique 8-corner style not available; return first of each face verts roughly
    # For tests counting verts, full expanded mesh is fine (more verts)
    return pos


def _aabb_box_mesh(
    x0: float, y0: float, z0: float, x1: float, y1: float, z1: float
) -> tuple[list[float], list[float], list[int]]:
    """Axis-aligned box in plan mm + elev."""
    xa, xb = min(x0, x1), max(x0, x1)
    ya, yb = min(y0, y1), max(y0, y1)
    za, zb = min(z0, z1), max(z0, z1)
    corners = [
        (xa, ya, za),
        (xb, ya, za),
        (xb, yb, za),
        (xa, yb, za),
        (xa, ya, zb),
        (xb, ya, zb),
        (xb, yb, zb),
        (xa, yb, zb),
    ]
    return _box_solid(corners)


def _cylinder_mesh(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    z_bot: float,
    z_top: float,
    radius: float,
    *,
    vertical: bool = False,
    segments: int = 14,
) -> tuple[list[float], list[float], list[int]]:
    """Horizontal cylinder along plan start→end, or vertical at XY."""
    segs = max(6, segments)
    pos: list[float] = []
    nrm: list[float] = []
    idx: list[int] = []
    if vertical:
        cx, cy = x0, y0
        h0, h1 = z_bot, z_top
        # rings at bottom and top
        ring: list[list[tuple[float, float, float]]] = [[], []]
        for ri, z in enumerate((h0, h1)):
            for i in range(segs):
                ang = 2 * math.pi * i / segs
                px = cx + radius * math.cos(ang)
                py = cy + radius * math.sin(ang)
                ring[ri].append((px, py, z))
        # side faces
        vi = 0
        for i in range(segs):
            j = (i + 1) % segs
            b0, b1 = ring[0][i], ring[0][j]
            t0, t1 = ring[1][i], ring[1][j]
            # outward normal approx mid
            mx = (b0[0] + b1[0]) / 2 - cx
            my = (b0[1] + b1[1]) / 2 - cy
            ln = math.hypot(mx, my) or 1.0
            nx, ny = mx / ln, my / ln
            for p in (b0, b1, t1, t0):
                gx, gy, gz = _mm_to_gltf(p[0], p[1], p[2])
                pos.extend([gx, gy, gz])
                # normal in glTF: plan n → (nx, 0, ny)
                nrm.extend([nx, 0.0, ny])
            idx.extend([vi, vi + 1, vi + 2, vi, vi + 2, vi + 3])
            vi += 4
        return pos, nrm, idx

    # horizontal: axis along start→end at mid elevation
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-3:
        return [], [], []
    ux, uy = dx / length, dy / length
    # perpendicular in plan
    px, py = -uy, ux
    z_mid = (z_bot + z_top) / 2.0
    r = radius
    # build rings at start and end
    rings: list[list[tuple[float, float, float]]] = [[], []]
    for ri, (cx, cy) in enumerate(((x0, y0), (x1, y1))):
        for i in range(segs):
            ang = 2 * math.pi * i / segs
            # circle in plane perpendicular to axis: mix elev + plan normal
            # local: cos*perp_plan + sin*up
            ox = px * math.cos(ang) * r
            oy = py * math.cos(ang) * r
            oz = math.sin(ang) * r
            rings[ri].append((cx + ox, cy + oy, z_mid + oz))
    vi = 0
    for i in range(segs):
        j = (i + 1) % segs
        s0, s1 = rings[0][i], rings[0][j]
        e0, e1 = rings[1][i], rings[1][j]
        # normal from radial direction at mid
        mx = (s0[0] + e0[0]) / 2 - (x0 + x1) / 2
        my = (s0[1] + e0[1]) / 2 - (y0 + y1) / 2
        mz = (s0[2] + e0[2]) / 2 - z_mid
        # better: use cos/sin of segment
        ang = 2 * math.pi * (i + 0.5) / segs
        n_plan_x = px * math.cos(ang)
        n_plan_y = py * math.cos(ang)
        n_up = math.sin(ang)
        # glTF normal
        gx_n, gy_n, gz_n = n_plan_x, n_up, n_plan_y
        ln = math.sqrt(gx_n * gx_n + gy_n * gy_n + gz_n * gz_n) or 1.0
        gx_n, gy_n, gz_n = gx_n / ln, gy_n / ln, gz_n / ln
        for p in (s0, s1, e1, e0):
            gx, gy, gz = _mm_to_gltf(p[0], p[1], p[2])
            pos.extend([gx, gy, gz])
            nrm.extend([gx_n, gy_n, gz_n])
        idx.extend([vi, vi + 1, vi + 2, vi, vi + 2, vi + 3])
        vi += 4
    return pos, nrm, idx


def _mesh_from_origin_size(
    el: Element, model: ProjectModel
) -> tuple[list[float], list[float], list[int]]:
    try:
        origin = el.params.get("origin_mm")
        size = el.params.get("size_mm") or [100, 100, 100]
        if not origin:
            return [], [], []
        z0_off = float(el.params.get("z0_mm", 0))
        shape = el.params.get("shape", "box")
        x0, y0 = float(origin[0]), float(origin[1])
        lx = float(size[0]) if len(size) > 0 else 100.0
        ly = float(size[1]) if len(size) > 1 else 100.0
        hz = float(size[2]) if len(size) > 2 else ly
        z0 = _level_z(model, el.level_id) + z0_off
        if shape == "cylinder":
            r = max(ly, hz, 30) / 2
            return _cylinder_mesh(x0, y0, x0 + max(lx, 50), y0, z0, z0 + max(hz, ly, 30), r)
        # column: centered box
        if el.category == "column" or el.params.get("fitting_type") == "column":
            ht = float(el.params.get("height_mm") or hz or 3000)
            return _aabb_box_mesh(x0 - lx / 2, y0 - ly / 2, z0, x0 + lx / 2, y0 + ly / 2, z0 + ht)
        return _aabb_box_mesh(x0, y0, z0, x0 + max(lx, 50), y0 + max(ly, 30), z0 + max(hz, 30))
    except (KeyError, TypeError, ValueError, IndexError):
        return [], [], []


def _mesh_from_pipe(el: Element, model: ProjectModel) -> tuple[list[float], list[float], list[int]]:
    try:
        od = 50.0
        if el.params.get("size_mm") and len(el.params["size_mm"]) >= 2:
            od = max(float(el.params["size_mm"][1]), 20.0)
        is_duct = el.category in {"duct", "hvac"} or el.params.get("fitting_type") == "duct"
        is_tray = el.category == "cable_tray" or el.params.get("fitting_type") == "cable_tray"
        is_beam = el.category == "beam" or el.params.get("fitting_type") == "beam"
        is_conduit = el.category == "conduit" or el.params.get("fitting_type") == "conduit"
        is_pipe = el.category in {"pipe", "plumbing_pipe"} or el.params.get("fitting_type") == "pipe"
        if is_duct or is_tray:
            od = float(el.params.get("width_mm") or od)
        if el.params.get("vertical") or el.params.get("orientation") == "vertical":
            o = el.params.get("origin_mm") or el.params.get("start_mm") or [0, 0]
            x, y = float(o[0]), float(o[1])
            z_lo = _level_z(model, el.level_id) + float(el.params.get("z0_mm") or 0)
            z_hi = _level_z(model, el.level_id) + float(
                el.params.get("z1_mm") or (float(el.params.get("z0_mm") or 0) + 1000)
            )
            r = max(od / 2, 15.0)
            if is_pipe or is_conduit:
                return _cylinder_mesh(x, y, x, y, min(z_lo, z_hi), max(z_lo, z_hi), r, vertical=True)
            return _aabb_box_mesh(x - r, y - r, min(z_lo, z_hi), x + r, y + r, max(z_lo, z_hi))
        if "start_mm" in el.params and "end_mm" in el.params:
            s, e = el.params["start_mm"], el.params["end_mm"]
            x0, y0 = float(s[0]), float(s[1])
            x1, y1 = float(e[0]), float(e[1])
        elif "origin_mm" in el.params and "size_mm" in el.params:
            o, sz = el.params["origin_mm"], el.params["size_mm"]
            x0, y0 = float(o[0]), float(o[1])
            x1, y1 = x0 + float(sz[0]), y0
        else:
            return [], [], []
        z0_off = float(el.params.get("z0_mm", 0))
        z0 = _level_z(model, el.level_id) + z0_off
        elev_h = od
        if is_duct:
            elev_h = float(el.params.get("height_mm") or 250)
        elif is_tray:
            elev_h = float(el.params.get("height_mm") or 100)
        elif is_beam:
            elev_h = float(el.params.get("height_mm") or el.params.get("depth_mm") or 300)
            od = float(el.params.get("width_mm") or od or 150)
        if is_pipe or is_conduit:
            r = max(od / 2, 12.0)
            return _cylinder_mesh(x0, y0, x1, y1, z0, z0 + elev_h, r)
        return _wall_box_mesh(x0, y0, x1, y1, od, z0, z0 + elev_h)
    except (KeyError, TypeError, ValueError, IndexError):
        return [], [], []


def _mesh_from_opening(
    el: Element, model: ProjectModel, wall_by_id: dict
) -> tuple[list[float], list[float], list[int]]:
    try:
        host = wall_by_id.get(el.host_id or "")
        if not host:
            return [], [], []
        s = host.params.get("start_mm")
        e = host.params.get("end_mm")
        if not s or not e:
            return [], [], []
        hx0, hy0 = float(s[0]), float(s[1])
        hx1, hy1 = float(e[0]), float(e[1])
        wlen = math.hypot(hx1 - hx0, hy1 - hy0)
        if wlen < 1:
            return [], [], []
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
        # slightly thinner so opening reads as insert
        return _wall_box_mesh(ax, ay, bx, by, max(th * 0.6, 40), z0, z1)
    except (KeyError, TypeError, ValueError, IndexError):
        return [], [], []


def _mesh_from_slab(el: Element, model: ProjectModel) -> tuple[list[float], list[float], list[int]]:
    try:
        poly = el.params.get("polygon_mm") or el.params.get("boundary_mm")
        th = float(el.params.get("thickness_mm") or 200)
        if not poly or len(poly) < 3:
            return [], [], []
        xs = [float(p[0]) for p in poly]
        ys = [float(p[1]) for p in poly]
        z1 = _level_z(model, el.level_id)
        z0 = z1 - th
        return _aabb_box_mesh(min(xs), min(ys), z0, max(xs), max(ys), z1)
    except (KeyError, TypeError, ValueError, IndexError):
        return [], [], []


def _gltf_material_key(el: Element) -> str:
    cat = el.category or ""
    if cat == "wall":
        return "wall"
    if cat == "slab":
        return "slab"
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
    """Write glTF 2.0 JSON with normals, per-layer nodes, presentation materials."""
    buckets: dict[str, dict] = {}

    def _ensure(key: str) -> dict:
        if key not in buckets:
            buckets[key] = {"pos": [], "nrm": [], "idx": [], "base": 0}
        return buckets[key]

    wall_by_id = {el.id: el for el in model.elements if el.category == "wall"}

    for el in model.elements:
        pos: list[float] = []
        nrm: list[float] = []
        indices: list[int] = []
        if el.category == "wall":
            try:
                s = el.params["start_mm"]
                e = el.params["end_mm"]
                th = float(el.params.get("thickness_mm", 200))
                ht = float(el.params.get("height_mm", 3000))
            except (KeyError, TypeError, ValueError):
                continue
            z0 = _level_z(model, el.level_id)
            pos, nrm, indices = _wall_box_mesh(
                float(s[0]), float(s[1]), float(e[0]), float(e[1]), th, z0, z0 + ht
            )
        elif el.category == "slab":
            pos, nrm, indices = _mesh_from_slab(el, model)
        elif el.category in {"door", "window"}:
            pos, nrm, indices = _mesh_from_opening(el, model, wall_by_id)
        elif el.category == "equipment":
            pos, nrm, indices = _mesh_from_origin_size(el, model)
        elif el.category == "column" or el.params.get("fitting_type") == "column":
            pos, nrm, indices = _mesh_from_origin_size(el, model)
        elif el.category == "beam" or el.params.get("fitting_type") == "beam":
            pos, nrm, indices = _mesh_from_pipe(el, model)
        elif el.category in {"pipe", "plumbing_pipe", "conduit", "duct", "hvac", "cable_tray"}:
            pos, nrm, indices = _mesh_from_pipe(el, model)
        elif el.category in _PROXY_CATS:
            if el.params.get("start_mm") and el.params.get("end_mm"):
                pos, nrm, indices = _mesh_from_pipe(el, model)
            else:
                pos, nrm, indices = _mesh_from_origin_size(el, model)
        else:
            continue
        if not pos:
            continue
        key = _gltf_material_key(el)
        _append_mesh(_ensure(key), pos, nrm, indices)

    if not buckets:
        # tiny fallback triangle
        buckets["default"] = {
            "pos": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.5, 1.0, 0.0],
            "nrm": [0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
            "idx": [0, 1, 2],
            "base": 3,
        }

    import base64
    import struct

    all_pos: list[float] = []
    all_nrm: list[float] = []
    all_idx: list[int] = []
    # (mat_key, pos_float_offset, n_verts, idx_start, n_idx)
    prim_meta: list[tuple[str, int, int, int, int]] = []
    vert_base = 0
    for key, b in buckets.items():
        pos = b["pos"]
        nrm = b["nrm"]
        idx = b["idx"]
        if not pos or not idx:
            continue
        if len(nrm) != len(pos):
            # safety: flat up normals
            nrm = [0.0, 1.0, 0.0] * (len(pos) // 3)
        pos_start = len(all_pos)
        n_verts = len(pos) // 3
        all_pos.extend(pos)
        all_nrm.extend(nrm)
        idx_start = len(all_idx)
        for i in idx:
            all_idx.append(vert_base + i)
        prim_meta.append((key, pos_start, n_verts, idx_start, len(idx)))
        vert_base += n_verts

    pos_bytes = b"".join(struct.pack("<f", float(v)) for v in all_pos)
    nrm_bytes = b"".join(struct.pack("<f", float(v)) for v in all_nrm)
    idx_bytes = b"".join(struct.pack("<H", int(i)) for i in all_idx)
    # align
    def _pad(b: bytes) -> bytes:
        p = (4 - (len(b) % 4)) % 4
        return b + (b"\x00" * p)

    pos_bytes_p = _pad(pos_bytes)
    nrm_bytes_p = _pad(nrm_bytes)
    idx_bytes_p = _pad(idx_bytes)
    blob = pos_bytes_p + nrm_bytes_p + idx_bytes_p
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
        rgba, metal, rough = _MATERIAL_PBR.get(key, _MATERIAL_PBR["default"])
        materials.append(
            {
                "name": key,
                "doubleSided": True,
                "alphaMode": "BLEND" if (len(rgba) > 3 and rgba[3] < 0.99) or key in {"wall", "window"} else "OPAQUE",
                "pbrMetallicRoughness": {
                    "baseColorFactor": list(rgba),
                    "metallicFactor": float(metal),
                    "roughnessFactor": float(rough),
                },
            }
        )
    mat_index = {k: i for i, k in enumerate(mat_keys)}

    off_nrm = len(pos_bytes_p)
    off_idx = off_nrm + len(nrm_bytes_p)
    buffer_views = [
        {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_bytes), "target": 34962},
        {"buffer": 0, "byteOffset": off_nrm, "byteLength": len(nrm_bytes), "target": 34962},
        {"buffer": 0, "byteOffset": off_idx, "byteLength": len(idx_bytes), "target": 34963},
    ]

    accessors: list[dict] = [
        {
            "bufferView": 0,
            "byteOffset": 0,
            "componentType": 5126,
            "count": n_verts_total,
            "type": "VEC3",
            "max": [max_x, max_y, max_z],
            "min": [min_x, min_y, min_z],
        },
        {
            "bufferView": 1,
            "byteOffset": 0,
            "componentType": 5126,
            "count": n_verts_total,
            "type": "VEC3",
        },
    ]
    meshes: list[dict] = []
    nodes: list[dict] = []
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
        nrm_acc = len(accessors)
        accessors.append(
            {
                "bufferView": 1,
                "byteOffset": pos_start * 4,  # same float layout as positions
                "componentType": 5126,
                "count": n_verts,
                "type": "VEC3",
            }
        )
        idx_acc = len(accessors)
        accessors.append(
            {
                "bufferView": 2,
                "byteOffset": idx_start * 2,
                "componentType": 5123,
                "count": n_idx,
                "type": "SCALAR",
            }
        )
        mesh_i = len(meshes)
        meshes.append(
            {
                "name": key,
                "primitives": [
                    {
                        "attributes": {"POSITION": pos_acc, "NORMAL": nrm_acc},
                        "indices": idx_acc,
                        "mode": 4,
                        "material": mat_index[key],
                    }
                ],
            }
        )
        nodes.append({"mesh": mesh_i, "name": key})

    gltf = {
        "asset": {"version": "2.0", "generator": "llm-bim-presentation"},
        "buffers": [{"byteLength": len(blob), "uri": uri}],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "materials": materials,
        "meshes": meshes,
        "nodes": nodes,
        "scenes": [{"nodes": list(range(len(nodes))), "name": model.name or "llm-bim"}],
        "scene": 0,
        "extras": {
            "material_legend": {k: _MATERIAL_RGBA.get(k) for k in mat_keys},
            "layer_names": list(mat_keys),
            "units": "metres",
            "up": "Y",
            "honesty": "Presentation envelopes — coordination grade, not PE-stamped fabrication",
        },
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(gltf, indent=2) + "\n", encoding="utf-8")
    return p
