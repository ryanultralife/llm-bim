"""CLI place fitting/pipe/riser/part + csi_instances takeoff."""

from __future__ import annotations

import json
from pathlib import Path

from llmbim import Project
from llmbim_cli.main import main


def test_cli_place_riser_and_fitting(tmp_path: Path):
    p = Project.create("cli-place", vcs=False)
    p.add_level("L1", 0)
    model = tmp_path / "model.llmbim.json"
    p.save(model)

    rc = main(
        [
            "place",
            str(model),
            "--kind",
            "riser",
            "--level",
            "L1",
            "--origin",
            "1000,2000",
            "--nps",
            "2",
            "--z0",
            "0",
            "--z1",
            "3000",
            "--material",
            "copper",
        ]
    )
    assert rc == 0
    p2 = Project.open(model)
    pipes = [e for e in p2.model.elements if e.category == "pipe"]
    assert any(e.params.get("vertical") for e in pipes)

    rc = main(
        [
            "place",
            str(model),
            "--kind",
            "fitting",
            "--level",
            "L1",
            "--origin",
            "500,500",
            "--fitting-type",
            "elbow_90",
            "--nps",
            "3/4",
        ]
    )
    assert rc == 0
    p3 = Project.open(model)
    assert any(e.category == "fitting" for e in p3.model.elements)


def test_cli_place_shell(tmp_path: Path, capsys):
    p = Project.create("cli-shell", vcs=False)
    p.add_level("L1", 0)
    model = tmp_path / "model.llmbim.json"
    p.save(model)
    rc = main(
        [
            "place",
            str(model),
            "--kind",
            "shell",
            "--level",
            "L1",
            "--origin",
            "0,0",
            "--end",
            "10000,8000",
            "--height",
            "3000",
            "--thickness",
            "200",
            "--name",
            "B",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["kind"] == "shell"
    assert out["count"] == 4
    assert len(out["wall_ids"]) == 4
    p2 = Project.open(model)
    assert p2.stats().get("wall") == 4


def test_cli_place_note(tmp_path: Path, capsys):
    p = Project.create("cli-note", vcs=False)
    p.add_level("L1", 0)
    model = tmp_path / "model.llmbim.json"
    p.save(model)
    rc = main(
        [
            "place",
            str(model),
            "--kind",
            "note",
            "--level",
            "L1",
            "--origin",
            "1500,2000",
            "--text",
            "Fire rating TBD",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["kind"] == "note"
    assert "Fire" in out["text"]
    p2 = Project.open(model)
    notes = [e for e in p2.model.elements if e.category == "note"]
    assert len(notes) == 1
    assert notes[0].params.get("text") == "Fire rating TBD"


def test_cli_place_grid(tmp_path: Path, capsys):
    p = Project.create("cli-grid", vcs=False)
    p.add_level("L1", 0)
    model = tmp_path / "model.llmbim.json"
    p.save(model)
    rc = main(
        [
            "place",
            str(model),
            "--kind",
            "grid",
            "--axis",
            "U",
            "--positions",
            "0,6000,12000",
            "--name",
            "Grid-U",
            "--labels",
            "1,2,3",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["kind"] == "grid"
    assert out["axis"] == "U"
    assert out["count"] == 3
    p2 = Project.open(model)
    assert any(g.category == "grid" for g in p2.model.grids) or any(
        e.category == "grid" for e in p2.model.elements
    ) or len(p2.model.grids) >= 1


def test_cli_place_equipment_box(tmp_path: Path, capsys):
    p = Project.create("cli-eq", vcs=False)
    p.add_level("L1", 0)
    model = tmp_path / "model.llmbim.json"
    p.save(model)
    rc = main(
        [
            "place",
            str(model),
            "--kind",
            "equipment",
            "--level",
            "L1",
            "--origin",
            "2000,3000",
            "--size",
            "1200,800,1500",
            "--name",
            "Sep-Shell",
            "--part-kind",
            "shell",
            "--shape",
            "box",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["kind"] == "equipment"
    assert out["size_mm"] == [1200.0, 800.0, 1500.0]
    p2 = Project.open(model)
    eqs = [e for e in p2.model.elements if e.category == "equipment"]
    assert len(eqs) == 1
    assert eqs[0].params.get("kind") == "shell"
    assert eqs[0].params.get("size_mm") == [1200.0, 800.0, 1500.0]


def test_cli_place_slab_rect(tmp_path: Path, capsys):
    p = Project.create("cli-slab", vcs=False)
    p.add_level("L1", 0)
    model = tmp_path / "model.llmbim.json"
    p.save(model)
    rc = main(
        [
            "place",
            str(model),
            "--kind",
            "slab",
            "--level",
            "L1",
            "--origin",
            "0,0",
            "--end",
            "10000,8000",
            "--width",
            "200",
            "--name",
            "Slab-L1",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["kind"] == "slab"
    assert out["thickness_mm"] == 200
    p2 = Project.open(model)
    slabs = [e for e in p2.model.elements if e.category == "slab"]
    assert len(slabs) == 1
    assert slabs[0].params.get("thickness_mm") == 200


def test_cli_place_room_rect_and_boundary(tmp_path: Path, capsys):
    p = Project.create("cli-room", vcs=False)
    p.add_level("L1", 0)
    model = tmp_path / "model.llmbim.json"
    p.save(model)

    rc = main(
        [
            "place",
            str(model),
            "--kind",
            "room",
            "--level",
            "L1",
            "--origin",
            "0,0",
            "--end",
            "4000,3000",
            "--height",
            "2700",
            "--name",
            "Office",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["kind"] == "room"
    assert out["boundary_pts"] == 4

    rc = main(
        [
            "place",
            str(model),
            "--kind",
            "room",
            "--level",
            "L1",
            "--boundary",
            "5000,0;8000,0;8000,2500;5000,2500",
            "--name",
            "Lab",
            "--height",
            "3000",
        ]
    )
    assert rc == 0
    p2 = Project.open(model)
    rooms = [e for e in p2.model.elements if e.category == "room"]
    assert len(rooms) == 2
    names = {e.name for e in rooms}
    assert "Office" in names and "Lab" in names


def test_cli_demo_door_fire_rating(tmp_path: Path, capsys):
    out = tmp_path / "demo"
    rc = main(["demo", "--out", str(out)])
    assert rc == 0
    p = Project.open(out / "simple_house.llmbim.json")
    doors = [e for e in p.model.elements if e.category == "door"]
    assert doors
    assert doors[0].params.get("fire_rating") == "90 min"
    assert doors[0].type_id == "D-HM-36" or doors[0].params.get("type_id") == "D-HM-36"
    walls = [e for e in p.model.elements if e.name == "W-S"]
    assert walls and walls[0].params.get("fire_rating") == "1-hr"
    assert (out / "doors.csv").is_file()


def test_cli_place_wall_door_window(tmp_path: Path, capsys):
    p = Project.create("cli-open", vcs=False)
    p.add_level("L1", 0)
    model = tmp_path / "model.llmbim.json"
    p.save(model)

    rc = main(
        [
            "place",
            str(model),
            "--kind",
            "wall",
            "--level",
            "L1",
            "--origin",
            "0,0",
            "--end",
            "8000,0",
            "--width",
            "200",
            "--height",
            "3000",
            "--fire-rating",
            "2-hr",
            "--type-id",
            "W-2HR",
            "--name",
            "W-S",
        ]
    )
    assert rc == 0
    wall_out = json.loads(capsys.readouterr().out)
    host = wall_out["element_id"]

    rc = main(
        [
            "place",
            str(model),
            "--kind",
            "door",
            "--host",
            host,
            "--offset",
            "2000",
            "--width",
            "900",
            "--height",
            "2100",
            "--type-id",
            "D-HM-36",
            "--fire-rating",
            "90 min",
        ]
    )
    assert rc == 0
    _ = capsys.readouterr()

    rc = main(
        [
            "place",
            str(model),
            "--kind",
            "window",
            "--host",
            host,
            "--offset",
            "5000",
            "--width",
            "1200",
            "--height",
            "900",
            "--sill",
            "900",
            "--type-id",
            "WIN-VIEW",
        ]
    )
    assert rc == 0
    p2 = Project.open(model)
    assert any(e.category == "door" for e in p2.model.elements)
    assert any(e.category == "window" for e in p2.model.elements)
    walls = [e for e in p2.model.elements if e.category == "wall"]
    assert walls and walls[0].params.get("fire_rating") == "2-hr"


def test_cli_takeoff_csi_instances(tmp_path: Path, capsys):
    p = Project.create("cli-csi", vcs=False)
    p.add_level("L1", 0)
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="1/2", origin=(0, 0))
    model = tmp_path / "m.llmbim.json"
    p.save(model)
    rc = main(["takeoff", str(model), "--kind", "csi_instances"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["count"] >= 1
    assert "locator" in data["instances"][0]
    assert data["instances"][0]["csi_code"]


def test_cli_schedule_zone(tmp_path: Path, capsys):
    p = Project.create("cli-sched", vcs=False)
    p.add_level("L1", 0)
    p.create_room(
        level="L1",
        name="Lab",
        boundary=[(0, 0), (4000, 0), (4000, 3000), (0, 3000)],
        height_mm=3000,
    )
    model = tmp_path / "m.llmbim.json"
    p.save(model)
    out_csv = tmp_path / "zone.csv"
    rc = main(["schedule", str(model), "--kind", "zone", "--out", str(out_csv)])
    assert rc == 0
    assert out_csv.is_file()
    text = out_csv.read_text(encoding="utf-8")
    assert "Lab" in text
    assert "volume_m3" in text or "area_m2" in text
    _ = capsys.readouterr()  # clear first command stdout
    rc = main(["schedule", str(model), "--kind", "zone", "--limit", "5"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["count"] >= 1
    assert data["rows"][0]["name"] == "Lab"