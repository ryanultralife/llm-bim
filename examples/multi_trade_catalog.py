"""Multi-trade BIM catalog demo — fire, process, steel, rebar, framing, fixtures.

Answers takeoff questions across CSI divisions:
  - fire 90° elbows by size + sprinkler heads
  - process SS fittings
  - W-shapes / bolts
  - rebar # by size
  - toilets + TP dispensers + toilet hoses

  python examples/multi_trade_catalog.py
  llmbim takeoff output/multi_trade --kind trades
"""

from __future__ import annotations

import json
from pathlib import Path

from llmbim import Project
from llmbim_core.parts_catalog import catalog_summary


def build_multi_trade(out_dir: Path) -> Project:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = Project.create("Multi-Trade Catalog Demo")
    p.add_level("L1", 0)

    # Simple room shell
    p.create_rect_shell(
        level="L1", x=0, y=0, w=12000, d=8000, height_mm=3500, thickness_mm=200, name_prefix="R"
    )
    p.create_slab(
        level="L1",
        polygon=[(0, 0), (12000, 0), (12000, 8000), (0, 8000)],
        thickness_mm=200,
        name="SOG",
    )

    # --- Fire protection (CSI 21) ---
    p.place_pipe(level="L1", nps="4", start=(1000, 7000), end=(11000, 7000), material="fire", system="FP")
    p.place_pipe(level="L1", nps="2", start=(3000, 7000), end=(3000, 2000), material="fire", system="FP")
    p.place_pipe(level="L1", nps="1-1/2", start=(6000, 7000), end=(6000, 2000), material="fire", system="FP")
    for i, nps in enumerate(("4", "4", "2", "2", "1-1/2", "1-1/2")):
        p.place_fitting(
            level="L1",
            fitting_type="elbow_90",
            nps=nps,
            origin=(1000 + i * 800, 7000),
            material="fire",
            system="FP",
        )
    for i in range(12):
        p.place_part(
            level="L1",
            part_id="PT-FP-HEAD-PENDENT_5_6_155F",
            origin=(1500 + (i % 6) * 1500, 2500 + (i // 6) * 2000),
            name=f"SPK-{i+1}",
        )
    p.place_part(level="L1", part_id="PT-FP-EXT-ABC-10", origin=(500, 500), name="FE-1")

    # --- Process SS (CSI 40) ---
    p.place_pipe(level="L1", nps="2", start=(1000, 1000), end=(5000, 1000), material="process", system="PROC")
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="2", origin=(1000, 1000), material="process")
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="2", origin=(5000, 1000), material="process")
    p.place_fitting(level="L1", fitting_type="tee", nps="2", origin=(3000, 1000), material="process")
    p.place_fitting(level="L1", fitting_type="ball_valve", nps="2", origin=(2000, 1000), material="process")
    p.place_part(level="L1", part_id="PT-SS-STRAINER-2", origin=(2500, 1000))

    # --- Domestic copper (CSI 22) ---
    p.place_pipe(level="L1", nps="3/4", start=(8000, 1000), end=(11000, 1000), material="copper")
    for nps, n in (("3/4", 2), ("1/2", 3)):
        for i in range(n):
            p.place_fitting(
                level="L1",
                fitting_type="elbow_90",
                nps=nps,
                origin=(8000 + i * 200, 1200 if nps == "3/4" else 1400),
                material="copper",
            )

    # --- Restroom fixtures & accessories ---
    p.place_part(level="L1", kind="toilet", origin=(9000, 6000), name="WC-1")
    p.place_part(level="L1", kind="toilet", origin=(10000, 6000), name="WC-2")
    p.place_part(level="L1", kind="toilet_ada", origin=(11000, 6000), name="WC-ADA")
    p.place_part(level="L1", kind="toilet_hose", origin=(9000, 5950), name="WC-hose-1")
    p.place_part(level="L1", kind="toilet_hose", origin=(10000, 5950), name="WC-hose-2")
    p.place_part(level="L1", kind="toilet_hose", origin=(11000, 5950), name="WC-hose-3")
    p.place_part(level="L1", kind="tp_dispenser", origin=(9050, 6200), name="TP-1")
    p.place_part(level="L1", kind="tp_dispenser", origin=(10050, 6200), name="TP-2")
    p.place_part(level="L1", part_id="PT-ACC-TP-DOUBLE", origin=(11050, 6200), name="TP-3")
    p.place_part(level="L1", kind="grab_bar", origin=(11000, 6300), name="GB-36")
    p.place_part(level="L1", part_id="PT-ACC-GRAB-42", origin=(11000, 6400), name="GB-42")
    p.place_part(level="L1", kind="lavatory", origin=(8500, 6500), name="LAV-1")
    p.place_part(level="L1", kind="soap_dispenser", origin=(8550, 6600))
    p.place_part(level="L1", kind="mirror", origin=(8500, 6700))
    p.place_part(level="L1", kind="hand_dryer", origin=(8200, 6500))
    p.place_part(level="L1", kind="floor_drain", origin=(9500, 5500))

    # --- Structural steel (CSI 05) ---
    for i, sec in enumerate(("W10x33", "W12x50", "W16x26", "W18x35")):
        p.place_part(
            level="L1",
            section=sec,
            origin=(1500 + i * 2500, 4000),
            length_m=3.5,
            name=f"COL-{sec}",
        )
    p.place_part(level="L1", part_id="PT-STL-BOLT-A325-3_4", origin=(0, 0), qty=48, name="A325 bolts")
    p.place_part(level="L1", part_id="PT-STL-BASE-PL-20", origin=(1500, 4000), qty=4)

    # --- Rebar (CSI 03 20) ---
    p.place_part(level="L1", bar_size="4", length_m=120.0, origin=(0, 0), name="#4 temp")
    p.place_part(level="L1", bar_size="5", length_m=85.0, origin=(0, 0), name="#5 bottom")
    p.place_part(level="L1", bar_size="6", length_m=40.0, origin=(0, 0), name="#6 top")
    p.place_part(level="L1", part_id="PT-RBR-WWF-6X6-W2_9", qty=96.0, origin=(0, 0), name="WWF SOG")  # m2

    # --- Framing ---
    p.place_part(level="L1", part_id="PT-WD-STUD-2X4", length_m=48.0, origin=(0, 0))
    p.place_part(level="L1", part_id="PT-MS-STUD-362-20", length_m=36.0, origin=(0, 0))
    p.place_part(level="L1", part_id="PT-WD-PLY-12", qty=24, origin=(0, 0))

    p.auto_assign()
    p.commit("Multi-trade demo geometry + catalog assignments")

    man = p.export_deliverables(out_dir, mode="facility", plan_level="L1", plan_scale=0.015)
    trades = p.trade_schedule()
    answers = {
        "catalog": catalog_summary(),
        "copper_90_by_size": trades["plumbing"]["copper_90_elbows_by_size"],
        "fire_90_by_size": trades["fire"]["elbow_90_by_size"],
        "sprinkler_heads": trades["fire"]["sprinkler_heads"],
        "toilets_and_tp": [
            r
            for r in trades["fixtures"]
            if r.get("fitting_type") in ("toilet", "tp_dispenser", "toilet_hose")
            or "WC" in str(r.get("part_name", ""))
            or "Toilet" in str(r.get("part_name", ""))
            or "paper" in str(r.get("part_name", "")).lower()
            or "hose" in str(r.get("part_name", "")).lower()
        ],
        "steel_by_section": trades["structural_steel"],
        "rebar_by_size": trades["rebar"],
        "csi_rollup": trades["csi"],
        "deliverables_ok": man.get("ok"),
    }
    (out_dir / "TRADE_ANSWERS.json").write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
    (out_dir / "trade_meta.json").write_text(
        json.dumps({"stats": p.stats(), "catalog": catalog_summary()}, indent=2) + "\n",
        encoding="utf-8",
    )
    return p


def main() -> None:
    out = Path("output/multi_trade")
    build_multi_trade(out)
    a = json.loads((out / "TRADE_ANSWERS.json").read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "out": str(out.resolve()),
                "catalog_parts": a["catalog"]["parts_count"],
                "copper_90": a["copper_90_by_size"],
                "fire_90": a["fire_90_by_size"],
                "heads": a["sprinkler_heads"],
                "steel": [{"part_name": r.get("part_name"), "qty": r.get("qty")} for r in a["steel_by_section"][:8]],
                "rebar": [{"part_name": r.get("part_name"), "qty": r.get("qty")} for r in a["rebar_by_size"]],
                "fixtures": a["toilets_and_tp"],
                "csi_divisions": [r["csi_code"] for r in a["csi_rollup"]],
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
