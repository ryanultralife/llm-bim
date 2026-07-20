"""Obstacle-avoiding orthogonal MEP autoroute (grid A* + elbows + risers)."""

from __future__ import annotations

import pytest
from llmbim import Project
from llmbim_core.errors import ValidationError


def _segments(p: Project, ids: list[str]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    out = []
    for sid in ids:
        el = p.model.get_element(sid)
        s, e = el.params["start_mm"], el.params["end_mm"]
        out.append(((float(s[0]), float(s[1])), (float(e[0]), float(e[1]))))
    return out


def _seg_crosses_rect(
    seg: tuple[tuple[float, float], tuple[float, float]],
    rect: tuple[float, float, float, float],
) -> bool:
    (ax, ay), (bx, by) = seg
    x0, x1 = min(ax, bx), max(ax, bx)
    y0, y1 = min(ay, by), max(ay, by)
    rx0, ry0, rx1, ry1 = rect
    return not (x1 < rx0 or x0 > rx1 or y1 < ry0 or y0 > ry1)


def test_autoroute_avoids_blocking_wall() -> None:
    p = Project.create("AR-Wall", vcs=False)
    p.add_level("L1", 0)
    # wall perpendicular to the straight path, blocking it fully at x=3000
    p.create_wall(
        level="L1", start=(3000, -4000), end=(3000, 4000), thickness_mm=200, height_mm=3000
    )
    r = p.mep_autoroute(
        level="L1",
        start=(0, 0),
        end=(6000, 0),
        kind="pipe",
        nps="2",
        material="copper",
        system="CW",
        z0_mm=0,
        clearance_mm=150,
    )
    assert r["fallback"] is None
    assert r["method"] == "grid"
    seg_ids = list(r["segment_ids"])
    assert len(seg_ids) >= 3
    segs = _segments(p, seg_ids)
    # all segments axis-aligned
    for (ax, ay), (bx, by) in segs:
        assert abs(ax - bx) < 1 or abs(ay - by) < 1
    # none crosses the wall footprint (200 thick along x=3000, y -4000..4000)
    wall_rect = (2900.0, -4100.0, 3100.0, 4100.0)
    for seg in segs:
        assert not _seg_crosses_rect(seg, wall_rect), seg
    # elbow at every bend
    assert r["bends"] == len(r["path_mm"]) - 2
    assert len(r["fitting_ids"]) == r["bends"]
    elbows = [p.model.get_element(fid) for fid in r["fitting_ids"]]
    assert all(el.params.get("fitting_type") == "elbow_90" for el in elbows)
    # graph edge recorded, chained end-to-end
    edges = [g for g in p.mep_graph() if g.get("kind") == "mep_autoroute"]
    assert edges and edges[0]["segment_ids"] == seg_ids
    assert len(edges[0]["chain"]) == len(seg_ids) + len(r["fitting_ids"])


def test_autoroute_clear_path_degenerates() -> None:
    p = Project.create("AR-Clear", vcs=False)
    p.add_level("L1", 0)
    straight = p.mep_autoroute(
        level="L1", start=(0, 0), end=(5000, 0), kind="pipe", nps="2", z0_mm=0
    )
    assert straight["method"] == "straight"
    assert len(straight["segment_ids"]) == 1
    assert straight["fitting_ids"] == []
    dogleg = p.mep_autoroute(
        level="L1", start=(0, 1000), end=(4000, 3500), kind="pipe", nps="2", z0_mm=0
    )
    assert dogleg["method"] == "dogleg"
    assert dogleg["fallback"] is None
    assert len(dogleg["segment_ids"]) == 2
    assert len(dogleg["fitting_ids"]) == 1  # one elbow at the corner


def test_autoroute_z_transition_inserts_riser_and_elbows() -> None:
    p = Project.create("AR-Riser", vcs=False)
    p.add_level("L1", 0)
    r = p.mep_autoroute(
        level="L1",
        start=(0, 0),
        end=(4000, 0),
        kind="pipe",
        nps="2",
        z0_mm=0,
        z1_mm=2700,
    )
    assert r["riser_id"]
    riser = p.model.get_element(str(r["riser_id"]))
    assert riser.params.get("vertical") is True
    assert riser.params["z0_mm"] == 0
    assert riser.params["z1_mm"] == 2700
    # straight plan run: 0 bends, but riser adds bottom + top elbows
    assert len(r["fitting_ids"]) == 2
    zs = sorted(float(p.model.get_element(f).params["z0_mm"]) for f in r["fitting_ids"])
    assert zs == [0.0, 2700.0]
    assert r["length_m"] == pytest.approx((4000 + 2700) / 1000.0)


def test_autoroute_feeds_takeoffs() -> None:
    p = Project.create("AR-Takeoff", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(
        level="L1", start=(3000, -4000), end=(3000, 4000), thickness_mm=200, height_mm=3000
    )
    r = p.mep_autoroute(
        level="L1", start=(0, 0), end=(6000, 0), kind="pipe", nps="2", material="copper", z0_mm=0
    )
    assert r["fallback"] is None
    elbows = p.fitting_takeoff(fitting_type="elbow_90", material="copper")
    assert sum(float(row["qty"]) for row in elbows) >= len(r["fitting_ids"]) >= 2
    plumbing = p.plumbing_schedule()
    assert plumbing["totals"]["pipe_length_m"] >= r["length_m"] - 0.001
    pipe_rows = [row for row in plumbing["pipe"] if row.get("nps") == "2"]
    assert pipe_rows and sum(float(row["length_m"]) for row in pipe_rows) > 0


def test_autoroute_op_and_sdk_dispatch() -> None:
    p = Project.create("AR-Op", vcs=False)
    p.add_level("L1", 0)
    # raw op dispatch with list endpoints
    r = p.op("mep_autoroute", level="L1", start=[0, 0], end=[3000, 2000], kind="pipe", nps="2")
    assert r["segment_ids"]
    # fitting element ids as endpoints
    a = p.place_fitting(level="L1", fitting_type="elbow_90", nps="2", origin=(0, 5000))
    b = p.place_fitting(level="L1", fitting_type="tee", nps="2", origin=(4000, 8000))
    r2 = p.mep_autoroute(level="L1", start=a, end=b, kind="pipe", nps="2")
    assert r2["edge"]["from_id"] == a
    assert r2["edge"]["to_id"] == b
    # degenerate inputs rejected cleanly
    with pytest.raises(ValidationError):
        p.mep_autoroute(level="L1", start=(0, 0), end=(0.5, 0.5), kind="pipe")
    with pytest.raises(ValidationError):
        p.mep_autoroute(level="L1", start=(0, 0), end=(1000, 0), kind="chute")
    with pytest.raises(ValidationError):
        p.op("mep_autoroute", level="L1", start="", end=[1000, 0])
