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


def test_query_phase_filter():
    p = Project.create("q-phase", vcs=False)
    p.add_level("L1", 0)
    w1 = p.create_wall(level="L1", start=(0, 0), end=(3000, 0), thickness_mm=200, height_mm=3000)
    w2 = p.create_wall(level="L1", start=(0, 1000), end=(3000, 1000), thickness_mm=200, height_mm=3000)
    p.set_phase(w2, "existing")
    new_walls = run_query(p.model, "category=wall phase=new")
    ex_walls = run_query(p.model, "category=wall phase=existing")
    assert len(new_walls) == 1 and new_walls[0].id == w1
    assert len(ex_walls) == 1 and ex_walls[0].id == w2


def test_query_section_and_trade_size():
    p = Project.create("q-struct", vcs=False)
    p.add_level("L1", 0)
    p.place_column(level="L1", origin=(0, 0), section="W10x33", height_mm=3500)
    p.place_beam(level="L1", start=(0, 0), end=(5000, 0), section="W12x26")
    p.place_conduit(level="L1", start=(0, 1000), end=(3000, 1000), trade_size="1")
    cols = run_query(p.model, "category=column section=W10x33")
    assert len(cols) == 1
    beams = run_query(p.model, "category=beam section=W12x26")
    assert len(beams) == 1
    cond = run_query(p.model, "category=conduit trade_size=1")
    assert len(cond) == 1


def test_query_fire_rating():
    p = Project.create("q-fr", vcs=False)
    p.add_level("L1", 0)
    w = p.create_wall(
        level="L1",
        start=(0, 0),
        end=(6000, 0),
        thickness_mm=200,
        height_mm=3000,
        fire_rating="2-hr",
    )
    p.place_door(
        host=w,
        offset_mm=1000,
        width_mm=900,
        height_mm=2100,
        fire_rating="90 min",
        type_id="D-HM-36",
    )
    p.place_door(
        host=w,
        offset_mm=3500,
        width_mm=900,
        height_mm=2100,
        fire_rating="20 min",
    )
    fr90 = run_query(p.model, "category=door fire_rating=90_min")
    assert len(fr90) == 1
    fr_any = run_query(p.model, "fire_rating~90")
    assert len(fr_any) >= 1
    walls = run_query(p.model, "category=wall fire_rating~2")
    assert len(walls) == 1


def test_query_row_enrichment_fields_for_agents():
    """Fields agents need on query hits (mirrors MCP project_query row shape)."""
    from llmbim_core.csi import csi_for_element

    p = Project.create("q-enrich", vcs=False)
    p.add_level("L1", 0)
    cid = p.place_column(level="L1", origin=(1000, 1000), section="W10x33", height_mm=3500)
    el = p.model.get_element(cid)
    info = csi_for_element(p.model, el)
    row = {
        "id": el.id,
        "category": el.category,
        "section": el.params.get("section"),
        "csi_code": info.get("csi_code"),
        "locator": info.get("locator"),
        "length_m": el.params.get("length_m"),
        "fire_rating": el.params.get("fire_rating"),
        "phase": el.params.get("phase", "new"),
    }
    assert row["section"] == "W10x33"
    assert row["csi_code"] == "05 12 00"
    assert row["locator"]
    assert abs(float(row["length_m"]) - 3.5) < 0.01
