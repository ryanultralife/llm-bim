"""Drawing-set differentiation: plan (permit) set vs full construction set."""

from __future__ import annotations

import json
from pathlib import Path

from llmbim import Project
from llmbim_drawings.construction import export_construction_set

PERMIT_SHEETS = {
    "G-001",
    "A-101",
    "A-201",
    "A-202",
    "A-203",
    "A-204",
    "A-301",
    "A-601",
    "A-602",
    "A-603",
}


def _facility(name: str) -> Project:
    p = Project.create(name, vcs=False)
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=12000, d=9000, height_mm=3200, thickness_mm=200, name_prefix="B"
    )
    p.create_room(
        level="L1", name="Hall", boundary=[(0, 0), (12000, 0), (12000, 9000), (0, 9000)]
    )
    return p


def _multi_trade(name: str) -> Project:
    """Facility with structure + piping + HVAC + raceway content."""
    p = _facility(name)
    p.place_column(level="L1", origin=(3000, 3000))
    p.place_pipe(level="L1", nps="3/4", start=(1000, 1000), end=(6000, 1000))
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(6000, 1000))
    p.place_duct(level="L1", start=(1000, 5000), end=(8000, 5000))
    p.place_conduit(level="L1", start=(1000, 7000), end=(9000, 7000))
    p.place_cable_tray(level="L1", start=(1000, 8000), end=(9000, 8000))
    return p


def _nos(manifest: dict) -> set[str]:
    return {s["no"] for s in manifest["sheets"]}


def test_plan_set_exact_permit_sheets(tmp_path: Path) -> None:
    """set_type='plan' emits exactly the permit sheets — no S/M/P/E sheets even
    when the model carries structural + MEP content."""
    p = _multi_trade("PlanOnly")
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02, set_type="plan")
    assert man["set_type"] == "plan"
    assert _nos(man) == PERMIT_SHEETS
    disc_files = [f.name for f in tmp_path.glob("*.svg") if f.name[0] in "SMPE"]
    assert not disc_files, disc_files
    # every sheet entry carries a discipline
    assert all(s.get("discipline") in {"G", "A"} for s in man["sheets"])
    idx = json.loads((tmp_path / "SHEET_INDEX.json").read_text(encoding="utf-8"))
    assert idx["set_type"] == "plan"


def test_construction_set_emits_discipline_sheets(tmp_path: Path) -> None:
    p = _multi_trade("FullCon")
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02)
    assert man["set_type"] == "construction"
    nos = _nos(man)
    assert PERMIT_SHEETS <= nos
    for sn in ("S-101", "M-101", "P-101", "P-601", "E-101", "A-401", "A-501"):
        assert sn in nos, f"missing {sn} in {sorted(nos)}"
    for fname in (
        "S-101_structural.svg",
        "M-101_mechanical.svg",
        "P-101_piping.svg",
        "P-601_takeoff.svg",
        "E-101_raceway.svg",
        "A-401_wall_types.svg",
        "A-501_equipment.svg",
    ):
        assert (tmp_path / fname).is_file(), fname
    # discipline sheets ghost the walls: light grey outline, no solid wall fill
    s_txt = (tmp_path / "S-101_structural.svg").read_text(encoding="utf-8")
    assert "walls-ghost" in s_txt
    assert 'fill="#c8c8c8"' not in s_txt
    # piping plan draws the pipe run; the structural plan does not
    p_txt = (tmp_path / "P-101_piping.svg").read_text(encoding="utf-8")
    assert 'stroke="#c45c26"' in p_txt
    assert 'stroke="#c45c26"' not in s_txt
    # raceway plan carries the conduit/cable-tray strokes
    e_txt = (tmp_path / "E-101_raceway.svg").read_text(encoding="utf-8")
    assert 'stroke="#6a1b9a"' in e_txt


def test_no_structure_no_s_sheets(tmp_path: Path) -> None:
    """Content-driven: a model without columns/beams emits no S sheet (and no
    P/E sheets without piping/raceway content)."""
    p = _facility("NoStruct")
    p.place_duct(level="L1", start=(1000, 5000), end=(8000, 5000))
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02)
    nos = _nos(man)
    assert not [n for n in nos if n.startswith("S-")]
    assert "M-101" in nos
    assert not [n for n in nos if n.startswith(("P-", "E-"))]
    assert not (tmp_path / "S-101_structural.svg").exists()


def test_multi_level_floor_plans(tmp_path: Path) -> None:
    p = Project.create("TwoStorey", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 3200)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=10000, d=8000, height_mm=3200, thickness_mm=200, name_prefix="A"
    )
    p.create_rect_shell(
        level="L2", x=0, y=0, w=10000, d=8000, height_mm=3200, thickness_mm=200, name_prefix="B"
    )
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02, set_type="plan")
    nos = _nos(man)
    assert "A-101" in nos and "A-102" in nos
    assert (tmp_path / "A-101_plan.svg").is_file()
    assert (tmp_path / "A-102_plan.svg").is_file()
    assert man["levels"] == ["L1", "L2"]
    titles = {s["no"]: s["title"] for s in man["sheets"]}
    assert "L1" in titles["A-101"] and "L2" in titles["A-102"]


def test_set_type_lands_in_pack_manifest(tmp_path: Path) -> None:
    p = _facility("PackPlan")
    man = p.export_deliverables(tmp_path / "pack", plan_scale=0.05, set_type="plan")
    assert man["set_type"] == "plan"
    data = json.loads((tmp_path / "pack" / "MANIFEST.json").read_text(encoding="utf-8"))
    assert data["set_type"] == "plan"
    idx = json.loads(
        (tmp_path / "pack" / "construction" / "SHEET_INDEX.json").read_text(encoding="utf-8")
    )
    assert idx["set_type"] == "plan"
    disc = man["verification"]["sheet_count_by_discipline"]
    assert set(disc) == {"G", "A"}


def test_verify_pack_discipline_counts(tmp_path: Path) -> None:
    p = _multi_trade("PackCon")
    man = p.export_deliverables(tmp_path / "pack", plan_scale=0.05)
    assert man["set_type"] == "construction"
    disc = man["verification"]["sheet_count_by_discipline"]
    assert disc.get("S", 0) >= 1
    assert disc.get("M", 0) >= 1
    assert disc.get("P", 0) >= 2  # P-101 + P-601 takeoff
    assert disc.get("E", 0) >= 1


def test_cli_pack_set_plan(tmp_path: Path) -> None:
    from llmbim_cli.main import main

    p = _facility("CliPlan")
    model = tmp_path / "model.llmbim.json"
    p.save(model)
    out = tmp_path / "out"
    rc = main(["pack", str(model), "--out", str(out), "--set", "plan"])
    assert rc == 0
    data = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    assert data["set_type"] == "plan"
    cons = out / "construction"
    assert (cons / "A-101_plan.svg").is_file()
    stray = [f.name for f in cons.glob("*.svg") if f.name[0] in "SMPE"]
    assert not stray, stray
