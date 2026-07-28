"""WS1 (excellence audit 2026-07-21) drift pins — the Schad flagship routes
REAL MEP, not note markers.

Guards against regression to the #1 audit gap ("FULL MEP = zero routed MEP")
and against the re-grade residuals #6/#7/#8:

* every run goes through the Manhattan A* engine (``mep_autoroute``) — NO
  diagonal plan segments, elbows at bends, wall obstacles respected (honest
  ``fallback: dogleg`` where a run penetrates a wall);
* real flow terminals (category ``fixture`` → IfcFlowTerminal) stand at the
  plumbing-fixture basis positions, and the routed graph emits
  IfcDistributionPort / IfcRelConnectsPortToElement / IfcRelConnectsPorts;
* the calc text, the routed geometry, and the takeoff share ONE sizing source
  (``schad_mep._dcw_main_sizing`` / ``_feeder_trade`` from
  ``llmbim_core.mep_sizing``);
* fire protection is not routed per the basis — the empty fire takeoff carries
  the CRC R313 exemption note instead of silence.

Sizes trace to ``llmbim_core.mep_sizing`` (Hunter's curve / Hazen-Williams
water, NEC Ch.9 conduit fill) — engineering estimates, not stamped designs.
"""

from __future__ import annotations

import pytest
from llmbim_core import material_lists as ml
from llmbim_core import mep_sizing as sz
from llmbim_ifc.export import export_ifc

import projects.schad.build_llmbim as build  # noqa: F401  (adds projects/schad to sys.path)


@pytest.fixture(scope="module")
def project():
    return build.build_model()


@pytest.fixture(scope="module")
def ifc_text(project, tmp_path_factory):
    out = tmp_path_factory.mktemp("schad_ifc") / "schad_mep.ifc"
    export_ifc(project.model, out)
    return out.read_text(encoding="utf-8")


def test_mep_takeoffs_nonempty(project):
    m = project.model
    assert len(ml.pipe_takeoff(m)) > 0, "flagship routes no pipe"
    assert len(ml.duct_takeoff(m)) > 0, "flagship routes no duct"
    assert len(ml.conduit_takeoff(m)) > 0, "flagship routes no conduit"
    assert len(ml.fitting_takeoff(m)) > 0, "flagship routes no fittings"


def test_mep_element_counts(project):
    # >= the pre-A* counts (30 pipe / 3 duct / 7 conduit); autorouting only
    # ever adds segments (elbowed bends split runs). Never lower these.
    st = project.stats()
    assert st.get("pipe", 0) >= 30, st
    assert st.get("duct", 0) >= 3, st
    assert st.get("conduit", 0) >= 7, st
    assert st.get("fixture", 0) >= 11, st  # real flow terminals (not notes)


def test_no_diagonal_plan_runs(project):
    # Residual #6: every pipe/duct/conduit plan segment is axis-aligned —
    # start and end differ in only ONE of x/y (vertical risers have zero plan
    # extent and pass trivially).
    diagonals = []
    for el in project.model.elements:
        if el.category not in {"pipe", "plumbing_pipe", "duct", "conduit"}:
            continue
        s, e = el.params.get("start_mm"), el.params.get("end_mm")
        if not s or not e:
            continue
        dx = abs(float(e[0]) - float(s[0]))
        dy = abs(float(e[1]) - float(s[1]))
        if dx >= 1.0 and dy >= 1.0:
            diagonals.append((el.id, el.name, round(dx), round(dy)))
    assert not diagonals, f"diagonal MEP runs placed: {diagonals}"


def test_routed_graph_and_connections(project):
    # mep_autoroute records every run as a mep_graph edge mirrored into
    # meta['connections'] — this is what fills materials/connections.json.
    m = project.model
    edges = [e for e in m.meta.get("mep_graph") or [] if isinstance(e, dict)]
    assert len(edges) >= 30, len(edges)
    assert all(e.get("kind") == "mep_autoroute" for e in edges)
    kinds = {e.get("route_kind") for e in edges}
    assert {"pipe", "duct", "conduit"} <= kinds
    assert len(ml.connection_schedule(m)) >= 30


def test_ifc_carries_concrete_mep_and_systems(ifc_text):
    text = ifc_text
    # concrete IFC4 distribution segments (not the abstract IfcFlowSegment)
    assert "IFCPIPESEGMENT(" in text, "no IfcPipeSegment in IFC"
    assert "IFCDUCTSEGMENT(" in text, "no IfcDuctSegment in IFC"
    assert "IFCCABLECARRIERSEGMENT(" in text, "no IfcCableCarrierSegment in IFC"
    # trade grouping for downstream clash/quantity
    assert "IFCSYSTEM(" in text, "no IfcSystem grouping in IFC"
    assert "IFCRELSERVICESBUILDINGS(" in text


def test_ifc_terminals_and_ports(ifc_text):
    # Residual #6: fixtures are real IfcFlowTerminal entities and the routed
    # graph is stitched with distribution ports (2 per mated pair, each
    # attached to its host element).
    assert ifc_text.count("IFCFLOWTERMINAL(") >= 11
    n_ports = ifc_text.count("IFCDISTRIBUTIONPORT(")
    n_mates = ifc_text.count("IFCRELCONNECTSPORTS(")
    n_attach = ifc_text.count("IFCRELCONNECTSPORTTOELEMENT(")
    assert n_ports > 0 and n_mates > 0
    assert n_ports == n_attach, (n_ports, n_attach)
    assert n_ports == 2 * n_mates, (n_ports, n_mates)


def test_calc_matches_routed_takeoff(project):
    # Residual #7: ONE sizing source — the DCW main NPS printed in the calc
    # text is the same NPS route_mep placed and the takeoff quantifies.
    import schad_mep as mep

    nps = str(mep._dcw_main_sizing()["nps"])
    calc = "\n".join(mep.plumbing_calc())
    assert f'{nps}" copper service/main' in calc, calc
    rows = ml.pipe_takeoff(project.model)
    assert any(
        r["nps"] == nps and "copper" in str(r["material_id"]).lower() for r in rows
    ), rows
    # feeder conduit trade sizes: calc text == routed trade sizes
    elec = "\n".join(mep.electrical_service_calc())
    for amps in (100.0, 50.0, 30.0):
        assert f'in {mep._feeder_trade(amps)}" EMT' in elec, elec
    routed_trades = {r["trade_size"] for r in ml.conduit_takeoff(project.model)}
    assert {mep._feeder_trade(100.0), mep._feeder_trade(50.0)} <= routed_trades


def test_fire_exemption_note(project):
    # Residual #8: no sprinklers routed — the basis records a CRC R313
    # exemption and the EMPTY fire takeoff carries that reason ("n/a per
    # basis"), not silence.
    ft = ml.fire_takeoff(project.model)
    assert ft["sprinkler_heads"] == [] and ft["pipe"] == []
    assert "R313" in str(ft.get("note")), ft.get("note")
    import schad_design_basis as basis

    assert ft["note"] == basis.build_notes()["fire_protection"][0]


def test_foundation_rebar_quantified(project):
    # WS1b: the specified footing rebar ((2) #4 CONT, Grade 60) is quantified as
    # CSI 03 20 00 — previously rebar_takeoff was []. Unspecified stem/pad/slab
    # reinforcement stays unquantified (not invented), so exactly the #4 line.
    m = project.model
    rt = ml.rebar_takeoff(m)
    assert len(rt) >= 1, "footing rebar not quantified"
    assert all(r["csi_code"] == "03 20 00" for r in rt)
    total_m = sum(float(r["qty"]) for r in rt if r["unit"] == "m")
    assert total_m > 100.0, total_m  # 2 x ~69.5 m continuous across 13 footings


def test_conduit_fill_matches_nec():
    # 100 A feeder -> #3 Cu (75C), #8 EGC, in 1" EMT at <=40% fill
    assert sz.conductor_for_amps(100.0) == "3"
    assert sz.egc_for_amps(100.0) == "8"
    f100 = sz.feeder_conduit(100.0)
    assert f100["trade_size"] == "1"
    assert f100["fill_pct"] <= 40.0
    # 240.4(D) small-conductor limit: 20 A -> #12 even though #14 ampacity is 20
    assert sz.conductor_for_amps(20.0) == "12"
    # 50 A EV feeder -> #8 in 3/4" EMT
    assert sz.feeder_conduit(50.0)["trade_size"] == "3/4"
