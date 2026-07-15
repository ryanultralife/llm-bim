"""IFC export acceptance (pure SPF writer — no ifcopenshell required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmbim import Project

pytestmark = pytest.mark.wp_ifc


def test_export_ifc_spf(tmp_path: Path) -> None:
    from llmbim_ifc import export_ifc

    p = Project.create("IFC House")
    p.add_level("L1", 0)
    p.create_wall(
        level="L1", start=(0, 0), end=(5000, 0), thickness_mm=200, height_mm=3000
    )
    out = tmp_path / "model.ifc"
    export_ifc(p.model, out)
    text = out.read_text(encoding="utf-8")
    assert out.stat().st_size > 100
    assert "ISO-10303-21" in text
    assert "IFCPROJECT" in text
    assert "IFCWALLSTANDARDCASE" in text or "IFCWALL" in text


def test_export_ifc_optional_ifcopenshell(tmp_path: Path) -> None:
    ifcopenshell = pytest.importorskip("ifcopenshell")
    p = Project.create("IFC2")
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(3000, 0), thickness_mm=200, height_mm=2700)
    out = tmp_path / "m.ifc"
    p.export_ifc(out)
    f = ifcopenshell.open(str(out))
    assert f.by_type("IfcProject")
