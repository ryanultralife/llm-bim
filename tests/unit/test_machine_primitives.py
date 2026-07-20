"""Machine-scale primitives from the grok audit (SSOT doc §5.3 A–D).

Covers:
- NPS normalization end-to-end ("1.5" → "1-1/2" through SDK + ops) with
  ValidationError messages that LIST the known catalog labels per material
- place_tube: oriented cylinder along +Z and along a diagonal — glTF node
  exists, oriented bbox sane, indices valid against POSITION counts
- place_wire_path: 20 points → ONE element, one primitive, valid indices,
  per-phase material key present
- frozen kind → glTF material map spot checks
"""

from __future__ import annotations

import base64
import json
import struct
from pathlib import Path

import pytest
from llmbim import Project
from llmbim_core.errors import ValidationError
from llmbim_core.parts_catalog import (
    known_nps_for_material,
    normalize_nps,
    resolve_fitting_part_id,
)
from llmbim_geometry.mesh import EQUIP_KIND_MATERIAL, WIRE_PHASE_MATERIAL

# --- glTF hand-parse helpers (pattern from test_viewer3d_rich.py) -------------


def _export(p: Project, tmp_path: Path) -> dict:
    out = tmp_path / "model.gltf"
    p.export_gltf(out)
    return json.loads(out.read_text(encoding="utf-8"))


def _scene_nodes(data: dict) -> list[dict]:
    return [data["nodes"][i] for i in data["scenes"][data.get("scene", 0)]["nodes"]]


def _node_for(data: dict, element_id: str) -> dict:
    for node in _scene_nodes(data):
        if (node.get("extras") or {}).get("id") == element_id:
            return node
    raise AssertionError(f"no scene node for element {element_id}")


def _blob(data: dict) -> bytes:
    uri = data["buffers"][0]["uri"]
    return base64.b64decode(uri.split(",", 1)[1])


def _assert_indices_valid(data: dict, node: dict) -> None:
    blob = _blob(data)
    mesh = data["meshes"][node["mesh"]]
    assert mesh["primitives"], node
    for prim in mesh["primitives"]:
        pos_acc = data["accessors"][prim["attributes"]["POSITION"]]
        idx_acc = data["accessors"][prim["indices"]]
        bv = data["bufferViews"][idx_acc["bufferView"]]
        size, fmt = (2, "<H") if idx_acc["componentType"] == 5123 else (4, "<I")
        off = bv["byteOffset"] + idx_acc.get("byteOffset", 0)
        vals = [
            struct.unpack_from(fmt, blob, off + k * size)[0]
            for k in range(idx_acc["count"])
        ]
        assert max(vals) < pos_acc["count"], (node["name"], max(vals), pos_acc["count"])
        assert min(vals) >= 0


def _prim_material_names(data: dict, node: dict) -> set[str]:
    mesh = data["meshes"][node["mesh"]]
    return {data["materials"][pr["material"]]["name"] for pr in mesh["primitives"]}


def _node_bbox(data: dict, node: dict) -> tuple[list[float], list[float]]:
    """Union of POSITION accessor min/max over the node's primitives (metres)."""
    mesh = data["meshes"][node["mesh"]]
    mins = [1e9, 1e9, 1e9]
    maxs = [-1e9, -1e9, -1e9]
    for prim in mesh["primitives"]:
        acc = data["accessors"][prim["attributes"]["POSITION"]]
        for k in range(3):
            mins[k] = min(mins[k], acc["min"][k])
            maxs[k] = max(maxs[k], acc["max"][k])
    return mins, maxs


def _project() -> Project:
    p = Project.create("MachinePrims", vcs=False)
    p.add_level("L1", 0)
    return p


# --- §5.3C nps normalization --------------------------------------------------


def test_normalize_nps_spellings() -> None:
    assert normalize_nps("1.5") == "1-1/2"
    assert normalize_nps(1.5) == "1-1/2"
    assert normalize_nps("1.25") == "1-1/4"
    assert normalize_nps("0.75") == "3/4"
    assert normalize_nps(".5") == "1/2"
    assert normalize_nps("2.5") == "2-1/2"
    assert normalize_nps(" 2 ") == "2"
    assert normalize_nps("2.0") == "2"
    assert normalize_nps('1-1/2"') == "1-1/2"
    assert normalize_nps("1 1/2") == "1-1/2"
    # already-canonical labels pass through
    assert normalize_nps("3/4") == "3/4"
    assert normalize_nps("1-1/4") == "1-1/4"


def test_resolve_fitting_part_id_normalizes() -> None:
    assert resolve_fitting_part_id("pipe", "1.5") == "PT-CU-PIPE-1_1_2"
    assert resolve_fitting_part_id("elbow_90", "1.25", material="copper") == "PT-CU-ELB90-1_1_4"


def test_known_nps_for_material_sorted() -> None:
    labels = known_nps_for_material("copper")
    for want in ("1/2", "3/4", "1", "1-1/2", "2", "4"):
        assert want in labels
    # smallest first
    assert labels.index("1/2") < labels.index("2")
    assert known_nps_for_material("pvc")  # non-copper families populated too


def test_place_pipe_decimal_nps_end_to_end() -> None:
    p = _project()
    eid = p.place_pipe(level="L1", nps="1.5", start=(0, 0), end=(2000, 0))
    el = p.model.get_element(eid)
    assert el.params["nps"] == "1-1/2"
    assert el.params["part_id"] == "PT-CU-PIPE-1_1_2"
    # ops path (registry dispatch)
    r = p.op("place_fitting", level="L1", fitting_type="elbow_90", nps="1.25", origin=[500, 500])
    fit = p.model.get_element(r["element_id"])
    assert fit.params["nps"] == "1-1/4"
    assert fit.params["part_id"] == "PT-CU-ELB90-1_1_4"
    # riser too
    rid = p.place_riser(level="L1", nps="0.75", origin=(100, 100), z0_mm=0, z1_mm=2500)
    ris = p.model.get_element(rid)
    assert ris.params["nps"] == "3/4"


def test_unknown_nps_error_lists_known_labels() -> None:
    p = _project()
    with pytest.raises(ValidationError) as ei:
        p.place_pipe(level="L1", nps="7", start=(0, 0), end=(1000, 0))
    msg = str(ei.value.message)
    assert "known NPS" in msg
    assert "1-1/2" in msg and "3/4" in msg
    assert ei.value.details["known_nps"] == known_nps_for_material("copper")
    # fitting path carries the listing too
    with pytest.raises(ValidationError) as ei2:
        p.place_fitting(level="L1", fitting_type="elbow_90", nps="9.99", origin=(0, 0))
    assert "known NPS" in str(ei2.value.message)


# --- §5.3A oriented tube / port -----------------------------------------------


def test_place_tube_along_z(tmp_path: Path) -> None:
    p = _project()
    eid = p.place_tube(
        level="L1",
        origin=(1000, 2000),
        z0_mm=500,
        direction="z",
        length_mm=400,
        od_mm=100,
        kind="kf40_port",
    )
    el = p.model.get_element(eid)
    assert el.category == "equipment"
    assert el.params["shape"] == "cylinder"
    assert el.params["axis_dir"] == [0.0, 0.0, 1.0]
    data = _export(p, tmp_path)
    node = _node_for(data, eid)
    _assert_indices_valid(data, node)
    # oriented bbox: glTF X = plan x, Y = elevation, Z = plan y (metres)
    mins, maxs = _node_bbox(data, node)
    assert mins[0] == pytest.approx(0.95, abs=0.01)
    assert maxs[0] == pytest.approx(1.05, abs=0.01)
    assert mins[1] == pytest.approx(0.5, abs=0.01)  # axis start elevation
    assert maxs[1] == pytest.approx(0.9, abs=0.01)  # + length along +Z
    assert mins[2] == pytest.approx(1.95, abs=0.01)
    assert maxs[2] == pytest.approx(2.05, abs=0.01)
    # KF port kind → stable equip_port material
    assert "equip_port" in _prim_material_names(data, node)


def test_place_tube_along_diagonal(tmp_path: Path) -> None:
    p = _project()
    eid = p.place_tube(
        level="L1",
        origin=(0, 0),
        z0_mm=1000,
        direction=(1, 1, 0),  # normalized internally
        length_mm=1000,
        od_mm=100,
        id_mm=80,  # hollow stub
        kind="port",
    )
    el = p.model.get_element(eid)
    d = el.params["axis_dir"]
    assert d[0] == pytest.approx(0.7071, abs=1e-3)
    assert d[1] == pytest.approx(0.7071, abs=1e-3)
    assert d[2] == 0.0
    data = _export(p, tmp_path)
    node = _node_for(data, eid)
    _assert_indices_valid(data, node)
    mins, maxs = _node_bbox(data, node)
    # plan extents ≈ axis projection (707 mm) + radius fringe; elevation ≈ od
    assert (maxs[0] - mins[0]) == pytest.approx(0.7071 + 0.0707, abs=0.02)
    assert (maxs[2] - mins[2]) == pytest.approx(0.7071 + 0.0707, abs=0.02)
    assert (maxs[1] - mins[1]) == pytest.approx(0.1, abs=0.01)
    # centered on axis elevation 1000 mm
    assert (maxs[1] + mins[1]) / 2 == pytest.approx(1.0, abs=0.01)


def test_place_tube_rejects_zero_direction() -> None:
    p = _project()
    with pytest.raises(ValidationError):
        p.place_tube(level="L1", origin=(0, 0), z0_mm=0, direction=(0, 0, 0), length_mm=100, od_mm=50)
    with pytest.raises(ValidationError):
        p.op("place_tube", level="L1", direction="q", length_mm=100, od_mm=50)


# --- §5.3B 3D wire path -------------------------------------------------------


def test_wire_path_single_element_single_primitive(tmp_path: Path) -> None:
    import math

    p = _project()
    # 20-point helical-ish coil path (the Proto-10 killer shape)
    pts = [
        [
            500 + 200 * math.cos(2 * math.pi * i / 19 * 3),
            500 + 200 * math.sin(2 * math.pi * i / 19 * 3),
            800 + 20 * i,
        ]
        for i in range(20)
    ]
    eid = p.place_wire_path(
        level="L1",
        points_mm=pts,
        diameter_mm=8,
        phase="A",
        system="RMF_A",
        wire_role="coil",
    )
    # ONE element for the whole polyline
    wire_paths = [e for e in p.model.elements if e.category == "wire_path"]
    assert len(wire_paths) == 1
    assert wire_paths[0].id == eid
    assert len(wire_paths[0].params["points_mm"]) == 20
    data = _export(p, tmp_path)
    node = _node_for(data, eid)
    mesh = data["meshes"][node["mesh"]]
    assert len(mesh["primitives"]) == 1  # single tube mesh, no per-segment explosion
    _assert_indices_valid(data, node)
    # per-phase material key present on the primitive and in the legend
    assert _prim_material_names(data, node) == {"wire_phase_a"}
    assert "wire_phase_a" in data["extras"]["material_legend"]
    # phase surfaces in extras for viewer filtering
    assert node["extras"]["params"]["phase"] == "A"


def test_wire_path_validation() -> None:
    p = _project()
    with pytest.raises(ValidationError):
        p.place_wire_path(level="L1", points_mm=[[0, 0, 0]], diameter_mm=6)
    with pytest.raises(ValidationError):
        p.place_wire_path(level="L1", points_mm=[[0, 0], [1, 1]], diameter_mm=6)
    with pytest.raises(ValidationError):
        p.place_wire_path(
            level="L1", points_mm=[[0, 0, 0], [100, 0, 0]], diameter_mm=6, phase="D"
        )


def test_wire_path_role_and_system_material_keys(tmp_path: Path) -> None:
    p = _project()
    hose = p.place_wire_path(
        level="L1",
        points_mm=[[0, 0, 100], [500, 0, 100], [500, 500, 400]],
        diameter_mm=20,
        wire_role="hose",
        system="SIG",
    )
    plain = p.place_wire_path(
        level="L1",
        points_mm=[[0, 1000, 100], [800, 1000, 100]],
        diameter_mm=6,
    )
    b = p.place_wire_path(
        level="L1",
        points_mm=[[0, 2000, 100], [800, 2000, 300]],
        diameter_mm=6,
        system="RMF_B",  # phase from system tag
    )
    data = _export(p, tmp_path)
    assert _prim_material_names(data, _node_for(data, hose)) == {"wire_lead"}
    assert _prim_material_names(data, _node_for(data, plain)) == {"wire"}
    assert _prim_material_names(data, _node_for(data, b)) == {"wire_phase_b"}


# --- §5.3D frozen kind → material map -----------------------------------------


def test_frozen_material_map_spot_checks() -> None:
    # existing keys must stay stable (viewer layer styling contract)
    assert EQUIP_KIND_MATERIAL["shell"] == "equip_shell"
    assert EQUIP_KIND_MATERIAL["yoke"] == "equip_yoke"
    assert EQUIP_KIND_MATERIAL["magnet"] == "equip_magnet"
    assert EQUIP_KIND_MATERIAL["cartridge"] == "equip_cartridge"
    assert EQUIP_KIND_MATERIAL["flange"] == "equip_flange"
    assert EQUIP_KIND_MATERIAL["kf40_port"] == "equip_port"
    assert EQUIP_KIND_MATERIAL["kf25_port"] == "equip_port"
    assert EQUIP_KIND_MATERIAL["port"] == "equip_port"
    # §5.3D additions
    assert EQUIP_KIND_MATERIAL["turbo"] == "equip_vacuum"
    assert EQUIP_KIND_MATERIAL["pump"] == "equip_vacuum"
    assert EQUIP_KIND_MATERIAL["roughing"] == "equip_vacuum"
    assert EQUIP_KIND_MATERIAL["gauge"] == "equip_sensor"
    assert EQUIP_KIND_MATERIAL["rga"] == "equip_sensor"
    assert EQUIP_KIND_MATERIAL["probe"] == "equip_sensor"
    assert EQUIP_KIND_MATERIAL["gas"] == "equip_gas"
    assert EQUIP_KIND_MATERIAL["feed"] == "equip_gas"
    assert EQUIP_KIND_MATERIAL["collection"] == "equip_collection"
    assert EQUIP_KIND_MATERIAL["canister"] == "equip_collection"
    assert EQUIP_KIND_MATERIAL["chiller"] == "equip_chiller"
    assert EQUIP_KIND_MATERIAL["manifold"] == "equip_chiller"
    assert EQUIP_KIND_MATERIAL["controls"] == "equip_controls"
    assert EQUIP_KIND_MATERIAL["terminal"] == "equip_controls"
    assert WIRE_PHASE_MATERIAL == {
        "a": "wire_phase_a",
        "b": "wire_phase_b",
        "c": "wire_phase_c",
    }


def test_material_map_through_gltf(tmp_path: Path) -> None:
    p = _project()
    turbo = p.create_equipment_box(
        level="L1", origin=(0, 0), size=(400, 200, 200), kind="turbo", shape="cylinder"
    )
    shell = p.create_equipment_box(
        level="L1", origin=(2000, 0), size=(500, 320, 320), kind="shell", shape="cylinder"
    )
    chiller = p.create_equipment_box(level="L1", origin=(4000, 0), size=(800, 600, 1200), kind="chiller")
    proc = p.place_pipe(level="L1", nps="2", start=(0, 2000), end=(3000, 2000), material="process", system="PROC")
    cu = p.place_pipe(level="L1", nps="3/4", start=(0, 3000), end=(3000, 3000), material="copper")
    data = _export(p, tmp_path)
    assert _prim_material_names(data, _node_for(data, turbo)) == {"equip_vacuum"}
    assert _prim_material_names(data, _node_for(data, shell)) == {"equip_shell"}
    assert _prim_material_names(data, _node_for(data, chiller)) == {"equip_chiller"}
    assert _prim_material_names(data, _node_for(data, proc)) == {"pipe_process"}
    assert _prim_material_names(data, _node_for(data, cu)) == {"pipe_copper"}


def test_plain_wire_gains_phase_key_when_tagged(tmp_path: Path) -> None:
    """place_wire stays 'wire' by default; a phase param opts into phase colors."""
    p = _project()
    plain = p.place_wire(level="L1", start=(0, 0), end=(1000, 0), diameter_mm=6)
    tagged = p.place_wire(level="L1", start=(0, 500), end=(1000, 500), diameter_mm=6)
    p.op("set_param", id=tagged, key="phase", value="C")
    data = _export(p, tmp_path)
    assert _prim_material_names(data, _node_for(data, plain)) == {"wire"}
    assert _prim_material_names(data, _node_for(data, tagged)) == {"wire_phase_c"}
