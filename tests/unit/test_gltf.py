"""glTF export smoke."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project


def test_gltf_export(tmp_path: Path) -> None:
    p = Project.create("G")
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(4000, 0), thickness_mm=200, height_mm=3000)
    out = tmp_path / "m.gltf"
    p.export_gltf(out)
    text = out.read_text(encoding="utf-8")
    assert "meshes" in text
    assert out.stat().st_size > 100


def test_gltf_includes_pipe_and_fitting(tmp_path: Path) -> None:
    """MEP markers must appear in 3D review mesh (vision multi-trade pack)."""
    p = Project.create("MEP-G", vcs=False)
    p.add_level("L1", 0)
    p.place_pipe(level="L1", nps="3/4", start=(0, 0), end=(5000, 0), material="copper")
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(0, 0), material="copper")
    p.place_part(level="L1", kind="toilet", origin=(2000, 1000))
    out = tmp_path / "mep.gltf"
    p.export_gltf(out)
    # more vertices than a single tiny fallback triangle
    import json

    data = json.loads(out.read_text(encoding="utf-8"))
    n_verts = data["accessors"][0]["count"]
    assert n_verts >= 24  # at least 3 boxes × 8 corners


def test_gltf_doors_and_windows(tmp_path: Path) -> None:
    """Hosted openings appear as door/window materials on host wall geometry."""
    import json

    p = Project.create("G-open", vcs=False)
    p.add_level("L1", 0)
    wid = p.create_wall(
        level="L1", start=(0, 0), end=(10000, 0), thickness_mm=200, height_mm=3000
    )
    p.place_door(
        host=wid, offset_mm=2000, width_mm=900, height_mm=2100, type_id="D-HM-36"
    )
    p.place_window(
        host=wid, offset_mm=5000, width_mm=1200, height_mm=900, sill_mm=900, type_id="WIN"
    )
    out = tmp_path / "open.gltf"
    p.export_gltf(out)
    data = json.loads(out.read_text(encoding="utf-8"))
    names = {m.get("name") for m in (data.get("materials") or [])}
    assert "door" in names
    assert "window" in names
    assert "wall" in names
    # wall + door + window → at least 3*8 verts
    assert data["accessors"][0]["count"] >= 24


def test_viewer3d_html_written(tmp_path: Path) -> None:
    """Pack 3D review page embeds glTF + three look-and-feel step-changes."""
    from llmbim_drawings.viewer3d import write_viewer_3d

    p = Project.create("G-view", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(5000, 0), thickness_mm=200, height_mm=3000)
    p.place_pipe(level="L1", nps="1", start=(0, 500), end=(4000, 500), material="copper")
    pack = tmp_path / "pack"
    pack.mkdir()
    p.export_gltf(pack / "model.gltf")
    path = write_viewer_3d(pack)
    assert path is not None and path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "OrbitControls" in text
    assert "ghostWalls" in text
    assert "GLTFLoader" in text
    assert "pipe_copper" in text or "wall" in text  # embedded glTF layers
    # Step 1 — interactive section cut
    assert "localClippingEnabled" in text
    assert "clipOn" in text
    assert "clipAxis" in text
    # Step 2 — cinematic bloom / ACES
    assert "UnrealBloomPass" in text
    assert "ACESFilmicToneMapping" in text
    # Step 3 — Imagine studio sky + concrete floor (data-URI or toggle)
    assert "studioSky" in text
    assert "floor_concrete" in text or "data:image/jpeg;base64," in text
    # also via SDK helper
    path2 = p.export_viewer_3d(tmp_path / "pack2")
    assert path2 is not None and path2.is_file()


def test_gltf_system_material_colors(tmp_path: Path) -> None:
    """Copper / fire / duct / conduit get distinct glTF materials (coordination colors)."""
    import json

    p = Project.create("G-color", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    p.place_pipe(level="L1", nps="2", start=(0, 1000), end=(5000, 1000), material="copper")
    p.place_pipe(level="L1", nps="2", start=(0, 2000), end=(5000, 2000), material="fire")
    p.place_duct(level="L1", start=(0, 3000), end=(5000, 3000), width_mm=400, height_mm=250)
    p.place_conduit(level="L1", start=(0, 4000), end=(5000, 4000), trade_size="1")
    out = tmp_path / "colors.gltf"
    p.export_gltf(out)
    data = json.loads(out.read_text(encoding="utf-8"))
    mats = data.get("materials") or []
    names = {m.get("name") for m in mats}
    assert "pipe_copper" in names
    assert "pipe_fire" in names
    assert "duct" in names
    assert "conduit" in names
    assert "wall" in names
    # one mesh/node per layer (for 3D viewer layer toggles)
    assert len(data.get("meshes") or []) >= 4
    node_names = {n.get("name") for n in (data.get("nodes") or [])}
    assert "wall" in node_names
    assert "duct" in node_names or "pipe_copper" in node_names
    for m in data["meshes"]:
        assert m.get("primitives") and "material" in m["primitives"][0]
    legend = (data.get("extras") or {}).get("material_legend") or {}
    assert "duct" in legend
    assert (data.get("extras") or {}).get("layer_names")
    # Walls/pipes opaque so solids occlude; only glass blends
    by_name = {m["name"]: m for m in mats}
    assert by_name["wall"].get("alphaMode", "OPAQUE") == "OPAQUE"
    assert by_name["pipe_copper"].get("alphaMode", "OPAQUE") == "OPAQUE"
    assert by_name["pipe_copper"]["pbrMetallicRoughness"]["metallicFactor"] > 0.5
    # Round pipe: ≥32 side segments → well above old 14-facet boxes
    pipe_mesh = next(m for m in data["meshes"] if m.get("name") == "pipe_copper")
    pos_acc = data["accessors"][pipe_mesh["primitives"][0]["attributes"]["POSITION"]]
    assert pos_acc["count"] >= 64  # 32 rings × 2 + caps


def test_gltf_detail_wire_coil_bolt_flange(tmp_path: Path) -> None:
    """Wires, coils, bolts, joined flanges render as distinct glTF layers."""
    import json

    p = Project.create("G-detail", vcs=False)
    p.add_level("L1", 0)
    p.place_wire(level="L1", start=(0, 0), end=(3000, 0), diameter_mm=8, z0_mm=2500)
    p.place_coil(level="L1", origin=(1500, 1500), coil_radius_mm=60, turns=4, z0_mm=500)
    p.place_bolt(level="L1", origin=(500, 500), shank_d_mm=16, shank_len_mm=50, z0_mm=100)
    p.place_flange(level="L1", origin=(2000, 0), od_mm=120, thickness_mm=16, z0_mm=800)
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="1", origin=(100, 100), material="copper")
    p.place_fitting(level="L1", fitting_type="tee", nps="1", origin=(400, 100), material="copper")
    out = tmp_path / "detail.gltf"
    p.export_gltf(out)
    data = json.loads(out.read_text(encoding="utf-8"))
    names = {m.get("name") for m in (data.get("materials") or [])}
    assert "wire" in names
    assert "coil" in names
    assert "bolt" in names
    assert "flange" in names or "fitting" in names
    # fitting elbows must produce multi-solid geometry (not empty)
    node_names = {n.get("name") for n in (data.get("nodes") or [])}
    assert "wire" in node_names
    assert "coil" in node_names
    assert "bolt" in node_names
    for key in ("wire", "coil", "bolt"):
        mesh = next(m for m in data["meshes"] if m.get("name") == key)
        pos_acc = data["accessors"][mesh["primitives"][0]["attributes"]["POSITION"]]
        assert pos_acc["count"] >= 12

