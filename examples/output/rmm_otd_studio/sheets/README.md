# MB-OTD drawing package (Rev C cascade — production CAD master)

**Architecture lock:** `docs/RMM_OTD_ARCHITECTURE_LOCK.md` (staged)  
**Geometry SSOT:** `scripts/rmm_otd_geometry_master.py` → `cad/rmm_otd_dims.json`  
**Honesty:** [ENGINEERING ESTIMATE] — configuration / design-basis class; FAB-001 is shop-template only  
**Regenerate:**

```text
PYTHONUTF8=1 PYTHONPATH=. python scripts/rmm_otd_geometry_master.py
PYTHONUTF8=1 PYTHONPATH=. python scripts/generate_rmm_otd_drawing_package.py
PYTHONUTF8=1 PYTHONPATH=. python scripts/generate_rmm_otd_plates.py
```

## Sheet index

| Sheet | Class | Role |
|-------|-------|------|
| MB-OTD-GA-001 | design-basis | General arrangement |
| MB-OTD-DET-001..004 | design-basis | Rotor, magnetic couplings, coil-vessel segment, flux modulators |
| MB-OTD-ASM-001 | process | Assembly sequence |
| MB-OTD-BOM-001 | process | Bill of materials |
| MB-OTD-QA-001 | process | Inspection plan |
| MB-OTD-FAB-001 | **fab** | Bottom end cap (shop-usable template) |
| MB-OTD-FAB-002 | fab | Top end cap |
| MB-OTD-FAB-003 | fab | Central column |
| MB-OTD-FAB-004 | fab | Outer rotor hub ring |
| MB-OTD-FAB-005 | fab | CVT housing ring |
| MB-OTD-FAB-006 | fab | Flux modulator carrier stage B |
| MB-OTD-FAB-007 | fab | Coil-vessel segment flange (×N_SEG) |
| MB-OTD-FAB-008 | fab | Touchdown land ring |
| MB-OTD-PLT-001..004 | pictorial | Assembled / section / exploded / gallery |

**Studio pack:** `python scripts/publish_rmm_otd_studio.py` → `llm-bim/examples/output/rmm_otd_studio/`

## Related (do not mix authorities)

| Path | Authority |
|------|-----------|
| `docs/tier4_drawings/rmm_otd/` | Fusion GO envelope GA from `rmm_otd_basis.json` (architecture A) |
| `docs/RMM_OTD_MULE1_Prototype_Specification.md` | MULE-1 PAIR prototype (architecture B) |
| `cad/fusion/RMM_OTD_Builder/` | Fusion STEP path for envelope |

## Parity gap (vs MineClean studio)

Still needed for full MineClean/Ti-Melt depth: llm-bim `rmm_otd_studio` (STEP parts, BOQ, PLOT_SET, viewer, MANIFEST), remaining FAB sheets, process/vendor specs.
