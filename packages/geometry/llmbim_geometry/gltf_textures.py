"""Procedural tiling PBR detail textures for the glTF export (pure stdlib).

The presentation glTF shipped flat solid colours (baseColorFactor only), so
concrete / drywall / metal / wood read as indistinguishable pastels. This module
generates small, deterministic, seamlessly-tiling grayscale *detail* textures
(embedded as PNG data URIs) that multiply the existing palette colour — so the
material hues are preserved but surfaces gain real grain/relief in any glTF
viewer (the in-app viewer and Blender / model-viewer / Windows 3D Viewer).

Pure standard-library (struct/zlib/base64) — no PIL/numpy — so the kernel stays
pip-free. Deterministic (hash noise, no RNG) so golden glTF stays byte-stable.
"""

from __future__ import annotations

import base64
import math
import struct
import zlib
from collections.abc import Callable
from typing import Any

_TILE = 64  # texture is _TILE x _TILE, tiled by REPEAT sampler


def _hash01(x: int, y: int, seed: int) -> float:
    """Deterministic pseudo-random in [0, 1) from integer coords (no RNG)."""
    v = (x * 374761393 + y * 668265263 + seed * 2654435761) & 0xFFFFFFFF
    v ^= v >> 13
    v = (v * 1274126177) & 0xFFFFFFFF
    v ^= v >> 16
    return (v & 0xFFFF) / 65535.0


def _value_noise(x: float, y: float, seed: int) -> float:
    """Bilinearly-interpolated value noise on the integer lattice (tiles at _TILE)."""
    x0, y0 = math.floor(x), math.floor(y)
    fx, fy = x - x0, y - y0
    # wrap the lattice so the tile is seamless
    x0w, y0w = x0 % _TILE, y0 % _TILE
    x1w, y1w = (x0 + 1) % _TILE, (y0 + 1) % _TILE
    n00 = _hash01(x0w, y0w, seed)
    n10 = _hash01(x1w, y0w, seed)
    n01 = _hash01(x0w, y1w, seed)
    n11 = _hash01(x1w, y1w, seed)
    sx = fx * fx * (3 - 2 * fx)
    sy = fy * fy * (3 - 2 * fy)
    return (n00 * (1 - sx) + n10 * sx) * (1 - sy) + (n01 * (1 - sx) + n11 * sx) * sy


def _clampb(v: float) -> int:
    return max(0, min(255, int(round(v))))


def _pattern_pixel(pattern: str, x: int, y: int) -> tuple[int, int, int]:
    """Grayscale-ish detail value (0..255 RGB) for a pattern at (x, y). Bright
    average (~0.9) so multiplying the palette colour tints only subtly."""
    if pattern == "concrete":
        base = 232.0
        low = _value_noise(x / 8.0, y / 8.0, 11) - 0.5
        speck = _hash01(x, y, 12)
        val = base + low * 34.0 - (10.0 if speck > 0.93 else 0.0)
        g = _clampb(val)
        return g, g, g
    if pattern == "drywall":
        base = 244.0
        n = _value_noise(x / 12.0, y / 12.0, 21) - 0.5
        val = base + n * 12.0
        g = _clampb(val)
        return g, g, g
    if pattern == "metal":
        # brushed: horizontal streaks (per-row bias) + fine per-pixel jitter
        row = _hash01(0, y, 31)
        streak = math.sin(y * 0.9) * 4.0
        jit = (_hash01(x, y, 32) - 0.5) * 8.0
        val = 236.0 + (row - 0.5) * 10.0 + streak + jit
        g = _clampb(val)
        return g, g, g
    if pattern == "wood":
        # horizontal grain bands + warm tint
        band = math.sin((y + _value_noise(x / 20.0, y / 6.0, 41) * 6.0) * 0.7)
        val = 222.0 + band * 16.0
        r = _clampb(val + 6.0)
        g = _clampb(val - 2.0)
        b = _clampb(val - 12.0)
        return r, g, b
    g = 240
    return g, g, g


def _png_rgb(
    width: int, height: int, pixel: Callable[[int, int], tuple[int, int, int]]
) -> bytes:
    """Encode an 8-bit RGB PNG (filter 0 per scanline). ``pixel(x, y)->(r,g,b)``."""
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter type 0 (None)
        for x in range(width):
            r, g, b = pixel(x, y)
            rows.append(r)
            rows.append(g)
            rows.append(b)

    def _chunk(typ: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + typ
            + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit, colour type 2 (RGB)
    idat = zlib.compress(bytes(rows), 9)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def texture_png(pattern: str) -> bytes:
    """Deterministic tiling PNG bytes for a named pattern."""
    return _png_rgb(_TILE, _TILE, lambda x, y: _pattern_pixel(pattern, x, y))


def texture_data_uri(pattern: str) -> str:
    return "data:image/png;base64," + base64.b64encode(texture_png(pattern)).decode("ascii")


# --- Tangent-space normal maps -------------------------------------------------
# A companion normal map per pattern gives the surfaces subtle relief without a
# TANGENT accessor: three.js (and glTF viewers generally) derive tangents from
# the shared TEXCOORD_0 UVs, so the same detail UVs drive both base colour and
# bump. Encoding is the standard tangent-space convention: a flat normal is
# (0,0,1) -> RGB (128,128,255); a perturbed normal tilts R/G away from 128.
#
# Per-pattern bump strength — kept small so the relief reads as texture, not
# geometry (nz stays close to 1.0, RGB blue channel near 255).
_NORMAL_STRENGTH: dict[str, float] = {
    "concrete": 1.5,
    "drywall": 0.8,
    "metal": 1.2,
    "wood": 1.6,
}


def _pattern_height(pattern: str, x: int, y: int) -> float:
    """Scalar surface height (~0..1) whose gradient yields the normal map. Mirrors
    the relief cues of ``_pattern_pixel`` so bump lines up with the base colour."""
    if pattern == "concrete":
        h = _value_noise(x / 8.0, y / 8.0, 11)
        if _hash01(x, y, 12) > 0.93:
            h -= 0.4  # aggregate pits sit lower
        return h
    if pattern == "drywall":
        return _value_noise(x / 12.0, y / 12.0, 21)
    if pattern == "metal":
        # brushed: shallow horizontal streaks along the rows + fine jitter
        return 0.5 + math.sin(y * 0.9) * 0.15 + (_hash01(x, y, 32) - 0.5) * 0.1
    if pattern == "wood":
        band = math.sin((y + _value_noise(x / 20.0, y / 6.0, 41) * 6.0) * 0.7)
        return 0.5 + band * 0.5
    return 0.5


def _normal_pixel(pattern: str, x: int, y: int, strength: float) -> tuple[int, int, int]:
    """Encode a tangent-space normal (0..255 RGB) from the wrapped height gradient.
    Neighbours wrap on ``_TILE`` so the normal map tiles seamlessly like the base."""
    h_l = _pattern_height(pattern, (x - 1) % _TILE, y)
    h_r = _pattern_height(pattern, (x + 1) % _TILE, y)
    h_d = _pattern_height(pattern, x, (y - 1) % _TILE)
    h_u = _pattern_height(pattern, x, (y + 1) % _TILE)
    dx = (h_l - h_r) * strength
    dy = (h_d - h_u) * strength
    inv = 1.0 / math.sqrt(dx * dx + dy * dy + 1.0)
    nx, ny, nz = dx * inv, dy * inv, inv
    return (
        _clampb((nx * 0.5 + 0.5) * 255.0),
        _clampb((ny * 0.5 + 0.5) * 255.0),
        _clampb((nz * 0.5 + 0.5) * 255.0),
    )


def normal_png(pattern: str) -> bytes:
    """Deterministic tiling tangent-space normal-map PNG bytes for a pattern."""
    strength = _NORMAL_STRENGTH.get(pattern, 1.0)
    return _png_rgb(_TILE, _TILE, lambda x, y: _normal_pixel(pattern, x, y, strength))


def normal_data_uri(pattern: str) -> str:
    return "data:image/png;base64," + base64.b64encode(normal_png(pattern)).decode("ascii")


# Material key (from _MATERIAL_PBR) → detail pattern. Only surfaces that read as
# flat pastels get a detail texture; metals/glass/equipment keep their factor.
_PATTERN_FOR: dict[str, str] = {
    "wall": "drywall",
    "wall_structure": "drywall",
    "wall_finish": "drywall",
    "wall_insulation": "drywall",
    "wall_membrane": "drywall",
    "slab": "concrete",
    "concrete": "concrete",
    "roof": "metal",
    "column": "metal",
    "beam": "metal",
    "door": "wood",
}


def build_gltf_textures(
    mat_keys: list[str],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, int],
    dict[str, int],
]:
    """Return (images, textures, samplers, key->baseColor_tex, key->normal_tex) for
    the material keys present. Each distinct pattern actually used contributes one
    base-colour detail image+texture AND one tangent-space normal image+texture,
    all sharing a single REPEAT sampler and the same TEXCOORD_0 UVs. Materials
    with no pattern are absent from both returned maps."""
    patterns: list[str] = []
    for key in mat_keys:
        pat = _PATTERN_FOR.get(key)
        if pat and pat not in patterns:
            patterns.append(pat)
    if not patterns:
        return [], [], [], {}, {}
    samplers = [{"wrapS": 10497, "wrapT": 10497, "magFilter": 9729, "minFilter": 9987}]
    images: list[dict[str, Any]] = []
    textures: list[dict[str, Any]] = []
    pat_to_tex: dict[str, int] = {}
    pat_to_norm: dict[str, int] = {}
    for pat in patterns:
        base_img = len(images)
        images.append({"name": f"{pat}_detail", "uri": texture_data_uri(pat)})
        pat_to_tex[pat] = len(textures)
        textures.append({"name": f"{pat}_tex", "source": base_img, "sampler": 0})
        norm_img = len(images)
        images.append({"name": f"{pat}_normal", "uri": normal_data_uri(pat)})
        pat_to_norm[pat] = len(textures)
        textures.append({"name": f"{pat}_normal_tex", "source": norm_img, "sampler": 0})
    key_to_tex = {
        key: pat_to_tex[_PATTERN_FOR[key]] for key in mat_keys if key in _PATTERN_FOR
    }
    key_to_norm = {
        key: pat_to_norm[_PATTERN_FOR[key]] for key in mat_keys if key in _PATTERN_FOR
    }
    return images, textures, samplers, key_to_tex, key_to_norm
