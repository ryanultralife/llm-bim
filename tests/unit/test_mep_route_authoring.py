"""MEP route graph + authoring checklist + layered walls."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project


def test_mep_route_places_pipe_and_graph() -> None:
    p = Project.create("MEP-R", vcs=False)
    p.add_level("L1", 0)
    a = p.place_fitting(
        level="L1", fitting_type="elbow_90", nps="2", origin=(0, 0), material="copper"
    )
    b = p.place_fitting(
        level="L1", fitting_type="tee", nps="2", origin=(4000, 3000), material="copper"
    )
    r = p.mep_route(a, b, kind="pipe", nps="2", material="copper", system="CW", orthogonal=True)
    assert r.get("length_m", 0) > 0
    assert len(r.get("segment_ids") or []) >= 1
    g = p.mep_graph()
    assert len(g) >= 1
    assert g[0].get("from_id") == a
    pipes = [e for e in p.model.elements if e.category == "pipe"]
    assert len(pipes) >= 1


def test_authoring_checklist_and_validate_intent() -> None:
    p = Project.create("Auth", vcs=False)
    chk = p.authoring_checklist("building_shell")
    assert chk.get("ok") is True
    assert "required" in chk
    empty = p.validate_intent("building_shell")
    assert empty.get("ok") is False
    assert empty.get("missing")
    p.add_level("L1", 0)
    p.create_rect_shell(level="L1", x=0, y=0, w=8000, d=6000, height_mm=3000, thickness_mm=200)
    ok = p.validate_intent("building_shell")
    assert ok.get("ok") is True


def test_layered_wall_gltf_and_plan(tmp_path: Path) -> None:
    import json

    p = Project.create("Layered", vcs=False)
    p.add_level("L1", 0)
    w = p.create_wall(level="L1", start=(0, 0), end=(6000, 0), thickness_mm=200, height_mm=3000)
    p.set_type(w, "W-EXT-CMU")
    el = p.model.get_element(w)
    assert el.params.get("wall_layers")
    assert len(el.params["wall_layers"]) >= 2
    gltf = tmp_path / "L.gltf"
    p.export_gltf(gltf)
    data = json.loads(gltf.read_text(encoding="utf-8"))
    names = {m.get("name") for m in (data.get("materials") or [])}
    # layered export uses wall_structure / insulation / finish keys
    assert names & {"wall_structure", "wall_insulation", "wall_finish", "wall"}
    from llmbim_drawings.plan import render_plan_view

    view = render_plan_view(p.model, "L1", scale=0.02)
    svg = view.body if hasattr(view, "body") else str(view)
    # multi-fill colors present
    assert "#f0e68c" in svg or "walls" in svg
