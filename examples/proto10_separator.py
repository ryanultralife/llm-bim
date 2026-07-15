"""Proto 10 RMF plasma separator — LLM-BIM test case (Fusion parity envelopes).

Source (same geometry class as Fusion INTEC_Proto10_Builder / MB-SEP-PROTO):
  - Al6061 shell 320 OD × 500 L mm
  - End flanges 380 OD × 25 thk
  - Iron yoke envelope 560 × 300 × (shell L + caps)
  - Ultem/PEEK cartridge envelope 298 OD × 450 L
  - Magnet stack rings (4 × ~50 thk) as stacked boxes
  - Pedestal / skid under assembly

This is **equipment-scale BIM**, not nuclear facility scale. Plan is looking
down the bore axis (Z in Fusion bench frame mapped to plan Y for readability:
shell length along X).

Run:
  python examples/proto10_separator.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from llmbim import Project

# --- Fusion RFQ dimensions (mm) ---
SHELL_OD = 320.0
SHELL_ID = 300.0  # approx; wall ~10
SHELL_L = 500.0
FLANGE_OD = 380.0
FLANGE_THK = 25.0
CARTRIDGE_OD = 298.0
CARTRIDGE_ID = 270.0
CARTRIDGE_L = 450.0
YOKE_W = 560.0  # across
YOKE_D = 300.0  # height of yoke side in plan when looking along bore
YOKE_L = SHELL_L + 2 * FLANGE_THK + 40.0
MAGNET_OD = 500.0
MAGNET_ID = 340.0
MAGNET_THK = 50.0
N_MAGNETS = 4
PEDESTAL = (800.0, 800.0, 200.0)  # footprint + pad height


def _circle_poly(cx: float, cy: float, r: float, n: int = 24) -> list[tuple[float, float]]:
    return [
        (cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def build_proto10(out_dir: Path) -> Project:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = Project.create("MB-SEP-PROTO Proto10 Separator")
    p.add_level("Bench", 0)

    # Local origin at shell geometric center in plan
    # X = along bore, Y = transverse
    cx, cy = 0.0, 0.0

    # Pedestal / skid
    p.create_equipment_box(
        level="Bench",
        origin=(cx, cy),
        size=(PEDESTAL[0], PEDESTAL[1], PEDESTAL[2]),
        name="Pedestal pad",
        kind="pedestal",
        centered=True,
        z0_mm=0.0,
    )

    # Iron yoke envelope (outer magnetic return)
    p.create_equipment_box(
        level="Bench",
        origin=(cx, cy),
        size=(YOKE_L, YOKE_W, YOKE_D),
        name="Iron yoke envelope",
        kind="yoke",
        centered=True,
        z0_mm=PEDESTAL[2],
    )

    # Shell — cylinder along +X (Fusion parity OD×L)
    p.create_equipment_box(
        level="Bench",
        origin=(cx, cy),
        size=(SHELL_L, SHELL_OD, SHELL_OD),
        name="Al6061 shell 320OD×500",
        kind="shell",
        shape="cylinder",
        centered=True,
        z0_mm=PEDESTAL[2] + (YOKE_D - SHELL_OD) / 2,
    )

    # End flanges (disk-like cylinders short along X)
    for side, xoff in (("A", -SHELL_L / 2 - FLANGE_THK / 2), ("B", SHELL_L / 2 + FLANGE_THK / 2)):
        p.create_equipment_box(
            level="Bench",
            origin=(cx + xoff, cy),
            size=(FLANGE_THK, FLANGE_OD, FLANGE_OD),
            name=f"End flange {side} 380×25",
            kind="flange",
            shape="cylinder",
            centered=True,
            z0_mm=PEDESTAL[2] + (YOKE_D - FLANGE_OD) / 2,
        )

    # Cartridge cylinder
    p.create_equipment_box(
        level="Bench",
        origin=(cx, cy),
        size=(CARTRIDGE_L, CARTRIDGE_OD, CARTRIDGE_OD),
        name="Ultem cartridge 298×450",
        kind="cartridge",
        shape="cylinder",
        centered=True,
        z0_mm=PEDESTAL[2] + (YOKE_D - CARTRIDGE_OD) / 2,
    )

    # Magnet rings
    span = N_MAGNETS * MAGNET_THK
    x0 = -span / 2 + MAGNET_THK / 2
    for i in range(N_MAGNETS):
        p.create_equipment_box(
            level="Bench",
            origin=(cx + x0 + i * MAGNET_THK, cy),
            size=(MAGNET_THK, MAGNET_OD, MAGNET_OD),
            name=f"N42 ring {i + 1}",
            kind="magnet",
            shape="cylinder",
            centered=True,
            z0_mm=PEDESTAL[2] + (YOKE_D - MAGNET_OD) / 2,
        )

    # Room = clear bench area for drawing label
    clear = 1200.0
    p.create_room(
        level="Bench",
        name="Proto10 assembly envelope",
        boundary=[
            (-clear / 2, -clear / 2),
            (clear / 2, -clear / 2),
            (clear / 2, clear / 2),
            (-clear / 2, clear / 2),
        ],
    )

    # Optional: polygonal "bore outline" as slab for plan readability
    p.create_slab(
        level="Bench",
        polygon=_circle_poly(cx, cy, SHELL_OD / 2, n=32),
        thickness_mm=2.0,
        name="Shell OD plan silhouette",
    )

    # Full pack: BIM + IFC + glTF + assembly STEP + per-part STEP + 2D part sheets
    manifest = p.export_deliverables(
        out_dir,
        mode="part",
        plan_level="Bench",
        plan_scale=0.4,
    )
    if (out_dir / "model.llmbim.json").exists():
        (out_dir / "proto10_separator.llmbim.json").write_text(
            (out_dir / "model.llmbim.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    meta = {
        "source": "MB-SEP-PROTO / Fusion Proto10 RFQ dimensions",
        "honesty": "ENGINEERING ESTIMATE — envelopes only, not full STEP body count",
        "dims_mm": {
            "shell_od": SHELL_OD,
            "shell_l": SHELL_L,
            "flange_od": FLANGE_OD,
            "cartridge_od": CARTRIDGE_OD,
            "cartridge_l": CARTRIDGE_L,
            "yoke": [YOKE_L, YOKE_W, YOKE_D],
            "magnets": {"n": N_MAGNETS, "od": MAGNET_OD, "thk": MAGNET_THK},
        },
        "stats": p.stats(),
        "validation": p.validate(),
        "deliverables": manifest,
    }
    (out_dir / "proto10_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return p


def main() -> None:
    out = Path("examples/output/proto10")
    p = build_proto10(out)
    print(json.dumps({"out": str(out), "stats": p.stats()}, indent=2))


if __name__ == "__main__":
    main()
