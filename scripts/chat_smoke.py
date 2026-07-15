#!/usr/bin/env python3
"""Simulate the end-user chat goal: agent runs this path → files in ./output/.

If this script exits 0, pointing an agent at the repo and asking for drawings should work.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# editable install paths
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for sub in ("sdk", "core", "geometry", "drawings", "ifc", "templates"):
    sys.path.insert(0, str(ROOT / "packages" / sub))

from llmbim import Project  # noqa: E402
from llmbim_core.paths import output_root, project_output_dir  # noqa: E402


def main() -> int:
    print("1. Template office → output/chat_smoke_office/")
    p = Project.from_template("office_bay")
    p.model.name = "Chat Smoke Office"
    man = p.export_deliverables()  # default output/<slug>/
    out = Path(man["output_dir"])
    required = [
        out / "model.llmbim.json",
        out / "model.ifc",
        out / "model.step",
        out / "model.gltf",
        out / "index.html",
        out / "PLOT_SET.pdf",
        out / "boq.json",
        out / "construction" / "A-101_plan.svg",
    ]
    missing = [str(r) for r in required if not r.is_file()]
    if missing:
        print("MISSING:", missing)
        return 1
    if not man.get("ok"):
        print("MANIFEST not ok:", man.get("errors"))
        return 1

    print("2. Freeform custom building")
    p2 = Project.create("Chat Smoke Custom")
    p2.add_level("L1", 0)
    p2.create_rect_shell(
        level="L1", x=0, y=0, w=8000, d=6000, height_mm=3000, thickness_mm=200, name_prefix="B"
    )
    walls = p2.query("category=wall")
    south = next(w for w in walls if w.name == "B-S")
    p2.place_door(host=south.id, offset_mm=3000, width_mm=900, height_mm=2100, name="Entry")
    p2.create_equipment_box(
        level="L1",
        origin=(4000, 3000),
        size=(2000, 1000, 1500),
        name="HVAC skid",
        kind="equipment",
        centered=True,
    )
    man2 = p2.export_deliverables()
    out2 = Path(man2["output_dir"])
    if not (out2 / "index.html").is_file() or not man2.get("ok"):
        print("custom pack failed", man2.get("errors"))
        return 1

    print("3. Materials catalog present")
    cat = p.catalog()
    assert "materials" in cat and "concrete_4000psi" in cat["materials"]

    print("4. Multi-trade + structure + CSI locators + glTF MEP")
    p3 = Project.create("Chat Smoke MultiTrade", vcs=False)
    p3.add_level("L1", 0)
    p3.create_wall(
        level="L1",
        start=(0, 0),
        end=(8000, 0),
        thickness_mm=200,
        height_mm=3500,
        type_id="W-EXT-CMU",
        fire_rating="2-hr",
    )
    p3.place_pipe(level="L1", nps="3/4", start=(0, 500), end=(4000, 500), material="copper")
    p3.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(0, 500), material="copper")
    p3.place_fitting(level="L1", fitting_type="elbow_90", nps="2", origin=(100, 500), material="fire")
    p3.place_duct(level="L1", start=(0, 2000), end=(5000, 2000), width_mm=400, height_mm=250)
    p3.place_conduit(level="L1", start=(0, 2500), end=(5000, 2500), trade_size="1")
    p3.place_cable_tray(level="L1", start=(0, 3000), end=(5000, 3000), width_mm=300)
    p3.place_column(level="L1", origin=(2000, 1000), section="W10x33", height_mm=3500)
    p3.place_beam(level="L1", start=(0, 1000), end=(6000, 1000), section="W12x26", z0_mm=3000)
    p3.place_part(level="L1", kind="toilet", origin=(2000, 2000))
    ft = p3.fitting_takeoff(fitting_type="elbow_90")
    assert any(r["nps"] == "3/4" for r in ft)
    assert any(r.get("system") == "fire" or "black" in str(r.get("material_id", "")).lower() for r in ft)
    assert p3.duct_takeoff() and p3.conduit_takeoff() and p3.cable_tray_takeoff()
    assert p3.steel_takeoff()
    inst = p3.csi_instances()
    codes = {r["csi_code"] for r in inst}
    assert "22 11 16" in codes
    assert "21 13 13" in codes
    assert "23 31 00" in codes
    assert "26 05 33" in codes
    assert "26 05 36" in codes
    assert "05 12 00" in codes
    man3 = p3.export_deliverables(project_output_dir("chat_smoke_multitrade"))
    out3 = Path(man3["output_dir"])
    assert (out3 / "materials" / "csi_instances.json").is_file() or (
        out3 / "materials" / "MATERIALS_AND_PARTS.json"
    ).is_file()
    assert (out3 / "model.gltf").is_file() and (out3 / "model.gltf").stat().st_size > 500
    assert (out3 / "materials" / "duct_takeoff.json").is_file() or (
        out3 / "schedules" / "duct.csv"
    ).is_file()
    assert (out3 / "schedules" / "drawing_list.csv").is_file()
    assert list((out3 / "views").glob("elev*.dxf")) or list((out3 / "views").glob("plan*.dxf"))

    print(
        json.dumps(
            {
                "ok": True,
                "output_root": str(output_root()),
                "office": str(out),
                "custom": str(out2),
                "multitrade": str(out3),
                "open_office": str(out / "index.html"),
                "open_custom": str(out2 / "index.html"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
