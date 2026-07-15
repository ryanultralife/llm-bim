"""Phase filter on model and deliverables pack."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project


def test_filter_by_phase_keeps_only_allowed():
    p = Project.create("phase-f", vcs=False)
    p.add_level("L1", 0)
    w_new = p.create_wall(
        level="L1", start=(0, 0), end=(5000, 0), thickness_mm=200, height_mm=3000, name="W-new"
    )
    w_ex = p.create_wall(
        level="L1", start=(0, 3000), end=(5000, 3000), thickness_mm=200, height_mm=3000, name="W-ex"
    )
    p.set_phase(w_ex, "existing")
    # default phase is new
    filt = p.model.filter_by_phase("new")
    ids = {e.id for e in filt.elements}
    assert w_new in ids
    assert w_ex not in ids
    assert filt.meta.get("phase_filter") == ["new"]
    both = p.model.filter_by_phase(["new", "existing"])
    assert len(both.elements) == 2


def test_export_deliverables_phase_filter(tmp_path: Path):
    p = Project.create("phase-pack", vcs=False)
    p.add_level("L1", 0)
    w_new = p.create_wall(
        level="L1", start=(0, 0), end=(4000, 0), thickness_mm=200, height_mm=3000
    )
    w_ex = p.create_wall(
        level="L1", start=(0, 2000), end=(4000, 2000), thickness_mm=200, height_mm=3000
    )
    p.set_phase(w_ex, "existing")
    p.place_pipe(level="L1", nps="1", start=(0, 500), end=(3000, 500), material="copper")
    out = tmp_path / "pack_new"
    man = p.export_deliverables(out, phases="new")
    assert man.get("phase_filter") == ["new"]
    assert man.get("export_element_count") == 2  # one wall + pipe (both new)
    assert man.get("full_element_count") == 3
    assert (out / "model.llmbim.json").is_file()
    assert (out / "model_phase_filtered.llmbim.json").is_file()
    # full model still has existing wall
    import json

    full = json.loads((out / "model.llmbim.json").read_text(encoding="utf-8"))
    assert len(full["elements"]) == 3
    filt = json.loads((out / "model_phase_filtered.llmbim.json").read_text(encoding="utf-8"))
    assert len(filt["elements"]) == 2
    assert all(
        (e.get("params") or {}).get("phase", "new") != "existing" for e in filt["elements"]
    )


def test_mcp_export_pack_and_set_phase_signatures():
    """MCP tools expose phases + set_phase for agent pack filtering."""
    import inspect

    import llmbim_mcp.server as srv

    src = inspect.getsource(srv)
    assert "phases" in src
    assert "def set_phase" in src
    assert "export_deliverables" in src
    assert "phase_filter" in src
