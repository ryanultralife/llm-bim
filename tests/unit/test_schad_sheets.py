"""WP-SCHAD-S6 acceptance — full Schad sheet content.

Covers: foundations integrated into the build (F1/F2 footings, S1/S2 stems,
dual slabs — counts and sections from the basis / structural record), roofs
(main gable ridge 18', Bay-2 cross-gable valleys, rear shed), MEP/ADU basis
content, and the Gate C custom sheet register (numbers/titles verbatim from
``basis.sheet_register()``) with details D01–D12, structural schedules and
the honesty stamp. Every dimension asserted here is read from the basis
modules — never retyped.

Deliberately independent of the WP-SCHAD-S7 annotation options (imperial
dim strings / tag bubbles): assertions cover sheet files, register order and
schedule/doc content only, so this suite passes before and after S7 lands.
"""

from __future__ import annotations

import json
import re

import pytest

import projects.schad.build_llmbim  # noqa: F401  (adds projects/schad to sys.path)
import projects.schad.schad_design_basis as basis
import projects.schad.schad_structural as struct
from examples.schad_build import build_schad_model
from projects.schad.build_llmbim import build_pack, schad_sheet_register

FT_TO_MM = 304.8
IN_TO_MM = 25.4
MM2_PER_SF = FT_TO_MM * FT_TO_MM

# Gate C register — [RB A0.1] permit-set index order, plus the S4.1
# structural-schedules judgment sheet after A4.1.
EXPECTED_SHEET_NOS = [
    "A0.1", "C1.1", "A1.1", "A1.2", "A2.1", "A2.2", "A3.1",
    "S1.1", "S2.1", "S3.1", "S3.2", "S3.3", "A4.1", "S4.1",
    "MEP-101", "MEP-201", "MEP-301", "H1.1", "H1.2", "H2.1", "H2.2",
]
EXPECTED_SHEET_FILES = {
    "A0-1_cover.svg", "C1-1_custom.svg", "A1-1_plan.svg", "A1-2_custom.svg",
    "A2-1_elevations.svg", "A2-2_elevations.svg", "A3-1_sections.svg",
    "S1-1_custom.svg", "S2-1_custom.svg",
    "S3-1_details.svg", "S3-2_details.svg", "S3-3_details.svg",
    "A4-1_schedule.svg", "S4-1_custom.svg",
    "MEP-101_custom.svg", "MEP-201_custom.svg", "MEP-301_custom.svg",
    "H1-1_doc.svg", "H1-2_doc.svg", "H2-1_doc.svg", "H2-2_custom.svg",
}


@pytest.fixture(scope="module")
def project():
    return build_schad_model()


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("schad_s6") / "pack"
    proj, verify = build_pack(out)
    return proj, out, verify


def _by_category(project, category):
    return [el for el in project.model.elements if el.category == category]


# --- 1. foundations in the build ---------------------------------------------


def test_strip_footings_under_bearing_walls(project):
    s = basis.build_scalars()
    bearing = [
        w for w in basis.build_walls()
        if str(w["kind"]).startswith("exterior") or "fire" in str(w["kind"])
    ]
    strips = [
        el for el in _by_category(project, "footing") if el.params["kind"] == "strip"
    ]
    assert len(strips) == len(bearing) == 13
    rebar_note = next(
        n for n in basis.build_notes()["foundation"] if n.startswith("REBAR:")
    )
    for el in strips:
        assert el.params["mark"] == "F1"
        assert el.params["width_mm"] == pytest.approx(s["footing_w"] * FT_TO_MM)  # 18"
        assert el.params["depth_mm"] == pytest.approx(s["footing_d"] * FT_TO_MM)  # 12"
        assert el.params["rebar"] == rebar_note  # carried verbatim
        assert el.params["under_wall_id"]  # placed under_wall=, not a retyped path
        # top of footing below datum by the (flagged) stem height
        assert el.params["top_of_footing_mm"] < 0
        assert el.params.get("stem_height_assumed") is True


def test_pad_footings_match_structural_record(project):
    # 36"x36"x30" [BOM] — parsed from the structural record docstring
    m = re.search(r'(\d+)"x(\d+)"x(\d+)"', struct.point_footing_check.__doc__ or "")
    assert m, "pad record missing from schad_structural.point_footing_check"
    w_in, d_in, depth_in = (float(g) for g in m.groups())
    pads = [el for el in _by_category(project, "footing") if el.params["kind"] == "pad"]
    beams = basis.build_structure()["beams"]
    assert len(pads) == 2 * len(beams) == 4  # under each HSS post
    expected_centers = {
        (round(b["x"] * FT_TO_MM, 1), round(y * FT_TO_MM, 1))
        for b in beams
        for y in (b["y1"], b["y2"])
    }
    got_centers = {
        (round(el.params["center_mm"][0], 1), round(el.params["center_mm"][1], 1))
        for el in pads
    }
    assert got_centers == expected_centers
    for el in pads:
        assert el.params["mark"] == "F2"
        assert el.params["w_mm"] == pytest.approx(w_in * IN_TO_MM)
        assert el.params["d_mm"] == pytest.approx(d_in * IN_TO_MM)
        assert el.params["depth_mm"] == pytest.approx(depth_in * IN_TO_MM)


def test_stem_walls_front_8in_typical_6in(project):
    s = basis.build_scalars()
    stems = _by_category(project, "stem_wall")
    exterior = [w for w in basis.build_walls() if str(w["kind"]).startswith("exterior")]
    assert len(stems) == len(exterior) == 12
    s1 = [el for el in stems if el.params["mark"] == "S1"]
    s2 = [el for el in stems if el.params["mark"] == "S2"]
    # garage front = the 5 footprint segments on the y<=0 OH-door line
    assert len(s1) == 5 and len(s2) == 7
    for el in s1:
        assert el.params["thickness_mm"] == pytest.approx(s["stem_front"] * FT_TO_MM)
    for el in s2:
        assert el.params["thickness_mm"] == pytest.approx(s["stem_typ"] * FT_TO_MM)
    ab_note = next(
        n for n in basis.build_notes()["foundation"] if n.startswith("ANCHOR BOLTS:")
    )
    for el in stems:
        assert el.params.get("height_assumed") is True  # frost depth not in record
        assert el.params.get("anchor_bolts") == ab_note


def test_dual_slabs_on_grade_thickness_and_area(project):
    s = basis.build_scalars()
    slabs = [
        el
        for el in _by_category(project, "slab")
        if el.params.get("kind") == "slab_on_grade"
    ]
    by_mark = {el.params["mark"]: el for el in slabs}
    assert set(by_mark) == {"SOG-4", "SOG-3"}
    g, a = by_mark["SOG-4"], by_mark["SOG-3"]
    assert g.params["thickness_mm"] == pytest.approx(s["slab_garage_t"] * FT_TO_MM)  # 4"
    assert a.params["thickness_mm"] == pytest.approx(s["slab_adu_t"] * FT_TO_MM)  # 3"
    # ADU slab = the ADU panel; garage/workshop slab = footprint minus ADU
    adu_sf = s["adu_L"] * s["rear_W"]
    assert a.params["area_mm2"] / MM2_PER_SF == pytest.approx(adu_sf, rel=0.01)
    total_sf = s["area_total"]  # footprint area published [RB A0.1]
    assert g.params["area_mm2"] / MM2_PER_SF == pytest.approx(total_sf - adu_sf, rel=0.01)


def test_rebar_schedule_aggregates_marks(project):
    rows = {(r["mark"], r["type"]): r for r in project.rebar_schedule()}
    assert rows[("F1", "strip_footing")]["qty"] == 13
    assert rows[("F2", "pad_footing")]["qty"] == 4
    assert rows[("S1", "stem_wall")]["qty"] == 5
    assert rows[("S2", "stem_wall")]["qty"] == 7
    assert rows[("SOG-4", "slab_on_grade")]["qty"] == 1
    assert rows[("SOG-3", "slab_on_grade")]["qty"] == 1
    # the strip rebar spec is the carried basis callout
    assert "(2) #4" in rows[("F1", "strip_footing")]["rebar"]


# --- 2. roofs per basis -------------------------------------------------------


def test_roofs_placed_ridge_18ft(project):
    s = basis.build_scalars()
    roofs = {el.name: el for el in _by_category(project, "roof")}
    assert set(roofs) == {"Roof-Main-Gable", "Roof-Bay2-CrossGable", "Roof-Rear-Shed"}
    ridge_mm = s["ridge"] * FT_TO_MM  # 18' = 5486.4
    main = roofs["Roof-Main-Gable"]
    assert main.params["kind"] == "gable"
    assert main.params["ridge_z_mm"] == pytest.approx(ridge_mm)
    assert main.params["pitch"] == pytest.approx(s["roof_pitch"])  # 6:12
    assert main.params["overhang_mm"] == pytest.approx(s["overhang"] * FT_TO_MM)  # 18"
    # Bay-2 cross-gable peaks at the SAME 18' ridge (Q-BAY2ROOF) and cuts
    # valleys against the main roof
    bay2 = roofs["Roof-Bay2-CrossGable"]
    assert bay2.params["ridge_z_mm"] == pytest.approx(ridge_mm)
    assert bay2.params["valley_lines_mm"], "Bay-2 gable must intersect the main roof"
    assert "Q-BAY2ROOF" in str(bay2.params.get("status"))
    # rear shed: 12' bearing at the main wall to the 10' north eave → 1.5:12
    shed = roofs["Roof-Rear-Shed"]
    assert shed.params["kind"] == "shed"
    run_mm = s["rear_W"] * FT_TO_MM
    expected_slope = (s["plate_rear_high"] - s["plate_rear_low"]) * FT_TO_MM / run_mm
    assert shed.params["slope"] == pytest.approx(expected_slope)
    assert "Q-SHED" in str(shed.params.get("status"))


# --- 3. Gate C register -------------------------------------------------------


def test_register_titles_verbatim_from_basis():
    reg = schad_sheet_register(build_schad_model())
    assert [e["no"] for e in reg] == EXPECTED_SHEET_NOS
    titles = {row["number"]: row["title"] for row in basis.sheet_register()}
    for e in reg:
        if e["no"] == "S4.1":
            continue  # judgment sheet — not in the [RB A0.1] index
        assert e["title"] == titles[e["no"]]
    # S7 annotation contract keys are present on every entry (inert until S7)
    assert all(e.get("units") == "imperial" for e in reg)
    plan = next(e for e in reg if e["kind"] == "plan")
    assert plan.get("tags") is True


def test_pack_emits_full_gate_c_sheet_files(pack):
    _proj, out, _verify = pack
    cons = out / "construction"
    assert {f.name for f in cons.glob("*.svg")} == EXPECTED_SHEET_FILES
    idx = json.loads((cons / "SHEET_INDEX.json").read_text(encoding="utf-8"))
    assert idx["register"] == "custom"
    assert [sh["no"] for sh in idx["sheets"]] == EXPECTED_SHEET_NOS


def test_details_sheets_carry_d01_to_d12(pack):
    _proj, out, _verify = pack
    cons = out / "construction"
    groups = {
        "S3-1_details.svg": {"D01", "D02", "D03", "D04"},
        "S3-2_details.svg": {"D05", "D06", "D07", "D08"},
        "S3-3_details.svg": {"D09", "D10", "D11", "D12"},
    }
    for fname, ids in groups.items():
        svg = (cons / fname).read_text(encoding="utf-8")
        found = set(re.findall(r"D\d\d", svg))
        assert found == ids, f"{fname}: {found}"


def test_structural_schedule_sheet_has_ssw_and_rebar_rows(pack):
    _proj, out, _verify = pack
    svg = (out / "construction" / "S4-1_custom.svg").read_text(encoding="utf-8")
    for model_name in ("SSW24x9", "SSW24x12"):
        assert model_name in svg
    # rebar schedule rows: strip mark + the carried basis callout
    assert "F1" in svg and "(2) #4" in svg


def test_doc_sheet_carries_honesty_stamp(pack):
    _proj, out, _verify = pack
    svg = (out / "construction" / "H2-1_doc.svg").read_text(encoding="utf-8")
    assert "NOT FOR CONSTRUCTION" in svg
    # cover carries the stamp too
    cover = (out / "construction" / "A0-1_cover.svg").read_text(encoding="utf-8")
    assert "NOT FOR CONSTRUCTION" in cover


def test_pack_verify_ok_with_calc_docs_and_history(pack):
    proj, out, verify = pack
    assert verify.get("ok"), verify
    assert (out / "index.html").is_file()
    assert (out / "PLOT_SET.pdf").is_file()
    for doc in ("STRUCTURAL_CALCS.md", "MEP_CALCS.md", "SPECIFICATIONS.md"):
        assert (out / "docs" / doc).stat().st_size > 200
    # model VCS shows the staged build history and a clean tree
    log = proj.log()
    assert len(log) >= 5
    messages = " | ".join(c.get("message", "") for c in log)
    for token in ("S3 foundations", "S2 roofs", "S6 MEP/ADU"):
        assert token in messages
    assert proj.status().get("clean") is True
