"""VAV + fire damper place, CSI, plan marks."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.plan import write_plan_svg


def test_place_vav_and_fire_damper_csi():
    p = Project.create("hvac-dev", vcs=False)
    p.add_level("L1", 0)
    vav = p.place_part(level="L1", kind="vav", origin=(2000, 2000))
    fd = p.place_part(level="L1", kind="fire_damper", origin=(4000, 2000))
    el_v = p.model.get_element(vav)
    el_d = p.model.get_element(fd)
    assert el_v.params.get("fitting_type") == "vav"
    assert el_d.params.get("fitting_type") == "fire_damper"
    rows = {r["element_id"]: r for r in p.csi_instances()}
    assert rows[vav]["csi_code"] == "23 36 00"
    assert rows[fd]["csi_code"] == "23 33 00"


def test_hvac_devices_on_plan(tmp_path: Path):
    p = Project.create("hvac-plan", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    p.place_part(level="L1", kind="vav", origin=(1500, 1500))
    p.place_part(level="L1", kind="fire_damper", origin=(3500, 1500))
    p.place_part(level="L1", kind="diffuser", origin=(5500, 1500))
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    text = plan.read_text(encoding="utf-8")
    assert "VAV" in text
    assert "FD" in text
    assert "CD" in text
    assert "hvac-device" in text
