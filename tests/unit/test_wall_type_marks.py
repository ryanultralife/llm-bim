"""Plan shows wall type marks (e.g. EXT-CMU)."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.plan import write_plan_svg


def test_wall_type_on_plan(tmp_path: Path):
    p = Project.create("wall-types", vcs=False)
    p.add_level("L1", 0)
    wid = p.create_wall(
        level="L1",
        start=(0, 0),
        end=(8000, 0),
        thickness_mm=200,
        height_mm=3000,
        type_id="W-EXT-CMU",
    )
    assert wid
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    text = plan.read_text(encoding="utf-8")
    assert 'class="wall-types"' in text
    assert "EXT-CMU" in text


def test_room_ceiling_height_schedule():
    from llmbim_drawings.schedules import schedule_rows

    p = Project.create("room-h", vcs=False)
    p.add_level("L1", 0)
    p.create_room(
        level="L1",
        name="Office",
        boundary=[(0, 0), (4000, 0), (4000, 3000), (0, 3000)],
        height_mm=2700,
    )
    rows = schedule_rows(p.model, "room")
    assert rows[0]["height_mm"] == 2700
    assert rows[0]["ceiling_height_mm"] == 2700
    el = next(e for e in p.model.elements if e.category == "room")
    assert el.params.get("ceiling_height_mm") == 2700


def test_door_window_type_marks_on_plan(tmp_path: Path):
    from llmbim_drawings.plan import write_plan_svg

    p = Project.create("open-types", vcs=False)
    p.add_level("L1", 0)
    w = p.create_wall(
        level="L1", start=(0, 0), end=(10000, 0), thickness_mm=200, height_mm=3000
    )
    p.place_door(host=w, offset_mm=1000, width_mm=900, height_mm=2100, type_id="D-HM-36")
    p.place_window(
        host=w,
        offset_mm=4000,
        width_mm=600,
        height_mm=600,
        sill_mm=900,
        type_id="WIN-VIEW-24x24",
    )
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    text = plan.read_text(encoding="utf-8")
    assert "D1" in text
    assert "HM-36" in text
    assert "opening-type" in text
    assert "WIN-VIEW" in text or "VIEW-24" in text
