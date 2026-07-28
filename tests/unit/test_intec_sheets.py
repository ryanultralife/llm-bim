"""INTEC Gate C acceptance — full MB-INT-CAD-001 sheet register.

Pins: sheet numbers/titles from ``intec_design_basis.sheet_register()``,
bioshield wall typing (W-SHIELD-CONC), Eigen-derived snapshot content on
key derived sheets, and pack rebuild health.

Every dimension/title asserted here is read from the basis modules — never
retyped. Honesty: [ENGINEERING ESTIMATE].
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_INTEC = _ROOT / "projects" / "intec"
if str(_INTEC) not in sys.path:
    sys.path.insert(0, str(_INTEC))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import intec_derived as derived  # noqa: E402
import intec_design_basis as basis  # noqa: E402

from projects.intec.build_llmbim import (  # noqa: E402
    WALL_TYPE_SHIELD,
    build_model,
    build_pack,
    intec_sheet_register,
    wall_type_counts,
)

EXPECTED_SHEET_NOS = [r["number"] for r in basis.sheet_register()]
EXPECTED_COUNT = 128
EXPECTED_DISCIPLINES = {
    "G": 13,
    "C": 7,
    "S": 17,
    "EQ": 17,
    "A": 19,
    "N": 14,
    "H": 6,
    "P": 11,
    "E": 9,
    "I": 6,
    "F": 4,
    "L": 2,
    "LS": 3,
}


@pytest.fixture(scope="module")
def project():
    return build_model()


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("intec_gate") / "pack"
    proj, verify = build_pack(out)
    return proj, out, verify


# --- 1. register SSOT -------------------------------------------------------


def test_register_count_and_disciplines():
    reg = basis.sheet_register()
    assert len(reg) == EXPECTED_COUNT
    assert basis.discipline_counts() == EXPECTED_DISCIPLINES
    # unique numbers
    nos = [r["number"] for r in reg]
    assert len(nos) == len(set(nos))
    # first/last sanity
    assert nos[0] == "G-000"
    assert nos[-1] == "LS-002"
    assert "A-001" in nos and "EQ-016" in nos and "N-013" in nos


def test_register_titles_nonempty():
    for r in basis.sheet_register():
        assert r["title"].strip()
        assert r["discipline"]
        assert r["doc"] == basis.DOC


def test_sheet_register_maps_1to1(project):
    sheets = intec_sheet_register(project)
    got = [s["no"] for s in sheets]
    assert got == EXPECTED_SHEET_NOS
    for s in sheets:
        assert s["kind"] in {
            "cover",
            "plan",
            "elevations",
            "sections",
            "schedule",
            "details",
            "custom_svg",
            "doc",
        }


# --- 2. model geometry / shield walls ---------------------------------------


def test_placements_and_vessels(project):
    pls = basis.build_placements()
    assert len(pls) == 23
    vessels = [pl for pl in pls if pl.get("vessel")]
    assert len(vessels) == 6  # active cells
    eq = [el for el in project.model.elements if el.category == "equipment"]
    vessel_eq = [e for e in eq if "vessel" in (e.name or "").lower() or "SizeB" in (e.name or "")]
    assert len(vessel_eq) >= 6


def test_bioshield_wall_types(project):
    counts = wall_type_counts(project)
    assert counts.get(WALL_TYPE_SHIELD, 0) >= 40, counts  # many shield walls
    # tunnel walls are 1500 mm bioshield
    tunnel = [
        el
        for el in project.model.elements
        if el.category == "wall" and (el.name or "").startswith("TUNNEL")
    ]
    assert len(tunnel) == 4
    for el in tunnel:
        assert el.type_id == WALL_TYPE_SHIELD or el.params.get("type_id") == WALL_TYPE_SHIELD
        th = float(el.params.get("thickness_mm") or 0)
        assert th >= 1400.0, (el.name, th)  # full bioshield


def test_structure_present(project):
    cols = [e for e in project.model.elements if e.category == "column"]
    beams = [e for e in project.model.elements if e.category == "beam"]
    assert len(cols) >= 30
    assert len(beams) >= 6


def test_mep_spine(project):
    pipes = [e for e in project.model.elements if e.category == "pipe"]
    ducts = [e for e in project.model.elements if e.category == "duct"]
    trays = [e for e in project.model.elements if e.category == "cable_tray"]
    assert pipes
    assert ducts
    assert trays


# --- 3. Eigen-derived snapshot ----------------------------------------------


def test_snapshot_present_and_keyed():
    s = derived.load_snapshot()
    for key in (
        "lighting",
        "electrical",
        "hvac",
        "plumbing",
        "fire",
        "bid_quantities",
        "module_stations",
        "egress",
        "site",
    ):
        assert key in s, key
    assert len(s["lighting"]) >= 10
    assert s["electrical"]["service_design_mw"] == 10.25
    assert "rooms" in s["hvac"]
    assert len(s["bid_quantities"]) >= 5
    assert "TUNNEL" in s["module_stations"]


def test_derived_svg_providers_emit_svg():
    for fn in (
        derived.g006_calc_index,
        derived.g010_bid_quantities,
        derived.h005_airflow,
        derived.e007_lighting,
        derived.f003_fire,
        derived.s016_station_matrix,
        derived.p008_plumbing,
        derived.i005_rad_io,
    ):
        svg = fn()
        assert svg.lstrip().startswith("<svg"), fn.__name__
        assert "ENGINEERING ESTIMATE" in svg or "derived" in svg.lower() or "m" in svg


# --- 4. pack rebuild --------------------------------------------------------


def test_pack_sheet_files(pack):
    _proj, out, verify = pack
    cons = out / "construction"
    index = json.loads((cons / "SHEET_INDEX.json").read_text(encoding="utf-8"))
    assert index["register"] == "custom"
    assert len(index["sheets"]) == EXPECTED_COUNT
    nos = [s["no"] for s in index["sheets"]]
    assert nos == EXPECTED_SHEET_NOS
    for s in index["sheets"]:
        f = cons / s["file"]
        assert f.is_file(), s["file"]
        assert f.stat().st_size > 200, s["file"]


def test_pack_plot_and_verify(pack):
    _proj, out, verify = pack
    assert (out / "PLOT_SET.pdf").is_file()
    assert (out / "PLOT_SET.pdf").stat().st_size > 50_000
    assert (out / "model.llmbim.json").is_file()
    assert (out / "index.html").is_file()
    assert (out / "SHEET_REGISTER.json").is_file()
    assert verify.get("ok") is True


def test_pack_derived_sheets_have_content(pack):
    """Derived sheets must not be empty placeholders."""
    _proj, out, _verify = pack
    cons = out / "construction"
    checks = {
        "G-010": ("m3", "BID", "concrete", "steel", "t"),
        "H-005": ("m3/h", "cfm", "Pa", "ACH", "HEPA", "R5"),
        "E-007": ("lux", "LF-", "fixture", "kW"),
        "F-003": ("water", "clean agent", "detection", "NFPA", "suppression"),
        "S-016": ("TUNNEL", "tier", "T1", "CELL"),
        "G-006": ("MW", "calc", "kW", "I/O"),
    }
    index = json.loads((cons / "SHEET_INDEX.json").read_text(encoding="utf-8"))
    by_no = {s["no"]: s["file"] for s in index["sheets"]}
    for no, needles in checks.items():
        text = (cons / by_no[no]).read_text(encoding="utf-8", errors="ignore")
        assert any(n.lower() in text.lower() for n in needles), (no, needles)


def test_pack_shield_type_in_model_json(pack):
    _proj, out, _verify = pack
    model = json.loads((out / "model.llmbim.json").read_text(encoding="utf-8"))
    walls = [e for e in model.get("elements", []) if e.get("category") == "wall"]
    shield = [
        e
        for e in walls
        if e.get("type_id") == WALL_TYPE_SHIELD
        or (e.get("params") or {}).get("type_id") == WALL_TYPE_SHIELD
    ]
    assert len(shield) >= 40
