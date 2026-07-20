"""Requirements-driven equipment auto-placement (derived, deterministic, honest)."""

from __future__ import annotations

from typing import Any

import pytest
from llmbim import Project
from llmbim_core.auto_place import PLACEMENT_BASIS
from llmbim_core.errors import ValidationError

ROOM_W = 12000.0
ROOM_D = 9000.0


def _make_room(name: str = "Process Bay") -> tuple[Project, list[str]]:
    p = Project.create("AutoPlace", vcs=False)
    p.add_level("L1", 0)
    wall_ids = p.create_rect_shell(
        level="L1", x=0, y=0, w=ROOM_W, d=ROOM_D, height_mm=3500, thickness_mm=200, name_prefix="B"
    )
    p.create_room(
        level="L1",
        name=name,
        boundary=[(0, 0), (ROOM_W, 0), (ROOM_W, ROOM_D), (0, ROOM_D)],
    )
    return p, wall_ids


def _rects(r: dict[str, Any]) -> list[tuple[list[float], list[float]]]:
    """(footprint, reserved) rect pairs [x0,y0,x1,y1] for each placed item."""
    return [(e["footprint_mm"], e["reserved_mm"]) for e in r["placed"]]


def _overlap(a: list[float], b: list[float], tol: float = 0.5) -> bool:
    return (
        min(a[2], b[2]) - max(a[0], b[0]) > tol
        and min(a[3], b[3]) - max(a[1], b[1]) > tol
    )


FOUR_ITEMS = [
    {"name": "Glovebox A", "w_mm": 2400, "d_mm": 1200, "h_mm": 2200},
    {"name": "Fume Hood", "w_mm": 1800, "d_mm": 900, "h_mm": 2400, "clearance_front_mm": 1500},
    {"name": "Workbench", "w_mm": 1800, "d_mm": 750, "h_mm": 900},
    {"name": "Acid Cabinet", "w_mm": 900, "d_mm": 600, "h_mm": 2000},
]


def test_perimeter_places_all_without_overlap_inside_room() -> None:
    p, _ = _make_room()
    r = p.auto_place(room="Process Bay", items=FOUR_ITEMS)
    assert r["unplaced"] == []
    assert len(r["placed"]) == 4
    assert r["strategy"] == "perimeter"
    assert r["room"] == "Process Bay"
    rects = _rects(r)
    # zero overlaps: footprint x footprint AND footprint x other's clearance zone
    for i in range(len(rects)):
        for j in range(len(rects)):
            if i == j:
                continue
            fp_i, res_i = rects[i]
            fp_j, _res_j = rects[j]
            assert not _overlap(fp_i, fp_j), (i, j)
            assert not _overlap(res_i, fp_j), ("reserved", i, "footprint", j)
    for fp, res in rects:
        # footprint and clearance zone fully inside the room boundary
        for rect in (fp, res):
            assert rect[0] >= -0.01 and rect[1] >= -0.01
            assert rect[2] <= ROOM_W + 0.01 and rect[3] <= ROOM_D + 0.01
        # back within tolerance of a wall (some side sits on the boundary)
        assert (
            abs(fp[0]) < 1.0
            or abs(fp[1]) < 1.0
            or abs(fp[2] - ROOM_W) < 1.0
            or abs(fp[3] - ROOM_D) < 1.0
        ), fp
    # every placed item is a real equipment element with matching coordinates
    for e in r["placed"]:
        el = p.model.get_element(e["id"])
        assert el.category == "equipment"
        assert el.params["origin_mm"] == e["origin_mm"]


def test_perimeter_walk_order_longest_edge_first() -> None:
    p, _ = _make_room()
    r = p.auto_place(
        room="Process Bay",
        items=[{"name": "Big Bench", "w_mm": 3000, "d_mm": 800, "h_mm": 900}],
    )
    (e,) = r["placed"]
    # longest edges are the 12 m north/south walls — first item lands on one of them
    fp = e["footprint_mm"]
    assert abs(fp[1]) < 1.0 or abs(fp[3] - ROOM_D) < 1.0


def test_door_swing_zone_is_respected() -> None:
    p, wall_ids = _make_room()
    # door on the south wall (0,0)->(12000,0): opening x 5500..6400
    p.place_door(host=wall_ids[0], offset_mm=5500, width_mm=900, height_mm=2100)
    items = [
        {"name": f"Rack {chr(65 + i)}", "w_mm": 2000, "d_mm": 800, "h_mm": 2000}
        for i in range(8)
    ]
    r = p.auto_place(room="Process Bay", items=items)
    assert r["unplaced"] == []
    # swing zone: opening +/- (door width + 300) margin, same depth into the room
    swing = [5500 - 1200.0, 0.0, 6400 + 1200.0, 1200.0]
    south = []
    for e in r["placed"]:
        fp = e["footprint_mm"]
        assert not _overlap(fp, swing), fp
        if abs(fp[1]) < 1.0:
            south.append(fp)
    # the south wall was actually used, so the skip mattered
    assert south


def test_oversized_item_reported_unplaced_with_reason() -> None:
    p, _ = _make_room()
    r = p.auto_place(
        room="Process Bay",
        items=[
            {"name": "Fits", "w_mm": 1200, "d_mm": 600, "h_mm": 900},
            {"name": "Mega Autoclave", "w_mm": 20000, "d_mm": 3000, "h_mm": 2500},
            {"name": "Too Deep", "w_mm": 1000, "d_mm": 11500, "h_mm": 2000},
        ],
    )
    assert len(r["placed"]) == 1
    assert r["placed"][0]["name"] == "Fits"
    unplaced = {u["name"]: u for u in r["unplaced"]}
    assert set(unplaced) == {"Mega Autoclave", "Too Deep"}
    for u in unplaced.values():
        assert u["reason"].strip()
    assert r["ok"] is False
    # nothing was silently created for the unplaced items
    names = {el.name for el in p.model.query(category="equipment")}
    assert "Mega Autoclave" not in names and "Too Deep" not in names


def test_deterministic_same_inputs_same_coordinates() -> None:
    results = []
    for _ in range(2):
        p, wall_ids = _make_room()
        p.place_door(host=wall_ids[0], offset_mm=2000, width_mm=900, height_mm=2100)
        r = p.auto_place(room="Process Bay", items=FOUR_ITEMS)
        results.append(
            [(e["name"], e["origin_mm"], e["size_mm"], e["rotation_deg"]) for e in r["placed"]]
        )
    assert results[0] == results[1]


def test_grid_strategy_rows_with_aisle_separation() -> None:
    p, _ = _make_room()
    items = [
        {"name": f"Skid {i}", "w_mm": 4000, "d_mm": 1000, "h_mm": 1500} for i in range(3)
    ]
    r = p.auto_place(room="Process Bay", items=items, strategy="grid", aisle_mm=1200)
    assert r["unplaced"] == []
    assert len(r["placed"]) == 3
    fps = sorted((e["footprint_mm"] for e in r["placed"]), key=lambda f: (f[1], f[0]))
    row_ys = sorted({fp[1] for fp in fps})
    assert len(row_ys) == 2  # 2 in first row, 1 wraps to a second row
    # rows separated by at least the aisle
    first_row_bottom = max(fp[3] for fp in fps if fp[1] == row_ys[0])
    assert row_ys[1] - first_row_bottom >= 1200 - 0.01
    # no overlaps incl. clearance zones
    rects = _rects(r)
    for i in range(len(rects)):
        for j in range(len(rects)):
            if i != j:
                assert not _overlap(rects[i][0], rects[j][0])
                assert not _overlap(rects[i][1], rects[j][0])


def test_existing_equipment_is_avoided() -> None:
    p, _ = _make_room()
    # pre-existing gear parked against the north wall, left half
    p.create_equipment_box(
        level="L1", origin=(0, ROOM_D - 1500), size=(6000, 1500, 2000), name="Legacy Tank"
    )
    r = p.auto_place(
        room="Process Bay",
        items=[{"name": "New Unit", "w_mm": 2000, "d_mm": 1000, "h_mm": 2000}],
    )
    assert r["unplaced"] == []
    legacy = [0.0, ROOM_D - 1500, 6000.0, ROOM_D]
    fp, res = _rects(r)[0]
    assert not _overlap(fp, legacy)
    assert not _overlap(res, legacy)


def test_placed_items_in_equipment_schedule_and_tagged() -> None:
    p, _ = _make_room()
    r = p.auto_place(room="Process Bay", items=FOUR_ITEMS)
    rows = p.schedule("equipment")
    row_ids = {row["id"] for row in rows}
    for e in r["placed"]:
        assert e["id"] in row_ids
        el = p.model.get_element(e["id"])
        assert el.params["placement_basis"] == PLACEMENT_BASIS
        assert "derived" in el.params["placement_basis"]
        assert el.params["clearance_front_mm"] >= 0
        assert el.params["room"] == "Process Bay"
    assert r["placement_basis"] == PLACEMENT_BASIS


def test_op_and_sdk_dispatch_and_validation() -> None:
    p, _ = _make_room()
    # raw registry op dispatch
    r = p.op(
        "auto_place",
        room="Process Bay",
        items=[{"name": "Op Unit", "w_mm": 1000, "d_mm": 800, "h_mm": 1200}],
    )
    assert len(r["placed"]) == 1
    # by-needs aggregation across rooms
    p.create_room(
        level="L1", name="Utility", boundary=[(15000, 0), (21000, 0), (21000, 5000), (15000, 5000)]
    )
    agg = p.auto_place_by_needs(
        assignments=[
            {
                "room": "Utility",
                "items": [{"name": "AHU", "w_mm": 2500, "d_mm": 1200, "h_mm": 1800}],
                "strategy": "grid",
            },
            {
                "room": "Process Bay",
                "items": [{"name": "Chiller", "w_mm": 1500, "d_mm": 900, "h_mm": 1600}],
            },
        ]
    )
    assert agg["rooms"] == 2
    assert agg["placed_count"] == 2
    assert agg["unplaced_count"] == 0
    assert agg["ok"] is True
    utility = p.model.get_element(agg["results"][0]["placed"][0]["id"])
    assert utility.params["room"] == "Utility"
    # bad input is rejected loudly
    with pytest.raises(ValidationError):
        p.auto_place(room="No Such Room", items=FOUR_ITEMS)
    with pytest.raises(ValidationError):
        p.auto_place(room="Process Bay", items=[])
    with pytest.raises(ValidationError):
        p.auto_place(room="Process Bay", items=FOUR_ITEMS, strategy="teleport")
    with pytest.raises(ValidationError):
        p.auto_place(
            room="Process Bay", items=[{"name": "No Size", "w_mm": 1000, "h_mm": 100}]
        )
    with pytest.raises(ValidationError):
        p.auto_place_by_needs(assignments=[])
