"""Machine / skid GA set — Sierra Star anatomy on wall-less equipment packs."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.construction import export_construction_set
from llmbim_drawings.deliverables import export_deliverables
from llmbim_drawings.plan import DIM_GOVERNS_NOTE, render_plan_view


def _skid(name: str = "AMD Skid") -> Project:
    p = Project.create(name, vcs=False)
    p.add_level("Skid", 0)
    # ISO 20-ft envelope, process train along +X
    p.create_equipment_box(
        level="Skid",
        origin=(-2400, 0),
        size=(600, 500, 800),
        name="feed pump",
        kind="equipment",
        centered=True,
        equipment="M-FEED-PUMP",
        part="housing",
    )
    p.create_equipment_box(
        level="Skid",
        origin=(-1600, 0),
        size=(480, 400, 450),
        name="EC cell",
        kind="equipment",
        centered=True,
        equipment="M-EC",
        part="body",
    )
    p.create_equipment_box(
        level="Skid",
        origin=(0, 0),
        size=(2500, 516, 516),
        name="chamber",
        kind="shell",
        centered=True,
        shape="cylinder",
        equipment="M-CHAMBER",
        part="shell",
    )
    p.create_equipment_box(
        level="Skid",
        origin=(1800, -200),
        size=(400, 400, 900),
        name="filter bank",
        kind="equipment",
        centered=True,
        equipment="M-FILTER",
        part="housing",
    )
    p.create_equipment_box(
        level="Skid",
        origin=(2400, 400),
        size=(700, 500, 1400),
        name="power MCC",
        kind="equipment",
        centered=True,
        equipment="M-POWER",
        part="enclosure",
    )
    # skid frame — swallows the envelope; must render as outline only
    p.create_equipment_box(
        level="Skid",
        origin=(0, 0),
        size=(6058, 2438, 300),
        name="skid deck",
        kind="equipment",
        centered=True,
        equipment="M-SKID",
        part="deck",
    )
    p.place_pipe(
        level="Skid",
        nps="3",
        start=(-2100, 0),
        end=(-1840, 0),
        name="P-001",
    )
    p.model.meta["process_notes"] = [
        "Process: EC → magnetite seed → magnetic floc recovery → polish.",
        "Connected load ~4–6 kW [EE]. Liquid MHD is not process SSOT.",
    ]
    return p


def test_auto_grid_and_dim_tiers_without_walls() -> None:
    body = render_plan_view(
        _skid().model,
        "Skid",
        scale=0.03,
        auto_grid=True,
        dim_tiers=True,
        tags=True,
        grid_dims=True,
        collapse_equipment=True,
        include={"equipment", "pipes", "grids", "notes"},
    ).body
    assert 'class="grids"' in body
    assert 'class="dim-tiers"' in body
    assert 'class="dim-tier tier-overall"' in body
    assert DIM_GOVERNS_NOTE in body
    assert 'class="equipment-tags"' in body
    assert "M-CHAMBER" in body
    assert "M-FEED-PUMP" in body
    assert 'class="equip-envelope"' in body  # skid deck outline
    assert 'class="equip-machine"' in body
    assert "WRITTEN DIMENSIONS GOVERN" in body


def test_defaults_stay_off_for_building_plans() -> None:
    """auto_grid / collapse / dim_tiers default off — existing A-plans unchanged."""
    p = Project.create("house", vcs=False)
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=8000, d=6000, height_mm=3000, thickness_mm=200
    )
    body = render_plan_view(p.model, "L1", scale=0.02).body
    assert 'class="dim-tiers"' not in body
    assert "equip-machine" not in body


def test_construction_set_auto_picks_machine_register(tmp_path: Path) -> None:
    p = _skid()
    man = export_construction_set(p.model, tmp_path, plan_level="Skid", plan_scale=0.03)
    nos = {s["no"] for s in man["sheets"]}
    assert nos == {"G-001", "EQ-101", "EQ-201", "EQ-301", "EQ-501"}
    ga = tmp_path / "EQ-101_plan.svg"
    assert ga.is_file()
    txt = ga.read_text(encoding="utf-8")
    assert "GENERAL ARRANGEMENT" in txt or "EQ-101" in txt
    assert "dim-tiers" in txt
    assert "M-CHAMBER" in txt
    assert "WRITTEN DIMENSIONS GOVERN" in txt
    # cover carries ECO-style process notes from model.meta
    cover = (tmp_path / "G-001_cover.svg").read_text(encoding="utf-8")
    assert "magnetite" in cover.lower() or "4–6" in cover or "4-6" in cover


def test_deliverables_part_mode_emits_machine_set(tmp_path: Path) -> None:
    p = _skid("Part Pack")
    man = export_deliverables(
        p.model, tmp_path / "pack", mode="part", plan_level="Skid", plan_scale=0.03
    )
    outs = man.get("outputs") or {}
    assert outs.get("machine_set") is True
    assert outs.get("construction")
    root = tmp_path / "pack"
    assert (root / "construction" / "EQ-101_plan.svg").is_file()
    assert (root / "construction" / "EQ-201_elevations.svg").is_file()
    assert (root / "construction" / "EQ-501_custom.svg").is_file() or (
        root / "construction" / "EQ-501_schedule.svg"
    ).is_file()
    plan = (root / "views" / "plan_Skid.svg").read_text(encoding="utf-8")
    assert "dim-tiers" in plan
    assert "M-EC" in plan or "M-CHAMBER" in plan


def test_facility_pack_still_emits_a101(tmp_path: Path) -> None:
    p = Project.create("Facility", vcs=False)
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=10000, d=8000, height_mm=3000, thickness_mm=200
    )
    p.create_equipment_box(
        level="L1", origin=(2000, 2000), size=(1000, 800, 900), name="AHU-1"
    )
    man = export_construction_set(p.model, tmp_path, plan_scale=0.02)
    nos = {s["no"] for s in man["sheets"]}
    assert "A-101" in nos
    assert "EQ-101" not in nos
