"""End-to-end: chat agent path writes packs under output/."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_core.paths import project_output_dir, slugify


def test_default_export_to_output(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLMBIM_OUTPUT_DIR", str(tmp_path / "output"))
    # re-import paths would need env at call time — project_output_dir reads env each call
    p = Project.create("Agent Demo Building")
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=5000, d=4000, height_mm=3000, thickness_mm=200, name_prefix="B"
    )
    man = p.export_deliverables()
    out = Path(man["output_dir"])
    assert out.is_dir()
    assert "output" in str(out).replace("\\", "/")
    assert (out / "model.ifc").is_file()
    assert (out / "index.html").is_file()
    assert man.get("ok") is True


def test_slugify() -> None:
    assert slugify("My Building!") == "my_building"
    assert project_output_dir("x", create=False).name == "x"


def test_full_multi_trade_pack_artifacts(tmp_path: Path) -> None:
    """Vision pack: CSI, zone schedule, elev DXF, IFC spaces — agent-ready."""
    p = Project.create("Full Trade Pack", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 3500)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=10000, d=8000, height_mm=3500, thickness_mm=200
    )
    p.create_room(
        level="L1",
        name="Mech",
        boundary=[(500, 500), (4000, 500), (4000, 3500), (500, 3500)],
        height_mm=3000,
    )
    p.place_pipe(level="L1", nps="2", start=(1000, 1500), end=(6000, 1500), material="copper")
    p.place_riser(level="L1", nps="2", origin=(6000, 1500), to_level="L2", material="copper")
    p.place_duct(level="L1", start=(1000, 4000), end=(7000, 4000), width_mm=500, height_mm=300)
    p.place_conduit(level="L1", start=(1000, 5000), end=(7000, 5000), trade_size="1")
    p.place_part(level="L1", kind="vav", origin=(2000, 4000))
    out = tmp_path / "pack"
    man = p.export_deliverables(out)
    assert man.get("ok") is True
    assert (out / "schedules" / "zone_areas.csv").is_file()
    assert (out / "schedules" / "csi.csv").is_file() or (
        out / "materials" / "csi_instances.json"
    ).is_file()
    assert (out / "views" / "elev_S.dxf").is_file()
    assert (out / "views" / "elev_E.dxf").is_file()
    ifc = (out / "model.ifc").read_text(encoding="utf-8")
    assert "IFCSPACE" in ifc
    assert "IFCFLOWSEGMENT" in ifc
    step = (out / "model.step").read_text(encoding="utf-8")
    assert "PIPE-CU:" in step or "DUCT:" in step
    gltf = (out / "model.gltf").read_text(encoding="utf-8")
    assert "pipe_copper" in gltf or "duct" in gltf
