"""Structural steel column place, CSI, plan, BOQ."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_core.quantities import compute_boq
from llmbim_drawings.plan import write_plan_svg
from llmbim_drawings.schedules import schedule_rows


def test_place_column_csi_boq_plan(tmp_path: Path):
    p = Project.create("cols", vcs=False)
    p.add_level("L1", 0)
    eid = p.place_column(
        level="L1",
        origin=(3000, 4000),
        section="W10x33",
        height_mm=3500,
        name="C1",
    )
    el = p.model.get_element(eid)
    assert el.category == "column"
    assert el.params.get("section") == "W10x33"
    assert abs(float(el.params["length_m"]) - 3.5) < 0.01
    row = next(r for r in p.csi_instances() if r.get("element_id") == eid)
    assert row["csi_code"] == "05 12 00"

    boq = compute_boq(p.model)
    cols = [r for r in boq if r["category"] == "column"]
    assert len(cols) == 1
    assert abs(float(cols[0]["qty"]) - 3.5) < 0.01

    sched = schedule_rows(p.model, "column")
    assert len(sched) == 1
    assert sched[0]["section"] == "W10x33"

    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    text = plan.read_text(encoding="utf-8")
    assert 'class="columns"' in text
    assert "W10x33" in text


def test_place_beam_csi_and_plan(tmp_path: Path):
    p = Project.create("beams", vcs=False)
    p.add_level("L1", 0)
    eid = p.place_beam(
        level="L1",
        start=(0, 2000),
        end=(8000, 2000),
        section="W12x26",
        name="B1",
    )
    el = p.model.get_element(eid)
    assert el.category == "beam"
    assert abs(float(el.params["length_m"]) - 8.0) < 0.01
    row = next(r for r in p.csi_instances() if r.get("element_id") == eid)
    assert row["csi_code"] == "05 12 00"
    boq = compute_boq(p.model)
    assert any(r["category"] == "beam" and abs(float(r["qty"]) - 8.0) < 0.01 for r in boq)
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    text = plan.read_text(encoding="utf-8")
    assert 'class="beams"' in text
    assert "W12x26" in text


def test_structure_on_plan_dxf(tmp_path: Path):
    from llmbim_drawings.dxf_export import export_plan_dxf

    p = Project.create("struct-dxf", vcs=False)
    p.add_level("L1", 0)
    p.place_column(level="L1", origin=(2000, 2000), section="W10x33", height_mm=3500)
    p.place_beam(level="L1", start=(0, 2000), end=(6000, 2000), section="W12x26")
    dxf = tmp_path / "s.dxf"
    export_plan_dxf(p.model, "L1", dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "COLUMNS" in text
    assert "BEAMS" in text
    assert "W10x33" in text
    assert "W12x26" in text


def test_column_beam_clash():
    from llmbim_core.clash import find_clashes

    p = Project.create("struct-clash", vcs=False)
    p.add_level("L1", 0)
    # beam through column center at same Z band
    p.place_column(level="L1", origin=(4000, 2000), section="W10x33", height_mm=3500)
    p.place_beam(
        level="L1",
        start=(0, 2000),
        end=(8000, 2000),
        section="W12x26",
        z0_mm=3000,
    )
    clashes = find_clashes(p.model)
    assert any(
        {c.get("a_category"), c.get("b_category")} == {"column", "beam"} for c in clashes
    ), clashes[:5]


def test_steel_takeoff_includes_placed_columns_beams():
    p = Project.create("steel-to", vcs=False)
    p.add_level("L1", 0)
    p.place_column(level="L1", origin=(0, 0), section="W10x33", height_mm=3500)
    p.place_beam(level="L1", start=(0, 0), end=(10000, 0), section="W12x26")
    steel = p.steel_takeoff() if hasattr(p, "steel_takeoff") else None
    if steel is None:
        from llmbim_core.material_lists import steel_takeoff

        steel = steel_takeoff(p.model)
    assert steel
    # lengths present for column 3.5m and beam 10m
    total = 0.0
    for r in steel:
        total += float(r.get("qty") or r.get("length_m") or 0)
    assert total >= 13.0, steel
