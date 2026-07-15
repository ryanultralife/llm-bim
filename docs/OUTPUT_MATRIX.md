# Output matrix — audit vs target

**Audit date:** 2026-07-15  
**Goal:** Parts (3D / 2D / STEP) + Facilities (3D / BIM / construction drawings)

## Status legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented and tested |
| 🟡 | Partial / engineering estimate quality |
| ❌ | Missing |

## Facilities & buildings (INTEC, houses)

| Deliverable | Format | Status | Module |
|-------------|--------|--------|--------|
| Semantic BIM model | `.llmbim.json` | ✅ | `llmbim_core` |
| Industry BIM interchange | IFC4 `.ifc` | ✅ pure SPF writer | `llmbim_ifc` |
| 3D review mesh | glTF | 🟡 walls + equipment boxes | `llmbim_geometry.mesh` |
| 3D solid exchange | STEP AP203 | ✅ boxes/cylinders assembly | `llmbim_geometry.step_export` |
| Floor plan | SVG | ✅ | `llmbim_drawings.plan` |
| Section / elevation | SVG | 🟡 basic | `llmbim_drawings.section` |
| Construction sheet set | multi SVG + index | ✅ | `llmbim_drawings.construction` |
| Schedules | CSV/JSON | ✅ | `llmbim_drawings.schedules` |
| Dimensions / tags / title block | | 🟡 title block + sheet frames | construction sheets |
| True wall joins / layered walls | | ❌ | future |

## Parts / equipment (Proto10 separator)

| Deliverable | Format | Status | Module |
|-------------|--------|--------|--------|
| Part envelopes in BIM | equipment boxes | ✅ | commands |
| Part 2D drawing pack | SVG GA + views | ✅ | `llmbim_drawings.parts` |
| Part / assembly STEP | STEP | ✅ | step_export per equipment + assembly |
| Full Fusion body fidelity (118 solids) | | ❌ | import STEP later; not authoring kernel |
| Machining drawings w/ GD&T | | ❌ | future |

## One-shot pack

```text
Project.export_deliverables(out_dir)
→ model.llmbim.json
→ model.ifc
→ model.gltf
→ model.step
→ drawings/  (construction or part pack)
→ schedules/
→ MANIFEST.json
```

## Honesty

Geometry is **parametric BIM + solid envelopes**, not a replacement for Fusion BREP detail or Revit CD packages. Suitable for agent-driven layout, coordination, and exchange; refine in domain CAD for fabrication.