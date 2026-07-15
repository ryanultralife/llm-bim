"""Vertical pipe risers: place, takeoff, plan/elev, AABB."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_core.clash import element_aabb
from llmbim_drawings.plan import write_plan_svg
from llmbim_drawings.section import write_elevation_svg


def test_place_riser_length_and_takeoff():
    p = Project.create("riser", vcs=False)
    p.add_level("L1", 0)
    eid = p.place_riser(
        level="L1",
        nps="2",
        origin=(1500, 2000),
        z0_mm=0,
        z1_mm=3000,
        material="copper",
        system="CW",
    )
    el = p.model.get_element(eid)
    assert el.params.get("vertical") is True
    assert abs(float(el.params["length_m"]) - 3.0) < 0.01
    pipes = p.pipe_takeoff(nps="2")
    assert pipes and abs(float(pipes[0]["length_m"]) - 3.0) < 0.01
    box = element_aabb(el, p.model)
    assert box is not None
    assert box.zmax - box.zmin >= 2990


def test_riser_on_plan_and_elev(tmp_path: Path):
    p = Project.create("riser-draw", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(5000, 0), thickness_mm=200, height_mm=3000)
    p.place_riser(level="L1", nps="1", origin=(2500, 1000), z0_mm=200, z1_mm=2800, material="fire")
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    pt = plan.read_text(encoding="utf-8")
    assert 'class="pipes"' in pt
    # riser plan symbol uses filled circle
    assert pt.count("<circle ") >= 2
    elev = tmp_path / "e.svg"
    write_elevation_svg(p.model, "S", elev, scale=0.02)
    et = elev.read_text(encoding="utf-8")
    assert 'class="pipes-elev"' in et
