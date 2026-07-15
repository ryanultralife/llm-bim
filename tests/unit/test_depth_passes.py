"""Depth passes: cylindrical STEP, PDF binder, STEP import, CSI BOQ."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_geometry.step_export import export_step
from llmbim_geometry.step_import import parse_step_bbox
from llmbim_drawings.pdf_binder import export_pdf_binder


def test_cylindrical_step_has_many_faces(tmp_path: Path) -> None:
    p = Project.create("Cyl")
    p.add_level("B", 0)
    p.create_equipment_box(
        level="B",
        origin=(0, 0),
        size=(500, 320, 320),
        name="Shell",
        shape="cylinder",
        centered=True,
    )
    out = tmp_path / "c.step"
    export_step(p.model, out, include_walls=False, cyl_sides=24)
    text = out.read_text(encoding="utf-8")
    assert "MANIFOLD_SOLID_BREP" in text
    # cylinder has many ADVANCED_FACE vs box's 6
    assert text.count("ADVANCED_FACE") >= 20


def test_step_exports_pipe_and_fitting(tmp_path: Path) -> None:
    p = Project.create("STEP-MEP", vcs=False)
    p.add_level("L1", 0)
    p.place_pipe(level="L1", nps="1", start=(0, 0), end=(2000, 0), material="copper")
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="1", origin=(0, 0), material="copper")
    out = tmp_path / "mep.step"
    export_step(p.model, out, include_walls=False)
    text = out.read_text(encoding="utf-8")
    assert "MANIFOLD_SOLID_BREP" in text
    assert text.count("MANIFOLD_SOLID_BREP") >= 2


def test_pdf_binder(tmp_path: Path) -> None:
    p = Project.from_template("office_bay")
    sheets = tmp_path / "sheets"
    p.export_construction_set(sheets, plan_scale=0.05)
    pdf = tmp_path / "set.pdf"
    export_pdf_binder(sheets, pdf, title=p.name)
    data = pdf.read_bytes()
    assert data[:5] == b"%PDF-"
    assert len(data) > 500
    assert b"endobj" in data


def test_step_import_roundtrip(tmp_path: Path) -> None:
    # create a STEP via our exporter then re-import
    p = Project.create("Src")
    p.add_level("L1", 0)
    p.create_equipment_box(
        level="L1", origin=(0, 0), size=(1000, 500, 500), name="Block", shape="box", centered=True
    )
    step = tmp_path / "block.step"
    p.export_step(step, include_walls=False)
    bbox = parse_step_bbox(step)
    assert bbox is not None
    assert bbox["point_count"] >= 8

    p2 = Project.create("Imp")
    p2.add_level("L1", 0)
    eid = p2.import_step(step, level="L1", name="Imported", copy_into=tmp_path / "refs")
    el = p2.model.get_element(eid)
    assert el.params.get("locked") is True
    assert Path(str(el.params["step_ref_path"])).is_file()
    pack = tmp_path / "pack"
    man = p2.export_deliverables(pack, mode="part")
    assert (pack / "step_refs").is_dir() or man.get("ok")


def test_csi_in_boq() -> None:
    p = Project.from_template("office_bay")
    boq = p.boq()
    wall = next(r for r in boq["lines"] if r["category"] == "wall")
    assert "csi_code" in wall
    assert wall["csi_division"]
    assert "est_cost_by_csi_division" in boq["summary"]


def test_door_tags_in_plan(tmp_path: Path) -> None:
    p = Project.from_template("office_bay")
    p.export_plan("L1", tmp_path / "plan.svg", scale=0.05)
    text = (tmp_path / "plan.svg").read_text(encoding="utf-8")
    assert "D1" in text  # door tag
