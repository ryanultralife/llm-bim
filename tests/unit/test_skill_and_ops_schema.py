"""Skill pack + ops schema export."""

from __future__ import annotations

from pathlib import Path

from llmbim_core.registry import list_ops, ops_schema, write_ops_schema


def test_ops_schema_has_tools() -> None:
    s = ops_schema()
    assert "tools" in s
    names = {t["name"] for t in s["tools"]}
    assert "stats" in names
    assert "create_generic" in names
    assert "export_pack" in names
    assert "project.export_deliverables" in names


def test_write_schema(tmp_path: Path) -> None:
    out = tmp_path / "ops.schema.json"
    write_ops_schema(str(out))
    assert out.is_file()
    assert out.stat().st_size > 100


def test_skill_files_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    assert (root / "skills" / "llm-bim" / "SKILL.md").is_file()
    assert (root / "docs" / "LOCAL.md").is_file()
    assert (root / "skills" / "llm-bim" / "recipes" / "office.md").is_file()
    batch = (root / "skills" / "llm-bim" / "recipes" / "batch_ops.md").read_text(
        encoding="utf-8"
    )
    assert "place_door" in batch
    assert "create_wall" in batch
    skill = (root / "skills" / "llm-bim" / "SKILL.md").read_text(encoding="utf-8")
    assert "fire_rating=90_min" in skill


def test_assembly_op() -> None:
    from llmbim import Project

    p = Project.create()
    p.add_level("L1", 0)
    w = p.create_wall(level="L1", start=(0, 0), end=(1000, 0), thickness_mm=200, height_mm=3000)
    aid = p.create_assembly("North walls", [w])
    assert aid.startswith("asm_")
    assert len(p.assemblies()) == 1


def test_design_option_clone() -> None:
    from llmbim import Project

    p = Project.create()
    p.add_level("L1", 0)
    w = p.create_wall(level="L1", start=(0, 0), end=(2000, 0), thickness_mm=200, height_mm=3000)
    r = p.design_option("Option B", [w], clone=True)
    assert r["count"] == 1
    assert p.stats().get("wall") == 2


def test_registry_create_wall_place_door_window() -> None:
    """create_wall / place_door / place_window registered for project_op / bulk."""
    from llmbim import Project
    from llmbim_core.registry import dispatch, list_ops

    names = {o["name"] for o in list_ops()}
    assert "create_wall" in names
    assert "place_door" in names
    assert "place_window" in names

    p = Project.create("reg-open", vcs=False)
    p.add_level("L1", 0)
    wr = dispatch(
        p.model,
        "create_wall",
        {
            "level": "L1",
            "start": [0, 0],
            "end": [8000, 0],
            "thickness_mm": 200,
            "height_mm": 3000,
            "fire_rating": "2-hr",
            "type_id": "W-2HR",
        },
    )
    host = wr["element_id"]
    assert wr.get("fire_rating") == "2-hr"
    dr = dispatch(
        p.model,
        "place_door",
        {
            "host": host,
            "offset_mm": 2000,
            "width_mm": 900,
            "height_mm": 2100,
            "type_id": "D-HM-36",
            "fire_rating": "90 min",
        },
    )
    assert dr["category"] == "door"
    assert dr.get("fire_rating") == "90 min"
    win = dispatch(
        p.model,
        "place_window",
        {
            "host": host,
            "offset_mm": 5000,
            "width_mm": 1200,
            "height_mm": 900,
            "sill_mm": 900,
            "type_id": "WIN-VIEW",
        },
    )
    assert win["category"] == "window"
    assert p.stats().get("door") == 1
    assert p.stats().get("window") == 1

    room = dispatch(
        p.model,
        "create_room",
        {
            "level": "L1",
            "name": "Office",
            "boundary": [[0, 0], [4000, 0], [4000, 3000], [0, 3000]],
            "height_mm": 2700,
        },
    )
    assert room.get("element_id") or room.get("category") == "room" or "Office" in str(room)
    assert p.stats().get("room") == 1
