"""SCHAD Garage / ADU / Workshop — BIM from the Schad design-basis SSOT.

Geometry is NOT invented here. Source of truth is the Ledger Built /
Schad digital thread (imperial basis, already used for the Revit model):

  G:\\My Drive\\Schad Garage\\Revit\\schad_design_basis.py
  (target after WP-SCHAD-S0: projects/schad/design_basis.py)

Phase 1: 3730 Chandler Rd, Quincy CA 95971 — Garage/ADU/Workshop complex
  48' x 32' main + Bay 2 +2' south + rear ADU/workshop shed
  2,080 SF published; W16x40 beams; SSW panels; Mech/Bath in Bay 3 NE

Honesty: [DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION].

Transition review (Claude work until Gate D):
  docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md

Run:
  python examples/schad_garage.py
  $env:SCHAD_ROOT = "G:\\My Drive\\Schad Garage"
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

from llmbim import Project

FT_TO_MM = 304.8
IN_TO_MM = 25.4


def _schad_root() -> Path | None:
    candidates: list[Path] = []
    if os.environ.get("SCHAD_ROOT"):
        candidates.append(Path(os.environ["SCHAD_ROOT"]))
    # After WP-SCHAD-S0: in-repo projects/schad
    here = Path(__file__).resolve().parent.parent
    candidates.append(here / "projects" / "schad")
    candidates.append(Path(r"G:\My Drive\Schad Garage"))
    candidates.append(
        Path(os.environ.get("USERPROFILE", "")) / "MechanicalBattery" / "SchadWork"
    )
    for p in candidates:
        if (p / "design_basis.py").is_file():
            return p.resolve()
        basis = p / "Revit" / "schad_design_basis.py"
        if basis.is_file():
            return p.resolve()
        if (p / "schad_design_basis.py").is_file():
            return p.resolve()
    return None


def _load_basis_module(root: Path) -> Any:
    for candidate in (
        root / "design_basis.py",
        root / "Revit" / "schad_design_basis.py",
        root / "schad_design_basis.py",
    ):
        if candidate.is_file():
            basis_path = candidate
            break
    else:
        raise FileNotFoundError(f"schad design_basis not under {root}")
    spec = importlib.util.spec_from_file_location("schad_design_basis", basis_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {basis_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schad_design_basis"] = mod
    spec.loader.exec_module(mod)
    return mod


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


def _type_for_kind(kind: str) -> tuple[str | None, str]:
    """Map Schad wall kind → (type_id, fire_rating).

    NOTE: Until WP-SCHAD-S1 ships wood types, we still map to industrial
    catalog IDs (WRONG for BOQ). Transition review forbids leaving this
    after S1 — replace with W-EXT-2x6-BNB / W-INT-2x4 / W-1HR-GAR-ADU.
    """
    k = (kind or "").lower()
    if "fire" in k:
        return "W-EXT-CMU", "1-hr"  # TEMP — S1 must fix
    if "interior" in k:
        return "W-INT-GYP", ""
    return "W-EXT-CMU", ""


def build_schad(out_dir: Path, schad_root: Path | None = None) -> Project:
    root = schad_root or _schad_root()
    if root is None:
        raise FileNotFoundError(
            "Schad design basis not found. Set SCHAD_ROOT to the folder that "
            "contains design_basis.py or Revit/schad_design_basis.py "
            "(e.g. G:\\My Drive\\Schad Garage). After S0: projects/schad/."
        )
    basis = _load_basis_module(root)
    s = basis.build_scalars()
    walls_ft = basis.build_walls()
    doors = basis.build_doors()
    windows = basis.build_windows()
    placements = basis.build_placements()
    structure = basis.build_structure()
    notes = basis.build_notes()
    footprint_ft = basis.footprint()

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    p = Project.create("SCHAD Garage / ADU / Workshop")
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
        type_id, fire = _type_for_kind(w.get("kind", ""))
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
        is_oh = "OVERHEAD" in (d.get("type") or "").upper()
        type_id = "D-HM-72" if is_oh else "D-HM-36"
        p.place_door(
            host=wid,
            offset_mm=off_door,
            width_mm=w_mm,
            height_mm=h_mm,
            name=d["mark"],
            type_id=type_id,
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
            type_id="WIN-VIEW",
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
            z0_mm=plate_mm - 16 * IN_TO_MM,
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
            f"{s['area_total']:.0f} SF total | "
            f"[DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION] | "
            f"see docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md"
        ),
        position=(ft(s["main_L"] / 2), ft(-8.0)),
    )

    basis_dump = {
        "source": str(root),
        "project": "2024-008 SCHAD Garage/ADU/Workshop",
        "address": "3730 Chandler Rd, Quincy, CA 95971",
        "scalars_ft": s,
        "areas": {
            "total": s["area_total"],
            "garage": s["area_garage"],
            "adu": s["area_adu"],
            "workshop": s["area_workshop"],
            "mech_published": s.get("area_mech"),
            "mechbath_sf": 108.0,
        },
        "honesty": "[DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION]",
        "transition_review": "docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md",
        "known_gaps": [
            "wall types still industrial CMU until WP-SCHAD-S1",
            "no roof planes until WP-SCHAD-S2",
            "no footings/rebar until WP-SCHAD-S3",
        ],
        "open_questions": basis.open_questions() if hasattr(basis, "open_questions") else [],
    }
    (out_dir / "schad_basis_snapshot.json").write_text(
        json.dumps(basis_dump, indent=2, default=str),
        encoding="utf-8",
    )

    p.commit("SCHAD Phase 1 shell from design basis SSOT (pre-Gate-A)")
    man = p.export_deliverables(out_dir)
    if not man.get("ok"):
        raise RuntimeError(f"export_deliverables failed: {man}")

    root_abs = out_dir.resolve()
    print("SCHAD_ROOT", root)
    print("stats", p.stats())
    print("OPEN_INDEX", root_abs / "index.html")
    print("OPEN_VIEWER3D", root_abs / "viewer3d.html")
    print("OPEN_STEP", root_abs / "model.step")
    print("OPEN_PDF", root_abs / "PLOT_SET.pdf")
    print("OPEN_IFC", root_abs / "model.ifc")
    print("OPEN_GLTF", root_abs / "model.gltf")
    print("PACK_OK", root_abs)
    print("TRANSITION", "docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md")
    return p


def main() -> int:
    here = Path(__file__).resolve().parent.parent
    out = here / "output" / "schad_garage"
    try:
        build_schad(out)
    except FileNotFoundError as e:
        print("ERROR", e, file=sys.stderr)
        return 1
    except Exception as e:
        print("ERROR", type(e).__name__, e, file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
