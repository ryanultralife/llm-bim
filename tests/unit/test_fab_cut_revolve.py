"""fab_cut_revolve — annular revolved cut (O-ring / relief grooves).

The mirror of ``fab_revolve``: the feature set could add a revolved boss but
had no way to cut one, so a sealed flange could not be modelled.
"""

from __future__ import annotations

import math

import pytest

pytest.importorskip("cadquery")

from llmbim_geometry.fab_brep import solid_volume_mm3  # noqa: E402


def _disc(r: float = 190.0, h: float = 25.0) -> list[dict]:
    return [{"op": "revolve", "radius_mm": r, "inner_radius_mm": 0.0,
             "height_mm": h, "origin_mm": [0, 0, 0]}]


def test_groove_removes_the_analytic_volume() -> None:
    """A groove is an annulus of material — volume removed must match exactly."""
    r_out, r_in, h, z = 158.55, 151.45, 4.1, 20.9
    base = _disc()
    grooved = base + [{"op": "cut_revolve", "radius_mm": r_out,
                       "inner_radius_mm": r_in, "height_mm": h,
                       "origin_mm": [0, 0, z]}]
    removed = solid_volume_mm3(base) - solid_volume_mm3(grooved)
    expect = math.pi * (r_out ** 2 - r_in ** 2) * h
    assert removed == pytest.approx(expect, rel=1e-3)


def test_groove_alias_is_accepted() -> None:
    """`groove` is a friendlier alias for the same op."""
    base = _disc()
    a = base + [{"op": "cut_revolve", "radius_mm": 100.0, "inner_radius_mm": 90.0,
                 "height_mm": 3.0, "origin_mm": [0, 0, 22.0]}]
    b = base + [{"op": "groove", "radius_mm": 100.0, "inner_radius_mm": 90.0,
                 "height_mm": 3.0, "origin_mm": [0, 0, 22.0]}]
    assert solid_volume_mm3(a) == pytest.approx(solid_volume_mm3(b))


def test_cut_revolve_needs_a_base_solid() -> None:
    from llmbim_geometry.fab_brep import FabBrepError, rebuild_solid

    with pytest.raises(FabBrepError):
        rebuild_solid([{"op": "cut_revolve", "radius_mm": 10.0,
                        "inner_radius_mm": 5.0, "height_mm": 2.0}])


def test_registered_as_an_op() -> None:
    """Agents drive the kernel by op name — it must resolve in the registry."""
    from llmbim import Project

    p = Project.create("groove-op", vcs=False)
    pid = p.create_fab_part(name="disc", material="aluminum_6061")
    p.fab_revolve(pid, radius_mm=50.0, height_mm=10.0)
    p.op("fab_cut_revolve", element_id=pid, radius_mm=40.0,
         inner_radius_mm=35.0, height_mm=2.0, origin_mm=[0, 0, 8.0])
    feats = p.model.get_element(pid).params["features"]
    assert feats[-1]["op"] == "cut_revolve"


def test_sdk_method_matches_the_op() -> None:
    from llmbim import Project

    p = Project.create("groove-sdk", vcs=False)
    pid = p.create_fab_part(name="disc", material="aluminum_6061")
    p.fab_revolve(pid, radius_mm=50.0, height_mm=10.0)
    p.fab_cut_revolve(pid, radius_mm=40.0, inner_radius_mm=35.0,
                      height_mm=2.0, origin_mm=(0.0, 0.0, 8.0))
    assert p.model.get_element(pid).params["features"][-1]["op"] == "cut_revolve"
