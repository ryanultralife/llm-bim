"""Domestic / process copper plumbing loop — fitting takeoff demo.

Answers: how many 90° copper fittings of what size?

  python examples/plumbing_loop.py
  llmbim takeoff output/plumbing_loop --kind plumbing
"""

from __future__ import annotations

import json
from pathlib import Path

from llmbim import Project


def build_plumbing_loop(out_dir: Path) -> Project:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = Project.create("Plumbing Loop Demo")
    p.add_level("L1", 0)

    # Simple room for context
    p.create_rect_shell(
        level="L1", x=0, y=0, w=8000, d=6000, height_mm=3000, thickness_mm=200, name_prefix="R"
    )
    p.create_slab(
        level="L1",
        polygon=[(0, 0), (8000, 0), (8000, 6000), (0, 6000)],
        thickness_mm=150,
        name="Slab",
    )

    # CW loop: rectangle in plan at ~900 mm AFF
    # 3/4" main around room, 1/2" drops
    runs = [
        ((500, 500), (7500, 500), "3/4"),
        ((7500, 500), (7500, 5500), "3/4"),
        ((7500, 5500), (500, 5500), "3/4"),
        ((500, 5500), (500, 500), "3/4"),
        # fixture branches
        ((2000, 500), (2000, 200), "1/2"),
        ((4000, 500), (4000, 200), "1/2"),
        ((6000, 500), (6000, 200), "1/2"),
        ((2000, 5500), (2000, 5800), "1/2"),
        ((5000, 5500), (5000, 5800), "1/2"),
    ]
    for start, end, nps in runs:
        p.place_pipe(
            level="L1",
            nps=nps,
            start=start,
            end=end,
            material="copper",
            system="CW",
            z0_mm=900,
        )

    # Four 3/4" 90° elbows at corners
    for i, origin in enumerate([(500, 500), (7500, 500), (7500, 5500), (500, 5500)]):
        p.place_fitting(
            level="L1",
            fitting_type="elbow_90",
            nps="3/4",
            origin=origin,
            name=f"EL90-3/4-{i+1}",
            material="copper",
        )

    # 1/2" 90° at fixture ends
    for i, origin in enumerate(
        [(2000, 200), (4000, 200), (6000, 200), (2000, 5800), (5000, 5800)]
    ):
        p.place_fitting(
            level="L1",
            fitting_type="elbow_90",
            nps="1/2",
            origin=origin,
            name=f"EL90-1/2-{i+1}",
            material="copper",
        )

    # Tees where branches leave the main
    for i, origin in enumerate([(2000, 500), (4000, 500), (6000, 500), (2000, 5500), (5000, 5500)]):
        p.place_fitting(
            level="L1",
            fitting_type="tee",
            nps="3/4",
            origin=origin,
            name=f"TEE-3/4-{i+1}",
            material="copper",
        )

    # Valves
    p.place_fitting(
        level="L1",
        fitting_type="ball_valve",
        nps="3/4",
        origin=(500, 1000),
        name="Main isolation",
        material="copper",
    )
    p.place_fitting(
        level="L1",
        fitting_type="ball_valve",
        nps="1/2",
        origin=(2000, 350),
        name="Fixture stop 1",
        material="copper",
    )

    p.auto_assign()
    p.commit("Plumbing loop copper takeoff model")

    man = p.export_deliverables(out_dir, mode="facility", plan_level="L1", plan_scale=0.02)
    schedule = p.plumbing_schedule()
    (out_dir / "COPPER_90_ELBOWS.json").write_text(
        json.dumps(
            {
                "question": "How many 90° copper fittings of what size?",
                "answer": schedule["copper_90_elbows_by_size"],
                "full_plumbing": schedule,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    meta = {
        "stats": p.stats(),
        "copper_90_by_size": schedule["copper_90_elbows_by_size"],
        "totals": schedule["totals"],
        "deliverables_ok": man.get("ok"),
    }
    (out_dir / "plumbing_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return p


def main() -> None:
    out = Path("output/plumbing_loop")
    p = build_plumbing_loop(out)
    sched = p.plumbing_schedule()
    print(
        json.dumps(
            {
                "out": str(out.resolve()),
                "copper_90_elbows_by_size": sched["copper_90_elbows_by_size"],
                "totals": sched["totals"],
                "open": str((out / "index.html").resolve()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
