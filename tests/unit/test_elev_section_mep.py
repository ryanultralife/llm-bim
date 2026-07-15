"""Elevation/section include pipe markers; clash includes pipe-pipe."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_core.clash import find_clashes
from llmbim_drawings.section import write_elevation_svg, write_section_svg


def test_elevation_draws_pipes(tmp_path: Path) -> None:
    p = Project.create("ElevMEP", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    eid = p.place_pipe(level="L1", nps="1", start=(500, 500), end=(7000, 500), material="copper")
    p.model.get_element(eid).params["z0_mm"] = 2400
    out = tmp_path / "elev_S.svg"
    write_elevation_svg(p.model, "S", out, scale=0.02)
    text = out.read_text(encoding="utf-8")
    assert 'class="pipes-elev"' in text
    assert "<line " in text


def test_section_draws_pipe_circles(tmp_path: Path) -> None:
    p = Project.create("SecMEP", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(0, 5000), thickness_mm=200, height_mm=3000)
    # pipe parallel to cut, near cut line y=1000
    eid = p.place_pipe(level="L1", nps="2", start=(1000, 1000), end=(4000, 1000), material="fire")
    p.model.get_element(eid).params["z0_mm"] = 2000
    out = tmp_path / "sec.svg"
    # cut along X at y≈1000
    write_section_svg(p.model, (0, 1000), (5000, 1000), out, scale=0.02, depth_mm=800)
    text = out.read_text(encoding="utf-8")
    assert 'class="pipes-section"' in text
    assert "<circle " in text


def test_pipe_pipe_clash():
    p = Project.create("ClashPipe", vcs=False)
    p.add_level("L1", 0)
    p.place_pipe(level="L1", nps="2", start=(0, 0), end=(3000, 0), material="copper")
    p.place_pipe(level="L1", nps="2", start=(0, 0), end=(3000, 0), material="copper")
    c = find_clashes(p.model)
    assert any(
        {x["a_category"], x["b_category"]} <= {"pipe", "plumbing_pipe"}
        or "pipe" in (x["a_category"], x["b_category"])
        for x in c
    )
