# Hero product render pipeline

**Audience:** agents and engineers publishing device / skid / structure / facility packs.  
**Goal:** every design pack ships **sheets + specs + 3D** *and* a **pitch-grade product hero still** that matches the quality of the Mechanical Battery field-skid and melt-skid renders.

## Why

| Layer | What it is | Role |
|-------|------------|------|
| Sheets / construction set | Plans, sections, details | Build / review |
| Specs + design basis | Numbers, locks, honesty | SSOT |
| 3D (glTF / STEP / viewer) | Coordination geometry | Review / clash |
| Layout `product_views` | AABB equipment diagrams | Readable layout |
| **Hero product still** | Photoreal communication image | Pitch, NDA, studio cover |

The hero still is **not** fab CAD and **not** a substitute for `hero.svg` (deterministic axonometric). It sits **alongside** them.

## Pack outputs

After `export_deliverables` or `export_hero_pipeline(pack)`:

```
output/<slug>/
  hero.svg                 # deterministic shaded axonometric (existing)
  renders/
    product_hero.jpg       # photoreal hero (staged or library)
    HERO_BRIEF.json        # structured prompt + envelope + locks
    HERO_MANIFEST.json     # status ready | needs_render
    R1_iso.png …           # layout product_views (existing)
  index.html               # features product_hero when present
  viewer3d.html
  construction/ | sheets/
  model.gltf · model.step · …
```

## API

```python
from llmbim_drawings.hero_product import (
    export_hero_pipeline,
    build_hero_brief,
    stage_hero_render,
    find_library_hero,
)

# On any pack directory:
man = export_hero_pipeline(
    "output/my_skid",
    product_id="mineclean",   # maps to docs/renders/mineclean/
    kind="skid",              # device | skid | structure | facility
    title="MineClean field skid",
    use_library=True,         # auto-stage from docs/renders/<id>/
)

# After generating a still externally (Imagine / Midjourney / etc.):
stage_hero_render("output/my_skid", "path/to/new_hero.jpg")
```

Also wired into **`export_deliverables`** automatically (best-effort; never fails the pack).

## Library stills (committed)

| Product | Path |
|---------|------|
| MineClean | `docs/renders/mineclean/field_skid_hero.jpg` |
| INTEC facility | `docs/renders/intec/hero.jpg` (also Eigen `docs/renders/intec/`) |
| (Eigen mirror) | `Eigen/docs/renders/{mineclean,mb_ti_melt,rmm_otd,intec}/` |

`export_hero_pipeline(..., use_library=True)` searches **llm-bim** and sibling
**Eigen** `docs/renders/` (plus `EIGEN_ROOT` / `LLMBIM_RENDER_LIBRARY`). Product
ids like `intec_fp_separation_facility` normalize to `intec`.

**Export order (fixed):** product_views → hero pipeline → `write_pack_index`,
so `index.html` features `product_hero` when the library stages successfully.

## Agent / Imagine step (when status = needs_render)

1. Open `renders/HERO_BRIEF.json`.
2. Use `prompt` (and envelope / equipment tags) with an image model.
3. Prefer **image_edit** from pack **3-D / mesh-match views first** (honest massing):
   - `renders/model_match_iso_full.png` or `model_match_iso.png`
   - `renders/L1_layout_iso.png` / `R1_iso.png`
   - elev sheets (`R3_elev*.png`) or construction elev thumbs
   - List via `preferred_img2img_refs(pack)` — do **not** invent a generic plant.
4. Save the result and run `stage_hero_render(pack, path)`.
5. Re-open `index.html` — product hero is the cover.

Quick stage from an existing pack view (no Imagine):

```python
from llmbim_drawings.hero_product import stage_hero_from_pack_views
stage_hero_from_pack_views(pack, prefer="model_match_iso_full")
```

Prompt language should match brand stills: cream/copper industrial, full-frame subject, no logos/text, no people.

## Honesty

- Hero stills: **ENGINEERING ESTIMATE** communication assets.  
- Geometry / performance: design basis + pack model only.  
- Never claim G5 / field demonstration from a still.

## Recipe

`skills/llm-bim/recipes/hero_product_render.md`
