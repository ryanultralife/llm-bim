"""Doors and windows must be real holes in the tessellated wall.

The IFC has always carried proper IfcOpeningElement voids, but the mesher
emitted a plain box per wall and floated a thin panel inside it — so glTF,
the web viewer and STEP showed solid walls you could not see through.

Volume is the test that actually bites: a wall that merely gained triangles
around an opening still comes out at full box volume.
"""

from __future__ import annotations

import pytest
from llmbim_geometry.mesh import _wall_box_mesh, _wall_with_openings_mesh

# mesh vertices are glTF space: metres, Y-up. Volumes below are therefore m3.
L, TH, HT = 6000.0, 200.0, 3000.0
FULL_M3 = (L / 1000) * (TH / 1000) * (HT / 1000)


def _volume(pos: list[float], idx: list[int]) -> float:
    """Signed volume of a closed triangle soup (divergence theorem)."""
    v = 0.0
    for k in range(0, len(idx), 3):
        a, b, c = idx[k], idx[k + 1], idx[k + 2]
        A = pos[a * 3:a * 3 + 3]
        B = pos[b * 3:b * 3 + 3]
        C = pos[c * 3:c * 3 + 3]
        v += (A[0] * (B[1] * C[2] - C[1] * B[2])
              - A[1] * (B[0] * C[2] - C[0] * B[2])
              + A[2] * (B[0] * C[1] - C[0] * B[1])) / 6.0
    return abs(v)


def _wall(openings):
    return _wall_with_openings_mesh(0, 0, L, 0, TH, 0, HT, openings)


def test_plain_wall_matches_the_old_box() -> None:
    """No openings must not change anything — byte-for-byte with the box."""
    assert _wall([]) == _wall_box_mesh(0, 0, L, 0, TH, 0, HT)
    assert _volume(*[_wall([])[i] for i in (0, 2)]) == pytest.approx(FULL_M3)


def test_door_removes_its_own_volume() -> None:
    """Door to the floor: two piers + a header, no sill block."""
    w, h = 3000.0, 2400.0
    pos, _n, idx = _wall([(1000.0, 1000.0 + w, 0.0, h)])
    cut = (w / 1000) * (h / 1000) * (TH / 1000)
    assert _volume(pos, idx) == pytest.approx(FULL_M3 - cut, abs=1e-9)
    assert _volume(pos, idx) < FULL_M3


def test_window_leaves_sill_and_header() -> None:
    w, sill, h = 1200.0, 900.0, 1200.0
    pos, _n, idx = _wall([(2000.0, 2000.0 + w, sill, sill + h)])
    cut = (w / 1000) * (h / 1000) * (TH / 1000)
    assert _volume(pos, idx) == pytest.approx(FULL_M3 - cut, abs=1e-9)
    # sill block below and header above => more pieces than a door's
    door = _wall([(2000.0, 2000.0 + w, 0.0, h)])
    assert len(idx) > len(door[2])


def test_many_openings_and_full_height_opening() -> None:
    ops = [(500.0, 1500.0, 0.0, 2100.0),
           (2500.0, 3500.0, 900.0, 2100.0),
           (4500.0, 5500.0, 0.0, HT)]      # full height: no header either
    pos, _n, idx = _wall(ops)
    cut = sum((b - a) / 1000 * (zb - za) / 1000 * (TH / 1000)
              for a, b, za, zb in ops)
    assert _volume(pos, idx) == pytest.approx(FULL_M3 - cut, abs=1e-9)


def test_overlapping_openings_are_not_double_cut() -> None:
    """Two overlapping openings must not remove the overlap twice."""
    pos, _n, idx = _wall([(1000.0, 3000.0, 0.0, 2000.0),
                          (2000.0, 4000.0, 0.0, 2000.0)])
    cut = (3000 / 1000) * (2000 / 1000) * (TH / 1000)   # union = 1000..4000
    assert _volume(pos, idx) == pytest.approx(FULL_M3 - cut, abs=1e-9)


def test_opening_wider_than_the_wall_is_clamped() -> None:
    pos, _n, idx = _wall([(-500.0, L + 500.0, 0.0, HT)])
    assert _volume(pos, idx) == pytest.approx(0.0, abs=1e-9)


def test_degenerate_openings_are_ignored() -> None:
    for bad in ([(1000.0, 1000.0, 0.0, HT)],        # zero width
                [(1000.0, 2000.0, 500.0, 500.0)],   # zero height
                [(9000.0, 9500.0, 0.0, HT)]):       # entirely off the wall
        pos, _n, idx = _wall(bad)
        assert _volume(pos, idx) == pytest.approx(FULL_M3, abs=1e-9), bad


def _box_vol_m3(corners) -> float:
    """AABB-ish volume of an 8-corner block (bottom 4 then top 4)."""
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    zs = [c[2] for c in corners]
    return (max(xs) - min(xs)) * (max(ys) - min(ys)) * (max(zs) - min(zs))


def test_step_wall_solids_cut_the_same_volume() -> None:
    """The STEP path (_wall_solids) must remove exactly what the mesh does."""
    from llmbim_core.model import Element, ProjectModel
    from llmbim_geometry.step_export import _wall_solids

    model = ProjectModel(name="t")
    wall = Element(
        id="w", category="wall", level_id=None,
        params={"start_mm": [0, 0], "end_mm": [L, 0],
                "thickness_mm": TH, "height_mm": HT},
    )
    # door 3 m wide to the floor + window 1.2 m at 0.9 m sill (metres, wall-local)
    ops = [(1.0, 4.0, 0.0, 2.4), (4.5, 5.7, 0.9, 2.1)]
    pieces = _wall_solids(wall, model, ops)
    total = sum(_box_vol_m3(c) for c, _f in pieces)
    cut = sum((b - a) * (zb - za) * (TH / 1000) for a, b, za, zb in ops)
    assert total == pytest.approx(FULL_M3 - cut, abs=1e-9)
    assert len(pieces) > 1                       # split around the openings
