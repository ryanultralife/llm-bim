"""SCHAD Phase 1 — basis → llm-bim Project (repo-first, WP-SCHAD-S0/S1/S3/S2/S6).

This is the CI build harness: it imports the design basis ONLY from
``projects/schad`` (the in-repo SSOT). There is no ``SCHAD_ROOT`` / G:-drive
lookup here — the repo is the CI source of truth. ``examples/schad_garage.py``
remains for local G:-drive sync use.

Geometry is NOT invented here; every number comes from
``projects/schad/schad_design_basis.py`` (the only number source), the
structural record (``schad_structural.py``) or the ported detail geometry
(``schad_details.py``). The few values the record does not fix carry an
explicit ``*_assumed`` flag (stem height, equipment massing sizes).

Wall / door / window types are the WP-SCHAD-S1 residential registry
(``llmbim_core.types_catalog``): W-EXT-2x6-BNB / W-INT-2x4 / W-1HR-GAR-ADU,
D-OH-12x9 / D-OH-12x12 / D-SC-36-ADA / D-HM-30, WIN-CASE-48x48.
Per the transition review §8, no Schad wall may map to W-EXT-CMU / W-INT-GYP.

WP-SCHAD-S6 adds: foundations (strip/pad footings, stem walls, dual slabs —
S3 kernel), roofs (main gable / Bay-2 cross-gable / rear shed — S2 kernel),
MEP + ADU basis content, and the full Gate C sheet register (S5 kernel custom
``sheets=[]``) driven verbatim by ``schad_design_basis.sheet_register()``.

Honesty: [DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION].

Run (from repo root):
  python examples/schad_build.py
"""

from __future__ import annotations

import html
import json
import math
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import generate_schad_docs as gendocs
import schad_design_basis as basis
import schad_details as details_mod
import schad_house_basis as house
import schad_mep as mep
import schad_structural as struct
import svg_plans
from llmbim import Project
from llmbim_core.types_catalog import DEFAULT_HEADER_TYPES, DEFAULT_SHEARWALL_TYPES

FT_TO_MM = 304.8
IN_TO_MM = 25.4

HONESTY = "[DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION]"

# WP-SCHAD-S1 residential registry (llmbim_core.types_catalog)
WALL_TYPE_EXT = "W-EXT-2x6-BNB"
WALL_TYPE_INT = "W-INT-2x4"
WALL_TYPE_FIRE = "W-1HR-GAR-ADU"
DOOR_TYPES_OH = ("D-OH-12x9", "D-OH-12x12")
DOOR_TYPE_SC = "D-SC-36-ADA"
DOOR_TYPE_HM = "D-HM-30"
WINDOW_TYPE = "WIN-CASE-48x48"

# The record fixes footing section (18"x12") and stem thickness (8"/6") but not
# a stem height / frost-depth scalar. The drawn D01 wall section (schad_details:
# stem -0.9 ft → datum, footing -1.9 → -0.9 ft) is the only drawn value —
# transcribed ONCE here and flagged assumed (EOR / frost depth to confirm).
STEM_HEIGHT_FT_ASSUMED = 0.9  # [schad_details.d01_wall_section geometry]

# Mech/Bath equipment massing boxes: PLAN POSITIONS come from the MEP basis
# (schad_mep.mech_equipment_layout); the box sizes below are massing-only
# coordination volumes NOT fixed by the record — flagged size_assumed.
MECH_EQUIP_SIZE_FT_ASSUMED: dict[str, tuple[str, float, float, float]] = {
    "B-1": ("boiler", 2.0, 2.5, 5.0),
    "B-2": ("boiler", 2.0, 2.5, 5.0),
    "PT-1": ("pressure_vessel", 2.0, 2.0, 6.0),
    "WH-1": ("water_heater", 1.5, 1.5, 4.0),
    "MAN": ("manifold", 3.0, 1.0, 3.0),
}


def ft(v: float) -> float:
    return float(v) * FT_TO_MM


def _wall_len_mm(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(ft(x2) - ft(x1), ft(y2) - ft(y1))


def _point_on_segment(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float, tol_ft: float = 0.35
) -> float | None:
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return None
    t = ((px - x1) * dx + (py - y1) * dy) / L2
    if t < -0.05 or t > 1.05:
        return None
    t_clamped = max(0.0, min(1.0, t))
    cx, cy = x1 + t_clamped * dx, y1 + t_clamped * dy
    if math.hypot(px - cx, py - cy) > tol_ft:
        return None
    return t_clamped


def wall_type_for_kind(kind: str) -> tuple[str, str]:
    """Map Schad wall kind → (type_id, fire_rating) — S1 wood types only.

    The garage/rear-addition separation is the 1-hr rated wall per the basis
    annotation (kind ``fire-separation-1hr``, [RB note 4]).
    """
    k = (kind or "").lower()
    if "fire" in k:
        return WALL_TYPE_FIRE, "1-hr"
    if "interior" in k:
        return WALL_TYPE_INT, ""
    return WALL_TYPE_EXT, ""


def door_type_for(d: dict[str, Any]) -> str:
    """Pick the registered S1 door type matching the basis schedule row.

    Overhead doors select by leaf size against the registered D-OH-* types
    (no dimensions retyped here — nearest catalog match to the basis w/h).
    """
    from llmbim_core.types_catalog import DEFAULT_DOOR_TYPES

    kind = (d.get("type") or "").upper()
    if "OVERHEAD" in kind:
        w_mm, h_mm = d["w"] * FT_TO_MM, d["h"] * FT_TO_MM
        return min(
            DOOR_TYPES_OH,
            key=lambda tid: abs(DEFAULT_DOOR_TYPES[tid].width_mm - w_mm)
            + abs(DEFAULT_DOOR_TYPES[tid].height_mm - h_mm),
        )
    if "HOLLOW METAL" in (d.get("remarks") or "").upper():
        return DOOR_TYPE_HM
    return DOOR_TYPE_SC


def pad_footing_record_mm() -> tuple[float, float, float]:
    """Point-footing size under the HSS posts, parsed from the structural record.

    ``schad_structural.point_footing_check`` documents the [BOM] pad as
    36"x36"x30" — parsed here (never retyped) and cross-checked against the
    check's plan-size string.
    """
    m = re.search(r'(\d+)"x(\d+)"x(\d+)"', struct.point_footing_check.__doc__ or "")
    if not m:
        raise RuntimeError("pad footing size not found in structural record docstring")
    w_in, d_in, depth_in = (float(g) for g in m.groups())
    element = struct.point_footing_check()["element"]
    if f'{w_in:.0f}"x{d_in:.0f}"' not in element:
        raise RuntimeError(f"pad size mismatch vs record element {element!r}")
    return w_in * IN_TO_MM, d_in * IN_TO_MM, depth_in * IN_TO_MM


# --------------------------------------------------------------------------- #
# staged model build                                                           #
# --------------------------------------------------------------------------- #


def _build_shell(p: Project) -> dict[str, Any]:
    """Levels, grids, walls, openings, rooms, general notes. Returns build ctx."""
    s = basis.build_scalars()
    walls_ft = basis.build_walls()
    doors = basis.build_doors()
    windows = basis.build_windows()
    placements = basis.build_placements()
    notes = basis.build_notes()

    p.add_level("L1", 0)
    p.add_level("T.O. Plate - Main", ft(s["plate_main"]))
    p.add_level("T.O. Plate - Bay 2", ft(s["plate_bay2"]))
    p.add_level("Ridge", ft(s["ridge"]))

    bay = s["bay_L"]
    p.add_grid(
        "U",
        [ft(x) for x in (0.0, bay, 2 * bay, s["main_L"])],
        name="Grid-U",
        labels=["A", "B", "C", "D"],
    )
    p.add_grid(
        "V",
        [
            ft(y)
            for y in (
                -s["bay2_proj"],
                0.0,
                s["main_W"] / 2,
                s["main_W"],
                s["main_W"] + s["rear_W"],
            )
        ],
        name="Grid-V",
        labels=["1", "2", "3", "4", "5"],
    )

    wall_records: list[dict[str, Any]] = []
    for i, w in enumerate(walls_ft):
        type_id, fire = wall_type_for_kind(w.get("kind", ""))
        name = f"W{i + 1:02d}-{w.get('kind', 'wall')}"
        eid = p.create_wall(
            level="L1",
            start=(w["x1"], w["y1"]),
            end=(w["x2"], w["y2"]),
            unit="ft",
            thickness=w["thick"],
            height=w["height"],
            name=name,
            type_id=type_id,
            fire_rating=fire or None,
        )
        if w["height"] > s["plate_main"]:
            # Real multi-plate condition from the basis (Bay 2 14' plate,
            # 1-hr fire wall to 12' shed bearing): declare the intent so
            # WALL_EXCEEDS_STORY does not false-flag against the L1 10' clear
            # (transition review §7.5, WP-SCHAD-S4).
            p.op("set_param", id=eid, key="multi_plate", value=True)
            p.op("set_param", id=eid, key="plate_height_mm", value=ft(w["height"]))
        wall_records.append({**w, "id": eid, "name": name})
    wall_by_id = {wr["id"]: wr for wr in wall_records}

    def find_host(
        cx: float, cy: float, prefer: str | None = None
    ) -> tuple[str, float, float] | None:
        best: tuple[str, float, float, float] | None = None
        for wr in wall_records:
            t = _point_on_segment(cx, cy, wr["x1"], wr["y1"], wr["x2"], wr["y2"])
            if t is None:
                continue
            L = _wall_len_mm(wr["x1"], wr["y1"], wr["x2"], wr["y2"])
            off = t * L
            score = 0.0
            kind = (wr.get("kind") or "").lower()
            wall_hint = (prefer or "").lower()
            if wall_hint and wall_hint in kind:
                score -= 1.0
            if wall_hint == "front" and wr["y1"] <= 0.01 and wr["y2"] <= 0.01:
                score -= 2.0
            if wall_hint == "rear-north" and min(wr["y1"], wr["y2"]) >= s["main_W"] + s[
                "rear_W"
            ] - 0.05:
                score -= 2.0
            if (
                wall_hint == "rear-west"
                and abs(wr["x1"] - s["rear_off_x"]) < 0.05
                and abs(wr["x2"] - s["rear_off_x"]) < 0.05
            ):
                score -= 2.0
            if "fire" in wall_hint and "fire" in kind:
                score -= 2.0
            cand = (wr["id"], off, L, score)
            if best is None or cand[3] < best[3]:
                best = cand
        if best is None:
            return None
        return best[0], best[1], best[2]

    # Header jobs collected while placing openings (WP-SCHAD-S4): the header
    # mark per opening follows the structural record's header_schedule —
    # HDR-2 at the 12' overhead doors, HDR-1 at man doors + windows.
    header_jobs: list[dict[str, Any]] = []

    for d in doors:
        host = find_host(d["cx"], d["cy"], prefer=d.get("wall"))
        if host is None:
            p.create_note(
                level="L1",
                text=f"ORPHAN DOOR {d['mark']} at ({d['cx']:.1f},{d['cy']:.1f})",
                position=(ft(d["cx"]), ft(d["cy"])),
            )
            continue
        wid, off, L = host
        w_mm = d["w"] * FT_TO_MM
        h_mm = d["h"] * FT_TO_MM
        off_door = max(0.0, min(L - w_mm, off - w_mm / 2.0))
        p.place_door(
            host=wid,
            offset_mm=off_door,
            width_mm=w_mm,
            height_mm=h_mm,
            name=d["mark"],
            type_id=door_type_for(d),
        )
        header_jobs.append(
            {
                "opening": d["mark"],
                "hdr": "HDR-2" if "OVERHEAD" in (d.get("type") or "").upper() else "HDR-1",
                "wall_id": wid,
                "off_center_mm": off,
                "width_mm": w_mm,
                "head_mm": h_mm,
            }
        )

    for win in windows:
        host = find_host(win["cx"], win["cy"], prefer=win.get("wall"))
        if host is None:
            p.create_note(
                level="L1",
                text=f"ORPHAN WINDOW {win['mark']}",
                position=(ft(win["cx"]), ft(win["cy"])),
            )
            continue
        wid, off, L = host
        w_mm = win["w"] * FT_TO_MM
        h_mm = win["h"] * FT_TO_MM
        sill = win.get("sill", 3.0) * FT_TO_MM
        off_w = max(0.0, min(L - w_mm, off - w_mm / 2.0))
        p.place_window(
            host=wid,
            offset_mm=off_w,
            width_mm=w_mm,
            height_mm=h_mm,
            sill_mm=sill,
            name=win["mark"],
            type_id=WINDOW_TYPE,
        )
        header_jobs.append(
            {
                "opening": win["mark"],
                "hdr": "HDR-1",
                "wall_id": wid,
                "off_center_mm": off,
                "width_mm": w_mm,
                "head_mm": sill + h_mm,
            }
        )

    for room in placements:
        x, y, w, d = room["x"], room["y"], room["w"], room["d"]
        boundary = [
            (ft(x), ft(y)),
            (ft(x + w), ft(y)),
            (ft(x + w), ft(y + d)),
            (ft(x), ft(y + d)),
        ]
        p.create_room(
            level="L1",
            name=room["name"],
            boundary=boundary,
            height_mm=ft(s["plate_main"]),
        )
        if room.get("req"):
            p.create_note(
                level="L1",
                text=f"{room['id']}: {room['req'][:80]}",
                position=(ft(x + w / 2), ft(y + d / 2)),
            )

    for i, text in enumerate(notes.get("general", [])[:6]):
        p.create_note(
            level="L1",
            text=text,
            position=(ft(-8.0), ft(s["main_W"] + 4.0 - i * 2.5)),
        )
    p.create_note(
        level="L1",
        text=(
            f"SCHAD 2024-008 | 3730 Chandler Rd Quincy CA | "
            f"{s['area_total']:.0f} SF total | {HONESTY} | "
            f"see docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md"
        ),
        position=(ft(s["main_L"] / 2), ft(-8.0)),
    )
    return {
        "s": s,
        "notes": notes,
        "placements": placements,
        "structure": basis.build_structure(),
        "wall_records": wall_records,
        "wall_by_id": wall_by_id,
        "header_jobs": header_jobs,
    }


def _build_structure(p: Project, ctx: dict[str, Any]) -> None:
    """W16x40 beams, HSS posts, HDR headers, typed SSW panels (WP-SCHAD-S4)."""
    s = ctx["s"]
    structure = ctx["structure"]
    plate_mm = ft(s["plate_main"])
    beam_z0_mm = plate_mm - s["beam_depth"] * FT_TO_MM
    for beam in structure.get("beams", []):
        p.place_beam(
            level="L1",
            start=(ft(beam["x"]), ft(beam["y1"])),
            end=(ft(beam["x"]), ft(beam["y2"])),
            section=beam.get("section", s["beam"]),
            name=beam.get("id", "beam"),
            material="steel_A992",
            z0_mm=beam_z0_mm,
        )
        # HSS posts under the beam ends [BOM via schad_structural.post_check];
        # post height = underside of the W16x40 (plate - beam depth, basis).
        post_section = struct.post_check()["member"].replace(" ", "")
        for tag, yy in (("S", beam["y1"]), ("N", beam["y2"])):
            p.place_column(
                level="L1",
                origin=(ft(beam["x"]), ft(yy)),
                section=post_section,
                height_mm=beam_z0_mm,
                name=f"P-{beam.get('id', 'B')}-{tag}",
                material="steel_A500",
            )

    # Opening headers per the structural record's schedule (data-carry;
    # HDR marks/members from schad_structural.header_schedule, spans from
    # the basis door/window schedules).
    hdr_sched = {row["mark"]: row for row in struct.header_schedule()}
    for job in ctx["header_jobs"]:
        mark = job["hdr"]
        row = hdr_sched[mark]
        ht_type = DEFAULT_HEADER_TYPES[mark]
        wr = ctx["wall_by_id"][job["wall_id"]]
        x1, y1 = ft(wr["x1"]), ft(wr["y1"])
        dx, dy = ft(wr["x2"]) - x1, ft(wr["y2"]) - y1
        wall_len = math.hypot(dx, dy)
        ux, uy = dx / wall_len, dy / wall_len
        half = job["width_mm"] / 2.0
        c = max(half, min(wall_len - half, job["off_center_mm"]))
        p.op(
            "create_generic",
            category="header",
            level="L1",
            name=f"{mark} @ {job['opening']}",
            type_id=mark,
            params={
                "mark": mark,
                "member": ht_type.member,
                "record": row["member"],  # verbatim callout incl. citation
                "opening": job["opening"],
                "start_mm": [x1 + ux * (c - half), y1 + uy * (c - half)],
                "end_mm": [x1 + ux * (c + half), y1 + uy * (c + half)],
                "z0_mm": job["head_mm"],
                "span_mm": job["width_mm"],
                "width_mm": ht_type.width_mm,
                "depth_mm": ht_type.depth_mm,
                "ply": ht_type.ply,
                "material": ht_type.material,
                "use": row["use"],
                "honesty": "design development — EOR to confirm",
            },
        )

    # Simpson Strong-Walls: typed first-class panels (WP-SCHAD-S4) —
    # model/size from the basis + ShearWallType registry; positions carry
    # the basis pos_assumed flag (exact stations are the engineer's).
    for sw in structure.get("strong_walls", []):
        h_mm = ft(sw["h"])
        eid = p.create_equipment_box(
            level="L1",
            origin=(ft(sw["x"]), ft(sw["y"])),
            size=(ft(s["ssw_w"]), s["ssw_t"] * FT_TO_MM, h_mm),
            name=f"{sw['id']}-{sw['model']}",
            kind="shear_panel",
            centered=False,
        )
        swt = DEFAULT_SHEARWALL_TYPES[sw["model"]]
        p.op("set_type", id=eid, type_id=sw["model"])
        p.op("set_param", id=eid, key="mark", value=swt.mark)
        p.op("set_param", id=eid, key="model", value=sw["model"])
        p.op("set_param", id=eid, key="pos_assumed", value=bool(sw.get("pos_assumed")))


def _build_foundations(p: Project, ctx: dict[str, Any]) -> None:
    """WP-SCHAD-S3 content: strip/pad footings, stem walls, dual slabs.

    Basis fields consumed: footing_w 18" / footing_d 12", stem_front 8" /
    stem_typ 6", slab_garage_t 4" / slab_adu_t 3", rebar + anchor-bolt notes
    from ``build_notes()['foundation']`` (carried verbatim).
    """
    s = ctx["s"]
    fnd_notes = ctx["notes"]["foundation"]
    mech_notes = ctx["notes"]["mechanical"]
    ftg_w = s["footing_w"] * FT_TO_MM
    ftg_d = s["footing_d"] * FT_TO_MM
    stem_h = STEM_HEIGHT_FT_ASSUMED * FT_TO_MM
    rebar_note = next(n for n in fnd_notes if n.startswith("REBAR:"))
    ab_note = next(n for n in fnd_notes if n.startswith("ANCHOR BOLTS:"))

    # F1 strip footings under the bearing walls: exterior shell + the 1-hr
    # separation (it carries the shed bearing at 12', Q-SHED).
    for wr in ctx["wall_records"]:
        kind = str(wr.get("kind") or "")
        if not (kind.startswith("exterior") or "fire" in kind):
            continue  # interior 2x4 partitions are non-bearing per the record
        eid = p.create_strip_footing(
            level="L1",
            under_wall=wr["id"],
            width_mm=ftg_w,
            depth_mm=ftg_d,
            top_of_footing_mm=-stem_h,
            rebar=rebar_note,
            mark="F1",
            name=f"F1 @ {wr['name']}",
        )
        p.op("set_param", id=eid, key="stem_height_assumed", value=True)

    # Stem walls on the exterior perimeter: 8" at the garage front (the y<=0
    # OH-door line), 6" typical [RB foundation notes]. Height is the drawn D01
    # stem (STEM_HEIGHT_FT_ASSUMED) — flagged, frost depth by EOR.
    for wr in ctx["wall_records"]:
        kind = str(wr.get("kind") or "")
        if not kind.startswith("exterior"):
            continue
        front = max(wr["y1"], wr["y2"]) <= 1e-9  # garage-front segments (y<=0)
        t_mm = (s["stem_front"] if front else s["stem_typ"]) * FT_TO_MM
        mark = "S1" if front else "S2"
        eid = p.create_stem_wall(
            level="L1",
            path=[(ft(wr["x1"]), ft(wr["y1"])), (ft(wr["x2"]), ft(wr["y2"]))],
            height_mm=stem_h,
            thickness_mm=t_mm,
            mark=mark,
            name=f"{mark} @ {wr['name']}",
        )
        p.op("set_param", id=eid, key="height_assumed", value=True)
        p.op("set_param", id=eid, key="anchor_bolts", value=ab_note)

    # F2 pad footings under the HSS posts at the beam ends: 36"x36"x30"
    # [BOM via the structural record — parsed, not retyped]. Top at the datum
    # per the drawn D07 beam-bearing detail (base plate on footing top).
    pad_w, pad_d, pad_depth = pad_footing_record_mm()
    for beam in ctx["structure"].get("beams", []):
        for tag, yy in (("S", beam["y1"]), ("N", beam["y2"])):
            p.create_pad_footing(
                level="L1",
                origin=(ft(beam["x"]), ft(yy)),
                w_mm=pad_w,
                d_mm=pad_d,
                depth_mm=pad_depth,
                top_of_footing_mm=0.0,
                mark="F2",
                name=f"F2 @ P-{beam.get('id', 'B')}-{tag}",
            )

    # Dual slabs-on-grade [RB/BOM]: 4" garage/workshop (radiant), 3" ADU.
    # The 4" slab is the footprint minus the ADU panel — every coordinate
    # derives from the basis scalars.
    b, W, pj, L = s["bay_L"], s["main_W"], s["bay2_proj"], s["main_L"]
    rx, rL, rW = s["rear_off_x"], s["rear_L"], s["rear_W"]
    xw = rx + s["adu_L"]  # ADU / workshop partition line
    garage_poly_ft = [
        (0.0, 0.0), (b, 0.0), (b, -pj), (2 * b, -pj), (2 * b, 0.0),
        (L, 0.0), (L, W), (rx + rL, W), (rx + rL, W + rW),
        (xw, W + rW), (xw, W), (0.0, W),
    ]
    radiant_note = next(n for n in mech_notes if n.startswith("RADIANT FLOOR:"))
    g_id = p.create_slab_on_grade(
        level="L1",
        polygon=[(ft(x), ft(y)) for x, y in garage_poly_ft],
        thickness_mm=s["slab_garage_t"] * FT_TO_MM,
        mark="SOG-4",
        name="Slab-Garage-Workshop-4in",
    )
    p.op("set_param", id=g_id, key="radiant", value=radiant_note)
    a_id = p.create_slab_on_grade(
        level="L1",
        rect=(ft(rx), ft(W), ft(s["adu_L"]), ft(rW)),
        thickness_mm=s["slab_adu_t"] * FT_TO_MM,
        mark="SOG-3",
        name="Slab-ADU-3in",
    )
    r10_note = next(n for n in mech_notes if n.startswith("INSULATION: R-10"))
    p.op("set_param", id=a_id, key="underslab", value=r10_note)


def _build_roofs(p: Project, ctx: dict[str, Any]) -> None:
    """WP-SCHAD-S2 content: main gable, Bay-2 cross-gable, rear shed.

    Main: ridge E-W at y = main_W/2, plate 10', 6:12 → ridge 18' [RB/HANDOFF].
    Bay 2: PROPOSED cross-gable (Q-BAY2ROOF) — ridge N-S at x = 24' from the
    14' plate, peaks 18' and dies into the main ridge (footprint to y=16').
    Rear: shed bearing 12' at the main wall, 10' north eave (Q-SHED, 1.5:12).
    """
    s = ctx["s"]
    ov = s["overhang"] * FT_TO_MM
    thick = s["roof_t"] * FT_TO_MM
    pitch = s["roof_pitch"]
    L, W = s["main_L"], s["main_W"]
    b, pj = s["bay_L"], s["bay2_proj"]
    rx, rL, rW = s["rear_off_x"], s["rear_L"], s["rear_W"]

    main_id = p.create_gable_roof(
        level="L1",
        footprint=[(0.0, 0.0), (ft(L), 0.0), (ft(L), ft(W)), (0.0, ft(W))],
        ridge_axis="x",
        plate_mm=ft(s["plate_main"]),
        pitch=pitch,
        overhang_mm=ov,
        thickness_mm=thick,
        name="Roof-Main-Gable",
    )
    bay_id = p.create_gable_roof(
        level="L1",
        footprint=[
            (ft(b), ft(-pj)), (ft(2 * b), ft(-pj)),
            (ft(2 * b), ft(W / 2)), (ft(b), ft(W / 2)),
        ],
        ridge_axis="y",
        plate_mm=ft(s["plate_bay2"]),
        pitch=pitch,
        overhang_mm=ov,
        thickness_mm=thick,
        name="Roof-Bay2-CrossGable",
    )
    p.op(
        "set_param", id=bay_id, key="status",
        value="Q-BAY2ROOF proposed — confirm before elevations print",
    )
    shed_id = p.create_shed_roof(
        level="L1",
        footprint=[
            (ft(rx), ft(W)), (ft(rx + rL), ft(W)),
            (ft(rx + rL), ft(W + rW)), (ft(rx), ft(W + rW)),
        ],
        high_side="S",
        plate_low_mm=ft(s["plate_rear_low"]),
        plate_high_mm=ft(s["plate_rear_high"]),
        overhang_mm=ov,
        thickness_mm=thick,
        name="Roof-Rear-Shed",
    )
    p.op(
        "set_param", id=shed_id, key="status",
        value="Q-SHED open — verify 1.5:12 w/ truss fab against 75 psf snow",
    )

    # Roofing assembly for the takeoff (roof area is priced on-slope in the
    # BOQ). R-38 is the USER directive; the 75 psf snow load and 18" overhang
    # are basis. The FINISH is NOT specified in the basis — asphalt shingle is
    # assumed here so the takeoff has an assembly to price.
    # OPEN: confirm asphalt vs standing-seam metal (R-METAL-R38) with owner.
    for _rid in (main_id, bay_id, shed_id):
        p.op("set_type", id=_rid, type_id="R-ASPHALT-R38")


def _build_mep_content(p: Project, ctx: dict[str, Any]) -> None:
    """WP-SCHAD-S6 basis content: Mech/Bath equipment at the MEP-basis
    positions, plumbing fixture marks, panel/EV notes, ADU ADA note.

    Positions come from ``schad_mep`` layouts (design-intent schematic).
    Equipment box sizes are massing volumes NOT fixed by the record —
    flagged ``size_assumed``. Fixtures/devices without recorded dimensions
    are carried as note elements (no invented geometry).
    """
    s = ctx["s"]
    placed_marks: set[str] = set()
    for entry in mep.mech_equipment_layout():
        sym = str(entry["sym"])
        note = str(entry.get("note") or "")
        if sym in {"B", "PT", "WH"}:
            mark = note.split()[0]
        elif sym == "MAN":
            mark = "MAN"
        else:
            # thermostats / propane stub / exhaust fan / CO alarm: no recorded
            # dimensions — carried as design-intent notes, not boxes
            p.create_note(
                level="L1",
                text=f"{sym}: {note}"[:120],
                position=(ft(entry["x"]), ft(entry["y"])),
            )
            continue
        kind, ew, ed, eh = MECH_EQUIP_SIZE_FT_ASSUMED[mark]
        eid = p.create_equipment_box(
            level="L1",
            origin=(ft(entry["x"]), ft(entry["y"])),
            size=(ft(ew), ft(ed), ft(eh)),
            name=mark,
            kind=kind,
            centered=True,
        )
        p.op("set_param", id=eid, key="size_assumed", value=True)
        p.op("set_param", id=eid, key="basis_note", value=note)
        placed_marks.add(mark)

    # Plumbing fixtures [RB MEP-201 + USER]: plan positions only in the record
    # — carried as marked notes (fixture dimensions are not recorded).
    for fi in mep.plumbing_fixtures_layout():
        p.create_note(
            level="L1",
            text=f"{fi['sym']}: {fi['note']}"[:120],
            position=(ft(fi["x"]), ft(fi["y"])),
        )

    # Electrical panels + EV receptacle [RB MEP-101] — anchor devices only;
    # the full device layout renders on MEP-101 from the basis.
    for dev in mep.electrical_devices():
        if dev["sym"] in {"P", "EV"}:
            p.create_note(
                level="L1",
                text=f"{dev['sym']} ckt {dev['ckt']}: {dev.get('note') or dev['sym']}"[:120],
                position=(ft(dev["x"]), ft(dev["y"])),
            )

    # ADU ADA basis note at the ADU center (full build-out on sheet A1.2)
    import schad_adu as adu

    p.create_note(
        level="L1",
        text=adu.adu_ada_notes()[0][:120],
        position=(ft(s["rear_off_x"] + s["adu_L"] / 2), ft(s["main_W"] + s["rear_W"] / 2)),
    )


def build_model(
    *,
    author: str = "agent",
    on_stage: Callable[[Project, str], None] | None = None,
) -> Project:
    """Basis → Project. Pure model build: no VCS dir, no export (tests use this).

    ``on_stage(p, message)`` is invoked after each meaningful batch so
    ``build_pack`` can record true model-VCS history between stages.
    """
    p = Project.create("SCHAD Garage / ADU / Workshop", vcs=False, author=author)
    ctx = _build_shell(p)
    if on_stage:
        on_stage(
            p,
            "S0/S1 shell from in-repo basis SSOT — wood wall types "
            "(W-EXT-2x6-BNB / W-INT-2x4 / W-1HR-GAR-ADU), openings, rooms",
        )
    _build_structure(p, ctx)
    if on_stage:
        on_stage(
            p,
            "S4 structure — W16x40 beams, HSS posts, HDR-1/HDR-2 headers, "
            "typed SSW panels",
        )
    _build_foundations(p, ctx)
    if on_stage:
        on_stage(
            p,
            'S3 foundations — F1 strips 18"x12" w/ (2) #4, S1/S2 stems 8"/6", '
            'F2 pads 36"x36"x30", dual slabs 4"/3"',
        )
    _build_roofs(p, ctx)
    if on_stage:
        on_stage(
            p,
            "S2 roofs — main gable 6:12 ridge 18', Bay-2 cross-gable "
            "(Q-BAY2ROOF proposed), rear shed 12'/10' (Q-SHED)",
        )
    _build_mep_content(p, ctx)
    if on_stage:
        on_stage(
            p,
            "S6 MEP/ADU content — Mech/Bath equipment at MEP-basis positions, "
            "plumbing fixture marks, panel/EV notes, ADU ADA note",
        )
    return p


def wall_type_counts(p: Project) -> dict[str, int]:
    counts: dict[str, int] = {}
    for el in p.model.elements:
        if el.category == "wall":
            tid = el.type_id or "(untyped)"
            counts[tid] = counts.get(tid, 0) + 1
    return counts


# --------------------------------------------------------------------------- #
# Gate C sheet register (WP-SCHAD-S5/S6)                                       #
# --------------------------------------------------------------------------- #


def _foundation_plan_view(model: Any) -> Any:
    """S1.1 — plan of the PLACED foundation elements (footings dashed, stems,
    slabs) + the basis foundation notes and the strip-footing design check.

    Rendered from the model (not re-derived from the basis) so the sheet is
    honest to what was built; labels quote the basis scalars.
    """
    from llmbim_core.foundations import strip_segment_rects
    from llmbim_drawings.view import DrawingView

    s = basis.build_scalars()
    scale = 0.036  # px/mm
    pad = 30.0

    footings: list[Any] = []
    stems: list[Any] = []
    slabs: list[Any] = []
    pts: list[tuple[float, float]] = []
    for el in model.elements:
        if el.category == "footing":
            footings.append(el)
        elif el.category == "stem_wall":
            stems.append(el)
        elif el.category == "slab" and el.params.get("kind") == "slab_on_grade":
            slabs.append(el)
        else:
            continue
        for key in ("path_mm", "polygon_mm"):
            for q in el.params.get(key) or []:
                pts.append((float(q[0]), float(q[1])))
    if not pts:
        return DrawingView(width=400, height=200, body="<text y='20'>no foundations</text>")
    minx = min(q[0] for q in pts)
    miny = min(q[1] for q in pts)
    maxy = max(q[1] for q in pts)
    height = (maxy - miny) * scale + 2 * pad

    def T(x: float, y: float) -> tuple[float, float]:
        return ((x - minx) * scale + pad, height - ((y - miny) * scale + pad))

    def poly_d(poly: list[Any]) -> str:
        return (
            "M "
            + " L ".join(
                f"{T(float(q[0]), float(q[1]))[0]:.1f},{T(float(q[0]), float(q[1]))[1]:.1f}"
                for q in poly
            )
            + " Z"
        )

    parts: list[str] = []
    for el in slabs:
        mark = el.params.get("mark") or ""
        t_in = float(el.params.get("thickness_mm") or 0) / IN_TO_MM
        poly = el.params.get("polygon_mm") or []
        parts.append(
            f'<path d="{poly_d(poly)}" fill="#f5f2ea" stroke="#999" stroke-width="1"/>'
        )
        cx = sum(float(q[0]) for q in poly) / len(poly)
        cy = sum(float(q[1]) for q in poly) / len(poly)
        tx, ty = T(cx, cy)
        parts.append(
            f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="middle" font-size="11" '
            f'font-family="Segoe UI,Arial">{html.escape(str(mark))} — {t_in:.0f}" SLAB</text>'
        )
    for el in footings:
        if el.params.get("kind") == "pad":
            poly = el.params.get("polygon_mm") or []
            parts.append(
                f'<path d="{poly_d(poly)}" fill="#e8ddc8" stroke="#8B4513" '
                f'stroke-width="1.4" stroke-dasharray="6 3"/>'
            )
            cx, cy = (float(v) for v in el.params.get("center_mm") or [0, 0])
            tx, ty = T(cx, cy)
            parts.append(
                f'<text x="{tx:.1f}" y="{ty - 10:.1f}" text-anchor="middle" font-size="8" '
                f'font-family="Segoe UI,Arial" fill="#5a3310">F2</text>'
            )
        else:
            path = el.params.get("path_mm") or []
            for rect in strip_segment_rects(path, float(el.params.get("width_mm") or 0)):
                parts.append(
                    f'<path d="{poly_d(list(rect))}" fill="none" stroke="#8B4513" '
                    f'stroke-width="1.2" stroke-dasharray="7 4" opacity="0.9"/>'
                )
    for el in stems:
        path = el.params.get("path_mm") or []
        for rect in strip_segment_rects(path, float(el.params.get("thickness_mm") or 0)):
            parts.append(
                f'<path d="{poly_d(list(rect))}" fill="#cfcfcf" stroke="#333" stroke-width="0.9"/>'
            )

    # legend + notes column (basis values quoted, check from the record)
    legend = [
        f'F1 STRIP FTG {s["footing_w"] * 12:.0f}"W x {s["footing_d"] * 12:.0f}"D (DASHED)',
        f'F2 PAD FTG @ HSS POSTS (see D07) — {struct.point_footing_check()["element"]}',
        f'S1 STEM {s["stem_front"] * 12:.0f}" @ GARAGE FRONT · S2 STEM {s["stem_typ"] * 12:.0f}" TYP',
        f'SOG-4 GARAGE/SHOP SLAB {s["slab_garage_t"] * 12:.0f}" · SOG-3 ADU SLAB {s["slab_adu_t"] * 12:.0f}"',
    ]
    chk = struct.strip_footing_check()
    notes_col = (
        legend
        + [""]
        + basis.build_notes()["foundation"]
        + [
            "",
            f"STRIP q={chk['q_psf']} psf <= {chk['q_allow_psf']:.0f} presumptive OK "
            "(design-support; geotech + EOR required)",
            HONESTY,
        ]
    )
    x_notes = (max(q[0] for q in pts) - minx) * scale + 2 * pad + 20
    for i, line in enumerate(notes_col):
        parts.append(
            f'<text x="{x_notes:.1f}" y="{40 + i * 15:.1f}" font-size="9.5" '
            f'font-family="Segoe UI,Arial">{html.escape(line)}</text>'
        )
    width = x_notes + 480
    return DrawingView(width=width, height=height, body="\n".join(parts))


def _structural_schedules_view(model: Any) -> Any:
    """S4.1 — shear-wall schedule + foundation rebar schedule (carried data)."""
    from llmbim_core.foundations import rebar_schedule
    from llmbim_core.material_lists import shear_wall_schedule
    from llmbim_drawings.layout import compose_sheet, table_view

    sw_rows = [
        [
            r["mark"],
            r["model"],
            r["size"],
            r["count"],
            "stations assumed — EOR to confirm" if all(
                loc.get("pos_assumed") for loc in r["locations"]
            ) else "",
        ]
        for r in shear_wall_schedule(model)
    ]
    rb_rows = [
        [
            r["mark"],
            r["type"],
            r["rebar"] or "—",
            r["qty"],
            r["length_m"] or "",
            r["area_m2"] or "",
        ]
        for r in rebar_schedule(model)
    ]
    cells = [
        (
            table_view(
                ["MARK", "MODEL", "SIZE", "QTY", "NOTE"],
                sw_rows,
                title="SHEAR WALL SCHEDULE — SIMPSON SSW [BOM]",
            ),
            "SHEAR WALL SCHEDULE",
            "NTS",
        ),
        (
            table_view(
                ["MARK", "TYPE", "REBAR / REINF (carried)", "QTY", "LEN m", "AREA m2"],
                rb_rows,
                title="FOUNDATION REBAR SCHEDULE (carried basis callouts)",
            ),
            "REBAR SCHEDULE",
            "NTS",
        ),
    ]
    return compose_sheet(cells, width=1000, height=680, arrange="column")


def _house_doc_text(level: str) -> str:
    """H1.x — existing-house record [HPLAN] as a doc sheet."""
    rooms = [r for r in house.house_rooms() if r["level"] == level]
    lines = [
        "# EXISTING HOUSE RECORD [HPLAN]",
        "",
        "FLOORPLAN for PLANNING ONLY. CONFIRM ALL DIMENSIONS. [HPLAN, verbatim]",
        "",
        f"## {level} level rooms",
    ]
    for r in rooms:
        lines.append(f"- {r['name']}" + (f" — {r['note']}" if r["note"] else ""))
    if level == "Main":
        lines += ["", "## Exterior features"]
        lines += [f"- {f}" for f in house.house_exterior_features()]
        lines += ["", "## Opening callouts legible on the record"]
        lines += [f"- {o['mark']}: {o['size']} ({o['loc']})" for o in house.house_openings()]
    fr = house.house_framing()
    lines += ["", "## Framing record"]
    lines += [f"- {k}: {v}" for k, v in fr.items()]
    lines += ["", f"{HONESTY} — existing conditions; field verification required."]
    return "\n".join(lines)


def _remodel_doc_text() -> str:
    """H2.1 — Phase 2 scope + design criteria + honesty/basis notes."""
    scope = house.remodel_scope()
    lines = [
        "# HOUSE REMODEL — SCOPE & DESIGN CRITERIA (PHASE 2)",
        "",
        HONESTY,
        "",
        "## Directive",
        scope["directive"],
        "",
        "## Design directives",
    ]
    lines += [f"- {d}" for d in scope["design_directives"]]
    lines += ["", "## Work outline"]
    lines += [f"- {w}" for w in scope["work"]]
    lines += ["", "## Structural flags (EOR)"]
    lines += [f"- {f}" for f in scope["structural_flags"]]
    lines += ["", "## Basis + calc documents in this pack"]
    lines += [
        "- docs/STRUCTURAL_CALCS.md — design-support member/footing/lateral checks",
        "- docs/MEP_CALCS.md — service / plumbing / mechanical sizing",
        "- docs/SPECIFICATIONS.md — CSI outline specification",
        "- schad_basis_snapshot.json — scalars + open questions (SSOT snapshot)",
    ]
    lines += ["", "## Open owner questions"]
    lines += [f"- {q}" for q in scope["owner_questions"]]
    lines += [
        "",
        "Values marked (ASSUMED) require confirmation; structural PE review "
        "reserved per contract. " + HONESTY,
    ]
    return "\n".join(lines)


def schad_sheet_register(p: Project) -> list[dict[str, Any]]:
    """The Gate C register — numbers/titles/scales verbatim from
    ``basis.sheet_register()`` (the permit-set index [RB A0.1]), plus S4.1
    structural schedules (shear wall + rebar; Gate C schedule content the
    basis index carries on other sheets).

    ``units: "imperial"`` / ``tags: True`` are the WP-SCHAD-S7 annotation
    contract keys — inert extra opts until S7 lands (register entries are
    permissive dicts), imperial dims + door/window tag bubbles after.
    """
    s = basis.build_scalars()
    reg = {row["number"]: row for row in basis.sheet_register()}
    details = details_mod.build_details()
    open_q = [q for q in basis.open_questions() if q["status"] not in ("resolved",)]

    def e(no: str, kind: str, **opts: Any) -> dict[str, Any]:
        row = reg[no]
        return {
            "no": no,
            "title": row["title"],
            "kind": kind,
            "scale_note": row["scale"],
            "units": "imperial",
            **opts,
        }

    sheets: list[dict[str, Any]] = [
        e(
            "A0.1",
            "cover",
            subtitle="SCHAD 2024-008 · 3730 Chandler Rd, Quincy CA 95971 · Ledger Built LLC",
            notes=[
                HONESTY,
                f"AREAS [RB A0.1]: {s['area_total']:.0f} SF TOTAL — GARAGE "
                f"{s['area_garage']:.0f} / ADU {s['area_adu']:.0f} / WORKSHOP "
                f"{s['area_workshop']:.0f}",
                f"OPEN QUESTIONS: {len(open_q)} unresolved — see "
                "schad_basis_snapshot.json (Q-SETBACK, Q-LOC, Q-WIN, ...)",
                "STRUCTURAL PE: RESERVED (by others per HANDOFF)",
            ],
        ),
        e("C1.1", "custom_svg", view=svg_plans.site_plan_svg()),
        e("A1.1", "plan", level="L1", tags=True),
        e("A1.2", "custom_svg", view=svg_plans.adu_plan_svg()),
        e("A2.1", "elevations", pair=["S", "N"]),
        e("A2.2", "elevations", pair=["E", "W"]),
        e("A3.1", "sections"),
        e("S1.1", "custom_svg", provider=_foundation_plan_view),
        e("S2.1", "custom_svg", view=svg_plans.roof_framing_svg()),
        e("S3.1", "details", details=details[0:4]),
        e("S3.2", "details", details=details[4:8]),
        e("S3.3", "details", details=details[8:12]),
        e("A4.1", "schedule", schedule=["door", "window"]),
        # S4.1 is not in the [RB A0.1] index — Gate C judgment sheet carrying
        # the SSW + rebar schedules as first-class tables.
        {
            "no": "S4.1",
            "title": "STRUCTURAL SCHEDULES - SHEAR WALLS & REBAR",
            "kind": "custom_svg",
            "scale_note": "-",
            "units": "imperial",
            "provider": _structural_schedules_view,
        },
        e("MEP-101", "custom_svg", view=svg_plans.mep_plan_svg("E")[2]),
        e("MEP-201", "custom_svg", view=svg_plans.mep_plan_svg("P")[2]),
        e("MEP-301", "custom_svg", view=svg_plans.mep_plan_svg("M")[2]),
        e("H1.1", "doc", text=_house_doc_text("Main")),
        e("H1.2", "doc", text=_house_doc_text("Upper")),
        e("H2.1", "doc", text=_remodel_doc_text()),
        e("H2.2", "custom_svg", view=svg_plans.house_concept_svg()),
    ]
    return sheets


def _basis_snapshot() -> dict[str, Any]:
    s = basis.build_scalars()
    return {
        "source": "projects/schad/schad_design_basis.py (in-repo SSOT)",
        "project": "2024-008 SCHAD Garage/ADU/Workshop",
        "address": "3730 Chandler Rd, Quincy, CA 95971",
        "scalars_ft": s,
        "areas": {
            "total": s["area_total"],
            "garage": s["area_garage"],
            "adu": s["area_adu"],
            "workshop": s["area_workshop"],
            "mech_published": s.get("area_mech"),
        },
        "honesty": HONESTY,
        "transition_review": "docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md",
        "known_gaps": [
            "SSW pad anchorage footings carried on detail D06 only (EOR scope)",
            "stem height / frost depth assumed from drawn D01 (flagged in model)",
            "S7 imperial dims + door/window tags pending on plan sheets",
        ],
        "assumed_flags": [
            "stem_height_assumed (STEM_HEIGHT_FT_ASSUMED from D01 geometry)",
            "size_assumed on Mech/Bath equipment massing boxes",
            "pos_assumed on SSW panels + basis door/window placements (Q-LOC)",
        ],
        "open_questions": basis.open_questions(),
    }


def build_pack(out_dir: Path) -> tuple[Project, dict[str, Any]]:
    """Full harness: staged build with model-VCS commits, export, Gate C
    register, calc docs, re-verified pack."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bound = {"vcs": False}

    def _stage(proj: Project, message: str) -> None:
        if not bound["vcs"]:
            proj.bind_vcs(out_dir)
            bound["vcs"] = True
        proj.commit(message)

    p = build_model(on_stage=_stage)

    (out_dir / "schad_basis_snapshot.json").write_text(
        json.dumps(_basis_snapshot(), indent=2, default=str),
        encoding="utf-8",
    )

    man = p.export_deliverables(out_dir)
    if not man.get("ok"):
        raise RuntimeError(f"export_deliverables failed: {man}")

    # Gate C: replace the default construction register with the Schad set
    # (WP-SCHAD-S5 custom sheets), then refresh the artifacts derived from it.
    from llmbim_drawings.construction import export_construction_set
    from llmbim_drawings.html_index import write_pack_index
    from llmbim_drawings.pdf_binder import export_pdf_binder
    from llmbim_drawings.schedules import export_drawing_list

    cons = out_dir / "construction"
    # Full professional CD anatomy (WP-SCHAD-ANATOMY-REBUILD): grid bubbles
    # with fractional intermediates + per-discipline sides, 3-tier dimension
    # chains, material hatches, 3-tier line-weight hierarchy, boxed room tags
    # with areas, numbered keynotes + legend, key plan, and a reserved PE/SE
    # stamp block on structural sheets. Per docs/CD_COMPLETENESS_STANDARD.md
    # (Ryan Group Architects / CFBR Structural = the Sierra Star + Verseon
    # reference sets). Revisions omitted — first DD issue, nothing to cloud yet.
    register = export_construction_set(
        p.model, cons, plan_level="L1", plan_scale=0.04,
        units="imperial",
        dim_tiers=True,
        fractional_grids=True,
        grid_sides=True,
        room_areas=True,
        key_plan=True,
        keynotes=True,
        line_weights=True,
        hatches=True,
        stamp_block=True,
        sheets=schad_sheet_register(p),
    )
    export_pdf_binder(cons, out_dir / "PLOT_SET.pdf", title=p.model.name)
    export_drawing_list(out_dir)

    # Gate C calc / basis docs generated into the pack
    docs_dir = out_dir / "docs"
    docs_dir.mkdir(exist_ok=True)
    for fname, gen in (
        ("STRUCTURAL_CALCS.md", gendocs.structural_doc),
        ("MEP_CALCS.md", gendocs.mep_doc),
        ("SPECIFICATIONS.md", gendocs.spec_doc),
    ):
        (docs_dir / fname).write_text("\n".join(gen()) + "\n", encoding="utf-8")

    write_pack_index(out_dir)

    # Re-verify AFTER the register swap so VERIFY.json reflects the real pack
    verify = p.verify_pack(out_dir)
    (out_dir / "VERIFY.json").write_text(
        json.dumps(verify, indent=2) + "\n", encoding="utf-8"
    )

    root_abs = out_dir.resolve()
    print("BASIS", "projects/schad/schad_design_basis.py")
    print("stats", p.stats())
    print("wall_types", wall_type_counts(p))
    print("vcs", p.status())
    print("vcs_log", [c.get("message", "")[:44] for c in p.log()])
    print("register", [sh["no"] for sh in register["sheets"]])
    print("OPEN", root_abs / "index.html")
    print("PACK_OK", root_abs)
    print("VERIFY_OK", bool(verify.get("ok")), verify.get("missing") or "")
    print("HONESTY", HONESTY)
    print("TRANSITION", "docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md")
    return p, verify
