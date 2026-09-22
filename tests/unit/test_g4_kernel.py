"""G4 kernel: tray/duct elevation aliases and the pipe SKUs those runs need."""

from __future__ import annotations

import pytest

from llmbim import Project
from llmbim_core.catalog_systems import STEEL_NPS
from llmbim_core.errors import ValidationError
from llmbim_core.parts_catalog import get_part, resolve_fitting_part_id, resolve_pipe_sku


def _project() -> Project:
    p = Project.create("g4", vcs=False)
    p.add_level("L1", 0)
    return p


def test_place_cable_tray_stores_system_tag_and_z0() -> None:
    p = _project()
    eid = p.place_cable_tray(
        level="L1",
        start=(0, 0),
        end=(4000, 0),
        width_mm=600,
        system_tag="IC",
        z0=8500,
        tray_type="solid_bottom",
    )
    el = p.model.get_element(eid)
    assert el.params["system_tag"] == "IC"
    assert el.params["system"] == "IC"
    assert el.params["z0"] == 8500
    assert el.params["z0_mm"] == 8500
    assert el.params["tray_type"] == "solid_bottom"

    # Omitted system and z keep the historical defaults.
    bare = p.model.get_element(
        p.place_cable_tray(level="L1", start=(0, 1000), end=(2000, 1000))
    )
    assert bare.params["system_tag"] == "PWR"
    assert bare.params["z0"] == 2900
    assert bare.params["z0_mm"] == 2900
    assert bare.params["tray_type"] == "rung"

    # Old keyword names still land on the same fields.
    old = p.model.get_element(
        p.place_cable_tray(
            level="L1",
            start=(0, 2000),
            end=(2000, 2000),
            system="IC",
            z0_mm=4100,
            tray_type="ladder",
            nema_width_mm=304.8,
        )
    )
    assert old.params["system_tag"] == "IC"
    assert old.params["z0"] == 4100
    assert old.params["tray_type"] == "rung"
    assert old.params["nema_width_mm"] == 304.8
    assert old.params["width_mm"] == 304.8


def test_place_duct_stores_z0() -> None:
    p = _project()
    eid = p.place_duct(
        level="L1",
        start=(0, 0),
        end=(3000, 0),
        width_mm=500,
        height_mm=300,
        z0=4200,
    )
    el = p.model.get_element(eid)
    assert el.params["z0"] == 4200
    assert el.params["z0_mm"] == 4200

    bare = p.model.get_element(
        p.place_duct(level="L1", start=(0, 1000), end=(2000, 1000))
    )
    assert bare.params["z0"] == 2700
    assert bare.params["z0_mm"] == 2700

    # z0_mm still wins when both are passed, and still stores z0.
    both = p.model.get_element(
        p.place_duct(
            level="L1",
            start=(0, 2000),
            end=(2000, 2000),
            z0_mm=5100,
            z0=100,
        )
    )
    assert both.params["z0_mm"] == 5100
    assert both.params["z0"] == 5100


def test_place_duct_bank_is_conduits_not_a_tray() -> None:
    p = _project()
    eid = p.place_duct_bank(
        level="L1",
        start=(0, 0),
        end=(8000, 0),
        trade_size="4",
        conduit_count=6,
        spare_count=2,
        system_tag="PWR",
        z0=-900,
        feeder_ids=["FDR-1"],
    )
    el = p.model.get_element(eid)
    assert el.category == "duct_bank"
    assert el.category != "cable_tray"
    assert el.params["fitting_type"] == "duct_bank"
    assert el.params["trade_size"] == "4"
    assert el.params["conduit_count"] == 6
    assert el.params["spare_count"] == 2
    assert el.params["feeder_ids"] == ["FDR-1"]
    assert el.params["z0"] == -900
    assert el.params["system_tag"] == "PWR"
    assert el.params["width_mm"] > el.params["conduit_od_mm"]


def test_g4_pipe_skus_resolve() -> None:
    # DN → NPS on the existing steel ladder. DN32/65/100 already had SS parts.
    existing_ss = {32: "PT-SS-PIPE-1_1_4", 65: "PT-SS-PIPE-2_1_2", 100: "PT-SS-PIPE-4"}
    added = {125: "5", 250: "10", 300: "12"}
    for dn, pid in existing_ss.items():
        assert resolve_pipe_sku("ss", dn) == pid
        assert resolve_pipe_sku("process", f"DN{dn}") == pid
        cs = resolve_pipe_sku("cs", dn)
        assert cs is not None and cs != pid
        assert get_part(cs).specs["od_mm"] == get_part(pid).specs["od_mm"]
        assert get_part(cs).specs["schedule"] == "40"
    for dn, nps in added.items():
        ss = resolve_pipe_sku("ss", dn)
        cs = resolve_pipe_sku("carbon_steel", dn)
        assert ss == f"PT-SS-PIPE-{nps.replace('-', '_')}"
        assert get_part(ss).specs["od_mm"] == STEEL_NPS[nps]["od_mm"]
        assert get_part(ss).specs["dn"] == dn
        assert get_part(cs).specs["od_mm"] == STEEL_NPS[nps]["od_mm"]
        assert resolve_fitting_part_id("pipe", nps, material="cs") == cs
        assert resolve_fitting_part_id("pipe", nps, material="process") == ss

    # One Sch40 SS pipe per DN — the old sizes were not registered twice.
    assert get_part("PT-SS-PIPE-DN32") is None
    assert get_part("PT-SS-PIPE-1_1_4").specs["dn"] == 32

    jacket50 = resolve_pipe_sku("cs", 25, schedule="80", containment_dn=50)
    jacket80 = resolve_pipe_sku("cl2", "DN25", schedule="Sch80", containment_dn=80)
    assert jacket50 == "PT-CS-CL2-SCH80-DN25-IN-DN50"
    assert jacket80 == "PT-CS-CL2-SCH80-DN25-IN-DN80"
    c50 = get_part(jacket50)
    c80 = get_part(jacket80)
    assert c50.specs["carrier_od_mm"] == STEEL_NPS["1"]["od_mm"]
    assert c50.specs["carrier_schedule"] == "80"
    assert c50.specs["containment_od_mm"] == STEEL_NPS["2"]["od_mm"]
    assert c80.specs["containment_od_mm"] == STEEL_NPS["3"]["od_mm"]
    # No bare CS DN25 Sch40 pipe was added beside the carrier.
    assert resolve_fitting_part_id("pipe", "1", material="cs") is None

    ci80 = resolve_pipe_sku("cast_iron", 80)
    ci100 = resolve_pipe_sku("no-hub", 100)
    assert ci80 == "PT-CI-PIPE-3"
    assert ci100 == "PT-CI-PIPE-4"
    # Soil-pipe barrel OD, not the steel DN80/DN100 OD.
    assert get_part(ci80).specs["od_mm"] == 85.1
    assert get_part(ci80).specs["od_mm"] != STEEL_NPS["3"]["od_mm"]
    assert get_part(ci100).specs["spec"].startswith("ASTM A888")

    sch40 = resolve_pipe_sku("ss", 300)
    sch10 = resolve_pipe_sku("ss", 300, schedule="10S")
    assert sch40 == "PT-SS-PIPE-12"
    assert sch10 == "PT-SS-PIPE-10S-12"
    assert sch10 != sch40
    thin = get_part(sch10)
    assert thin.specs["schedule"] == "10S"
    assert thin.specs["dn"] == 300
    assert thin.specs["od_mm"] == STEEL_NPS["12"]["od_mm"]
    assert thin.specs["mass_kg_m"] < get_part(sch40).specs["mass_kg_m"]


def test_place_shield_slab_is_a_monolithic_lid() -> None:
    bare = _project()
    assert not any(e.params.get("kind") == "shield_slab" for e in bare.model.elements)
    with pytest.raises(ValidationError):
        bare.place_shield_slab(
            level="L1",
            origin=(0, 0),
            width_mm=1000,
            depth_mm=1000,
            thickness_mm=1500,
        )
    assert not any(e.params.get("kind") == "shield_slab" for e in bare.model.elements)

    p = _project()
    eid = p.place_shield_slab(
        level="L1",
        origin=(0, 0),
        width_mm=10000,
        depth_mm=4000,
        thickness_mm=1500,
        z0=9000,
    )
    el = p.model.get_element(eid)
    assert el.category == "slab"
    assert el.params["kind"] == "shield_slab"
    assert el.params["monolithic"] is True
    assert el.params["thickness_mm"] == 1500
    assert el.params["z0"] == 9000
    assert el.params["z0_mm"] == 9000
    assert el.params["top_of_slab_mm"] == 10500
    assert "plug" not in el.params
    assert "well" not in el.params
    floor = p.model.get_element(
        p.create_slab(
            level="L1",
            polygon=[(0, 0), (1000, 0), (1000, 1000)],
            thickness_mm=200,
        )
    )
    assert floor.params.get("kind") != "shield_slab"
    assert "z0" not in floor.params
