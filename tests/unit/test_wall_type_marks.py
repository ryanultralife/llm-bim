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
        fire_rating="2-hr",
    )
    assert wid
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    text = plan.read_text(encoding="utf-8")
    assert 'class="wall-types"' in text
    assert "EXT-CMU" in text
    assert "2HR" in text


def test_wall_type_and_fire_on_plan_dxf(tmp_path: Path):
    from llmbim_drawings.dxf_export import export_plan_dxf

    p = Project.create("wall-dxf", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(
        level="L1",
        start=(0, 0),
        end=(8000, 0),
        thickness_mm=200,
        height_mm=3000,
        type_id="W-EXT-CMU",
        fire_rating="2-hr",
    )
    dxf = tmp_path / "p.dxf"
    export_plan_dxf(p.model, "L1", dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "WALL-TYPES" in text
    assert "EXT-CMU" in text
    assert "2HR" in text


def test_plan_dxf_doors_and_windows(tmp_path: Path):
    from llmbim_drawings.dxf_export import export_plan_dxf

    p = Project.create("open-dxf", vcs=False)
    p.add_level("L1", 0)
    w = p.create_wall(
        level="L1", start=(0, 0), end=(10000, 0), thickness_mm=200, height_mm=3000
    )
    p.place_door(
        host=w,
        offset_mm=1000,
        width_mm=900,
        height_mm=2100,
        type_id="D-HM-36",
        fire_rating="90 min",
    )
    p.place_window(
        host=w,
        offset_mm=4000,
        width_mm=600,
        height_mm=600,
        sill_mm=900,
        type_id="WIN-VIEW-24x24",
    )
    dxf = tmp_path / "p.dxf"
    export_plan_dxf(p.model, "L1", dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "DOORS" in text
    assert "WINDOWS" in text
    assert "D1" in text
    assert "HM-36" in text or "D-HM" in text
    assert "90m" in text or "90" in text
    assert "W1" in text


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


def test_zone_area_schedule_with_volume(tmp_path: Path):
    from llmbim_drawings.schedules import export_schedule_csv, schedule_rows

    p = Project.create("zones", vcs=False)
    p.add_level("L1", 0)
    p.create_room(
        level="L1",
        name="Office A",
        boundary=[(0, 0), (5000, 0), (5000, 4000), (0, 4000)],
        height_mm=2700,
    )
    rows = schedule_rows(p.model, "zone")
    assert rows
    assert rows[0]["name"] == "Office A"
    assert rows[0]["level"] == "L1"
    assert abs(float(rows[0]["area_m2"]) - 20.0) < 0.01  # 5m x 4m
    assert rows[0]["height_mm"] == 2700
    assert abs(float(rows[0]["volume_m3"]) - 54.0) < 0.1  # 20 * 2.7
    export_schedule_csv(p.model, "zone", tmp_path / "zone_areas.csv")
    text = (tmp_path / "zone_areas.csv").read_text(encoding="utf-8")
    assert "volume_m3" in text
    assert "Office A" in text
