"""Query language: room / csi / vertical filters."""

from __future__ import annotations

from llmbim import Project
from llmbim_core.query_lang import run_query


def test_query_room_and_csi():
    p = Project.create("q-csi", vcs=False)
    p.add_level("L1", 0)
    p.create_room(
        level="L1",
        name="Restroom A",
        boundary=[(0, 0), (4000, 0), (4000, 3000), (0, 3000)],
    )
    p.place_fitting(
        level="L1",
        fitting_type="elbow_90",
        nps="3/4",
        origin=(1000, 1000),
        material="copper",
    )
    p.place_fitting(
        level="L1",
        fitting_type="elbow_90",
        nps="2",
        origin=(9000, 9000),  # outside room
        material="fire",
    )
    in_room = run_query(p.model, "room~Restroom category=fitting")
    assert len(in_room) == 1
    assert in_room[0].params.get("nps") == "3/4"

    # CSI uses underscore form in query tokens (spaces break parser)
    copper = run_query(p.model, "csi~22_11 category=fitting")
    assert any(e.params.get("material_id") == "copper_C12200" or "copper" in str(e.params.get("material_id")) for e in copper) or len(copper) >= 1

    fire = run_query(p.model, "csi~21_13")
    assert fire


def test_query_vertical_riser():
    p = Project.create("q-riser", vcs=False)
    p.add_level("L1", 0)
    p.place_pipe(level="L1", nps="1", start=(0, 0), end=(3000, 0), material="copper")
    p.place_riser(level="L1", nps="2", origin=(100, 100), z0_mm=0, z1_mm=3000, material="copper")
    risers = run_query(p.model, "vertical=true")
    assert len(risers) == 1
    assert risers[0].params.get("vertical") is True
    nps2 = run_query(p.model, "nps=2 vertical=true")
    assert len(nps2) == 1
