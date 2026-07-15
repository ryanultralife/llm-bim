"""Import a fabrication/machine module into a facility host.

Demonstrates:
  - export Proto10-class skid as a module package
  - import as **block** (instance) and as **native** (editable)
  - define ports and **connect** machine to process header

  python examples/module_machine_host.py
"""

from __future__ import annotations

import json
from pathlib import Path

from llmbim import Project


def main() -> None:
    root = Path("output/module_demo")
    root.mkdir(parents=True, exist_ok=True)

    # --- Machine / fabrication design ---
    machine = Project.create("MB-SEP skid module", vcs=False)
    machine.add_level("Skid", 0)
    shell = machine.create_equipment_box(
        level="Skid",
        origin=(0, 0),
        size=(1200, 800, 900),
        name="Separator skid envelope",
        kind="separator_skid",
        centered=True,
    )
    machine.create_equipment_box(
        level="Skid",
        origin=(0, 0),
        size=(500, 320, 320),
        name="Shell 320OD",
        kind="shell",
        shape="cylinder",
        centered=True,
        z0_mm=200,
    )
    machine.define_port(shell, "FEED", role="process", medium="slurry", position=(-600, 0))
    machine.define_port(shell, "PRODUCT", role="process", medium="product", position=(600, 0))
    machine.define_port(shell, "DRAIN", role="drain", medium="waste", position=(0, -400))
    machine.define_port(shell, "PWR", role="power", medium="480V", position=(0, 400))

    mod_dir = root / "modules" / "sep_skid"
    machine.export_module(mod_dir, kind="machine")
    machine.save(mod_dir / "model.llmbim.json")

    # --- Host facility ---
    host = Project.create("Process bay host", vcs=True)
    host.add_level("L0", 0)
    host.create_rect_shell(
        level="L0", x=0, y=0, w=24000, d=18000, height_mm=8000, thickness_mm=300, name_prefix="BAY"
    )
    header = host.create_equipment_box(
        level="L0",
        origin=(2000, 9000),
        size=(3000, 400, 400),
        name="Process header",
        kind="header",
    )
    host.define_port(header, "DROP_A", role="process", medium="slurry", position=(2500, 9000))
    host.define_port(header, "DROP_B", role="process", medium="slurry", position=(3500, 9000))

    # Native import (editable fabrication inside host)
    n = host.import_module(
        mod_dir,
        level="L0",
        origin=(8000, 6000),
        mode="native",
        kind="machine",
        name="Sep skid cell-1",
    )
    # Block import (library instance)
    b = host.import_module(
        mod_dir,
        level="L0",
        origin=(16000, 6000),
        mode="block",
        kind="machine",
        name="Sep skid cell-2 (block)",
    )

    # Connect native skid FEED → header DROP_A
    skid_els = [
        e
        for e in host.model.elements
        if e.params.get("imported_from_module") == n["module_id"] and e.params.get("ports")
    ]
    if skid_els:
        host.connect(skid_els[0].id, "FEED", header, "DROP_A", medium="slurry", name="cell1-feed")
        host.connect(skid_els[0].id, "PRODUCT", header, "DROP_B", medium="product", name="cell1-prod")

    host.commit("Host bay + machine modules + process connections")
    man = host.export_deliverables(root / "host_pack", mode="facility", plan_level="L0", plan_scale=0.01)

    summary = {
        "module_package": str(mod_dir),
        "native_import": n,
        "block_import": b,
        "modules": host.modules(),
        "pack_ok": man.get("ok"),
        "out": str((root / "host_pack").resolve()),
    }
    (root / "MODULE_DEMO.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
