"""WS4 (excellence audit) — the presentation glTF carries triplanar UVs and
procedural PBR detail textures, so surfaces read as concrete/drywall/metal/wood
instead of flat pastels. Guards the binary buffer layout too (bounds valid)."""

from __future__ import annotations

import json
from pathlib import Path

from llmbim import Project
from llmbim_geometry import gltf_textures as gt
from llmbim_geometry.mesh import export_gltf_walls

_COMP_SIZE = {5126: 4, 5123: 2, 5125: 4}
_TYPE_N = {"VEC2": 2, "VEC3": 3, "SCALAR": 1}


def test_texture_pngs_valid_and_deterministic() -> None:
    for pat in ("concrete", "drywall", "metal", "wood"):
        png = gt.texture_png(pat)
        assert png[:8] == b"\x89PNG\r\n\x1a\n", pat  # PNG signature
        assert gt.texture_png(pat) == png, f"{pat} not deterministic"


def test_build_gltf_textures_maps_only_architectural_keys() -> None:
    imgs, texs, samps, k2t = gt.build_gltf_textures(
        ["wall", "slab", "roof", "window", "pipe_copper"]
    )
    assert len(imgs) == len(texs) >= 1
    assert len(samps) == 1
    assert "wall" in k2t and "slab" in k2t and "roof" in k2t
    # glass and copper keep their factor colour — no detail texture
    assert "window" not in k2t and "pipe_copper" not in k2t


def test_gltf_has_uvs_textures_and_valid_buffer(tmp_path: Path) -> None:
    p = Project.create("Tex", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(6000, 0), thickness_mm=200, height_mm=3000)
    p.create_slab(
        level="L1", polygon=[(0, 0), (6000, 0), (6000, 4000), (0, 4000)], thickness_mm=200
    )
    out = tmp_path / "t.gltf"
    export_gltf_walls(p.model, out)
    g = json.loads(out.read_text(encoding="utf-8"))

    assert g.get("images") and g.get("textures") and g.get("samplers")
    prims = [pr for m in g["meshes"] for pr in m["primitives"]]
    assert prims, "no primitives"
    assert all("TEXCOORD_0" in pr["attributes"] for pr in prims), "missing UVs"

    # every accessor stays within its bufferView, every bufferView within the buffer
    buf_len = g["buffers"][0]["byteLength"]
    bvs = g["bufferViews"]
    for a in g["accessors"]:
        bv = bvs[a["bufferView"]]
        elem = _COMP_SIZE[a["componentType"]] * _TYPE_N[a["type"]]
        assert a.get("byteOffset", 0) + a["count"] * elem <= bv["byteLength"]
        assert bv.get("byteOffset", 0) + bv["byteLength"] <= buf_len
