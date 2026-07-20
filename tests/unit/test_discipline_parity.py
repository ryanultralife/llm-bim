"""Discipline parity vs the 126-sheet reference register: EQ / N / C / H series.

Content-driven emitters added to the construction set:
  EQ-1xx per-room equipment arrangements (cropped, enlarged plans + table)
  N-1xx  shielding & confinement plan (walls color-coded by type + legend)
  C-1xx  site / underground plan (underground equipment + ghost shell + slabs)
  H-1xx  HVAC supply / exhaust plans split out of M
"""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.construction import export_construction_set
from llmbim_drawings.deliverables import verify_pack


def _parity_facility(name: str) -> Project:
    """Two equipment rooms + shield walls + underground vault + HVS/HVE ducts."""
    p = Project.create(name, vcs=False)
    p.add_level("L1", 0)
    shell = p.create_rect_shell(
        level="L1", x=0, y=0, w=16000, d=10000, height_mm=3500, thickness_mm=300,
        name_prefix="B",
    )
    p.set_type(shell[0], "W-SHIELD-CONC")
    p.set_type(shell[1], "W-SHIELD-CONC")
    p.set_type(shell[2], "W-EXT-CMU")
    p.create_room(
        level="L1", name="Hot Cell",
        boundary=[(0, 0), (8000, 0), (8000, 10000), (0, 10000)],
    )
    p.create_room(
        level="L1", name="Service",
        boundary=[(8000, 0), (16000, 0), (16000, 10000), (8000, 10000)],
    )
    p.create_equipment_box(
        level="L1", origin=(2000, 2000), size=(1500, 1000, 2000),
        name="CellPress", kind="press",
    )
    p.create_equipment_box(
        level="L1", origin=(10000, 2000), size=(1200, 900, 1800),
        name="ServiceSkid", kind="skid",
    )
    # far outside both rooms — must be cropped off every EQ sheet
    p.create_equipment_box(
        level="L1", origin=(30000, 20000), size=(500, 500, 500),
        name="YardTank", kind="tank",
    )
    p.create_equipment_box(
        level="L1", origin=(3000, -5000), size=(2000, 1500, 1200),
        name="SumpVault", kind="underground",
    )
    p.create_slab(
        level="L1", polygon=[(0, 0), (16000, 0), (16000, 10000), (0, 10000)],
        thickness_mm=200,
    )
    p.place_duct(level="L1", start=(1000, 8000), end=(7000, 8000), system="HVS")
    p.place_duct(level="L1", start=(1000, 9000), end=(7000, 9000), system="HVE")
    p.place_conduit(level="L1", start=(1000, 7000), end=(9000, 7000))
    return p


def _nos(manifest: dict) -> set[str]:
    return {s["no"] for s in manifest["sheets"]}


def test_parity_model_emits_all_new_disciplines(tmp_path: Path) -> None:
    p = _parity_facility("Parity")
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02)
    nos = _nos(man)
    for sn in ("EQ-101", "EQ-102", "N-101", "C-101", "H-101", "H-102"):
        assert sn in nos, f"missing {sn} in {sorted(nos)}"
    for fname in (
        "EQ-101_equipment_arrangement.svg",
        "EQ-102_equipment_arrangement.svg",
        "N-101_shielding.svg",
        "C-101_site_underground.svg",
        "H-101_hvac.svg",
        "H-102_hvac.svg",
    ):
        assert (tmp_path / fname).is_file(), fname
    # only HVS/HVE mechanical exists → it all moved to H, so no M sheet
    assert not [n for n in nos if n.startswith("M-")]
    # sheet index rows carry the new discipline codes
    by_no = {s["no"]: s for s in man["sheets"]}
    assert by_no["EQ-101"]["discipline"] == "EQ"
    assert by_no["N-101"]["discipline"] == "N"
    assert by_no["C-101"]["discipline"] == "C"
    assert by_no["H-101"]["discipline"] == "H"
    # cover lists every new sheet
    cover = (tmp_path / "G-001_cover.svg").read_text(encoding="utf-8")
    for sn in ("EQ-101", "EQ-102", "N-101", "C-101", "H-101", "H-102"):
        assert sn in cover


def test_eq_sheets_room_crop_and_table(tmp_path: Path) -> None:
    p = _parity_facility("ParityEQ")
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02)
    titles = {s["no"]: s["title"] for s in man["sheets"]}
    assert "Hot Cell" in titles["EQ-101"]
    assert "Service" in titles["EQ-102"]
    eq1 = (tmp_path / "EQ-101_equipment_arrangement.svg").read_text(encoding="utf-8")
    eq2 = (tmp_path / "EQ-102_equipment_arrangement.svg").read_text(encoding="utf-8")
    # room's own equipment drawn + tabulated (name appears in plan tag and table)
    assert "CellPress" in eq1
    assert "ServiceSkid" in eq2
    # crop: elements wholly outside the room window never render
    assert "YardTank" not in eq1
    assert "YardTank" not in eq2
    assert "ServiceSkid" not in eq1  # neighbor room's equipment outside the crop
    # walls ghosted; equipment table cell present
    assert "walls-ghost" in eq1
    assert 'class="schedule-table"' in eq1
    assert "W×D×H mm" in eq1
    # partially-inside geometry is clipped at the crop window
    assert "clip-path" in eq1


def test_shielding_plan_fills_and_legend(tmp_path: Path) -> None:
    p = _parity_facility("ParityN")
    export_construction_set(p.model, tmp_path, plan_scale=0.02)
    svg = (tmp_path / "N-101_shielding.svg").read_text(encoding="utf-8")
    # color-coded wall fills: shield red-brown + CMU grey; unknown types hatch
    assert 'fill="#8d4a3b"' in svg
    assert 'fill="#9e9e9e"' in svg
    assert "llmbim-wall-hatch" in svg  # untyped 4th shell wall hatches
    # legend: type → color → count → total length (2 shield walls: 16 m + 10 m)
    assert "W-SHIELD-CONC" in svg
    assert "× 2" in svg
    assert "26.0 m" in svg
    assert "W-EXT-CMU" in svg
    assert "× 1" in svg
    # room tags kept on the shielding plan
    assert 'class="room-tags"' in svg
    assert "HOT CELL" in svg


def test_underground_plan_content(tmp_path: Path) -> None:
    p = _parity_facility("ParityC")
    export_construction_set(p.model, tmp_path, plan_scale=0.02)
    svg = (tmp_path / "C-101_site_underground.svg").read_text(encoding="utf-8")
    assert "SumpVault" in svg  # underground structure + legend name count
    assert "walls-ghost" in svg  # building outline for context
    assert 'class="slabs"' in svg  # slab outline
    # only underground equipment renders — in-building equipment filtered out
    assert "CellPress" not in svg
    assert "ServiceSkid" not in svg


def test_hvac_split_and_m_keeps_rest(tmp_path: Path) -> None:
    p = _parity_facility("ParityH")
    # extra non-HVS/HVE mechanical: stays on M while HVS/HVE move to H
    p.place_duct(level="L1", start=(1000, 4000), end=(7000, 4000), system="SA")
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02)
    nos = _nos(man)
    assert "H-101" in nos and "H-102" in nos
    assert "M-101" in nos
    h1 = (tmp_path / "H-101_hvac.svg").read_text(encoding="utf-8")
    h2 = (tmp_path / "H-102_hvac.svg").read_text(encoding="utf-8")
    assert "HVS duct runs" in h1
    assert "HVE duct runs" in h2
    # M legend counts only the non-H duct
    m1 = (tmp_path / "M-101_mechanical.svg").read_text(encoding="utf-8")
    assert "Duct runs" in m1
    assert "× 1" in m1


def test_hvac_untagged_fallback_all_on_h101(tmp_path: Path) -> None:
    p = Project.create("Fallback", vcs=False)
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=12000, d=9000, height_mm=3200, thickness_mm=200,
        name_prefix="B",
    )
    did = p.place_duct(level="L1", start=(1000, 5000), end=(8000, 5000))
    # authoring ops always tag a system; simulate legacy/imported untagged ducts
    duct = next(el for el in p.model.elements if el.id == did)
    duct.params.pop("system", None)
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02)
    nos = _nos(man)
    assert "H-101" in nos
    assert "H-102" not in nos
    # the untagged duct moved to H → nothing mechanical left for M
    assert not [n for n in nos if n.startswith("M-")]


def test_plain_sa_ducts_stay_on_m_without_h(tmp_path: Path) -> None:
    """Tagged non-HVS/HVE systems (SA) keep the legacy M sheet, no H series."""
    p = Project.create("PlainM", vcs=False)
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=12000, d=9000, height_mm=3200, thickness_mm=200,
        name_prefix="B",
    )
    p.place_duct(level="L1", start=(1000, 5000), end=(8000, 5000))  # system="SA"
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02)
    nos = _nos(man)
    assert "M-101" in nos
    assert not [n for n in nos if n.startswith("H-")]


def test_discipline_counter_separates_e_and_eq(tmp_path: Path) -> None:
    p = _parity_facility("ParityCount")
    out = tmp_path / "pack"
    export_construction_set(p.model, out / "construction", plan_scale=0.02)
    checks = verify_pack(out)
    disc = checks["sheet_count_by_discipline"]
    assert disc.get("EQ", 0) == 2  # two equipment rooms
    assert disc.get("E", 0) == 1  # the conduit raceway plan — not merged with EQ
    assert disc.get("N", 0) == 1
    assert disc.get("C", 0) == 1
    assert disc.get("H", 0) == 2


def test_plan_set_emits_no_new_disciplines(tmp_path: Path) -> None:
    p = _parity_facility("ParityPlan")
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02, set_type="plan")
    nos = _nos(man)
    assert not [n for n in nos if n.startswith(("EQ-", "N-", "C-", "H-"))]
    stray = [
        f.name for f in tmp_path.glob("*.svg")
        if f.name.startswith(("EQ-", "N-", "C-", "H-"))
    ]
    assert not stray, stray


def test_repack_construction_to_plan_drops_new_sheets(tmp_path: Path) -> None:
    """Stale-sheet cleanup covers the two-letter EQ prefix and N/C/H."""
    p = _parity_facility("ParityRepack")
    export_construction_set(p.model, tmp_path, plan_scale=0.02)
    assert (tmp_path / "EQ-101_equipment_arrangement.svg").is_file()
    export_construction_set(p.model, tmp_path, plan_scale=0.02, set_type="plan")
    stray = [
        f.name for f in tmp_path.glob("*.svg")
        if f.name.startswith(("EQ-", "N-", "C-", "H-"))
    ]
    assert not stray, stray
