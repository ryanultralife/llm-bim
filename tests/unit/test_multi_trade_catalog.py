"""Multi-trade catalogs: fire, process, steel, rebar, fixtures, CSI."""

from __future__ import annotations

from llmbim import Project
from llmbim_core.csi import CSI_DIVISIONS, CSI_SECTIONS
from llmbim_core.parts_catalog import (
    PARTS,
    catalog_summary,
    get_part,
    list_parts,
    resolve_fitting_part_id,
    resolve_part_id,
)


def test_catalog_covers_trades():
    s = catalog_summary()
    assert s["parts_count"] >= 250
    cats = s["by_category"]
    for need in (
        "plumbing",
        "fire_protection",
        "process_piping",
        "structural_steel",
        "rebar",
        "framing",
        "fixture",
        "accessory",
    ):
        assert need in cats, need
        assert cats[need] >= 1


def test_resolve_cross_trade():
    assert resolve_fitting_part_id("elbow_90", "2", material="fire") == "PT-FP-ELB90-2"
    assert resolve_fitting_part_id("pipe", "4", material="fire") == "PT-FP-PIPE-4"
    assert resolve_fitting_part_id("elbow_90", "2", material="process") == "PT-SS-ELB90-2"
    assert resolve_fitting_part_id("elbow_90", "1/2", material="copper") == "PT-CU-ELB90-1_2"
    assert resolve_part_id(section="W10x33") in PARTS
    assert resolve_part_id(bar_size="5") == "PT-RBR-BAR-5"
    assert resolve_part_id(kind="toilet") == "PT-PLB-WC-FLOOR"
    assert resolve_part_id(kind="tp_dispenser") == "PT-ACC-TP-DOUBLE"
    assert resolve_part_id(kind="toilet_hose") == "PT-PLB-HOSE-WC-BRAID"
    assert get_part("PT-ACC-TP-SINGLE").csi_code.startswith("10 28")


def test_csi_sections_present():
    assert "21" in CSI_DIVISIONS
    assert "03 20 00" in CSI_SECTIONS
    assert "22 40 00" in CSI_SECTIONS
    assert "10 28 13" in CSI_SECTIONS
    assert "05 12 00" in CSI_SECTIONS


def test_fire_and_fixture_takeoff():
    p = Project.create("mt", vcs=False)
    p.add_level("L1", 0)
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="2", origin=(0, 0), material="fire")
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="2", origin=(100, 0), material="fire")
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="4", origin=(200, 0), material="fire")
    p.place_part(level="L1", part_id="PT-FP-HEAD-PENDENT_5_6_155F", origin=(0, 0))
    p.place_part(level="L1", part_id="PT-FP-HEAD-PENDENT_5_6_155F", origin=(100, 0))
    p.place_part(level="L1", kind="toilet", origin=(500, 500))
    p.place_part(level="L1", kind="tp_dispenser", origin=(500, 600))
    p.place_part(level="L1", kind="toilet_hose", origin=(500, 550))

    fire90 = p.fitting_takeoff(fitting_type="elbow_90", system="fire")
    by = {r["nps"]: r["qty"] for r in fire90}
    assert by.get("2") == 2
    assert by.get("4") == 1

    ft = p.fire_takeoff()
    heads = ft["sprinkler_heads"]
    assert sum(r["qty"] for r in heads) == 2

    fixtures = p.system_takeoff("fixture")
    ids = {r["part_id"] for r in fixtures}
    assert "PT-PLB-WC-FLOOR" in ids
    assert "PT-ACC-TP-DOUBLE" in ids

    csi = p.csi_takeoff()
    codes = {r["csi_code"] for r in csi}
    assert any(c.startswith("21") for c in codes)
    assert any(c.startswith("22") or c.startswith("10") for c in codes)


def test_steel_rebar_place():
    p = Project.create("st", vcs=False)
    p.add_level("L1", 0)
    p.place_part(level="L1", section="W12x50", length_m=4.0)
    p.place_part(level="L1", bar_size="5", length_m=50.0)
    steel = p.steel_takeoff()
    assert any("W12" in str(r.get("part_name")) for r in steel)
    rebar = p.rebar_takeoff()
    assert any(r.get("bar_size") == "5" or "#5" in str(r.get("part_name")) for r in rebar)


def test_list_parts_filters():
    fire_elb = list_parts(system="fire", fitting_type="elbow_90")
    assert len(fire_elb) >= 5
    toilets = list_parts(fitting_type="toilet")
    assert len(toilets) >= 2
    wwf = list_parts(category="rebar", fitting_type="wwf")
    assert len(wwf) >= 1


def test_boq_linear_steel_and_rebar_units():
    """Vision: quantities derive from model with correct units (m not ea for WF)."""
    p = Project.create("boq-lin", vcs=False)
    p.add_level("L1", 0)
    p.place_part(level="L1", section="W10x33", length_m=3.5, name="COL-1")
    p.place_part(level="L1", bar_size="5", length_m=50.0, name="R5")
    p.place_part(level="L1", kind="toilet", origin=(0, 0))
    boq = p.boq()["lines"]
    steel = [r for r in boq if "W10" in str(r.get("type_name", "")) or "W10" in str(r.get("type_id", ""))]
    assert steel, boq
    assert steel[0]["unit"] == "m"
    assert abs(float(steel[0]["qty"]) - 3.5) < 0.01
    rebar = [r for r in boq if "rebar" in str(r.get("category", "")).lower() or "#5" in str(r.get("type_name", ""))]
    assert rebar
    assert rebar[0]["unit"] == "m"
    assert abs(float(rebar[0]["qty"]) - 50.0) < 0.01
    # part assignment list units
    from llmbim_core.material_lists import part_assignment_list

    assigns = part_assignment_list(p.model)
    w = next(a for a in assigns if "W10" in str(a["part_id"]))
    assert w["unit"] == "m"
    assert abs(float(w["qty"]) - 3.5) < 0.01
