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
