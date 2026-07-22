"""WP-CD-ANATOMY slice B — graphics hierarchy: line weights, hatches, furniture.

Covers the CD_COMPLETENESS_STANDARD gap rows that live in section/elevation
rendering and sheet furniture: 3-tier line-weight hierarchy (+ "ABV." dashed
hidden convention), material hatches (deterministic stipple / 45° diagonal /
batt zigzag / earth ticks) clipped analytically to the cut polygons,
new-vs-existing poché split, reserved PE/SE stamp block, revision clouds with
Δ deltas, and the shared legend block helper. All options are opt-in —
defaults stay byte-stable.
"""

from __future__ import annotations

import re

from llmbim import Project
from llmbim_drawings.layout import compose_sheet, legend_view
from llmbim_drawings.section import render_elevation_svg, render_section_svg
from llmbim_drawings.sheets import revision_cloud, title_block_svg
from llmbim_drawings.view import DrawingView

CUT = ((5000.0, -3000.0), (5000.0, 3000.0))  # vertical plane crossing y walls


def _proj(name: str) -> Project:
    p = Project.create(name, vcs=False)
    p.add_level("L1", 0)
    return p


def _wall_proj(name: str, type_id: str | None = None) -> Project:
    p = _proj(name)
    p.create_wall(
        level="L1", start=(0, 0), end=(10000, 0), thickness_mm=200,
        height_mm=3000, type_id=type_id,
    )
    return p


def _section(p: Project, **opts: object) -> str:
    return render_section_svg(p.model, CUT[0], CUT[1], **opts)  # type: ignore[arg-type]


# ── 1. line-weight hierarchy ─────────────────────────────────────────────────


def test_weight_classes_present_and_distinct() -> None:
    svg = _section(_wall_proj("lw-tiers"), weights=True)
    assert 'class="cut-walls lw-heavy"' in svg
    assert "lw-medium" in svg and "lw-light" in svg
    widths = {
        tier: float(re.search(rf"\.lw-{tier}\{{stroke-width:([\d.]+)", svg).group(1))  # type: ignore[union-attr]
        for tier in ("heavy", "medium", "light")
    }
    assert len(set(widths.values())) == 3
    assert widths["heavy"] > widths["medium"] > widths["light"]


def test_beyond_cut_renders_medium() -> None:
    p = _wall_proj("lw-beyond")
    # beam parallel to the cut plane, 200 mm away, below the wall top → beyond
    p.place_beam(level="L1", start=(4800, -500), end=(4800, 500), z0_mm=1000)
    svg = _section(p, weights=True)
    assert 'class="beyond-section lw-medium"' in svg
    assert ">ABV.<" not in svg  # legend mentions ABV.; no element is labeled


def test_above_cut_dashed_with_abv_label() -> None:
    p = _wall_proj("lw-abv")
    # projected beam ABOVE the cut walls' top (3000) → dashed + "ABV."
    p.place_beam(level="L1", start=(4800, -500), end=(4800, 500), z0_mm=4000)
    svg = _section(p, weights=True)
    m = re.search(r'<g class="hidden-above lw-hidden"[^>]*>', svg)
    assert m is not None
    assert "stroke-dasharray" in m.group(0)
    assert ">ABV.<" in svg


def test_line_legend_only_when_weights() -> None:
    p = _wall_proj("legend-proj")
    on = _section(p, weights=True)
    off = _section(p)
    assert 'class="line-legend"' in on and "LINE LEGEND" in on
    assert "line-legend" not in off
    # elevation carries the same hierarchy + legend
    elev = render_elevation_svg(p.model, "S", weights=True)
    assert 'class="walls lw-medium"' in elev
    assert "lw-light" in elev and "line-legend" in elev
    assert "lw-" not in render_elevation_svg(p.model, "S")


def test_elevation_opening_labels_stagger_when_crowded() -> None:
    # Two openings with heads at the same height, close together: their tags
    # would print on top of each other at one point. The renderer assigns the
    # nearer-left tag to a higher row and drops a leader to its opening.
    p = _wall_proj("elev-stagger")
    wid = p.model.query(category="wall", level="L1")[0].id
    for off, tid in ((1000.0, "WIN-AAAAAA-01"), (1700.0, "WIN-BBBBBB-02")):
        p.place_window(
            host=wid, offset_mm=off, width_mm=400, height_mm=1200,
            sill_mm=1000, type_id=tid,
        )
    grp = render_elevation_svg(p.model, "S").split('class="openings-elev')[1].split("</g>")[0]
    ys = [float(m) for m in re.findall(r'<text x="[\d.-]+" y="([\d.-]+)"', grp)]
    assert len(ys) == 2  # both tags present
    assert len(set(ys)) == 2  # ...on distinct rows (staggered, not piled)
    assert 'stroke-width="0.4"' in grp  # leader dropped for the raised tag


def test_no_storey_dim_above_topmost_level() -> None:
    # Storey dims run between consecutive levels. The topmost level has nothing
    # above it, so no dim to an arbitrary point above the roof should be drawn
    # (it would land above the viewBox and bleed onto the sheet border or the
    # neighbouring cell's title). Consecutive levels → len(levels) - 1 dims.
    p = _proj("multi-lvl")  # adds L1 @ 0
    p.add_level("L2", 3000)
    p.add_level("ROOF", 6000)
    p.create_wall(
        level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=6000,
    )
    svg = render_elevation_svg(p.model, "S")
    storey_ys = [
        float(m)
        for m in re.findall(r'y="([\d.-]+)"[^>]*class="storey-height"', svg)
    ]
    assert len(storey_ys) == 2  # L1→L2 and L2→ROOF only, not a 3rd above ROOF
    # every storey label sits within the drawn view, never above its top edge
    assert min(storey_ys) >= 0.0


# ── 2. material hatches ──────────────────────────────────────────────────────


def test_concrete_stipple_deterministic() -> None:
    p = _wall_proj("hatch-conc", type_id="W-SHIELD-CONC")
    a = _section(p, hatches=True)
    b = _section(p, hatches=True)
    assert a == b  # seeded from element id → byte-identical re-render
    assert 'class="hatch-concrete"' in a
    assert a.count("<circle", a.index("hatch-concrete")) > 5
    assert "CONC." in a  # leader note


def test_wood_diagonal_hatch_clipped_to_cut_polygon() -> None:
    svg = _section(_wall_proj("hatch-wood", type_id="W-EXT-2x6-BNB"), hatches=True)
    assert 'class="hatch-wood"' in svg
    assert "WD. FRMG." in svg
    # the cut wall rect bounds (the only wall-sized rect in cut-walls group)
    grp = re.search(r'class="cut-walls".*?</g>', svg, re.S).group(0)  # type: ignore[union-attr]
    rx, ry, rw, rh = (
        float(v)
        for v in re.search(
            r'<rect x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)"', grp
        ).groups()  # type: ignore[union-attr]
    )
    hatch = re.search(r'class="hatch-wood".*?</g>', svg, re.S).group(0)  # type: ignore[union-attr]
    lines = re.findall(
        r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"', hatch
    )
    assert lines, "diagonal hatch emitted"
    for x1, y1, x2, y2 in ((float(a) for a in ln) for ln in lines):
        assert rx - 0.5 <= x1 <= rx + rw + 0.5 and rx - 0.5 <= x2 <= rx + rw + 0.5
        assert ry - 0.5 <= y1 <= ry + rh + 0.5 and ry - 0.5 <= y2 <= ry + rh + 0.5


def test_insulation_hatch_single_leader_note() -> None:
    p = _proj("hatch-insul")
    for yy in (0, 2000):  # two insulated walls → hatch twice, note once
        p.create_wall(
            level="L1", start=(0, yy), end=(10000, yy), thickness_mm=150,
            height_mm=3000, type_id="W-INT-GYP",
        )
    svg = _section(p, hatches=True)
    assert 'class="hatch-insul"' in svg
    assert svg.count("BATT INSUL.") == 1


def test_earth_hatch_below_grade_only() -> None:
    p = _wall_proj("hatch-earth")
    p.create_strip_footing(
        level="L1", width_mm=450, depth_mm=300, path=[(4000, 0), (6000, 0)],
    )
    svg = _section(p, hatches=True)
    assert 'class="hatch-earth"' in svg and "EARTH" in svg
    gy = float(re.search(r'class="ground[^"]*" x1="[-\d.]+" y1="([-\d.]+)"', svg).group(1))  # type: ignore[union-attr]
    earth = re.search(r'class="hatch-earth".*?</g>', svg, re.S).group(0)  # type: ignore[union-attr]
    ys = [
        float(v)
        for ln in re.findall(r'y1="([-\d.]+)" *\n? *x2="[-\d.]+" y2="([-\d.]+)"', earth)
        for v in ln
    ]
    assert ys and all(y >= gy for y in ys)  # ticks strictly below the grade line
    # foundation cut also gets concrete stipple
    assert 'class="hatch-concrete"' in svg


# ── 3. poché new/existing split ──────────────────────────────────────────────


def test_poche_new_vs_existing_split() -> None:
    p = _proj("poche-phase")
    p.create_wall(level="L1", start=(0, 0), end=(10000, 0), height_mm=3000)
    ex = p.create_wall(level="L1", start=(0, 2000), end=(10000, 2000), height_mm=3000)
    p.set_phase(ex, "existing")
    svg = _section(p, weights=True)
    new_grp = re.search(r'<g class="cut-walls lw-heavy"[^>]*>', svg).group(0)  # type: ignore[union-attr]
    ex_grp = re.search(r'<g class="cut-existing lw-medium"[^>]*>', svg).group(0)  # type: ignore[union-attr]
    assert 'fill="#4d4d4d"' in new_grp  # new = heavy solid poché
    assert 'fill="#fff"' in ex_grp  # existing = open / lighter


# ── 4. sheet furniture ───────────────────────────────────────────────────────


def test_stamp_block_on_demand() -> None:
    kw = {"project": "P", "sheet_title": "FOUNDATION PLAN", "sheet_no": "S1.0", "body": ""}
    with_stamp = title_block_svg(stamp_block=True, **kw)  # type: ignore[arg-type]
    without = title_block_svg(**kw)  # type: ignore[arg-type]
    assert 'class="stamp-block"' in with_stamp and ">STAMP<" in with_stamp
    assert "stamp-block" not in without


def test_revision_cloud_closed_arcs_and_numbered_delta() -> None:
    svg = revision_cloud(10, 20, 120, 60, number="2")
    assert 'class="revision-cloud"' in svg
    d = re.search(r'<path d="([^"]+)"', svg).group(1)  # type: ignore[union-attr]
    assert d.startswith("M ") and d.endswith("Z")  # closed path
    assert d.count("A ") >= 8  # scallops on all four edges
    assert 'class="rev-delta"' in svg and ">2<" in svg


def test_compose_sheet_places_revision_cloud() -> None:
    cell = (DrawingView(width=100, height=80, body="<rect width='100' height='80'/>"), "V", "")
    sheet = compose_sheet(
        [cell], width=400, height=300,
        clouds=[{"x": 50, "y": 40, "w": 90, "h": 50, "number": "3"}],
    )
    assert 'class="revision-cloud"' in sheet.body and ">3<" in sheet.body


def test_legend_view_rows() -> None:
    rows = [
        ('<circle cx="12" cy="9" r="6" fill="none" stroke="#111"/>', "DOOR TAG"),
        ('<rect x="4" y="3" width="16" height="12" fill="none" stroke="#111"/>', "WINDOW TAG"),
    ]
    view = legend_view(rows, title="SYMBOL LEGEND")
    assert 'class="legend-block"' in view.body
    assert "SYMBOL LEGEND" in view.body
    assert "DOOR TAG" in view.body and "WINDOW TAG" in view.body
    assert view.body.count('class="legend-symbol"') == 2
    assert view.height > 22


# ── 5. defaults byte-stable ──────────────────────────────────────────────────


def test_defaults_byte_stable_when_options_unset() -> None:
    p = _wall_proj("stable", type_id="W-EXT-CMU")
    p.create_strip_footing(
        level="L1", width_mm=450, depth_mm=300, path=[(4000, 0), (6000, 0)],
    )
    plain = _section(p)
    assert plain == _section(p, weights=False, hatches=False)
    assert "lw-" not in plain and "hatch-" not in plain and "line-legend" not in plain
    elev = render_elevation_svg(p.model, "S")
    assert elev == render_elevation_svg(p.model, "S", weights=False)
    assert "lw-" not in elev
    cell = (DrawingView(width=100, height=80, body="<rect/>"), "V", "")
    assert (
        compose_sheet([cell], width=400, height=300).body
        == compose_sheet([cell], width=400, height=300, clouds=None).body
    )
