# Schad: Revit → llm-bim transition review

**Audience:** Claude (primary implementer), Grok, or any agent.  
**Status:** OPEN — work until Gates A–D resolve; close this review when Gate D is signed.  
**Human directive (2026-07-19):** *Transition away from Revit to our own llm-bim at the same or better quality and execution.*  
**Not a PE seal.** Designer CD quality + agent-regenerable pack. Structural PE remains human.

Related: `HONESTY.md` · `CAPABILITY.md` · `VISION.md` · `OUTPUT_MATRIX.md` · `EQUIPMENT_3D_AND_DEVICE_SSOT.md` (SSOT pattern) · `examples/schad_garage.py` · `notes/handoffs/NOW.md` · `docs/WORK_PACKAGES.md` (WP-SCHAD-*) · `docs/RETIRING_REVIT_SCHAD.md` (Gate D decision record) · `skills/llm-bim/recipes/schad_cd.md` (rebuild recipe)

---

## 1. Summary

Schad Phase 1 (Garage / ADU / Workshop, Ledger Built **2024-008**, 3730 Chandler Rd, Quincy CA) has a mature **pure-Python design basis** and a **Revit digital thread** that already produces a ~20-sheet DD set. llm-bim has a **shell consumer** (`examples/schad_garage.py` → `output/schad_garage/`) that is **coordination-grade only** and **lies about wall types** (CMU industrial catalog).

**Decision:** llm-bim becomes the sole authoring host. Revit adapters and `.rvt` files become **archive / visual regression** after Gate D. The basis modules never retype numbers — they move into this repo as SSOT.

**Win condition:** one command rebuilds a pack meeting `docs/CD_COMPLETENESS_STANDARD.md` (professional doc-set anatomy, exemplar-calibrated) for Phase 1 — roofs, wood assemblies, foundations, S-details, full sheet register — with open formats, model VCS, and agent API. Revit is the data source being retired, not the benchmark.

---

## 2. Current state (evidence)

### 2.1 Revit thread (further along on CD graphics)

| Location | Role |
|----------|------|
| `G:\My Drive\Schad Garage\Revit\schad_design_basis.py` | Imperial SSOT (scalars, walls, doors, structure, rooms, notes, open_questions) |
| `schad_structural.py` / `schad_mep.py` / `schad_site.py` / `schad_adu.py` / `schad_details.py` / `schad_house_basis.py` | Portable domain modules |
| `schad_revit_bridge.py` → `schad_revit_model.json` | Transform only (ft→m + solids) |
| `Schad_*.py` (Builder, Polish, Annotate, Details_Render, TechDocs, Headless, …) | **Revit-only** — do not port |
| `sheet_renders/` (~20 PNGs) | Visual benchmark for Gate C/D |
| `model_qa/` | Roof/footing QA shots (valley, curb, eave) |
| Local `.rvt` | `C:\Users\ryanv\MechanicalBattery\SchadWork\` |

### 2.2 llm-bim pack today

| Item | Value |
|------|--------|
| Script | `examples/schad_garage.py` (loads basis via `SCHAD_ROOT` / G: path) |
| Pack | `output/schad_garage/` — VERIFY file-complete |
| Elements | ~59: 16 walls, 6 doors, 4 windows, 6 rooms, 2 beams, 11 equipment (SSW+mech boxes), 13 notes, 1 slab |
| Sheets | **11 generic** G/A only (not Schad A0.1…S3.x register) |
| Wall types | **Wrong:** `W-EXT-CMU` / `W-INT-GYP` (industrial), not 2×6 BnB / 1-hr wood |
| Roofs | **Missing** (Ridge level is a datum name only) |
| Foundations | **Missing** (single slab polygon) |
| Connections | empty |
| Clashes | ~68 AABB noise + real overlaps |
| Rules | WALL_EXCEEDS_STORY errors (Bay 2 14′ / fire wall 12′ vs 10′ story — multi-plate real condition) |

### 2.3 Program facts (resolved — do not re-litigate)

- Main 48′ × 32′; Bay 2 +2′ south; rear ADU 14′ + workshop 18′ × 16′  
- Areas: 2080 total / 1568 garage / 224 ADU / 224 workshop published  
- Plates: main 10′, Bay 2 14′, rear high 12′ / low 10′; ridge 18′; pitch 6:12; overhang 18″  
- Mech/Bath 9′×12′ in Bay 3 NE (boilers propane, tankless DHW, 60-gal PT-1)  
- Structure: W16x40 ×2, SSW24x9 ×4 + SSW24x12 ×2, snow 75 psf  
- Finishes: 5/8″ DF board-and-batten structural siding; standing-seam charcoal  
- C1.1 site composition **user-approved as-is** (survey still required for setbacks)

### 2.4 Open questions still blocking “print CDs”

| ID | Blocks |
|----|--------|
| Q-SETBACK | Site legality — survey + Plumas zoning |
| Q-LOC | D4–D6 / W1–W4 positions assumed |
| Q-WIN | Schedule mix RB vs BOM |
| Q-SHED / Q-BAY2ROOF | Confirm before freezing elevations |
| Q-SHTG | Memo governs 5/8 DF over OSB note |
| Q-HANDOFF10 | Owner finishes |

Software can proceed to Gate C with open Qs **flagged on sheets**; Gate D “retire Revit” does not require PE or closed setbacks, but pack must remain **NOT FOR CONSTRUCTION** until human checklist.

---

## 3. Gap matrix (Revit CD intent vs llm-bim)

| Domain | Exists in kernel | Schad pack uses it correctly? | Work needed |
|--------|------------------|-------------------------------|-------------|
| Plan shell (walls, rooms, grids, openings) | Yes | Partial | Fix types; imperial dims |
| Wall assemblies / `set_type` | Catalog of 4 industrial types | **No** | Residential registry + Schad types |
| Roof planes / valleys / eaves | **No** | No | **WP-SCHAD-S2** domain ops |
| Footings / stem / dual slabs | Slab only | No | **WP-SCHAD-S3** |
| Beams / columns | Yes | Beams only; W16x40 not in catalog list | Posts + W16x40 + headers |
| Shear / SSW | Equipment boxes | Envelopes only | Typed shear + schedule |
| Rebar | place_part + takeoff | Unused | Footing #4 + marks |
| Framing / studs | Catalog BOM proxies | Unused | Header + stud takeoff estimate |
| Connections | ports/modules API | Empty | Structural marks + MEP ports |
| Sheet register custom | Fixed A-101… | Wrong titles | Configurable sheets |
| Details 2D ops DSL | **No** (fab GD&T only) | 12 details exist in Schad pure Python | Detail SVG renderer |
| Site / ADU enlarge / MEP symbols | Partial generic | No | Content port WP-SCHAD-S6 |
| BOQ truth | Yes but wrong types | **Lies** | Fix after S1 |

---

## 4. Target architecture

```text
projects/schad/                 # SSOT ported from G:\…\Revit pure modules
  design_basis.py
  structural.py  mep.py  site.py  adu.py  details.py  house_basis.py
  generate_docs.py
  tests/

examples/schad_build.py         # basis → Project → export_deliverables
        │
        ▼
kernel: wall types · roofs · footings · headers · shear · sheet register · detail SVG
        │
        ▼
output/schad_garage/            # CD pack + .llmbim/versions VCS

ARCHIVE (after Gate D): G:\…\Revit\*.rvt + Schad_* adapters (read-only)
```

**Invariant:** never retype dimensions in chat or in kernel examples. Basis is the only number source.

---

## 5. Quality gates (same or better than Revit)

### Gate A — Honest massing
- [x] Roofs in mesh + elev + section (main gable, Bay-2 cross-gable/valley, shed, 18″ overhang) — S2 kernel `llmbim_core/roofs.py`; `tests/unit/test_roof_planes.py` (glTF mesh, elev silhouette, section slopes, IFC) + `test_schad_sheets.py::test_roofs_placed_ridge_18ft`
- [x] Wood wall types (not CMU); 1-hr fire sep correct — S1 registry; `tests/unit/test_schad_types.py` (zero industrial types, W-1HR-GAR-ADU on the separation)
- [x] Dual slabs + strip footings + stem — S3 kernel `llmbim_core/foundations.py`; `tests/unit/test_schad_sheets.py` (13 F1 strips, 4 F2 pads, 12 stems, SOG-4/SOG-3)
- [x] W16x40 + HSS posts + typed SSW — S4 catalogs; `tests/unit/test_schad_structure.py` (2 beams, 4 posts, 4+2 SSW typed)
- [x] Areas drift tests: 2080 / 1568 / 224 / 224 — `tests/unit/test_schad_areas.py` (published pins + model rooms within 1 %)
- [x] Pack VERIFY ok — `test_schad_sheets.py::test_pack_verify_ok_with_calc_docs_and_history` + `scripts/verify_all.py`

### Gate B — Structure + details
- [x] S1.1 foundation plan (footings, pads, rebar marks, notes from structural module) — `build_llmbim._foundation_plan_view` renders placed F1/F2/stems/slabs + carried rebar/AB notes + strip check
- [x] S2.1 roof framing / bearing / deferred truss notes — `projects/schad/svg_plans.roof_framing_svg` (ridge, trusses 24″ OC, W16x40, basis framing notes, deferred-submittal note)
- [x] S3.1–S3.3 details D01–D12 from ops DSL (4-up) — S5 renderer; `test_detail_ops.py` + `test_schad_sheets.py::test_details_sheets_carry_d01_to_d12`
- [x] Header schedule at OH doors (HDR-1, HDR-2 LVL) — `test_schad_structure.py::test_schad_headers_placed_at_basis_openings` (HDR-2 at 12′ OH doors); schedule carried in pack `docs/STRUCTURAL_CALCS.md`

### Gate C — Full 20-sheet register
**Status: met (S6)** — 21-sheet custom register ([RB A0.1] index + S4.1 schedules) built by `projects/schad/build_llmbim.py`; `test_schad_sheets.py::test_pack_emits_full_gate_c_sheet_files` + `scripts/verify_all.py` assert the register.  
A0.1, C1.1, A1.1, A1.2, A2.1, A2.2, A3.1, A4.1, S1.1, S2.1, S3.1–S3.3, MEP-101/201/301, H1.1–H2.2  
Plus generated `STRUCTURAL_CALCS.md` / `MEP_CALCS.md` / `SPECIFICATIONS.md` in pack.  
BOQ/CSI reflects wood building.

### Gate D — Better execution than Revit (retire seat)
- [x] `python examples/schad_build.py` (or `llmbim case schad`) rebuilds all — S8 golden command in `llmbim_cli`; `tests/unit/test_cli_case_schad.py`
- [x] Model VCS commits after basis changes — staged commits per build phase in `build_pack`; `test_pack_verify_ok_with_calc_docs_and_history` asserts history + clean tree
- [x] CI: basis drift + pack smoke + wall type ≠ CMU — `scripts/verify_all.py::check_schad` (VERIFY ok, 21 sheets, zero rule errors, zero industrial wall types) + pytest drift suites (`test_schad_areas/sheets/structure/types`) + `llmbim case schad` workflow step, all in `.github/workflows/ci.yml`
- [x] Recipe: `skills/llm-bim/recipes/schad_cd.md`
- [x] Doc: Revit archived; no edit path via `.rvt` — `docs/RETIRING_REVIT_SCHAD.md` (decision record; archive final on human sign-off)
- [ ] Human review of the pack against `docs/CD_COMPLETENESS_STANDARD.md` — **pending**; until signed, the review stays OPEN. (Reframed from Revit side-by-side: the benchmark is professional doc-set anatomy — Sierra Star / Verseon calibration — not the old tool's renders, which remain available as reference only.)

**“Better”** = regenerate in minutes, no dual Revit licenses, open formats, true versions, agent undo — not prettier families on day one.

---

## 6. Work packages (claim in TEAM_STATUS; one at a time preferred)

See `docs/WORK_PACKAGES.md` **WP-SCHAD-*** series.

| ID | Name | Freeze (approx) | Depends |
|----|------|-----------------|---------|
| **WP-SCHAD-S0** | SSOT in-repo + build harness | `projects/schad/**`, `examples/schad_*.py` | — |
| **WP-SCHAD-S1** | Residential wall/door/window types | `types_catalog.py`, `annotations.py` set_type | S0 |
| **WP-SCHAD-S2** | Roof planes + elev/section | core roof cmds, mesh, section/elev | S0 |
| **WP-SCHAD-S3** | Foundation + rebar marks | footing ops, slab split, foundation plan | S0 |
| **WP-SCHAD-S4** | Headers, posts, shear panels, W16x40 | assignment/catalog/structure | S1 |
| **WP-SCHAD-S5** | Configurable sheets + detail SVG | `construction.py`, new detail renderer | S0 |
| **WP-SCHAD-S6** | ADU / site / MEP / house sheet content | schad modules + drawings | S5 |
| **WP-SCHAD-S7** | Sierra-Star annotation (imperial dims, tags) | plan/sheets | S5 |
| **WP-SCHAD-S8** | Golden case, CI, recipe, retire Revit doc | cli case, tests, skill recipe | A–C |

Recommended order: **S0+S1 → S2+S3 → S4+S5 → S6+S7 → S8**.

---

## 7. Platform APIs to add (concrete)

### 7.1 Types (`types_catalog.py`)
```python
register_wall_type(WallType(...))  # or project-level registry
# Ship:
# W-EXT-2x6-BNB, W-INT-2x4, W-1HR-GAR-ADU
# D-OH-12x9, D-OH-12x12, D-SC-36-ADA, D-HM-30
# WIN-CASE-48x48 (U=0.30)
```
`set_type` must sync `thickness_mm` + `wall_layers` for registered types (already does for `DEFAULT_WALL_TYPES` — extend that map).

### 7.2 Roofs
```python
p.create_gable_roof(level=..., footprint=..., ridge_y=..., plate_mm=..., pitch=0.5, overhang_mm=...)
p.create_shed_roof(...)
p.create_roof_plane(...)  # low-level
# Bay-2 valley: two planes or boolean-capable massing
```
Mesh + elevation silhouette + section cut required. IFC: IfcRoof or generic solid with category `roof`.

### 7.3 Foundation
```python
p.create_footing(kind="strip"|"pad", polygon|center, width_mm, depth_mm, ...)
# rebar marks via place_part(bar_size="4", ...) + schedule
```

### 7.4 Sheets + details
```python
export_construction_set(model, out, sheets=[{no, title, kind, ...}])
render_detail_ops(ops, scale=...) -> SVG  # ops: l/d/r/c/h/t in local feet
```
Detail DSL already defined in Schad `schad_details.py` — port renderer only.

### 7.5 Multi-plate rules
`WALL_EXCEEDS_STORY` should respect per-wall height / plate levels (Bay 2 14′, fire wall 12′) instead of false errors against L1 10′ clear.

---

## 8. What not to do

- Do **not** port `Schad_Revit_Builder.py` / pyRevit / UIA / dual-session hacks  
- Do **not** keep editing `.rvt` as SSOT  
- Do **not** invent dimensions in chat — only basis  
- Do **not** claim PE / code stamp  
- Do **not** map Schad walls to `W-EXT-CMU` after S1  
- Do **not** treat empty `connections.json` as done  
- Do **not** start full Phase 2 house BIM before Gate D on Phase 1  

---

## 9. Portable SSOT port checklist (S0)

Copy from `G:\My Drive\Schad Garage\Revit\` (pure modules only):

- [ ] `schad_design_basis.py` → `projects/schad/design_basis.py`  
- [ ] `schad_structural.py`, `schad_mep.py`, `schad_site.py`, `schad_adu.py`, `schad_details.py`, `schad_house_basis.py`  
- [ ] `generate_schad_docs.py`  
- [ ] Drift tests from `test_schad_bridge.py` (areas, sheet count) retargeted to llm-bim  
- [ ] Optional: keep G: as sync source; **repo is CI source of truth**

---

## 10. Acceptance tests (minimum)

```text
tests/unit/test_schad_types.py     — Schad walls use wood types; fire sep 1-hr
tests/unit/test_schad_areas.py     — room/zone areas match basis
tests/unit/test_roof_planes.py     — roof solid in mesh/export
tests/unit/test_detail_ops.py      — D01 SVG non-empty
tests/wp/test_schad_pack.py        — case schad → 20 sheet files + VERIFY
```

Manual: open `viewer3d.html` — pitched roof visible; elev S shows three OH doors + Bay-2 gable.

---

## 11. Claude operating protocol

1. Read this doc + `notes/handoffs/NOW.md` + claim one **WP-SCHAD-S\*** in `TEAM_STATUS.md`.  
2. Implement platform feature + update `examples/schad_build.py` (or evolve `schad_garage.py`) in the **same PR** so the fixture never lags.  
3. Run: `ruff check .` · `mypy` · `pytest` · rebuild pack · print OPEN_* paths.  
4. Update Gate checkboxes in this file (or WORK_PACKAGES status) when a gate criterion lands.  
5. Leave handoff in `notes/handoffs/` when stopping.  
6. **Work until Gate D** or human redirects — this review stays open.

Freeze courtesy: avoid stomping unrelated claims; Schad WPs own types/roofs/foundations/sheets/details as listed.

---

## 12. Grok / launch lane

- Do not block Claude on Schad domain work.  
- Help with CLI `llmbim case schad`, CI wiring, server export routes if needed.  
- Review PRs for honesty stamps and VERIFY.

---

## 13. Resolution criteria (close this review)

All of:

1. Gates A–D checkboxes complete (or waived in writing by human).  
2. `llmbim case schad` / `examples/schad_build.py` green on CI.  
3. Pack wall types are wood; roofs visible; ≥20 Schad-titled sheets.  
4. `docs/LOCAL.md` or recipe documents rebuild without Revit.  
5. Human: “Revit not required for Phase 1 regeneration.”

Until then: **status remains OPEN.**

---

## 14. Appendix — sheet register (target)

| No | Title |
|----|--------|
| A0.1 | Cover & site summary |
| C1.1 | Site plan |
| A1.1 | Floor plan |
| A1.2 | ADU enlarged ADA plan |
| A2.1 | Elevations S & N |
| A2.2 | Elevations E & W |
| A3.1 | Building sections |
| A4.1 | Door & window schedules |
| S1.1 | Foundation plan |
| S2.1 | Roof framing plan |
| S3.1–S3.3 | Structural details |
| MEP-101 | Electrical |
| MEP-201 | Plumbing |
| MEP-301 | Mechanical |
| H1.1 / H1.2 | Existing house |
| H2.1 / H2.2 | Remodel scope / concept |

---

*Authored 2026-07-19 by Grok from live Schad basis audit + llm-bim capability review. Human directive: full transition off Revit.*
