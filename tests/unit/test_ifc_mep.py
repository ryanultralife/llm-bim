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
    # at least equipment-style proxies for pipe + fitting + toilet
    assert text.count("IFCBUILDINGELEMENTPROXY") >= 3
    assert "PIPE" in text or "FITTING" in text or "FIXTURE" in text
