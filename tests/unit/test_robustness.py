"""Robustness: cascade delete, cylinders, verify pack."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.deliverables import verify_pack


def test_cascade_delete_door() -> None:
    p = Project.create()
    p.add_level("L1", 0)
    w = p.create_wall(level="L1", start=(0, 0), end=(5000, 0), thickness_mm=200, height_mm=3000)
    p.place_door(host=w, offset_mm=1000, width_mm=900, height_mm=2100)
    assert p.stats().get("door") == 1
    p.delete_element(w)  # cascade default
    assert p.stats().get("wall", 0) == 0
    assert p.stats().get("door", 0) == 0
    p.undo()
    assert p.stats().get("wall") == 1
    assert p.stats().get("door") == 1


def test_cylinder_equipment_and_pack(tmp_path: Path) -> None:
    p = Project.create("Cyl")
    p.add_level("B", 0)
    p.create_equipment_box(
        level="B",
        origin=(0, 0),
        size=(500, 320, 320),
        name="Shell",
        shape="cylinder",
        kind="shell",
        centered=True,
    )
    el = p.query(category="equipment")[0]
    assert el.params["shape"] == "cylinder"
    m = p.export_deliverables(tmp_path / "pack", mode="part", plan_scale=0.5)
    assert m.get("ok") is True or (tmp_path / "pack" / "model.step").is_file()
    v = verify_pack(tmp_path / "pack", require_parts=True, require_materials=True)
    assert v["ok"] is True
    assert v["part_steps"] >= 1
    assert v.get("has_materials_package") is True
    assert (tmp_path / "pack" / "materials" / "MATERIALS_AND_PARTS.json").is_file()


def test_verify_pack_requires_materials(tmp_path: Path) -> None:
    """Vision: full pack includes materials takeoff; flag fails without it."""
    pack = tmp_path / "emptyish"
    pack.mkdir()
    for name in ("model.llmbim.json", "model.ifc", "model.gltf", "model.step"):
        # minimal content to pass size/probe soft checks where applicable
        if name.endswith(".ifc"):
            (pack / name).write_text("ISO-10303-21;\nDATA;\n#1=IFCPROJECT('x');\nENDSEC;\n", encoding="utf-8")
        elif name.endswith(".step"):
            (pack / name).write_text("ISO-10303-21;\nDATA;\n#1=MANIFOLD_SOLID_BREP('x',$);\nENDSEC;\n", encoding="utf-8")
        else:
            (pack / name).write_text('{"ok": true, "pad": "' + ("x" * 40) + '"}\n', encoding="utf-8")
    soft = verify_pack(pack)
    assert soft.get("has_materials_package") is False
    hard = verify_pack(pack, require_materials=True)
    assert hard["ok"] is False
    assert "materials/MATERIALS_AND_PARTS.json" in hard["missing"]
