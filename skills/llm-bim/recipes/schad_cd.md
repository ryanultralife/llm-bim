# Recipe: Schad Phase 1 CD set (Garage / ADU / Workshop, 2024-008)

Rebuild the full 21-sheet Schad CD pack — no Revit involved.

## Golden command

```bash
llmbim case schad                 # → output/schad_garage/
llmbim case schad --out out/dir   # non-default target
```

Exit is non-zero if pack VERIFY fails. Python API (same build):

```python
from examples.schad_build import build_schad_pack
project, verify = build_schad_pack()          # default output/schad_garage/
assert verify["ok"], verify
```

Model-only (no export — what the unit tests use):
`from examples.schad_build import build_schad_model`.

## Where the numbers live (SSOT)

`projects/schad/schad_design_basis.py` is the **only** number source
(plus `schad_structural.py` / `schad_mep.py` / `schad_site.py` /
`schad_adu.py` / `schad_details.py` / `schad_house_basis.py`).
The harness is `projects/schad/build_llmbim.py`. **Never retype dimensions**
in chat, kernel code, or sheets — read them from the basis. Values the record
does not fix carry explicit `*_assumed` flags in the model.

## Honesty rules

- Every pack is stamped `[DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION]`.
- No PE / code-compliance claims; structural PE is human and reserved.
- Open questions (Q-SETBACK, Q-LOC, Q-WIN, Q-SHED, Q-BAY2ROOF, …) stay
  flagged on sheets and in `schad_basis_snapshot.json` — never silently resolve.
- No Schad wall may carry an industrial type (`W-EXT-CMU` / `W-INT-GYP`) —
  guarded by `tests/unit/test_schad_types.py` and `scripts/verify_all.py`.

## To modify the design

1. Edit the basis module (e.g. `schad_design_basis.py`) — nothing else.
2. Rebuild: `llmbim case schad` (model VCS commits are staged automatically).
3. Gates: `python -m pytest tests/unit/test_schad_*.py tests/unit/test_cli_case_schad.py -q`
   then `python scripts/verify_all.py`. Drift guards (areas 2080/1568/224/224 SF,
   ridge 18', 13 strip footings, 6 SSW, 2 W16x40) fail loudly if the basis and
   model diverge.

## Output contract

Hand the user **exactly one path**: `output/schad_garage/index.html`
(3D viewer, PLOT_SET.pdf, all 21 sheets, schedules, calc docs are linked
from it). Reference: `docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md` and
`docs/RETIRING_REVIT_SCHAD.md`.
