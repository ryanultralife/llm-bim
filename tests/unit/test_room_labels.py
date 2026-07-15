"""Room name + area + height labels on plan SVG."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
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
