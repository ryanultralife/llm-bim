"""Universal capability tests — import, units, query, ops, script, migrate."""

from __future__ import annotations

import json
from pathlib import Path

from llmbim import Project
from llmbim_core.migrate import migrate
from llmbim_core.units import parse_length, to_mm


def test_units() -> None:
    assert abs(to_mm(1, "m") - 1000) < 1e-6
    assert abs(to_mm(1, "ft") - 304.8) < 1e-6
    assert abs(parse_length("3.5m") - 3500) < 1e-6
    assert abs(parse_length("10ft") - 3048) < 1e-6


def test_wall_with_feet() -> None:
    p = Project.create()
    p.add_level("L1", 0)
    wid = p.create_wall(
        level="L1",
        start=(0, 0),
        end=(10, 0),
        thickness=0.2,
        height=3,
        unit="m",
        name="MetricWall",
    )
    el = p.model.get_element(wid)
    assert abs(el.params["length_mm"] - 10000) < 1e-3
    assert abs(el.params["height_mm"] - 3000) < 1e-3


def test_generic_and_query() -> None:
    p = Project.create()
    p.add_level("L1", 0)
    p.create_generic("duct", level="L1", name="MAH-1", diameter_mm=400, system="supply")
    p.create_generic("cable_tray", level="L1", name="CT-1", width_mm=300)
    ducts = p.query("category=duct")
    assert len(ducts) == 1
    assert ducts[0].params.get("diameter_mm") == 400


def test_bulk_ops() -> None:
    p = Project.create()
    r = p.bulk(
        [
            {"op": "add_level", "name": "L1", "elevation_mm": 0},
            {
                "op": "create_wall",
                "level": "L1",
                "start": [0, 0],
                "end": [5000, 0],
                "thickness_mm": 200,
                "height_mm": 3000,
            },
        ]
    )
    assert r["applied"] == 2
    assert p.stats().get("wall") == 1


def test_script_runner(tmp_path: Path) -> None:
    script = tmp_path / "b.py"
    script.write_text(
        """
def build(project):
    project.add_level("L1", 0)
    project.create_wall(level="L1", start=(0,0), end=(4000,0), thickness_mm=200, height_mm=2700, name="W")
""",
        encoding="utf-8",
    )
    p = Project.create("S")
    r = p.run_script(script)
    assert r["ok"] is True
    assert p.stats().get("wall") == 1


def test_migrate_v1() -> None:
    data = {
        "schema_version": 1,
        "id": "prj_x",
        "name": "Old",
        "units": "mm",
        "levels": [{"id": "lvl_1", "name": "L1", "elevation_mm": 0}],
        "grids": [],
        "elements": [
            {
                "id": "wal_1",
                "category": "wall",
                "name": "W",
                "level_id": "lvl_1",
                "params": {
                    "start_mm": [0, 0],
                    "end_mm": [1000, 0],
                    "thickness_mm": 200,
                    "height_mm": 3000,
                    "length_mm": 1000,
                },
            }
        ],
    }
    m = migrate(data)
    assert m["schema_version"] == 2
    assert "assemblies" in m
    p = ProjectModel_from(m)
    assert p.elements[0].params.get("phase") == "new"


def ProjectModel_from(data):
    from llmbim_core.model import ProjectModel

    return ProjectModel.from_dict(data)


def test_dxf_roundtrip(tmp_path: Path) -> None:
    p = Project.create()
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(3000, 0), thickness_mm=200, height_mm=3000)
    dxf = tmp_path / "a.dxf"
    p.export_dxf("L1", dxf)
    p2 = Project.create()
    p2.add_level("L1", 0)
    r = p2.import_file(dxf, level="L1")
    assert r["created"] >= 1


def test_repair() -> None:
    p = Project.create()
    p.add_level("L1", 0)
    # inject bad element via model
    from llmbim_core.ids import new_id
    from llmbim_core.model import Element

    p.model.add_element(
        Element(
            id=new_id("wal"),
            category="wall",
            level_id="missing_level",
            params={"start_mm": [0, 0], "end_mm": [0, 0], "thickness_mm": 200, "height_mm": 3000},
        )
    )
    r = p.repair()
    assert r["ok"]
    # degenerate removed or reassigned
    assert all(el.level_id == p.levels()[0].id for el in p.model.elements)


def test_op_list() -> None:
    p = Project.create()
    names = {o["name"] for o in p.ops()}
    assert "stats" in names
    assert "create_generic" in names
    assert "repair" in names
