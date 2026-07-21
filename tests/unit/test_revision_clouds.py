"""Auto-clouding from model diffs + equipment schedule-key linkage (WP-CD-ANATOMY-2).

Closes the CD_COMPLETENESS_STANDARD gaps: "auto-clouding on model diffs"
(revision clouds row) and "schedule-key linkage partial" (equipment tags row).
"""

from __future__ import annotations

from llmbim import Project
from llmbim_drawings.revisions import revision_cloud_rects, revision_rows
from llmbim_drawings.schedules import equipment_marks, export_schedule_csv, schedule_rows


def _base(name: str = "RevClouds") -> Project:
    p = Project.create(name, vcs=False)
    p.add_level("L1", 0)
    p.create_wall(
        level="L1", start=(0, 0), end=(6000, 0), thickness_mm=200, height_mm=3000, name="W1"
    )
    return p


# --- revision_cloud_rects -----------------------------------------------------


def test_added_element_clouded_at_bbox() -> None:
    p = _base()
    prior = p.model.model_copy(deep=True)
    eid = p.create_equipment_box(
        level="L1", origin=(1000, 1000), size=(600, 400, 1200), name="AHU"
    )
    rects = revision_cloud_rects(p.model, prior)
    assert set(rects) == {"L1"}
    (r,) = rects["L1"]
    assert r["element_ids"] == [eid]
    assert (r["x0"], r["y0"], r["x1"], r["y1"]) == (1000.0, 1000.0, 1600.0, 1400.0)


def test_changed_moved_wall_clouds_old_and_new_position() -> None:
    p = _base()
    prior = p.model.model_copy(deep=True)
    wall = p.model.query(category="wall")[0]
    wall.params["start_mm"] = [0.0, 2000.0]
    wall.params["end_mm"] = [6000.0, 2000.0]
    rects = revision_cloud_rects(p.model, prior)
    (r,) = rects["L1"]
    assert r["element_ids"] == [wall.id]
    # union of old (y ≈ -100..100) and new (y ≈ 1900..2100) footprints
    assert r["y0"] <= -99.0
    assert r["y1"] >= 2099.0


def test_removed_element_clouded_at_old_bbox() -> None:
    p = _base()
    eid = p.create_equipment_box(
        level="L1", origin=(8000, 8000), size=(500, 500, 1000), name="TANK"
    )
    prior = p.model.model_copy(deep=True)
    p.delete_element(eid)
    rects = revision_cloud_rects(p.model, prior)
    (r,) = rects["L1"]
    assert r["element_ids"] == [eid]
    # clouded where the prior issue showed it
    assert (r["x0"], r["y0"], r["x1"], r["y1"]) == (8000.0, 8000.0, 8500.0, 8500.0)


def test_nearby_boxes_merge_into_one_cloud() -> None:
    p = _base()
    prior = p.model.model_copy(deep=True)
    e1 = p.create_equipment_box(
        level="L1", origin=(10000, 10000), size=(500, 500, 1000), name="P1"
    )
    # 300 mm clear gap (≤ 500 mm merge tolerance)
    e2 = p.create_equipment_box(
        level="L1", origin=(10800, 10000), size=(500, 500, 1000), name="P2"
    )
    rects = revision_cloud_rects(p.model, prior)
    (r,) = rects["L1"]
    assert r["element_ids"] == sorted([e1, e2])
    assert (r["x0"], r["x1"]) == (10000.0, 11300.0)


def test_distant_boxes_stay_separate() -> None:
    p = _base()
    prior = p.model.model_copy(deep=True)
    p.create_equipment_box(level="L1", origin=(10000, 10000), size=(500, 500, 1000), name="P1")
    # 1500 mm clear gap (> 500 mm merge tolerance)
    p.create_equipment_box(level="L1", origin=(12000, 10000), size=(500, 500, 1000), name="P2")
    rects = revision_cloud_rects(p.model, prior)
    assert len(rects["L1"]) == 2
    assert all(len(r["element_ids"]) == 1 for r in rects["L1"])


def test_level_filtering() -> None:
    p = Project.create("RevLvl", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 4000)
    prior = p.model.model_copy(deep=True)
    p.create_equipment_box(level="L1", origin=(0, 0), size=(500, 500, 1000), name="A")
    p.create_equipment_box(level="L2", origin=(0, 0), size=(500, 500, 1000), name="B")
    both = revision_cloud_rects(p.model, prior)
    assert set(both) == {"L1", "L2"}
    only = revision_cloud_rects(p.model, prior, level="L2")
    assert set(only) == {"L2"}
    assert len(only["L2"]) == 1


def test_no_changes_yields_empty() -> None:
    p = _base()
    prior = p.model.model_copy(deep=True)
    assert revision_cloud_rects(p.model, prior) == {}
    assert revision_rows(p.model, prior, delta="1", date="2026-07-21") == []


# --- SDK hook (checkout-free, real committed history) -------------------------


def test_sdk_revision_clouds_since_committed_version(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLMBIM_OUTPUT_DIR", str(tmp_path / "output"))
    p = Project.create("RevSDK", author="test")
    p.add_level("L1", 0)
    p.create_wall(
        level="L1", start=(0, 0), end=(6000, 0), thickness_mm=200, height_mm=3000, name="W1"
    )
    ver = p.commit("issue 1")["version_id"]
    eid = p.create_equipment_box(
        level="L1", origin=(2000, 2000), size=(600, 400, 1200), name="AHU"
    )
    before = p.model.to_dict()
    rects = p.revision_clouds(since=ver)
    # checkout-free: working model untouched, still dirty vs HEAD
    assert p.model.to_dict() == before
    assert p.status()["clean"] is False
    (r,) = rects["L1"]
    assert r["element_ids"] == [eid]
    assert (r["x0"], r["y0"]) == (2000.0, 2000.0)


# --- revision_rows ------------------------------------------------------------


def test_revision_rows_auto_and_explicit_description() -> None:
    p = _base()
    prior = p.model.model_copy(deep=True)
    p.create_equipment_box(level="L1", origin=(1000, 1000), size=(600, 400, 1200), name="AHU")
    p.model.query(category="wall")[0].params["height_mm"] = 3500
    rows = revision_rows(p.model, prior, delta="2", date="2026-07-21")
    assert rows == [
        {
            "delta": "2",
            "date": "2026-07-21",
            "description": "2 ELEMENTS REVISED",
            "added": 1,
            "changed": 1,
            "removed": 0,
        }
    ]
    rows2 = revision_rows(p.model, prior, delta=3, date="2026-08-01", description="ADDENDUM 1")
    assert rows2[0]["delta"] == "3"
    assert rows2[0]["description"] == "ADDENDUM 1"


# --- equipment schedule-key linkage -------------------------------------------


def test_equipment_marks_deterministic_and_override() -> None:
    p = Project.create("Marks", vcs=False)
    p.add_level("L1", 0)
    ids = sorted(
        p.create_equipment_box(
            level="L1", origin=(i * 3000, 0), size=(500, 500, 1000), name=f"EQ{i}"
        )
        for i in range(3)
    )
    marks = equipment_marks(p.model)
    assert marks == equipment_marks(p.model)  # deterministic
    assert [marks[i] for i in ids] == ["EQ-1", "EQ-2", "EQ-3"]  # sorted-id order
    # explicit params["mark"] wins; generated marks skip claimed keys
    p.model.get_element(ids[0]).params["mark"] = "AHU-1"
    p.model.get_element(ids[1]).params["mark"] = "EQ-1"
    marks2 = equipment_marks(p.model)
    assert marks2[ids[0]] == "AHU-1"
    assert marks2[ids[1]] == "EQ-1"
    assert marks2[ids[2]] == "EQ-2"  # EQ-1 claimed explicitly → next free


def test_equipment_schedule_mark_column_and_csv(tmp_path) -> None:
    p = Project.create("Sched", vcs=False)
    p.add_level("L1", 0)
    a = p.create_equipment_box(level="L1", origin=(0, 0), size=(500, 500, 1000), name="AHU")
    b = p.create_equipment_box(level="L1", origin=(3000, 0), size=(500, 500, 1000), name="FAN")
    p.model.get_element(a).params["mark"] = "AHU-1"
    rows = schedule_rows(p.model, "equipment")
    by_id = {r["id"]: r for r in rows}
    marks = equipment_marks(p.model)
    # schedule and plan-tag helper agree on the same mark per element
    assert by_id[a]["mark"] == marks[a] == "AHU-1"
    assert by_id[b]["mark"] == marks[b]
    assert marks[b].startswith("EQ-")
    # mark column lands in the pack CSV
    csv_path = tmp_path / "equipment.csv"
    export_schedule_csv(p.model, "equipment", csv_path)
    header = csv_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert "mark" in header
