"""WS1 (excellence audit 2026-07-21) drift pins — the Schad flagship routes
REAL MEP, not note markers.

Guards against regression to the #1 audit gap ("FULL MEP = zero routed MEP"):
the build must place sized pipe/duct/conduit so the material takeoffs are
non-empty and the IFC coordination model carries concrete IFC4 distribution
segments grouped into systems. Sizes trace to ``llmbim_core.mep_sizing``
(Hunter's curve / Hazen-Williams water, NEC Ch.9 conduit fill) — engineering
estimates, not stamped designs.
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


def test_mep_takeoffs_nonempty(project):
    m = project.model
    assert len(ml.pipe_takeoff(m)) > 0, "flagship routes no pipe"
    assert len(ml.duct_takeoff(m)) > 0, "flagship routes no duct"
    assert len(ml.conduit_takeoff(m)) > 0, "flagship routes no conduit"
    assert len(ml.fitting_takeoff(m)) > 0, "flagship routes no fittings"


def test_mep_element_counts(project):
    st = project.stats()
    assert st.get("pipe", 0) >= 20, st
    assert st.get("duct", 0) >= 1, st
    assert st.get("conduit", 0) >= 4, st


def test_ifc_carries_concrete_mep_and_systems(project, tmp_path):
    out = tmp_path / "schad_mep.ifc"
    export_ifc(project.model, out)
    text = out.read_text(encoding="utf-8")
    # concrete IFC4 distribution segments (not the abstract IfcFlowSegment)
    assert "IFCPIPESEGMENT(" in text, "no IfcPipeSegment in IFC"
    assert "IFCDUCTSEGMENT(" in text, "no IfcDuctSegment in IFC"
    assert "IFCCABLECARRIERSEGMENT(" in text, "no IfcCableCarrierSegment in IFC"
    # trade grouping for downstream clash/quantity
    assert "IFCSYSTEM(" in text, "no IfcSystem grouping in IFC"
    assert "IFCRELSERVICESBUILDINGS(" in text


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
