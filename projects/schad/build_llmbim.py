"""SCHAD Phase 1 — basis → llm-bim Project (repo-first, WP-SCHAD-S0/S1).

This is the CI build harness: it imports the design basis ONLY from
``projects/schad`` (the in-repo SSOT). There is no ``SCHAD_ROOT`` / G:-drive
lookup here — the repo is the CI source of truth. ``examples/schad_garage.py``
remains for local G:-drive sync use.

Geometry is NOT invented here; every number comes from
``projects/schad/schad_design_basis.py`` (the only number source).

Wall / door / window types are the WP-SCHAD-S1 residential registry
(``llmbim_core.types_catalog``): W-EXT-2x6-BNB / W-INT-2x4 / W-1HR-GAR-ADU,
D-OH-12x9 / D-OH-12x12 / D-SC-36-ADA / D-HM-30, WIN-CASE-48x48.
Per the transition review §8, no Schad wall may map to W-EXT-CMU / W-INT-GYP.

Honesty: [DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION].

Run (from repo root):
  python examples/schad_build.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import schad_design_basis as basis
from llmbim import Project

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


def build_model(*, author: str = "agent") -> Project:
    """Basis → Project. Pure model build: no VCS dir, no export (tests use this)."""
    s = basis.build_scalars()
    walls_ft = basis.build_walls()
    doors = basis.build_doors()
    windows = basis.build_windows()
    placements = basis.build_placements()
    structure = basis.build_structure()
    notes = basis.build_notes()
    footprint_ft = basis.footprint()

    p = Project.create("SCHAD Garage / ADU / Workshop", vcs=False, author=author)
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

    poly_mm = [(ft(x), ft(y)) for x, y in footprint_ft]
    p.create_slab(
        level="L1",
        polygon=poly_mm,
        thickness_mm=s["slab_garage_t"] * FT_TO_MM,
        name="Slab-Garage-Workshop",
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
        wall_records.append({**w, "id": eid, "name": name})

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

    plate_mm = ft(s["plate_main"])
    for beam in structure.get("beams", []):
        p.place_beam(
            level="L1",
            start=(ft(beam["x"]), ft(beam["y1"])),
            end=(ft(beam["x"]), ft(beam["y2"])),
            section=beam.get("section", "W16x40"),
            name=beam.get("id", "beam"),
            z0_mm=plate_mm - s["beam_depth"] * FT_TO_MM,
        )

    for sw in structure.get("strong_walls", []):
        h_mm = ft(sw["h"])
        p.create_equipment_box(
            level="L1",
            origin=(ft(sw["x"]), ft(sw["y"])),
            size=(ft(s["ssw_w"]), s["ssw_t"] * FT_TO_MM, h_mm),
            name=f"{sw['id']}-{sw['model']}",
            kind="shear_panel",
            centered=False,
        )

    mech = next((r for r in placements if r["id"] == "MECHBATH"), None)
    if mech:
        mx, my = mech["x"] + 1.0, mech["y"] + 1.0
        equip = [
            ("B-1", "boiler", 2.0, 2.5, 5.0),
            ("B-2", "boiler", 2.0, 2.5, 5.0),
            ("PT-1", "pressure_vessel", 2.0, 2.0, 6.0),
            ("WH-1", "water_heater", 1.5, 1.5, 4.0),
            ("MANIFOLD", "manifold", 3.0, 1.0, 3.0),
        ]
        for i, (name, kind, ew, ed, eh) in enumerate(equip):
            p.create_equipment_box(
                level="L1",
                origin=(ft(mx + (i % 3) * 2.5), ft(my + (i // 3) * 3.0)),
                size=(ft(ew), ft(ed), ft(eh)),
                name=name,
                kind=kind,
                centered=False,
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
    return p


def wall_type_counts(p: Project) -> dict[str, int]:
    counts: dict[str, int] = {}
    for el in p.model.elements:
        if el.category == "wall":
            tid = el.type_id or "(untyped)"
            counts[tid] = counts.get(tid, 0) + 1
    return counts


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
            "no roof planes until WP-SCHAD-S2",
            "no footings/rebar until WP-SCHAD-S3",
            "headers/posts/typed shear until WP-SCHAD-S4",
            "Schad sheet register/details until WP-SCHAD-S5",
        ],
        "open_questions": basis.open_questions(),
    }


def build_pack(out_dir: Path) -> tuple[Project, dict[str, Any]]:
    """Full S0 harness: build model, commit to model VCS, export the pack."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    p = build_model()

    (out_dir / "schad_basis_snapshot.json").write_text(
        json.dumps(_basis_snapshot(), indent=2, default=str),
        encoding="utf-8",
    )

    p.bind_vcs(out_dir)
    p.commit(
        "SCHAD Phase 1 shell from in-repo basis SSOT — S1 wood types "
        "(W-EXT-2x6-BNB / W-INT-2x4 / W-1HR-GAR-ADU)"
    )
    man = p.export_deliverables(out_dir)
    if not man.get("ok"):
        raise RuntimeError(f"export_deliverables failed: {man}")
    verify = p.verify_pack(out_dir)

    root_abs = out_dir.resolve()
    print("BASIS", "projects/schad/schad_design_basis.py")
    print("stats", p.stats())
    print("wall_types", wall_type_counts(p))
    print("vcs", p.status())
    print("OPEN", root_abs / "index.html")
    print("PACK_OK", root_abs)
    print("VERIFY_OK", bool(verify.get("ok")), verify.get("missing") or "")
    print("HONESTY", HONESTY)
    print("TRANSITION", "docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md")
    return p, verify
