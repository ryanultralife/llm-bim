"""Plan shows wall type marks (e.g. EXT-CMU)."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.plan import write_plan_svg


def test_wall_type_on_plan(tmp_path: Path):
    p = Project.create("wall-types", vcs=False)
    p.add_level("L1", 0)
    wid = p.create_wall(
        level="L1",
        start=(0, 0),
        end=(8000, 0),
        thickness_mm=200,
        height_mm=3000,
        type_id="W-EXT-CMU",
    )
    assert wid
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    text = plan.read_text(encoding="utf-8")
    assert 'class="wall-types"' in text
    assert "EXT-CMU" in text
