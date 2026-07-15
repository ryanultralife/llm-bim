"""Scripted building — agent-style modeling (critical path).

Run:
  python examples/simple_house.py
"""

from __future__ import annotations

from pathlib import Path

from llmbim import Project


def main() -> None:
    out_dir = Path("examples/output")
    out_dir.mkdir(parents=True, exist_ok=True)

    p = Project.create("Simple House")
    p.add_level("L1", 0)
    p.add_level("L2", 3000)
    p.add_grid("U", [0, 5000, 10000])
    p.add_grid("V", [0, 4000, 8000])

    footprint = [(0, 0), (10000, 0), (10000, 8000), (0, 8000)]
    p.create_slab(level="L1", polygon=footprint, thickness_mm=200, name="Slab-L1")

    walls = [
        ((0, 0), (10000, 0), "W-S"),
        ((10000, 0), (10000, 8000), "W-E"),
        ((10000, 8000), (0, 8000), "W-N"),
        ((0, 8000), (0, 0), "W-W"),
    ]
    ids: dict[str, str] = {}
    for start, end, name in walls:
        ids[name] = p.create_wall(
            level="L1",
            start=start,
            end=end,
            thickness_mm=200,
            height_mm=3000,
            name=name,
        )

    p.place_door(host=ids["W-S"], offset_mm=2000, width_mm=900, height_mm=2100, name="Entry")
    p.place_window(
        host=ids["W-N"],
        offset_mm=3000,
        width_mm=1500,
        height_mm=1200,
        sill_mm=900,
        name="NorthWin",
    )
    p.create_room(level="L1", name="Living", boundary=footprint)

    path = out_dir / "simple_house.llmbim.json"
    p.save(path)
    print(f"Wrote {path}")
    print("stats:", p.stats())
    print("Note: drawings/IFC are Claude work packages — see docs/WORK_PACKAGES.md")


if __name__ == "__main__":
    main()
