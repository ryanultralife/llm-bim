"""Level schedule + pack drawing list."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.schedules import drawing_list, export_drawing_list, schedule_rows


def test_level_schedule_floor_to_floor():
    p = Project.create("levels", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 3500)
    p.add_level("Roof", 7000)
    p.create_wall(level="L1", start=(0, 0), end=(5000, 0), thickness_mm=200, height_mm=3500)
    rows = schedule_rows(p.model, "level")
    assert len(rows) == 3
    assert rows[0]["name"] == "L1"
    assert rows[0]["floor_to_floor_mm"] == 3500
    assert rows[1]["floor_to_floor_mm"] == 3500
    assert rows[2]["floor_to_floor_mm"] is None
    assert rows[2]["is_top"] is True
    assert rows[0]["element_count"] >= 1


def test_drawing_list_from_pack(tmp_path: Path):
    p = Project.create("draw-list", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    p.place_duct(level="L1", start=(0, 1000), end=(5000, 1000), width_mm=400, height_mm=250)
    out = tmp_path / "pack"
    man = p.export_deliverables(out)
    assert man.get("ok") or (out / "schedules" / "levels.csv").is_file()
    levels_csv = out / "schedules" / "levels.csv"
    assert levels_csv.is_file()
    assert "elevation_mm" in levels_csv.read_text(encoding="utf-8")
    dl = out / "schedules" / "drawing_list.csv"
    assert dl.is_file()
    text = dl.read_text(encoding="utf-8")
    assert "sheet_no" in text
    rows = drawing_list(out)
    assert len(rows) >= 1
    assert any(r["kind"] in {"plan", "elevation", "section", "cad", "sheet"} for r in rows)
