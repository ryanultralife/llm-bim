"""Critical-path element commands (Grok fast path)."""

from __future__ import annotations

import pytest

from llmbim import Project
from llmbim_core.errors import ValidationError


def test_slab_door_window_room_grid() -> None:
    p = Project.create("Full Box")
    p.add_level("L1", 0)
    p.add_grid("U", [0, 5000, 10000])
    p.add_grid("V", [0, 8000])

    footprint = [(0, 0), (10000, 0), (10000, 8000), (0, 8000)]
    p.create_slab(level="L1", polygon=footprint, thickness_mm=200, name="F1")

    south = p.create_wall(
        level="L1",
        start=(0, 0),
        end=(10000, 0),
        thickness_mm=200,
        height_mm=3000,
        name="W-S",
    )
    p.create_wall(
        level="L1",
        start=(10000, 0),
        end=(10000, 8000),
        thickness_mm=200,
        height_mm=3000,
        name="W-E",
    )
    p.create_wall(
        level="L1",
        start=(10000, 8000),
        end=(0, 8000),
        thickness_mm=200,
        height_mm=3000,
        name="W-N",
    )
    p.create_wall(
        level="L1",
        start=(0, 8000),
        end=(0, 0),
        thickness_mm=200,
        height_mm=3000,
        name="W-W",
    )

    p.place_door(host=south, offset_mm=2000, width_mm=900, height_mm=2100, name="D1")
    p.place_window(
        host=south,
        offset_mm=5000,
        width_mm=1200,
        height_mm=1200,
        sill_mm=900,
        name="Win1",
    )
    p.create_room(level="L1", name="Living", boundary=footprint)

    s = p.stats()
    assert s["wall"] == 4
    assert s["slab"] == 1
    assert s["door"] == 1
    assert s["window"] == 1
    assert s["room"] == 1
    assert len(p.model.grids) == 2


def test_door_too_wide_fails() -> None:
    p = Project.create()
    p.add_level("L1", 0)
    w = p.create_wall(
        level="L1",
        start=(0, 0),
        end=(1000, 0),
        thickness_mm=200,
        height_mm=3000,
    )
    with pytest.raises(ValidationError):
        p.place_door(host=w, offset_mm=0, width_mm=2000, height_mm=2100)
