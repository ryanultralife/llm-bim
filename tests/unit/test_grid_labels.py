"""Plan grid bubble labels A/B/1/2."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.plan import write_plan_svg


def test_grid_bubbles_on_plan(tmp_path: Path):
    p = Project.create("grids", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(20000, 0), thickness_mm=200, height_mm=3000)
    p.create_wall(level="L1", start=(0, 0), end=(0, 15000), thickness_mm=200, height_mm=3000)
    p.add_grid("U", [0, 10000, 20000], labels=["1", "2", "3"])
    p.add_grid("V", [0, 7500, 15000], labels=["A", "B", "C"])
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.01)
    text = plan.read_text(encoding="utf-8")
    assert 'class="grids"' in text
    assert ">A</text>" in text
    assert ">1</text>" in text
    assert ">B</text>" in text
    assert ">3</text>" in text
