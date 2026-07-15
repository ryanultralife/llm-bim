"""Cable tray place, takeoff, CSI, plan, BOQ."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.dxf_export import export_plan_dxf
from llmbim_drawings.plan import write_plan_svg


def test_place_cable_tray_csi_and_takeoff():
    p = Project.create("tray", vcs=False)
    p.add_level("L1", 0)
    eid = p.place_cable_tray(
        level="L1",
        start=(0, 0),
        end=(10000, 0),
        width_mm=450,
        height_mm=100,
        system="PWR",
    )
    el = p.model.get_element(eid)
    assert el.category == "cable_tray"
    assert abs(float(el.params["length_m"]) - 10.0) < 0.01
    row = next(r for r in p.csi_instances() if r.get("element_id") == eid)
    assert row["csi_code"] == "26 05 36"
    trays = p.cable_tray_takeoff()
    assert len(trays) == 1
    assert abs(trays[0]["length_m"] - 10.0) < 0.01
    assert trays[0]["csi_code"] == "26 05 36"
    trades = p.trade_schedule()
    assert "cable_tray" in trades["electrical"]
    assert len(trades["electrical"]["cable_tray"]) == 1


def test_cable_tray_on_plan_and_dxf(tmp_path: Path):
    p = Project.create("tray-draw", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(12000, 0), thickness_mm=200, height_mm=3000)
    p.place_cable_tray(level="L1", start=(1000, 2000), end=(9000, 2000), width_mm=300)
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    pt = plan.read_text(encoding="utf-8")
    assert "cable-trays" in pt
    assert "CT 300" in pt
    dxf = tmp_path / "d.dxf"
    export_plan_dxf(p.model, "L1", dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "CABLE-TRAY" in text


def test_boq_includes_cable_tray():
    p = Project.create("boq-tray", vcs=False)
    p.add_level("L1", 0)
    p.place_cable_tray(level="L1", start=(0, 0), end=(5000, 0), width_mm=300)
    from llmbim_core.quantities import compute_boq

    rows = compute_boq(p.model)
    cats = {r["category"] for r in rows}
    assert "cable_tray" in cats
    tray = next(r for r in rows if r["category"] == "cable_tray")
    assert abs(float(tray["qty"]) - 5.0) < 0.01
    assert tray["csi_code"] == "26 05 36"
