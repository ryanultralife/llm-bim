"""WP-SCHAD-S1 acceptance — Schad walls/doors/windows use the wood
residential type registry (docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md §7.1,
§8, §10).

After S1 no Schad wall may remain on the industrial catalog
(W-EXT-CMU / W-INT-GYP); the garage/ADU separation must be the 1-hr rated
W-1HR-GAR-ADU; ``set_type`` must sync thickness_mm + wall_layers from the
registered layer stacks. Dimensions asserted here are read from the basis
(projects/schad/schad_design_basis.py) — the only number source.
"""

from __future__ import annotations

import pytest
from llmbim_core.types_catalog import (
    DEFAULT_DOOR_TYPES,
    DEFAULT_WALL_TYPES,
    DEFAULT_WINDOW_TYPES,
)

import projects.schad.schad_design_basis as basis
from examples.schad_build import build_schad_model

FT_TO_MM = 304.8

RESIDENTIAL_WALL_TYPES = {"W-EXT-2x6-BNB", "W-INT-2x4", "W-1HR-GAR-ADU"}
RESIDENTIAL_DOOR_TYPES = {"D-OH-12x9", "D-OH-12x12", "D-SC-36-ADA", "D-HM-30"}
INDUSTRIAL_WALL_TYPES = {"W-EXT-CMU", "W-INT-GYP", "W-SHIELD-CONC", "W-GENERIC-200"}
INDUSTRIAL_DOOR_TYPES = {"D-HM-36", "D-HM-72", "D-SHIELD-PLUG"}


@pytest.fixture(scope="module")
def project():
    return build_schad_model()


def _by_category(project, category):
    return [el for el in project.model.elements if el.category == category]


def test_registry_ships_residential_types():
    assert RESIDENTIAL_WALL_TYPES <= set(DEFAULT_WALL_TYPES)
    assert RESIDENTIAL_DOOR_TYPES <= set(DEFAULT_DOOR_TYPES)
    assert "WIN-CASE-48x48" in DEFAULT_WINDOW_TYPES
    # window U-factor per the basis schedule [RB A4.1]
    u_factors = {w["u_factor"] for w in basis.build_windows()}
    assert {DEFAULT_WINDOW_TYPES["WIN-CASE-48x48"].u_value} == u_factors
    # wall thickness comes from the layer stack, not a hardcoded scalar
    for tid in RESIDENTIAL_WALL_TYPES:
        wt = DEFAULT_WALL_TYPES[tid]
        assert wt.layers, tid
        assert wt.total_thickness_mm == sum(layer.thickness_mm for layer in wt.layers)
        assert wt.total_thickness_mm > 0


def test_all_walls_wood_zero_industrial(project):
    walls = _by_category(project, "wall")
    assert len(walls) == len(basis.build_walls())
    type_ids = {w.type_id for w in walls}
    assert type_ids <= RESIDENTIAL_WALL_TYPES, f"non-residential wall types: {type_ids}"
    # transition §8: do NOT map Schad walls to W-EXT-CMU after S1
    assert not (type_ids & INDUSTRIAL_WALL_TYPES)
    # every basis wall kind resolved to the intended type
    for w, rec in zip(walls, basis.build_walls()):
        kind = rec["kind"].lower()
        if "fire" in kind:
            assert w.type_id == "W-1HR-GAR-ADU", w.name
        elif "interior" in kind:
            assert w.type_id == "W-INT-2x4", w.name
        else:
            assert w.type_id == "W-EXT-2x6-BNB", w.name


def test_fire_separation_wall_is_1hr(project):
    fire_walls = [w for w in _by_category(project, "wall") if w.type_id == "W-1HR-GAR-ADU"]
    # exactly one fire-separation wall in the basis (garage/rear-addition line)
    assert len(fire_walls) == sum(
        1 for w in basis.build_walls() if "fire" in w["kind"].lower()
    ) == 1
    wt = DEFAULT_WALL_TYPES["W-1HR-GAR-ADU"]
    assert wt.fire_rating == "1-hr"
    for w in fire_walls:
        assert w.params.get("fire_rating") == "1-hr"


def test_set_type_synced_thickness_and_layers(project):
    for w in _by_category(project, "wall"):
        wt = DEFAULT_WALL_TYPES[w.type_id]
        assert w.params["thickness_mm"] == pytest.approx(wt.total_thickness_mm)
        assert w.params["wall_layers"] == [layer.model_dump() for layer in wt.layers]
    # interior stack reproduces the basis partition thickness exactly
    # (wall_t_int = 2x4 stud + gyp both sides)
    s = basis.build_scalars()
    assert DEFAULT_WALL_TYPES["W-INT-2x4"].total_thickness_mm == pytest.approx(
        s["wall_t_int"] * FT_TO_MM
    )


def test_doors_typed_per_basis(project):
    doors = _by_category(project, "door")
    schedule = {d["mark"]: d for d in basis.build_doors()}
    # every scheduled door placed (no orphans dropped to notes)
    assert {d.name for d in doors} == set(schedule)
    for d in doors:
        rec = schedule[d.name]
        assert d.type_id in RESIDENTIAL_DOOR_TYPES, (d.name, d.type_id)
        assert d.type_id not in INDUSTRIAL_DOOR_TYPES
        dt = DEFAULT_DOOR_TYPES[d.type_id]
        if "OVERHEAD" in rec["type"].upper():
            assert d.type_id.startswith("D-OH-")
            # the registered leaf matches the basis schedule size
            assert dt.width_mm == pytest.approx(rec["w"] * FT_TO_MM)
            assert dt.height_mm == pytest.approx(rec["h"] * FT_TO_MM)
        elif "HOLLOW METAL" in rec.get("remarks", "").upper():
            assert d.type_id == "D-HM-30"
        else:
            assert d.type_id == "D-SC-36-ADA"


def test_windows_typed_per_basis(project):
    windows = _by_category(project, "window")
    schedule = basis.build_windows()
    assert len(windows) == len(schedule)
    for w in windows:
        assert w.type_id == "WIN-CASE-48x48"
    # registered casement matches the basis 4'x4' schedule row
    wt = DEFAULT_WINDOW_TYPES["WIN-CASE-48x48"]
    assert wt.width_mm == pytest.approx(schedule[0]["w"] * FT_TO_MM)
    assert wt.height_mm == pytest.approx(schedule[0]["h"] * FT_TO_MM)
