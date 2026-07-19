"""Deliverables pack: IFC, STEP, construction, parts."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project


def _mini_facility() -> Project:
    p = Project.create("Mini Facility")
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=10000, d=8000, height_mm=3000, thickness_mm=200, name_prefix="B"
    )
    p.create_slab(
        level="L1",
        polygon=[(0, 0), (10000, 0), (10000, 8000), (0, 8000)],
        thickness_mm=200,
    )
    p.create_room(
        level="L1",
        name="Hall",
        boundary=[(0, 0), (10000, 0), (10000, 8000), (0, 8000)],
    )
    p.create_equipment_box(
        level="L1",
        origin=(4000, 3000),
        size=(2000, 1000, 1500),
        name="Skid-1",
        kind="skid",
        centered=True,
    )
    return p


def test_deliverables_pack(tmp_path: Path) -> None:
    p = _mini_facility()
    m = p.export_deliverables(tmp_path / "pack", plan_scale=0.05)
    assert (tmp_path / "pack" / "model.llmbim.json").is_file()
    assert (tmp_path / "pack" / "model.ifc").is_file()
    assert (tmp_path / "pack" / "model.gltf").is_file()
    assert (tmp_path / "pack" / "model.step").is_file()
    ifc = (tmp_path / "pack" / "model.ifc").read_text(encoding="utf-8")
    assert "IFCPROJECT" in ifc
    assert "IFCWALL" in ifc or "IFCWALLSTANDARDCASE" in ifc
    step = (tmp_path / "pack" / "model.step").read_text(encoding="utf-8")
    assert "ISO-10303-21" in step
    assert "MANIFOLD_SOLID_BREP" in step
    assert (tmp_path / "pack" / "construction" / "SHEET_INDEX.json").is_file()
    assert (tmp_path / "pack" / "construction" / "A-101_plan.svg").is_file()
    assert (tmp_path / "pack" / "parts" / "PARTS_INDEX.json").is_file()
    assert m["project"] == "Mini Facility"


def test_verify_reflects_late_written_artifacts(tmp_path: Path) -> None:
    """VERIFY.json / checksums must run AFTER index.html + viewer3d.html are
    written — a regression guard for the ordering bug where they were computed
    before those files existed and reported has_index_html/has_viewer3d=false."""
    import json

    p = _mini_facility()
    m = p.export_deliverables(tmp_path / "pack")
    out = tmp_path / "pack"
    assert (out / "index.html").is_file()
    assert (out / "viewer3d.html").is_file()
    verify = json.loads((out / "VERIFY.json").read_text(encoding="utf-8"))
    assert verify["has_index_html"] is True
    assert verify["has_viewer3d"] is True
    # checksums cover the late-written HTML viewers, exclude the roll-up zip
    ck = m["checksums_sha256"]
    assert "index.html" in ck
    assert "viewer3d.html" in ck
    assert not any(k.endswith(".zip") for k in ck)


def test_part_step_files(tmp_path: Path) -> None:
    p = Project.create("PartOnly")
    p.add_level("Bench", 0)
    p.create_equipment_box(
        level="Bench",
        origin=(0, 0),
        size=(500, 320, 320),
        name="Shell",
        kind="shell",
        centered=True,
    )
    p.export_part_pack(tmp_path / "parts", scale=0.5)
    steps = list((tmp_path / "parts" / "step").glob("*.step"))
    assert len(steps) >= 1
    assert "MANIFOLD_SOLID_BREP" in steps[0].read_text(encoding="utf-8")


def test_dimension_labels_stay_on_canvas(tmp_path: Path) -> None:
    """Plan/section/elevation SVGs must keep their dimension text inside the
    viewBox. Regression: a fixed screen-space dim offset exceeded the margin so
    every overall dimension rendered off-canvas (invisible)."""
    import re

    p = _mini_facility()
    out = tmp_path / "pack"
    p.export_deliverables(out)
    for rel in ("views/plan_L1.svg", "views/section.svg", "views/elev_S.svg"):
        svg_path = out / rel
        if not svg_path.is_file():
            continue
        svg = svg_path.read_text(encoding="utf-8")
        vb = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"', svg)
        assert vb, f"{rel}: no viewBox"
        vx, vy, vw, vh = (float(g) for g in vb.groups())
        # dimension labels carry a metric unit suffix (" m")
        for mt in re.finditer(r'<text x="([-\d.]+)" y="([-\d.]+)"[^>]*>([^<]*\bm)</text>', svg):
            x, y = float(mt.group(1)), float(mt.group(2))
            assert vx - 1 <= x <= vx + vw + 1 and vy - 1 <= y <= vy + vh + 1, (
                f"{rel}: dimension {mt.group(3)!r} at ({x},{y}) outside "
                f"viewBox [{vx},{vy},{vw},{vh}]"
            )
