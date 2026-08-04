"""Baked, deterministic shaded axonometric hero render of a model, as an SVG.

``export_deliverables`` writes ``hero.svg`` into every pack and ``index.html``
embeds it (PR #33). This module is the renderer: a shaded axonometric of the
whole building as a self-contained SVG (stdlib only — no WebGL snapshot).

It reuses the exact tessellation the viewer shows by running
:func:`llmbim_geometry.mesh.export_gltf_walls` and reading the triangles back
out of the glTF (positions in metres, glTF Y-up), and it shades each triangle
from the same material palette (:data:`llmbim_geometry.mesh._MATERIAL_RGBA`), so
the still matches the 3D model. The render is deterministic: no RNG and no
wall-clock, so the same model always produces a byte-identical SVG.
"""

from __future__ import annotations

import base64
import json
import math
import struct
import tempfile
from pathlib import Path
from typing import Any

from llmbim_geometry.mesh import _MATERIAL_RGBA, export_gltf_walls

_Vec3 = tuple[float, float, float]
_Vec2 = tuple[float, float]
# (v0, v1, v2, material_key) — world coords in metres, glTF Y-up.
_Tri = tuple[_Vec3, _Vec3, _Vec3, str]

_FALLBACK_RGBA: tuple[float, float, float, float] = (0.62, 0.62, 0.65, 1.0)

# Fixed camera-space light (x right, y up, z toward viewer): over the left
# shoulder and slightly above, so roofs read bright and near walls read mid.
_LIGHT: _Vec3 = (-0.38, 0.72, 0.58)

_AMBIENT = 0.32
_DIFFUSE = 0.68
# Second fill light (opposite shoulder) — residual #14 soft lighting lift
_FILL: _Vec3 = (0.42, 0.25, 0.35)
_FILL_W = 0.22


def render_hero_svg(
    model: Any,
    path: str | Path,
    *,
    size: tuple[int, int] = (1600, 1000),
    azimuth_deg: float = 225.0,
    elevation_deg: float = 30.0,
) -> Path:
    """Render a shaded axonometric hero image of ``model`` to ``path`` as SVG.

    ``model`` is a ``ProjectModel`` or any wrapper exposing ``.model`` (e.g. the
    SDK ``Project``). ``size`` is ``(width, height)`` in pixels. ``azimuth_deg``
    rotates about the vertical (up) axis; ``elevation_deg`` tilts the view. The
    projection is orthographic (true axonometric). Returns the written path.
    """
    tris, name = _gather_triangles(model)
    rows = _rotation_rows(azimuth_deg, elevation_deg)
    faces = _project_and_shade(tris, rows)
    svg = _emit_svg(faces, name, int(size[0]), int(size[1]))
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    return out


def load_gltf_triangles(gltf_path: str | Path) -> tuple[list[_Tri], str]:
    """Load triangles + material keys from an on-disk glTF (exact viewer mesh)."""
    p = Path(gltf_path)
    gltf: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    name = str((gltf.get("asset") or {}).get("extras", {}).get("name") or p.stem)
    # Prefer pack project name from extras if present
    extras = gltf.get("extras") or {}
    if extras.get("name"):
        name = str(extras["name"])
    return _gltf_triangles(gltf), name


# Vertical enclosure ghosted so structure/MEP reads through (roof stays solid
# so primary stills are full-shell, not cutaway iso).
# equip_shell = facility massing envelopes (often mis-tagged as cyan equipment);
# ghost them as walls so they don't read as blue iso cut planes.
_GHOST_WALL_KEYS = frozenset({
    "wall", "wall_structure", "wall_insulation", "wall_finish", "wall_membrane",
    "door", "window", "glass", "curtain", "cladding",
    "equip_shell",
})
# Optional light shell ghost (off by default when ghost_walls=True — roof solid)
_GHOST_SHELL_KEYS = frozenset({
    "slab", "roof", "concrete", "floor",
})
# When ghosting, recolor these keys to neutral wall so cyan massing doesn't
# look like section-cut hatching.
_GHOST_NEUTRAL_KEYS = frozenset({"equip_shell"})
_GHOST_NEUTRAL_RGB = (0.72, 0.74, 0.76)


def render_mesh_png(
    tris: list[_Tri],
    path: str | Path,
    *,
    title: str = "model match",
    size: tuple[int, int] = (1600, 1000),
    azimuth_deg: float = 225.0,
    elevation_deg: float = 30.0,
    dpi: int = 140,
    footer: str | None = None,
    ghost_walls: bool = False,
    wall_alpha: float = 0.22,
    ghost_roof: bool = False,
    roof_alpha: float = 0.45,
) -> Path:
    """Painter-algorithm PNG of glTF triangles — same mesh the 3D viewer shows.

    Includes pipes, tubes, wire_paths, fittings — whatever is in the glTF.

    ``ghost_walls``: draw wall/door/window materials translucent so structure
    reads through — full shell stays closed (no process-open iso cut).
    ``ghost_roof``: also light-ghost roof/slab (default off so roof reads solid).
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib.colors import to_rgba

    rows = _rotation_rows(azimuth_deg, elevation_deg)
    faces = _project_and_shade(
        tris,
        rows,
        ghost_walls=ghost_walls,
        wall_alpha=wall_alpha,
        ghost_roof=ghost_roof,
        roof_alpha=roof_alpha,
    )
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not faces:
        fig = plt.figure(figsize=(size[0] / dpi, size[1] / dpi), dpi=dpi)
        fig.text(0.5, 0.5, "no mesh", ha="center")
        fig.savefig(out, facecolor="#d8dee6")
        plt.close(fig)
        return out

    xs = [x for _d, pts, _c, _a in faces for x, _y in pts]
    ys = [y for _d, pts, _c, _a in faces for _x, y in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)

    fig_w = size[0] / dpi
    fig_h = size[1] / dpi
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=dpi)
    # sky-ish background like hero.svg
    fig.patch.set_facecolor("#c7d3e0")
    ax = fig.add_axes([0.02, 0.06, 0.96, 0.88])
    ax.set_facecolor("#c7d3e0")

    # soft ground shadow under mass
    cx = 0.5 * (min_x + max_x)
    cy = min_y + 0.06 * span_y
    from matplotlib.patches import Ellipse

    ax.add_patch(
        Ellipse(
            (cx, cy),
            width=span_x * 0.95,
            height=span_y * 0.08,
            facecolor="black",
            alpha=0.18,
            zorder=1,
            edgecolor="none",
        )
    )

    # Draw ghost shell first (low zorder), then opaque content on top
    ghost_faces = [(d, pts, c, a) for d, pts, c, a in faces if a < 0.99]
    solid_faces = [(d, pts, c, a) for d, pts, c, a in faces if a >= 0.99]
    for batch, z0 in ((ghost_faces, 2), (solid_faces, 3)):
        if not batch:
            continue
        polys = [list(pts) for _d, pts, _c, _a in batch]
        colors = [to_rgba(c, alpha=a) for _d, _pts, c, a in batch]
        coll = PolyCollection(
            polys,
            facecolors=colors,
            edgecolors="none",
            linewidths=0,
            antialiased=True,
            zorder=z0,
        )
        ax.add_collection(coll)

    pad = 0.05 * max(span_x, span_y)
    ax.set_xlim(min_x - pad, max_x + pad)
    ax.set_ylim(min_y - pad, max_y + pad)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=12, fontweight="bold", color="#1c2530", pad=8)
    foot = footer or (
        "mesh match · exact glTF triangles"
        + (" · ghost walls" if ghost_walls else "")
        + " · [ENGINEERING ESTIMATE — presentation, not PE stamp]"
    )
    fig.text(0.02, 0.012, foot, fontsize=7.5, color="#33404e")
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)
    return out


def _filter_open_process(tris: list[_Tri]) -> list[_Tri]:
    """Drop high canopy roof faces so process train / piping stays readable.

    glTF Y-up: elevation is Y. Keep faces whose centroid is below ~78% of the
    pack height (removes weather canopy panels + roof, keeps deck equipment).
    """
    if not tris:
        return tris
    ys = [v[1] for t in tris for v in t[:3]]
    y0, y1 = min(ys), max(ys)
    cut = y0 + 0.78 * max(y1 - y0, 1e-6)
    keep: list[_Tri] = []
    for v0, v1, v2, key in tris:
        cy = (v0[1] + v1[1] + v2[1]) / 3.0
        if cy > cut:
            continue
        # Drop tall thin south curtain sheets (high vertical span, low thickness)
        span_y = max(v0[1], v1[1], v2[1]) - min(v0[1], v1[1], v2[1])
        span_x = max(v0[0], v1[0], v2[0]) - min(v0[0], v1[0], v2[0])
        span_z = max(v0[2], v1[2], v2[2]) - min(v0[2], v1[2], v2[2])
        if span_y > 0.4 * (y1 - y0) and min(span_x, span_z) < 0.04:
            continue
        keep.append((v0, v1, v2, key))
    return keep or tris


def export_mesh_product_views(
    pack_dir: str | Path,
    *,
    out_subdir: str = "renders",
    title_prefix: str = "llm-bim",
    gltf_name: str = "model.gltf",
) -> list[Path]:
    """Write multi-view PNGs from pack ``model.gltf`` — matches viewer 3D.

    Primary product stills use **full shell + ghost walls** (no process-open
    cutaway; roof solid, walls translucent). Process-open is MEP-only.

    Files:
      R1_iso.png / model_match_iso_full.png  full iso, ghost walls (hero 3-D side)
      model_match_iso.png                    same (no process cut)
      R1_iso_process.png                     process-open (MEP only)
      R2_plan / R3_elev / R4_elev            elev/plan with ghost walls
    """
    pack = Path(pack_dir)
    gltf_path = pack / gltf_name
    if not gltf_path.is_file():
        return []
    tris, gname = load_gltf_triangles(gltf_path)
    if not tris:
        return []
    open_tris = _filter_open_process(tris)
    out = pack / out_subdir
    out.mkdir(parents=True, exist_ok=True)
    prefix = title_prefix or gname
    # (fname, az, el, title, use_open, ghost_walls)
    views: list[tuple[str, float, float, str, bool, bool]] = [
        (
            "R1_iso.png",
            225.0,
            28.0,
            f"{prefix} — isometric · full shell · ghost walls",
            False,
            True,
        ),
        (
            "R1_iso_process.png",
            210.0,
            22.0,
            f"{prefix} — process train open (MEP review)",
            True,
            False,
        ),
        ("R2_plan.png", 0.0, 89.0, f"{prefix} — plan · ghost walls", False, True),
        ("R3_elev.png", 180.0, 0.0, f"{prefix} — elev S · ghost walls", False, True),
        ("R3_elev_S.png", 180.0, 0.0, f"{prefix} — elev S · ghost walls", False, True),
        ("R4_elev_E.png", 90.0, 0.0, f"{prefix} — elev E · ghost walls", False, True),
        (
            "model_match_iso.png",
            225.0,
            28.0,
            f"{prefix} — model-match iso · full shell · ghost walls",
            False,
            True,
        ),
        ("model_match_plan.png", 0.0, 89.0, f"{prefix} — model-match plan · ghost walls", False, True),
        (
            "model_match_iso_full.png",
            225.0,
            28.0,
            f"{prefix} — model-match iso · full shell · ghost walls",
            False,
            True,
        ),
    ]
    paths: list[Path] = []
    for fname, az, el, title, use_open, ghost in views:
        p = out / fname
        render_mesh_png(
            open_tris if use_open else tris,
            p,
            title=title,
            azimuth_deg=az,
            elevation_deg=el,
            size=(1600, 1000) if "iso" in fname else (1600, 900),
            ghost_walls=ghost,
            wall_alpha=0.20,
            ghost_roof=False,  # closed shell — no translucent roof cut look
        )
        paths.append(p)
    man = {
        "rule": "mesh match — exact pack glTF; primary stills = full shell + ghost walls (no iso cut; roof solid)",
        "source": gltf_name,
        "triangle_count": len(tris),
        "triangle_count_process_open": len(open_tris),
        "ghost_walls_primary": True,
        "ghost_roof_primary": False,
        "files": [p.name for p in paths],
        "honesty": "presentation stills from live model mesh — not PE stamp",
    }
    (out / "MESH_VIEWS.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    return paths


# --------------------------------------------------------------------------- #
# Triangle gathering (reuse the glTF tessellation the viewer shows)
# --------------------------------------------------------------------------- #
def _gather_triangles(model: Any) -> tuple[list[_Tri], str]:
    m = getattr(model, "model", model)
    name = str(getattr(m, "name", "") or "Model")
    with tempfile.TemporaryDirectory() as tmp:
        gltf_path = Path(tmp) / "_hero_source.gltf"
        export_gltf_walls(m, gltf_path)
        gltf: dict[str, Any] = json.loads(gltf_path.read_text(encoding="utf-8"))
    return _gltf_triangles(gltf), name


def _decode_buffer(gltf: dict[str, Any]) -> bytes:
    uri = str(gltf["buffers"][0]["uri"])
    b64 = uri.split(",", 1)[1]
    return base64.b64decode(b64)


def _accessor_floats(blob: bytes, gltf: dict[str, Any], acc_index: int) -> list[float]:
    acc = gltf["accessors"][acc_index]
    bv = gltf["bufferViews"][acc["bufferView"]]
    base = int(bv.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
    ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[str(acc["type"])]
    n = int(acc["count"]) * ncomp
    return [float(v) for v in struct.unpack_from(f"<{n}f", blob, base)]


def _accessor_ints(blob: bytes, gltf: dict[str, Any], acc_index: int) -> list[int]:
    acc = gltf["accessors"][acc_index]
    bv = gltf["bufferViews"][acc["bufferView"]]
    base = int(bv.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
    count = int(acc["count"])
    fmt = {5121: "B", 5123: "H", 5125: "I"}[int(acc["componentType"])]
    return [int(v) for v in struct.unpack_from(f"<{count}{fmt}", blob, base)]


def _gltf_triangles(gltf: dict[str, Any]) -> list[_Tri]:
    """Every triangle the default scene renders, once, with a material key.

    The scene references per-element nodes (or the aggregate layer nodes as a
    fallback); either set covers all geometry exactly once, so reading the scene
    avoids the double-count that iterating every mesh would cause.
    """
    blob = _decode_buffer(gltf)
    materials = gltf.get("materials", [])
    scene = gltf["scenes"][int(gltf.get("scene", 0))]
    tris: list[_Tri] = []
    for node_index in scene["nodes"]:
        node = gltf["nodes"][int(node_index)]
        if "mesh" not in node:
            continue
        for prim in gltf["meshes"][int(node["mesh"])]["primitives"]:
            if int(prim.get("mode", 4)) != 4:  # only triangle lists
                continue
            pos = _accessor_floats(blob, gltf, int(prim["attributes"]["POSITION"]))
            idx = _accessor_ints(blob, gltf, int(prim["indices"]))
            mat_i = prim.get("material")
            key = "default"
            if mat_i is not None and 0 <= int(mat_i) < len(materials):
                key = str(materials[int(mat_i)].get("name", "default"))
            for t in range(0, len(idx) - 2, 3):
                a, b, c = idx[t], idx[t + 1], idx[t + 2]
                v0 = (pos[3 * a], pos[3 * a + 1], pos[3 * a + 2])
                v1 = (pos[3 * b], pos[3 * b + 1], pos[3 * b + 2])
                v2 = (pos[3 * c], pos[3 * c + 1], pos[3 * c + 2])
                tris.append((v0, v1, v2, key))
    return tris


# --------------------------------------------------------------------------- #
# Projection + flat Lambert shading
# --------------------------------------------------------------------------- #
def _rotation_rows(azimuth_deg: float, elevation_deg: float) -> tuple[_Vec3, _Vec3, _Vec3]:
    """Rows of R = Rx(elevation) . Ry(azimuth) mapping world -> camera space.

    Camera space: +x right, +y up, +z toward the viewer (a larger z is nearer).
    """
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    ca, sa = math.cos(az), math.sin(az)
    ce, se = math.cos(el), math.sin(el)
    r0: _Vec3 = (ca, 0.0, sa)
    r1: _Vec3 = (se * sa, ce, -se * ca)
    r2: _Vec3 = (-ce * sa, se, ce * ca)
    return r0, r1, r2


def _apply(rows: tuple[_Vec3, _Vec3, _Vec3], v: _Vec3) -> _Vec3:
    r0, r1, r2 = rows
    return (
        r0[0] * v[0] + r0[1] * v[1] + r0[2] * v[2],
        r1[0] * v[0] + r1[1] * v[1] + r1[2] * v[2],
        r2[0] * v[0] + r2[1] * v[1] + r2[2] * v[2],
    )


# (depth, (p0, p1, p2), "#rrggbb", alpha)
_Face = tuple[float, tuple[_Vec2, _Vec2, _Vec2], str, float]


def _project_and_shade(
    tris: list[_Tri],
    rows: tuple[_Vec3, _Vec3, _Vec3],
    *,
    ghost_walls: bool = False,
    wall_alpha: float = 0.22,
    ghost_roof: bool = False,
    roof_alpha: float = 0.45,
) -> list[_Face]:
    faces: list[_Face] = []
    for v0, v1, v2, key in tris:
        c0 = _apply(rows, v0)
        c1 = _apply(rows, v1)
        c2 = _apply(rows, v2)
        # Geometric normal in camera space.
        ux, uy, uz = c1[0] - c0[0], c1[1] - c0[1], c1[2] - c0[2]
        vx, vy, vz = c2[0] - c0[0], c2[1] - c0[1], c2[2] - c0[2]
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        ln = math.sqrt(nx * nx + ny * ny + nz * nz)
        if ln < 1e-12:  # degenerate triangle
            continue
        nx, ny, nz = nx / ln, ny / ln, nz / ln
        if nz < 0.0:  # orient toward the camera (double-sided shading)
            nx, ny, nz = -nx, -ny, -nz
        ndl = nx * _LIGHT[0] + ny * _LIGHT[1] + nz * _LIGHT[2]
        if ndl < 0.0:
            ndl = 0.0
        fill = nx * _FILL[0] + ny * _FILL[1] + nz * _FILL[2]
        if fill < 0.0:
            fill = 0.0
        lambert = _AMBIENT + _DIFFUSE * ndl + _FILL_W * fill
        # Silhouette darkening: faces grazing the camera (small nz) go darker.
        facing = 0.55 + 0.45 * nz
        shade = min(1.15, lambert * facing)
        base = _MATERIAL_RGBA.get(key) or _FALLBACK_RGBA
        k = (key or "").lower()
        # Ghost walls (vertical enclosure + facility massing shells)
        alpha = 1.0
        rgb0, rgb1, rgb2 = float(base[0]), float(base[1]), float(base[2])
        if ghost_walls and (k in _GHOST_WALL_KEYS or k.startswith("wall")):
            alpha = float(wall_alpha)
            if k in _GHOST_NEUTRAL_KEYS:
                rgb0, rgb1, rgb2 = _GHOST_NEUTRAL_RGB
        elif (ghost_walls and ghost_roof) and (
            k in _GHOST_SHELL_KEYS or k.startswith("roof") or k.startswith("slab")
        ):
            alpha = float(roof_alpha)
        color = _hex(rgb0 * shade, rgb1 * shade, rgb2 * shade)
        # base RGBA may already carry window glass alpha
        if len(base) >= 4 and base[3] < 0.99:
            alpha = min(alpha, float(base[3]))
        depth = (c0[2] + c1[2] + c2[2]) / 3.0
        pts = ((c0[0], c0[1]), (c1[0], c1[1]), (c2[0], c2[1]))
        faces.append((depth, pts, color, alpha))
    # Painter's algorithm: far (smaller camera z) first, near last. Stable sort
    # keeps input order on ties, so the result is deterministic.
    faces.sort(key=lambda f: f[0])
    return faces


def _hex(r: float, g: float, b: float) -> str:
    ri = max(0, min(255, int(round(r * 255.0))))
    gi = max(0, min(255, int(round(g * 255.0))))
    bi = max(0, min(255, int(round(b * 255.0))))
    return f"#{ri:02x}{gi:02x}{bi:02x}"


# --------------------------------------------------------------------------- #
# SVG emission
# --------------------------------------------------------------------------- #
def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _emit_svg(faces: list[_Face], name: str, width: int, height: int) -> str:
    pad = round(min(width, height) * 0.05)
    title_h = 44
    footer_h = 34
    avail_w = max(1.0, float(width - 2 * pad))
    avail_h = max(1.0, float(height - 2 * pad - title_h - footer_h))
    top = pad + title_h

    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    for _d, pts, _c in faces:
        for x, y in pts:
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
    if not faces or not math.isfinite(min_x):
        min_x = min_y = 0.0
        max_x = max_y = 1.0

    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    scale = min(avail_w / span_x, avail_h / span_y)
    draw_w = span_x * scale
    draw_h = span_y * scale
    off_x = pad + (avail_w - draw_w) / 2.0
    off_y = top + (avail_h - draw_h) / 2.0

    def to_px(x: float, y: float) -> _Vec2:
        return (off_x + (x - min_x) * scale, off_y + (max_y - y) * scale)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )
    parts.append(
        '<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#eaf2fb"/>'
        '<stop offset="0.55" stop-color="#c7d3e0"/>'
        '<stop offset="1" stop-color="#9aa7b4"/>'
        "</linearGradient>"
        # Residual #14 — soft contact shadow under the building mass
        '<radialGradient id="groundShadow" cx="50%" cy="50%" r="50%">'
        '<stop offset="0%" stop-color="#000" stop-opacity="0.38"/>'
        '<stop offset="55%" stop-color="#000" stop-opacity="0.14"/>'
        '<stop offset="100%" stop-color="#000" stop-opacity="0"/>'
        "</radialGradient></defs>"
    )
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="url(#sky)"/>')

    # Soft elliptical shadow on the ground plane of the massing (painter under faces)
    cx = off_x + draw_w / 2.0
    cy = off_y + draw_h * 0.92
    rx = draw_w * 0.48
    ry = max(12.0, draw_h * 0.08)
    parts.append(
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
        f'fill="url(#groundShadow)"/>'
    )

    parts.append('<g shape-rendering="geometricPrecision">')
    for face in faces:
        # Support legacy 3-tuple faces and new 4-tuple (with alpha)
        if len(face) == 4:
            _d, pts, color, alpha = face  # type: ignore[misc]
        else:
            _d, pts, color = face  # type: ignore[misc]
            alpha = 1.0
        coords = " ".join(f"{px:.1f},{py:.1f}" for px, py in (to_px(x, y) for x, y in pts))
        op = f' fill-opacity="{alpha:.3f}"' if alpha < 0.999 else ""
        parts.append(f'<polygon points="{coords}" fill="{color}"{op}/>')
    parts.append("</g>")

    title = _xml_escape(name)
    footer = _xml_escape(f"{name} — presentation view [NOT FOR CONSTRUCTION]")
    parts.append(
        f'<text x="{pad}" y="{pad + 28}" font-family="Helvetica,Arial,sans-serif" '
        f'font-size="26" font-weight="bold" fill="#1c2530">{title}</text>'
    )
    parts.append(
        f'<text x="{pad}" y="{height - pad}" font-family="Helvetica,Arial,sans-serif" '
        f'font-size="16" fill="#33404e">{footer}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
