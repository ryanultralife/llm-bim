"""Door/wall fire_rating on place + schedules."""

from __future__ import annotations

from llmbim import Project
from llmbim_drawings.schedules import schedule_rows


def test_place_door_fire_rating_schedule():
    p = Project.create("door-fr", vcs=False)
    p.add_level("L1", 0)
    wid = p.create_wall(
        level="L1",
        start=(0, 0),
        end=(6000, 0),
        thickness_mm=200,
        height_mm=3000,
        fire_rating="2-hr",
    )
    assert p.model.get_element(wid).params.get("fire_rating") == "2-hr"
    walls = schedule_rows(p.model, "wall")
    assert any(r.get("fire_rating") == "2-hr" for r in walls)

    did = p.place_door(
        host=wid,
        offset_mm=1000,
        width_mm=900,
        height_mm=2100,
        name="D1",
        fire_rating="90 min",
        type_id="D-HM-36",
    )
    el = p.model.get_element(did)
    assert el.params.get("fire_rating") == "90 min"
    rows = schedule_rows(p.model, "door")
    assert any(r.get("fire_rating") == "90 min" for r in rows)
    assert any(r.get("type_id") == "D-HM-36" for r in rows)
