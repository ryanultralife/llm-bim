"""WS4 (+extensions) — the presentation glTF carries triplanar UVs, procedural
PBR detail textures AND tangent-space normal maps, so surfaces read as
concrete/drywall/metal/wood with real relief instead of flat pastels; the trade
materials (pipes/ducts/conduit/tray/equipment) get brushed/painted-metal detail
the same way, and only instrument-faced equipment carries a faint emissive.
Also guards the additive KHR material extensions (transmission glass + declared
``extensionsUsed``), that every embedded PNG decodes, and that the binary
buffer layout stays in-bounds and byte-deterministic."""

from __future__ import annotations

import base64
import json
import struct
import sys
import zlib
from pathlib import Path

from llmbim import Project
from llmbim_geometry import gltf_textures as gt
from llmbim_geometry.mesh import export_gltf_walls

_COMP_SIZE = {5126: 4, 5123: 2, 5125: 4}
_TYPE_N = {"VEC2": 2, "VEC3": 3, "SCALAR": 1}

_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_SCHAD_DIR = Path(__file__).resolve().parents[2] / "projects" / "schad"


def _png_info(raw: bytes) -> tuple[int, int, int]:
    """(width, height, color_type) from a PNG's IHDR, and zlib-decompress the
    IDAT stream so a corrupt image raises. Stdlib only — Pillow is not a repo
    dependency, so tests must not import it (CI installs only .[dev,server])."""
    assert raw[:8] == _PNG_SIG, "not a PNG"
    assert raw[12:16] == b"IHDR", "no IHDR"
    width, height, _bit_depth, color_type = struct.unpack(">IIBB", raw[16:26])
    idat = b""
    pos = 8
    while pos < len(raw):
        length = struct.unpack(">I", raw[pos : pos + 4])[0]
        ctype = raw[pos + 4 : pos + 8]
        if ctype == b"IDAT":
            idat += raw[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"IEND":
            break
    zlib.decompress(idat)  # raises zlib.error on a corrupt pixel stream
    return width, height, color_type


def _bounds_violations(g: dict) -> int:
    """Count accessor/bufferView reads that fall outside their container:
    byteOffset + count*compSize*typeN must fit the bufferView, and each
    bufferView must fit the buffer."""
    buf_len = g["buffers"][0]["byteLength"]
    bvs = g["bufferViews"]
    viol = 0
    for a in g["accessors"]:
        bv = bvs[a["bufferView"]]
        elem = _COMP_SIZE[a["componentType"]] * _TYPE_N[a["type"]]
        if a.get("byteOffset", 0) + a["count"] * elem > bv["byteLength"]:
            viol += 1
        if bv.get("byteOffset", 0) + bv["byteLength"] > buf_len:
            viol += 1
    return viol


def _decode_embedded_pngs(g: dict) -> int:
    """PIL-verify every embedded image data URI; return how many decoded."""
    n = 0
    for img in g.get("images", []):
        uri = img["uri"]
        assert uri.startswith("data:image/png;base64,"), uri[:32]
        raw = base64.b64decode(uri.split(",", 1)[1])
        _png_info(raw)  # raises on a corrupt PNG (signature + IHDR + IDAT)
        n += 1
    return n


def _synthetic_gltf(tmp_path: Path) -> dict:
    """A tiny wall + slab + window model, exported and parsed back."""
    p = Project.create("Tex", vcs=False)
    p.add_level("L1", 0)
    wid = p.create_wall(
        level="L1", start=(0, 0), end=(6000, 0), thickness_mm=200, height_mm=3000
    )
    p.create_slab(
        level="L1", polygon=[(0, 0), (6000, 0), (6000, 4000), (0, 4000)], thickness_mm=200
    )
    p.place_window(host=wid, offset_mm=2000, width_mm=1200, height_mm=1200, sill_mm=900)
    out = tmp_path / "t.gltf"
    export_gltf_walls(p.model, out)
    return json.loads(out.read_text(encoding="utf-8"))


def test_texture_and_normal_pngs_valid_and_deterministic() -> None:
    for pat in ("concrete", "drywall", "metal", "wood", "brushed_metal", "painted_metal"):
        base = gt.texture_png(pat)
        norm = gt.normal_png(pat)
        assert base[:8] == _PNG_SIG, pat
        assert norm[:8] == _PNG_SIG, pat
        assert gt.texture_png(pat) == base, f"{pat} base not deterministic"
        assert gt.normal_png(pat) == norm, f"{pat} normal not deterministic"
        # normal maps are RGB (PNG colour type 2); a flat normal encodes to
        # ~(128,128,255) so the blue channel dominates and relief stays subtle.
        assert _png_info(norm)[2] == 2, pat


def test_build_gltf_textures_maps_base_and_normal_for_architectural_keys() -> None:
    imgs, texs, samps, k2t, k2n = gt.build_gltf_textures(
        ["wall", "slab", "roof", "window", "pipe_copper", "duct", "pipe_pvc", "equipment"]
    )
    # base + normal per distinct pattern -> images and textures match, even count
    assert len(imgs) == len(texs) >= 2
    assert len(imgs) % 2 == 0
    assert len(samps) == 1
    for key in ("wall", "slab", "roof", "pipe_copper", "duct", "pipe_pvc", "equipment"):
        assert key in k2t and key in k2n
        # base and normal textures are distinct entries sharing the one sampler
        assert k2t[key] != k2n[key]
        assert texs[k2t[key]]["sampler"] == texs[k2n[key]]["sampler"] == 0
    # trade runs share the brushed pattern; PVC/equipment the smooth painted one
    assert k2t["pipe_copper"] == k2t["duct"]
    assert k2t["pipe_pvc"] == k2t["equipment"]
    assert k2t["pipe_copper"] != k2t["pipe_pvc"]
    # glass keeps its factor colour (transmission look) — no detail/normal texture
    assert "window" not in k2t and "window" not in k2n


def test_pattern_map_excludes_glass_and_tiny_geometry() -> None:
    # window stays glass, wire/coil/bolt texels are too small to read, and the
    # generic fallback stays flat.
    for key in ("window", "wire", "wire_steel", "wire_phase_a", "coil", "bolt", "default"):
        assert key not in gt._PATTERN_FOR, key


def test_synthetic_gltf_uvs_normal_extensions_and_bounds(tmp_path: Path) -> None:
    g = _synthetic_gltf(tmp_path)

    assert g.get("images") and g.get("textures") and g.get("samplers")
    prims = [pr for m in g["meshes"] for pr in m["primitives"]]
    assert prims, "no primitives"
    assert all("TEXCOORD_0" in pr["attributes"] for pr in prims), "missing UVs"

    mats = {m["name"]: m for m in g["materials"]}
    # architectural mats carry a normalTexture reusing the same TEXCOORD_0 UVs
    for key in ("wall", "slab"):
        nt = mats[key].get("normalTexture")
        assert nt and "index" in nt, key
        assert nt.get("scale") == 0.5, key

    # additive, backward-compatible extensions on the glass material
    win = mats["window"]
    assert win["alphaMode"] == "BLEND"  # legacy viewers still render glass
    assert float(win["pbrMetallicRoughness"]["baseColorFactor"][3]) < 1.0
    win_ext = win.get("extensions", {})
    assert "KHR_materials_transmission" in win_ext
    assert win_ext["KHR_materials_transmission"]["transmissionFactor"] > 0.5
    assert win_ext["KHR_materials_ior"]["ior"] == 1.5

    # extensionsUsed lists exactly the extensions actually emitted
    used = g.get("extensionsUsed")
    assert used, "extensionsUsed missing"
    assert "KHR_materials_transmission" in used and "KHR_materials_ior" in used
    emitted = set()
    for m in g["materials"]:
        emitted.update(m.get("extensions", {}))
    assert set(used) == emitted
    # KHR_lights_punctual must NOT be declared (would double-light in-app viewer)
    assert "KHR_lights_punctual" not in used

    assert _bounds_violations(g) == 0
    assert _decode_embedded_pngs(g) == len(g["images"]) >= 4


def test_trade_materials_textured_and_honest_emissive(tmp_path: Path) -> None:
    """Residuals #12 + #11: a model with real MEP runs + equipment exports trade
    materials with baseColorTexture AND normalTexture while keeping each key's
    palette hue, and ONLY the instrument-faced equipment kinds emit — at low
    strength, with KHR_materials_emissive_strength declared exactly when used."""
    from llmbim_geometry.mesh import _MATERIAL_PBR

    p = Project.create("Trades", vcs=False)
    p.add_level("L1", 0)
    p.place_pipe(level="L1", nps="3/4", start=(0, 0), end=(4000, 0), material="copper")
    p.place_pipe(level="L1", nps="2", start=(0, 500), end=(4000, 500), material="pvc")
    p.place_duct(level="L1", start=(0, 1000), end=(4000, 1000))
    p.place_conduit(level="L1", start=(0, 1500), end=(4000, 1500))
    p.place_cable_tray(level="L1", start=(0, 2000), end=(4000, 2000))
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(4000, 0))
    p.create_equipment_box(level="L1", origin=(500, 3000), size=(800, 600, 1200))
    p.create_equipment_box(
        level="L1", origin=(2000, 3000), size=(200, 200, 300), kind="sensor"
    )
    p.create_equipment_box(
        level="L1", origin=(3000, 3000), size=(600, 600, 1800), kind="controls"
    )
    out = tmp_path / "trades.gltf"
    export_gltf_walls(p.model, out)
    # determinism: trade textures + emissive stay byte-stable
    out2 = tmp_path / "trades2.gltf"
    export_gltf_walls(p.model, out2)
    assert out.read_bytes() == out2.read_bytes()

    g = json.loads(out.read_text(encoding="utf-8"))
    mats = {m["name"]: m for m in g["materials"]}
    trade = ("pipe_copper", "pipe_pvc", "duct", "conduit", "cable_tray", "fitting",
             "equipment", "equip_sensor", "equip_controls")
    for key in trade:
        assert key in mats, key
        pbr = mats[key]["pbrMetallicRoughness"]
        assert "baseColorTexture" in pbr, key
        assert "normalTexture" in mats[key], key
        assert mats[key]["normalTexture"]["scale"] == 0.5, key
        # the texture is multiplicative detail — the palette hue is untouched
        assert pbr["baseColorFactor"] == list(_MATERIAL_PBR[key][0]), key

    # honest emissive: instrument faces glow faintly; passive surfaces do not
    for key in ("equip_sensor", "equip_controls"):
        factor = mats[key].get("emissiveFactor")
        assert factor is not None, key
        assert 0.0 < max(factor) <= 0.2, key  # faint hue-matched tint only
        ext = mats[key].get("extensions", {})
        strength = ext["KHR_materials_emissive_strength"]["emissiveStrength"]
        assert 1.0 < strength <= 2.0, key  # a dim indicator, not a light source
    for key in ("pipe_copper", "pipe_pvc", "duct", "conduit", "cable_tray",
                "fitting", "equipment"):
        assert "emissiveFactor" not in mats[key], key
        assert "KHR_materials_emissive_strength" not in mats[key].get("extensions", {}), key

    # extensionsUsed == exactly what the materials emit; still no punctual lights
    used = set(g.get("extensionsUsed", []))
    assert "KHR_materials_emissive_strength" in used
    emitted: set[str] = set()
    for m in g["materials"]:
        emitted.update(m.get("extensions", {}))
    assert used == emitted
    assert "KHR_lights_punctual" not in used

    assert _bounds_violations(g) == 0
    assert _decode_embedded_pngs(g) == len(g["images"])


def test_gltf_export_is_byte_deterministic(tmp_path: Path) -> None:
    p = Project.create("Det", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(6000, 0), thickness_mm=200, height_mm=3000)
    a = tmp_path / "a.gltf"
    b = tmp_path / "b.gltf"
    export_gltf_walls(p.model, a)
    export_gltf_walls(p.model, b)
    assert a.read_bytes() == b.read_bytes(), "glTF export not deterministic"


def test_schad_model_gltf_textures_normals_and_bounds(tmp_path: Path) -> None:
    """Realistic model: schad build_model() must export a valid textured glTF
    with normal maps on every architectural material and zero buffer-bounds
    violations across its many primitives."""
    if str(_SCHAD_DIR) not in sys.path:
        sys.path.insert(0, str(_SCHAD_DIR))
    import build_llmbim  # type: ignore[import-not-found]

    model = build_llmbim.build_model().model
    out = tmp_path / "schad.gltf"
    export_gltf_walls(model, out)
    # determinism on the realistic model too
    out2 = tmp_path / "schad2.gltf"
    export_gltf_walls(model, out2)
    assert out.read_bytes() == out2.read_bytes()

    g = json.loads(out.read_text(encoding="utf-8"))
    prims = [pr for m in g["meshes"] for pr in m["primitives"]]
    assert prims
    assert all("TEXCOORD_0" in pr["attributes"] for pr in prims)

    mats = {m["name"]: m for m in g["materials"]}
    arch = [
        k
        for k in ("wall", "wall_structure", "wall_finish", "slab", "concrete", "roof", "door")
        if k in mats
    ]
    assert arch, "no architectural materials in schad model"
    for key in arch:
        assert "normalTexture" in mats[key], key
        assert mats[key]["normalTexture"]["scale"] == 0.5

    assert g.get("extensionsUsed"), "extensionsUsed missing on schad model"
    assert _bounds_violations(g) == 0
    assert _decode_embedded_pngs(g) == len(g["images"])
