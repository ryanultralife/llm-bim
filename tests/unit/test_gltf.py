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
