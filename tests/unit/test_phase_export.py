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
    assert "def project_verify_pack" in src
    assert "verify_pack" in src
    assert "def place_door" in src
    assert "def place_window" in src
    assert "fire_rating" in src


def test_mcp_place_door_window_api_parity():
    """SDK place_door/window + wall fire_rating match what MCP tools wrap."""
    from llmbim import Project

    p = Project.create("mcp-open", vcs=False)
    p.add_level("L1", 0)
    wid = p.create_wall(
        level="L1",
        start=(0, 0),
        end=(8000, 0),
        thickness_mm=200,
        height_mm=3000,
        fire_rating="2-hr",
        type_id="W-2HR",
    )
    did = p.place_door(
        host=wid,
        offset_mm=2000,
        width_mm=900,
        height_mm=2100,
        type_id="D-HM-36",
        fire_rating="90 min",
    )
    win = p.place_window(
        host=wid,
        offset_mm=5000,
        width_mm=1200,
        height_mm=900,
        sill_mm=900,
        type_id="WIN-VIEW",
    )
    assert p.model.get_element(did).params.get("fire_rating") == "90 min"
    assert p.model.get_element(win).category == "window"
    assert p.model.get_element(wid).params.get("fire_rating") == "2-hr"
    assert len(p.query("category=door")) == 1
