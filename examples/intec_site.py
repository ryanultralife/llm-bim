"""INTEC FP separation facility — LLM-BIM test case.

Source of truth for arrangement (ENGINEERING ESTIMATE / design-basis):
  Eigen-discovery/cad/fusion/intec_fusion_params.json  (params_version 2026-06-13.site4)
  Same placements used by Fusion INTEC_Site_Builder and MB-INTEC-SITE Revit path.

Builds:
  - Main building shell 35 m × 48 m × 12 m (0.3 m walls)
  - Receipt annex 31 m × 11 m
  - Hot-cell tunnel, robotic spine, e-beam hub
  - 8 separator vessel cells (6 active / 2 reserved)
  - Support boxes: uncask, declad, cask bay, casking, waste, down-blend, etc.
  - Control / HP / MCA rooms
  - Production Size-B vessel envelopes (Ø610×1200 mm) inside active cells
  - Plans + section + glTF + schedules

Run:
  python examples/intec_site.py
  # or after install:
  python -m examples.intec_site
"""

from __future__ import annotations

import json
from pathlib import Path

from llmbim import Project

# --- engine-derived params (m) — keep in sync with intec_fusion_params.json ---
BLDG_W, BLDG_L, BLDG_H = 35.0, 48.0, 12.0
WALL_T, SLAB_T = 0.3, 1.0
ANNEX_L, ANNEX_D = 31.0, 11.0

# Placements: id, name, x, y, w, d, h (m) — from fusion params
PLACEMENTS: list[dict] = [
    {"id": "TUNNEL", "name": "Hot cell tunnel", "x": 5.5, "y": 2.5, "w": 36.5, "d": 19.3, "h": 9.0},
    {"id": "SPINE", "name": "Robotic spine", "x": 5.5, "y": 10.15, "w": 36.5, "d": 4.0, "h": 9.0},
    {"id": "EBEAM", "name": "E-beam hub", "x": 5.5, "y": 4.0, "w": 7.0, "d": 16.3, "h": 9.0},
    {"id": "UNCASK", "name": "Cask unloading", "x": 1.0, "y": -10.0, "w": 8.0, "d": 10.0, "h": 10.0},
    {"id": "CELL-1", "name": "Sep cell 1 active", "x": 13.0, "y": 16.475, "w": 3.0, "d": 3.0, "h": 9.0, "vessel": True},
    {"id": "CELL-2", "name": "Sep cell 2 active", "x": 20.0, "y": 16.475, "w": 3.0, "d": 3.0, "h": 9.0, "vessel": True},
    {"id": "CELL-3", "name": "Sep cell 3 active", "x": 27.0, "y": 16.475, "w": 3.0, "d": 3.0, "h": 9.0, "vessel": True},
    {"id": "CELL-4", "name": "Sep cell 4 reserved", "x": 34.0, "y": 16.475, "w": 3.0, "d": 3.0, "h": 9.0},
    {"id": "CELL-5", "name": "Sep cell 5 active", "x": 13.0, "y": 4.825, "w": 3.0, "d": 3.0, "h": 9.0, "vessel": True},
    {"id": "CELL-6", "name": "Sep cell 6 active", "x": 20.0, "y": 4.825, "w": 3.0, "d": 3.0, "h": 9.0, "vessel": True},
    {"id": "CELL-7", "name": "Sep cell 7 active", "x": 27.0, "y": 4.825, "w": 3.0, "d": 3.0, "h": 9.0, "vessel": True},
    {"id": "CELL-8", "name": "Sep cell 8 reserved", "x": 34.0, "y": 4.825, "w": 3.0, "d": 3.0, "h": 9.0},
    {"id": "DOWNBLEND", "name": "Down-blend", "x": 1.0, "y": 26.0, "w": 13.0, "d": 8.0, "h": 8.0},
    {"id": "ROBMAINT", "name": "Robot maint", "x": 16.0, "y": 26.0, "w": 12.0, "d": 8.0, "h": 6.0},
    {"id": "WASTE", "name": "Waste handling", "x": 30.0, "y": 26.0, "w": 13.0, "d": 8.0, "h": 9.0},
    {"id": "DECLAD", "name": "Declad / shear", "x": 10.0, "y": -10.0, "w": 8.0, "d": 10.0, "h": 10.0},
    {"id": "CASKBAY", "name": "Cask receipt", "x": 20.0, "y": -10.0, "w": 9.0, "d": 10.0, "h": 10.0},
    {"id": "CASKING", "name": "Product casking", "x": 31.0, "y": -10.0, "w": 14.0, "d": 10.0, "h": 10.0},
    {"id": "CONTROL", "name": "Control room", "x": 44.0, "y": 2.5, "w": 3.8, "d": 9.5, "h": 4.5},
    {"id": "DECON", "name": "Personnel decon", "x": 44.0, "y": 13.0, "w": 3.8, "d": 6.0, "h": 4.5},
    {"id": "HP", "name": "Health physics", "x": 44.0, "y": 20.0, "w": 3.8, "d": 6.0, "h": 4.5},
    {"id": "MCA", "name": "MCA", "x": 44.0, "y": 27.0, "w": 3.8, "d": 7.0, "h": 4.5},
]

# Production Size-B vessel (L&H / MB-INTEC-FAB-001) — plan footprint as bounding box
VESSEL_OD_MM = 610.0
VESSEL_LEN_MM = 1200.0
VESSEL_CL_Z_MM = 1200.0  # centerline height ~1.2 m


def m_to_mm(v: float) -> float:
    return v * 1000.0


def build_intec(out_dir: Path) -> Project:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = Project.create("INTEC FP Separation Facility")
    p.add_level("L0", 0)  # grade / process floor
    p.add_level("L1", m_to_mm(BLDG_H))  # roof reference

    # Site grid (10 m)
    p.add_grid("U", [m_to_mm(x) for x in range(0, 55, 10)], name="Grid-U")
    p.add_grid("V", [m_to_mm(y) for y in range(-15, 45, 10)], name="Grid-V")

    # Foundation slabs (main + annex)
    main_poly = [
        (0.0, 0.0),
        (m_to_mm(BLDG_L), 0.0),
        (m_to_mm(BLDG_L), m_to_mm(BLDG_W)),
        (0.0, m_to_mm(BLDG_W)),
    ]
    p.create_slab(level="L0", polygon=main_poly, thickness_mm=m_to_mm(SLAB_T), name="Slab-main")

    annex_x0, annex_y0 = m_to_mm(1.0), m_to_mm(-ANNEX_D)
    annex_poly = [
        (annex_x0, annex_y0),
        (annex_x0 + m_to_mm(ANNEX_L), annex_y0),
        (annex_x0 + m_to_mm(ANNEX_L), annex_y0 + m_to_mm(ANNEX_D)),
        (annex_x0, annex_y0 + m_to_mm(ANNEX_D)),
    ]
    p.create_slab(level="L0", polygon=annex_poly, thickness_mm=m_to_mm(SLAB_T), name="Slab-annex")

    # Building exterior shell (approx 0–48 m in X, 0–35 m in Y)
    p.create_rect_shell(
        level="L0",
        x=0.0,
        y=0.0,
        w=m_to_mm(BLDG_L),
        d=m_to_mm(BLDG_W),
        height_mm=m_to_mm(BLDG_H),
        thickness_mm=m_to_mm(WALL_T),
        name_prefix="BLDG",
    )

    # Annex shell (south of main)
    p.create_rect_shell(
        level="L0",
        x=annex_x0,
        y=annex_y0,
        w=m_to_mm(ANNEX_L),
        d=m_to_mm(ANNEX_D),
        height_mm=m_to_mm(10.0),
        thickness_mm=m_to_mm(WALL_T),
        name_prefix="ANNEX",
    )

    # Interior station shells + rooms + vessels
    for pl in PLACEMENTS:
        x, y = m_to_mm(pl["x"]), m_to_mm(pl["y"])
        w, d, h = m_to_mm(pl["w"]), m_to_mm(pl["d"]), m_to_mm(pl["h"])
        # Skip full wall shells for tiny cells would explode wall count; use thin shells
        p.create_rect_shell(
            level="L0",
            x=x,
            y=y,
            w=w,
            d=d,
            height_mm=h,
            thickness_mm=200.0,  # interior partition placeholder
            name_prefix=pl["id"],
        )
        p.create_room(
            level="L0",
            name=pl["name"],
            boundary=[(x, y), (x + w, y), (x + w, y + d), (x, y + d)],
        )
        if pl.get("vessel"):
            # Horizontal vessel along cell X, centered in cell plan
            cx = x + w / 2
            cy = y + d / 2
            # Bounding box for Ø610 × L1200 cylinder lying on X
            p.create_equipment_box(
                level="L0",
                origin=(cx, cy),
                size=(VESSEL_LEN_MM, VESSEL_OD_MM, VESSEL_OD_MM),
                name=f"{pl['id']}-SizeB-vessel",
                kind="separator_vessel_size_b",
                shape="cylinder",
                centered=True,
                z0_mm=VESSEL_CL_Z_MM - VESSEL_OD_MM / 2,
            )

    # Stack as equipment
    p.create_equipment_box(
        level="L0",
        origin=(m_to_mm(18.0), m_to_mm(35.5)),
        size=(m_to_mm(1.2), m_to_mm(1.2), m_to_mm(21.0)),
        name="Off-gas stack",
        kind="stack",
        centered=False,
        z0_mm=0.0,
    )

    # Entry door on south main facade
    south_walls = [el for el in p.query(category="wall") if el.name == "BLDG-S"]
    if south_walls:
        p.place_door(
            host=south_walls[0].id,
            offset_mm=m_to_mm(20.0),
            width_mm=1800,
            height_mm=2400,
            name="Main personnel entry",
        )

    # Process / domestic copper water loop (takeoff demo — ENGINEERING ESTIMATE)
    # Main CW spine along tunnel north edge + risers to active sep cells
    p.place_pipe(
        level="L0",
        nps="2",
        start=(m_to_mm(5.5), m_to_mm(22.0)),
        end=(m_to_mm(40.0), m_to_mm(22.0)),
        name="CW main 2\" spine",
        material="copper",
        system="CW",
        z0_mm=3000,
    )
    for nps, x in (("1", 13.0), ("1", 20.0), ("1", 27.0), ("3/4", 13.0), ("3/4", 20.0), ("3/4", 27.0)):
        # branch drops (plan stubs)
        p.place_pipe(
            level="L0",
            nps=nps,
            start=(m_to_mm(x), m_to_mm(22.0)),
            end=(m_to_mm(x), m_to_mm(16.5 if nps == "1" else 4.9)),
            name=f"CW branch {nps}\" x={x}",
            material="copper",
            system="CW",
            z0_mm=2500,
        )
    # 90° elbows at spine / branch junctions + cell ends (count by size)
    for nps, count, x0 in (("2", 2, 5.5), ("1", 6, 13.0), ("3/4", 6, 13.0), ("1/2", 4, 44.0)):
        for i in range(count):
            p.place_fitting(
                level="L0",
                fitting_type="elbow_90",
                nps=nps,
                origin=(m_to_mm(x0 + i * 1.2), m_to_mm(22.0 if nps != "1/2" else 5.0)),
                name=f"Cu 90° {nps}\" #{i+1}",
                material="copper",
                system="CW",
            )
    for nps, n in (("2", 2), ("1", 3), ("3/4", 3)):
        for i in range(n):
            p.place_fitting(
                level="L0",
                fitting_type="tee",
                nps=nps,
                origin=(m_to_mm(10 + i * 5), m_to_mm(22.0)),
                name=f"Cu tee {nps}\" #{i+1}",
                material="copper",
                system="CW",
            )
    p.place_fitting(level="L0", fitting_type="ball_valve", nps="2", origin=(m_to_mm(5.5), m_to_mm(22.0)), name="CW isolation 2\"", material="copper")
    p.place_fitting(level="L0", fitting_type="ball_valve", nps="1", origin=(m_to_mm(13.0), m_to_mm(18.0)), name="Cell CW valve 1\"", material="copper")

    # Assign vessel/equipment parts + wall materials where typed
    p.auto_assign()
    p.commit("INTEC shell, vessels, CW copper plumbing")

    # Full deliverables pack: BIM JSON, IFC, glTF, STEP, construction set, part sheets
    manifest = p.export_deliverables(
        out_dir,
        mode="auto",
        plan_level="L0",
        plan_scale=0.008,
    )
    # Legacy-friendly aliases
    if (out_dir / "model.llmbim.json").exists():
        (out_dir / "intec_site.llmbim.json").write_text(
            (out_dir / "model.llmbim.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    meta = {
        "source": "intec_fusion_params.json params_version 2026-06-13.site4",
        "honesty": "ENGINEERING ESTIMATE — arrangement per INT-GA-001",
        "stats": p.stats(),
        "validation": p.validate(),
        "placements": len(PLACEMENTS),
        "deliverables": manifest,
    }
    (out_dir / "intec_site_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return p


def main() -> None:
    out = Path("examples/output/intec")
    p = build_intec(out)
    print(json.dumps({"out": str(out), "stats": p.stats()}, indent=2))


if __name__ == "__main__":
    main()
