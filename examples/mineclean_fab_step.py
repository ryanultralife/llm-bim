#!/usr/bin/env python
"""MB-MCLEAN — per-part machining STEP kernel (llm-bim CAD surface).

The MCAD digital thread pins CAD/BREP generation to llm-bim (engine -> SSOT -> llm-bim
BREP). This is the per-part **machining STEP** kernel: it reads the Eigen SSOT design basis
(`mbclean_basis.json`, parts_mm + geometry_mm) and emits one solid STEP file per engineered
fabricated part via cadquery (OCC B-rep). No dimension is freehanded — every value comes from
the imported basis (CLAUDE.md recursive design loop / DL-MC-005).

Companion to the Eigen 2-D detail sheets (scripts/mbclean_part_details.py) and the dimensioned
fab schedule (scripts/mbclean_fab_details.py). Together: schedule + 2-D detail + 3-D STEP =
released-for-fab per part.

HONESTY: geometry is fab-intent [ENGINEERING ESTIMATE]; STEP solids are nominal (no GD&T,
no weld-prep detail) — a machinist working drawing pairs the STEP with the 2-D detail sheet.

Build:  python examples/mineclean_fab_step.py
Out:    examples/output/mineclean_studio/fab_step/<PN>.step
"""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import cadquery as cq

HERE = Path(__file__).resolve().parent
OUT = HERE / "output" / "mineclean_studio" / "fab_step"

# --- Eigen SSOT basis resolution (branch/checkout-independent) ---------------
# The SSOT `mbclean_basis.json` is CANONICAL on the Eigen `main` branch. The main
# ~/Eigen working tree floats across feature/collab branches, so we do NOT trust its
# working-tree copy — we read the basis straight from git by ref (`git show`). That
# survives whatever branch any checkout happens to be on. Working-tree files are only
# a last-resort fallback for a detached/offline clone.
_REL = "cad/design_basis/mbclean_basis.json"
_NAME = "mbclean_basis.json"


def _eigen_repo() -> Path:
    for c in (HERE.parents[1] / "Eigen", Path.home() / "Eigen"):
        if (c / ".git").exists():
            return c
    return Path.home() / "Eigen"


def _git_show(repo: Path, ref: str) -> dict | None:
    try:
        r = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{_REL}"],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception:
        pass
    return None


def _load_basis() -> dict:
    repo = _eigen_repo()
    for ref in ("origin/main", "main"):                    # canonical, checkout-independent
        b = _git_show(repo, ref)
        if b is not None:
            print(f"[basis] {repo} @ {ref} (git ref — canonical)")
            return b
    # fallback: any working-tree / worktree copy (detached or offline clone)
    cands = [repo / _REL, Path.home() / "Eigen" / _REL]
    _wt = Path.home() / "Eigen" / ".claude" / "worktrees"
    if _wt.exists():
        cands += sorted(_wt.glob(f"*/{_REL}"))
    for c in cands:
        if c.exists():
            print(f"[basis] {c} (working-tree fallback)")
            return json.loads(c.read_text(encoding="utf-8"))
    raise SystemExit(
        f"SSOT basis not resolvable. Tried git refs origin/main, main in {repo}; "
        f"and working-tree copies. Run Eigen scripts/mbclean_design_basis.py + push to main."
    )


def _tube(OD: float, ID: float, L: float):
    return cq.Workplane("XY").circle(OD / 2).circle(ID / 2).extrude(L)


def _disc_with_bolts(OD: float, thk: float, n: int, BC: float, bolt_d: float = 18.0):
    d = cq.Workplane("XY").circle(OD / 2).extrude(thk)
    pts = [(BC / 2 * math.cos(2 * math.pi * i / n), BC / 2 * math.sin(2 * math.pi * i / n))
           for i in range(int(n))]
    return d.faces(">Z").workplane().pushPoints(pts).hole(bolt_d)


def _plate(L: float, W: float, thk: float):
    return cq.Workplane("XY").box(L, W, thk, centered=(True, True, False))


def _boss(OD: float, L: float, bore: float):
    b = cq.Workplane("XY").circle(OD / 2).extrude(L)
    if bore:
        b = b.faces(">Z").workplane().hole(bore)
    return b


def build_all(basis: dict) -> list[tuple[str, object]]:
    g = basis["geometry_mm"]
    parts = basis.get("parts_mm", {})
    out: list[tuple[str, object]] = []

    # --- SSOT geometry_mm parts (pressure/drive core) ---
    out.append(("MB-MC-100-001_chamber_shell",
                _tube(g["chamber_OD"], g["chamber_ID"], g["chamber_L"])))
    out.append(("MB-MC-100-002_end_cap",
                _disc_with_bolts(g["cap_OD"], g["cap_thk"], g["cap_bolt_n"], g["cap_bolt_BC"])))
    out.append(("MB-MC-200-001_rmf_bobbin",
                _tube(g["rmf_bobbin_OD"], g["rmf_bobbin_ID"], g["rmf_bobbin_L"])))

    # --- parts_mm engineered set ---
    for pn, p in parts.items():
        shp = p["shape"]
        nm = f"{pn}_{p['name'].lower().replace(' ', '_').replace('/', '-')}"
        if shp in ("plate",):
            out.append((nm, _plate(p["L"], p["W"], p["thk"])))
        elif shp == "box":
            out.append((nm, _plate(p["L"], p["W"], p["H"])))
        elif shp == "pipe":
            out.append((nm, _tube(p["OD"], p["OD"] - 2 * p["wall"], p["L"])))
        elif shp == "boss":
            out.append((nm, _boss(p["OD"], p["L"], p.get("bore", 0.0))))
    return out


def main() -> None:
    basis = _load_basis()
    OUT.mkdir(parents=True, exist_ok=True)
    solids = build_all(basis)
    for name, solid in solids:
        path = OUT / f"{name}.step"
        cq.exporters.export(solid, str(path))
        print(f"[STEP] {name}.step")
    print(f"\n{len(solids)} per-part STEP solids -> {OUT}")
    print("SSOT: Eigen mbclean_basis.json (parts_mm + geometry_mm). [ENGINEERING ESTIMATE].")


if __name__ == "__main__":
    main()
