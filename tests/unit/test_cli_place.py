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
