"""WP-SCHAD-S2 — roof planes: gable/shed/plane commands, mesh, elev/section, IFC.

Hand-calc basis (Schad Phase 1): main 48' x 32', plate 10', pitch 6:12 (0.5),
overhang 18" → run 16', rise 8', ridge 18'.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from llmbim import Project

FT = 304.8
IN = 25.4

PLATE = 10 * FT  # 3048
OVERHANG = 18 * IN  # 457.2
RIDGE = 18 * FT  # 5486.4


def _footprint_48x32() -> list[tuple[float, float]]:
    return [(0, 0), (48 * FT, 0), (48 * FT, 32 * FT), (0, 32 * FT)]


def _gable_project(ridge_axis: str = "x") -> tuple[Project, str]:
    p = Project.create("roof-gable", vcs=False)
    p.add_level("L1", 0)
    rid = p.create_gable_roof(
        level="L1",
        footprint=_footprint_48x32(),
        ridge_axis=ridge_axis,
        plate_mm=PLATE,
        pitch=0.5,
        overhang_mm=OVERHANG,
        name="Roof-Main",
    )
    return p, rid


def test_gable_two_planes_ridge_z_hand_calc():
    p, rid = _gable_project()
    el = p.model.get_element(rid)
    assert el.category == "roof"
    assert el.params["kind"] == "gable"
    planes = el.params["planes"]
    assert len(planes) == 2
    # ridge z = plate + pitch * run = 10' + 0.5*16' = 18'
    assert abs(float(el.params["ridge_z_mm"]) - RIDGE) < 0.1
    for pl in planes:
        assert abs(float(pl["ridge_z_mm"]) - RIDGE) < 0.1
        assert abs(float(pl["slope"]) - 0.5) < 1e-9
        # eave drops below plate over the 18" overhang: plate - 0.5*457.2
        assert abs(float(pl["eave_z_mm"]) - (PLATE - 0.5 * OVERHANG)) < 0.1
        poly = pl["polygon_mm"]
        assert len(poly) == 4
        assert all(len(q) == 3 for q in poly)
        # eave edges extend 18" past the footprint
        xs = [float(q[0]) for q in poly]
        assert min(xs) == -OVERHANG and max(xs) == 48 * FT + OVERHANG
    # ridge line stored for downstream consumers
    (r0, r1) = el.params["ridge_line_mm"]
    assert abs(float(r0[2]) - RIDGE) < 0.1 and abs(float(r1[2]) - RIDGE) < 0.1
    # opposite downhill directions
    d0 = planes[0]["downhill_dir"]
    d1 = planes[1]["downhill_dir"]
    assert abs(d0[0] + d1[0]) < 1e-9 and abs(d0[1] + d1[1]) < 1e-9


def test_gable_undo_removes_roof():
    p, rid = _gable_project()
    assert p.model.stats().get("roof") == 1
    p.undo()
    assert p.model.stats().get("roof", 0) == 0


def test_gable_gltf_mesh_valid_and_above_plate(tmp_path: Path):
    from llmbim_drawings.deliverables import _verify_gltf_strict

    p, _rid = _gable_project()
    # a wall so the scene isn't roof-only
    p.create_wall(level="L1", start=(0, 0), end=(48 * FT, 0), thickness_mm=140, height_mm=PLATE)
    out = tmp_path / "model.gltf"
    p.export_gltf(out)
    v = _verify_gltf_strict(out)
    assert v["gltf_valid"], v["failures"]
    data = json.loads(out.read_text(encoding="utf-8"))
    names = [m.get("name") for m in data.get("materials") or []]
    assert "roof" in names
    # glTF Y (metres) is elevation: bbox must reach the ridge above the plate
    max_y = float(data["accessors"][0]["max"][1])
    assert max_y > PLATE / 1000.0
    assert abs(max_y - RIDGE / 1000.0) < 1e-3


def test_gable_elevation_silhouette_reaches_above_walls(tmp_path: Path):
    # ridge along Y → S elevation views the gable end (triangle silhouette)
    p, _rid = _gable_project(ridge_axis="y")
    p.create_wall(level="L1", start=(0, 0), end=(48 * FT, 0), thickness_mm=140, height_mm=PLATE)
    from llmbim_drawings.section import render_elevation_svg

    svg = render_elevation_svg(p.model, "S")
    assert 'class="roof-elev"' in svg
    m = re.search(r'<g class="roof-elev".*?</g>', svg, re.DOTALL)
    assert m is not None
    polys = re.findall(r'points="([^"]+)"', m.group(0))
    assert len(polys) == 2  # both gable planes projected
    # SVG y decreases with elevation: the roof apex must sit above wall tops
    roof_min_y = min(
        float(pt.split(",")[1]) for poly in polys for pt in poly.split()
    )
    walls = re.search(r'<g class="walls".*?</g>', svg, re.DOTALL)
    assert walls is not None
    wall_min_y = min(float(v) for v in re.findall(r'<rect x="[^"]+" y="([^"]+)"', walls.group(0)))
    assert roof_min_y < wall_min_y


def test_gable_section_sloped_lines():
    from llmbim_drawings.section import render_section_svg

    p, _rid = _gable_project(ridge_axis="x")
    p.create_wall(level="L1", start=(24 * FT, 0), end=(24 * FT, 32 * FT), thickness_mm=140, height_mm=PLATE)
    # cut perpendicular to the ridge → both planes crossed as sloped lines
    svg = render_section_svg(p.model, (24 * FT, -2000), (24 * FT, 32 * FT + 2000))
    assert 'class="roof-section"' in svg
    m = re.search(r'<g class="roof-section".*?</g>', svg, re.DOTALL)
    assert m is not None
    lines = re.findall(
        r'<line x1="([^"]+)" y1="([^"]+)" x2="([^"]+)" y2="([^"]+)"', m.group(0)
    )
    assert len(lines) >= 4  # 2 planes x (top + underside)
    sloped = [ln for ln in lines if abs(float(ln[1]) - float(ln[3])) > 1.0]
    assert sloped, lines


def test_gable_ifc_roof_entity(tmp_path: Path):
    p, _rid = _gable_project()
    out = tmp_path / "model.ifc"
    p.export_ifc(out)
    text = out.read_text(encoding="utf-8")
    assert "IFCROOF(" in text
    assert ".GABLE_ROOF." in text
    assert "IFCFACETEDBREP(" in text
    assert "IFCCLOSEDSHELL(" in text


def test_shed_roof_single_plane_slope():
    p = Project.create("roof-shed", vcs=False)
    p.add_level("L1", 0)
    rid = p.create_shed_roof(
        level="L1",
        footprint=[(0, 0), (18 * FT, 0), (18 * FT, 16 * FT), (0, 16 * FT)],
        high_side="N",
        plate_low_mm=10 * FT,
        plate_high_mm=12 * FT,
        overhang_mm=OVERHANG,
    )
    el = p.model.get_element(rid)
    assert el.params["kind"] == "shed"
    planes = el.params["planes"]
    assert len(planes) == 1
    slope = (12 * FT - 10 * FT) / (16 * FT)
    assert abs(float(el.params["slope"]) - slope) < 1e-9
    poly = planes[0]["polygon_mm"]
    # high (N) eave continues the slope past the plate; low eave drops below
    zs = {round(float(q[2]), 3) for q in poly}
    assert round(10 * FT - slope * OVERHANG, 3) in zs
    assert round(12 * FT + slope * OVERHANG, 3) in zs


def test_roof_plane_low_level():
    p = Project.create("roof-plane", vcs=False)
    p.add_level("L1", 0)
    rid = p.create_roof_plane(
        level="L1",
        polygon=[(0, 0, 3000), (6000, 0, 3000), (6000, 4000, 5000), (0, 4000, 5000)],
    )
    el = p.model.get_element(rid)
    assert el.params["kind"] == "plane"
    assert len(el.params["planes"]) == 1
    assert abs(float(el.params["slope"]) - 2000.0 / 4000.0) < 1e-9


def test_cross_gable_valley_lines():
    # Bay-2 style cross-gable: perpendicular ridge, footprints overlap → valleys
    p, main_id = _gable_project(ridge_axis="x")
    bay_id = p.create_gable_roof(
        level="L1",
        footprint=[(16 * FT, -2 * FT), (32 * FT, -2 * FT), (32 * FT, 16 * FT), (16 * FT, 16 * FT)],
        ridge_axis="y",
        plate_mm=PLATE,
        pitch=0.5,
        overhang_mm=OVERHANG,
        name="Roof-Bay2",
    )
    bay = p.model.get_element(bay_id)
    valleys = bay.params["valley_lines_mm"]
    assert valleys, "cross-gable over an existing roof must produce valley lines"
    assert main_id in bay.params["valley_with"]
    for seg in valleys:
        assert len(seg) == 2 and all(len(pt) == 3 for pt in seg)
        (x0, y0, z0), (x1, y1, z1) = seg
        assert math.hypot(x1 - x0, y1 - y0) > 50.0
        # valley z stays within the roof band (eave..ridge, small tolerance)
        for z in (z0, z1):
            assert PLATE - 0.5 * OVERHANG - 1.0 <= z <= RIDGE + 1.0
    # the standalone main roof carries no valleys (it came first)
    assert p.model.get_element(main_id).params["valley_lines_mm"] == []


def test_roof_ops_registered():
    p = Project.create("roof-ops", vcs=False)
    p.add_level("L1", 0)
    r = p.op(
        "create_gable_roof",
        level="L1",
        footprint=[[0, 0], [10000, 0], [10000, 8000], [0, 8000]],
        plate_mm=3000,
        pitch=0.5,
        overhang_mm=300,
    )
    assert r["plane_count"] == 2
    r2 = p.op(
        "create_shed_roof",
        level="L1",
        footprint=[[12000, 0], [18000, 0], [18000, 8000], [12000, 8000]],
        high_side="E",
        plate_low_mm=3000,
        plate_high_mm=3600,
    )
    assert r2["plane_count"] == 1
    r3 = p.op(
        "create_roof_plane",
        level="L1",
        polygon=[[0, 0, 3000], [4000, 0, 3000], [4000, 3000, 4200], [0, 3000, 4200]],
    )
    assert r3["plane_count"] == 1
    ops = {o["name"] for o in p.ops()}
    assert {"create_gable_roof", "create_shed_roof", "create_roof_plane"} <= ops
