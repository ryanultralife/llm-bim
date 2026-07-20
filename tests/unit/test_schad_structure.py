"""WP-SCHAD-S4 acceptance — structural catalogs + Schad structure.

Covers: W16x40 in the steel catalog with published AISC section data (matches
the basis beam scalars), HSS6x6x1/4 posts, HDR-1/HDR-2 header types, typed
Simpson Strong-Wall panels + shear wall schedule, the multi-plate
WALL_EXCEEDS_STORY fix, and the Schad build placing the structure. Every
project dimension asserted here is read from the basis modules
(projects/schad/schad_design_basis.py / schad_structural.py) — the only
number source. Schedules are carried design-development data, not
engineering claims.
"""

from __future__ import annotations

import pytest
from llmbim import Project
from llmbim_core.material_lists import shear_wall_schedule, steel_takeoff
from llmbim_core.parts_catalog import PARTS, resolve_part_id
from llmbim_core.rules import run_design_rules
from llmbim_core.types_catalog import (
    DEFAULT_HEADER_TYPES,
    DEFAULT_SHEARWALL_TYPES,
    catalog_dict,
)

import projects.schad.build_llmbim  # noqa: F401  (adds projects/schad to sys.path)
import projects.schad.schad_design_basis as basis
import projects.schad.schad_structural as struct
from examples.schad_build import build_schad_model

FT_TO_MM = 304.8
IN_TO_MM = 25.4
LB_FT_TO_KG_M = 1.48816


@pytest.fixture(scope="module")
def project():
    return build_schad_model()


def _by_category(project, category):
    return [el for el in project.model.elements if el.category == category]


# --- 1. steel catalog -------------------------------------------------------


def test_w16x40_catalog_properties_match_basis():
    part = PARTS["PT-STL-W16x40"]
    specs = part.specs or {}
    s = basis.build_scalars()
    assert specs["section"] == s["beam"] == "W16x40"
    # catalog carries the designation weight (40 plf [RB/BOM] → kg/m)
    assert specs["weight_plf"] == struct.W16X40["wt_plf"]
    assert specs["weight_kg_m"] == pytest.approx(40.0 * LB_FT_TO_KG_M, rel=0.01)
    # AISC published dims agree with the basis scalars (depth 16", bf 7")
    assert specs["depth_mm"] == pytest.approx(s["beam_depth"] * FT_TO_MM)
    assert specs["bf_mm"] == pytest.approx(s["beam_width"] * FT_TO_MM)
    # section properties agree with the structural record module
    assert specs["Zx_in3"] == struct.W16X40["Zx_in3"]
    assert specs["Ix_in4"] == struct.W16X40["Ix_in4"]
    assert specs["Fy_ksi"] == struct.W16X40["Fy_ksi"]
    assert part.primary_material_id == "steel_A992"


def test_hss_post_section_in_catalog():
    # basis post member [BOM]: 'HSS 6x6x1/4' → catalog HSS6x6x1/4
    member = struct.post_check()["member"].replace(" ", "")
    pid = resolve_part_id(section=member)
    assert pid is not None and pid in PARTS
    specs = PARTS[pid].specs or {}
    assert specs["section"] == member
    # AISC 19.02 plf published nominal weight
    assert specs["weight_kg_m"] == pytest.approx(19.02 * LB_FT_TO_KG_M, rel=0.01)


def test_steel_takeoff_w16x40_weight_from_catalog():
    p = Project.create("takeoff", vcs=False)
    p.add_level("L1", 0)
    p.place_beam(level="L1", start=(0, 0), end=(10000, 0), section="W16x40", z0_mm=2600)
    rows = [r for r in steel_takeoff(p.model) if r.get("section") == "W16x40"]
    assert len(rows) == 1
    r = rows[0]
    assert r["unit"] == "m"
    assert r["qty"] == pytest.approx(10.0, rel=1e-3)
    # weight comes from the catalog entry (40 plf → kg/m), not a guess
    assert r["weight_kg_m"] == pytest.approx(40.0 * LB_FT_TO_KG_M, rel=0.001)
    assert r["mass_kg"] == pytest.approx(10.0 * 40.0 * LB_FT_TO_KG_M, rel=0.001)


# --- 2. header + shear wall type registries ---------------------------------


def test_header_types_registered_per_record():
    sched = {row["mark"]: row for row in struct.header_schedule()}
    for mark in ("HDR-1", "HDR-2"):
        assert mark in DEFAULT_HEADER_TYPES
        assert DEFAULT_HEADER_TYPES[mark].member == sched[mark]["member"].split(" [")[0]
    hdr2 = DEFAULT_HEADER_TYPES["HDR-2"]
    assert hdr2.ply == 2
    assert hdr2.depth_mm == pytest.approx(16 * IN_TO_MM)
    assert hdr2.width_mm == pytest.approx(2 * 1.75 * IN_TO_MM)
    assert hdr2.max_span_mm == pytest.approx(12 * FT_TO_MM)  # 12' OH doors [RB]
    hdr1 = DEFAULT_HEADER_TYPES["HDR-1"]
    assert hdr1.ply == 1
    assert hdr1.depth_mm == pytest.approx(7.25 * IN_TO_MM)  # dressed 4x8
    # registry is exported to agents via the catalog dict
    cat = catalog_dict()
    assert set(cat["header_types"]) >= {"HDR-1", "HDR-2"}
    assert set(cat["shear_wall_types"]) >= {"SSW24x9", "SSW24x12"}


def test_shear_wall_types_match_basis():
    s = basis.build_scalars()
    models = {sw["model"]: sw for sw in basis.build_structure()["strong_walls"]}
    assert set(models) == {"SSW24x9", "SSW24x12"}
    for model_name, sw in models.items():
        swt = DEFAULT_SHEARWALL_TYPES[model_name]
        assert swt.model == model_name
        assert swt.manufacturer == "Simpson Strong-Tie"
        assert swt.width_mm == pytest.approx(s["ssw_w"] * FT_TO_MM)
        assert swt.thickness_mm == pytest.approx(s["ssw_t"] * FT_TO_MM)
        assert swt.height_mm == pytest.approx(sw["h"] * FT_TO_MM)
    assert DEFAULT_SHEARWALL_TYPES["SSW24x9"].mark != DEFAULT_SHEARWALL_TYPES["SSW24x12"].mark


# --- 3. multi-plate WALL_EXCEEDS_STORY fix ----------------------------------


def _story_project(tall_wall_params=None):
    p = Project.create("rule", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 3048)  # 10' story
    eid = p.create_wall(
        level="L1", start=(0, 0), end=(6000, 0), thickness_mm=150, height_mm=4267
    )
    for k, v in (tall_wall_params or {}).items():
        p.op("set_param", id=eid, key=k, value=v)
    return p, eid


def test_multi_plate_wall_does_not_false_flag():
    for declared in (
        {"multi_plate": True},
        {"balloon_framed": True},
        {"plate_height_mm": 4267.2},
    ):
        p, eid = _story_project(declared)
        findings = run_design_rules(p.model)
        errors = [f for f in findings if f["rule"] == "WALL_EXCEEDS_STORY"]
        assert not errors, declared
        # still surfaced as an informational note, not silently dropped
        infos = [f for f in findings if f["rule"] == "WALL_MULTI_PLATE"]
        assert infos and infos[0]["severity"] == "info" and infos[0]["element_id"] == eid


def test_genuinely_tall_wall_still_flags():
    p, eid = _story_project()
    findings = run_design_rules(p.model)
    errors = [f for f in findings if f["rule"] == "WALL_EXCEEDS_STORY"]
    assert len(errors) == 1 and errors[0]["severity"] == "error"
    assert errors[0]["element_id"] == eid
    # an insufficient declaration (plate below actual height) still errors
    p2, _ = _story_project({"plate_height_mm": 3200.0})
    assert any(f["rule"] == "WALL_EXCEEDS_STORY" for f in run_design_rules(p2.model))


# --- 4. Schad build integration ---------------------------------------------


def test_schad_beams_and_posts_placed_per_basis(project):
    structure = basis.build_structure()
    beams = _by_category(project, "beam")
    assert len(beams) == len(structure["beams"]) == 2
    for b in beams:
        assert b.params["section"] == basis.build_scalars()["beam"] == "W16x40"
        assert b.params["part_id"] == "PT-STL-W16x40"
    posts = _by_category(project, "column")
    # HSS posts under each beam end [BOM]
    post_section = struct.post_check()["member"].replace(" ", "")
    assert len(posts) == 2 * len(structure["beams"]) == 4
    for c in posts:
        assert c.params["section"] == post_section
    # posts stop at the underside of the beam (plate - beam depth, basis)
    s = basis.build_scalars()
    underside = (s["plate_main"] - s["beam_depth"]) * FT_TO_MM
    for c in posts:
        assert c.params["height_mm"] == pytest.approx(underside)


def test_schad_headers_placed_at_basis_openings(project):
    headers = _by_category(project, "header")
    doors = basis.build_doors()
    windows = basis.build_windows()
    assert len(headers) == len(doors) + len(windows) == 10
    oh_marks = {d["mark"] for d in doors if "OVERHEAD" in d["type"].upper()}
    hdr2 = [h for h in headers if h.type_id == "HDR-2"]
    hdr1 = [h for h in headers if h.type_id == "HDR-1"]
    assert {h.params["opening"] for h in hdr2} == oh_marks  # 12' OH doors
    assert len(hdr1) == len(headers) - len(oh_marks)
    for h in headers:
        assert h.type_id in DEFAULT_HEADER_TYPES
        assert h.params["member"] == DEFAULT_HEADER_TYPES[h.type_id].member
        # header spans the basis opening width
        opening = next(
            (d for d in [*doors, *windows] if d["mark"] == h.params["opening"]), None
        )
        assert opening is not None
        assert h.params["span_mm"] == pytest.approx(opening["w"] * FT_TO_MM)


def test_schad_shear_walls_typed_with_schedule(project):
    panels = [
        el
        for el in project.model.elements
        if el.params.get("kind") == "shear_panel"
    ]
    ssw_basis = basis.build_structure()["strong_walls"]
    assert len(panels) == len(ssw_basis) == 6
    by_model = {}
    for el in panels:
        assert el.type_id in DEFAULT_SHEARWALL_TYPES
        assert el.params["mark"] == DEFAULT_SHEARWALL_TYPES[el.type_id].mark
        by_model[el.type_id] = by_model.get(el.type_id, 0) + 1
    assert by_model == {"SSW24x9": 4, "SSW24x12": 2}  # [BOM]
    rows = shear_wall_schedule(project.model)
    assert [r["mark"] for r in rows] == ["SSW-1", "SSW-2"]
    assert {r["model"]: r["count"] for r in rows} == {"SSW24x9": 4, "SSW24x12": 2}
    for r in rows:
        assert r["size"]
        assert len(r["locations"]) == r["count"]
        # basis flags SSW stations as assumed — carried through, not hidden
        assert all(loc["pos_assumed"] for loc in r["locations"])


def test_schad_rules_no_wall_exceeds_story(project):
    findings = run_design_rules(project.model)
    assert not [f for f in findings if f["rule"] == "WALL_EXCEEDS_STORY"]
    # the tall Bay-2 / fire-separation walls surface as multi-plate info
    s = basis.build_scalars()
    tall = [w for w in basis.build_walls() if w["height"] > s["plate_main"]]
    infos = [f for f in findings if f["rule"] == "WALL_MULTI_PLATE"]
    assert len(infos) == len(tall)


def test_schad_pack_verify_ok(tmp_path):
    from projects.schad.build_llmbim import build_pack

    project, verify = build_pack(tmp_path / "schad_pack")
    assert verify.get("ok"), verify
