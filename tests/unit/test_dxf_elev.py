"""Elevation + section DXF export for CAD handoff."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.dxf_export import export_elevation_dxf, export_section_dxf


def test_elevation_dxf_walls_and_mep(tmp_path: Path):
    p = Project.create("elev-dxf", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 3500)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3500)
    p.place_pipe(level="L1", nps="2", start=(0, 1000), end=(5000, 1000), material="copper")
    p.place_riser(level="L1", nps="2", origin=(2500, 1000), to_level="L2", material="fire")
    p.place_duct(level="L1", start=(0, 2000), end=(4000, 2000), width_mm=400, height_mm=250)
    dxf = tmp_path / "elev_S.dxf"
    export_elevation_dxf(p.model, "S", dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "WALLS" in text
    assert "PIPE-CU" in text or "PIPE-FP" in text
    assert "DUCT" in text
    assert "LEVELS" in text
    assert "L1" in text
    assert "LINE" in text


def test_elevation_dxf_columns_and_beams(tmp_path: Path):
    p = Project.create("elev-struct", vcs=False)
    p.add_level("L1", 0)
    p.place_column(level="L1", origin=(2000, 1000), section="W10x33", height_mm=3500)
    p.place_beam(level="L1", start=(0, 1000), end=(8000, 1000), section="W12x26", z0_mm=3000)
    dxf = tmp_path / "elev_S.dxf"
    export_elevation_dxf(p.model, "S", dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "COLUMNS" in text
    assert "BEAMS" in text
    assert "W10x33" in text
    assert "W12x26" in text


def test_elevation_dxf_doors_and_windows(tmp_path: Path):
    p = Project.create("elev-open", vcs=False)
    p.add_level("L1", 0)
    w = p.create_wall(
        level="L1", start=(0, 0), end=(10000, 0), thickness_mm=200, height_mm=3000
    )
    p.place_door(
        host=w,
        offset_mm=2000,
        width_mm=900,
        height_mm=2100,
        type_id="D-HM-36",
        fire_rating="90 min",
    )
    p.place_window(
        host=w,
        offset_mm=5000,
        width_mm=1200,
        height_mm=900,
        sill_mm=900,
        type_id="WIN-VIEW",
    )
    dxf = tmp_path / "elev_S.dxf"
    export_elevation_dxf(p.model, "S", dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "DOORS" in text
    assert "WINDOWS" in text
    assert "HM-36" in text or "D-HM" in text
    assert "90m" in text or "90" in text


def test_section_dxf_cut_and_mep(tmp_path: Path):
    p = Project.create("sec-dxf", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    p.create_wall(level="L1", start=(0, 6000), end=(8000, 6000), thickness_mm=200, height_mm=3000)
    p.place_pipe(level="L1", nps="2", start=(0, 3000), end=(8000, 3000), material="copper")
    p.place_duct(level="L1", start=(0, 3000), end=(6000, 3000), width_mm=500, height_mm=300)
    p.place_riser(level="L1", nps="2", origin=(4000, 3000), z0_mm=0, z1_mm=3000, material="fire")
    dxf = tmp_path / "section.dxf"
    # NS cut through mid
    export_section_dxf(p.model, (4000, -1000), (4000, 7000), dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "WALLS" in text
    assert "LEVELS" in text
    assert "SECTION CUT" in text
    assert "PIPE-CU" in text or "PIPE-FP" in text or "DUCT" in text
    assert "LINE" in text


def test_section_dxf_columns_and_beams(tmp_path: Path):
    p = Project.create("sec-struct", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(10000, 0), thickness_mm=200, height_mm=3500)
    # column on cut line x=5000
    p.place_column(level="L1", origin=(5000, 2000), section="W10x33", height_mm=3500)
    # beam crossing cut
    p.place_beam(level="L1", start=(0, 2000), end=(10000, 2000), section="W12x26", z0_mm=3000)
    dxf = tmp_path / "section.dxf"
    export_section_dxf(p.model, (5000, -1000), (5000, 5000), dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "COLUMNS" in text
    assert "BEAMS" in text
    assert "W10x33" in text
    assert "W12x26" in text


def test_section_dxf_doors_and_windows(tmp_path: Path):
    p = Project.create("sec-open", vcs=False)
    p.add_level("L1", 0)
    # wall crosses NS cut at x=4000
    w = p.create_wall(
        level="L1", start=(0, 2000), end=(8000, 2000), thickness_mm=200, height_mm=3000
    )
    p.place_door(
        host=w,
        offset_mm=3500,
        width_mm=900,
        height_mm=2100,
        type_id="D-HM-36",
        fire_rating="90 min",
    )
    p.place_window(
        host=w,
        offset_mm=1000,
        width_mm=1000,
        height_mm=900,
        sill_mm=900,
        type_id="WIN-VIEW",
    )
    dxf = tmp_path / "section.dxf"
    # cut along Y through wall mid
    export_section_dxf(p.model, (4000, -1000), (4000, 5000), dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "DOORS" in text
    assert "WINDOWS" in text
    assert "HM-36" in text or "D-HM" in text
