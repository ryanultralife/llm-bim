"""Scripted building — grows into golden e2e (PR-14).

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

    # 10m x 8m rectangle footprint walls
    walls = [
        ((0, 0), (10000, 0), "W-S"),
        ((10000, 0), (10000, 8000), "W-E"),
        ((10000, 8000), (0, 8000), "W-N"),
        ((0, 8000), (0, 0), "W-W"),
    ]
    for start, end, name in walls:
        p.create_wall(
            level="L1",
            start=start,
            end=end,
            thickness_mm=200,
            height_mm=3000,
            name=name,
        )

    path = out_dir / "simple_house.llmbim.json"
    p.save(path)
    print(f"Wrote {path}")
    print("stats:", p.stats())


if __name__ == "__main__":
    main()
