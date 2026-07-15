"""Plan dimensions include wall and MEP run lengths."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.plan import write_plan_svg


def test_plan_dimensions_walls_and_pipes(tmp_path: Path):
    p = Project.create("dims", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    p.place_pipe(
        level="L1",
        nps="2",
        start=(500, 2000),
        end=(6500, 2000),
        material="copper",
    )
    p.place_duct(
        level="L1",
        start=(500, 4000),
        end=(5500, 4000),
        width_mm=400,
        height_mm=250,
    )
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    text = plan.read_text(encoding="utf-8")
    assert 'class="dimensions"' in text
    # wall 8m and/or pipe 6m labels
    assert " m" in text or "mm" in text
    # MEP prefix markers for pipe nps and duct
    assert '2"' in text or "P " in text or "D " in text or "6.00 m" in text or "5.00 m" in text
