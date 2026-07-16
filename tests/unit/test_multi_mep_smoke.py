"""Multi-trade pack smoke: MEP + structure + tray + takeoffs + pack artifacts."""

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
    walls = p.create_rect_shell(
        level="L1", x=0, y=0, w=12000, d=8000, height_mm=3500, thickness_mm=200
    )
    # openings on south wall (first shell wall is typically S)
    host = walls[0] if walls else None
    if host:
        p.place_door(
            host=host,
            offset_mm=2000,
            width_mm=900,
            height_mm=2100,
            type_id="D-HM-36",
            fire_rating="90 min",
        )
        p.place_window(
            host=host,
            offset_mm=5000,
            width_mm=1200,
            height_mm=900,
            sill_mm=900,
            type_id="WIN-VIEW",
        )
    p.create_slab(
        level="L1",
        polygon=[(0, 0), (12000, 0), (12000, 8000), (0, 8000)],
        thickness_mm=200,
        name="Slab-L1",
    )
    p.create_room(
        level="L1",
        name="Mech Room",
        boundary=[(200, 200), (4000, 200), (4000, 3000), (200, 3000)],
        height_mm=3500,
    )
    p.add_grid(axis="U", positions_mm=[0, 6000, 12000], name="Grid-U", labels=["1", "2", "3"])
    p.add_grid(axis="V", positions_mm=[0, 4000, 8000], name="Grid-V", labels=["A", "B", "C"])
    p.create_note(level="L1", text="Multi-trade coordination grade", position=(500, 7500))
    p.create_equipment_box(
        level="L1",
        origin=(9000, 3000),
        size=(1500, 1000, 1800),
        name="AHU-1",
        kind="ahu",
        centered=True,
    )
    p.place_pipe(level="L1", nps="2", start=(500, 1500), end=(5000, 1500), material="copper")
    p.place_riser(level="L1", nps="2", origin=(5000, 1500), to_level="L2", material="copper")
    p.place_duct(level="L1", start=(1000, 4000), end=(9000, 4000), width_mm=600, height_mm=350)
    p.place_conduit(level="L1", start=(200, 5000), end=(8000, 5000), trade_size="1")
    p.place_cable_tray(level="L1", start=(200, 5500), end=(8000, 5500), width_mm=450)
    p.place_column(level="L1", origin=(6000, 2000), section="W10x33", height_mm=3500)
    p.place_beam(level="L1", start=(2000, 2000), end=(10000, 2000), section="W12x26", z0_mm=3000)
    p.place_part(level="L1", part_id="PT-ELEC-PANEL-42", origin=(800, 800))
    p.place_part(level="L1", part_id="PT-HVAC-DIFF-24", origin=(6000, 5000))

    codes = {r["csi_code"] for r in p.csi_instances()}
    assert "22 11 16" in codes  # pipe
    assert "23 31 00" in codes  # duct
    assert "26 05 33" in codes  # conduit
    assert "26 05 36" in codes  # cable tray
    assert "05 12 00" in codes  # column/beam
    assert "26 24 16" in codes  # panel
    assert "23 37 00" in codes  # diffuser

    rooms = [r for r in p.csi_instances() if r.get("room") == "Mech Room"]
    assert rooms

    # Trade takeoffs
    assert p.duct_takeoff() and sum(r["length_m"] for r in p.duct_takeoff()) > 0
    assert p.conduit_takeoff()
    assert p.cable_tray_takeoff()
    steel = p.steel_takeoff()
    assert steel
    assert any(float(r.get("qty") or 0) > 0 for r in steel)

    plan = tmp_path / "plan.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.01)
    pt = plan.read_text(encoding="utf-8")
    assert 'class="ducts"' in pt
    assert 'class="pipes"' in pt
    assert 'class="columns"' in pt
    assert 'class="beams"' in pt
    assert "cable-trays" in pt
    assert 'class="notes"' in pt or "Multi-trade" in pt
    if host:
        assert "openings" in pt or "D-HM" in pt or "HM-36" in pt

    elev = tmp_path / "elev.svg"
    write_elevation_svg(p.model, "S", elev, scale=0.01)
    et = elev.read_text(encoding="utf-8")
    assert elev.is_file()
    assert "columns-elev" in et or "W10x33" in et
    if host:
        assert "openings-elev" in et or "HM-36" in et or "WIN" in et

    ifc = tmp_path / "m.ifc"
    export_ifc(p.model, ifc)
    text = ifc.read_text(encoding="utf-8")
    assert "IFCFLOWSEGMENT" in text
    assert "Pset_CSIMasterFormat" in text
    if host:
        assert "IFCDOOR" in text
        assert "IFCWINDOW" in text
    assert "IFCCOLUMN" in text or "IFCBEAM" in text

    out = tmp_path / "pack"
    man = p.export_deliverables(out)
    assert man.get("ok") is True
    assert (out / "materials" / "csi_instances.json").is_file() or (
        out / "schedules" / "csi.csv"
    ).is_file()
    # structure + MEP schedules / views from pack
    assert (out / "schedules" / "levels.csv").is_file()
    assert (out / "schedules" / "drawing_list.csv").is_file()
    assert (out / "schedules" / "doors.csv").is_file() or (
        out / "schedules" / "door.csv"
    ).is_file()
    assert (out / "schedules" / "windows.csv").is_file() or (
        out / "schedules" / "window.csv"
    ).is_file()
    assert (out / "schedules" / "duct.csv").is_file() or (
        out / "materials" / "duct_takeoff.json"
    ).is_file()
    assert (out / "views" / "elev_S.dxf").is_file() or list((out / "views").glob("elev*.dxf"))
    assert (out / "views" / "section.dxf").is_file() or list(
        (out / "views").glob("section*.dxf")
    )
    # plan DXF has structure + openings layers
    plan_dxfs = list((out / "views").glob("plan*.dxf"))
    if plan_dxfs:
        dx = plan_dxfs[0].read_text(encoding="utf-8")
        assert "COLUMNS" in dx or "BEAMS" in dx
        if host:
            assert "DOORS" in dx or "WINDOWS" in dx
    v = p.verify_pack(out)
    assert v.get("ok") is True
    assert v.get("has_doors_schedule") is True
    assert v.get("has_windows_schedule") is True
    assert v.get("has_index_html") is True
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "Door schedule" in html or "doors.csv" in html or "door.csv" in html
