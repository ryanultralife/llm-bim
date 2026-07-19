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


def _parse_entities(text: str) -> dict[int, tuple[str, str]]:
    import re

    ent: dict[int, tuple[str, str]] = {}
    for line in text.splitlines():
        m = re.match(r"#(\d+)=([A-Z0-9]+)\((.*)\);$", line)
        if m:
            ent[int(m.group(1))] = (m.group(2), m.group(3))
    return ent


def _top_level_args(body: str) -> list[str]:
    out: list[str] = []
    depth = 0
    cur = ""
    for ch in body:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def test_ifc4_entity_attribute_counts(tmp_path: Path) -> None:
    """IFC4 requires exact attribute counts; a short entity is rejected by strict
    readers (Revit/ifcopenshell). Guards the door=13 / wall=9 / column=9 fixes."""
    import re

    from llmbim_ifc import export_ifc

    p = Project.create("IFC Attr")
    p.add_level("L1", 0)
    w = p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    p.place_door(host=w, offset_mm=2000, width_mm=900, height_mm=2100)
    p.place_window(host=w, offset_mm=5000, width_mm=1200, height_mm=900, sill_mm=900)
    out = tmp_path / "m.ifc"
    export_ifc(p.model, out)
    ent = _parse_entities(out.read_text(encoding="utf-8"))

    expected = {
        "IFCDOOR": 13,
        "IFCWINDOW": 13,
        "IFCWALLSTANDARDCASE": 9,
        "IFCAPPLICATION": 4,
    }
    seen: dict[str, int] = {}
    for _i, (typ, body) in ent.items():
        if typ in expected:
            seen[typ] = len(_top_level_args(body))
    for typ, n in expected.items():
        assert seen.get(typ) == n, f"{typ}: expected {n} attrs, got {seen.get(typ)}"

    # every #id reference must resolve (no dangling refs)
    defined = set(ent.keys())
    refs = set()
    for _i, (_t, body) in ent.items():
        refs.update(int(x) for x in re.findall(r"#(\d+)", body))
    assert refs <= defined, f"dangling refs: {sorted(refs - defined)}"


def test_ifc_multistorey_elevation_flows(tmp_path: Path) -> None:
    """Elements on an upper level must inherit the storey elevation through the
    placement chain, not collapse to world Z=0."""
    import re

    from llmbim_ifc import export_ifc

    p = Project.create("Two Storey")
    p.add_level("L1", 0)
    p.add_level("L2", 3500)
    p.create_wall(level="L1", start=(0, 0), end=(6000, 0), thickness_mm=200, height_mm=3000)
    p.create_wall(level="L2", start=(0, 0), end=(6000, 0), thickness_mm=200, height_mm=3000)
    out = tmp_path / "m.ifc"
    export_ifc(p.model, out)
    ent = _parse_entities(out.read_text(encoding="utf-8"))

    def placement_point(placement_id: int) -> tuple[str, list[float]]:
        _t, body = ent[placement_id]
        a = _top_level_args(body)
        parent = a[0]
        a3 = int(a[1][1:])
        pt_id = int(_top_level_args(ent[a3][1])[0][1:])
        coords = _top_level_args(ent[pt_id][1].strip("()"))
        return parent, [float(c) for c in coords]

    storey_z = set()
    for _i, (typ, body) in ent.items():
        if typ == "IFCWALLSTANDARDCASE":
            pl = int(re.search(r"#(\d+)", _top_level_args(body)[5]).group(1))
            parent, _pt = placement_point(pl)
            assert parent.startswith("#"), "wall must be placed relative to a storey, not $"
            _pp, storey_pt = placement_point(int(parent[1:]))
            storey_z.add(storey_pt[2])
    assert storey_z == {0.0, 3500.0}, f"storey elevations not distinct: {storey_z}"


def test_export_ifc_optional_ifcopenshell(tmp_path: Path) -> None:
    ifcopenshell = pytest.importorskip("ifcopenshell")
    p = Project.create("IFC2")
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(3000, 0), thickness_mm=200, height_mm=2700)
    out = tmp_path / "m.ifc"
    p.export_ifc(out)
    f = ifcopenshell.open(str(out))
    assert f.by_type("IfcProject")


def test_ifc_openings_void_and_fill(tmp_path: Path) -> None:
    """Hosted doors/windows must punch a real IfcOpeningElement through the host
    wall (IfcRelVoidsElement) and fill it (IfcRelFillsElement); openings must not
    be contained in the spatial structure."""
    import re

    from llmbim_ifc import export_ifc

    p = Project.create("Openings", vcs=False)
    p.add_level("L1", 0)
    w = p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    p.place_door(host=w, offset_mm=2000, width_mm=900, height_mm=2100)
    p.place_window(host=w, offset_mm=5000, width_mm=1200, height_mm=900, sill_mm=900)
    out = tmp_path / "m.ifc"
    export_ifc(p.model, out)
    ent = _parse_entities(out.read_text(encoding="utf-8"))

    kinds = [t for t, _ in ent.values()]
    assert kinds.count("IFCOPENINGELEMENT") == 2
    assert kinds.count("IFCRELVOIDSELEMENT") == 2
    assert kinds.count("IFCRELFILLSELEMENT") == 2
    # voids: wall -> opening; fills: opening -> door/window
    for i, (typ, body) in ent.items():
        a = _top_level_args(body)
        if typ == "IFCRELVOIDSELEMENT":
            assert ent[int(a[4][1:])][0] == "IFCWALLSTANDARDCASE"
            assert ent[int(a[5][1:])][0] == "IFCOPENINGELEMENT"
        if typ == "IFCRELFILLSELEMENT":
            assert ent[int(a[4][1:])][0] == "IFCOPENINGELEMENT"
            assert ent[int(a[5][1:])][0] in {"IFCDOOR", "IFCWINDOW"}
    # openings are related via voids, never contained in a storey
    opn = {i for i, (t, _) in ent.items() if t == "IFCOPENINGELEMENT"}
    for i, (typ, body) in ent.items():
        if typ == "IFCRELCONTAINEDINSPATIALSTRUCTURE":
            refs = {int(x) for x in re.findall(r"#(\d+)", body)}
            assert not (refs & opn), "opening contained in spatial structure"


def test_ifc_wall_corner_joins(tmp_path: Path) -> None:
    """Walls meeting at a corner extend by half the adjacent wall's thickness so
    the corner closes (L-join): 8000mm wall + 300/2 -> XDim 8150."""
    from llmbim_ifc import export_ifc

    p = Project.create("Corners", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    p.create_wall(level="L1", start=(0, 0), end=(0, 6000), thickness_mm=300, height_mm=3000)
    out = tmp_path / "m.ifc"
    export_ifc(p.model, out)
    ent = _parse_entities(out.read_text(encoding="utf-8"))
    dims = set()
    for _i, (typ, body) in ent.items():
        if typ == "IFCRECTANGLEPROFILEDEF":
            a = _top_level_args(body)
            dims.add((float(a[3]), float(a[4])))
    assert (8150.0, 200.0) in dims, f"wall A not extended: {dims}"
    assert (6100.0, 300.0) in dims, f"wall B not extended: {dims}"
