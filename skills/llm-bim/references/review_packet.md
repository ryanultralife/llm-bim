# Review packet (post-export visual gate)

Adopted from text-to-cad's mandatory snapshot-review pattern
(see `docs/REFERENCE_TEXT_TO_CAD.md`). After every `export_deliverables`:

## Required open paths (read them)

1. `output/<slug>/index.html` — pack home  
2. `output/<slug>/hero.svg` — baked axonometric still  
3. One plan sheet (e.g. `construction/A1-1_plan.svg` or `views/plan_*.svg`)  
4. One elevation or section if present  

## Convert every visual concern into a check

| You see… | Deterministic check |
|----------|---------------------|
| Blank / empty 3D | `model.gltf` size > 500; re-export; open `viewer3d.html` |
| Missing walls | `p.stats()["wall"]` · query `category=wall` |
| Door not on wall | `validate` / host id · `repair` |
| Wrong size | measure via params / `query` · authoring checklist |
| MEP missing on plan | MEP sheet is plan-kind with include set, not note overlay |
| Clash blobs | `clash` report |

## Done only when

- Pack files exist this session (not an old demo folder)  
- Visual review done (hero + plan at minimum)  
- Every concern either fixed or recorded as `*_assumed` / `Q-` note  
