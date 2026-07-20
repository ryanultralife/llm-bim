"""WP-SCHAD-S3 — foundations: strip/pad footings, stem walls, dual slabs-on-grade.

Every Schad dimension is IMPORTED from the design basis
(``projects/schad/schad_design_basis.py``, imperial feet) and converted once
here — never retyped. [RB foundation notes]: footings 18" x 12", stem walls
8" front / 6" typical, slabs 4" garage / 3" ADU, rebar "(2) #4 CONTINUOUS".
Values that the basis does NOT fix (stem height / frost depth, pad sizes) are
explicit test fixtures, not Schad claims.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from llmbim import Project

import projects.schad.schad_design_basis as basis

FT_TO_MM = 304.8

_S = basis.build_scalars()
# [RB foundation notes] via the basis — converted once, feet → mm
FOOTING_W_MM = _S["footing_w"] * FT_TO_MM  # 18" = 457.2
FOOTING_D_MM = _S["footing_d"] * FT_TO_MM  # 12" = 304.8
STEM_FRONT_MM = _S["stem_front"] * FT_TO_MM  # 8" = 203.2
STEM_TYP_MM = _S["stem_typ"] * FT_TO_MM  # 6" = 152.4
SLAB_GARAGE_MM = _S["slab_garage_t"] * FT_TO_MM  # 4" = 101.6
SLAB_ADU_MM = _S["slab_adu_t"] * FT_TO_MM  # 3" = 76.2
MAIN_L_MM = _S["main_L"] * FT_TO_MM  # 48'
MAIN_W_MM = _S["main_W"] * FT_TO_MM  # 32'
ADU_X0_MM = _S["rear_off_x"] * FT_TO_MM
ADU_L_MM = _S["adu_L"] * FT_TO_MM
REAR_W_MM = _S["rear_W"] * FT_TO_MM
# [RB foundation notes] rebar callout — carried verbatim from the basis
REBAR_NOTE = next(n for n in basis.build_notes()["foundation"] if n.startswith("REBAR:"))

# Test fixtures (NOT basis values — the basis does not fix stem height or pads)
FIX_STEM_H_MM = 600.0
FIX_PAD_W_MM = 600.0
FIX_PAD_D_MM = 600.0


def _project() -> Project:
    p = Project.create("schad-s3-foundations", vcs=False)
    p.add_level("L1", 0)
    return p


def _perimeter_path() -> list[tuple[float, float]]:
    return [
        (0.0, 0.0),
        (MAIN_L_MM, 0.0),
        (MAIN_L_MM, MAIN_W_MM),
        (0.0, MAIN_W_MM),
        (0.0, 0.0),
    ]


def _full_foundation_project() -> Project:
    """Schad-flavoured foundation set: F1 strip + F2 pad + stem walls + dual slabs."""
    p = _project()
    p.create_strip_footing(
        level="L1",
        path=_perimeter_path(),
        width_mm=FOOTING_W_MM,
        depth_mm=FOOTING_D_MM,
        top_of_footing_mm=-FIX_STEM_H_MM,
        rebar={"long": REBAR_NOTE},
        mark="F1",
    )
    p.create_pad_footing(
        level="L1",
        origin=(MAIN_L_MM / 2.0, MAIN_W_MM / 2.0),
        w_mm=FIX_PAD_W_MM,
        d_mm=FIX_PAD_D_MM,
        depth_mm=FOOTING_D_MM,
        top_of_footing_mm=-FIX_STEM_H_MM,
        rebar={"mat": REBAR_NOTE},
        mark="F2",
    )
    # stem walls: 8" at the garage front (south), 6" typical [RB foundation notes]
    p.create_stem_wall(
        level="L1",
        path=[(0.0, 0.0), (MAIN_L_MM, 0.0)],
        height_mm=FIX_STEM_H_MM,
        thickness_mm=STEM_FRONT_MM,
        rebar=REBAR_NOTE,
        mark="SW1",
    )
    p.create_stem_wall(
        level="L1",
        path=[(MAIN_L_MM, 0.0), (MAIN_L_MM, MAIN_W_MM), (0.0, MAIN_W_MM), (0.0, 0.0)],
        height_mm=FIX_STEM_H_MM,
        thickness_mm=STEM_TYP_MM,
        rebar=REBAR_NOTE,
        mark="SW2",
    )
    # DUAL slabs [RB/BOM]: 4" garage w/ radiant, 3" ADU for tile
    p.create_slab_on_grade(
        level="L1",
        rect=(0.0, 0.0, MAIN_L_MM, MAIN_W_MM),
        thickness_mm=SLAB_GARAGE_MM,
        mark="S1",
        name="Slab-Garage",
    )
    p.create_slab_on_grade(
        level="L1",
        rect=(ADU_X0_MM, MAIN_W_MM, ADU_L_MM, REAR_W_MM),
        thickness_mm=SLAB_ADU_MM,
        mark="S2",
        name="Slab-ADU",
    )
    return p


def test_strip_footing_carries_schad_basis_section():
    # basis-driven hand check: 18" x 12" [RB foundation notes]
    assert abs(FOOTING_W_MM - 457.2) < 1e-9
    assert abs(FOOTING_D_MM - 304.8) < 1e-9
    p = _project()
    fid = p.create_strip_footing(
        level="L1",
        path=_perimeter_path(),
        width_mm=FOOTING_W_MM,
        depth_mm=FOOTING_D_MM,
        top_of_footing_mm=-FIX_STEM_H_MM,
        rebar={"long": REBAR_NOTE},
        mark="F1",
    )
    el = p.model.get_element(fid)
    assert el.category == "footing"
    assert el.params["kind"] == "strip"
    assert el.params["width_mm"] == FOOTING_W_MM
    assert el.params["depth_mm"] == FOOTING_D_MM
    assert el.params["mark"] == "F1"
    assert el.params["rebar"] == {"long": REBAR_NOTE}
    # perimeter length = 2*(48'+32')
    assert abs(el.params["length_mm"] - 2 * (MAIN_L_MM + MAIN_W_MM)) < 0.1
    # honesty stamp: rebar is carried data, not a calculation
    assert "not engineering calculations" in el.params["honesty"]


def test_strip_footing_under_wall_and_undo():
    p = _project()
    wid = p.create_wall(
        level="L1", start=(0, 0), end=(MAIN_L_MM, 0), thickness_mm=165, height_mm=3048
    )
    fid = p.create_strip_footing(
        level="L1",
        under_wall=wid,
        width_mm=FOOTING_W_MM,
        depth_mm=FOOTING_D_MM,
        top_of_footing_mm=-FIX_STEM_H_MM,
        mark="F1",
    )
    el = p.model.get_element(fid)
    assert el.params["under_wall_id"] == wid
    # path derived once from the wall centerline
    assert el.params["path_mm"] == [[0.0, 0.0], [MAIN_L_MM, 0.0]]
    assert p.model.stats().get("footing") == 1
    p.undo()
    assert p.model.stats().get("footing", 0) == 0


def test_pad_footing_geometry_and_undo():
    p = _project()
    fid = p.create_pad_footing(
        level="L1",
        origin=(MAIN_L_MM / 2.0, MAIN_W_MM / 2.0),
        w_mm=FIX_PAD_W_MM,
        d_mm=FIX_PAD_D_MM,
        depth_mm=FOOTING_D_MM,
        top_of_footing_mm=-FIX_STEM_H_MM,
        mark="F2",
    )
    el = p.model.get_element(fid)
    assert el.params["kind"] == "pad"
    assert el.params["mark"] == "F2"
    xs = [q[0] for q in el.params["polygon_mm"]]
    ys = [q[1] for q in el.params["polygon_mm"]]
    assert abs((max(xs) - min(xs)) - FIX_PAD_W_MM) < 1e-6
    assert abs((max(ys) - min(ys)) - FIX_PAD_D_MM) < 1e-6
    p.undo()
    assert p.model.stats().get("footing", 0) == 0


def test_stem_wall_schad_thicknesses():
    # basis-driven hand check: 8" front / 6" typical [RB foundation notes]
    assert abs(STEM_FRONT_MM - 203.2) < 1e-9
    assert abs(STEM_TYP_MM - 152.4) < 1e-9
    p = _full_foundation_project()
    stems = p.model.query(category="stem_wall")
    assert len(stems) == 2
    by_mark = {el.params["mark"]: el for el in stems}
    assert by_mark["SW1"].params["thickness_mm"] == STEM_FRONT_MM
    assert by_mark["SW2"].params["thickness_mm"] == STEM_TYP_MM
    # tops out at the level datum by default, extends down toward the footing
    assert by_mark["SW1"].params["top_mm"] == 0.0
    assert by_mark["SW1"].params["height_mm"] == FIX_STEM_H_MM


def test_dual_slabs_on_grade_schad_thicknesses():
    # DUAL slabs [RB/BOM]: 4" garage w/ radiant vs 3" ADU for tile
    assert abs(SLAB_GARAGE_MM - 101.6) < 1e-9
    assert abs(SLAB_ADU_MM - 76.2) < 1e-9
    assert SLAB_GARAGE_MM != SLAB_ADU_MM
    p = _full_foundation_project()
    slabs = [
        el for el in p.model.elements
        if el.category == "slab" and el.params.get("kind") == "slab_on_grade"
    ]
    assert len(slabs) == 2
    by_mark = {el.params["mark"]: el for el in slabs}
    assert by_mark["S1"].params["thickness_mm"] == SLAB_GARAGE_MM
    assert by_mark["S2"].params["thickness_mm"] == SLAB_ADU_MM
    # areas derive from the basis footprint dims
    assert abs(by_mark["S1"].params["area_mm2"] - MAIN_L_MM * MAIN_W_MM) < 1.0
    assert abs(by_mark["S2"].params["area_mm2"] - ADU_L_MM * REAR_W_MM) < 1.0


def test_rebar_schedule_rows():
    p = _full_foundation_project()
    rows = p.rebar_schedule()
    by_mark = {(r["mark"], r["type"]): r for r in rows}
    f1 = by_mark[("F1", "strip_footing")]
    assert f1["qty"] == 1
    assert REBAR_NOTE in f1["rebar"]
    assert abs(f1["length_m"] - 2 * (MAIN_L_MM + MAIN_W_MM) / 1000.0) < 0.01
    f2 = by_mark[("F2", "pad_footing")]
    assert f2["qty"] == 1 and f2["area_m2"] > 0
    assert ("SW1", "stem_wall") in by_mark and ("SW2", "stem_wall") in by_mark
    s1 = by_mark[("S1", "slab_on_grade")]
    assert abs(s1["area_m2"] - MAIN_L_MM * MAIN_W_MM / 1e6) < 0.01
    assert all("not engineering calculations" in r["note"] for r in rows)
    # registry op mirrors the SDK helper
    op = p.op("rebar_schedule")
    assert op["count"] == len(rows)


def test_gltf_strict_verify_with_foundations(tmp_path: Path):
    from llmbim_drawings.deliverables import _verify_gltf_strict

    p = _full_foundation_project()
    # a wall above grade so the scene mixes above/below-datum solids
    p.create_wall(
        level="L1", start=(0, 0), end=(MAIN_L_MM, 0), thickness_mm=165, height_mm=3048
    )
    out = tmp_path / "model.gltf"
    p.export_gltf(out)
    v = _verify_gltf_strict(out)
    assert v["gltf_valid"], v["failures"]
    data = json.loads(out.read_text(encoding="utf-8"))
    names = [m.get("name") for m in data.get("materials") or []]
    assert "concrete" in names
    # glTF Y (metres) is elevation: foundations must reach below the datum
    mins = [
        float(a["min"][1])
        for a in data.get("accessors") or []
        if isinstance(a.get("min"), list) and len(a["min"]) == 3
    ]
    assert mins and min(mins) < 0.0
    assert min(mins) <= -(FIX_STEM_H_MM + FOOTING_D_MM) / 1000.0 + 1e-6


def test_ifc_foundation_entities(tmp_path: Path):
    p = _full_foundation_project()
    out = tmp_path / "model.ifc"
    p.export_ifc(out)
    text = out.read_text(encoding="utf-8")
    assert "IFCFOOTING(" in text
    assert ".STRIP_FOOTING." in text
    assert ".PAD_FOOTING." in text
    assert ".BASESLAB." in text
    # stem walls as IfcWall solids; breps closed like the IfcRoof pattern
    assert re.search(r"IFCWALL\('[^']+',#\d+,'Stem-SW1'", text)
    assert ".SOLIDWALL." in text
    assert "IFCFACETEDBREP(" in text and "IFCCLOSEDSHELL(" in text


def test_section_shows_foundation_below_datum():
    from llmbim_drawings.section import render_section_svg

    p = _full_foundation_project()
    p.create_wall(
        level="L1", start=(0, 0), end=(MAIN_L_MM, 0), thickness_mm=165, height_mm=3048
    )
    # N-S cut through the middle: crosses both strip runs, the pad, and slab S1
    svg = render_section_svg(
        p.model, (MAIN_L_MM / 2.0, -2000.0), (MAIN_L_MM / 2.0, MAIN_W_MM + 2000.0)
    )
    assert 'class="foundation-section"' in svg
    m = re.search(r'<g class="foundation-section".*?</g>', svg, re.DOTALL)
    assert m is not None
    rects = re.findall(
        r'<rect x="[^"]+" y="([^"]+)" width="[^"]+" height="([^"]+)"', m.group(0)
    )
    assert rects
    # ground line marks z=0; SVG y grows downward, so foundation bottoms
    # (y + height) must extend below the ground line
    g = re.search(r'class="ground" x1="[^"]+" y1="([^"]+)"', svg)
    assert g is not None
    ground_y = float(g.group(1))
    max_bottom = max(float(y) + float(h) for y, h in rects)
    assert max_bottom > ground_y + 1.0


def test_elevation_dashed_below_grade_foundations():
    from llmbim_drawings.section import render_elevation_svg

    p = _full_foundation_project()
    p.create_wall(
        level="L1", start=(0, 0), end=(MAIN_L_MM, 0), thickness_mm=165, height_mm=3048
    )
    svg = render_elevation_svg(p.model, "S")
    assert 'class="foundation-elev"' in svg
    m = re.search(r'<g class="foundation-elev".*?</g>', svg, re.DOTALL)
    assert m is not None
    assert "stroke-dasharray" in m.group(0)
    assert "<rect" in m.group(0)


def test_foundation_ops_registered():
    p = _project()
    r = p.op(
        "create_strip_footing",
        level="L1",
        path=[[0, 0], [10000, 0]],
        width_mm=FOOTING_W_MM,
        depth_mm=FOOTING_D_MM,
        top_of_footing_mm=-500,
        mark="F1",
    )
    assert r["kind"] == "strip" and r["length_mm"] == 10000.0
    r2 = p.op(
        "create_pad_footing",
        level="L1",
        origin=[5000, 5000],
        w_mm=FIX_PAD_W_MM,
        d_mm=FIX_PAD_D_MM,
        depth_mm=FOOTING_D_MM,
        mark="F2",
    )
    assert r2["kind"] == "pad"
    r3 = p.op(
        "create_stem_wall",
        level="L1",
        path=[[0, 0], [10000, 0]],
        height_mm=FIX_STEM_H_MM,
        thickness_mm=STEM_TYP_MM,
    )
    assert r3["category"] == "stem_wall"
    r4 = p.op(
        "create_slab_on_grade",
        level="L1",
        x=0,
        y=0,
        w=10000,
        d=8000,
        thickness_mm=SLAB_GARAGE_MM,
        mark="S1",
    )
    assert r4["kind"] == "slab_on_grade"
    ops = {o["name"] for o in p.ops()}
    assert {
        "create_strip_footing",
        "create_pad_footing",
        "create_stem_wall",
        "create_slab_on_grade",
        "rebar_schedule",
    } <= ops
