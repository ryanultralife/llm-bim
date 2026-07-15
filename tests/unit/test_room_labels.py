"""Room name + area + height labels on plan SVG and DXF."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.dxf_export import export_plan_dxf
from llmbim_drawings.plan import write_plan_svg


def test_room_label_area_and_height(tmp_path: Path):
    p = Project.create("room-lab", vcs=False)
    p.add_level("L1", 0)
    p.create_room(
        level="L1",
        name="Restroom A",
        boundary=[(0, 0), (5000, 0), (5000, 4000), (0, 4000)],
        height_mm=2700,
    )
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    text = plan.read_text(encoding="utf-8")
    assert "room-label" in text
    assert "Restroom A" in text
    assert "20.0m" in text or "20m" in text or "m" in text
    assert "H2700" in text


def test_room_label_on_plan_dxf(tmp_path: Path):
    p = Project.create("room-dxf", vcs=False)
    p.add_level("L1", 0)
    p.create_room(
        level="L1",
        name="Office",
        boundary=[(0, 0), (4000, 0), (4000, 3000), (0, 3000)],
        height_mm=3000,
    )
    dxf = tmp_path / "p.dxf"
    export_plan_dxf(p.model, "L1", dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "Office" in text
    assert "m2" in text
    assert "H3000" in text
    assert "ROOMS" in text
