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


def test_ifc_space_links_mep_in_room(tmp_path: Path) -> None:
    """MEP inside a room polygon is related to IfcSpace via SpaceContents rel."""
    p = Project.create("Space MEP", vcs=False)
    p.add_level("L1", 0)
    p.create_room(
        level="L1",
        name="Restroom A",
        boundary=[(0, 0), (5000, 0), (5000, 4000), (0, 4000)],
        height_mm=2700,
    )
    p.place_fitting(
        level="L1",
        fitting_type="elbow_90",
        nps="1/2",
        origin=(2000, 2000),
        material="copper",
    )
    p.place_part(level="L1", kind="toilet", origin=(2500, 1500))
    out = tmp_path / "space.ifc"
    export_ifc(p.model, out)
    text = out.read_text(encoding="utf-8")
    assert "IFCSPACE" in text
    assert "Restroom" in text or "RM:Restroom" in text
    assert "SpaceContents" in text
    # at least one containment rel naming SpaceContents
    assert text.count("IFCRELCONTAINEDINSPATIALSTRUCTURE") >= 2


def test_ifc_csi_property_sets(tmp_path: Path) -> None:
    """MEP elements carry Pset_CSIMasterFormat with CSI_Code + Locator."""
    p = Project.create("CSI IFC", vcs=False)
    p.add_level("L1", 0)
    p.create_room(
        level="L1",
        name="Mech",
        boundary=[(0, 0), (6000, 0), (6000, 5000), (0, 5000)],
    )
    p.place_pipe(level="L1", nps="2", start=(500, 2500), end=(5500, 2500), material="copper")
    p.place_duct(level="L1", start=(500, 1000), end=(4000, 1000), width_mm=400, height_mm=250)
    out = tmp_path / "csi.ifc"
    export_ifc(p.model, out)
    text = out.read_text(encoding="utf-8")
    assert "Pset_CSIMasterFormat" in text
    assert "CSI_Code" in text
    assert "22 11 16" in text
    assert "23 31 00" in text
    assert "IFCRELDEFINESBYPROPERTIES" in text


def test_ifc_door_window_host_placement(tmp_path: Path) -> None:
    """Doors/windows placed on host wall baseline (not world origin) with FR tag."""
    p = Project.create("Open IFC", vcs=False)
    p.add_level("L1", 0)
    wid = p.create_wall(
        level="L1",
        start=(2000, 3000),
        end=(10000, 3000),
        thickness_mm=200,
        height_mm=3000,
    )
    p.place_door(
        host=wid,
        offset_mm=2500,
        width_mm=900,
        height_mm=2100,
        type_id="D-HM-36",
        fire_rating="90 min",
        name="Entry",
    )
    p.place_window(
        host=wid,
        offset_mm=5000,
        width_mm=1200,
        height_mm=900,
        sill_mm=900,
        type_id="WIN-VIEW",
        name="View",
    )
    out = tmp_path / "open.ifc"
    export_ifc(p.model, out)
    text = out.read_text(encoding="utf-8")
    assert "IFCDOOR" in text
    assert "IFCWINDOW" in text
    # placement should reference host wall coords (2000+offset, 3000) not only 0,0,0
    assert "4500" in text or "4500." in text  # 2000 + 2500 door start
    assert "3000" in text or "3000." in text
    assert "FR90" in text or "90min" in text or "D-HM" in text


def test_ifc_column_and_beam_entities(tmp_path: Path) -> None:
    """Structure exports as IFCCOLUMN / IFCBEAM with CSI psets and section tags."""
    p = Project.create("Struct IFC", vcs=False)
    p.add_level("L1", 0)
    p.place_column(level="L1", origin=(2000, 2000), section="W10x33", height_mm=3500)
    p.place_beam(level="L1", start=(0, 2000), end=(6000, 2000), section="W12x26", z0_mm=3000)
    out = tmp_path / "struct.ifc"
    export_ifc(p.model, out)
    text = out.read_text(encoding="utf-8")
    assert "IFCCOLUMN" in text
    assert "IFCBEAM" in text
    assert "W10x33" in text
    assert "W12x26" in text
    assert "Pset_CSIMasterFormat" in text
    assert "05 12 00" in text
