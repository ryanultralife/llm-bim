"""WALL_EXCEEDS_STORY uses the plate that covers the wall XY, not the next name."""
from __future__ import annotations

from llmbim import Project
from llmbim_core.rules import run_design_rules


def _partial_mezz():
    p = Project.create("cover", vcs=False)
    p.add_level("B1", -4000)
    p.add_level("L1", 0)
    p.add_level("L2", 4200)
    p.add_level("Roof", 12000)
    p.create_room(
        level="L1", name="Hall",
        boundary=[(0, 0), (10000, 0), (10000, 8000), (0, 8000)],
        height_mm=9000,
    )
    p.create_room(
        level="L2", name="East mezz",
        boundary=[(6000, 0), (10000, 0), (10000, 8000), (6000, 8000)],
        height_mm=3500,
    )
    return p


def test_hall_wall_west_of_mezz_spans_to_roof():
    p = _partial_mezz()
    wid = p.create_wall(
        level="L1", start=(1000, 0), end=(2000, 0),
        thickness_mm=200, height_mm=9000,
    )
    err = [f for f in run_design_rules(p.model) if f["rule"] == "WALL_EXCEEDS_STORY"]
    assert not any(f["element_id"] == wid for f in err), err


def test_hall_wall_under_mezz_exceeds_mezz_plate():
    p = _partial_mezz()
    wid = p.create_wall(
        level="L1", start=(7000, 0), end=(8000, 0),
        thickness_mm=200, height_mm=9000,
    )
    err = [f for f in run_design_rules(p.model) if f["rule"] == "WALL_EXCEEDS_STORY"]
    assert any(f["element_id"] == wid for f in err), err
    assert "L2" in (err[0]["message"] if err else "")


def test_b1_nine_metre_stub_still_errors_against_grade():
    p = _partial_mezz()
    p.create_room(
        level="B1", name="Cave",
        boundary=[(6000, 0), (8000, 0), (8000, 4000), (6000, 4000)],
        height_mm=3000,
    )
    wid = p.create_wall(
        level="B1", start=(6500, 0), end=(7250, 0),
        thickness_mm=200, height_mm=9000,
    )
    err = [f for f in run_design_rules(p.model) if f["rule"] == "WALL_EXCEEDS_STORY"]
    assert any(f["element_id"] == wid for f in err)
