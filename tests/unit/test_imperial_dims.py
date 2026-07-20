"""Imperial dimensioning + door/window tags (WP-SCHAD-S7).

``units="imperial"`` renders dimension strings as feet-inches to the nearest
1/2" (1 ft = 304.8 mm) across plan / section / elevation, and ``tags=True``
draws marked door (hexagon) / window (diamond) tag bubbles on plans. The
metric default stays byte-compatible with prior output.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from llmbim import Project
from llmbim_core.errors import ValidationError
from llmbim_drawings.construction import export_construction_set
from llmbim_drawings.detail_ops import format_mm_feet_inches, imperial_scale_note
from llmbim_drawings.plan import render_plan_view
from llmbim_drawings.section import render_elevation_svg, render_section_svg

# 40' x 30' shell, 10' walls — clean imperial numbers (1 ft = 304.8 mm)
W_MM, D_MM, H_MM = 12192.0, 9144.0, 3048.0


def _project(name: str = "SierraStar") -> Project:
    p = Project.create(name, vcs=False)
    p.add_level("L1", 0)
    walls = p.create_rect_shell(
        level="L1", x=0, y=0, w=W_MM, d=D_MM,
        height_mm=H_MM, thickness_mm=150, name_prefix="B",
    )
    p.place_door(host=walls[0], offset_mm=2000, width_mm=915, height_mm=2100, name="D1")
    p.place_window(
        host=walls[1], offset_mm=1500, width_mm=1200, height_mm=1200, sill_mm=900, name="W2"
    )
    p.create_room(
        level="L1", name="Garage", boundary=[(0, 0), (W_MM, 0), (W_MM, D_MM), (0, D_MM)]
    )
    return p


def test_format_mm_feet_inches_exact_strings() -> None:
    assert format_mm_feet_inches(7315.2) == "24'-0\""
    assert format_mm_feet_inches(1066.8) == "3'-6\""
    assert format_mm_feet_inches(12192.0) == "40'-0\""
    # fractional inches round to the nearest 1/2"
    assert format_mm_feet_inches(1231.9) == "4'-0 1/2\""  # 48.5 in
    assert format_mm_feet_inches(0.0) == "0'-0\""
    assert format_mm_feet_inches(-304.8) == "-1'-0\""


def test_imperial_scale_note_clean_ratios_only() -> None:
    assert imperial_scale_note(48) == "1/4\" = 1'-0\""
    assert imperial_scale_note(96) == "1/8\" = 1'-0\""
    assert imperial_scale_note(16) == "3/4\" = 1'-0\""
    # metric ratios have no clean architectural equivalent
    assert imperial_scale_note(50) is None
    assert imperial_scale_note(100) is None
    assert imperial_scale_note(0) is None


def test_metric_default_unchanged() -> None:
    p = _project()
    body = render_plan_view(p.model, "L1", scale=0.02).body
    assert "12.19 m" in body  # 12192 mm wall dim, metric snapshot
    assert "'-" not in body  # no feet-inches text anywhere


def test_plan_imperial_dim_text() -> None:
    p = _project()
    body = render_plan_view(p.model, "L1", scale=0.02, units="imperial").body
    assert "40'-0\"" in body
    assert "30'-0\"" in body
    assert "12.19 m" not in body


def test_plan_imperial_room_tag_area_sf() -> None:
    p = _project()
    body = render_plan_view(
        p.model, "L1", scale=0.02, units="imperial", room_tags=True
    ).body
    assert "1200 SF" in body  # 40' x 30' garage
    assert "m²" not in body


def test_plan_tags_render_door_and_window_marks() -> None:
    p = _project()
    # explicit mark param wins over the element name
    door = next(el for el in p.model.elements if el.category == "door")
    door.params["mark"] = "D101"
    body = render_plan_view(p.model, "L1", scale=0.02, tags=True).body
    assert 'class="door-tag"' in body  # hexagon bubble
    assert 'class="window-tag"' in body  # diamond bubble
    assert ">D101</text>" in body
    assert ">W2</text>" in body  # window falls back to its name


def test_plan_tags_fallback_to_short_id() -> None:
    p = _project()
    window = next(el for el in p.model.elements if el.category == "window")
    window.name = ""
    body = render_plan_view(p.model, "L1", scale=0.02, tags=True).body
    assert f">{window.id[:6]}</text>" in body


def test_section_datum_and_storey_imperial() -> None:
    p = _project()
    cut = ((W_MM / 2, -2000.0), (W_MM / 2, D_MM + 2000.0))
    svg = render_section_svg(p.model, *cut, scale=0.02, units="imperial")
    assert "EL. +0'-0\"" in svg  # L1 datum label
    assert "10'-0\"" in svg  # 3048 mm storey height dim
    assert "0.000 m" not in svg
    # metric default unchanged
    svg_m = render_section_svg(p.model, *cut, scale=0.02)
    assert "EL. +0.000 m" in svg_m


def test_elevation_datum_imperial() -> None:
    p = _project()
    svg = render_elevation_svg(p.model, "S", scale=0.02, units="imperial")
    assert "EL. +0'-0\"" in svg
    assert "10'-0\"" in svg
    assert "0.000 m" not in svg


def test_units_validation() -> None:
    p = _project()
    with pytest.raises(ValidationError):
        render_plan_view(p.model, "L1", units="furlongs")
    with pytest.raises(ValidationError):
        render_section_svg(p.model, (0, 0), (0, D_MM), units="feet")
    with pytest.raises(ValidationError):
        export_construction_set(p.model, Path("."), units="nope")


def test_custom_register_per_sheet_units(tmp_path: Path) -> None:
    p = _project()
    register = [
        {
            "no": "A1.1",
            "title": "FLOOR PLAN",
            "kind": "plan",
            "level": "L1",
            "units": "imperial",
            "tags": True,
        },
        {"no": "A1.2", "title": "FLOOR PLAN (SI)", "kind": "plan", "level": "L1"},
    ]
    export_construction_set(p.model, tmp_path, plan_scale=0.02, sheets=register)
    imp = (tmp_path / "A1-1_plan.svg").read_text(encoding="utf-8")
    assert "40'-0&quot;" in imp or "40'-0\"" in imp
    assert 'class="door-tag"' in imp
    # sibling sheet without a units opt stays on the export default (metric)
    met = (tmp_path / "A1-2_plan.svg").read_text(encoding="utf-8")
    assert "12.19 m" in met
    assert "40'-0" not in met


def test_export_level_units_default_propagates(tmp_path: Path) -> None:
    p = _project()
    register = [
        {"no": "A1.1", "title": "FLOOR PLAN", "kind": "plan", "level": "L1"},
        {"no": "A3.1", "title": "BUILDING SECTIONS", "kind": "sections"},
    ]
    export_construction_set(
        p.model, tmp_path, plan_scale=0.02, units="imperial", sheets=register
    )
    plan = (tmp_path / "A1-1_plan.svg").read_text(encoding="utf-8")
    assert "40'-0\"" in plan
    sec = (tmp_path / "A3-1_sections.svg").read_text(encoding="utf-8")
    assert "EL. +0'-0\"" in sec


def test_default_register_imperial_and_scale_note(tmp_path: Path) -> None:
    p = _project()
    export_construction_set(
        p.model, tmp_path, plan_scale=1 / 48, set_type="plan", units="imperial"
    )
    plan = (tmp_path / "A-101_plan.svg").read_text(encoding="utf-8")
    assert "40'-0\"" in plan
    # 1:48 maps cleanly to the architectural quarter-inch scale note
    assert "1/4\" = 1'-0\"" in plan
    elev = (tmp_path / "A-201_elevations.svg").read_text(encoding="utf-8")
    assert "EL. +0'-0\"" in elev
    # unclean metric ratio keeps the numeric note
    export_construction_set(p.model, tmp_path, plan_scale=0.02, set_type="plan")
    plan_m = (tmp_path / "A-101_plan.svg").read_text(encoding="utf-8")
    assert "1:50" in plan_m
