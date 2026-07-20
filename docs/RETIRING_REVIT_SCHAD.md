# Retiring Revit for Schad Phase 1 — decision record

**Project:** Schad Garage / ADU / Workshop, Ledger Built 2024-008, 3730 Chandler Rd, Quincy CA
**Directive (human, 2026-07-19):** *Transition away from Revit to our own llm-bim at the same or better quality and execution.*
**Governing review:** `docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md` (Gates A–D)
**Stamp:** every regenerated pack is **[DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION]**.

## Decision

llm-bim is the sole authoring host for Schad Phase 1. The design basis lives
in this repo (`projects/schad/`) and is the only number source. The Revit
thread (`G:\My Drive\Schad Garage\Revit\` adapters, local `.rvt` files) is
**archived**: it is kept read-only as a visual-regression benchmark
(`sheet_renders/`, `model_qa/`), and there is **no edit path via `.rvt`** —
design changes are made in the basis modules and regenerated here.

Archive status is *conditional until Gate D signs*: the final criterion —
human review of this pack against `docs/CD_COMPLETENESS_STANDARD.md`;
the last Revit
`sheet_renders/` set — is still pending (see Residual gaps). Until the human
signs "Revit not required for Phase 1 regeneration", the `.rvt` archive
remains the visual benchmark of record.

## What replaced each Revit function

| Revit function | llm-bim replacement | Evidence |
|---|---|---|
| Model authoring (`.rvt`, Schad_Builder/pyRevit adapters) | `projects/schad/build_llmbim.py`: basis → kernel (walls/openings/rooms, roofs, foundations, structure, MEP content) | `tests/unit/test_schad_types.py`, `test_schad_areas.py`, `test_schad_sheets.py`, `test_schad_structure.py` |
| Wall/door/window families | Residential type registry (`llmbim_core/types_catalog.py`): W-EXT-2x6-BNB / W-INT-2x4 / W-1HR-GAR-ADU, D-OH-\*, D-SC-36-ADA, D-HM-30, WIN-CASE-48x48 | `test_schad_types.py` — zero CMU/industrial types |
| Roofs | `llmbim_core/roofs.py` gable/shed/plane ops — main 6:12 gable ridge 18', Bay-2 cross-gable with valleys, rear shed | `test_roof_planes.py`, `test_schad_sheets.py` |
| Foundations | `llmbim_core/foundations.py` — F1 strips 18"x12", F2 pads 36"x36"x30", S1/S2 stems, dual slabs 4"/3", rebar schedule | `test_foundations.py`, `test_schad_sheets.py` |
| Structure | W16x40 + HSS posts + HDR-1/HDR-2 headers + typed SSW panels from catalogs; multi-plate rule fix | `test_schad_structure.py` |
| Sheet set (~20 PNG renders) | Gate C custom register — 21 SVG sheets (A0.1…H2.2 per [RB A0.1] index + S4.1) + `PLOT_SET.pdf` | `test_schad_sheets.py`, `scripts/verify_all.py` |
| Schedules | Door/window (A4.1), shear-wall + rebar (S4.1), header schedule in `docs/STRUCTURAL_CALCS.md`, BOQ/CSI takeoffs | `test_schad_sheets.py`, `test_schad_structure.py` |
| 2D details | Detail-ops DSL renderer — D01–D12 from `schad_details.py`, 4-up on S3.1–S3.3 | `test_detail_ops.py`, `test_schad_sheets.py` |
| 3D views | glTF mesh + `index.html` 3D viewer (roofs, structure, equipment visible) | pack `viewer3d` via `index.html` |
| Version history (Revit saves) | True model VCS — staged commits per build phase, `p.diff()`/`p.log()`/`p.checkout()` | `.llmbim/versions/` in the pack; `test_cli_case_schad.py` |
| Imperial annotation | WP-SCHAD-S7 imperial dims + tag bubbles on register sheets | `test_imperial_dims.py`, register `units: "imperial"` |

## One-command rebuild

```bash
llmbim case schad          # → output/schad_garage/index.html, exit != 0 if VERIFY fails
```

(equivalent: `python examples/schad_build.py`). Runs in under a minute on a
laptop; regenerates model, VCS history, all 21 sheets, PDF binder, schedules,
calc docs, and `VERIFY.json`. CI rebuilds and gates it on every push
(`scripts/verify_all.py` + the pytest drift guards + the
"Schad golden command" workflow step). Recipe:
`skills/llm-bim/recipes/schad_cd.md`.

## What is deliberately NOT claimed

- **No PE stamp, no code-compliance calcs.** Structural PE remains human and
  reserved; calc docs are design-support only. Geotech, survey/setbacks
  (Q-SETBACK) and truss engineering (deferred submittal) are by others.
- **Not construction documents.** Every sheet and doc carries
  [DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION]; the pack stays that way until
  the human checklist clears.
- **Not day-one graphic parity with Revit families.** "Better" here means
  regeneration in seconds, no license, open formats, true model versions and
  an agent API — not prettier linework on day one.
- **Open questions are not resolved by the transition** (Q-LOC positions,
  Q-WIN mix, Q-SHED/Q-BAY2ROOF roof confirmations, Q-HANDOFF10): they remain
  flagged on sheets and in `schad_basis_snapshot.json`.

## Residual gaps

1. **Human QA pending** — this pack reviewed against
   `docs/CD_COMPLETENESS_STANDARD.md` (professional doc-set anatomy;
   Sierra Star / Verseon calibrated). Reference only: the last Revit
   `sheet_renders/` set (Gate D final checkbox). Until reviewed and signed,
   the `.rvt` archive stays authoritative for visual comparison.
2. Values the record does not fix remain flagged `*_assumed` in the model
   (stem height/frost depth from drawn D01, equipment massing sizes, SSW
   stations) — EOR to confirm.
3. G:-drive basis copies remain as a sync source only; the repo is the CI
   source of truth (`examples/schad_garage.py` kept for local G: sync use).

## Decision record

- Authoring host: **llm-bim** (`projects/schad/` SSOT + kernel).
- Revit: **archive / visual regression only; no edit path via `.rvt`.**
- Rebuild: `llmbim case schad` — one command, CI-gated.
- Close-out: on the human sign-off "Revit not required for Phase 1
  regeneration" (transition review §13), the review closes and the archive
  becomes final.
