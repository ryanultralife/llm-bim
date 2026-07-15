"""MEP design rules: pipe in wall, fire material, missing NPS, connections."""

from __future__ import annotations

from llmbim import Project
from llmbim_core.rules import run_design_rules


def test_pipe_in_wall_rule():
    p = Project.create("mep-rules", vcs=False)
    p.add_level("L1", 0)
    # wall along X at y=0
    p.create_wall(level="L1", start=(0, 0), end=(5000, 0), thickness_mm=200, height_mm=3000)
    # pipe along same wall line (intersects)
    p.place_pipe(level="L1", nps="3/4", start=(500, 0), end=(4000, 0), material="copper")
    findings = run_design_rules(p.model)
    rules = {f["rule"] for f in findings}
    assert "PIPE_IN_WALL" in rules


def test_fire_pipe_copper_error():
    p = Project.create("fire-bad", vcs=False)
    p.add_level("L1", 0)
    # force copper material on fire system path
    eid = p.place_pipe(
        level="L1", nps="2", start=(0, 1000), end=(3000, 1000), material="copper", system="FP"
    )
    # place_pipe with material copper sets copper_C12200; system FP
    el = p.model.get_element(eid)
    el.params["system"] = "FP"
    el.params["material_id"] = "copper_C12200"
    findings = run_design_rules(p.model)
    assert any(f["rule"] == "FIRE_PIPE_MATERIAL" and f["severity"] == "error" for f in findings)


def test_fitting_missing_nps():
    p = Project.create("fit-nps", vcs=False)
    p.add_level("L1", 0)
    eid = p.place_fitting(level="L1", fitting_type="elbow_90", nps="1/2", origin=(0, 0))
    el = p.model.get_element(eid)
    el.params.pop("nps", None)
    findings = run_design_rules(p.model)
    assert any(f["rule"] == "FITTING_MISSING_NPS" for f in findings)


def test_broken_connection():
    p = Project.create("conn", vcs=False)
    p.add_level("L1", 0)
    a = p.create_equipment_box(level="L1", origin=(0, 0), size=(500, 500, 500), name="A")
    p.define_port(a, "OUT", role="process")
    p.model.meta["connections"] = [
        {
            "id": "con_x",
            "from_id": a,
            "from_port": "OUT",
            "to_id": "missing_element",
            "to_port": "IN",
            "medium": "process",
        }
    ]
    findings = run_design_rules(p.model)
    assert any(f["rule"] == "BROKEN_CONNECTION" for f in findings)


def test_structure_column_in_wall_and_beam_low():
    p = Project.create("struct-rules", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3500)
    # column centered on wall → COLUMN_IN_WALL
    p.place_column(level="L1", origin=(4000, 0), section="W10x33", height_mm=3500)
    # low beam → BEAM_LOW_CLEARANCE
    p.place_beam(level="L1", start=(0, 2000), end=(6000, 2000), section="W12x26", z0_mm=1800)
    findings = run_design_rules(p.model)
    rules = {f["rule"] for f in findings}
    assert "COLUMN_IN_WALL" in rules
    assert "BEAM_LOW_CLEARANCE" in rules


def test_duct_in_wall_and_low_clearance():
    p = Project.create("duct-rules", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(6000, 0), thickness_mm=200, height_mm=3000)
    # duct along wall centerline → DUCT_IN_WALL
    p.place_duct(
        level="L1",
        start=(500, 0),
        end=(5000, 0),
        width_mm=400,
        height_mm=300,
        z0_mm=1500,  # low headroom → DUCT_LOW_CLEARANCE
    )
    # conduit across wall
    p.place_conduit(level="L1", start=(0, -500), end=(0, 500), trade_size="1")
    findings = run_design_rules(p.model)
    rules = {f["rule"] for f in findings}
    assert "DUCT_IN_WALL" in rules
    assert "DUCT_LOW_CLEARANCE" in rules
    assert "CONDUIT_IN_WALL" in rules
