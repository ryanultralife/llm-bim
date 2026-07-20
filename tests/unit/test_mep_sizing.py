"""Hydraulic pipe + duct sizing (mep_sizing) — known-value and route tests.

All reference numbers below are hand-computed with the same published
formulas the module documents (Hazen-Williams, Darcy/Swamee-Jain, Huebscher),
so the tests check the physics, not the implementation against itself.
"""

from __future__ import annotations

import pytest
from llmbim_core.errors import ValidationError
from llmbim_core.ids import new_id
from llmbim_core.material_lists import duct_takeoff, pipe_takeoff
from llmbim_core.mep_route import mep_route
from llmbim_core.mep_sizing import (
    HONESTY_NOTE,
    check_duct,
    check_pipe,
    equivalent_diameter_mm,
    size_duct,
    size_pipe,
    size_route,
    validate_runs,
    wsfu_to_lps,
)
from llmbim_core.model import Element, ProjectModel

# --- pipe sizing ---------------------------------------------------------------


def test_size_pipe_copper_1lps_picks_1in() -> None:
    # Copper Type L IDs from parts_catalog.COPPER_NPS:
    #   3/4" id = 19.9 mm -> A = pi*(0.00995)^2 = 3.1103e-4 m2
    #     v = 0.001 / 3.1103e-4 = 3.215 m/s  -> fails 2.4 m/s
    #   1"   id = 26.0 mm -> A = pi*(0.0130)^2 = 5.3093e-4 m2
    #     v = 0.001 / 5.3093e-4 = 1.883 m/s  -> passes 2.4 m/s
    r = size_pipe(1.0, material="copper", max_velocity_ms=2.4)
    assert r["nps"] == "1"
    assert r["velocity_ms"] == pytest.approx(1.883, abs=0.01)
    # Hazen-Williams, C=140, Q=0.001 m3/s, d=0.026 m:
    #   hf = 10.67 * 0.001^1.852 / (140^1.852 * 0.026^4.87)
    #      = 10.67 * 2.780e-6 / (9433 * 1.910e-8) = 0.1646 m/m
    #   kPa/m = 0.1646 * 9.80665 = 1.614
    assert r["gradient_kpa_m"] == pytest.approx(1.614, abs=0.03)
    assert r["honesty"] == HONESTY_NOTE
    # and 3/4" is explicitly among the rejected candidates
    assert any(c["nps"] == "3/4" for c in r["rejected"])


def test_check_pipe_undersized_and_ok() -> None:
    bad = check_pipe("3/4", 1.0, material="copper")
    # v = 3.215 m/s > 2.4 (see above)
    assert bad["velocity_ms"] == pytest.approx(3.215, abs=0.01)
    assert bad["velocity_ok"] is False and bad["ok"] is False
    # gradient at 3/4": hf = 10.67*2.780e-6/(9433*0.0199^4.87 = 5.194e-9)
    #                      = 0.6054 m/m -> 5.94 kPa/m
    assert bad["gradient_kpa_m"] == pytest.approx(5.94, rel=0.02)
    good = check_pipe("1", 1.0, material="copper")
    assert good["ok"] is True
    assert good["honesty"] == HONESTY_NOTE


def test_size_pipe_steel_uses_c120_and_sch40_id() -> None:
    r = size_pipe(1.0, material="steel", max_velocity_ms=2.4)
    # Sch40: 1" id=26.6 -> v = 0.001/(pi*0.0133^2) = 1.800 m/s -> passes
    assert r["nps"] == "1"
    assert r["hw_c"] == 120.0
    assert r["velocity_ms"] == pytest.approx(1.800, abs=0.01)
    # C=120 gradient must exceed the copper C=140 gradient at similar id
    assert r["gradient_kpa_m"] > 1.4


def test_size_pipe_monotone_in_flow() -> None:
    ids = []
    for q in (0.2, 0.5, 1.0, 2.0, 4.0, 8.0):
        ids.append(float(size_pipe(q, material="copper")["id_mm"]))
    assert ids == sorted(ids)
    assert ids[0] < ids[-1]


def test_size_pipe_input_validation() -> None:
    with pytest.raises(ValidationError):
        size_pipe(0.0)
    with pytest.raises(ValidationError):
        size_pipe(1.0, fixture_units=10.0)  # ambiguous: both given
    with pytest.raises(ValidationError):
        size_pipe(1.0, material="unobtainium")


def test_wsfu_conversion_and_sizing() -> None:
    # Hunter table anchor: 10 WSFU -> 14.6 gpm -> 14.6 * 0.0630902 = 0.9211 L/s
    assert wsfu_to_lps(10.0) == pytest.approx(0.9211, abs=0.002)
    # interpolation between (2, 5.0) and (3, 6.5): 2.5 WSFU -> 5.75 gpm
    assert wsfu_to_lps(2.5) == pytest.approx(5.75 * 0.0630902, abs=0.002)
    # monotone
    vals = [wsfu_to_lps(x) for x in (1, 5, 20, 100, 500, 1500)]
    assert vals == sorted(vals)
    # 0.9211 L/s copper: 3/4" v = 0.9211e-3/3.1103e-4 = 2.962 > 2.4;
    # 1" v = 0.9211e-3/5.3093e-4 = 1.735 <= 2.4 -> 1"
    r = size_pipe(fixture_units=10.0)
    assert r["nps"] == "1"
    assert r["fixture_units"] == 10.0
    assert r["velocity_ms"] == pytest.approx(1.735, abs=0.01)


# --- duct sizing ---------------------------------------------------------------


def test_size_duct_1000m3h_equal_friction() -> None:
    # 1000 m3/h = 0.27778 m3/s at 0.8 Pa/m, eps=0.09 mm, rho=1.2, nu=1.5e-5.
    # Hand bisection: D=0.285 m -> A=0.063794, v=4.355 m/s,
    #   Re = 4.355*0.285/1.5e-5 = 82,740; Swamee-Jain f = 0.0202;
    #   dp/L = 0.0202*1.2*18.96/(2*0.285) = 0.804 Pa/m  (~target)
    # D=0.28 m gives 0.877 Pa/m (too high) -> solution ~285 mm.
    r = size_duct(1000.0, friction_pa_m=0.8)
    assert 260.0 <= r["round_d_mm"] <= 320.0
    assert r["governed_by"] == "friction"
    assert r["round_velocity_ms"] == pytest.approx(4.3, abs=0.3)
    # module rounds D up to 5 mm, so actual friction is at or under target
    assert r["round_friction_pa_m"] <= 0.8 + 1e-6
    # rectangular equivalent (Huebscher), aspect <= 4:1, De covers the round D
    w, h = float(r["width_mm"]), float(r["height_mm"])
    assert w % 50 == 0 and h % 50 == 0
    assert w / h <= 4.0
    assert equivalent_diameter_mm(w, h) >= r["round_d_mm"] - 1e-6
    assert r["velocity_ms"] <= 7.5
    assert r["honesty"] == HONESTY_NOTE


def test_size_duct_velocity_governed() -> None:
    # High allowed friction forces a small friction-based D; the 7.5 m/s cap
    # then governs: D_vel = sqrt(4*0.27778/(pi*7.5)) = 0.2172 m
    r = size_duct(1000.0, friction_pa_m=5.0)
    assert r["governed_by"] == "velocity"
    assert r["round_d_mm"] == pytest.approx(220.0, abs=5.0)
    assert r["round_velocity_ms"] <= 7.5


def test_size_duct_monotone_in_flow() -> None:
    ds = [float(size_duct(q)["round_d_mm"]) for q in (200.0, 500.0, 1000.0, 3000.0, 8000.0)]
    assert ds == sorted(ds)
    assert ds[0] < ds[-1]


def test_size_duct_round_shape_and_validation() -> None:
    r = size_duct(1000.0, shape="round")
    assert "width_mm" not in r
    assert r["velocity_ms"] == r["round_velocity_ms"]
    with pytest.raises(ValidationError):
        size_duct(0.0)
    with pytest.raises(ValidationError):
        size_duct(1000.0, method="static_regain")
    with pytest.raises(ValidationError):
        size_duct(1000.0, shape="oval")


def test_check_duct_known_values() -> None:
    # 350x200: Huebscher De = 1.30*(70000)^0.625/(550)^0.25
    #        = 1.30*1067.1/4.8428 = 286.4 mm
    # v = 0.27778/(0.35*0.20) = 3.968 m/s; friction at De ~ 0.785 Pa/m
    r = check_duct(350.0, 200.0, 1000.0)
    assert r["equivalent_d_mm"] == pytest.approx(286.4, abs=1.0)
    assert r["velocity_ms"] == pytest.approx(3.968, abs=0.01)
    assert r["friction_pa_m"] == pytest.approx(0.785, abs=0.03)
    assert r["ok"] is True
    # undersized 200x150: v = 0.27778/0.03 = 9.26 m/s > 7.5
    bad = check_duct(200.0, 150.0, 1000.0)
    assert bad["velocity_ms"] == pytest.approx(9.259, abs=0.02)
    assert bad["velocity_ok"] is False and bad["ok"] is False
    assert bad["honesty"] == HONESTY_NOTE


# --- route application ---------------------------------------------------------


def _model_with_endpoints() -> tuple[ProjectModel, str, str]:
    m = ProjectModel(name="mep-sizing-test")
    m.add_level("L1", 0)
    lvl = m.get_level("L1").id
    a = Element(id=new_id("eq"), category="equipment", name="A", level_id=lvl, params={"origin_mm": [0, 0]})
    b = Element(id=new_id("eq"), category="equipment", name="B", level_id=lvl, params={"origin_mm": [4000, 3000]})
    m.add_element(a)
    m.add_element(b)
    return m, a.id, b.id


def test_size_route_pipe_apply_updates_params_and_takeoff() -> None:
    m, a, b = _model_with_endpoints()
    r = mep_route(m, a, b, kind="pipe", nps="3/4", material="copper", system="CW")
    edge = m.meta["mep_graph"][0]
    res = size_route(m, edge, flow_lps=1.0, apply=True)
    assert res["kind"] == "pipe"
    assert res["sizing"]["nps"] == "1"  # same 1.0 L/s copper reference as above
    assert res["applied"] is True
    assert res["honesty"] == HONESTY_NOTE
    # segment params updated with the takeoff-visible keys + provenance note
    for sid in r["segment_ids"]:
        el = m.get_element(sid)
        assert el.params["nps"] == "1"
        assert el.params["sized_by"] == "mep_sizing"
        assert el.params["flow_lps"] == pytest.approx(1.0)
        assert el.type_id == "PT-CU-PIPE-1"  # part reassigned to the new size
    # live edge updated too
    assert m.meta["mep_graph"][0]["nps"] == "1"
    assert m.meta["mep_graph"][0]["sized_by"] == "mep_sizing"
    # takeoff still counts the run, now under the new NPS
    # (dogleg (0,0)->(4000,3000) = 4 m + 3 m = 7 m of pipe)
    rows = pipe_takeoff(m, nps="1")
    assert rows, "resized run missing from pipe takeoff"
    assert sum(float(x["length_m"]) for x in rows) == pytest.approx(7.0, abs=0.01)
    assert not pipe_takeoff(m, nps="3/4")  # nothing left at the old size
    # corner elbow resized along with the run
    fid = r["fitting_ids"][0]
    assert m.get_element(fid).params["nps"] == "1"


def test_size_route_duct_apply_and_takeoff() -> None:
    m, a, b = _model_with_endpoints()
    r = mep_route(m, a, b, kind="duct", width_mm=200.0, height_mm=150.0, system="SA")
    edge = m.meta["mep_graph"][0]
    res = size_route(m, edge, flow_m3h=1000.0, apply=True)
    assert res["kind"] == "duct"
    w = float(res["sizing"]["width_mm"])
    h = float(res["sizing"]["height_mm"])
    assert w * h > 200.0 * 150.0  # grew from the undersized guess
    for sid in r["segment_ids"]:
        el = m.get_element(sid)
        assert el.params["width_mm"] == w
        assert el.params["height_mm"] == h
        assert el.params["sized_by"] == "mep_sizing"
    rows = duct_takeoff(m)
    assert len(rows) == len(r["segment_ids"])
    assert all(row["width_mm"] == w and row["height_mm"] == h for row in rows)
    # takeoff length preserved (7 m dogleg) and area follows the new size
    total_len = sum(float(row["length_m"]) for row in rows)
    assert total_len == pytest.approx(7.0, abs=0.01)
    assert sum(float(row["area_m2"]) for row in rows) == pytest.approx(
        2.0 * (w + h) / 1000.0 * total_len, abs=0.05
    )


def test_size_route_accepts_segment_id_list_and_validates_input() -> None:
    m, a, b = _model_with_endpoints()
    r = mep_route(m, a, b, kind="pipe", nps="1/2", material="copper", system="CW")
    res = size_route(m, list(r["segment_ids"]), flow_lps=1.0, apply=True)
    assert res["sizing"]["nps"] == "1"
    assert m.get_element(r["segment_ids"][0]).params["nps"] == "1"
    with pytest.raises(ValidationError):
        size_route(m, list(r["segment_ids"]))  # no flow given
    with pytest.raises(ValidationError):
        size_route(m, [])


def test_validate_runs_ok_undersized_and_no_flow() -> None:
    m, a, b = _model_with_endpoints()
    # run 1: sized correctly at 1.0 L/s (apply stores flow on edge + segments)
    mep_route(m, a, b, kind="pipe", nps="3/4", material="copper", system="CW")
    size_route(m, m.meta["mep_graph"][0], flow_lps=1.0, apply=True)
    # run 2: undersized 1/2" copper carrying 1.0 L/s
    #   (id 13.8 mm -> v = 0.001/(pi*0.0069^2) = 6.69 m/s >> 2.4)
    r2 = mep_route(m, b, a, kind="pipe", nps="1/2", material="copper", system="HW")
    m.meta["mep_graph"][1]["flow_lps"] = 1.0
    # run 3: no flow data anywhere
    mep_route(m, a, b, kind="pipe", nps="2", material="copper", system="CW")

    rows = validate_runs(m)
    assert len(rows) == 3
    by_id = {row["edge_id"]: row for row in rows}
    ok_row = by_id[m.meta["mep_graph"][0]["id"]]
    assert ok_row["status"] == "ok" and ok_row["ok"] is True
    bad_row = by_id[r2["edge"]["id"]]
    assert bad_row["status"] == "warning" and bad_row["ok"] is False
    assert float(bad_row["velocity_ms"]) == pytest.approx(6.69, abs=0.05)
    noflow_row = by_id[m.meta["mep_graph"][2]["id"]]
    assert noflow_row["status"] == "no flow data"
    assert all(row["honesty"] == HONESTY_NOTE for row in rows)


def test_validate_runs_reads_segment_flow_params_for_ducts() -> None:
    m, a, b = _model_with_endpoints()
    r = mep_route(m, a, b, kind="duct", width_mm=200.0, height_mm=150.0, system="SA")
    # flow stored on a segment, not the edge: 1000 m3/h in 200x150 -> 9.26 m/s
    m.get_element(r["segment_ids"][0]).params["flow_m3h"] = 1000.0
    rows = validate_runs(m)
    assert len(rows) == 1
    assert rows[0]["status"] == "warning"
    assert float(rows[0]["velocity_ms"]) == pytest.approx(9.259, abs=0.02)
