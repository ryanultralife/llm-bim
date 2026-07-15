"""Smoke tests for bootstrap semantic model + SDK."""

from __future__ import annotations

from pathlib import Path

import pytest

from llmbim import Project
from llmbim_core.errors import GeometryDegenerateError, NotFoundError


def test_create_levels_and_wall(tmp_path: Path) -> None:
    p = Project.create("Smoke House")
    l1 = p.add_level("L1", 0)
    l2 = p.add_level("L2", 3000)
    assert l1.startswith("lvl_")
    assert l2.startswith("lvl_")

    wid = p.create_wall(
        level="L1",
        start=(0, 0),
        end=(10_000, 0),
        thickness_mm=200,
        height_mm=3000,
        name="W-North",
    )
    assert wid.startswith("wal_")
    walls = p.query(category="wall")
    assert len(walls) == 1
    assert walls[0].params["length_mm"] == pytest.approx(10_000)

    out = tmp_path / "smoke.llmbim.json"
    p.save(out)
    p2 = Project.open(out)
    assert p2.name == "Smoke House"
    assert p2.stats()["wall"] == 1
    assert len(p2.levels()) == 2


def test_zero_length_wall_rejected() -> None:
    p = Project.create()
    p.add_level("L1", 0)
    with pytest.raises(GeometryDegenerateError):
        p.create_wall(
            level="L1",
            start=(0, 0),
            end=(0, 0),
            thickness_mm=200,
            height_mm=3000,
        )


def test_missing_level() -> None:
    p = Project.create()
    with pytest.raises(NotFoundError):
        p.create_wall(
            level="Nope",
            start=(0, 0),
            end=(1000, 0),
            thickness_mm=200,
            height_mm=3000,
        )
