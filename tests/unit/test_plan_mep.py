"""Plan SVG includes pipe runs and fitting markers."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.plan import write_plan_svg


def test_plan_svg_draws_pipes_and_fittings(tmp_path: Path) -> None:
    p = Project.create("PlanMEP", vcs=False)
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=10000, d=8000, height_mm=3000, thickness_mm=200, name_prefix="B"
    )
    p.place_pipe(level="L1", nps="3/4", start=(1000, 1000), end=(8000, 1000), material="copper")
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(1000, 1000), material="copper")
    p.place_fitting(level="L1", fitting_type="tee", nps="3/4", origin=(4000, 1000), material="copper")
    p.place_part(level="L1", kind="toilet", origin=(5000, 5000))
    out = tmp_path / "plan.svg"
    write_plan_svg(p.model, "L1", out, scale=0.02)
    text = out.read_text(encoding="utf-8")
    assert 'class="pipes"' in text
    assert 'class="fittings"' in text
    assert "3/4" in text or "3/4&quot;" in text or '3/4"' in text
    assert "<line " in text
    assert text.count("<circle ") >= 1 or text.count("<rect ") >= 1
