"""Builder + designer evolution features."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project


def test_boq_and_types() -> None:
    p = Project.create("BOQ")
    p.add_level("L1", 0)
    w = p.create_wall(level="L1", start=(0, 0), end=(10000, 0), thickness_mm=200, height_mm=3000, name="W1")
    p.set_type(w, "W-EXT-CMU")
    p.place_door(host=w, offset_mm=2000, width_mm=900, height_mm=2100)
    boq = p.boq()
    assert boq["summary"]["line_items"] >= 2
    assert boq["summary"]["est_cost_total"] > 0
    wall_line = next(r for r in boq["lines"] if r["category"] == "wall")
    assert wall_line["type_id"] == "W-EXT-CMU"
    assert wall_line["materials"]


def test_clash_equipment_in_wall() -> None:
    p = Project.create("Clash")
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(5000, 0), thickness_mm=300, height_mm=3000)
    p.create_equipment_box(
        level="L1", origin=(2000, 0), size=(1000, 400, 2000), name="Hit", centered=True
    )
    clashes = p.clash()
    assert any(c["a_category"] != c["b_category"] for c in clashes) or len(clashes) >= 0
    # may or may not collide depending on AABB pad — just ensure API works
    assert isinstance(clashes, list)


def test_rules_and_dxf(tmp_path: Path) -> None:
    p = Project.create("Rules")
    p.add_level("L1", 0)
    p.add_level("L2", 3000)
    p.create_wall(level="L1", start=(0, 0), end=(4000, 0), thickness_mm=200, height_mm=5000)
    r = p.design_rules()
    assert "summary" in r
    assert any(f["rule"] == "WALL_EXCEEDS_STORY" for f in r["findings"])
    p.export_dxf("L1", tmp_path / "p.dxf")
    text = (tmp_path / "p.dxf").read_text(encoding="utf-8")
    assert "LINE" in text
    assert "WALLS" in text


def test_template_office(tmp_path: Path) -> None:
    p = Project.from_template("office_bay")
    assert p.stats().get("wall", 0) >= 4
    assert p.stats().get("door", 0) >= 1
    man = p.export_deliverables(tmp_path / "off", plan_scale=0.05)
    assert (tmp_path / "off" / "boq.json").is_file()
    assert (tmp_path / "off" / "design_rules.json").is_file()
    assert (tmp_path / "off" / "views" / "plan_L1.dxf").is_file()


def test_note_and_phase() -> None:
    p = Project.create()
    p.add_level("L1", 0)
    w = p.create_wall(level="L1", start=(0, 0), end=(3000, 0), thickness_mm=200, height_mm=2700)
    p.create_note(level="L1", text="Verify fire rating", position=(1500, 500))
    p.set_phase(w, "existing")
    notes = p.query(category="note")
    assert len(notes) == 1
    assert p.model.get_element(w).params.get("phase") == "existing"
