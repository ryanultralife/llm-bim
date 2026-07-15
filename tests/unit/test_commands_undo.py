"""Command bus undo/redo tests."""

from __future__ import annotations

from llmbim import Project


def test_undo_redo_wall() -> None:
    p = Project.create("Undo House")
    p.add_level("L1", 0)
    wid = p.create_wall(
        level="L1",
        start=(0, 0),
        end=(5000, 0),
        thickness_mm=200,
        height_mm=3000,
    )
    assert p.stats().get("wall") == 1
    p.undo()  # undo wall
    assert p.stats().get("wall", 0) == 0
    p.redo()
    assert p.stats().get("wall") == 1
    assert p.model.get_element(wid).category == "wall"


def test_delete_and_undo() -> None:
    p = Project.create()
    p.add_level("L1", 0)
    wid = p.create_wall(
        level="L1",
        start=(0, 0),
        end=(1000, 0),
        thickness_mm=100,
        height_mm=2700,
    )
    p.delete_element(wid)
    assert p.stats().get("wall", 0) == 0
    p.undo()
    assert p.stats().get("wall") == 1
