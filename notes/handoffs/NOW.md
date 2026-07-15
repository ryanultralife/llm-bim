# NOW — active lanes

**Updated:** 2026-07-15 by **Grok** (post output-matrix audit)

## Grok just finished

Full deliverables path audited and implemented:

- `export_deliverables()` → JSON + **IFC** + **glTF** + **STEP** + construction set + part pack  
- INTEC + Proto10 cases regenerate full packs  
- **20 tests passed**  
- Claude still owns deeper IFC/MVD polish if desired; pure IFC works without ifcopenshell  

## Claude when free

| Claim | Notes |
|-------|--------|
| Optional: IFC quality / ifcopenshell round-trip | `packages/ifc/**` — Grok left a working SPF writer; improve fidelity |
| Optional: drawings quality | dimension strings, true wall joins |
| **Do not** rewrite deliverables pack wiring |

Fixtures: `examples/output/intec/`, `examples/output/proto10/`

## Remaining honesty gaps (not claiming done)

- STEP/IFC are **envelope solids**, not Fusion 118-body BREP  
- Construction sheets are agent CD **frames**, not sealed A-E packages  
- No true cylindrical BREP in STEP yet (AABB boxes)  
- No PDF multi-page binder (SVG set only)  
