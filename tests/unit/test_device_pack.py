"""Device SSOT pack → BIM instantiation (Proto-10 pattern in core)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from llmbim_core.device_pack import DevicePack, build_device, load_device_pack
from llmbim_core.errors import ValidationError
from llmbim_core.model import Element, ProjectModel
from llmbim_core.registry import list_ops

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "device_pack_minimal.json"


def fresh_model() -> ProjectModel:
    m = ProjectModel(name="Device test")
    m.add_level("L1", 0)
    return m


def op_names() -> set[str]:
    return {str(o["name"]) for o in list_ops()}


def element_for(model: ProjectModel, res: dict[str, Any], component_id: str) -> Element:
    ids = res["element_ids"][component_id]
    assert ids, f"no elements created for {component_id}"
    return model.get_element(ids[0])


def test_load_fixture() -> None:
    pack = load_device_pack(FIXTURE)
    assert pack.name == "Proto10 Mini Separator"
    assert pack.units == "mm"
    assert pack.origin_mode == "center"
    assert pack.scale == 1.0
    assert len(pack.components) == 9
    shapes = {c.id: c.shape for c in pack.components}
    assert shapes["shell"] == "tube"
    assert shapes["magnet"] == "box"
    assert shapes["coil_a"] == "wire_path"
    assert shapes["turbo"] == "cylinder"
    assert pack.components[0].cyl_dims() == (400.0, 380.0, 1200.0)


def test_build_counts_and_offsets() -> None:
    pack = load_device_pack(FIXTURE)
    model = fresh_model()
    res = build_device(model, pack, level="L1", origin_mm=(5000, 5000), name_prefix="P10-")
    assert res["ok"], res
    assert not res["skipped"], res["skipped"]
    assert res["honesty"].startswith("device instantiation — engineering estimate")
    # every component produced at least one element
    assert set(res["element_ids"]) == {c.id for c in pack.components}
    assert res["created_total"] >= len(pack.components)

    magnet = element_for(model, res, "magnet")
    assert magnet.category == "equipment"
    assert magnet.name == "P10-Yoke magnet"
    assert magnet.params["origin_mm"] == [4850.0, 4740.0]  # centered 300x520 at (5000,5000)
    assert magnet.params["z0_mm"] == 640.0  # center z 900 - 520/2
    assert magnet.params["size_mm"] == [300.0, 520.0, 520.0]
    assert magnet.params["device_component"] == "magnet"
    assert magnet.params["material_hint"] == "NdFeB"

    pedestal = element_for(model, res, "pedestal")
    assert pedestal.params["origin_mm"] == [4300.0, 4650.0]
    assert pedestal.params["z0_mm"] == 0.0


def test_cylinder_axis_params() -> None:
    pack = load_device_pack(FIXTURE)
    model = fresh_model()
    res = build_device(model, pack, level="L1", origin_mm=(5000, 5000))
    shell = element_for(model, res, "shell")
    assert shell.params["axis"] == "x"
    assert shell.params["od_mm"] == 400.0
    assert shell.params["id_mm"] == 380.0
    assert shell.params["length_mm"] == 1200.0
    turbo = element_for(model, res, "turbo")
    assert turbo.params["axis"] == "z"
    assert turbo.params["od_mm"] == 200.0
    if "place_tube" in op_names():
        # oriented tube op: origin is the axis start point (plan XY + z0_mm)
        assert shell.params["origin_mm"] == [4400.0, 5000.0]  # center x - L/2
        assert shell.params["z0_mm"] == 900.0  # bore axis elevation
        assert shell.params["axis_dir"] == [1.0, 0.0, 0.0]
        assert turbo.params["origin_mm"] == [5700.0, 5000.0]
        assert turbo.params["z0_mm"] == 300.0  # center z 450 - length/2
        assert turbo.params["axis_dir"] == [0.0, 0.0, 1.0]
        assert not any("place_tube" in w for w in res["warnings"])
    else:
        # native +X cylinder path: exact placement is deterministic
        assert shell.params["shape"] == "cylinder"
        assert shell.params["origin_mm"] == [4400.0, 5000.0]  # x0 = cx - L/2, y = centerline
        assert shell.params["z0_mm"] == 700.0  # bore z 900 - od/2
        assert shell.params["size_mm"] == [1200.0, 400.0, 400.0]
        # oriented (z) cylinder falls back to a box envelope + warning
        assert turbo.params["shape"] == "box"
        assert any("turbo" in w and "place_tube" in w for w in res["warnings"])


def test_wire_paths_single_element_or_fallback_warning() -> None:
    pack = load_device_pack(FIXTURE)
    model = fresh_model()
    res = build_device(model, pack, level="L1", origin_mm=(5000, 5000))
    coil_ids = {"coil_a", "coil_b", "coil_c"}
    if "place_wire_path" in op_names():
        for cid in coil_ids:
            assert len(res["element_ids"][cid]) == 1, "wire path must be a single element"
        assert not any("place_wire_path" in w for w in res["warnings"])
    else:
        wire_warnings = [w for w in res["warnings"] if "place_wire_path" in w]
        assert len(wire_warnings) == 3
        coil_a = element_for(model, res, "coil_a")
        assert coil_a.category == "wire_path"
        assert coil_a.params["segments"] == 4
        # points offset by the placement origin
        assert coil_a.params["points_mm"][0] == [4700.0, 5000.0, 1130.0]
    coil_a = element_for(model, res, "coil_a")
    assert coil_a.params["phase"] == "A"
    assert coil_a.params["system"] == "RMF_A"


def snapshot(model: ProjectModel) -> list[tuple[Any, ...]]:
    keys = ("origin_mm", "z0_mm", "size_mm", "points_mm", "axis", "device_component")
    return sorted(
        (el.name, el.category, json.dumps([el.params.get(k) for k in keys]))
        for el in model.elements
    )


def test_determinism_two_builds_identical() -> None:
    pack = load_device_pack(FIXTURE)
    m1, m2 = fresh_model(), fresh_model()
    r1 = build_device(m1, pack, level="L1", origin_mm=(5000, 5000), name_prefix="P10-")
    r2 = build_device(m2, pack, level="L1", origin_mm=(5000, 5000), name_prefix="P10-")
    assert [c["name"] for c in r1["created"]] == [c["name"] for c in r2["created"]]
    assert r1["warnings"] == r2["warnings"]
    assert snapshot(m1) == snapshot(m2)


def test_metres_scaling_like_primitives_importer() -> None:
    pack = DevicePack.model_validate(
        {
            "name": "Metric skid",
            "units": "m",
            "components": [
                {
                    "id": "rack",
                    "shape": "box",
                    "center_mm": [0, 0, 0.9],
                    "size_mm": [1.2, 0.6, 0.5],
                    "kind": "controls",
                }
            ],
        }
    )
    assert pack.scale == 1000.0
    model = fresh_model()
    res = build_device(model, pack, level="L1")
    rack = element_for(model, res, "rack")
    assert rack.params["size_mm"] == [1200.0, 600.0, 500.0]
    assert rack.params["origin_mm"] == [-600.0, -300.0]
    assert rack.params["z0_mm"] == 650.0  # 0.9 m center - 0.25 m half height


def test_min_corner_origin_mode() -> None:
    pack = DevicePack.model_validate(
        {
            "name": "Corner box",
            "origin_mode": "min_corner",
            "components": [
                {"id": "b", "shape": "box", "origin_mm": [100, 200, 300], "size_mm": [400, 600, 800]}
            ],
        }
    )
    model = fresh_model()
    res = build_device(model, pack, level="L1")
    el = element_for(model, res, "b")
    assert el.params["origin_mm"] == [100.0, 200.0]
    assert el.params["z0_mm"] == 300.0


def write_pack(tmp_path: Path, components: list[dict[str, Any]]) -> Path:
    p = tmp_path / "bad_pack.json"
    p.write_text(json.dumps({"name": "Bad", "components": components}), encoding="utf-8")
    return p


def test_bad_pack_unknown_shape_names_component(tmp_path: Path) -> None:
    path = write_pack(
        tmp_path,
        [{"id": "weird_part", "shape": "sphere", "center_mm": [0, 0, 0], "size_mm": [1, 1, 1]}],
    )
    with pytest.raises(ValidationError, match="weird_part"):
        load_device_pack(path)


def test_bad_pack_missing_size_names_component(tmp_path: Path) -> None:
    path = write_pack(tmp_path, [{"id": "no_size_box", "shape": "box", "center_mm": [0, 0, 0]}])
    with pytest.raises(ValidationError, match="no_size_box"):
        load_device_pack(path)


def test_bad_pack_wire_path_needs_points(tmp_path: Path) -> None:
    path = write_pack(tmp_path, [{"id": "lonely_wire", "shape": "wire_path", "phase": "A"}])
    with pytest.raises(ValidationError, match="lonely_wire"):
        load_device_pack(path)


def test_bad_pack_duplicate_component_ids(tmp_path: Path) -> None:
    comp = {"id": "twin", "shape": "box", "center_mm": [0, 0, 0], "size_mm": [1, 1, 1]}
    path = write_pack(tmp_path, [comp, dict(comp)])
    with pytest.raises(ValidationError, match="twin"):
        load_device_pack(path)
