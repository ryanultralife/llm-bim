"""The takeoff must price the whole building, and price it net.

Kernel `compute_boq` priced only wall/slab/door/window/room/equipment — the
roof, footings and stem walls (the concrete + roofing envelope) had no line
at all, and wall areas billed openings as if they were wall. These guards
lock in the coverage + net-pricing fixes.
"""

from __future__ import annotations

import math

import pytest
from llmbim import Project
from llmbim_core.quantities import (
    _poly_clip_area,
    boq_summary,
    compute_boq,
    roof_area_m2,
    wall_corner_overlap_m3,
    wall_net_area_m2,
)


@pytest.fixture(scope="module")
def pack():
    p = Project.create("boq coverage", vcs=False)
    p.add_level("L1", 0)
    w = 6000.0
    ids = [
        p.create_wall(level="L1", start=(0, 0), end=(w, 0), thickness_mm=200, height_mm=3000),
        p.create_wall(level="L1", start=(w, 0), end=(w, w), thickness_mm=200, height_mm=3000),
        p.create_wall(level="L1", start=(w, w), end=(0, w), thickness_mm=200, height_mm=3000),
        p.create_wall(level="L1", start=(0, w), end=(0, 0), thickness_mm=200, height_mm=3000),
    ]
    for wid in ids:
        p.set_type(wid, "W-EXT-WOOD-BNB")
    south = ids[0]
    p.place_door(host=south, offset_mm=1000, width_mm=3000, height_mm=2400)
    rid = p.create_gable_roof(
        level="L1",
        footprint=[(0, 0), (w, 0), (w, w), (0, w)],
        ridge_axis="x", plate_mm=3000.0, pitch=0.5,
        overhang_mm=0.0, thickness_mm=200.0, name="R",
    )
    p.set_type(rid, "R-ASPHALT-R38")
    p.create_strip_footing(level="L1", width_mm=450, depth_mm=300,
                           path=[(0, 0), (w, 0)], mark="F1")
    p.create_stem_wall(level="L1", path=[(0, 0), (w, 0)],
                       height_mm=600, thickness_mm=200, mark="S1")
    return p


def test_envelope_categories_have_boq_lines(pack) -> None:
    """Roof, footing and stem wall must each price (were $0/absent)."""
    rows = compute_boq(pack.model)
    cats = {r["category"] for r in rows}
    for cat in ("roof", "footing", "stem_wall"):
        assert cat in cats, f"{cat} missing from BOQ"
        line = next(r for r in rows if r["category"] == cat)
        assert line["qty"] > 0 and line["est_cost"] > 0, cat


def test_roof_prices_as_assembly_on_slope(pack) -> None:
    """6:12 gable: real assembly (not generic), area on the slope not plan."""
    roof = next(e for e in pack.model.elements if e.category == "roof")
    slope = roof_area_m2(roof)
    assert slope == pytest.approx(36.0 * math.sqrt(1.25), rel=0.03)  # >plan 36 m2
    line = next(r for r in compute_boq(pack.model) if r["category"] == "roof")
    assert "R-38" in line["type_name"]                 # not the generic fallback
    # rafters + insulation dominate — a real assembly, not a thin skin
    assert line["est_cost"] > slope * 100


def test_openings_deducted_from_wall(pack) -> None:
    south = next(e for e in pack.model.elements
                 if e.category == "wall" and e.params["start_mm"] == [0.0, 0.0])
    gross = 6.0 * 3.0
    net = wall_net_area_m2(south, pack.model)
    assert net == pytest.approx(gross - 3.0 * 2.4, abs=1e-6)
    row = next(r for r in compute_boq(pack.model)
               if r["category"] == "wall" and r["id"] == south.id)
    assert row["qty"] == pytest.approx(net, abs=1e-3)
    assert row["gross_qty"] == pytest.approx(gross, abs=1e-3)


def test_corner_overlap_is_exact_not_naive(pack) -> None:
    """Four L-corners of equal-thickness walls: each overlap is (t/2)^2 * h."""
    wall = next(e for e in pack.model.elements if e.category == "wall")
    t = float(wall.params["thickness_mm"]) / 1000.0
    overlap = wall_corner_overlap_m3(pack.model)
    assert overlap == pytest.approx(4 * (t / 2) ** 2 * 3.0, rel=1e-6)


def test_collinear_split_is_not_deducted() -> None:
    """Two walls end-to-end share an endpoint but must not double-count."""
    p = Project.create("collinear", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(3000, 0), thickness_mm=200, height_mm=3000)
    p.create_wall(level="L1", start=(3000, 0), end=(6000, 0), thickness_mm=200, height_mm=3000)
    assert wall_corner_overlap_m3(p.model) == pytest.approx(0.0, abs=1e-9)


def test_summary_reports_net_wall_volume(pack) -> None:
    rows = compute_boq(pack.model)
    s = boq_summary(rows, pack.model)
    assert s["wall_volume_net_m3"] < s["wall_volume_gross_m3"]
    assert s["wall_volume_net_m3"] == pytest.approx(
        s["wall_volume_gross_m3"] - s["wall_corner_deduction_m3"], abs=1e-6)
    assert "wall_corner_deduction_m3" not in boq_summary(rows)  # needs model


def test_material_takeoff_covers_roof_and_footing(pack) -> None:
    from llmbim_core.material_lists import exploded_material_bom

    rows = exploded_material_bom(pack.model)
    sources = {r["source"] for r in rows}
    assert {"roof_layer", "footing", "stem_wall"} <= sources
    roof_mats = {r["material_id"] for r in rows if r["source"] == "roof_layer"}
    assert "rafter_2x12" in roof_mats and "batt_insulation_r38" in roof_mats


def test_clip_area_matches_hand_computation() -> None:
    a = [(0, 0), (1, 0), (1, 1), (0, 1)]
    b = [(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5)]
    assert _poly_clip_area(a, b) == pytest.approx(0.25)
    assert _poly_clip_area(list(reversed(a)), b) == pytest.approx(0.25)  # CW ok
    assert _poly_clip_area(a, [(2, 2), (3, 2), (3, 3)]) == pytest.approx(0.0)
