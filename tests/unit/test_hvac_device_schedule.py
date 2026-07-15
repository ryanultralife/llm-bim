"""HVAC/electrical device schedule (VAV, diffuser, panel, …)."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.schedules import export_schedule_csv, schedule_rows


def test_hvac_device_schedule_csi(tmp_path: Path):
    p = Project.create("dev-sched", vcs=False)
    p.add_level("L1", 0)
    p.place_part(level="L1", kind="vav", origin=(1000, 1000))
    p.place_part(level="L1", kind="diffuser", origin=(3000, 1000))
    p.place_part(level="L1", kind="fire_damper", origin=(5000, 1000))
    p.place_part(level="L1", kind="panel", origin=(7000, 1000))
    rows = schedule_rows(p.model, "hvac_device")
    types = {r["device_type"] for r in rows}
    assert "vav" in types
    assert "diffuser" in types
    assert "fire_damper" in types
    assert "panel" in types
    assert any(r.get("csi_code") == "23 36 00" for r in rows)
    assert any(str(r.get("csi_code", "")).startswith("26") for r in rows)
    export_schedule_csv(p.model, "hvac_device", tmp_path / "hvac_devices.csv")
    text = (tmp_path / "hvac_devices.csv").read_text(encoding="utf-8")
    assert "device_type" in text
    assert "vav" in text
