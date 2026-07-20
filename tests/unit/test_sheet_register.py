"""Configurable sheet register (WP-SCHAD-S5): custom sheets=[] replaces the default set."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from llmbim import Project
from llmbim_core.errors import ValidationError
from llmbim_drawings.construction import export_construction_set
from llmbim_drawings.deliverables import verify_pack
from llmbim_drawings.view import DrawingView

DETAIL = {
    "id": "D01",
    "title": "TYPICAL WALL SECTION",
    "scale": 16,
    "ops": [
        ("l", 0.0, 0.0, 4.0, 0.0),
        ("r", 0.0, 0.0, 0.54, 10.0),
        ("h", -0.75, -1.9, 1.5, 1.0),
        ("c", 0.27, -1.6, 0.03),
        ("dim", 0.0, 0.0, 4.0, 0.0, 0.8),
        ("t", 1.0, 5.0, 0.5, "2x6 DF-L @ 16 OC W/ R-21 BATTS"),
    ],
}

REGISTER = [
    {"no": "A0.1", "title": "COVER SHEET & SITE SUMMARY", "kind": "cover"},
    {"no": "A1.1", "title": "FLOOR PLAN", "kind": "plan", "level": "L1"},
    {
        "no": "A2.1",
        "title": "EXTERIOR ELEVATIONS - SOUTH & NORTH",
        "kind": "elevations",
        "pair": ["S", "N"],
    },
    {"no": "S3.1", "title": "STRUCTURAL DETAILS", "kind": "details", "details": [DETAIL]},
    {
        "no": "A4.1",
        "title": "DOOR & WINDOW SCHEDULES",
        "kind": "schedule",
        "schedule": ["door", "window"],
    },
]

EXPECTED_FILES = {
    "A0-1_cover.svg",
    "A1-1_plan.svg",
    "A2-1_elevations.svg",
    "S3-1_details.svg",
    "A4-1_schedule.svg",
}

# default register baseline (mirrors test_drawing_sets.PERMIT_SHEETS)
DEFAULT_PERMIT = {"G-001", "A-101", "A-201", "A-202", "A-301", "A-601", "A-602", "A-603"}


def _project(name: str = "SchadLike") -> Project:
    p = Project.create(name, vcs=False)
    p.add_level("L1", 0)
    walls = p.create_rect_shell(
        level="L1", x=0, y=0, w=12000, d=9000, height_mm=3000, thickness_mm=150, name_prefix="B"
    )
    p.place_door(host=walls[0], offset_mm=2000, width_mm=915, height_mm=2100, name="D1")
    p.place_window(host=walls[1], offset_mm=1500, width_mm=1200, height_mm=1200, sill_mm=900)
    p.create_room(
        level="L1", name="Garage", boundary=[(0, 0), (12000, 0), (12000, 9000), (0, 9000)]
    )
    return p


def test_custom_register_emits_exactly_declared_sheets(tmp_path: Path) -> None:
    p = _project()
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02, sheets=REGISTER)
    assert man["register"] == "custom"
    assert {f.name for f in tmp_path.glob("*.svg")} == EXPECTED_FILES
    assert [s["no"] for s in man["sheets"]] == ["A0.1", "A1.1", "A2.1", "S3.1", "A4.1"]
    titles = {s["no"]: s["title"] for s in man["sheets"]}
    assert titles["A0.1"] == "COVER SHEET & SITE SUMMARY"
    assert titles["S3.1"] == "STRUCTURAL DETAILS"
    # disciplines derive from the alpha prefix of the sheet no
    assert {s["discipline"] for s in man["sheets"]} == {"A", "S"}
    # SHEET_INDEX.json carries the custom register
    idx = json.loads((tmp_path / "SHEET_INDEX.json").read_text(encoding="utf-8"))
    assert idx["register"] == "custom"
    assert [s["no"] for s in idx["sheets"]] == [s["no"] for s in man["sheets"]]
    assert [s["title"] for s in idx["sheets"]] == [s["title"] for s in man["sheets"]]


def test_custom_cover_indexes_custom_register(tmp_path: Path) -> None:
    p = _project()
    export_construction_set(p.model, tmp_path, plan_scale=0.02, sheets=REGISTER)
    cover = (tmp_path / "A0-1_cover.svg").read_text(encoding="utf-8")
    for no in ("A0.1", "A1.1", "A2.1", "S3.1", "A4.1"):
        assert no in cover
    assert "FLOOR PLAN" in cover and "STRUCTURAL DETAILS" in cover
    assert "A0.1" in cover  # big sheet-number box uses the unsanitized no
    # elevations sheet carries the requested pair
    elev = (tmp_path / "A2-1_elevations.svg").read_text(encoding="utf-8")
    assert "SOUTH ELEVATION" in elev and "NORTH ELEVATION" in elev
    assert "EAST ELEVATION" not in elev
    # details sheet renders the ops DSL (detail label + hatch + dim text)
    det = (tmp_path / "S3-1_details.svg").read_text(encoding="utf-8")
    assert "D01" in det
    assert 'class="hatch"' in det
    assert "4'-0\"" in det


def test_more_kinds_sections_doc_custom_svg(tmp_path: Path) -> None:
    p = _project("KindsProj")
    register = [
        {"no": "A3.1", "title": "BUILDING SECTIONS", "kind": "sections"},
        {
            "no": "H2.1",
            "title": "HOUSE REMODEL - SCOPE",
            "kind": "doc",
            "text": "# Scope\n\n- remodel kitchen\n- new roof\n\n## Criteria\nSnow load 75 psf.",
        },
        {
            "no": "C1.1",
            "title": "SITE PLAN",
            "kind": "custom_svg",
            "provider": lambda: DrawingView(width=200, height=100, body='<rect width="200" height="100" fill="none" stroke="#111"/>'),
        },
    ]
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02, sheets=register)
    assert {f.name for f in tmp_path.glob("*.svg")} == {
        "A3-1_sections.svg",
        "H2-1_doc.svg",
        "C1-1_custom.svg",
    }
    doc = (tmp_path / "H2-1_doc.svg").read_text(encoding="utf-8")
    assert "Scope" in doc and "remodel kitchen" in doc
    sec = (tmp_path / "A3-1_sections.svg").read_text(encoding="utf-8")
    assert "SECTION A-A" in sec and "SECTION B-B" in sec
    assert {s["discipline"] for s in man["sheets"]} == {"A", "H", "C"}


def test_register_validation_errors(tmp_path: Path) -> None:
    p = _project("BadReg")
    with pytest.raises(ValidationError) as ei:
        export_construction_set(
            p.model, tmp_path, sheets=[{"no": "X1", "title": "X", "kind": "nope"}]
        )
    assert "cover" in str(ei.value) and "details" in str(ei.value)
    with pytest.raises(ValidationError):
        export_construction_set(p.model, tmp_path, sheets=[{"title": "no number", "kind": "doc"}])
    with pytest.raises(ValidationError):
        export_construction_set(
            p.model, tmp_path,
            sheets=[{"no": "S3.1", "title": "DETAILS", "kind": "details"}],  # missing specs
        )


def test_default_register_unchanged_when_sheets_none(tmp_path: Path) -> None:
    p = _project("DefaultReg")
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02, set_type="plan")
    assert "register" not in man
    assert {s["no"] for s in man["sheets"]} == DEFAULT_PERMIT
    assert (tmp_path / "G-001_cover.svg").is_file()
    assert (tmp_path / "A-101_plan.svg").is_file()
    # re-export over a previous CUSTOM register drops the stale custom sheets
    export_construction_set(p.model, tmp_path, plan_scale=0.02, sheets=REGISTER)
    export_construction_set(p.model, tmp_path, plan_scale=0.02, set_type="plan")
    assert not (tmp_path / "A0-1_cover.svg").exists()
    assert {f.name for f in tmp_path.glob("*.svg")} == {
        f"{no}_{slug}.svg"
        for no, slug in (
            ("G-001", "cover"), ("A-101", "plan"), ("A-201", "elevations"),
            ("A-202", "elevations"), ("A-301", "sections"), ("A-601", "rooms"),
            ("A-602", "doors"), ("A-603", "windows"),
        )
    }


def test_verify_pack_counts_alpha_prefix_disciplines(tmp_path: Path) -> None:
    p = _project("VerifyDisc")
    cons = tmp_path / "construction"
    export_construction_set(p.model, cons, plan_scale=0.02, sheets=REGISTER)
    res = verify_pack(tmp_path)
    disc = res["sheet_count_by_discipline"]
    # A0-1 / A1-1 / A2-1 / A4-1 → "A"; S3-1 → "S" (alpha prefix, not "A0"/"S3")
    assert disc == {"A": 4, "S": 1}
    # default register keys stay plain letters
    export_construction_set(p.model, cons, plan_scale=0.02, set_type="plan")
    res2 = verify_pack(tmp_path)
    assert set(res2["sheet_count_by_discipline"]) == {"G", "A"}
