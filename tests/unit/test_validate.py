"""Validation tests."""

from __future__ import annotations

from llmbim import Project


def test_valid_house_has_no_errors() -> None:
    p = Project.create("V")
    p.add_level("L1", 0)
    w = p.create_wall(
        level="L1", start=(0, 0), end=(5000, 0), thickness_mm=200, height_mm=3000
    )
    p.place_door(host=w, offset_mm=1000, width_mm=900, height_mm=2100)
    issues = p.validate()
    assert not any(i["severity"] == "error" for i in issues)


def test_empty_project_errors() -> None:
    p = Project.create("Empty")
    issues = p.validate()
    codes = {i["code"] for i in issues}
    assert "NO_LEVELS" in codes
