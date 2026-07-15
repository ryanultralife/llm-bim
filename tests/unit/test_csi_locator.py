"""CSI MasterFormat codes + location locators."""

from __future__ import annotations

from llmbim import Project
from llmbim_core.csi import csi_for_element, csi_instance_schedule, normalize_csi_code, resolve_csi_code


def test_normalize_and_resolve_real_codes():
    assert normalize_csi_code("221116") == "22 11 16"
    assert resolve_csi_code(fitting_type="elbow_90", material_id="copper_C12200") == "22 11 16"
    assert resolve_csi_code(fitting_type="elbow_90", system="fire") == "21 13 13"
    assert resolve_csi_code(fitting_type="pipe", system="process") == "40 05 13"
    assert resolve_csi_code(part_id="PT-PLB-WC-FLOOR") == "22 42 13"
    assert resolve_csi_code(fitting_type="ball_valve") == "22 05 23"


def test_csi_instance_has_level_xy_z():
    p = Project.create("csi-loc", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 3500)
    p.place_fitting(
        level="L1",
        fitting_type="elbow_90",
        nps="3/4",
        origin=(1200, 3400),
        material="copper",
    )
    # set height on fitting
    el = [e for e in p.model.elements if e.category == "fitting"][0]
    el.params["z0_mm"] = 900
    row = csi_for_element(p.model, el)
    assert row["csi_code"] == "22 11 16"
    assert row["csi_section_name"]  # titled
    assert row["level"] == "L1"
    assert row["x_mm"] == 1200
    assert row["y_mm"] == 3400
    assert row["z_mm"] == 900
    assert "L1" in row["locator"]
    assert "X1200" in row["locator"]
    assert "Z900" in row["locator"]
    assert row["csi_instance"].startswith("22 11 16 @")


def test_fire_fitting_csi_and_schedule():
    p = Project.create("csi-fire", vcs=False)
    p.add_level("L0", 0)
    p.place_fitting(level="L0", fitting_type="elbow_90", nps="2", origin=(0, 0), material="fire")
    p.place_part(level="L0", kind="toilet", origin=(5000, 5000))
    rows = csi_instance_schedule(p.model)
    codes = {r["csi_code"] for r in rows}
    assert "21 13 13" in codes  # fire elbow
    assert "22 42 13" in codes  # water closet
    # SDK
    assert any(r["csi_code"] == "21 13 13" for r in p.csi_instances())


def test_locator_includes_room_name():
    p = Project.create("csi-room", vcs=False)
    p.add_level("L1", 0)
    p.create_room(
        level="L1",
        name="Restroom A",
        boundary=[(0, 0), (4000, 0), (4000, 3000), (0, 3000)],
    )
    p.place_part(level="L1", kind="toilet", origin=(2000, 1500))
    p.place_fitting(
        level="L1",
        fitting_type="elbow_90",
        nps="1/2",
        origin=(1500, 1200),
        material="copper",
    )
    rows = p.csi_instances()
    toilet = next(r for r in rows if r.get("fitting_type") == "toilet" or "WC" in str(r.get("part_id", "")))
    # part assignment uses toilet fitting_type from specs
    toilet = next((r for r in rows if "toilet" in str(r.get("fitting_type", "")).lower() or "WC" in str(r.get("element_name", ""))), None)
    if toilet is None:
        toilet = next(r for r in rows if r.get("x_mm") == 2000)
    assert toilet.get("room") == "Restroom A" or "Restroom" in str(toilet.get("locator", ""))
    assert "RM:Restroom" in str(toilet.get("locator", "")) or toilet.get("room") == "Restroom A"
    elbow = next(r for r in rows if r.get("fitting_type") == "elbow_90")
    assert elbow.get("room") == "Restroom A"
