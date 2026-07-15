"""WP-IFC acceptance tests — excluded from default pytest.

Claude: pip install -e ".[ifc]"; pytest -m wp_ifc
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llmbim import Project

pytestmark = pytest.mark.wp_ifc


def test_export_ifc_opens(tmp_path: Path) -> None:
    ifcopenshell = pytest.importorskip("ifcopenshell")

    from llmbim_ifc import export_ifc

    p = Project.create("IFC House")
    p.add_level("L1", 0)
    p.create_wall(
        level="L1", start=(0, 0), end=(5000, 0), thickness_mm=200, height_mm=3000
    )
    out = tmp_path / "model.ifc"
    export_ifc(p.model, out)
    assert out.is_file() and out.stat().st_size > 100
    f = ifcopenshell.open(str(out))
    walls = f.by_type("IfcWall")
    assert len(walls) >= 1
