"""Parts catalog, material lists, plumbing takeoff."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_core.material_lists import (
    export_lists,
    fitting_takeoff,
)
from llmbim_core.parts_catalog import (
    PARTS,
    get_part,
    list_parts,
    resolve_fitting_part_id,
)


def test_plumbing_catalog_has_copper_90():
    assert resolve_fitting_part_id("elbow_90", "1/2", material="copper") == "PT-CU-ELB90-1_2"
    assert resolve_fitting_part_id("elbow_90", "3/4", material="copper") == "PT-CU-ELB90-3_4"
    assert resolve_fitting_part_id("pipe", "1", material="copper") == "PT-CU-PIPE-1"
    p = get_part("PT-CU-ELB90-1_2")
    assert p is not None
    assert p.specs["fitting_type"] == "elbow_90"
    assert p.specs["nps"] == "1/2"
    assert "copper" in p.primary_material_id or p.primary_material_id == "copper_fitting"
    elbows = list_parts(category="plumbing", fitting_type="elbow_90")
    assert len(elbows) >= 8  # multiple NPS


def test_place_and_count_copper_90():
    p = Project.create("takeoff-test", vcs=False)
    p.add_level("L1", 0)
    # 3× 1/2" 90°, 2× 3/4" 90°, 1× 1" tee
    for i in range(3):
        p.place_fitting(level="L1", fitting_type="elbow_90", nps="1/2", origin=(i * 100, 0))
    for i in range(2):
        p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(i * 100, 200))
    p.place_fitting(level="L1", fitting_type="tee", nps="1", origin=(0, 400))
    p.place_pipe(level="L1", nps="3/4", start=(0, 0), end=(3000, 0))  # 3 m

    rows = p.fitting_takeoff(fitting_type="elbow_90", material="copper")
    by_nps = {r["nps"]: r["qty"] for r in rows}
    assert by_nps.get("1/2") == 3
    assert by_nps.get("3/4") == 2

    all_f = p.fitting_takeoff()
    assert sum(r["qty"] for r in all_f) == 6  # 3+2+1

    pipes = p.pipe_takeoff(material="copper")
    assert len(pipes) == 1
    assert abs(pipes[0]["length_m"] - 3.0) < 0.01
    assert pipes[0]["nps"] == "3/4"

    sched = p.plumbing_schedule()
    assert sched["totals"]["fitting_pieces"] == 6
    assert abs(sched["totals"]["pipe_length_m"] - 3.0) < 0.01
    copper_90 = sched["copper_90_elbows_by_size"]
    assert {r["nps"]: r["qty"] for r in copper_90} == {"1/2": 3, "3/4": 2}


def test_assign_part_and_material_lists(tmp_path: Path):
    p = Project.create("mat-test", vcs=False)
    p.add_level("L1", 0)
    eid = p.create_equipment_box(
        level="L1",
        origin=(0, 0),
        size=(500, 320, 320),
        name="Shell",
        kind="shell",
        shape="cylinder",
        centered=True,
    )
    p.assign_part(eid, "PT-SEP-SHELL-320")
    p.assign_material(eid, "aluminum_6061")
    lists = p.material_lists()
    assert any(r["part_id"] == "PT-SEP-SHELL-320" for r in lists["part_assignments"])
    written = export_lists(p.model, tmp_path / "materials")
    assert "fitting_takeoff" in written
    assert (tmp_path / "materials" / "MATERIALS_AND_PARTS.json").is_file()


def test_auto_assign_proto_kinds():
    p = Project.create("auto", vcs=False)
    p.add_level("Bench", 0)
    eid = p.create_equipment_box(
        level="Bench",
        origin=(0, 0),
        size=(500, 320, 320),
        kind="shell",
        shape="cylinder",
        centered=True,
    )
    r = p.auto_assign()
    assert r["assigned"] >= 1
    el = p.model.get_element(eid)
    assert el.params.get("part_id") == "PT-SEP-SHELL-320"


def test_registry_ops():
    p = Project.create("ops", vcs=False)
    p.add_level("L1", 0)
    r = p.op("place_fitting", level="L1", fitting_type="elbow_90", nps="1/2", origin=[0, 0])
    assert "element_id" in r
    t = p.op("fitting_takeoff", fitting_type="elbow_90")
    assert t["count_rows"] >= 1
    cat = p.op("parts", category="plumbing", fitting_type="elbow_90")
    assert cat["count"] >= 8


def test_deliverables_include_materials(tmp_path: Path):
    p = Project.create("pack-mat", vcs=False)
    p.add_level("L1", 0)
    p.place_fitting(level="L1", fitting_type="elbow_90", nps="1/2", origin=(0, 0))
    p.place_pipe(level="L1", nps="1/2", start=(0, 0), end=(2000, 0))
    p.create_wall(level="L1", start=(0, 0), end=(4000, 0), thickness_mm=200, height_mm=3000)
    man = p.export_deliverables(tmp_path / "pack", mode="facility")
    assert (tmp_path / "pack" / "materials" / "fitting_takeoff.json").is_file()
    assert (tmp_path / "pack" / "schedules" / "plumbing_takeoff.json").is_file()
    data = fitting_takeoff(p.model)
    assert data[0]["qty"] == 1


def test_explode_bom_scales_mass_and_volume_by_qty():
    """mass_kg / volume_m3 must scale with instance_qty just like qty / est_cost.
    Regression: they previously stayed at the per-unit value, undercounting
    procurement mass on every multi-count / multi-meter part."""
    from llmbim_core.parts_catalog import explode_part_bom

    part = next(
        p
        for p in PARTS.values()
        if any(r.get("mass_kg") for r in explode_part_bom(p, 1.0))
    )
    one = explode_part_bom(part, 1.0)
    ten = explode_part_bom(part, 10.0)
    for r1, r10 in zip(one, ten):
        if r1["mass_kg"] is not None:
            assert r10["mass_kg"] == round(r1["mass_kg"] * 10, 3)
        if r1["volume_m3"] is not None:
            assert r10["volume_m3"] == round(r1["volume_m3"] * 10, 6)
        assert r10["qty"] == r1["qty"] * 10
        assert r10["est_cost"] == round(r1["est_cost"] * 10, 2)


def test_steel_takeoff_tonnage_and_no_double_count():
    """steel_takeoff must emit weight_kg_m + mass_kg per section row (catalog
    weight, else lb/ft from the W-designation) and must not count a placed
    column twice (catalog rollup + bucket pass)."""
    from llmbim_core.material_lists import steel_takeoff

    p = Project.create("SteelTonnage", vcs=False)
    p.add_level("L1", 0)
    p.op("place_column", level="L1", section="W10x33", origin=[0, 0], height_mm=4000)
    p.op("place_beam", level="L1", section="W16x40", start=[0, 0], end=[6000, 0], z0_mm=4000)
    rows = steel_takeoff(p.model)
    by_section = {}
    for r in rows:
        assert r["section"] not in by_section, f"duplicate row for {r['section']}"
        by_section[r["section"]] = r
    assert by_section["W10x33"]["qty"] == 4.0
    assert by_section["W10x33"]["mass_kg"] == 196.4  # 4 m x 49.1 kg/m (catalog)
    assert by_section["W16x40"]["mass_kg"] == 357.2  # 6 m x 40 lb/ft x 1.48816
