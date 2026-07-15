"""HVAC rectangular duct place + CSI + plan/DXF."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.dxf_export import export_plan_dxf
from llmbim_drawings.plan import write_plan_svg


def test_place_duct_length_area_csi():
    p = Project.create("duct", vcs=False)
    p.add_level("L1", 0)
    eid = p.place_duct(
        level="L1",
        start=(0, 0),
        end=(5000, 0),
        width_mm=400,
        height_mm=250,
        system="SA",
    )
    el = p.model.get_element(eid)
    assert el.category == "duct"
    assert abs(float(el.params["length_m"]) - 5.0) < 0.01
    assert float(el.params["area_m2"]) > 0
    rows = p.csi_instances()
    duct = next(r for r in rows if r.get("element_id") == eid)
    assert duct["csi_code"] == "23 31 00"
    assert duct["csi_division"] == "23"


def test_duct_on_plan_and_dxf(tmp_path: Path):
    p = Project.create("duct-draw", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    p.place_duct(level="L1", start=(1000, 2000), end=(6000, 2000), width_mm=500, height_mm=300)
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    pt = plan.read_text(encoding="utf-8")
    assert 'class="ducts"' in pt
    assert "500x300" in pt
    dxf = tmp_path / "d.dxf"
    export_plan_dxf(p.model, "L1", dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "DUCT" in text
