"""glTF export smoke."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project


def test_gltf_export(tmp_path: Path) -> None:
    p = Project.create("G")
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(4000, 0), thickness_mm=200, height_mm=3000)
    out = tmp_path / "m.gltf"
    p.export_gltf(out)
    text = out.read_text(encoding="utf-8")
    assert "meshes" in text
    assert out.stat().st_size > 100


def test_gltf_includes_pipe_and_fitting(tmp_path: Path) -> None:
    """MEP markers must appear in 3D review mesh (vision multi-trade pack)."""
    p = Project.create("MEP-G", vcs=False)
    p.add_level("L1", 0)
    p.place_pipe(level="L1", nps="3/4", start=(0, 0), end=(5000, 0), material="copper")
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(0, 0), material="copper")
    p.place_part(level="L1", kind="toilet", origin=(2000, 1000))
    out = tmp_path / "mep.gltf"
    p.export_gltf(out)
    # more vertices than a single tiny fallback triangle
    import json

    data = json.loads(out.read_text(encoding="utf-8"))
    n_verts = data["accessors"][0]["count"]
    assert n_verts >= 24  # at least 3 boxes × 8 corners
