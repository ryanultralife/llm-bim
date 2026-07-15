"""WP-DRAWINGS acceptance tests — excluded from default pytest.

Claude: pytest -m wp_drawings
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmbim import Project

pytestmark = pytest.mark.wp_drawings


def _sample_project() -> Project:
    p = Project.create("Draw House")
    p.add_level("L1", 0)
    footprint = [(0, 0), (10000, 0), (10000, 8000), (0, 8000)]
    p.create_slab(level="L1", polygon=footprint, thickness_mm=200)
    south = p.create_wall(
        level="L1", start=(0, 0), end=(10000, 0), thickness_mm=200, height_mm=3000
    )
    p.create_wall(level="L1", start=(10000, 0), end=(10000, 8000), thickness_mm=200, height_mm=3000)
    p.create_wall(level="L1", start=(10000, 8000), end=(0, 8000), thickness_mm=200, height_mm=3000)
    p.create_wall(level="L1", start=(0, 8000), end=(0, 0), thickness_mm=200, height_mm=3000)
    p.place_door(host=south, offset_mm=2000, width_mm=900, height_mm=2100)
    p.create_room(level="L1", name="Living", boundary=footprint)
    return p


def test_plan_svg_written(tmp_path: Path) -> None:
    from llmbim_drawings import export_plan_svg

    p = _sample_project()
    out = tmp_path / "L1_plan.svg"
    export_plan_svg(p.model, "L1", out)
    text = out.read_text(encoding="utf-8")
    assert out.stat().st_size > 200
    assert "<svg" in text.lower()
    # Should reflect wall geometry somehow (path/line/polyline/rect)
    assert any(tag in text.lower() for tag in ("<path", "<line", "<polyline", "<rect", "<polygon"))


def test_section_svg_written(tmp_path: Path) -> None:
    from llmbim_drawings import export_section_svg

    p = _sample_project()
    out = tmp_path / "section.svg"
    export_section_svg(p.model, (5000, -1000), (5000, 9000), out)
    text = out.read_text(encoding="utf-8")
    assert out.stat().st_size > 100
    assert "<svg" in text.lower()


def test_elevation_svg_written(tmp_path: Path) -> None:
    from llmbim_drawings import export_elevation_svg

    p = _sample_project()
    out = tmp_path / "elev_s.svg"
    export_elevation_svg(p.model, "S", out)
    text = out.read_text(encoding="utf-8")
    assert out.stat().st_size > 100
    assert "<svg" in text.lower()
