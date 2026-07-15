"""End-to-end: chat agent path writes packs under output/."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_core.paths import project_output_dir, slugify


def test_default_export_to_output(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLMBIM_OUTPUT_DIR", str(tmp_path / "output"))
    # re-import paths would need env at call time — project_output_dir reads env each call
    p = Project.create("Agent Demo Building")
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=5000, d=4000, height_mm=3000, thickness_mm=200, name_prefix="B"
    )
    man = p.export_deliverables()
    out = Path(man["output_dir"])
    assert out.is_dir()
    assert "output" in str(out).replace("\\", "/")
    assert (out / "model.ifc").is_file()
    assert (out / "index.html").is_file()
    assert man.get("ok") is True


def test_slugify() -> None:
    assert slugify("My Building!") == "my_building"
    assert project_output_dir("x", create=False).name == "x"
