"""MineClean AMD / Superfund cleanup skid — llm-bim equipment pack.

Freestanding industrial product (NOT Proto-10 / isotope geometry).

Source SSOT (Eigen):
  scripts/mineclean_design_basis.py  →  cad/design_basis/mineclean_basis.json

Build:
  python examples/mineclean_skid.py

Outputs:
  examples/output/mineclean/  full deliverables pack (glTF, IFC, STEP, plans, BOM schedules)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import subprocess

from llmbim import Project

# Eigen SSOT is CANONICAL on the `main` branch as mbclean_basis.json (post-ECO-MC-001;
# the old mineclean_basis.json name is retired). The ~/Eigen working tree floats across
# branches, so read the basis by git ref, not from a working-tree copy.
_REL = "cad/design_basis/mbclean_basis.json"


def _eigen_repo() -> Path:
    for c in (Path(__file__).resolve().parents[2] / "Eigen", Path.home() / "Eigen"):
        if (c / ".git").exists():
            return c
    return Path.home() / "Eigen"


def _load_basis() -> dict:
    repo = _eigen_repo()
    for ref in ("origin/main", "main"):
        try:
            r = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{_REL}"],
                               capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout.strip():
                return json.loads(r.stdout)
        except Exception:
            pass
    for p in (repo / _REL, Path.home() / "Eigen" / _REL, Path(_REL)):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    # fallback closed dims (must match Eigen freestanding SSOT)
    return {
        "geometry_mm": {
            "chamber_ID": 500.0,
            "chamber_OD": 516.0,
            "chamber_L": 2500.0,
            "cap_OD": 620.0,
            "cap_thk": 35.0,
            "rmf_bobbin_OD": 700.0,
            "rmf_bobbin_L": 2200.0,
            "skid_W": 2438.0,
            "skid_L": 6058.0,
            "skid_H_overall": 2600.0,
        },
        "duty": {"flow_m3_h": 10.0, "power_kW": 35.0, "primary_mode": "liquid_mhd_plus_ec"},
        "not_an_isotope_machine": True,
        "honesty": "ENGINEERING ESTIMATE — freestanding MineClean",
    }


def build_mineclean(out_dir: Path) -> Project:
    out_dir.mkdir(parents=True, exist_ok=True)
    B = _load_basis()
    g = B["geometry_mm"]
    duty = B.get("duty", {})

    CH_OD = float(g["chamber_OD"])
    CH_L = float(g["chamber_L"])
    CAP_OD = float(g.get("cap_OD", 620))
    CAP_THK = float(g.get("cap_thk", 35))
    BOB_OD = float(g.get("rmf_bobbin_OD", 700))
    BOB_L = float(g.get("rmf_bobbin_L", 2200))
    SK_W = float(g["skid_W"])
    SK_L = float(g["skid_L"])
    SK_H = 300.0

    p = Project.create("MB-MCLEAN MineClean AMD Skid", vcs=False)
    p.add_level("Skid", 0)

    # ISO skid envelope
    skid = p.create_equipment_box(
        level="Skid",
        origin=(0, 0),
        size=(SK_L, SK_W, SK_H),
        name="ISO 20-ft skid frame",
        kind="separator_skid",
        centered=True,
        z0_mm=0.0,
    )

    # EC cell (inlet end, -X)
    p.create_equipment_box(
        level="Skid",
        origin=(-SK_L / 2 + 500, 0),
        size=(400, 350, 400),
        name="Electrocoag cell",
        kind="equipment",
        centered=True,
        z0_mm=SK_H,
    )
    p.create_equipment_box(
        level="Skid",
        origin=(-SK_L / 2 + 1100, 400),
        size=(800, 600, 700),
        name="Inclined-plate clarifier",
        kind="equipment",
        centered=True,
        z0_mm=SK_H,
    )

    # Chamber — cylinder along X (bore horizontal for skid transport)
    z_ch = SK_H + 160
    p.create_equipment_box(
        level="Skid",
        origin=(0, 0),
        size=(CH_L, CH_OD, CH_OD),
        name=f"316L chamber {CH_OD:.0f}OD x {CH_L:.0f}",
        kind="shell",
        shape="cylinder",
        centered=True,
        z0_mm=z_ch,
    )
    # Caps
    for tag, xoff in (("A", -CH_L / 2 - CAP_THK / 2), ("B", CH_L / 2 + CAP_THK / 2)):
        p.create_equipment_box(
            level="Skid",
            origin=(xoff, 0),
            size=(CAP_THK, CAP_OD, CAP_OD),
            name=f"End cap {tag}",
            kind="flange",
            shape="cylinder",
            centered=True,
            z0_mm=z_ch + (CH_OD - CAP_OD) / 2,
        )

    # RMF bobbin envelope around chamber
    p.create_equipment_box(
        level="Skid",
        origin=(0, 0),
        size=(BOB_L, BOB_OD, BOB_OD),
        name=f"RMF stator bobbin {BOB_OD:.0f}OD",
        kind="cartridge",
        shape="cylinder",
        centered=True,
        z0_mm=z_ch + (CH_OD - BOB_OD) / 2,
    )

    # Filter bank (outlet end)
    p.create_equipment_box(
        level="Skid",
        origin=(SK_L / 2 - 600, -300),
        size=(500, 400, 900),
        name="Effluent filter bank",
        kind="equipment",
        centered=True,
        z0_mm=SK_H,
    )
    p.create_equipment_box(
        level="Skid",
        origin=(SK_L / 2 - 600, 350),
        size=(400, 400, 800),
        name="Power / PLC enclosure",
        kind="equipment",
        centered=True,
        z0_mm=SK_H,
    )

    # Ports on skid (process interface)
    p.define_port(skid, "FEED", role="process", medium="AMD_water", position=(-SK_L / 2, 0))
    p.define_port(skid, "EFFLUENT", role="process", medium="polished_water", position=(SK_L / 2, 0))
    p.define_port(skid, "SLUDGE", role="drain", medium="sludge", position=(0, -SK_W / 2))
    p.define_port(skid, "CONCENTRATE", role="process", medium="metal_concentrate", position=(0, SK_W / 2))
    p.define_port(skid, "PWR", role="power", medium="480V", position=(SK_L / 2 - 600, SK_W / 2))
    p.define_port(skid, "CW_IN", role="utility", medium="coolant", position=(-400, -SK_W / 2))
    p.define_port(skid, "CW_OUT", role="utility", medium="coolant", position=(400, -SK_W / 2))

    # Room envelope for plan label
    clear = 800.0
    p.create_room(
        level="Skid",
        name="MineClean skid clear envelope",
        boundary=[
            (-SK_L / 2 - clear, -SK_W / 2 - clear),
            (SK_L / 2 + clear, -SK_W / 2 - clear),
            (SK_L / 2 + clear, SK_W / 2 + clear),
            (-SK_L / 2 - clear, SK_W / 2 + clear),
        ],
    )

    try:
        p.auto_assign()
    except Exception as e:
        print(f"[warn] auto_assign: {e}", file=sys.stderr)
    try:
        p.commit("MineClean freestanding AMD skid geometry + ports")
    except Exception as e:
        # vcs=False or empty delta after re-run — not fatal for export
        print(f"[warn] commit: {e}", file=sys.stderr)

    # Export as reusable machine module
    mod_dir = out_dir / "modules" / "mineclean_skid"
    try:
        p.export_module(mod_dir, kind="machine")
    except Exception as e:
        print(f"[warn] export_module: {e}", file=sys.stderr)

    manifest = p.export_deliverables(
        out_dir,
        mode="part",
        plan_level="Skid",
        plan_scale=0.05,
    )

    meta = {
        "product": "MB-MCLEAN MineClean Field Skid",
        "freestanding": True,
        "not_an_isotope_machine": True,
        "source_ssot": "Eigen scripts/mineclean_design_basis.py",
        "honesty": B.get("honesty", "ENGINEERING ESTIMATE"),
        "duty": duty,
        "geometry_mm": g,
        "ports": ["FEED", "EFFLUENT", "SLUDGE", "CONCENTRATE", "PWR", "CW_IN", "CW_OUT"],
        "stats": p.stats(),
        "validation": p.validate(),
        "deliverables": manifest,
        "module": str(mod_dir),
    }
    (out_dir / "mineclean_meta.json").write_text(json.dumps(meta, indent=2, default=str) + "\n", encoding="utf-8")
    if (out_dir / "model.llmbim.json").exists():
        (out_dir / "mineclean_skid.llmbim.json").write_text(
            (out_dir / "model.llmbim.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    return p


def main() -> None:
    out = Path("examples/output/mineclean")
    p = build_mineclean(out)
    print(json.dumps({"out": str(out.resolve()), "stats": p.stats(), "freestanding": True}, indent=2))


if __name__ == "__main__":
    main()
