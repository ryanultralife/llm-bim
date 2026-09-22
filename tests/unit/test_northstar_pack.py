"""A device and a site both leave one pack, at the size that was placed.

The kernel is the document and rendering path. A shield lid keeps its soffit.
A duct and a duct bank keep width_mm by height_mm in the mesh, the section,
and the IFC solid.
"""

from __future__ import annotations

import json
from pathlib import Path

from llmbim import Project
from llmbim_drawings.plan import write_plan_svg
from llmbim_drawings.section import write_section_svg
from llmbim_geometry.mesh import export_gltf_walls
from llmbim_ifc import export_ifc


def _vec3(gltf: dict) -> list[dict]:
    return [
        a
        for a in gltf["accessors"]
        if a.get("type") == "VEC3" and a.get("min") and a.get("max") and a["max"][1] > 2
    ]


def test_device_pack_is_the_document_set(tmp_path: Path) -> None:
    p = Project.create("Northstar device", vcs=False)
    p.add_level("L1", 0)
    p.create_equipment_box(
        level="L1", origin=(0, 0), size=(1200, 800, 1500), name="SKID-1", centered=True,
    )
    out = tmp_path / "device"
    p.export_deliverables(out)
    assert (out / "model.llmbim.json").is_file()
    assert (out / "index.html").is_file()
    assert (out / "hero.svg").stat().st_size > 100
    assert (out / "model.gltf").is_file()
    assert "SKID-1" in (out / "model.llmbim.json").read_text(encoding="utf-8")


def test_site_lid_duct_and_bank_keep_their_size(tmp_path: Path) -> None:
    p = Project.create("Northstar site", vcs=False)
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=12000, d=8000, height_mm=3500, thickness_mm=200,
        name_prefix="H",
    )
    p.place_shield_slab(
        level="L1",
        origin=(0, 0),
        width_mm=12000,
        depth_mm=8000,
        thickness_mm=1500,
        z0=9000,
        name="LID",
    )
    p.place_duct(
        level="L1",
        start=(500, 2000),
        end=(11000, 2000),
        width_mm=1118,
        height_mm=800,
        z0=7000,
        name="SA-MAIN",
    )
    bank_id = p.place_duct_bank(
        level="L1",
        start=(500, 6000),
        end=(11000, 6000),
        trade_size="4",
        conduit_count=6,
        spare_count=2,
        z0=-900,
        name="DB-1",
    )
    bank = p.model.get_element(bank_id)
    bank_w = float(bank.params["width_mm"])
    bank_h = float(bank.params["height_mm"])
    assert bank.category == "duct_bank"
    assert bank_w > float(bank.params["conduit_od_mm"])

    plan = tmp_path / "plan.svg"
    write_plan_svg(p.model, "L1", plan)
    plan_txt = plan.read_text(encoding="utf-8")
    assert 'class="shield-slabs"' in plan_txt
    assert "LID 1500 @ 9000" in plan_txt
    assert 'class="duct-banks"' in plan_txt
    assert f"DB 6×4&quot; {bank_w:.0f}" in plan_txt or f'DB 6×4" {bank_w:.0f}' in plan_txt

    section = tmp_path / "section.svg"
    write_section_svg(p.model, (6000, 0), (6000, 8000), section, scale=0.05)
    sec = section.read_text(encoding="utf-8")
    # 1118 mm by 800 mm at 0.05 px/mm. The old section drew the width at half.
    assert 'width="55.9" height="40"' in sec

    gltf_path = tmp_path / "site.gltf"
    export_gltf_walls(p.model, gltf_path)
    gltf = json.loads(gltf_path.read_text(encoding="utf-8"))
    boxes = _vec3(gltf)
    below = [
        a for a in gltf["accessors"]
        if a.get("type") == "VEC3" and a.get("min") and a["min"][1] < 0
    ]
    assert any(abs(a["min"][1] - 9.0) < 0.02 and abs(a["max"][1] - 10.5) < 0.02 for a in boxes)
    duct = next(
        a for a in boxes if abs(a["min"][1] - 7.0) < 0.02 and abs(a["max"][1] - 7.8) < 0.02
    )
    assert abs((duct["max"][2] - duct["min"][2]) - 1.118) < 0.02
    assert any(
        abs(a["min"][1] - (-0.9)) < 0.02 and abs(a["max"][1] - (-0.9 + bank_h / 1000.0)) < 0.02
        for a in below
    )

    ifc_path = tmp_path / "site.ifc"
    export_ifc(p.model, ifc_path)
    ifc = ifc_path.read_text(encoding="utf-8")
    assert "IFCCARTESIANPOINT((0.0,0.0,9000.0))" in ifc
    assert ".USERDEFINED." in ifc
    assert "IFCCARTESIANPOINT((500.0,2000.0,7000.0))" in ifc
    assert "10500.0,1118.0" in ifc
    assert "IFCEXTRUDEDAREASOLID" in ifc
    assert ",800.0)" in ifc
    assert "IFCCABLECARRIERSEGMENT" in ifc
    assert f"{bank_w}" in ifc
