"""INTEC — design basis → llm-bim Project + full CD sheet register.

Mirrors the Schad Gate C pattern: model is SSOT; drawings are a custom
``sheets=[]`` register from ``intec_design_basis.sheet_register()``.

Honesty: [ENGINEERING ESTIMATE] — design-basis class; PE seal reserved.

Run (repo root):
  python projects/intec/build_construction_set.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import intec_design_basis as basis
import intec_derived as derived
import svg_diagrams as diagrams
from llmbim import Project

HONESTY = basis.HONESTY
M = 1000.0  # m → mm

# Wall types (llmbim_core.types_catalog) — N-series plan poché keys these
WALL_TYPE_EXT = "W-EXT-CMU"
WALL_TYPE_INT = "W-INT-GYP"
WALL_TYPE_SHIELD = "W-SHIELD-CONC"

# Stations that get full bioshield thickness (1.5 m) + W-SHIELD-CONC
SHIELD_KINDS = frozenset({"tunnel", "ebeam", "cell", "uncask"})
# Other shielded process boxes: thinner CIP shield partition still typed shield
SHIELD_BOX_KINDS = frozenset({"box"})


def m_to_mm(v: float) -> float:
    return float(v) * M


def _mm(v: float) -> float:
    """Alias used in crop tuples (metres → mm)."""
    return m_to_mm(v)


def _typed_rect_shell(
    p: Project,
    *,
    level: str,
    x: float,
    y: float,
    w: float,
    d: float,
    height_mm: float,
    thickness_mm: float,
    name_prefix: str,
    type_id: str,
    fire_rating: str | None = None,
) -> list[str]:
    """Four walls with explicit type_id (create_rect_shell has no type_id)."""
    corners = [
        ((x, y), (x + w, y), f"{name_prefix}-S"),
        ((x + w, y), (x + w, y + d), f"{name_prefix}-E"),
        ((x + w, y + d), (x, y + d), f"{name_prefix}-N"),
        ((x, y + d), (x, y), f"{name_prefix}-W"),
    ]
    ids: list[str] = []
    for start, end, nm in corners:
        eid = p.create_wall(
            level=level,
            start=start,
            end=end,
            thickness_mm=thickness_mm,
            height_mm=height_mm,
            name=nm,
            type_id=type_id,
            fire_rating=fire_rating,
        )
        # set_type syncs thickness from the wall-type catalog; re-assert the
        # design thickness so bioshield (1500 mm) and partition shields stay true.
        try:
            p.op("set_param", id=eid, key="thickness_mm", value=float(thickness_mm))
        except Exception:
            pass
        ids.append(eid)
    return ids


def wall_type_counts(p: Project) -> dict[str, int]:
    out: dict[str, int] = {}
    for el in p.query(category="wall"):
        tid = el.type_id or el.params.get("type_id") or "(none)"
        out[str(tid)] = out.get(str(tid), 0) + 1
    return out


# --------------------------------------------------------------------------- #
# model build                                                                  #
# --------------------------------------------------------------------------- #
def build_model(*, on_stage: Any | None = None) -> Project:
    """Build the full INTEC facility coordination model."""
    s = basis.build_scalars()
    placements = basis.build_placements()

    p = Project.create(basis.PROJECT_NAME, vcs=False)
    p.add_level("L0", 0)
    p.add_level("L1-Roof", m_to_mm(s["bldg_H"]))
    p.add_level("L2-Stack", m_to_mm(s["bldg_H"] + s["stack_H_above_roof"]))

    # Structural grid (~8 m E-W, ~7 m N-S)
    u = [m_to_mm(x) for x in range(0, int(s["bldg_L"]) + 1, 8)]
    if u[-1] != m_to_mm(s["bldg_L"]):
        u.append(m_to_mm(s["bldg_L"]))
    v = [m_to_mm(y) for y in (-s["annex_D"], 0, 7, 14, 21, 28, s["bldg_W"])]
    p.add_grid("U", u, name="Grid-U")
    p.add_grid("V", v, name="Grid-V")

    # Slabs
    main_poly = [
        (0.0, 0.0),
        (m_to_mm(s["bldg_L"]), 0.0),
        (m_to_mm(s["bldg_L"]), m_to_mm(s["bldg_W"])),
        (0.0, m_to_mm(s["bldg_W"])),
    ]
    p.create_slab(
        level="L0", polygon=main_poly, thickness_mm=m_to_mm(s["slab_t"]), name="Slab-main"
    )
    ax0, ay0 = m_to_mm(s["annex_x0"]), m_to_mm(-s["annex_D"])
    annex_poly = [
        (ax0, ay0),
        (ax0 + m_to_mm(s["annex_L"]), ay0),
        (ax0 + m_to_mm(s["annex_L"]), ay0 + m_to_mm(s["annex_D"])),
        (ax0, ay0 + m_to_mm(s["annex_D"])),
    ]
    p.create_slab(
        level="L0",
        polygon=annex_poly,
        thickness_mm=m_to_mm(s["slab_t"]),
        name="Slab-annex",
    )

    # Exterior shells — industrial CMU envelope
    _typed_rect_shell(
        p,
        level="L0",
        x=0.0,
        y=0.0,
        w=m_to_mm(s["bldg_L"]),
        d=m_to_mm(s["bldg_W"]),
        height_mm=m_to_mm(s["bldg_H"]),
        thickness_mm=m_to_mm(s["wall_t"]),
        name_prefix="BLDG",
        type_id=WALL_TYPE_EXT,
        fire_rating="2-hr",
    )
    _typed_rect_shell(
        p,
        level="L0",
        x=ax0,
        y=ay0,
        w=m_to_mm(s["annex_L"]),
        d=m_to_mm(s["annex_D"]),
        height_mm=m_to_mm(s["annex_H"]),
        thickness_mm=m_to_mm(s["wall_t"]),
        name_prefix="ANNEX",
        type_id=WALL_TYPE_EXT,
        fire_rating="2-hr",
    )

    # Station shells + rooms + vessels
    # Bioshield: full 1.5 m W-SHIELD-CONC for tunnel/ebeam/cells/uncask;
    # other shielded process boxes use 600 mm shield-typed partitions;
    # occupied support uses W-INT-GYP.
    for pl in placements:
        if pl["id"] == "STACK":
            p.create_equipment_box(
                level="L0",
                origin=(m_to_mm(pl["x"]), m_to_mm(pl["y"])),
                size=(m_to_mm(pl["w"]), m_to_mm(pl["d"]), m_to_mm(pl["h"])),
                name=pl["name"],
                kind="stack",
                centered=False,
                z0_mm=0.0,
            )
            continue
        x, y = m_to_mm(pl["x"]), m_to_mm(pl["y"])
        w, d, h = m_to_mm(pl["w"]), m_to_mm(pl["d"]), m_to_mm(pl["h"])
        kind = pl.get("kind") or "box"
        if pl.get("shielded") and kind in SHIELD_KINDS:
            thick = m_to_mm(s["shield_t"])  # 1500 mm bioshield
            type_id = WALL_TYPE_SHIELD
            fire = "4-hr"
        elif pl.get("shielded") and kind in SHIELD_BOX_KINDS:
            thick = 600.0  # process shield partition [EST]
            type_id = WALL_TYPE_SHIELD
            fire = "4-hr"
        elif pl.get("occupied"):
            thick = 200.0
            type_id = WALL_TYPE_INT
            fire = "1-hr"
        else:
            thick = 200.0
            type_id = WALL_TYPE_EXT
            fire = "2-hr"
        wall_ids = _typed_rect_shell(
            p,
            level="L0",
            x=x,
            y=y,
            w=w,
            d=d,
            height_mm=h,
            thickness_mm=thick,
            name_prefix=pl["id"],
            type_id=type_id,
            fire_rating=fire,
        )
        if type_id == WALL_TYPE_SHIELD:
            for eid in wall_ids:
                try:
                    p.op(
                        "set_param",
                        id=eid,
                        key="shield_mm",
                        value=thick if kind in SHIELD_KINDS else 600.0,
                    )
                except Exception:
                    pass
        p.create_room(
            level="L0",
            name=pl["name"],
            boundary=[(x, y), (x + w, y), (x + w, y + d), (x, y + d)],
        )
        if pl.get("vessel"):
            cx, cy = x + w / 2, y + d / 2
            p.create_equipment_box(
                level="L0",
                origin=(cx, cy),
                size=(m_to_mm(s["vessel_LEN"]), m_to_mm(s["vessel_OD"]), m_to_mm(s["vessel_OD"])),
                name=f"{pl['id']}-SizeB-vessel",
                kind="separator_vessel_size_b",
                shape="cylinder",
                centered=True,
                z0_mm=m_to_mm(s["vessel_cl_z"]) - m_to_mm(s["vessel_OD"]) / 2,
            )

    # Columns on structural grid
    col_xs = [m_to_mm(x) for x in range(0, int(s["bldg_L"]) + 1, 8)]
    if col_xs[-1] != m_to_mm(s["bldg_L"]):
        col_xs.append(m_to_mm(s["bldg_L"]))
    col_ys = [m_to_mm(y) for y in (0, 7, 14, 21, 28, s["bldg_W"])]
    for i, cx in enumerate(col_xs):
        for j, cy in enumerate(col_ys):
            p.place_column(
                level="L0",
                origin=(cx, cy),
                section=s["col_section"],
                height_mm=m_to_mm(s["bldg_H"]),
                name=f"COL-{i}-{j}",
            )

    # Roof beams E-W on each N-S grid line
    for j, cy in enumerate(col_ys):
        p.place_beam(
            level="L0",
            start=(0.0, cy),
            end=(m_to_mm(s["bldg_L"]), cy),
            section=s["beam_section"],
            name=f"BM-EW-{j}",
            z0_mm=m_to_mm(s["bldg_H"]) - 400,
        )
    # Crane runways along tunnel long edges
    for k, yy in enumerate((2.5, 2.5 + 19.3)):
        p.place_beam(
            level="L0",
            start=(m_to_mm(5.5), m_to_mm(yy)),
            end=(m_to_mm(42.0), m_to_mm(yy)),
            section=s["crane_runway"],
            name=f"CRANE-RW-{k}",
            z0_mm=m_to_mm(s["crane_clear_H"]),
        )

    # Entry door
    south = [el for el in p.query(category="wall") if el.name == "BLDG-S"]
    if south:
        p.place_door(
            host=south[0].id,
            offset_mm=m_to_mm(20.0),
            width_mm=1800,
            height_mm=2400,
            name="Main personnel entry",
        )

    # CW copper process loop (takeoff demo)
    p.place_pipe(
        level="L0",
        nps="2",
        start=(m_to_mm(5.5), m_to_mm(22.0)),
        end=(m_to_mm(40.0), m_to_mm(22.0)),
        name="CW main 2\" spine",
        material="copper",
        system="CW",
        z0_mm=3000,
    )
    for nps, x in (("1", 13.0), ("1", 20.0), ("1", 27.0), ("3/4", 13.0), ("3/4", 20.0), ("3/4", 27.0)):
        p.place_pipe(
            level="L0",
            nps=nps,
            start=(m_to_mm(x), m_to_mm(22.0)),
            end=(m_to_mm(x), m_to_mm(16.5 if nps == "1" else 4.9)),
            name=f"CW branch {nps}\" x={x}",
            material="copper",
            system="CW",
            z0_mm=2500,
        )
    for nps, count, x0 in (("2", 2, 5.5), ("1", 6, 13.0), ("3/4", 6, 13.0)):
        for i in range(count):
            p.place_fitting(
                level="L0",
                fitting_type="elbow_90",
                nps=nps,
                origin=(m_to_mm(x0 + i * 1.2), m_to_mm(22.0)),
                name=f"Cu 90 {nps} #{i + 1}",
                material="copper",
                system="CW",
            )

    # Cable tray / raceway spine
    p.place_cable_tray(
        level="L0",
        start=(m_to_mm(5.5), m_to_mm(12.0)),
        end=(m_to_mm(42.0), m_to_mm(12.0)),
        width_mm=600,
        height_mm=150,
        name="Tray PWR main",
        system="PWR",
        z0_mm=4500,
    )
    p.place_cable_tray(
        level="L0",
        start=(m_to_mm(5.5), m_to_mm(13.0)),
        end=(m_to_mm(42.0), m_to_mm(13.0)),
        width_mm=300,
        height_mm=100,
        name="Tray IC main",
        system="IC",
        z0_mm=4500,
    )
    # HVAC duct main
    p.place_duct(
        level="L0",
        start=(m_to_mm(6.0), m_to_mm(21.0)),
        end=(m_to_mm(40.0), m_to_mm(21.0)),
        width_mm=1200,
        height_mm=600,
        name="HVE main exhaust",
        system="HVE",
        z0_mm=5000,
    )
    p.place_duct(
        level="L0",
        start=(m_to_mm(6.0), m_to_mm(3.5)),
        end=(m_to_mm(40.0), m_to_mm(3.5)),
        width_mm=800,
        height_mm=400,
        name="HVS main supply",
        system="HVS",
        z0_mm=5000,
    )

    # Notes
    for i, note in enumerate(basis.general_notes()[:5]):
        try:
            p.op("create_note", level="L0", text=note, origin=[m_to_mm(-5), m_to_mm(i * 2)])
        except Exception:
            pass

    p.auto_assign()
    if on_stage:
        on_stage(p, "INTEC shell structure MEP")
    return p


# --------------------------------------------------------------------------- #
# sheet register → llm-bim custom sheets                                       #
# --------------------------------------------------------------------------- #
def _doc_paras(no: str, title: str) -> list[str]:
    """Placeholder body for derived/doc sheets not yet fully modeled."""
    return [
        f"Sheet {no}: {title}",
        "",
        f"Document: {basis.DOC} · params {basis.PARAMS_VERSION} · engine {basis.ENGINE_SHA}",
        f"Site: {basis.SITE}",
        f"Owner: {basis.OWNER}",
        "",
        HONESTY,
        "",
        "This sheet is design-basis class. Quantities and arrangements are "
        "projected from the llm-bim model (stations, steel, CW, duct, trays) "
        "or transcribed from the MB-INT-CAD-001 register. Final production "
        "drawings and PE seal by the A-E firm at DS-2.",
        "",
        "See model schedules (doors, rooms, equipment, pipe takeoff) and "
        "materials/ CSI takeoff in the pack for derived quantities.",
    ]


def intec_sheet_register(p: Project) -> list[dict[str, Any]]:
    """Map every MB-INT-CAD-001 sheet to a llm-bim custom-register entry."""
    reg = {r["number"]: r for r in basis.sheet_register()}
    s = basis.build_scalars()
    plan_scale = 0.012  # ~1:80 px/mm for full facility
    hall_scale = 0.02
    full_crop = diagrams.full_crop_m()
    hall_crop = diagrams.hall_crop_m()
    annex_crop = diagrams.annex_crop_m()

    def e(no: str, kind: str, **opts: Any) -> dict[str, Any]:
        row = reg[no]
        return {
            "no": no,
            "title": row["title"],
            "kind": kind,
            "scale_note": row["scale"],
            "discipline": row["discipline"],
            "units": "metric",
            **opts,
        }

    def doc(no: str) -> dict[str, Any]:
        row = reg[no]
        return e(no, "doc", text="\n".join(_doc_paras(no, row["title"])))

    def cover_sec(no: str, disc: str, label: str) -> dict[str, Any]:
        return e(
            no,
            "custom_svg",
            view=diagrams.section_cover_svg(disc, label),
        )

    sheets: list[dict[str, Any]] = []

    # ── G ────────────────────────────────────────────────────────────────
    sheets.append(cover_sec("G-000", "G", "GENERAL"))
    sheets.append(
        e(
            "G-001",
            "cover",
            subtitle=f"{basis.OWNER} · {basis.DOC} · {basis.SITE}",
            notes=[
                HONESTY,
                f"{len(basis.sheet_register())} sheets · {len(basis.discipline_counts())} disciplines",
                f"params {basis.PARAMS_VERSION} · engine sha {basis.ENGINE_SHA}",
                "see G-002 for drawing index",
            ],
        )
    )
    sheets.append(e("G-002", "custom_svg", view=diagrams.index_table_svg()))
    sheets.append(e("G-003", "custom_svg", view=diagrams.notes_svg()))
    sheets.append(e("G-004", "custom_svg", view=diagrams.code_summary_svg()))
    sheets.append(e("G-005", "custom_svg", view=diagrams.zoning_svg()))
    sheets.append(e("G-006", "custom_svg", view=derived.g006_calc_index()))
    sheets.append(e("G-007", "custom_svg", view=derived.g007_equip_index()))
    sheets.append(doc("G-008"))  # fuel receipt — still placeholder (separate engine)
    sheets.append(e("G-009", "custom_svg", view=diagrams.sequence_svg()))
    sheets.append(e("G-010", "custom_svg", view=derived.g010_bid_quantities()))
    sheets.append(e("G-011", "custom_svg", view=derived.g011_scope()))
    sheets.append(e("G-012", "custom_svg", view=derived.g012_crosswalk()))

    # ── C ────────────────────────────────────────────────────────────────
    sheets.append(cover_sec("C-000", "C", "CIVIL / SITE"))
    sheets.append(e("C-001", "custom_svg", view=diagrams.site_plan_svg(mode="site")))
    sheets.append(e("C-002", "custom_svg", view=diagrams.site_plan_svg(mode="grading")))
    sheets.append(e("C-003", "custom_svg", view=diagrams.site_plan_svg(mode="utilities")))
    sheets.append(e("C-004", "custom_svg", view=diagrams.site_plan_svg(mode="ductbank")))
    sheets.append(e("C-005", "custom_svg", view=derived.c005_ops_site()))
    sheets.append(doc("C-006"))

    # ── S ────────────────────────────────────────────────────────────────
    sheets.append(cover_sec("S-000", "S", "STRUCTURAL"))
    sheets.append(e("S-001", "custom_svg", view=diagrams.foundation_svg(), stamp_block=True))
    sheets.append(e("S-002", "custom_svg", view=diagrams.framing_svg(roof=False), stamp_block=True))
    sheets.append(e("S-003", "custom_svg", view=diagrams.framing_svg(roof=True), stamp_block=True))
    sheets.append(
        e(
            "S-004",
            "elevations",
            pair=["S", "N"],
            stamp_block=True,
            line_weights=True,
            hatches=True,
        )
    )
    sheets.append(e("S-005", "sections", stamp_block=True, line_weights=True, hatches=True))
    sheets.append(doc("S-006"))
    sheets.append(e("S-007", "schedule", schedule=["equipment"], stamp_block=True))
    for no in ("S-008", "S-009", "S-010", "S-011", "S-012", "S-013", "S-014"):
        sheets.append(doc(no))
    sheets.append(e("S-015", "custom_svg", view=derived.s015_modules(), stamp_block=True))
    sheets.append(e("S-016", "custom_svg", view=derived.s016_station_matrix(), stamp_block=True))

    # ── EQ ───────────────────────────────────────────────────────────────
    sheets.append(cover_sec("EQ-000", "EQ", "STATION EQUIPMENT"))
    # Per-station enlarged plans where crop is meaningful; else doc
    station_crops = {
        "TUNNEL": (_mm(5.0), _mm(2.0), _mm(42.5), _mm(22.5)),
        "SPINE": (_mm(5.0), _mm(9.5), _mm(42.5), _mm(15.0)),
        "EBEAM": (_mm(5.0), _mm(3.5), _mm(13.0), _mm(21.0)),
        "UNCASK": (_mm(0.5), _mm(-10.5), _mm(9.5), _mm(0.5)),
        "DECLAD": (_mm(9.5), _mm(-10.5), _mm(18.5), _mm(0.5)),
        "CELL": hall_crop,
        "DOWNBLEND": (_mm(0.5), _mm(25.5), _mm(14.5), _mm(34.5)),
        "ROBMAINT": (_mm(15.5), _mm(25.5), _mm(28.5), _mm(34.5)),
        "WASTE": (_mm(29.5), _mm(25.5), _mm(43.5), _mm(34.5)),
        "CASKBAY": (_mm(19.5), _mm(-10.5), _mm(29.5), _mm(0.5)),
        "CASKING": (_mm(30.5), _mm(-10.5), _mm(45.5), _mm(0.5)),
        "STACK": (_mm(16.0), _mm(30.0), _mm(22.0), _mm(36.0)),
        "CONTROL": (_mm(43.5), _mm(2.0), _mm(48.5), _mm(12.5)),
        "DECON": (_mm(43.5), _mm(12.5), _mm(48.5), _mm(19.5)),
        "HP": (_mm(43.5), _mm(19.5), _mm(48.5), _mm(26.5)),
        "MCA": (_mm(43.5), _mm(26.5), _mm(48.5), _mm(34.5)),
    }
    for i, (st, _what) in enumerate(basis.eq_stations(), 1):
        no = f"EQ-{i:03d}"
        crop = station_crops.get(st)
        if crop:
            sheets.append(
                e(
                    no,
                    "plan",
                    level="L0",
                    crop=crop,
                    scale=0.025,
                    room_tags=True,
                    tags=True,
                    include=["wall", "equipment", "room", "column", "beam"],
                    key_plan=True,
                )
            )
        else:
            sheets.append(doc(no))

    # ── A ────────────────────────────────────────────────────────────────
    sheets.append(cover_sec("A-000", "A", "ARCHITECTURAL"))
    sheets.append(
        e(
            "A-001",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=full_crop,
            room_tags=True,
            tags=True,
            dimensions=True,
            dim_tiers=True,
            room_areas=True,
            key_plan=True,
            grid_sides="arch",
        )
    )
    sheets.append(
        e(
            "A-002",
            "plan",
            level="L0",
            scale=hall_scale,
            crop=hall_crop,
            room_tags=True,
            tags=True,
            dimensions=True,
            key_plan=True,
        )
    )
    sheets.append(
        e(
            "A-003",
            "plan",
            level="L0",
            scale=hall_scale,
            crop=annex_crop,
            room_tags=True,
            tags=True,
            dimensions=True,
        )
    )
    sheets.append(
        e(
            "A-004",
            "plan",
            level="L1-Roof",
            scale=plan_scale,
            crop=full_crop,
            room_tags=False,
            include=["wall", "equipment", "beam", "column"],
        )
    )
    sheets.append(e("A-005", "elevations", pair=["S", "N"], line_weights=True))
    sheets.append(e("A-006", "sections", line_weights=True, hatches=True))
    sheets.append(doc("A-007"))
    sheets.append(e("A-008", "schedule", schedule=["door"]))
    sheets.append(e("A-009", "schedule", schedule=["room"]))
    sheets.append(
        e(
            "A-010",
            "plan",
            level="L0",
            scale=hall_scale,
            crop=hall_crop,
            room_tags=True,
            tags=True,
            dimensions=True,
        )
    )
    sheets.append(e("A-011", "custom_svg", view=derived.a011_room_req()))
    sheets.append(e("A-012", "custom_svg", view=derived.a012_doors()))
    sheets.append(e("A-013", "custom_svg", view=derived.a013_door_leaves()))
    sheets.append(doc("A-014"))
    sheets.append(doc("A-015"))
    sheets.append(e("A-016", "sections", line_weights=True, hatches=True))
    sheets.append(e("A-017", "elevations", pair=["E", "W"], line_weights=True))
    sheets.append(e("A-018", "sections", line_weights=True, hatches=True))

    # ── N ────────────────────────────────────────────────────────────────
    sheets.append(cover_sec("N-000", "N", "NUCLEAR / SHIELDING"))
    sheets.append(e("N-001", "custom_svg", view=diagrams.zoning_svg()))
    sheets.append(
        e(
            "N-002",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=full_crop,
            room_tags=True,
            include=["wall", "equipment", "room"],
        )
    )
    sheets.append(
        e(
            "N-003",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=full_crop,
            room_tags=True,
            include=["wall", "duct", "room", "equipment"],
        )
    )
    sheets.append(doc("N-004"))
    sheets.append(e("N-005", "custom_svg", view=diagrams.material_flow_svg()))
    sheets.append(
        e(
            "N-006",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=hall_crop,
            include=["wall", "equipment", "beam", "room"],
        )
    )
    sheets.append(doc("N-007"))
    for no in ("N-008", "N-009", "N-010", "N-011", "N-012"):
        sheets.append(doc(no))
    sheets.append(e("N-013", "custom_svg", view=diagrams.material_flow_svg()))

    # ── H ────────────────────────────────────────────────────────────────
    sheets.append(cover_sec("H-000", "H", "HVAC / CONFINEMENT VENTILATION"))
    sheets.append(e("H-001", "custom_svg", view=diagrams.vent_cascade_svg()))
    sheets.append(
        e(
            "H-002",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=full_crop,
            include=["wall", "duct", "equipment", "room"],
            room_tags=True,
        )
    )
    sheets.append(doc("H-003"))
    sheets.append(e("H-004", "custom_svg", view=derived.h004_hvac_equip()))
    sheets.append(e("H-005", "custom_svg", view=derived.h005_airflow()))

    # ── P ────────────────────────────────────────────────────────────────
    sheets.append(cover_sec("P-000", "P", "PROCESS & PIPING"))
    sheets.append(e("P-001", "custom_svg", view=diagrams.pfd_svg()))
    sheets.append(doc("P-002"))
    sheets.append(
        e(
            "P-003",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=full_crop,
            include=["wall", "pipe", "fitting", "equipment", "room"],
            room_tags=True,
        )
    )
    sheets.append(
        e(
            "P-004",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=full_crop,
            include=["wall", "pipe", "room"],
        )
    )
    sheets.append(doc("P-005"))
    sheets.append(e("P-006", "schedule", schedule=["pipe"]))
    sheets.append(e("P-007", "custom_svg", view=diagrams.pfd_svg()))
    sheets.append(e("P-008", "custom_svg", view=derived.p008_plumbing()))
    sheets.append(e("P-009", "custom_svg", view=derived.p009_plumbing_conn()))
    sheets.append(doc("P-010"))

    # ── E ────────────────────────────────────────────────────────────────
    sheets.append(cover_sec("E-000", "E", "ELECTRICAL"))
    sheets.append(e("E-001", "custom_svg", view=diagrams.one_line_svg()))
    sheets.append(
        e(
            "E-002",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=full_crop,
            include=["wall", "cable_tray", "conduit", "equipment", "room"],
            room_tags=True,
        )
    )
    sheets.append(
        e(
            "E-003",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=full_crop,
            include=["wall", "room"],
            room_tags=True,
        )
    )
    sheets.append(doc("E-004"))
    sheets.append(
        e(
            "E-005",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=full_crop,
            include=["wall", "cable_tray", "conduit", "room"],
        )
    )
    sheets.append(e("E-006", "custom_svg", view=derived.e006_panels()))
    sheets.append(e("E-007", "custom_svg", view=derived.e007_lighting()))
    sheets.append(e("E-008", "custom_svg", view=diagrams.one_line_svg()))

    # ── I ────────────────────────────────────────────────────────────────
    sheets.append(cover_sec("I-000", "I", "INSTRUMENTATION & CONTROL"))
    sheets.append(doc("I-001"))
    sheets.append(doc("I-002"))
    sheets.append(
        e(
            "I-003",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=full_crop,
            room_tags=True,
            include=["wall", "equipment", "room"],
        )
    )
    sheets.append(doc("I-004"))
    sheets.append(e("I-005", "custom_svg", view=derived.i005_rad_io()))

    # ── F ────────────────────────────────────────────────────────────────
    sheets.append(cover_sec("F-000", "F", "FIRE PROTECTION"))
    sheets.append(
        e(
            "F-001",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=full_crop,
            room_tags=True,
            include=["wall", "room", "equipment"],
        )
    )
    sheets.append(doc("F-002"))
    sheets.append(e("F-003", "custom_svg", view=derived.f003_fire()))

    # ── L ────────────────────────────────────────────────────────────────
    sheets.append(cover_sec("L-000", "L", "LOGISTICS"))
    sheets.append(e("L-001", "custom_svg", view=derived.l001_logistics()))

    # ── LS ───────────────────────────────────────────────────────────────
    sheets.append(cover_sec("LS-000", "LS", "LIFE SAFETY"))
    sheets.append(e("LS-001", "custom_svg", view=derived.ls001_egress()))
    sheets.append(
        e(
            "LS-002",
            "plan",
            level="L0",
            scale=plan_scale,
            crop=full_crop,
            room_tags=True,
            tags=True,
            include=["wall", "door", "room"],
        )
    )

    # Sanity: every register number present exactly once
    expected = [r["number"] for r in basis.sheet_register()]
    got = [sh["no"] for sh in sheets]
    if got != expected:
        missing = set(expected) - set(got)
        extra = set(got) - set(expected)
        # order mismatch or missing — still return but flag
        if missing or extra or len(got) != len(expected):
            raise RuntimeError(
                f"sheet register mismatch: missing={sorted(missing)} "
                f"extra={sorted(extra)} count {len(got)} vs {len(expected)}"
            )
    return sheets


def _basis_snapshot() -> dict[str, Any]:
    return {
        "source": "projects/intec/intec_design_basis.py",
        "doc": basis.DOC,
        "params_version": basis.PARAMS_VERSION,
        "engine_sha": basis.ENGINE_SHA,
        "project": basis.PROJECT_NAME,
        "site": basis.SITE,
        "owner": basis.OWNER,
        "scalars_m": basis.build_scalars(),
        "placements": len(basis.build_placements()),
        "sheet_count": len(basis.sheet_register()),
        "disciplines": basis.discipline_counts(),
        "honesty": HONESTY,
        "open_questions": basis.open_questions(),
        "eigen_snapshot": derived.snapshot_meta(),
        "wall_types": {
            "ext": WALL_TYPE_EXT,
            "int": WALL_TYPE_INT,
            "shield": WALL_TYPE_SHIELD,
            "shield_t_m": basis.build_scalars()["shield_t"],
        },
    }


def build_pack(out_dir: Path | str | None = None) -> tuple[Project, dict[str, Any]]:
    """Full harness: model + custom 128-sheet CD register + PDF + verify."""
    out_dir = Path(out_dir or _ROOT / "output" / "intec_construction")
    out_dir.mkdir(parents=True, exist_ok=True)

    p = build_model()
    (out_dir / "intec_basis_snapshot.json").write_text(
        json.dumps(_basis_snapshot(), indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    man = p.export_deliverables(out_dir, plan_level="L0", plan_scale=0.01)
    if not man.get("ok"):
        # still continue — construction set is the primary goal
        pass

    from llmbim_drawings.construction import export_construction_set
    from llmbim_drawings.html_index import write_pack_index
    from llmbim_drawings.pdf_binder import export_pdf_binder
    from llmbim_drawings.schedules import export_drawing_list

    cons = out_dir / "construction"
    register = export_construction_set(
        p.model,
        cons,
        plan_level="L0",
        plan_scale=0.012,
        units="metric",
        dim_tiers=True,
        fractional_grids=True,
        grid_sides=True,
        room_areas=True,
        key_plan=True,
        keynotes=True,
        line_weights=True,
        hatches=True,
        stamp_block=True,
        sheets=intec_sheet_register(p),
    )
    export_pdf_binder(
        cons,
        out_dir / "PLOT_SET.pdf",
        title=f"{basis.PROJECT_NAME} — Construction Set ({basis.DOC})",
    )
    export_drawing_list(out_dir)
    write_pack_index(out_dir)

    verify = p.verify_pack(out_dir)
    (out_dir / "VERIFY.json").write_text(
        json.dumps(verify, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "SHEET_REGISTER.json").write_text(
        json.dumps(
            {
                "doc": basis.DOC,
                "count": len(register.get("sheets", [])),
                "sheets": register.get("sheets", []),
                "disciplines": basis.discipline_counts(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    root_abs = out_dir.resolve()
    print("BASIS", "projects/intec/intec_design_basis.py")
    print("stats", p.stats())
    print("wall_types", wall_type_counts(p))
    print("register_count", len(register.get("sheets", [])))
    print("disciplines", basis.discipline_counts())
    print("eigen_snapshot", derived.snapshot_meta().get("path"))
    print("OPEN", root_abs / "index.html")
    print("PLOT", root_abs / "PLOT_SET.pdf")
    print("PACK_OK", root_abs)
    print("VERIFY_OK", bool(verify.get("ok")), verify.get("missing") or "")
    print("HONESTY", HONESTY)
    return p, verify


if __name__ == "__main__":
    build_pack()
