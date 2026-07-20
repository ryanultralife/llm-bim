"""Engineering-dataset (primitive list) import: steel, doors, utilities, generic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmbim_core.io_import import auto_import
from llmbim_core.model import ProjectModel
from llmbim_core.primitives_import import import_primitives, looks_like_primitives
from llmbim_core.registry import dispatch


def _base_model() -> ProjectModel:
    """Model with L1 and one 10 m wall along X (doors host onto it)."""
    m = ProjectModel(name="prims")
    m.add_level("L1", 0)
    dispatch(
        m,
        "create_wall",
        {
            "level": "L1",
            "start": [0, 0],
            "end": [10000, 0],
            "thickness_mm": 300,
            "height_mm": 4000,
        },
    )
    return m


def _dataset() -> dict[str, Any]:
    return {
        "units": "m",
        "steel": [
            {
                "prim": "box",
                "x": -0.18,
                "y": -0.18,
                "z": 0,
                "w": 0.36,
                "d": 0.36,
                "h": 12.0,
                "name": "col_0_0",
                "sys": "STEEL",
                "attrs": {"member": "column", "section": "W14x90"},
            },
            {
                "prim": "box",
                "x": 7.82,
                "y": -0.18,
                "z": 0,
                "w": 0.36,
                "d": 0.36,
                "h": 12.0,
                "name": "col_8_0",
                "sys": "STEEL",
                "attrs": {"member": "column", "section": "W14x90"},
            },
            {
                "prim": "box",
                "x": 0,
                "y": 6.9,
                "z": 11.24,
                "w": 48.0,
                "d": 0.2,
                "h": 0.46,
                "name": "beam_x_7",
                "sys": "STEEL",
                "attrs": {"member": "roof_beam", "section": "W18x50"},
            },
        ],
        "doors": [
            {
                "prim": "box",
                "x": 4.0,
                "y": -0.075,
                "z": 0.05,
                "w": 2.0,
                "d": 0.15,
                "h": 3.5,
                "name": "shield_door_1",
                "sys": "DOOR",
                "attrs": {"door_type": "shield-transfer", "room": "UNCASK", "face": "N"},
            }
        ],
        "utilities": [
            {
                "prim": "pipe",
                "x": 5.0,
                "y": 24.0,
                "z": 10.5,
                "axis": "x",
                "len": 42.8,
                "r": 0.05,
                "name": "CWS_trunk",
                "sys": "UTIL",
                "attrs": {"service": "CWS", "medium": "water", "size_mm": 100, "line": "CWS-hdr"},
            },
            {
                "prim": "pipe",
                "x": 5.0,
                "y": 24.0,
                "z": 0.0,
                "axis": "z",
                "len": 10.5,
                "r": 0.05,
                "name": "CWS_riser",
                "sys": "UTIL",
                "attrs": {"service": "CWS", "medium": "water", "size_mm": 100, "line": "CWS-00"},
            },
            {
                "prim": "pipe",
                "x": 1.0,
                "y": 30.0,
                "z": 10.5,
                "axis": "y",
                "len": 6.0,
                "r": 0.1,
                "name": "FW_main",
                "sys": "UTIL",
                "attrs": {"service": "FW", "medium": "water", "size_mm": 200, "line": "FW-01"},
            },
            {
                "prim": "box",
                "x": 2.0,
                "y": 20.0,
                "z": 10.0,
                "w": 4.0,
                "d": 0.6,
                "h": 0.4,
                "name": "HVS_duct",
                "sys": "UTIL",
                "attrs": {"service": "HVS", "medium": "air"},
            },
            {
                "prim": "box",
                "x": 2.0,
                "y": 21.0,
                "z": 10.0,
                "w": 0.45,
                "d": 6.0,
                "h": 0.1,
                "name": "PWR_tray",
                "sys": "UTIL",
                "attrs": {"service": "PWR", "medium": "power"},
            },
            {
                "prim": "pipe",
                "x": 3.0,
                "y": 22.0,
                "z": 0.0,
                "axis": "z",
                "len": 9.0,
                "r": 0.3,
                "name": "HVE_riser",
                "sys": "UTIL",
                "attrs": {"service": "HVE", "medium": "air", "size_mm": 600},
            },
        ],
        "oddments": [
            {
                "prim": "box",
                "x": 1.0,
                "y": 1.0,
                "z": 0.5,
                "w": 2.0,
                "d": 1.0,
                "h": 0.8,
                "name": "mystery_block",
                "sys": "ODD",
                "attrs": {"foo": "bar"},
            }
        ],
    }


def _by_name(m: ProjectModel, name: str) -> Any:
    for el in m.elements:
        if el.name == name:
            return el
    raise AssertionError(f"element {name!r} not created")


def test_import_counts_and_categories() -> None:
    m = _base_model()
    res = import_primitives(m, _dataset())
    assert res["ok"] is True
    c = res["created"]
    assert c["columns"] == 2
    assert c["beams"] == 1
    assert c["doors"] == 1
    assert c["pipes"] == 2  # CWS trunk + 8" FW main
    assert c["risers"] == 1
    assert c["ducts"] == 1
    assert c["trays"] == 1
    assert c["riser_boxes"] == 1  # vertical HVAC exhaust → coordination box
    assert c["generic"] == 1
    assert res["created_total"] == sum(c.values())
    assert res["skipped"] == []


def test_mm_scaling_and_steel() -> None:
    m = _base_model()
    import_primitives(m, _dataset())
    col = _by_name(m, "col_0_0")
    assert col.category == "column"
    ox, oy = col.params["origin_mm"]
    assert abs(ox - 0.0) < 1e-6 and abs(oy - 0.0) < 1e-6  # centre of the m-space box
    assert abs(float(col.params["height_mm"]) - 12000.0) < 1e-6
    assert col.params["section"] == "W14x90"
    beam = _by_name(m, "beam_x_7")
    assert beam.category == "beam"
    assert beam.params["start_mm"] == [0.0, 7000.0]  # long-axis run at mid short axis
    assert beam.params["end_mm"] == [48000.0, 7000.0]
    assert abs(float(beam.params["z0_mm"]) - 11240.0) < 1e-6


def test_door_hosted_and_typed() -> None:
    m = _base_model()
    import_primitives(m, _dataset())
    door = _by_name(m, "shield_door_1")
    assert door.category == "door"
    host = m.get_element(door.host_id)
    assert host.category == "wall"
    assert door.type_id == "D-SHIELD-PLUG"  # door_type "shield-transfer" heuristic
    assert abs(float(door.params["width_mm"]) - 2000.0) < 1e-6
    # centre 5.0 m → offset 5000 − width/2 = 4000 mm along the host wall
    assert abs(float(door.params["offset_mm"]) - 4000.0) < 1e-6


def test_pipe_riser_and_material_fallback() -> None:
    m = _base_model()
    res = import_primitives(m, _dataset())
    trunk = _by_name(m, "CWS_trunk")
    assert trunk.category == "pipe"
    assert trunk.params["nps"] == "4"  # 100 mm → 4" (copper carries it)
    assert str(trunk.type_id).startswith("PT-CU")
    assert abs(float(trunk.params["length_mm"]) - 42800.0) < 1e-6
    riser = _by_name(m, "CWS_riser")
    assert riser.params["vertical"] is True
    assert abs(float(riser.params["z0_mm"]) - 0.0) < 1e-6
    assert abs(float(riser.params["z1_mm"]) - 10500.0) < 1e-6
    # 8" line: copper catalog tops out at 4" → falls back to a catalog that has 8"
    fw = _by_name(m, "FW_main")
    assert fw.params["nps"] == "8"
    assert str(fw.type_id).startswith("PT-FP")
    assert any("8" in w for w in res["warnings"])


def test_duct_tray_and_vertical_coordination_box() -> None:
    m = _base_model()
    import_primitives(m, _dataset())
    duct = _by_name(m, "HVS_duct")
    assert duct.category == "duct"
    assert duct.params["start_mm"] == [2000.0, 20300.0]  # along long axis, mid short axis
    assert duct.params["end_mm"] == [6000.0, 20300.0]
    tray = _by_name(m, "PWR_tray")
    assert tray.category == "cable_tray"
    assert tray.params["start_mm"] == [2225.0, 21000.0]
    assert tray.params["end_mm"] == [2225.0, 27000.0]
    box = _by_name(m, "HVE_riser")
    assert box.category == "equipment"
    assert box.params["kind"] == "hve_riser"
    assert abs(float(box.params["size_mm"][2]) - 9000.0) < 1e-6  # vertical extent
    assert abs(float(box.params["z0_mm"]) - 0.0) < 1e-6


def test_unknown_prim_becomes_generic_with_attrs() -> None:
    m = _base_model()
    import_primitives(m, _dataset())
    odd = _by_name(m, "mystery_block")
    assert odd.category == "generic"
    assert odd.params["attrs"] == {"foo": "bar"}
    assert odd.params["source"] == "primitives"
    assert odd.params["origin_mm"] == [1000.0, 1000.0]
    assert odd.params["size_mm"] == [2000.0, 1000.0, 800.0]
    assert abs(float(odd.params["z0_mm"]) - 500.0) < 1e-6


def test_mapping_override_changes_material() -> None:
    m = _base_model()
    mapping = {"services": {"CWS": {"kind": "pipe", "material": "process", "system": "CWS"}}}
    import_primitives(m, _dataset(), mapping=mapping)
    trunk = _by_name(m, "CWS_trunk")
    assert str(trunk.type_id).startswith("PT-SS")  # SS316 process instead of copper
    assert trunk.params["system"] == "CWS"


def test_bare_list_and_never_fatal() -> None:
    m = _base_model()
    res = import_primitives(
        m,
        [
            {"prim": "pipe", "x": 0, "y": 0, "axis": "x", "len": 3.0, "r": 0.025, "name": "p1"},
            {"prim": "pipe", "x": 0, "y": 0, "axis": "z", "len": 0.0, "r": 0.025, "name": "bad"},
            "not-a-dict",
        ],
    )
    assert res["created"]["pipes"] == 1
    assert len(res["skipped"]) == 1  # zero-length riser rejected, import continues
    assert res["skipped"][0]["name"] == "bad"


def test_auto_import_routes_primitives_json(tmp_path: Path) -> None:
    data = _dataset()
    path = tmp_path / "site_params.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    m = _base_model()
    res = auto_import(m, path)
    assert res.get("ok") is True
    assert res["created"]["columns"] == 2
    assert looks_like_primitives(data) is True
    # existing behaviors untouched: ops batch JSON still routes to the batch importer
    ops_path = tmp_path / "ops.json"
    ops_path.write_text(json.dumps([{"op": "add_level", "name": "L2", "elevation": 3500}]))
    res2 = auto_import(m, ops_path)
    assert res2["applied"] == 1
    assert any(lv.name == "L2" for lv in m.levels)
    assert looks_like_primitives({"ops": []}) is False
