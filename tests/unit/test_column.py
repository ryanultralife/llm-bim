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
