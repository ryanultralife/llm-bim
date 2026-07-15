"""Schedules include MasterFormat CSI + locators."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.schedules import export_schedule_csv, schedule_rows


def test_pipe_and_fitting_schedules_have_csi_and_locator():
    p = Project.create("sched-csi", vcs=False)
    p.add_level("L1", 0)
    p.place_pipe(level="L1", nps="3/4", start=(100, 200), end=(3100, 200), material="copper")
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(100, 200), material="copper")
    p.place_part(level="L1", kind="toilet", origin=(2000, 2000))

    pipes = schedule_rows(p.model, "pipe")
    assert pipes
    assert pipes[0]["csi_code"] == "22 11 16"
    assert pipes[0].get("locator")
    assert "L1" in str(pipes[0]["locator"])

    fits = schedule_rows(p.model, "fitting")
    assert any(r["csi_code"] == "22 11 16" for r in fits)

    toilets = [r for r in schedule_rows(p.model, "part") if "WC" in str(r.get("part_id", ""))]
    assert toilets
    assert toilets[0].get("csi_code") in ("22 42 13", "22 40 00") or str(
        toilets[0].get("csi_code", "")
    ).startswith("22")


def test_csi_schedule_kind_and_csv(tmp_path: Path):
    p = Project.create("csi-sched", vcs=False)
    p.add_level("L1", 0)
    p.place_riser(level="L1", nps="2", origin=(0, 0), z0_mm=0, z1_mm=3000, material="fire")
    rows = schedule_rows(p.model, "csi")
    assert any(r["csi_code"] == "21 13 13" for r in rows)
    export_schedule_csv(p.model, "csi", tmp_path / "csi.csv")
    text = (tmp_path / "csi.csv").read_text(encoding="utf-8")
    assert "csi_code" in text
    assert "locator" in text


def test_schedule_includes_room_column():
    p = Project.create("sched-room", vcs=False)
    p.add_level("L1", 0)
    p.create_room(
        level="L1",
        name="Restroom A",
        boundary=[(0, 0), (5000, 0), (5000, 4000), (0, 4000)],
    )
    p.place_fitting(
        level="L1",
        fitting_type="elbow_90",
        nps="1/2",
        origin=(2000, 2000),
        material="copper",
    )
    fits = schedule_rows(p.model, "fitting")
    assert fits
    assert fits[0].get("room") == "Restroom A"
    assert "RM:Restroom" in str(fits[0].get("locator", ""))


def test_duct_and_conduit_schedule_rows(tmp_path: Path):
    p = Project.create("sched-mep", vcs=False)
    p.add_level("L1", 0)
    p.place_duct(level="L1", start=(0, 0), end=(5000, 0), width_mm=400, height_mm=250, system="SA")
    p.place_conduit(level="L1", start=(0, 500), end=(8000, 500), trade_size="1")
    ducts = schedule_rows(p.model, "duct")
    assert len(ducts) == 1
    assert ducts[0]["csi_code"] == "23 31 00"
    assert ducts[0].get("size") == "400x250"
    assert ducts[0].get("locator")
    conds = schedule_rows(p.model, "conduit")
    assert len(conds) == 1
    assert conds[0]["csi_code"] == "26 05 33"
    assert conds[0].get("trade_size") == "1"
    export_schedule_csv(p.model, "duct", tmp_path / "duct.csv")
    export_schedule_csv(p.model, "conduit", tmp_path / "conduit.csv")
    assert "23 31 00" in (tmp_path / "duct.csv").read_text(encoding="utf-8")
    assert "26 05 33" in (tmp_path / "conduit.csv").read_text(encoding="utf-8")
