"""IFC export → import round-trip against our own SPF writer.

Exact round-trips: levels (name + elevation), wall start/end/thickness/height
(including L-corner walls whose end-join extension is resolvable from partner
geometry), door/window hosting + offset/sill/dims, equipment origin + size,
slab bbox + thickness, pipe endpoints, riser z-span.

Approximate by design: room extents (IfcSpace stores no boundary geometry —
only the min corner is exact) and wall lengths whose end-side corner-join
extension has no resolvable partner signature.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from llmbim import Project
from llmbim_core.model import Element, ProjectModel
from llmbim_ifc import export_ifc, import_ifc

TOL = 1.0  # mm


def _build() -> Project:
    p = Project.create("RoundTrip", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 3500)
    # L-corner pair: A end meets B start at (8000, 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000, name="WA")
    p.create_wall(level="L1", start=(8000, 0), end=(8000, 6000), thickness_mm=300, height_mm=3000, name="WB")
    # free-standing wall hosting the door + window (no corner joins)
    wc = p.create_wall(level="L1", start=(2000, 3000), end=(6000, 3000), thickness_mm=150, height_mm=3000, name="WC")
    # rotated wall on the upper level (no corner joins)
    p.create_wall(level="L2", start=(1000, 1000), end=(1000, 5000), thickness_mm=200, height_mm=2800, name="WD")
    p.place_door(host=wc, offset_mm=500, width_mm=900, height_mm=2100, name="D1")
    p.place_window(host=wc, offset_mm=2200, width_mm=1200, height_mm=900, sill_mm=900, name="N1")
    p.create_slab(level="L1", polygon=[(0, 0), (8000, 0), (8000, 6000), (0, 6000)], thickness_mm=200, name="S1")
    p.create_equipment_box(level="L1", origin=(1200, 800), size=(600, 400, 1500), name="AHU-1")
    p.create_room(level="L1", name="Lab", boundary=[(100, 100), (4000, 100), (4000, 2800), (100, 2800)])
    p.place_pipe(level="L1", nps="3/4", start=(500, 500), end=(4500, 500), z0_mm=2700)
    p.place_riser(level="L1", nps="3/4", origin=(700, 700), z0_mm=0, z1_mm=3000)
    return p


def _roundtrip(tmp_path: Path) -> tuple[ProjectModel, ProjectModel, dict[str, Any], Path]:
    p = _build()
    first = tmp_path / "first.ifc"
    export_ifc(p.model, first)
    fresh = ProjectModel(name="Imported")
    summary = import_ifc(fresh, first)
    return p.model, fresh, summary, first


def _by_name(model: ProjectModel, category: str, name: str) -> Element:
    hits = [e for e in model.elements if e.category == category and e.name == name]
    assert len(hits) == 1, f"{category} '{name}': {len(hits)} matches"
    return hits[0]


def _close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(float(a) - float(b)) <= tol


def _pt_close(a: list[float], b: tuple[float, float], tol: float = TOL) -> bool:
    return _close(a[0], b[0], tol) and _close(a[1], b[1], tol)


def test_levels_roundtrip_exact(tmp_path: Path) -> None:
    _src, fresh, summary, _f = _roundtrip(tmp_path)
    assert summary["ok"] is True
    assert summary["levels"] == 2
    assert len(fresh.levels) == 2
    by_name = {lv.name: lv.elevation_mm for lv in fresh.levels}
    assert by_name == {"L1": 0.0, "L2": 3500.0}


def test_walls_roundtrip(tmp_path: Path) -> None:
    _src, fresh, summary, _f = _roundtrip(tmp_path)
    walls = [e for e in fresh.elements if e.category == "wall"]
    assert len(walls) == 4
    assert summary["created"]["walls"] == 4

    # no-join walls: exact within 1mm
    wc = _by_name(fresh, "wall", "WC")
    assert _pt_close(wc.params["start_mm"], (2000, 3000))
    assert _pt_close(wc.params["end_mm"], (6000, 3000))
    assert _close(wc.params["thickness_mm"], 150)
    assert _close(wc.params["height_mm"], 3000)
    assert fresh.get_level(wc.level_id or "").name == "L1"

    wd = _by_name(fresh, "wall", "WD")
    assert _pt_close(wd.params["start_mm"], (1000, 1000))
    assert _pt_close(wd.params["end_mm"], (1000, 5000))
    assert _close(wd.params["thickness_mm"], 200)
    assert _close(wd.params["height_mm"], 2800)
    assert fresh.get_level(wd.level_id or "").name == "L2"

    # L-corner pair: WA's end extension is resolvable from WB's exact start
    # (end-to-start join), WB's start extension is encoded in its profile
    # center — both round-trip within 1mm.
    wa = _by_name(fresh, "wall", "WA")
    assert _pt_close(wa.params["start_mm"], (0, 0))
    assert _pt_close(wa.params["end_mm"], (8000, 0))
    assert _close(wa.params["thickness_mm"], 200)
    assert "ifc_length_approx" not in wa.params

    wb = _by_name(fresh, "wall", "WB")
    assert _pt_close(wb.params["start_mm"], (8000, 0))
    assert _pt_close(wb.params["end_mm"], (8000, 6000))
    assert _close(wb.params["thickness_mm"], 300)


def test_door_window_hosted_roundtrip(tmp_path: Path) -> None:
    _src, fresh, summary, _f = _roundtrip(tmp_path)
    assert summary["created"]["doors"] == 1
    assert summary["created"]["windows"] == 1
    wc = _by_name(fresh, "wall", "WC")

    door = _by_name(fresh, "door", "D1")
    assert door.host_id == wc.id, "door must be hosted on the recovered WC wall"
    assert _close(door.params["offset_mm"], 500)
    assert _close(door.params["width_mm"], 900)
    assert _close(door.params["height_mm"], 2100)

    win = _by_name(fresh, "window", "N1")
    assert win.host_id == wc.id, "window must be hosted on the recovered WC wall"
    assert _close(win.params["offset_mm"], 2200)
    assert _close(win.params["width_mm"], 1200)
    assert _close(win.params["height_mm"], 900)
    assert _close(win.params["sill_mm"], 900)


def test_slab_equipment_room_roundtrip(tmp_path: Path) -> None:
    _src, fresh, summary, _f = _roundtrip(tmp_path)

    slab = _by_name(fresh, "slab", "S1")
    poly = slab.params["polygon_mm"]
    xs = [pt[0] for pt in poly]
    ys = [pt[1] for pt in poly]
    assert _close(min(xs), 0) and _close(max(xs), 8000)
    assert _close(min(ys), 0) and _close(max(ys), 6000)
    assert _close(slab.params["thickness_mm"], 200)

    eq = _by_name(fresh, "equipment", "AHU-1")
    assert _pt_close(eq.params["origin_mm"], (1200, 800))
    sz = eq.params["size_mm"]
    assert _close(sz[0], 600) and _close(sz[1], 400) and _close(sz[2], 1500)
    assert _close(eq.params["z0_mm"], 0)

    rooms = [e for e in fresh.elements if e.category == "room"]
    assert len(rooms) == 1
    room = rooms[0]
    assert room.name == "Lab"
    # only the min corner survives IFC (IfcSpace has no boundary geometry)
    bxs = [pt[0] for pt in room.params["boundary_mm"]]
    bys = [pt[1] for pt in room.params["boundary_mm"]]
    assert _close(min(bxs), 100) and _close(min(bys), 100)
    assert room.params.get("ifc_extent_approx") is True


def test_pipes_roundtrip(tmp_path: Path) -> None:
    _src, fresh, summary, _f = _roundtrip(tmp_path)
    pipes = [e for e in fresh.elements if e.category == "pipe"]
    assert len(pipes) == 2
    assert summary["created"]["pipes"] == 2

    runs = [e for e in pipes if not e.params.get("vertical")]
    risers = [e for e in pipes if e.params.get("vertical")]
    assert len(runs) == 1 and len(risers) == 1

    run = runs[0]
    assert _pt_close(run.params["start_mm"], (500, 500))
    assert _pt_close(run.params["end_mm"], (4500, 500))
    assert _close(run.params["z0_mm"], 2700)
    assert run.params.get("nps") == "3/4"

    ris = risers[0]
    assert _pt_close(ris.params["origin_mm"], (700, 700))
    assert _close(ris.params["z0_mm"], 0)
    assert _close(ris.params["z1_mm"], 3000)


def _entity_counts(path: Path, types: tuple[str, ...]) -> dict[str, int]:
    counts = dict.fromkeys(types, 0)
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"#\d+=([A-Z0-9]+)\(", line)
        if m and m.group(1) in counts:
            counts[m.group(1)] += 1
    return counts


def test_second_export_same_entity_counts(tmp_path: Path) -> None:
    """Exporting the imported model again yields the same product/spatial
    entity population as the original export (property sets and space-content
    linkage may differ: part assignments are not recreated on import)."""
    _src, fresh, _summary, first = _roundtrip(tmp_path)
    second = tmp_path / "second.ifc"
    export_ifc(fresh, second)
    types = (
        "IFCBUILDINGSTOREY",
        "IFCWALLSTANDARDCASE",
        "IFCDOOR",
        "IFCWINDOW",
        "IFCOPENINGELEMENT",
        "IFCRELVOIDSELEMENT",
        "IFCRELFILLSELEMENT",
        "IFCSLAB",
        "IFCBUILDINGELEMENTPROXY",
        "IFCPIPESEGMENT",
        "IFCSPACE",
    )
    c1 = _entity_counts(first, types)
    c2 = _entity_counts(second, types)
    assert c1 == c2, f"first={c1} second={c2}"
    # sanity: the population is what the build script placed
    assert c1["IFCWALLSTANDARDCASE"] == 4
    assert c1["IFCPIPESEGMENT"] == 2
    assert c1["IFCOPENINGELEMENT"] == 2


def test_import_summary_and_cli_entry(tmp_path: Path) -> None:
    """auto_import (the CLI `llmbim import x.ifc` path) delegates to the real
    importer; unknown entities are counted, not fatal."""
    from llmbim_core.io_import import auto_import

    p = _build()
    first = tmp_path / "m.ifc"
    export_ifc(p.model, first)
    # splice in an entity type the importer does not know
    text = first.read_text(encoding="utf-8")
    text = text.replace("DATA;", "DATA;\n#99991=IFCWIBBLE($,$);", 1)
    first.write_text(text, encoding="utf-8")

    fresh = ProjectModel(name="ViaAutoImport")
    summary = auto_import(fresh, first)
    assert summary["ok"] is True
    assert summary["created"]["walls"] == 4
    assert summary["skipped"].get("IFCWIBBLE") == 1
    assert len([e for e in fresh.elements if e.category == "wall"]) == 4
