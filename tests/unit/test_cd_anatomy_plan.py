"""WP-CD-ANATOMY slice A — plan-side annotation anatomy.

Covers the CD completeness standard's plan-rendering gap rows: multi-tier
dimension chains (tick terminators, EQ-spaces collapse, governs note),
fractional grid intermediates (dash-dot centerlines, skip-I lettering),
tag anatomy completion (room area under boxed number, wall-type diamonds,
equipment leader tags), the key plan block, and byte-stable defaults.
"""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.construction import export_construction_set
from llmbim_drawings.plan import DIM_GOVERNS_NOTE, render_plan_view

# 12 m x 9 m shell; interior wall at x=5400 sits 90% between grids 1 and 2
W_MM, D_MM, H_MM = 12000.0, 9000.0, 3000.0
OFF_GRID_X = 5400.0


def _project(*, off_grid_wall: bool = False) -> Project:
    p = Project.create("cd-anatomy", vcs=False)
    p.add_level("L1", 0)
    walls = p.create_rect_shell(
        level="L1", x=0, y=0, w=W_MM, d=D_MM,
        height_mm=H_MM, thickness_mm=200, name_prefix="B",
    )
    # window on the north wall (feeds the top feature chain's jamb stations)
    p.place_window(
        host=walls[2], offset_mm=3000, width_mm=1200, height_mm=1200,
        sill_mm=900, name="W1",
    )
    p.place_door(host=walls[0], offset_mm=2000, width_mm=900, height_mm=2100, name="D1")
    p.add_grid("U", [0, 6000, 12000])
    p.add_grid("V", [0, 4500, 9000])
    p.create_room(
        level="L1", name="Lab",
        boundary=[(0, 0), (W_MM, 0), (W_MM, D_MM), (0, D_MM)],
    )
    p.create_equipment_box(
        level="L1", origin=(2000, 2000), size=(1000, 800, 900), name="AHU-1"
    )
    if off_grid_wall:
        p.create_wall(
            level="L1", start=(OFF_GRID_X, 0), end=(OFF_GRID_X, D_MM),
            thickness_mm=150, height_mm=H_MM, name="B-Int",
        )
    return p


# ── 1. multi-tier dimension chains ──────────────────────────────────────────


def test_dim_tiers_three_chains_and_governs_note() -> None:
    body = render_plan_view(_project().model, "L1", scale=0.02, dim_tiers=True).body
    assert 'class="dim-tiers"' in body
    # all three tiers, on two sides (top + left) each
    assert body.count('class="dim-tier tier-overall"') == 2
    assert body.count('class="dim-tier tier-grid"') == 2
    assert body.count('class="dim-tier tier-feature"') == 2
    assert "WRITTEN DIMENSIONS GOVERN" in body
    assert "DO NOT SCALE" in body
    assert DIM_GOVERNS_NOTE in body
    # witness lines carry the small-gap offset off the object
    assert 'class="dim-witness"' in body


def test_dim_tiers_tick_terminators_not_arrows() -> None:
    body = render_plan_view(_project().model, "L1", scale=0.02, dim_tiers=True).body
    assert 'class="dim-tick"' in body  # 45-degree slash terminators
    assert "marker-end" not in body  # never arrowheads
    assert "arrowhead" not in body


def test_dim_tiers_eq_spaces_collapse() -> None:
    p = Project.create("eq-spaces", vcs=False)
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=12000, d=9000, height_mm=3000, thickness_mm=200
    )
    p.add_grid("U", [0, 3000, 6000, 9000, 12000])  # 4 equal bays
    p.add_grid("V", [0, 4500, 9000])  # only 2 equal bays: stays itemized
    body = render_plan_view(p.model, "L1", scale=0.02, dim_tiers=True).body
    assert ">4 EQ. SPACES</text>" in body
    # 2-segment run stays itemized (no collapse under 3 equal segments)
    assert "2 EQ. SPACES" not in body
    assert ">4.50 m</text>" in body


def test_dim_tiers_imperial_labels() -> None:
    p = Project.create("tiers-imp", vcs=False)
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=12192, d=9144, height_mm=3048, thickness_mm=150
    )
    body = render_plan_view(
        p.model, "L1", scale=0.02, units="imperial", dim_tiers=True
    ).body
    tiers = body.split('class="dim-tiers"')[1]
    assert "'-" in tiers  # feet-inches strings on the chains
    assert " m</text>" not in tiers


# ── 2. fractional grid intermediates ────────────────────────────────────────


def test_fractional_grid_bubble_label_and_position() -> None:
    p = _project(off_grid_wall=True)
    body = render_plan_view(p.model, "L1", scale=0.02, fractional_grids=True).body
    frac = body.split('class="grids-frac"')[1].split("  </g>")[0]
    # 90% between grids 1 and 2 → "1.9", bubbled on BOTH ends of the line
    assert frac.count(">1.9</text>") == 2
    # dash-dot centerline convention
    assert 'stroke-dasharray="12 4 3 4"' in frac
    # position: x=5400 mm → screen (5400 - min_x) * scale = (5400+600)*0.02
    assert 'cx="120"' in frac


def test_fractional_grids_off_by_default_and_on_grid_walls_ignored() -> None:
    p = _project(off_grid_wall=False)  # every wall sits on a main grid
    base = render_plan_view(p.model, "L1", scale=0.02).body
    assert 'class="grids-frac"' not in base
    on = render_plan_view(p.model, "L1", scale=0.02, fractional_grids=True).body
    assert 'class="grids-frac"' not in on  # nothing lands off-grid


def test_fractional_skip_letter_i_in_default_lettering() -> None:
    p = Project.create("skip-i", vcs=False)
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=12000, d=9000, height_mm=3000, thickness_mm=200
    )
    p.add_grid("V", [i * 1000.0 for i in range(10)])  # no labels: defaults
    body = render_plan_view(p.model, "L1", scale=0.02, fractional_grids=True).body
    assert ">J</text>" in body  # 9th lettered axis jumps H → J
    assert ">I</text>" not in body
    # without the option the legacy A..I lettering is unchanged
    legacy = render_plan_view(p.model, "L1", scale=0.02).body
    assert ">I</text>" in legacy


# ── 3. tag anatomy completion ───────────────────────────────────────────────


def test_room_tag_area_metric_and_imperial() -> None:
    p = _project()
    metric = render_plan_view(
        p.model, "L1", scale=0.02, room_tags=True, room_areas=True
    ).body
    assert 'class="room-number-box"' in metric  # boxed number
    assert ">001</text>" in metric  # sequential fallback number
    assert 'class="room-area"' in metric
    assert "108.0 m²" in metric  # 12 m x 9 m under the boxed number
    imperial = render_plan_view(
        p.model, "L1", scale=0.02, room_tags=True, room_areas=True, units="imperial"
    ).body
    assert "1163 SF" in imperial  # 108 m² = 1162.5 SF, rounded
    assert "m²" not in imperial


def test_wall_type_diamond_when_tags() -> None:
    p = _project()
    wall = next(el for el in p.model.elements if el.category == "wall")
    wall.type_id = "W-EXT-CMU"
    tagged = render_plan_view(p.model, "L1", scale=0.02, tags=True).body
    assert 'class="wall-type-tag"' in tagged  # diamond around the type code
    assert ">EXT-CMU</text>" in tagged
    plain = render_plan_view(p.model, "L1", scale=0.02).body
    assert 'class="wall-type-tag"' not in plain
    assert 'class="wall-type"' in plain  # legacy midspan text unchanged


def test_equipment_leader_tag_when_tags() -> None:
    p = _project()
    tagged = render_plan_view(p.model, "L1", scale=0.02, tags=True).body
    assert 'class="equipment-tags"' in tagged
    assert 'class="equipment-leader"' in tagged
    assert 'class="equipment-tag-underline"' in tagged  # underlined name
    assert ">AHU-1</text>" in tagged
    plain = render_plan_view(p.model, "L1", scale=0.02).body
    assert 'class="equipment-tags"' not in plain
    assert ">AHU-1</text>" in plain  # legacy centroid label unchanged


# ── 4. key plan ─────────────────────────────────────────────────────────────


def test_key_plan_block_and_shaded_crop() -> None:
    p = _project()
    body = render_plan_view(p.model, "L1", scale=0.02, key_plan=True).body
    assert 'class="key-plan"' in body
    assert ">KEY PLAN</text>" in body
    assert 'class="key-plan-crop"' not in body  # no crop set → no shade
    cropped = render_plan_view(
        p.model, "L1", scale=0.02, key_plan=True,
        crop_mm=(1000, 1000, 7000, 7000),
    ).body
    assert 'class="key-plan"' in cropped  # footprint survives the crop filter
    assert 'class="key-plan-crop"' in cropped  # crop zone shaded


# ── 5. defaults byte-stable + register passthrough ──────────────────────────


def test_defaults_byte_stable_when_options_unset() -> None:
    p = _project(off_grid_wall=True)
    base = render_plan_view(p.model, "L1", scale=0.02).to_svg()
    explicit = render_plan_view(
        p.model, "L1", scale=0.02,
        dim_tiers=False, fractional_grids=False, key_plan=False, room_areas=False,
    ).to_svg()
    assert base == explicit  # snapshot: option-less render is byte-identical
    for marker in (
        'class="dim-tiers"', 'class="grids-frac"', 'class="key-plan"',
        'class="room-area"', 'class="equipment-tags"', 'class="wall-type-tag"',
        "EQ. SPACES", "WRITTEN DIMENSIONS GOVERN",
    ):
        assert marker not in base
    # room_tags path unchanged too when room_areas stays unset
    rt = render_plan_view(p.model, "L1", scale=0.02, room_tags=True).to_svg()
    rt_explicit = render_plan_view(
        p.model, "L1", scale=0.02, room_tags=True, room_areas=False
    ).to_svg()
    assert rt == rt_explicit
    assert 'class="room-number-box"' not in rt


def test_custom_register_opt_passthrough(tmp_path: Path) -> None:
    p = _project(off_grid_wall=True)
    register = [
        {
            "no": "A1.1", "title": "ANNOTATED PLAN", "kind": "plan", "level": "L1",
            "tags": True, "dim_tiers": True, "fractional_grids": True,
            "key_plan": True, "room_areas": True,
        },
        {"no": "A1.2", "title": "BARE PLAN", "kind": "plan", "level": "L1"},
    ]
    export_construction_set(p.model, tmp_path, plan_scale=0.02, sheets=register)
    annotated = (tmp_path / "A1-1_plan.svg").read_text(encoding="utf-8")
    assert 'class="dim-tiers"' in annotated
    assert 'class="grids-frac"' in annotated
    assert 'class="key-plan"' in annotated
    assert 'class="room-area"' in annotated
    assert 'class="equipment-tags"' in annotated
    # sibling entry without opts stays on the (unset) export-level defaults
    bare = (tmp_path / "A1-2_plan.svg").read_text(encoding="utf-8")
    for marker in ('class="dim-tiers"', 'class="grids-frac"', 'class="key-plan"',
                   'class="room-area"', 'class="equipment-tags"'):
        assert marker not in bare


def test_default_register_kwargs_passthrough(tmp_path: Path) -> None:
    p = _project(off_grid_wall=True)
    export_construction_set(
        p.model, tmp_path, plan_scale=0.02, set_type="plan",
        dim_tiers=True, fractional_grids=True, key_plan=True, room_areas=True,
    )
    plan = (tmp_path / "A-101_plan.svg").read_text(encoding="utf-8")
    assert 'class="dim-tiers"' in plan
    assert 'class="grids-frac"' in plan
    assert 'class="key-plan"' in plan
    assert 'class="room-number-box"' in plan
    assert "WRITTEN DIMENSIONS GOVERN" in plan
