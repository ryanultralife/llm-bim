# RMM-OTD Architecture Lock — staged (Grok, no-Claude continue)

**Date:** 2026-08-04  
**Authority:** Grok interim lock under Ryan directive *continue without Claude*  
**Honesty:** [ENGINEERING ESTIMATE] throughout  
**Status surface:** `reports/discovery/rmm_otd/COLLAB_STATUS.md`  
**Branch:** `grok/rmm-otd-parity`

---

## Decision (STAGED)

| Stage | Architecture | Authority | Role |
|-------|--------------|-----------|------|
| **MULE-1** | **B — equal counter-rotating PAIR** (Al 7075-T6, Portable R_o=100 mm) | `scripts/rmm_otd_mule1_design_point.py` + `docs/RMM_OTD_MULE1_Prototype_Specification.md` | First physical article; risk retirement only (~49 Wh) — **not** energy demo |
| **Production CAD master** | **C — Rev C nested cascade + magnetic gears + through-wall CVT** | `scripts/rmm_otd_geometry_master.py` → `cad/rmm_otd_dims.json` + OpenSCAD MB-OTD-SCAD-003; multi-sheet package `docs/rmm_otd_drawings/` | Configuration master + design-basis drawings (not fab-complete) |
| **Fusion GO envelope** | **A — 3 coaxial CF shells** (DL-RMM-001…005) | `cad/design_basis/rmm_otd_basis.json` + Fusion `RMM_OTD_Builder` | DRAFTING_RELEASE GO for mass-parity STEP path; **must not** be sold as a second independent machine |

**Single product story:** one mechanical-battery product line (P1).  
MULE-1 proves mechanisms; Rev C is the detailed production configuration master; Fusion nest is the **GO geometry envelope** until a Fusion builder is driven from the geometry master (ECO-RMM-FUSE-001).

---

## Forbidden

| Item | Why |
|------|-----|
| `cylindrical_battery_basis.json` as RMM-OTD | Steel-disc placeholder — HOLD (unchanged) |
| Dual freehand dims in OpenSCAD **and** sheets | Must regenerate from geometry master |
| Claiming `machine_rmm_otd_cf_hoop` as hoop-stress FEM | Operator-MMS only |
| Marketing kWh from VM Partners without engine recompute | See `RMM_OTD_VM_Partners_Reconciliation.md` |

---

## Falsifiers (when to reopen)

1. **MULE-1 AT-4 fails** counter-rotation cancellation → revisit PAIR lock.  
2. **Cascade gear residual** fails magnetic_gear droplet / bench → demote Rev C to concept; fall back to Fusion nest-only product.  
3. **Ryan or Claude countersign** replaces this interim with a dual-agent lock.

---

## Generators (do not confuse)

| Script | Consumes | Produces |
|--------|----------|----------|
| `generate_rmm_otd_drawings.py` | `rmm_otd_basis.json` (A) | tier4 single GA `docs/tier4_drawings/rmm_otd/` |
| `generate_rmm_otd_drawing_package.py` | `cad/rmm_otd_dims.json` (C) | multi-sheet `docs/rmm_otd_drawings/` |
| `generate_rmm_otd_plates.py` | OpenSCAD cascade (C) | PLT-001..004 |

---

## Parity campaign targets (MineClean / Ti-Melt)

- [x] Port multi-sheet + OpenSCAD + MULE-1 + solvers onto tip lineage  
- [x] Architecture lock written  
- [x] Geometry master regenerate green on this branch  
- [x] Guards for dual-authority drift  
- [x] llm-bim `rmm_otd_studio` deliverable classes (scaffold via `publish_rmm_otd_studio.py`)  
- [x] FAB series FAB-001..008  
- [ ] Full BIM solids (llmbim/IFC/glTF) + per-part STEP cascade  
- [ ] Company DR stubs (MULE-1) when Tier-1 available  

---

## Claude

Claude may supersede this lock by answering Q1–Q5 on the Fable channel. Until then, **this file is the working SSOT for the parity campaign.**
