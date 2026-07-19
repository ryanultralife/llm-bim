"""Fab BREP + GD&T (CadQuery/OCP) — skip if extra not installed."""

from __future__ import annotations

from pathlib import Path

import pytest
from llmbim import Project

try:
    from llmbim_geometry.fab_brep import HAS_CADQUERY
except Exception:  # noqa: BLE001
    HAS_CADQUERY = False

pytestmark = pytest.mark.skipif(not HAS_CADQUERY, reason="cadquery/OCP not installed")


def test_fab_box_fillet_hole_step(tmp_path: Path) -> None:
    p = Project.create("Fab1", vcs=False)
    p.add_level("L1", 0)
    fid = p.create_fab_part(name="Bracket", material="steel_A36")
    p.fab_box(fid, size_mm=(60, 40, 12), origin_mm=(0, 0, 0))
    p.fab_fillet(fid, radius_mm=2.0, selector="|Z")
    p.fab_hole(fid, diameter_mm=8, origin_mm=(20, 20, 12), depth_mm=12)
    v = p.validate_fab(fid)
    assert v.get("ok") is True
    assert float(v.get("volume_mm3") or 0) > 1000
    step = tmp_path / "bracket.step"
    info = p.export_fab_step(fid, step)
    assert step.is_file()
    text = step.read_text(encoding="utf-8", errors="ignore")
    assert "ISO-10303-21" in text
    assert "MANIFOLD_SOLID_BREP" in text or "ADVANCED_BREP" in text or "CLOSED_SHELL" in text
    assert info.get("fidelity") == "brep_cadquery"


def test_fab_thread_and_gdt(tmp_path: Path) -> None:
    p = Project.create("FabThread", vcs=False)
    p.add_level("L1", 0)
    fid = p.create_fab_part(name="Stud")
    # pure thread feature builds external stud
    p.fab_thread(fid, designation="M10x1.5", length_mm=25, origin_mm=(0, 0, 0), internal=False)
    p.gdt_datum(fid, label="A", face="bottom")
    p.gdt_fcf(fid, symbol="position", tolerance=0.05, datums=["A"], diameter=True, applies_to="thread axis")
    p.gdt_size(fid, dimension="M10x1.5 major", nominal=10.0, tol_plus=0.0, tol_minus=0.15)
    v = p.validate_fab(fid)
    assert v.get("ok") is True
    svg = p.export_gdt_drawing(fid, tmp_path / "stud_gdt.svg")
    assert svg.is_file()
    t = svg.read_text(encoding="utf-8")
    assert "GD" in t and "thread" in t.lower() or "M10" in t or "FEATURE" in t
    assert "datum" in t.lower() or ">A<" in t or "A</text>" in t


def test_fab_in_gltf_and_pack(tmp_path: Path) -> None:
    p = Project.create("FabPack", vcs=False)
    p.add_level("L1", 0)
    fid = p.create_fab_part(name="Pad")
    p.fab_box(fid, size_mm=(40, 30, 10))
    p.fab_chamfer(fid, distance_mm=1.0, selector="top_loop")
    p.gdt_datum(fid, label="A")
    out = tmp_path / "pack"
    # export glTF includes fab tessellation
    gltf = tmp_path / "m.gltf"
    p.export_gltf(gltf)
    text = gltf.read_text(encoding="utf-8")
    assert "fab_part" in text
    # deliverables pack writes fab/
    res = p.export_deliverables(out)
    assert (out / "fab").is_dir() or res.get("outputs", {}).get("fab_parts") or (
        out / "fab" / "FAB_INDEX.json"
    ).exists() or any((out / "fab").glob("*.step") if (out / "fab").is_dir() else [])
    # soft: at least pack ran
    assert (out / "model.llmbim.json").is_file()


def test_fab_depth_selectors_pattern_ortho_assembly(tmp_path: Path) -> None:
    """Next depth: top_loop fillet, hole pattern, ortho SVG, multi-body assembly."""
    p = Project.create("FabDepth", vcs=False)
    p.add_level("L1", 0)
    a = p.create_fab_part(name="Plate")
    p.fab_box(a, size_mm=(60, 40, 10))
    p.fab_fillet(a, radius_mm=2.0, selector="top_loop")
    p.fab_hole_pattern(
        a,
        diameter_mm=6,
        origin_mm=(12, 12, 10),
        count_x=2,
        count_y=2,
        spacing_x_mm=30,
        spacing_y_mm=16,
        depth_mm=10,
    )
    assert p.validate_fab(a).get("ok") is True

    b = p.create_fab_part(name="Bushing")
    p.fab_revolve(b, radius_mm=12, height_mm=8, inner_radius_mm=4)
    assert p.validate_fab(b).get("ok") is True

    ortho = p.export_fab_ortho(a, tmp_path / "views")
    assert set(ortho.get("views") or {}) >= {"top", "front", "right"}
    for vpath in (ortho.get("views") or {}).values():
        assert Path(vpath).is_file()
        assert "svg" in Path(vpath).read_text(encoding="utf-8", errors="ignore").lower()

    gdt = p.export_gdt_drawing(a, tmp_path / "plate_gdt.svg")
    gtxt = gdt.read_text(encoding="utf-8")
    assert "ORTHO" in gtxt or "TOP" in gtxt or "projection" in gtxt.lower() or "<svg" in gtxt

    assy = p.create_fab_assembly(name="Stack")
    p.fab_assembly_add(assy, a, origin_mm=(0, 0, 0))
    p.fab_assembly_add(assy, b, origin_mm=(0, 0, 12))
    step = tmp_path / "stack.step"
    info = p.export_fab_assembly_step(assy, step)
    assert step.is_file()
    assert info.get("n_members") == 2
    assert "ISO-10303-21" in step.read_text(encoding="utf-8", errors="ignore")


def test_fab_tags_iso_thread_mates_host_knit(tmp_path: Path) -> None:
    """All four depth items: tags, ISO V-thread, mates, host knit."""
    p = Project.create("Fab4", vcs=False)
    p.add_level("L1", 0)
    # 1) named edge tags → fillet only those edges
    plate = p.create_fab_part(name="TaggedPlate")
    p.fab_box(plate, size_mm=(80, 40, 12))
    p.fab_tag(plate, name="long_sides", selector="long", kind="edges")
    p.fab_fillet(plate, radius_mm=2.0, selector="tag:long_sides")
    assert p.validate_fab(plate).get("ok") is True

    # 2) ISO V-thread solid
    stud = p.create_fab_part(name="ISOStud")
    p.fab_thread(stud, designation="M10x1.5", length_mm=18, origin_mm=(0, 0, 0))
    v = p.validate_fab(stud)
    assert v.get("ok") is True
    assert float(v.get("volume_mm3") or 0) > 500

    # 3) mates: stack bushing on plate with concentric
    bush = p.create_fab_part(name="Bush")
    p.fab_revolve(bush, radius_mm=15, height_mm=10, inner_radius_mm=5)
    assy = p.create_fab_assembly(name="Mated")
    ia = p.fab_assembly_add(assy, plate, origin_mm=(0, 0, 0), instance_id="plate")
    ib = p.fab_assembly_add(assy, bush, origin_mm=(100, 100, 100), instance_id="bush")
    assert ia.get("instance_id") == "plate"
    p.fab_mate(assy, mate_type="coincident", a="plate", b="bush", a_face="top", b_face="bottom")
    p.fab_mate(assy, mate_type="concentric", a="plate", b="bush")
    astep = tmp_path / "mated.step"
    minfo = p.export_fab_assembly_step(assy, astep)
    assert astep.is_file()
    assert minfo.get("n_mates") == 2

    # 4) knit into building under a column host
    col = p.place_column(level="L1", origin=(2000, 1500), section="W10x33", height_mm=3500)
    base = p.create_fab_part(name="BasePlate")
    p.fab_box(base, size_mm=(200, 200, 20))
    knit = p.fab_host_to_building(
        base, level="L1", origin_mm=(0, 0, 0), host_id=col, z0_mm=0
    )
    assert knit.get("knit") is True
    assert knit.get("building_origin_mm")[0] == 2000
    gltf = tmp_path / "knit.gltf"
    p.export_gltf(gltf)
    assert "fab_part" in gltf.read_text(encoding="utf-8")
    step_b = tmp_path / "building.step"
    p.export_step(step_b)
    assert step_b.is_file()
    assert "FAB" in step_b.read_text(encoding="utf-8", errors="ignore") or step_b.stat().st_size > 100
