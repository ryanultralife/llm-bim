"""Multi-trade MEP smoke: pipe + riser + duct + conduit + panel + CSI rooms."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.plan import write_plan_svg
from llmbim_drawings.section import write_elevation_svg
from llmbim_ifc import export_ifc


def test_multi_mep_pack_smoke(tmp_path: Path):
    p = Project.create("multi-mep", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 3500)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=12000, d=8000, height_mm=3500, thickness_mm=200
    )
    p.create_room(
        level="L1",
        name="Mech Room",
        boundary=[(200, 200), (4000, 200), (4000, 3000), (200, 3000)],
    )
    p.place_pipe(level="L1", nps="2", start=(500, 1500), end=(5000, 1500), material="copper")
    p.place_riser(level="L1", nps="2", origin=(5000, 1500), to_level="L2", material="copper")
    p.place_duct(level="L1", start=(1000, 4000), end=(9000, 4000), width_mm=600, height_mm=350)
    p.place_conduit(level="L1", start=(200, 5000), end=(8000, 5000), trade_size="1")
    p.place_part(level="L1", part_id="PT-ELEC-PANEL-42", origin=(800, 800))
    p.place_part(level="L1", part_id="PT-HVAC-DIFF-24", origin=(6000, 5000))

    codes = {r["csi_code"] for r in p.csi_instances()}
    assert "22 11 16" in codes  # pipe
    assert "23 31 00" in codes  # duct
    assert "26 05 33" in codes  # conduit
    assert "26 24 16" in codes  # panel
    assert "23 37 00" in codes  # diffuser

    rooms = [r for r in p.csi_instances() if r.get("room") == "Mech Room"]
    assert rooms

    plan = tmp_path / "plan.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.01)
    pt = plan.read_text(encoding="utf-8")
    assert 'class="ducts"' in pt
    assert 'class="pipes"' in pt

    elev = tmp_path / "elev.svg"
    write_elevation_svg(p.model, "S", elev, scale=0.01)
    assert elev.is_file()

    ifc = tmp_path / "m.ifc"
    export_ifc(p.model, ifc)
    text = ifc.read_text(encoding="utf-8")
    assert "IFCFLOWSEGMENT" in text

    out = tmp_path / "pack"
    man = p.export_deliverables(out)
    assert man.get("ok") is True
    assert (out / "materials" / "csi_instances.json").is_file() or (
        out / "schedules" / "csi.csv"
    ).is_file()
