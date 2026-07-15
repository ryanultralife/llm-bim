"""Deliverables pack: IFC, STEP, construction, parts."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project


def _mini_facility() -> Project:
    p = Project.create("Mini Facility")
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=10000, d=8000, height_mm=3000, thickness_mm=200, name_prefix="B"
    )
    p.create_slab(
        level="L1",
        polygon=[(0, 0), (10000, 0), (10000, 8000), (0, 8000)],
        thickness_mm=200,
    )
    p.create_room(
        level="L1",
        name="Hall",
        boundary=[(0, 0), (10000, 0), (10000, 8000), (0, 8000)],
    )
    p.create_equipment_box(
        level="L1",
        origin=(4000, 3000),
        size=(2000, 1000, 1500),
        name="Skid-1",
        kind="skid",
        centered=True,
    )
    return p


def test_deliverables_pack(tmp_path: Path) -> None:
    p = _mini_facility()
    m = p.export_deliverables(tmp_path / "pack", plan_scale=0.05)
    assert (tmp_path / "pack" / "model.llmbim.json").is_file()
    assert (tmp_path / "pack" / "model.ifc").is_file()
    assert (tmp_path / "pack" / "model.gltf").is_file()
    assert (tmp_path / "pack" / "model.step").is_file()
    ifc = (tmp_path / "pack" / "model.ifc").read_text(encoding="utf-8")
    assert "IFCPROJECT" in ifc
    assert "IFCWALL" in ifc or "IFCWALLSTANDARDCASE" in ifc
    step = (tmp_path / "pack" / "model.step").read_text(encoding="utf-8")
    assert "ISO-10303-21" in step
    assert "MANIFOLD_SOLID_BREP" in step
    assert (tmp_path / "pack" / "construction" / "SHEET_INDEX.json").is_file()
    assert (tmp_path / "pack" / "construction" / "A-101_plan.svg").is_file()
    assert (tmp_path / "pack" / "parts" / "PARTS_INDEX.json").is_file()
    assert m["project"] == "Mini Facility"


def test_part_step_files(tmp_path: Path) -> None:
    p = Project.create("PartOnly")
    p.add_level("Bench", 0)
    p.create_equipment_box(
        level="Bench",
        origin=(0, 0),
        size=(500, 320, 320),
        name="Shell",
        kind="shell",
        centered=True,
    )
    p.export_part_pack(tmp_path / "parts", scale=0.5)
    steps = list((tmp_path / "parts" / "step").glob("*.step"))
    assert len(steps) >= 1
    assert "MANIFOLD_SOLID_BREP" in steps[0].read_text(encoding="utf-8")
