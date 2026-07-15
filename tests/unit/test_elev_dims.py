"""Elevation storey height dimensions + level labels."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.section import write_elevation_svg


def test_elevation_has_level_dims(tmp_path: Path):
    p = Project.create("elev-dim", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 3500)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3500)
    elev = tmp_path / "e.svg"
    write_elevation_svg(p.model, "S", elev, scale=0.02)
    text = elev.read_text(encoding="utf-8")
    assert 'class="level-dims"' in text
    assert "L1" in text and "L2" in text
    assert "storey-height" in text
    assert "3.50 m" in text


def test_section_has_level_dims(tmp_path: Path):
    from llmbim_drawings.section import write_section_svg

    p = Project.create("sec-dim", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 4000)
    p.create_wall(level="L1", start=(0, 0), end=(10000, 0), thickness_mm=200, height_mm=4000)
    sec = tmp_path / "s.svg"
    write_section_svg(p.model, (5000, -1000), (5000, 1000), sec, scale=0.02)
    text = sec.read_text(encoding="utf-8")
    assert 'class="level-dims"' in text
    assert "L1" in text and "L2" in text
    assert "storey-height" in text
    assert "4.00 m" in text
