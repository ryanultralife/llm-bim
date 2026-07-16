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
    p.fab_chamfer(fid, distance_mm=1.0, selector=">Z")
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
