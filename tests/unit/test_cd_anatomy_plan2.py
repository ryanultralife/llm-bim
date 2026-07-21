"""WP-CD-ANATOMY-2 slice A — plan-side gap closures.

Covers the CD completeness standard's remaining plan gap rows:
per-discipline grid bubble sides (arch vs framing), split-circle detail
callout bubbles with sheet refs (register auto-resolution from details
sheets), match lines (explicit edges + register auto-generation from
abutting crops), keynote squares + KEYNOTES legend, and byte-stable
defaults when every new option stays unset.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from llmbim import Project
from llmbim_core.errors import ValidationError
from llmbim_drawings.construction import export_construction_set
from llmbim_drawings.plan import render_plan_view

W_MM, D_MM, H_MM = 12000.0, 9000.0, 3000.0

LONG_NOTE = (
    "PROVIDE 2-HR RATED SHAFT WALL AT DUCT RISER PENETRATION, SEAL ALL JOINTS"
)


def _project(*, notes: bool = False, column: bool = False) -> Project:
    p = Project.create("cd-anatomy-2", vcs=False)
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=W_MM, d=D_MM,
        height_mm=H_MM, thickness_mm=200, name_prefix="B",
    )
    p.add_grid("U", [0, 6000, 12000])
    p.add_grid("V", [0, 4500, 9000])
    p.create_room(
        level="L1", name="Lab",
        boundary=[(0, 0), (W_MM, 0), (W_MM, D_MM), (0, D_MM)],
    )
    if notes:
        p.create_note(level="L1", text=LONG_NOTE, position=(2000, 2000))
        p.create_note(level="L1", text="SLOPE SLAB TO DRAIN", position=(6000, 4500))
        p.create_note(level="L1", text="DOWELS AT 16 OC", position=(9000, 7000))
    if column:
        p.place_column(level="L1", origin=(6000, 4500), name="C1")
    return p


def _grids_group(body: str) -> str:
    """Main grid group only (never the grids-frac group)."""
    return body.split('class="grids" stroke')[1].split("</g>")[0]


# ── 1. per-discipline grid bubble sides ─────────────────────────────────────


def test_grid_sides_framing_two_sides_only() -> None:
    p = _project()
    default_grids = _grids_group(render_plan_view(p.model, "L1", scale=0.02).body)
    framing_grids = _grids_group(
        render_plan_view(p.model, "L1", scale=0.02, grid_sides="framing").body
    )
    # default: bubbles on both ends of all 6 grid lines; framing: one end each
    assert default_grids.count("<circle") == 12
    assert framing_grids.count("<circle") == 6
    # numbers land on the TOP end (screen y=0), letters on the LEFT (x=0)
    assert framing_grids.count('cy="0"') == 3
    assert framing_grids.count('cx="0"') == 3
    # each label appears exactly once (vs twice with both-end bubbles)
    for lab in ("1", "2", "3", "A", "B", "C"):
        assert framing_grids.count(f">{lab}</text>") == 1
        assert default_grids.count(f">{lab}</text>") == 2


def test_grid_sides_arch_matches_both_end_default() -> None:
    p = _project()
    default_body = render_plan_view(p.model, "L1", scale=0.02).body
    arch_body = render_plan_view(p.model, "L1", scale=0.02, grid_sides="arch").body
    # arch = the reference convention drawn explicitly: letters left+right,
    # numbers top+bottom — identical to the both-end default
    assert _grids_group(arch_body) == _grids_group(default_body)
    assert _grids_group(arch_body).count("<circle") == 12


def test_grid_sides_invalid_mode_raises() -> None:
    p = _project()
    with pytest.raises(ValidationError):
        render_plan_view(p.model, "L1", scale=0.02, grid_sides="bogus")


# ── 2. detail callout bubbles (split circle) ────────────────────────────────


def test_detail_callout_split_circle_and_leader() -> None:
    p = _project()
    body = render_plan_view(
        p.model, "L1", scale=0.02,
        callouts=[{"x": 3000, "y": 3000, "detail": "9", "sheet": "A7.1"}],
    ).body
    group = body.split('class="detail-callouts"')[1].split("</g>")[0]
    assert 'class="detail-callout"' in group  # the circle
    assert 'class="callout-leader"' in group  # short leader off the point
    assert ">9</text>" in group
    assert ">A7.1</text>" in group
    # split-circle anatomy: horizontal divider through the bubble center
    # (x=3000,y=3000 mm → bubble center at screen (106, 104))
    assert 'class="callout-divider" x1="93" y1="104" x2="119" y2="104"' in group
    # detail number ABOVE the divider, sheet number BELOW it
    assert 'y="101"' in group  # detail text baseline above y=104
    assert 'y="113.5"' in group  # sheet text baseline below y=104


def test_register_callout_resolves_sheet_from_details(tmp_path: Path) -> None:
    p = _project()
    register = [
        {
            "no": "A1.1", "title": "FLOOR PLAN", "kind": "plan", "level": "L1",
            "callouts": [{"x": 3000, "y": 3000, "detail": "D07"}],  # no sheet
        },
        {
            "no": "S3.2", "title": "DETAILS", "kind": "details",
            "details": [
                {"id": "D07", "title": "BASE PLATE", "scale": 16,
                 "ops": [("l", 0, 0, 100, 100)]},
            ],
        },
    ]
    export_construction_set(p.model, tmp_path, plan_scale=0.02, sheets=register)
    plan = (tmp_path / "A1-1_plan.svg").read_text(encoding="utf-8")
    assert ">D07</text>" in plan
    assert ">S3.2</text>" in plan  # sheet ref resolved from the details entry


def test_register_callout_unresolvable_lists_known_ids(tmp_path: Path) -> None:
    p = _project()
    register = [
        {
            "no": "A1.1", "title": "FLOOR PLAN", "kind": "plan", "level": "L1",
            "callouts": [{"x": 3000, "y": 3000, "detail": "D99"}],
        },
        {
            "no": "S3.2", "title": "DETAILS", "kind": "details",
            "details": [
                {"id": "D07", "title": "BASE PLATE", "scale": 16,
                 "ops": [("l", 0, 0, 100, 100)]},
            ],
        },
    ]
    with pytest.raises(ValidationError) as ei:
        export_construction_set(p.model, tmp_path, plan_scale=0.02, sheets=register)
    msg = str(ei.value)
    assert "D99" in msg
    assert "D07" in msg  # the known detail ids are named
    assert ei.value.details["known_detail_ids"] == ["D07"]


# ── 3. match lines ──────────────────────────────────────────────────────────


def test_match_line_edge_placement_and_label() -> None:
    p = _project()
    body = render_plan_view(
        p.model, "L1", scale=0.02,
        match_lines=[
            {"edge": "N", "label": "MATCH LINE — SEE A1.2"},
            {"edge": "E", "label": "MATCH LINE — SEE A1.3"},
        ],
    ).body
    group = body.split('class="match-lines"')[1].split("</g>")[0]
    assert group.count('class="match-line"') == 2
    # heavy dash-dot linework
    assert 'stroke-width="2.2"' in group
    assert 'stroke-dasharray="18 5 4 5"' in group
    # N edge: horizontal line just inside the top (view is 264x204 px)
    assert 'x1="0" y1="8"' in group
    # E edge: vertical line just inside the right (264 - 8)
    assert 'x1="256" y1="0"' in group
    assert "MATCH LINE — SEE A1.2" in group
    # E/W labels read along the line (rotated)
    assert "rotate(-90" in group
    assert "MATCH LINE — SEE A1.3" in group


def test_match_line_invalid_edge_raises() -> None:
    p = _project()
    with pytest.raises(ValidationError):
        render_plan_view(
            p.model, "L1", scale=0.02,
            match_lines=[{"edge": "Q", "label": "MATCH LINE"}],
        )


def test_register_auto_match_lines_from_abutting_crops(tmp_path: Path) -> None:
    p = _project()
    register = [
        {"no": "A1.1", "title": "PLAN WEST", "kind": "plan", "level": "L1",
         "crop": (-600, -600, 6000, 9600)},
        {"no": "A1.2", "title": "PLAN EAST", "kind": "plan", "level": "L1",
         "crop": (6000, -600, 12600, 9600)},
    ]
    export_construction_set(p.model, tmp_path, plan_scale=0.02, sheets=register)
    west = (tmp_path / "A1-1_plan.svg").read_text(encoding="utf-8")
    east = (tmp_path / "A1-2_plan.svg").read_text(encoding="utf-8")
    # reciprocal references: each sheet points at the other across the seam
    assert 'class="match-line"' in west
    assert "MATCH LINE — SEE A1.2" in west
    assert 'class="match-line"' in east
    assert "MATCH LINE — SEE A1.1" in east


def test_register_explicit_match_lines_override_auto(tmp_path: Path) -> None:
    p = _project()
    register = [
        {"no": "A1.1", "title": "PLAN WEST", "kind": "plan", "level": "L1",
         "crop": (-600, -600, 6000, 9600),
         "match_lines": [{"edge": "S", "label": "CUSTOM MATCH NOTE"}]},
        {"no": "A1.2", "title": "PLAN EAST", "kind": "plan", "level": "L1",
         "crop": (6000, -600, 12600, 9600)},
    ]
    export_construction_set(p.model, tmp_path, plan_scale=0.02, sheets=register)
    west = (tmp_path / "A1-1_plan.svg").read_text(encoding="utf-8")
    east = (tmp_path / "A1-2_plan.svg").read_text(encoding="utf-8")
    # explicit opt replaces the auto line on that sheet only
    assert "CUSTOM MATCH NOTE" in west
    assert "SEE A1.2" not in west
    assert "MATCH LINE — SEE A1.1" in east  # sibling keeps its auto line


# ── 4. keynotes ─────────────────────────────────────────────────────────────


def test_keynote_squares_numbered_in_draw_order() -> None:
    p = _project(notes=True)
    body = render_plan_view(p.model, "L1", scale=0.02, keynotes=True).body
    group = body.split('class="keynotes"')[1].split("</g>")[0]
    assert group.count('class="keynote-square"') == 3
    assert group.count('class="keynote-leader"') == 3
    for num in ("1", "2", "3"):
        assert f">{num}</text>" in group
    # the plain inline note rendering is replaced, not doubled
    assert 'class="notes"' not in body
    assert f">{LONG_NOTE[:80]}</text>" not in body


def test_keynote_legend_contents_and_wrapping() -> None:
    p = _project(notes=True)
    body = render_plan_view(p.model, "L1", scale=0.02, keynotes=True).body
    legend = body.split('class="keynote-legend"')[1].split("</g>")[0]
    assert ">KEYNOTES</text>" in legend
    # short notes stay on one line
    assert ">SLOPE SLAB TO DRAIN</text>" in legend
    assert ">DOWELS AT 16 OC</text>" in legend
    # the 72-char note wraps into continuation lines (30-char width)
    assert f">{LONG_NOTE}</text>" not in legend
    assert "PROVIDE 2-HR RATED SHAFT WALL" in legend
    assert "SEAL ALL" in legend  # tail survives onto a wrapped line
    # legend rows: 3 numbered squares beside the texts
    assert legend.count("<rect") == 4  # frame + 3 number squares


def test_keynotes_skipped_when_no_notes() -> None:
    p = _project(notes=False)
    body = render_plan_view(p.model, "L1", scale=0.02, keynotes=True).body
    assert 'class="keynote-square"' not in body
    assert 'class="keynote-legend"' not in body  # no empty legend block


# ── 5. defaults byte-stable + register passthrough ──────────────────────────


def test_defaults_byte_stable_when_options_unset() -> None:
    p = _project(notes=True)
    base = render_plan_view(p.model, "L1", scale=0.02).to_svg()
    explicit = render_plan_view(
        p.model, "L1", scale=0.02,
        grid_sides=None, callouts=None, match_lines=None, keynotes=False,
    ).to_svg()
    assert base == explicit  # snapshot: option-less render is byte-identical
    for marker in (
        'class="keynotes"', 'class="keynote-legend"', 'class="keynote-square"',
        'class="detail-callouts"', 'class="match-lines"', 'class="match-line"',
        "KEYNOTES", "MATCH LINE",
    ):
        assert marker not in base
    # legacy inline notes unchanged
    assert 'class="notes"' in base
    assert "SLOPE SLAB TO DRAIN" in base


def test_custom_register_passthrough_all_four_options(tmp_path: Path) -> None:
    p = _project(notes=True)
    register = [
        {
            "no": "S2.1", "title": "FRAMING PLAN", "kind": "plan", "level": "L1",
            "grid_sides": "framing",
            "callouts": [{"x": 3000, "y": 3000, "detail": "5", "sheet": "S5.1"}],
            "match_lines": [{"edge": "W", "label": "MATCH LINE — SEE S2.2"}],
            "keynotes": True,
        },
        {"no": "A1.1", "title": "BARE PLAN", "kind": "plan", "level": "L1"},
    ]
    export_construction_set(p.model, tmp_path, plan_scale=0.02, sheets=register)
    framed = (tmp_path / "S2-1_plan.svg").read_text(encoding="utf-8")
    assert _grids_group(framed).count("<circle") == 6  # framing: 2 sides only
    assert 'class="detail-callout"' in framed
    assert ">S5.1</text>" in framed
    assert "MATCH LINE — SEE S2.2" in framed
    assert 'class="keynote-legend"' in framed
    # sibling entry without opts stays on the (unset) export-level defaults
    bare = (tmp_path / "A1-1_plan.svg").read_text(encoding="utf-8")
    assert _grids_group(bare).count("<circle") == 12
    for marker in ('class="detail-callouts"', 'class="match-lines"',
                   'class="keynotes"', 'class="keynote-legend"'):
        assert marker not in bare


def test_default_register_grid_sides_and_keynotes_flags(tmp_path: Path) -> None:
    p = _project(notes=True, column=True)
    export_construction_set(
        p.model, tmp_path, plan_scale=0.02, set_type="construction",
        grid_sides=True, keynotes=True,
    )
    # A-discipline floor plan: arch sides (both ends) + keynote legend
    arch_plan = (tmp_path / "A-101_plan.svg").read_text(encoding="utf-8")
    assert _grids_group(arch_plan).count("<circle") == 12
    assert 'class="keynote-legend"' in arch_plan
    assert ">KEYNOTES</text>" in arch_plan
    # S-discipline structural plan: framing sides (2 sides only), no keynotes
    s_plan = (tmp_path / "S-101_structural.svg").read_text(encoding="utf-8")
    assert _grids_group(s_plan).count("<circle") == 6
    assert 'class="keynote-legend"' not in s_plan
