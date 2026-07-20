"""WP-SCHAD-S0 acceptance — published-area drift guard.

Cover-sheet areas [RB A0.1] (transition review §2.3 program facts):
total 2080 / garage 1568 / ADU 224 / workshop 224 SF (published).

The basis exposes the published values as ``build_scalars()['area_*']`` and
the drawn geometry via ``footprint()`` / ``build_placements()``. Model rooms
are checked against the published areas within 1%. The one recorded
discrepancy — workshop drawn gross (workshop_L x rear_W) vs published 224 —
is a known conflict the basis carries in ``open_questions()`` (Q-MECH); the
basis never silently resolves conflicts, and neither does this test.
"""

from __future__ import annotations

import pytest
from llmbim_geometry.primitives import polygon_area_mm2

import projects.schad.schad_design_basis as basis
from examples.schad_build import build_schad_model

MM2_PER_SF = 304.8 * 304.8
TOL = 0.01  # 1 % drift tolerance


@pytest.fixture(scope="module")
def project():
    return build_schad_model()


@pytest.fixture(scope="module")
def room_areas_sf(project):
    """Model room areas in SF, grouped by the basis placement kind."""
    kinds = {r["name"]: r["kind"] for r in basis.build_placements()}
    out: dict[str, float] = {}
    for el in project.model.elements:
        if el.category == "room":
            kind = kinds[el.name]
            out[kind] = out.get(kind, 0.0) + el.params["area_mm2"] / MM2_PER_SF
    return out


def _within(actual: float, published: float) -> bool:
    return abs(actual - published) / published <= TOL


def test_published_areas_pinned_to_cover_sheet():
    # [RB A0.1] — the published program facts (transition review §2.3)
    s = basis.build_scalars()
    assert s["area_total"] == 2080.0
    assert s["area_garage"] == 1568.0
    assert s["area_adu"] == 224.0
    assert s["area_workshop"] == 224.0


def test_total_area_from_footprint():
    s = basis.build_scalars()
    footprint_sf = polygon_area_mm2(list(basis.footprint()))  # ft in → SF out
    assert _within(footprint_sf, s["area_total"])


def test_garage_area_from_rooms(room_areas_sf):
    s = basis.build_scalars()
    assert _within(room_areas_sf["garage"], s["area_garage"])


def test_adu_area_from_rooms(room_areas_sf):
    s = basis.build_scalars()
    assert _within(room_areas_sf["adu"], s["area_adu"])


def test_workshop_area_drift_is_recorded(room_areas_sf):
    """Workshop: drawn gross = workshop_L x rear_W; published 224 SF.

    The drawn room must match the basis geometry exactly; the published
    figure differs, and that conflict must be ON RECORD in the basis
    (Q-MECH) — never silently resolved.
    """
    s = basis.build_scalars()
    drawn_sf = s["workshop_L"] * s["rear_W"]
    assert _within(room_areas_sf["workshop"], drawn_sf)
    if not _within(drawn_sf, s["area_workshop"]):
        q_ids = {q["id"] for q in basis.open_questions()}
        assert "Q-MECH" in q_ids, (
            "workshop drawn gross differs from published area but the "
            "conflict is not recorded in open_questions()"
        )


def test_room_sum_matches_published_total(room_areas_sf):
    s = basis.build_scalars()
    total_sf = (
        room_areas_sf["garage"] + room_areas_sf["adu"] + room_areas_sf["workshop"]
    )
    assert _within(total_sf, s["area_total"])
