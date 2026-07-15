"""Elevation DXF export for CAD handoff."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.dxf_export import export_elevation_dxf


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
