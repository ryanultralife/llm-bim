"""IFC export includes pipe / fitting / fixture coordination proxies."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_ifc import export_ifc


def test_ifc_exports_pipe_and_fitting(tmp_path: Path) -> None:
    p = Project.create("MEP IFC", vcs=False)
    p.add_level("L1", 0)
    p.place_pipe(level="L1", nps="3/4", start=(0, 0), end=(3000, 0), material="copper")
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(0, 0), material="copper")
    p.place_part(level="L1", kind="toilet", origin=(1000, 1000))
    out = tmp_path / "mep.ifc"
    export_ifc(p.model, out)
    text = out.read_text(encoding="utf-8")
    assert "IFCPROJECT" in text
    # pipes → FlowSegment; fittings → FlowFitting; fixtures → FlowTerminal or proxy
    assert "IFCFLOWSEGMENT" in text
    assert "IFCFLOWFITTING" in text or "IFCBUILDINGELEMENTPROXY" in text
    assert "NPS" in text or "PIPE" in text or "elbow" in text.lower() or "ELBOW" in text


def test_ifc_exports_vertical_riser(tmp_path: Path) -> None:
    p = Project.create("Riser IFC", vcs=False)
    p.add_level("L1", 0)
    p.place_riser(
        level="L1",
        nps="2",
        origin=(1500, 2000),
        z0_mm=0,
        z1_mm=3000,
        material="copper",
    )
    out = tmp_path / "riser.ifc"
    export_ifc(p.model, out)
    text = out.read_text(encoding="utf-8")
    assert "IFCFLOWSEGMENT" in text
    assert "RISER" in text
