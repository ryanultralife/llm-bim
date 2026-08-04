# Recipe — hero product still (device / skid / structure / facility)

Use when publishing a machine, skid, structure, or facility pack and you need a **pitch-grade product hero** next to sheets, specs, and 3D.

## Outcome

Pack `index.html` shows a full-width **product_hero** still.  
`renders/HERO_BRIEF.json` + `HERO_MANIFEST.json` document how it was produced.

## Steps

1. **Build the engineering pack** (normal path)
   ```python
   man = p.export_deliverables()  # or studio publisher
   pack = man["output_dir"]       # output/<slug>/
   ```
   This already emits sheets, 3D, `hero.svg`, layout `product_views`, and runs `export_hero_pipeline`.

2. **Check hero status**
   ```python
   import json
   from pathlib import Path
   pack = Path("output/my_pack")
   man = json.loads((pack / "renders/HERO_MANIFEST.json").read_text(encoding="utf-8"))
   print(man["status"], man.get("product_hero"), man.get("source"))
   ```
   - `ready` + library/explicit source → done for decks.
   - `needs_render` → generate still from brief.

3. **Generate (if needed)**  
   Read `renders/HERO_BRIEF.json` → `prompt`.  
   Prefer image-to-image from:
   - existing `renders/R1_iso.png` / layout view, or
   - STEP silhouette / prior product photo  
   Keep massing honest; cream/copper industrial product photography; no text/logos.

4. **Stage**
   ```python
   from llmbim_drawings.hero_product import stage_hero_render, export_hero_pipeline
   stage_hero_render(pack, "path/to/hero.jpg")
   export_hero_pipeline(pack, product_id="mineclean", use_library=False)  # refresh manifest
   ```

5. **Hand over** one path: `output/<slug>/index.html`.

## Kind selection

| Kind | Use |
|------|-----|
| `device` | Single machine / vessel |
| `skid` | Process skid, melt island, ISO package |
| `structure` | Frames, cells, support steel |
| `facility` | Whole plant / campus exterior |

## Do not

- Composite unaligned STEP + bay screenshots (see EQUIPMENT_3D).  
- Replace fab sheets with a still.  
- Claim performance grades from a render.

## Library

Committed stills: `docs/renders/<product>/` (e.g. MineClean `field_skid_hero.jpg`).
