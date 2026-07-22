"""Baked, deterministic shaded axonometric hero render of a model, as an SVG.

The deliverable pack has no baked hero image, so any presentation still has to
be screenshotted from the WebGL viewer. This module renders one directly: a
shaded axonometric of the whole building, emitted as a self-contained SVG using
only the standard library.

It reuses the exact tessellation the viewer shows by running
:func:`llmbim_geometry.mesh.export_gltf_walls` and reading the triangles back
out of the glTF (positions in metres, glTF Y-up), and it shades each triangle
from the same material palette (:data:`llmbim_geometry.mesh._MATERIAL_RGBA`), so
the still matches the 3D model. The render is deterministic: no RNG and no
wall-clock, so the same model always produces a byte-identical SVG.

Wire into ``export_deliverables`` later (that pipeline is out of scope here).
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

_AMBIENT = 0.36
_DIFFUSE = 0.64


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


# (depth, (p0, p1, p2), "#rrggbb")
_Face = tuple[float, tuple[_Vec2, _Vec2, _Vec2], str]


def _project_and_shade(
    tris: list[_Tri], rows: tuple[_Vec3, _Vec3, _Vec3]
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
        lambert = _AMBIENT + _DIFFUSE * ndl
        # Silhouette darkening: faces grazing the camera (small nz) go darker.
        facing = 0.55 + 0.45 * nz
        shade = lambert * facing
        base = _MATERIAL_RGBA.get(key) or _FALLBACK_RGBA
        color = _hex(base[0] * shade, base[1] * shade, base[2] * shade)
        depth = (c0[2] + c1[2] + c2[2]) / 3.0
        pts = ((c0[0], c0[1]), (c1[0], c1[1]), (c2[0], c2[1]))
        faces.append((depth, pts, color))
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
        "</linearGradient></defs>"
    )
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="url(#sky)"/>')

    parts.append('<g shape-rendering="geometricPrecision">')
    for _d, pts, color in faces:
        coords = " ".join(f"{px:.1f},{py:.1f}" for px, py in (to_px(x, y) for x, y in pts))
        parts.append(f'<polygon points="{coords}" fill="{color}"/>')
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
