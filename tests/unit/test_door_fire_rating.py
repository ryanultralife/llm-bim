"""Door/wall fire_rating on place + schedules + plan tags."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.html_index import write_pack_index
from llmbim_drawings.plan import write_plan_svg
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
        type_id="W-EXT-CMU",
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


def test_plan_shows_wall_and_door_fire_rating(tmp_path: Path):
    p = Project.create("fr-plan", vcs=False)
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
    p.place_door(
        host=wid,
        offset_mm=1000,
        width_mm=900,
        height_mm=2100,
        type_id="D-HM-36",
        fire_rating="90 min",
    )
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    text = plan.read_text(encoding="utf-8")
    assert "2HR" in text or "2-hr" in text or "2HR" in text.upper() or "2HR" in text.replace("-", "")
    # wall type + fire compressed to EXT-CMU 2HR
    assert "EXT-CMU" in text
    assert "90m" in text or "90 min" in text or "90m" in text.replace(" ", "")


def test_html_index_door_schedule_sample(tmp_path: Path):
    pack = tmp_path / "pack"
    (pack / "schedules").mkdir(parents=True)
    (pack / "schedules" / "doors.csv").write_text(
        "name,type_id,fire_rating,width_mm,height_mm,locator\n"
        "Entry,D-HM-36,90 min,900,2100,L1|X2000|Y0|Z0\n",
        encoding="utf-8",
    )
    write_pack_index(pack)
    text = (pack / "index.html").read_text(encoding="utf-8")
    assert "Door schedule" in text
    assert "D-HM-36" in text
    assert "90 min" in text


def test_html_index_design_rules_sample(tmp_path: Path):
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "design_rules.json").write_text(
        __import__("json").dumps(
            {
                "summary": {"error": 0, "warning": 1, "info": 1, "total": 2},
                "findings": [
                    {
                        "rule": "COLUMN_IN_WALL",
                        "severity": "warning",
                        "domain": "structure",
                        "message": "Column intersects wall",
                    },
                    {
                        "rule": "BEAM_LOW_CLEARANCE",
                        "severity": "info",
                        "domain": "structure",
                        "message": "Beam low headroom",
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (pack / "MANIFEST.json").write_text(
        '{"project": "t", "ok": true, "verification": {"ok": true}}\n',
        encoding="utf-8",
    )
    write_pack_index(pack)
    html = (pack / "index.html").read_text(encoding="utf-8")
    assert "Design rules" in html
    assert "COLUMN_IN_WALL" in html
    assert "structure" in html
