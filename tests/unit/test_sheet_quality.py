"""Drafting-quality sheets: frame, multi-view layout, plan detail, tables."""

from __future__ import annotations

import pytest
from llmbim import Project
from llmbim_drawings.construction import export_construction_set
from llmbim_drawings.layout import compose_sheet, table_view
from llmbim_drawings.schedules import schedule_rows
from llmbim_drawings.sheets import title_block_svg
from llmbim_drawings.view import DrawingView


def _facility() -> Project:
    """Two-level multi-trade facility with grids and 30 rooms (forces A-601 pagination)."""
    p = Project.create("Sheet Quality Facility", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 3600)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=12000, d=9000, height_mm=3600, thickness_mm=200, name_prefix="A"
    )
    p.create_rect_shell(
        level="L2", x=0, y=0, w=12000, d=9000, height_mm=3600, thickness_mm=200, name_prefix="B"
    )
    p.add_grid("U", [0, 6000, 12000])
    p.add_grid("V", [0, 4500, 9000])
    wall_id = next(el.id for el in p.model.elements if el.category == "wall")
    p.place_door(host=wall_id, offset_mm=2000, width_mm=900, height_mm=2100, name="Entry")
    p.place_window(host=wall_id, offset_mm=5000, width_mm=1200, height_mm=900, sill_mm=900)
    for i in range(30):
        x = (i % 6) * 2000.0
        y = (i // 6) * 1500.0
        p.create_room(
            level="L1",
            name=f"R{i + 1:02d}",
            boundary=[(x, y), (x + 2000, y), (x + 2000, y + 1500), (x, y + 1500)],
        )
    p.place_column(level="L1", origin=(3000, 3000))
    p.place_pipe(level="L1", nps="3/4", start=(1000, 1000), end=(6000, 1000))
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(6000, 1000))
    p.place_duct(level="L1", start=(1000, 5000), end=(8000, 5000))
    p.place_conduit(level="L1", start=(1000, 7000), end=(9000, 7000))
    p.place_cable_tray(level="L1", start=(1000, 8000), end=(9000, 8000))
    return p


@pytest.fixture(scope="module")
def pack(tmp_path_factory: pytest.TempPathFactory):
    p = _facility()
    out = tmp_path_factory.mktemp("sheets")
    man = export_construction_set(p.model, out, plan_scale=0.02, date="2026-07-20")
    return p, out, man


# ── 1. professional sheet frame ─────────────────────────────────────────────


def test_title_block_frame_elements() -> None:
    svg = title_block_svg(
        project="Proj",
        sheet_title="Some Title",
        sheet_no="A-000",
        body="<rect/>",
        date="2026-07-20",
        px_per_mm=0.02,
        north_arrow=True,
    )
    # zone referencing: letters across top/bottom, numbers down the sides
    assert 'class="zone-ticks"' in svg
    assert svg.count(">A</text>") >= 2 and svg.count(">B</text>") >= 2  # top + bottom
    assert svg.count(">1</text>") >= 2 and svg.count(">2</text>") >= 2  # both sides
    # right-side title column with stacked blocks
    assert 'class="title-column"' in svg
    assert "PROJECT" in svg and "TITLE" in svg and "SHEET NO" in svg
    assert "SCALE" in svg and "DATE" in svg and "2026-07-20" in svg
    assert "DRAWN" in svg and "LLM-BIM agent" in svg
    assert "CHECKED" in svg and "APPROVED" in svg
    # revision table with row 0 = ISSUED FOR REVIEW
    assert 'class="rev-table"' in svg
    assert "REVISIONS" in svg
    assert "ISSUED FOR REVIEW" in svg
    # honesty stamp
    assert 'class="honesty-stamp"' in svg
    assert "ENGINEERING ESTIMATE" in svg
    assert "NOT FOR CONSTRUCTION" in svg
    # graphic scale bar + north arrow
    assert 'class="scale-bar"' in svg
    assert 'class="north-arrow"' in svg


def test_plan_sheet_carries_frame_and_north_arrow(pack) -> None:
    _p, out, _man = pack
    svg = (out / "A-101_plan.svg").read_text(encoding="utf-8")
    assert 'class="zone-ticks"' in svg
    assert 'class="title-column"' in svg
    assert 'class="rev-table"' in svg
    assert "ENGINEERING ESTIMATE" in svg
    assert 'class="scale-bar"' in svg
    assert 'class="north-arrow"' in svg
    assert "2026-07-20" in svg  # caller-passed issue date


# ── 2. multi-view layout ────────────────────────────────────────────────────


def test_a201_two_elevations_one_sheet(pack) -> None:
    _p, out, man = pack
    nos = {s["no"] for s in man["sheets"]}
    assert "A-201" in nos and "A-202" in nos
    assert "A-203" not in nos and "A-204" not in nos  # renumbered pairs
    svg = (out / "A-201_elevations.svg").read_text(encoding="utf-8")
    assert svg.count('class="view-label"') == 2
    assert "NORTH ELEVATION" in svg and "SOUTH ELEVATION" in svg
    svg2 = (out / "A-202_elevations.svg").read_text(encoding="utf-8")
    assert svg2.count('class="view-label"') == 2
    assert "EAST ELEVATION" in svg2 and "WEST ELEVATION" in svg2


def test_a301_two_sections_one_sheet(pack) -> None:
    _p, out, man = pack
    svg = (out / "A-301_sections.svg").read_text(encoding="utf-8")
    assert svg.count('class="view-label"') == 2
    assert "SECTION A-A" in svg and "SECTION B-B" in svg
    titles = {s["no"]: s["title"] for s in man["sheets"]}
    assert titles["A-301"] == "Building Sections"


def test_discipline_sheet_has_legend_cell(pack) -> None:
    _p, out, _man = pack
    s_svg = (out / "S-101_structural.svg").read_text(encoding="utf-8")
    assert 'class="legend"' in s_svg
    assert "SYSTEMS" in s_svg
    assert "Columns" in s_svg and "×" in s_svg  # swatch label + count
    p_svg = (out / "P-101_piping.svg").read_text(encoding="utf-8")
    assert 'class="legend"' in p_svg
    assert "Pipe —" in p_svg and "Fittings" in p_svg


def test_compose_sheet_grid_of_four() -> None:
    cells = [
        (DrawingView(width=100, height=80, body="<rect/>"), f"View {i}", "1:50")
        for i in range(4)
    ]
    v = compose_sheet(cells, width=800, height=600)
    assert v.body.count('class="view-label"') == 4
    assert "VIEW 1 — 1:50" in v.body


# ── 3. plan sheet detail ────────────────────────────────────────────────────


def test_plan_grid_dim_chains(pack) -> None:
    _p, out, _man = pack
    svg = (out / "A-101_plan.svg").read_text(encoding="utf-8")
    assert 'class="grid-dims"' in svg
    # running dims between consecutive grid positions (mm) + overall
    assert ">6000</text>" in svg  # U axis 0→6000→12000
    assert ">12000</text>" in svg  # overall U
    assert ">4500</text>" in svg  # V axis 0→4500→9000
    assert ">9000</text>" in svg  # overall V


def test_plan_room_tags_and_door_marks(pack) -> None:
    _p, out, _man = pack
    svg = (out / "A-101_plan.svg").read_text(encoding="utf-8")
    assert 'class="room-tags"' in svg
    assert "R01" in svg
    assert "m²" in svg  # area line in the boxed tag
    assert ">D1</text>" in svg  # door mark bubble


def test_plan_section_cut_markers(pack) -> None:
    _p, out, _man = pack
    svg = (out / "A-101_plan.svg").read_text(encoding="utf-8")
    assert 'class="section-marks"' in svg
    assert svg.count(">A-301</text>") >= 2  # both cut flags reference A-301
    assert ">A</text>" in svg and ">B</text>" in svg  # cut letters


# ── 4. section / elevation detail ───────────────────────────────────────────


def test_section_level_datums_and_overall_height(pack) -> None:
    _p, out, _man = pack
    svg = (out / "A-301_sections.svg").read_text(encoding="utf-8")
    assert 'class="level-datum"' in svg
    assert "EL. +0.000 m" in svg and "EL. +3.600 m" in svg
    assert 'class="storey-height"' in svg
    assert 'class="overall-height"' in svg


def test_elevation_level_datums(pack) -> None:
    _p, out, _man = pack
    svg = (out / "A-201_elevations.svg").read_text(encoding="utf-8")
    assert 'class="level-datum"' in svg
    assert "EL. +3.600 m" in svg
    assert 'class="overall-height"' in svg


# ── 5. schedule sheets as ruled tables ──────────────────────────────────────


def test_room_schedule_ruled_table_and_pagination(pack) -> None:
    p, out, man = pack
    n_rooms = len(schedule_rows(p.model, "room"))
    assert n_rooms == 30  # fixture: forces pagination at 28 rows/sheet
    nos = {s["no"] for s in man["sheets"]}
    assert "A-601" in nos and "A-601B" in nos
    first = (out / "A-601_rooms.svg").read_text(encoding="utf-8")
    second = (out / "A-601B_rooms.svg").read_text(encoding="utf-8")
    assert 'class="schedule-table"' in first
    assert "AREA m²" in first  # header band
    # one row rule per data row: 28 on the first page, remainder on the second
    assert first.count('stroke="#c3c9cf"') == 28
    assert second.count('stroke="#c3c9cf"') == n_rooms - 28
    assert "Room Schedule (1/2)" in first and "Room Schedule (2/2)" in second


def test_door_window_takeoff_tables(pack) -> None:
    p, out, _man = pack
    doors = (out / "A-602_doors.svg").read_text(encoding="utf-8")
    assert 'class="schedule-table"' in doors
    assert "MARK" in doors and "FIRE" in doors
    assert doors.count('stroke="#c3c9cf"') == len(schedule_rows(p.model, "door"))
    windows = (out / "A-603_windows.svg").read_text(encoding="utf-8")
    assert "SILL mm" in windows
    takeoff = (out / "P-601_takeoff.svg").read_text(encoding="utf-8")
    assert 'class="schedule-table"' in takeoff
    assert "MATERIAL" in takeoff and "QTY" in takeoff


def test_table_view_alignment_and_zebra() -> None:
    v = table_view(
        ["NAME", "QTY"],
        [["alpha", 12], ["beta", 3], ["gamma", 140]],
        title="T",
    )
    # numeric column right-aligned, text column left-aligned
    assert 'text-anchor="end"' in v.body
    assert 'text-anchor="start"' in v.body
    assert v.body.count('fill="#f2f5f7"') == 1  # zebra stripe on the middle row
    assert 'fill="#dfe3e8"' in v.body  # header band


def test_cover_lists_all_sheets(pack) -> None:
    _p, out, man = pack
    cover = (out / "G-001_cover.svg").read_text(encoding="utf-8")
    assert "Sheet Index" in cover
    for s in man["sheets"]:
        if s["no"] == "G-001":
            continue
        assert s["no"] in cover
