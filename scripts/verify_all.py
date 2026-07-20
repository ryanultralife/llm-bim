#!/usr/bin/env python3
"""Regenerate real cases and fail if packs are incomplete."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages" / "sdk"))
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "packages" / "geometry"))
sys.path.insert(0, str(ROOT / "packages" / "drawings"))
sys.path.insert(0, str(ROOT / "packages" / "ifc"))

from llmbim_core.rules import run_design_rules  # noqa: E402
from llmbim_drawings.deliverables import verify_pack  # noqa: E402

from examples.intec_site import build_intec  # noqa: E402
from examples.proto10_separator import build_proto10  # noqa: E402
from examples.schad_build import build_schad_pack  # noqa: E402

# Schad wall types that must NEVER appear after WP-SCHAD-S1
# (docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md §8: no CMU on Schad walls).
SCHAD_FORBIDDEN_WALL_TYPES = {"W-EXT-CMU", "W-INT-GYP", "W-SHIELD-CONC", "W-GENERIC-200"}
SCHAD_SHEET_COUNT = 21  # Gate C register: [RB A0.1] index + S4.1 schedules


def check_schad(out_dir: Path) -> list[str]:
    """Schad golden-case pack smoke (Gate D CI guard, WP-SCHAD-S8).

    Basis-drift invariants (areas 2080/1568/224/224 SF within 1%, ridge
    5486.4 mm, 13 strip footings, 6 SSW, 2 W16x40, wood-only wall types)
    are asserted by the pytest CI step — tests/unit/test_schad_areas.py,
    test_schad_sheets.py, test_schad_structure.py, test_schad_types.py.
    This smoke re-checks the pack-level contract on the real output dir:
    VERIFY ok, the full 21-sheet custom register, zero rule/validation
    errors, and zero industrial wall types.
    """
    errors: list[str] = []
    project, verify = build_schad_pack(out_dir)
    print("SCHAD verify:", json.dumps(verify, indent=2))
    if not verify.get("ok"):
        errors.append(f"VERIFY not ok: {verify}")
    idx = json.loads(
        (out_dir / "construction" / "SHEET_INDEX.json").read_text(encoding="utf-8")
    )
    sheets = idx.get("sheets") or []
    if idx.get("register") != "custom" or len(sheets) != SCHAD_SHEET_COUNT:
        errors.append(
            f"expected {SCHAD_SHEET_COUNT} custom-register sheets, got "
            f"{len(sheets)} (register={idx.get('register')!r})"
        )
    rule_errors = [f for f in run_design_rules(project.model) if f["severity"] == "error"]
    if rule_errors:
        errors.append(f"design-rule errors: {rule_errors}")
    validate_errors = [i for i in project.validate() if i["severity"] == "error"]
    if validate_errors:
        errors.append(f"validation errors: {validate_errors}")
    bad_types = {
        el.type_id
        for el in project.model.elements
        if el.category == "wall" and el.type_id in SCHAD_FORBIDDEN_WALL_TYPES
    }
    if bad_types:
        errors.append(f"industrial wall types on Schad walls: {sorted(bad_types)}")
    return errors


def main() -> int:
    out_i = ROOT / "examples" / "output" / "intec"
    out_p = ROOT / "examples" / "output" / "proto10"
    print("Building INTEC…")
    build_intec(out_i)
    print("Building Proto10…")
    build_proto10(out_p)

    vi = verify_pack(out_i, require_parts=True)
    vp = verify_pack(out_p, require_parts=True)
    print("INTEC verify:", json.dumps(vi, indent=2))
    print("Proto10 verify:", json.dumps(vp, indent=2))

    # Read manifests
    for label, path in ("intec", out_i), ("proto10", out_p):
        man = json.loads((path / "MANIFEST.json").read_text(encoding="utf-8"))
        print(f"{label} MANIFEST.ok={man.get('ok')} errors={len(man.get('errors') or [])}")
        if man.get("errors"):
            print(json.dumps(man["errors"], indent=2))

    print("Building SCHAD (golden case)…")
    schad_errors = check_schad(ROOT / "output" / "schad_garage")
    for err in schad_errors:
        print("SCHAD FAIL:", err, file=sys.stderr)

    ok = vi.get("ok") and vp.get("ok") and not schad_errors
    if not ok:
        print("VERIFY FAILED", file=sys.stderr)
        return 1
    print("ALL PACKS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
