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
    "wall_structure": ([0.72, 0.70, 0.66, 1.0], 0.02, 0.9),
    "wall_insulation": ([0.95, 0.9, 0.45, 1.0], 0.0, 0.95),
    "wall_finish": ([0.92, 0.92, 0.9, 1.0], 0.0, 0.85),
    "wall_membrane": ([0.2, 0.25, 0.35, 1.0], 0.1, 0.7),
    "slab": ([0.55, 0.55, 0.58, 1.0], 0.05, 0.82),
    "equipment": ([0.28, 0.52, 0.82, 1.0], 0.35, 0.45),
    # Equipment kinds — OPAQUE by default (viewer can ghost shells on demand).
    # Low alpha here made whole machines vanish on the dark studio background.
    "equip_shell": ([0.45, 0.78, 0.95, 1.0], 0.45, 0.35),  # bright Al cyan — readable on dark studio
    "equip_yoke": ([0.55, 0.58, 0.62, 1.0], 0.7, 0.4),  # mild steel gray (not near-black)
    "equip_magnet": ([0.25, 0.32, 0.55, 1.0], 0.45, 0.4),  # N42 deep blue-gray RING (was vanishing on bg)
    "equip_cartridge": ([0.95, 0.62, 0.28, 1.0], 0.05, 0.5),  # Ultem amber
    "equip_flange": ([0.75, 0.78, 0.82, 1.0], 0.65, 0.35),
    "equip_collector": ([0.7, 0.72, 0.75, 1.0], 0.85, 0.25),  # Mo
    "equip_port": ([0.35, 0.85, 0.55, 1.0], 0.35, 0.4),  # KF / gland
    "equip_spacer": ([0.85, 0.82, 0.55, 1.0], 0.15, 0.55),
    "equip_pedestal": ([0.5, 0.52, 0.55, 1.0], 0.2, 0.7),
    "equip_step_ref": ([0.65, 0.7, 0.85, 1.0], 0.1, 0.5),  # locked STEP bbox
    "fab_ultem": ([1.0, 0.55, 0.15, 1.0], 0.05, 0.4),  # slotted cartridge BREP — high contrast
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
    # Fine detail layers (wires / coils / fasteners / joined flanges)
    "wire": ([0.92, 0.72, 0.22, 1.0], 0.9, 0.22),  # copper conductor
    "wire_steel": ([0.55, 0.58, 0.62, 1.0], 0.85, 0.3),
    "coil": ([0.72, 0.38, 0.12, 1.0], 0.88, 0.28),  # copper coil
    "bolt": ([0.42, 0.44, 0.48, 1.0], 0.9, 0.28),  # A325 steel
    "flange": ([0.48, 0.5, 0.54, 1.0], 0.75, 0.35),  # joined material section
    "fab_part": ([0.55, 0.58, 0.62, 1.0], 0.88, 0.32),  # machined steel BREP
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
    "wire",
    "coil",
    "bolt",
    "fastener",
    "flange",
    "joint",
}


def _merge_meshes(
    parts: list[tuple[list[float], list[float], list[int]]],
) -> tuple[list[float], list[float], list[int]]:
    """Concatenate solid meshes (local 0-based indices each)."""
    pos: list[float] = []
    nrm: list[float] = []
    idx: list[int] = []
    base = 0
    for p, n, i in parts:
        if not p or not i:
            continue
        pos.extend(p)
        nrm.extend(n)
        for vi in i:
            idx.append(base + vi)
        base += len(p) // 3
    return pos, nrm, idx


def _disk_mesh(
    cx: float,
    cy: float,
    cz: float,
    radius: float,
    thickness: float,
    *,
    axis: str = "y",
    segments: int = 28,
) -> tuple[list[float], list[float], list[int]]:
    """Short cylinder (flange / washer) centered at plan XY, elev cz."""
    r = max(radius, 1.0)
    th = max(thickness, 1.0)
    half = th / 2.0
    if axis == "y":  # vertical axis in plan? elev is Y in glTF — disk in XZ, normal +Y
        return _cylinder_mesh(cx, cy, cx, cy, cz - half, cz + half, r, vertical=True, segments=segments)
    # horizontal axis along +X (plan east)
    return _cylinder_mesh(cx - half, cy, cx + half, cy, cz - r, cz + r, r, segments=segments, caps=True)


def _bolt_mesh(
    cx: float,
    cy: float,
    z0: float,
    *,
    shank_d: float = 20.0,
    shank_len: float = 60.0,
    head_af: float = 30.0,
    head_h: float = 14.0,
    orientation: str = "vertical",
) -> tuple[list[float], list[float], list[int]]:
    """Hex head + cylindrical shank (presentation fastener)."""
    r = max(shank_d, 4.0) / 2.0
    parts: list[tuple[list[float], list[float], list[int]]] = []
    # hex head as 6-sided prism approximated with short cylinder (readable under orbit)
    head_r = max(head_af, shank_d * 1.5) / 2.0
    if orientation == "vertical":
        parts.append(
            _cylinder_mesh(
                cx, cy, cx, cy, z0 + shank_len, z0 + shank_len + head_h, head_r, vertical=True, segments=6
            )
        )
        parts.append(
            _cylinder_mesh(cx, cy, cx, cy, z0, z0 + shank_len, r, vertical=True, segments=16)
        )
    else:
        # horizontal along +X from origin
        parts.append(
            _cylinder_mesh(cx, cy, cx + shank_len, cy, z0 - r, z0 + r, r, segments=16)
        )
        parts.append(
            _cylinder_mesh(
                cx + shank_len,
                cy,
                cx + shank_len + head_h,
                cy,
                z0 - head_r,
                z0 + head_r,
                head_r,
                segments=6,
            )
        )
    return _merge_meshes(parts)


def _helix_coil_mesh(
    cx: float,
    cy: float,
    z0: float,
    *,
    coil_radius: float = 80.0,
    tube_radius: float = 8.0,
    turns: float = 6.0,
    pitch: float = 24.0,
    axis: str = "vertical",
    segs_per_turn: int = 16,
) -> tuple[list[float], list[float], list[int]]:
    """Helical tube (coil / spring / wound conductor)."""
    cr = max(coil_radius, 10.0)
    tr = max(tube_radius, 2.0)
    n_turns = max(1.0, float(turns))
    n = max(8, int(segs_per_turn * n_turns))
    parts: list[tuple[list[float], list[float], list[int]]] = []
    pts: list[tuple[float, float, float]] = []
    for i in range(n + 1):
        t = i / n
        ang = 2 * math.pi * n_turns * t
        if axis == "vertical":
            x = cx + cr * math.cos(ang)
            y = cy + cr * math.sin(ang)
            z = z0 + pitch * n_turns * t
            pts.append((x, y, z))
        else:
            # axis along +X
            x = cx + pitch * n_turns * t
            y = cy + cr * math.cos(ang)
            z = z0 + cr * math.sin(ang)
            pts.append((x, y, z))
    # short cylinders between successive samples
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        # vertical-ish vs horizontal cylinder pick
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        if abs(dz) > abs(dx) and abs(dz) > abs(dy) and math.hypot(dx, dy) < tr * 0.5:
            parts.append(
                _cylinder_mesh(
                    a[0], a[1], a[0], a[1], min(a[2], b[2]), max(a[2], b[2]), tr, vertical=True, segments=10, caps=False
                )
            )
        else:
            # use mid elev span for horizontal cylinder API
            z_lo = min(a[2], b[2]) - tr
            z_hi = max(a[2], b[2]) + tr
            # better: place cylinder along plan projection with elev at midpoint
            zm = (a[2] + b[2]) / 2.0
            # if mostly plan-horizontal, standard horizontal cylinder
            if math.hypot(dx, dy) > 1e-3:
                parts.append(
                    _cylinder_mesh(a[0], a[1], b[0], b[1], zm - tr, zm + tr, tr, segments=10, caps=False)
                )
            else:
                parts.append(
                    _cylinder_mesh(
                        a[0], a[1], a[0], a[1], min(a[2], b[2]), max(a[2], b[2]), tr, vertical=True, segments=10, caps=False
                    )
                )
    return _merge_meshes(parts)


def _fitting_detail_mesh(
    el: Element, model: ProjectModel
) -> tuple[list[float], list[float], list[int]]:
    """Elbow / tee / flange / coupler as joined material solids (not a single box)."""
    try:
        origin = el.params.get("origin_mm") or [0, 0]
        x0, y0 = float(origin[0]), float(origin[1])
        size = el.params.get("size_mm") or [80, 80, 80]
        od = max(float(size[1]) if len(size) > 1 else 40.0, 15.0)
        r = od / 2.0
        z0 = _level_z(model, el.level_id) + float(el.params.get("z0_mm") or 0)
        ftype = str(el.params.get("fitting_type") or "").lower()
        arm = max(od * 1.8, 40.0)
        parts: list[tuple[list[float], list[float], list[int]]] = []

        if ftype in {"elbow_90", "elbow", "elb90"}:
            # two legs of a 90° elbow in plan + small bend body
            parts.append(_cylinder_mesh(x0, y0, x0 + arm, y0, z0 - r, z0 + r, r, segments=20))
            parts.append(_cylinder_mesh(x0, y0, x0, y0 + arm, z0 - r, z0 + r, r, segments=20))
            # join fillet: short vertical-ish torus approx as disk at corner
            parts.append(
                _cylinder_mesh(x0, y0, x0, y0, z0 - r * 1.1, z0 + r * 1.1, r * 1.15, vertical=True, segments=16)
            )
        elif ftype in {"elbow_45", "elb45"}:
            parts.append(_cylinder_mesh(x0, y0, x0 + arm, y0, z0 - r, z0 + r, r, segments=20))
            dx, dy = arm * 0.707, arm * 0.707
            parts.append(_cylinder_mesh(x0, y0, x0 + dx, y0 + dy, z0 - r, z0 + r, r, segments=20))
        elif ftype in {"tee", "t"}:
            parts.append(_cylinder_mesh(x0 - arm, y0, x0 + arm, y0, z0 - r, z0 + r, r, segments=20))
            parts.append(_cylinder_mesh(x0, y0, x0, y0 + arm, z0 - r, z0 + r, r, segments=20))
        elif ftype in {"flange", "union", "coupler", "coupling", "cpl"}:
            # pipe stub + two flange disks (joined materials)
            parts.append(_cylinder_mesh(x0 - arm * 0.6, y0, x0 + arm * 0.6, y0, z0 - r, z0 + r, r, segments=24))
            fr = r * 1.8
            for sx in (-arm * 0.55, arm * 0.55):
                parts.append(
                    _cylinder_mesh(
                        x0 + sx - 6, y0, x0 + sx + 6, y0, z0 - fr, z0 + fr, fr, segments=24
                    )
                )
        elif ftype in {"cap"}:
            parts.append(_cylinder_mesh(x0, y0, x0 + arm * 0.4, y0, z0 - r, z0 + r, r, segments=20))
            parts.append(
                _cylinder_mesh(x0, y0, x0, y0, z0 - r * 1.05, z0 + r * 1.05, r * 1.05, vertical=True, segments=16)
            )
        elif ftype in {"ball_valve", "gate_valve", "valve"}:
            # body box + two ports
            parts.append(_aabb_box_mesh(x0 - od, y0 - od, z0 - od, x0 + od, y0 + od, z0 + od))
            parts.append(_cylinder_mesh(x0 - arm, y0, x0 + arm, y0, z0 - r * 0.8, z0 + r * 0.8, r * 0.8, segments=16))
            # stem
            parts.append(
                _cylinder_mesh(x0, y0, x0, y0, z0 + od * 0.5, z0 + od * 2.0, r * 0.35, vertical=True, segments=12)
            )
        else:
            # generic joined fitting: cylinder body + end flanges
            parts.append(_cylinder_mesh(x0 - arm * 0.5, y0, x0 + arm * 0.5, y0, z0 - r, z0 + r, r, segments=20))
            fr = r * 1.6
            for sx in (-arm * 0.45, arm * 0.45):
                parts.append(
                    _cylinder_mesh(x0 + sx - 5, y0, x0 + sx + 5, y0, z0 - fr, z0 + fr, fr, segments=20)
                )
        return _merge_meshes(parts)
    except (KeyError, TypeError, ValueError, IndexError):
        return [], [], []


def _mesh_from_detail(
    el: Element, model: ProjectModel
) -> tuple[list[float], list[float], list[int]]:
    """Wire / coil / bolt / flange detail solids."""
    try:
        cat = el.category or ""
        ftype = str(el.params.get("fitting_type") or "").lower()
        shape = str(el.params.get("shape") or "").lower()
        origin = el.params.get("origin_mm") or el.params.get("start_mm") or [0, 0]
        x0, y0 = float(origin[0]), float(origin[1])
        z0 = _level_z(model, el.level_id) + float(el.params.get("z0_mm") or 0)

        if cat == "bolt" or ftype == "bolt" or shape == "bolt":
            return _bolt_mesh(
                x0,
                y0,
                z0,
                shank_d=float(el.params.get("shank_d_mm") or el.params.get("diameter_mm") or 20),
                shank_len=float(el.params.get("shank_len_mm") or el.params.get("length_mm") or 60),
                head_af=float(el.params.get("head_af_mm") or 30),
                head_h=float(el.params.get("head_h_mm") or 14),
                orientation=str(el.params.get("orientation") or "vertical"),
            )

        if cat == "coil" or ftype == "coil" or shape == "coil":
            if el.params.get("tube_radius_mm") is not None:
                tr = float(el.params["tube_radius_mm"])
            elif el.params.get("wire_d_mm") is not None:
                tr = float(el.params["wire_d_mm"]) / 2.0
            else:
                tr = 8.0
            return _helix_coil_mesh(
                x0,
                y0,
                z0,
                coil_radius=float(el.params.get("coil_radius_mm") or 80),
                tube_radius=tr,
                turns=float(el.params.get("turns") or 6),
                pitch=float(el.params.get("pitch_mm") or 24),
                axis=str(el.params.get("orientation") or el.params.get("axis") or "vertical"),
            )

        if cat == "wire" or ftype == "wire" or shape == "wire":
            od = float(el.params.get("diameter_mm") or el.params.get("wire_d_mm") or 6)
            r = max(od / 2.0, 1.5)
            if el.params.get("vertical") or el.params.get("orientation") == "vertical":
                z1 = z0 + float(el.params.get("length_mm") or 1000)
                return _cylinder_mesh(x0, y0, x0, y0, min(z0, z1), max(z0, z1), r, vertical=True, segments=12)
            s = el.params.get("start_mm") or origin
            e = el.params.get("end_mm")
            if not e:
                length = float(el.params.get("length_mm") or 1000)
                e = [x0 + length, y0]
            x1, y1 = float(e[0]), float(e[1])
            return _cylinder_mesh(float(s[0]), float(s[1]), x1, y1, z0 - r, z0 + r, r, segments=12)

        if cat in {"flange", "joint"} or ftype in {"flange", "joint"}:
            od = float(el.params.get("od_mm") or el.params.get("diameter_mm") or 120)
            th = float(el.params.get("thickness_mm") or 18)
            r = od / 2.0
            # flange disk + short neck (joined section)
            parts = [
                _cylinder_mesh(x0 - th / 2, y0, x0 + th / 2, y0, z0 - r, z0 + r, r, segments=28),
                _cylinder_mesh(
                    x0 - th, y0, x0 + th, y0, z0 - r * 0.45, z0 + r * 0.45, r * 0.45, segments=20
                ),
            ]
            return _merge_meshes(parts)

        return [], [], []
    except (KeyError, TypeError, ValueError, IndexError):
        return [], [], []


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
    segments: int = 32,
    caps: bool = True,
) -> tuple[list[float], list[float], list[int]]:
    """Round cylinder with smooth radial normals (pipe/conduit presentation).

    ``segments`` default 32 reads as circular under orbit review (was 14 faceted).
    """
    segs = max(12, int(segments))
    r = max(float(radius), 1.0)
    pos: list[float] = []
    nrm: list[float] = []
    idx: list[int] = []

    def _emit(gxyz: tuple[float, float, float], nxyz: tuple[float, float, float]) -> int:
        vi = len(pos) // 3
        pos.extend(gxyz)
        nrm.extend(nxyz)
        return vi

    if vertical:
        cx, cy = x0, y0
        h0, h1 = min(z_bot, z_top), max(z_bot, z_top)
        # Shared ring verts with smooth normals (one normal per radial angle)
        bot_i: list[int] = []
        top_i: list[int] = []
        for i in range(segs):
            ang = 2 * math.pi * i / segs
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            px = cx + r * cos_a
            py = cy + r * sin_a
            # glTF normal: plan radial → (nx, 0, ny)
            ng = (cos_a, 0.0, sin_a)
            bot_i.append(_emit(_mm_to_gltf(px, py, h0), ng))
            top_i.append(_emit(_mm_to_gltf(px, py, h1), ng))
        for i in range(segs):
            j = (i + 1) % segs
            a, b, c, d = bot_i[i], bot_i[j], top_i[j], top_i[i]
            idx.extend([a, b, c, a, c, d])
        if caps:
            # flat end caps (hard normals along ±Y in glTF)
            cb = _emit(_mm_to_gltf(cx, cy, h0), (0.0, -1.0, 0.0))
            ct = _emit(_mm_to_gltf(cx, cy, h1), (0.0, 1.0, 0.0))
            cap_bot: list[int] = []
            cap_top: list[int] = []
            for i in range(segs):
                ang = 2 * math.pi * i / segs
                cos_a, sin_a = math.cos(ang), math.sin(ang)
                px = cx + r * cos_a
                py = cy + r * sin_a
                cap_bot.append(_emit(_mm_to_gltf(px, py, h0), (0.0, -1.0, 0.0)))
                cap_top.append(_emit(_mm_to_gltf(px, py, h1), (0.0, 1.0, 0.0)))
            for i in range(segs):
                j = (i + 1) % segs
                idx.extend([cb, cap_bot[j], cap_bot[i]])
                idx.extend([ct, cap_top[i], cap_top[j]])
        return pos, nrm, idx

    # horizontal: axis along start→end at mid elevation
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-3:
        return [], [], []
    ux, uy = dx / length, dy / length
    # unit vectors in plan: along axis, plan-perp, elev-up
    px, py = -uy, ux
    z_mid = (z_bot + z_top) / 2.0
    start_i: list[int] = []
    end_i: list[int] = []
    for i in range(segs):
        ang = 2 * math.pi * i / segs
        cos_a, sin_a = math.cos(ang), math.sin(ang)
        # radial offset in mm plan+elev
        ox = px * cos_a * r
        oy = py * cos_a * r
        oz = sin_a * r
        # smooth normal in glTF
        nx, ny, nz = px * cos_a, sin_a, py * cos_a
        ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        ng = (nx / ln, ny / ln, nz / ln)
        start_i.append(_emit(_mm_to_gltf(x0 + ox, y0 + oy, z_mid + oz), ng))
        end_i.append(_emit(_mm_to_gltf(x1 + ox, y1 + oy, z_mid + oz), ng))
    for i in range(segs):
        j = (i + 1) % segs
        a, b, c, d = start_i[i], start_i[j], end_i[j], end_i[i]
        idx.extend([a, b, c, a, c, d])
    if caps:
        # axis direction in glTF: plan (ux,0,uy)
        n_start = (-ux, 0.0, -uy)
        n_end = (ux, 0.0, uy)
        cs = _emit(_mm_to_gltf(x0, y0, z_mid), n_start)
        ce = _emit(_mm_to_gltf(x1, y1, z_mid), n_end)
        cap_s: list[int] = []
        cap_e: list[int] = []
        for i in range(segs):
            ang = 2 * math.pi * i / segs
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            ox = px * cos_a * r
            oy = py * cos_a * r
            oz = sin_a * r
            cap_s.append(_emit(_mm_to_gltf(x0 + ox, y0 + oy, z_mid + oz), n_start))
            cap_e.append(_emit(_mm_to_gltf(x1 + ox, y1 + oy, z_mid + oz), n_end))
        for i in range(segs):
            j = (i + 1) % segs
            idx.extend([cs, cap_s[j], cap_s[i]])
            idx.extend([ce, cap_e[i], cap_e[j]])
    return pos, nrm, idx


def _tube_mesh(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    z_bot: float,
    z_top: float,
    r_outer: float,
    r_inner: float,
    *,
    segments: int = 32,
) -> tuple[list[float], list[float], list[int]]:
    """Horizontal hollow tube (magnet ring / pressure shell) — outer + inner + annular caps."""
    ro = max(float(r_outer), 2.0)
    ri = max(min(float(r_inner), ro - 1.0), 0.5)
    # Outer wall (caps off — annular ends added below)
    outer = _cylinder_mesh(x0, y0, x1, y1, z_bot, z_top, ro, segments=segments, caps=False)
    # Inner wall: reverse winding so normals face the bore
    inner = _cylinder_mesh(x0, y0, x1, y1, z_bot, z_top, ri, segments=segments, caps=False)
    # Flip inner indices (reverse each triangle)
    ipos, inrm, iidx = inner
    # invert normals
    inrm = [-n for n in inrm]
    flipped: list[int] = []
    for t in range(0, len(iidx), 3):
        flipped.extend([iidx[t], iidx[t + 2], iidx[t + 1]])
    # Annular end caps at both ends
    segs = max(12, int(segments))
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-3:
        return _merge_meshes([outer, (ipos, inrm, flipped)])
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    z_mid = (z_bot + z_top) / 2.0
    pos: list[float] = []
    nrm: list[float] = []
    idx: list[int] = []

    def _emit(gxyz: tuple[float, float, float], nxyz: tuple[float, float, float]) -> int:
        vi = len(pos) // 3
        pos.extend(gxyz)
        nrm.extend(nxyz)
        return vi

    for end, nx_sign in ((0.0, -1.0), (1.0, 1.0)):
        cx = x0 + ux * length * end
        cy = y0 + uy * length * end
        n_end = (nx_sign * ux, 0.0, nx_sign * uy)
        ring_o: list[int] = []
        ring_i: list[int] = []
        for i in range(segs):
            ang = 2 * math.pi * i / segs
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            ox_o = px * cos_a * ro
            oy_o = py * cos_a * ro
            oz_o = sin_a * ro
            ox_i = px * cos_a * ri
            oy_i = py * cos_a * ri
            oz_i = sin_a * ri
            ring_o.append(_emit(_mm_to_gltf(cx + ox_o, cy + oy_o, z_mid + oz_o), n_end))
            ring_i.append(_emit(_mm_to_gltf(cx + ox_i, cy + oy_i, z_mid + oz_i), n_end))
        for i in range(segs):
            j = (i + 1) % segs
            if nx_sign > 0:
                idx.extend([ring_i[i], ring_o[i], ring_o[j], ring_i[i], ring_o[j], ring_i[j]])
            else:
                idx.extend([ring_i[i], ring_o[j], ring_o[i], ring_i[i], ring_i[j], ring_o[j]])
    return _merge_meshes([outer, (ipos, inrm, flipped), (pos, nrm, idx)])


def _parse_w_section(section: str | None) -> dict[str, float]:
    """Approximate AISC W-shape dims (mm) from designation e.g. W10x33 / W12×26.

    Coordination-grade I profile — not mill-certified plate thicknesses.
    """
    s = (section or "W10x33").upper().replace("×", "x").replace(" ", "")
    d_in, weight = 10.0, 33.0
    if s.startswith("W") and "X" in s:
        try:
            body = s[1:]
            a, b = body.split("X", 1)
            d_in = float(a)
            weight = float(b.split("-")[0])
        except ValueError:
            pass
    d = d_in * 25.4
    # rough bf/tf/tw from depth + weight class (presentation, not AISC table)
    bf = max(d * 0.55, d_in * 20.0)  # ~ half to 0.8 of depth
    if d_in <= 8:
        bf = max(bf, 100.0)
    tf = max(d * 0.045, 8.0)
    tw = max(d * 0.028, 6.0)
    # heavier sections → thicker flanges
    if weight > 40:
        tf *= 1.15
        tw *= 1.1
        bf *= 1.05
    return {"d_mm": d, "bf_mm": bf, "tf_mm": tf, "tw_mm": tw}


def _w_column_mesh(
    cx: float,
    cy: float,
    z0: float,
    z1: float,
    *,
    d_mm: float,
    bf_mm: float,
    tf_mm: float,
    tw_mm: float,
    rotation_deg: float = 0.0,
) -> tuple[list[float], list[float], list[int]]:
    """Vertical wide-flange column (I extruded along elevation)."""
    d, bf, tf, tw = float(d_mm), float(bf_mm), float(tf_mm), float(tw_mm)
    # local plan: X = flange width, Y = depth; then rotate about Z
    rot = math.radians(float(rotation_deg))
    c, s = math.cos(rot), math.sin(rot)

    def _r(lx: float, ly: float) -> tuple[float, float]:
        return cx + lx * c - ly * s, cy + lx * s + ly * c

    parts: list[tuple[list[float], list[float], list[int]]] = []
    # bottom flange
    x0, y0 = _r(-bf / 2, -d / 2)
    x1, y1 = _r(bf / 2, -d / 2 + tf)
    # axis-aligned AABB of rotated flange is wrong for 45° — build via corners
    # Use unrotated boxes when rot~0; for general rot use three wall_box strips
    if abs(rot) < 1e-6:
        parts.append(_aabb_box_mesh(cx - bf / 2, cy - d / 2, z0, cx + bf / 2, cy - d / 2 + tf, z1))
        parts.append(_aabb_box_mesh(cx - bf / 2, cy + d / 2 - tf, z0, cx + bf / 2, cy + d / 2, z1))
        parts.append(_aabb_box_mesh(cx - tw / 2, cy - d / 2 + tf, z0, cx + tw / 2, cy + d / 2 - tf, z1))
    else:
        # three rectangular prisms along local axes via corner sets
        def _prism(lx0: float, ly0: float, lx1: float, ly1: float) -> tuple:
            corners = []
            for lx, ly, z in (
                (lx0, ly0, z0),
                (lx1, ly0, z0),
                (lx1, ly1, z0),
                (lx0, ly1, z0),
                (lx0, ly0, z1),
                (lx1, ly0, z1),
                (lx1, ly1, z1),
                (lx0, ly1, z1),
            ):
                px, py = _r(lx, ly)
                corners.append((px, py, z))
            return _box_solid(corners)

        parts.append(_prism(-bf / 2, -d / 2, bf / 2, -d / 2 + tf))
        parts.append(_prism(-bf / 2, d / 2 - tf, bf / 2, d / 2))
        parts.append(_prism(-tw / 2, -d / 2 + tf, tw / 2, d / 2 - tf))
    return _merge_meshes(parts)


def _w_beam_mesh(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    z_bot: float,
    *,
    d_mm: float,
    bf_mm: float,
    tf_mm: float,
    tw_mm: float,
) -> tuple[list[float], list[float], list[int]]:
    """Horizontal wide-flange beam along plan start→end (depth vertical)."""
    d, bf, tf, tw = float(d_mm), float(bf_mm), float(tf_mm), float(tw_mm)
    z_top = z_bot + d
    parts = [
        _wall_box_mesh(x0, y0, x1, y1, bf, z_bot, z_bot + tf),  # bottom flange
        _wall_box_mesh(x0, y0, x1, y1, bf, z_top - tf, z_top),  # top flange
        _wall_box_mesh(x0, y0, x1, y1, tw, z_bot + tf, z_top - tf),  # web
    ]
    return _merge_meshes(parts)


def _wall_join_extensions(
    model: ProjectModel,
) -> dict[str, tuple[float, float]]:
    """For each wall id → (extend_start_mm, extend_end_mm) so corners meet.

    When wall endpoints coincide (within tol), extend each leg by the other wall's
    half-thickness so 3D/plan bands don't leave corner gaps (Revit-like clean join).
    """
    walls = [el for el in model.elements if el.category == "wall"]
    ext: dict[str, list[float]] = {el.id: [0.0, 0.0] for el in walls}
    tol = 25.0  # mm

    def _ends(el: Element) -> tuple[float, float, float, float, float] | None:
        try:
            s, e = el.params["start_mm"], el.params["end_mm"]
            th = float(el.params.get("thickness_mm") or 200)
            return float(s[0]), float(s[1]), float(e[0]), float(e[1]), th
        except (KeyError, TypeError, ValueError, IndexError):
            return None

    parsed = [(el, _ends(el)) for el in walls]
    parsed = [(el, ep) for el, ep in parsed if ep is not None]
    for i, (el_a, a) in enumerate(parsed):
        ax0, ay0, ax1, ay1, ath = a
        for el_b, b in parsed[i + 1 :]:
            bx0, by0, bx1, by1, bth = b
            pairs = (
                (0, (ax0, ay0), (bx0, by0), bth),
                (0, (ax0, ay0), (bx1, by1), bth),
                (1, (ax1, ay1), (bx0, by0), bth),
                (1, (ax1, ay1), (bx1, by1), bth),
                # also extend B when A meets
            )
            for end_i, pa, pb, other_th in pairs:
                if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) <= tol:
                    ext[el_a.id][end_i] = max(ext[el_a.id][end_i], other_th / 2.0)
            # reverse: B's ends against A
            for end_i, pb, pa, other_th in (
                (0, (bx0, by0), (ax0, ay0), ath),
                (0, (bx0, by0), (ax1, ay1), ath),
                (1, (bx1, by1), (ax0, ay0), ath),
                (1, (bx1, by1), (ax1, ay1), ath),
            ):
                if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) <= tol:
                    ext[el_b.id][end_i] = max(ext[el_b.id][end_i], other_th / 2.0)
    return {k: (v[0], v[1]) for k, v in ext.items()}


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
            od = max(ly, hz, 30)
            r = od / 2
            # Inner diameter: explicit id_mm / inner_d_mm, or kind defaults for rings/tubes
            id_mm = el.params.get("id_mm")
            if id_mm is None:
                id_mm = el.params.get("inner_d_mm")
            if id_mm is None:
                id_mm = el.params.get("bore_mm")
            kind = str(el.params.get("kind") or "").lower()
            if id_mm is None:
                # magnets / shells / yoke / cartridge default to hollow when OD known
                if kind in {"magnet", "mag_spacer"}:
                    id_mm = od * 0.68  # typical N42 ring ID/OD ~340/500
                elif kind in {"shell", "yoke", "cartridge"}:
                    wall = float(el.params.get("wall_mm") or (10.0 if kind == "shell" else 25.0))
                    if kind == "cartridge":
                        wall = float(el.params.get("wall_mm") or 14.0)
                    id_mm = max(od - 2 * wall, od * 0.5)
            x1 = x0 + max(lx, 50)
            z1 = z0 + od
            if id_mm is not None and float(id_mm) > 1.0 and float(id_mm) < od - 1.0:
                return _tube_mesh(
                    x0, y0, x1, y0, z0, z1, r, float(id_mm) / 2.0, segments=36
                )
            return _cylinder_mesh(x0, y0, x1, y0, z0, z1, r, segments=28)
        # column: W-section I when section looks like W##x##
        if el.category == "column" or el.params.get("fitting_type") == "column":
            ht = float(el.params.get("height_mm") or hz or 3000)
            sec = str(el.params.get("section") or "")
            dims = el.params.get("section_dims_mm") or _parse_w_section(sec)
            if str(sec).upper().startswith("W") or el.params.get("shape") == "w_section":
                return _w_column_mesh(
                    x0,
                    y0,
                    z0,
                    z0 + ht,
                    d_mm=float(dims.get("d_mm") or lx),
                    bf_mm=float(dims.get("bf_mm") or ly),
                    tf_mm=float(dims.get("tf_mm") or 12),
                    tw_mm=float(dims.get("tw_mm") or 8),
                    rotation_deg=float(el.params.get("rotation_deg") or 0),
                )
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
                return _cylinder_mesh(
                    x, y, x, y, min(z_lo, z_hi), max(z_lo, z_hi), r, vertical=True, segments=32
                )
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
            sec = str(el.params.get("section") or "")
            dims = el.params.get("section_dims_mm") or _parse_w_section(sec)
            if str(sec).upper().startswith("W") or el.params.get("shape") == "w_section":
                return _w_beam_mesh(
                    x0,
                    y0,
                    x1,
                    y1,
                    z0,
                    d_mm=float(dims.get("d_mm") or elev_h),
                    bf_mm=float(dims.get("bf_mm") or od),
                    tf_mm=float(dims.get("tf_mm") or 12),
                    tw_mm=float(dims.get("tw_mm") or 8),
                )
        if is_pipe or is_conduit:
            r = max(od / 2, 12.0)
            return _cylinder_mesh(x0, y0, x1, y1, z0, z0 + elev_h, r, segments=32)
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
    ftype = str(el.params.get("fitting_type") or "").lower()
    if cat == "wall":
        return "wall"
    if cat == "slab":
        return "slab"
    if cat == "door":
        return "door"
    if cat == "window":
        return "window"
    if cat == "equipment":
        kind = str(el.params.get("kind") or "").lower()
        if kind in {"shell"}:
            return "equip_shell"
        if kind in {"yoke"}:
            return "equip_yoke"
        if kind in {"magnet"}:
            return "equip_magnet"
        if kind in {"cartridge"}:
            return "equip_cartridge"
        if kind in {"flange"}:
            return "equip_flange"
        if kind in {"collector"}:
            return "equip_collector"
        if kind in {"kf40_port", "kf25_port", "gland", "port"}:
            return "equip_port"
        if kind in {"mag_spacer", "spacer"}:
            return "equip_spacer"
        if kind in {"pedestal"}:
            return "equip_pedestal"
        if kind in {"step_ref", "step"}:
            return "equip_step_ref"
        return "equipment"
    if cat == "fab_part":
        mat = str(el.params.get("material_id") or el.params.get("material_spec") or "").lower()
        kind = str(el.params.get("kind") or "").lower()
        if "ultem" in mat or "peek" in mat or "cartridge" in kind:
            return "fab_ultem"
        return "fab_part"
    if cat in {"duct", "hvac"} or ftype == "duct":
        return "duct"
    if cat == "conduit" or ftype == "conduit":
        return "conduit"
    if cat == "cable_tray" or ftype == "cable_tray":
        return "cable_tray"
    if cat == "column" or ftype == "column":
        return "column"
    if cat == "beam" or ftype == "beam":
        return "beam"
    if cat == "bolt" or ftype == "bolt":
        return "bolt"
    if cat == "coil" or ftype == "coil":
        return "coil"
    if cat == "wire" or ftype == "wire":
        mid = str(el.params.get("material_id") or "").lower()
        if "steel" in mid or "alum" in mid:
            return "wire_steel"
        return "wire"
    if cat in {"flange", "joint"} or ftype in {"flange", "joint"}:
        return "flange"
    if cat in {"fixture", "accessory"}:
        return "fixture"
    if cat in {"module_instance", "module_root"}:
        return "module"
    if cat in {"fitting", "fittings"}:
        if ftype in {"flange", "union", "coupler", "coupling"}:
            return "flange"
        return "fitting"
    if cat in {"pipe", "plumbing_pipe"} or ftype == "pipe":
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
    wall_ext = _wall_join_extensions(model)

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
            x0, y0 = float(s[0]), float(s[1])
            x1, y1 = float(e[0]), float(e[1])
            # Extend endpoints so L/T corners meet (coordination join)
            ex0, ex1 = wall_ext.get(el.id, (0.0, 0.0))
            dx, dy = x1 - x0, y1 - y0
            length = math.hypot(dx, dy)
            if length > 1e-3 and (ex0 > 0 or ex1 > 0):
                ux, uy = dx / length, dy / length
                x0 -= ux * ex0
                y0 -= uy * ex0
                x1 += ux * ex1
                y1 += uy * ex1
            layers = el.params.get("wall_layers")
            if not layers and el.type_id:
                try:
                    from llmbim_core.types_catalog import DEFAULT_WALL_TYPES

                    wt = DEFAULT_WALL_TYPES.get(el.type_id)
                    if wt and wt.layers:
                        layers = [L.model_dump() for L in wt.layers]
                except Exception:  # noqa: BLE001
                    layers = None
            if layers and len(layers) >= 2:
                # Offset successive layers from centerline (layered wall assembly)
                total = sum(float(L.get("thickness_mm") or 0) for L in layers) or th
                # walk from -total/2 outward
                if length > 1e-3:
                    nx, ny = -dy / length, dx / length
                else:
                    nx, ny = 0.0, 1.0
                cursor = -total / 2.0
                for L in layers:
                    lt = float(L.get("thickness_mm") or 0)
                    if lt < 1:
                        continue
                    mid = cursor + lt / 2.0
                    ox, oy = nx * mid, ny * mid
                    fn = str(L.get("function") or "structure").lower()
                    key = {
                        "structure": "wall_structure",
                        "insulation": "wall_insulation",
                        "finish": "wall_finish",
                        "membrane": "wall_membrane",
                    }.get(fn, "wall")
                    p2, n2, i2 = _wall_box_mesh(
                        x0 + ox, y0 + oy, x1 + ox, y1 + oy, lt, z0, z0 + ht
                    )
                    if p2:
                        _append_mesh(_ensure(key), p2, n2, i2)
                    cursor += lt
                continue  # layers already appended
            pos, nrm, indices = _wall_box_mesh(x0, y0, x1, y1, th, z0, z0 + ht)
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
        elif el.category in {"wire", "coil", "bolt", "fastener", "flange", "joint"} or el.params.get(
            "fitting_type"
        ) in {"wire", "coil", "bolt", "flange", "joint"}:
            pos, nrm, indices = _mesh_from_detail(el, model)
        elif el.category == "fab_part" and el.params.get("features"):
            try:
                from llmbim_geometry.fab_brep import HAS_CADQUERY, tessellate_features

                if HAS_CADQUERY:
                    # knit into building: world origin (level Z included when host knit)
                    b_origin = el.params.get("building_origin_mm")
                    if b_origin is None and el.params.get("knit"):
                        oz = float(el.params.get("z0_mm") or 0)
                        o = el.params.get("origin_mm") or [0, 0, 0]
                        b_origin = [
                            float(o[0]),
                            float(o[1]),
                            _level_z(model, el.level_id) + oz,
                        ]
                    pos, nrm, indices = tessellate_features(
                        list(el.params.get("features") or []),
                        origin_mm=b_origin,
                        rotation_deg=el.params.get("building_rotation_deg"),
                    )
                else:
                    pos, nrm, indices = [], [], []
            except Exception:  # noqa: BLE001
                pos, nrm, indices = [], [], []
        elif el.category in {"fitting", "fittings"}:
            pos, nrm, indices = _fitting_detail_mesh(el, model)
            if not pos:
                pos, nrm, indices = _mesh_from_origin_size(el, model)
        elif el.category in _PROXY_CATS:
            detail = _mesh_from_detail(el, model)
            if detail[0]:
                pos, nrm, indices = detail
            elif el.params.get("start_mm") and el.params.get("end_mm"):
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
        # Only true glass/translucent layers use BLEND — walls must stay OPAQUE
        # so solids occlude (no "blocks showing through each other").
        is_trans = key == "window" or (len(rgba) > 3 and float(rgba[3]) < 0.99 and key != "wall")
        materials.append(
            {
                "name": key,
                "doubleSided": bool(is_trans),
                "alphaMode": "BLEND" if is_trans else "OPAQUE",
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
