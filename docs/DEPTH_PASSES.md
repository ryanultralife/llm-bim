# Depth passes (complete)

All previously deferred “next depth” items implemented on `main`.

| Pass | Status | How to use |
|------|--------|------------|
| **True cylindrical STEP** | Done | 24-side prism BREP in `export_step` for `shape=cylinder` |
| **PDF plot binder** | Done | `PLOT_SET.pdf` in packs; `llmbim pdf sheets/ --out set.pdf` |
| **Import Fusion STEP** | Done | `llmbim import-step file.step --level L1`; locked equipment + `step_refs/` |
| **CSI cost codes** | Done | BOQ lines include `csi_code` / division rollups |
| **Door/window tags** | Done | Plan tags `D1`, `W1` … |
| **Grid bubbles/lines** | Done | Plan dashed grids |
| **Deeper rules** | Done | ADA door, equip clearance, dual egress, missing STEP ref |
| **Dimension styles** | Done | Plan wall dimensions (m/mm labels) |

## Commands

```bash
# PDF from any SVG sheet folder
llmbim pdf examples/output/intec/construction --out plot.pdf

# Import Fusion STEP (e.g. Proto10)
llmbim import-step path/to/proto10_separator.step --level Bench --out examples/output/fusion_ref

# BOQ with CSI
llmbim boq model.llmbim.json
```

## Honesty

- STEP cylinders are **faceted** (n-gon), not exact NURBS circles.
- PDF binder **vector-approximates** SVG primitives (not pixel-perfect Cairo).
- STEP import stores **bbox envelope + file reference**, not full BREP editability inside llm-bim.
