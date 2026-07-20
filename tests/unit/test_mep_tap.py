"""Tee-tapping: split an existing run, insert a tee, branch to a target."""

from __future__ import annotations

import math

import pytest
from llmbim import Project
from llmbim_core.errors import NotFoundError, ValidationError


def _seg(p: Project, sid: str) -> tuple[tuple[float, float], tuple[float, float]]:
    el = p.model.get_element(sid)
    s, e = el.params["start_mm"], el.params["end_mm"]
    return (float(s[0]), float(s[1])), (float(e[0]), float(e[1]))


def _length(p: Project, sid: str) -> float:
    (ax, ay), (bx, by) = _seg(p, sid)
    return math.hypot(bx - ax, by - ay)


def _axis_aligned(p: Project, sid: str) -> bool:
    (ax, ay), (bx, by) = _seg(p, sid)
    return abs(ax - bx) < 1 or abs(ay - by) < 1


def test_tap_splits_source_and_branches_to_target() -> None:
    p = Project.create("Tap-Basic", vcs=False)
    p.add_level("L1", 0)
    src = p.place_pipe(
        level="L1", nps="2", start=(0, 0), end=(8000, 0), material="copper", system="CW", z0_mm=0
    )
    r = p.mep_tap(target=(4000, 3000), system="CW")
    assert r["source_id"] == src
    assert r["tap_xy"] == [4000.0, 0.0]

    # original replaced by two collinear pieces whose lengths sum to the original
    ids = {el.id for el in p.model.elements}
    assert src not in ids
    seg_a, seg_b = r["split_ids"]
    assert _seg(p, seg_a) == ((0.0, 0.0), (4000.0, 0.0))
    assert _seg(p, seg_b) == ((4000.0, 0.0), (8000.0, 0.0))
    assert _length(p, seg_a) + _length(p, seg_b) == pytest.approx(8000.0)
    for sid in (seg_a, seg_b):
        el = p.model.get_element(sid)
        assert el.category == "pipe"
        assert el.params["nps"] == "2"
        assert el.params["system"] == "CW"
        assert el.params["z0_mm"] == 0
        assert el.params["length_m"] == pytest.approx(4.0)
        assert el.params["part_qty"] == pytest.approx(4.0)  # takeoff preserved

    # tee at the junction, same nps/material family
    tee = p.model.get_element(str(r["tee_id"]))
    assert tee.params["fitting_type"] == "tee"
    assert tee.params["nps"] == "2"
    assert [float(v) for v in tee.params["origin_mm"]] == [4000.0, 0.0]

    # branch reaches the target; every segment axis-aligned
    branch_ids = list(r["segment_ids"])
    assert branch_ids
    assert _seg(p, branch_ids[0])[0] == (4000.0, 0.0)
    assert _seg(p, branch_ids[-1])[1] == (4000.0, 3000.0)
    for sid in branch_ids + [seg_a, seg_b]:
        assert _axis_aligned(p, sid)
    assert r["branch_nps"] == "2"
    assert r["reducing_tee"] is None

    # pipe takeoff still totals source + branch
    plumbing = p.plumbing_schedule()
    assert plumbing["totals"]["pipe_length_m"] == pytest.approx(8.0 + 3.0, abs=0.01)


def test_tap_snaps_away_from_run_ends() -> None:
    p = Project.create("Tap-Snap", vcs=False)
    p.add_level("L1", 0)
    p.place_pipe(level="L1", nps="2", start=(0, 0), end=(8000, 0), system="CW", z0_mm=0)
    r = p.mep_tap(target=(20, 2000))
    assert r["tap_xy"] == [100.0, 0.0]  # >= 100 mm from the run end
    seg_a, seg_b = r["split_ids"]
    assert _length(p, seg_a) == pytest.approx(100.0)
    assert _length(p, seg_b) == pytest.approx(7900.0)


def test_nearest_source_selection_respects_system_filter() -> None:
    p = Project.create("Tap-Nearest", vcs=False)
    p.add_level("L1", 0)
    cw = p.place_pipe(level="L1", nps="2", start=(0, 0), end=(8000, 0), system="CW", z0_mm=0)
    hw = p.place_pipe(level="L1", nps="2", start=(0, 2000), end=(8000, 2000), system="HW", z0_mm=0)

    # no filter: nearest run wins (HW at 500 mm vs CW at 1500 mm)
    r_near = p.mep_tap(target=(2000, 1500))
    assert r_near["source_id"] == hw
    assert r_near["system"] == "HW"
    assert r_near["edge"]["medium"] == "HW"

    # system filter respected even though the HW run (and its splits) are nearer
    r_cw = p.mep_tap(target=(6000, 1500), system="CW")
    assert r_cw["source_id"] == cw
    assert r_cw["system"] == "CW"


def test_trunk_branch_three_targets_counts_tees_and_elbows() -> None:
    p = Project.create("Tap-Trunk", vcs=False)
    p.add_level("L1", 0)
    # wall blocking the middle branch so it needs elbows to get around
    p.create_wall(
        level="L1", start=(3600, 1200), end=(5400, 1200), thickness_mm=200, height_mm=3000
    )
    r = p.mep_trunk_branch(
        level="L1",
        trunk_start=(0, 0),
        trunk_end=(9000, 0),
        targets=[(1500, 2000), (4500, 2500), (7500, 2000)],
        kind="pipe",
        nps="2",
        branch_nps="1",
        material="copper",
        system="CW",
        z0_mm=0,
    )
    assert r["count"] == 3
    assert len(r["branches"]) == 3
    assert len(set(r["tee_ids"])) == 3

    # every tap is a reducing tee (trunk 2", branch 1")
    for br in r["branches"]:
        assert br["nps"] == "2"
        assert br["branch_nps"] == "1"
        assert br["reducing_tee"] == "reducing tee 2 x 2 x 1"
        # branch terminates at its target
        (bx, by) = _seg(p, br["segment_ids"][-1])[1]
        assert (bx, by) in {(1500.0, 2000.0), (4500.0, 2500.0), (7500.0, 2000.0)}

    # fitting takeoff: exactly 3 tees at trunk size
    tees = p.fitting_takeoff(fitting_type="tee", material="copper")
    assert sum(float(row["qty"]) for row in tees) == pytest.approx(3.0)
    assert all(row["nps"] == "2" for row in tees)

    # elbows: one per bend across all branches (blocked branch must bend)
    branch_elbows = sum(len(br["fitting_ids"]) for br in r["branches"])
    trunk_elbows = len(r["trunk"]["fitting_ids"])
    assert branch_elbows >= 2  # middle branch routed around the wall
    elbows = p.fitting_takeoff(fitting_type="elbow_90", material="copper")
    assert sum(float(row["qty"]) for row in elbows) == pytest.approx(
        branch_elbows + trunk_elbows
    )

    # trunk length preserved across the splits: 2" pipe still totals 9 m
    trunk_len = sum(_length(p, sid) for sid in r["trunk_segment_ids"])
    assert trunk_len == pytest.approx(9000.0)
    for sid in r["trunk_segment_ids"]:
        assert p.model.get_element(sid).params["nps"] == "2"


def test_mep_graph_edges_consistent_after_tap() -> None:
    p = Project.create("Tap-Graph", vcs=False)
    p.add_level("L1", 0)
    trunk = p.mep_autoroute(
        level="L1", start=(0, 0), end=(6000, 0), kind="pipe", nps="2", system="CW", z0_mm=0
    )
    trunk_seg = trunk["segment_ids"][0]
    r = p.mep_tap(target=(3000, 2000))
    seg_a, seg_b = r["split_ids"]

    edges = p.mep_graph()
    trunk_edges = [g for g in edges if g["id"] == trunk["connection_id"]]
    assert len(trunk_edges) == 1
    te = trunk_edges[0]
    # split recorded in-place: original id replaced by the two pieces, in order
    assert trunk_seg not in te["segment_ids"]
    i = te["segment_ids"].index(seg_a)
    assert te["segment_ids"][i + 1] == seg_b
    assert r["tee_id"] in te["fitting_ids"]
    assert te["chain"][te["chain"].index(seg_a) + 1] == r["tee_id"]
    assert te["taps"][0]["tee_id"] == r["tee_id"]
    assert trunk["connection_id"] in r["split_edge_ids"]

    # branch edge: kind mep_tap, chained tee → ... → target
    branch_edges = [g for g in edges if g["id"] == r["connection_id"]]
    assert len(branch_edges) == 1
    be = branch_edges[0]
    assert be["kind"] == "mep_tap"
    assert be["from_id"] == r["tee_id"]
    assert be["tap_of"] == trunk_seg
    assert be["chain"][0] == r["tee_id"]
    assert be["segment_ids"] == r["segment_ids"]

    # no stale reference to the deleted segment anywhere (edges or connections)
    for g in edges:
        assert trunk_seg not in (g.get("segment_ids") or [])
        assert trunk_seg not in (g.get("chain") or [])
    for c in p.model.meta["connections"]:
        assert trunk_seg not in (c.get("segment_ids") or [])
        assert c["id"] != r["connection_id"] or c["kind"] == "mep_tap"


def test_op_dispatch_and_validation_errors() -> None:
    p = Project.create("Tap-Op", vcs=False)
    p.add_level("L1", 0)

    # no run to tap
    with pytest.raises(ValidationError):
        p.mep_tap(target=(1000, 1000))

    pid = p.place_pipe(level="L1", nps="2", start=(0, 0), end=(5000, 0), system="CW", z0_mm=0)

    # target on the run itself — nothing to branch
    with pytest.raises(ValidationError):
        p.mep_tap(target=(2500, 0))
    # bad kind / bad target / non-run source / no HW run to tap
    with pytest.raises(ValidationError):
        p.mep_tap(target=(2500, 2000), kind="chute")
    with pytest.raises(ValidationError):
        p.op("mep_tap", target="")
    with pytest.raises(ValidationError):
        p.mep_tap(target=(2500, 2000), system="HW")
    tee = p.place_fitting(level="L1", fitting_type="tee", nps="2", origin=(9000, 9000))
    with pytest.raises(ValidationError):
        p.mep_tap(target=(2500, 2000), source=tee)
    with pytest.raises(NotFoundError):
        p.mep_tap(target=(2500, 2000), source="nope")
    # trunk_branch needs targets
    with pytest.raises(ValidationError):
        p.mep_trunk_branch(
            level="L1", trunk_start=(0, 5000), trunk_end=(9000, 5000), targets=[]
        )

    # raw op dispatch works and matches the SDK facade
    r = p.op("mep_tap", target=[2500, 2000], source=pid, nps="1")
    assert r["source_id"] == pid
    assert r["branch_nps"] == "1"
    assert r["reducing_tee"] == "reducing tee 2 x 2 x 1"
    r2 = p.op(
        "mep_trunk_branch",
        level="L1",
        trunk_start=[0, 6000],
        trunk_end=[6000, 6000],
        targets=[[3000, 7500]],
        nps="2",
        system="PW",
    )
    assert r2["count"] == 1
    assert r2["branches"][0]["system"] == "PW"
