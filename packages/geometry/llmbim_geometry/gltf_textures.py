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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Return (images, textures, samplers, key->texture_index) for the material
    keys present. One image+texture per distinct pattern actually used; a single
    REPEAT sampler. Materials with no pattern are absent from the returned map."""
    patterns: list[str] = []
    for key in mat_keys:
        pat = _PATTERN_FOR.get(key)
        if pat and pat not in patterns:
            patterns.append(pat)
    if not patterns:
        return [], [], [], {}
    samplers = [{"wrapS": 10497, "wrapT": 10497, "magFilter": 9729, "minFilter": 9987}]
    images: list[dict[str, Any]] = []
    textures: list[dict[str, Any]] = []
    pat_to_tex: dict[str, int] = {}
    for pat in patterns:
        img_i = len(images)
        images.append({"name": f"{pat}_detail", "uri": texture_data_uri(pat)})
        pat_to_tex[pat] = len(textures)
        textures.append({"name": f"{pat}_tex", "source": img_i, "sampler": 0})
    key_to_tex = {
        key: pat_to_tex[_PATTERN_FOR[key]] for key in mat_keys if key in _PATTERN_FOR
    }
    return images, textures, samplers, key_to_tex
