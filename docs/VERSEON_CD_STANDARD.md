# Verseon CD standard (binding for llm-bim packs)

**Audience:** any agent issuing a construction / coordination set from llm-bim.  
**Evidence class:** REFERENCE BENCHMARK — form and density only. Engineering
numbers stay under `docs/HONESTY.md`. No PE/license is implied.

Ryan 2026-08-12: these four human-produced sets are the **detail bar**. A
pack is not done when it has a sheet count. It is done when a sheet reads
like these.

## Evidence of record (do not copy the PDFs into git)

| Set | Path on Ryan's machine | What to steal |
|-----|------------------------|---------------|
| Architectural V15 Rev 02 | `OneDrive/VM Partners/Verseon/Design/Design Documents/Architectural/17.03.02 _V15_Rev 02/Verseon Arch 3-2 OCR.pdf` | Overlay plans, furniture, room tags, keynotes, 1/8″ work |
| Cogen complete | `…/Cogen/Cogen Final Set/VERSEON_COGEN_Final Complete Set.pdf` | Plan + elev + section **on one sheet**; foundation/roof at 1/4″; 20-up details |
| Mechanical | `…/Mechanical-Plumbing/17.08.29_Verseon_Mechanical.pdf` | Duct size/CFM, equipment tags, screened arch background |
| Plumbing | `…/Mechanical-Plumbing/17.08.29_Verseon_Plumbing.pdf` | Fixture tags, waste/vent, slopes, risers |

Also: Base Takeoff FA-1.0 / FA-1.1 / A-1.8 (furniture + power overlays).

## Sheet composition (the thing INTEC was missing)

1. **One concern per overlay.** Same cut, new annotation set (dim / keynote /
   furniture / MEP / process). Do not dump every trade on the overall.
2. **True architectural scale.** Work plans **1/8″ = 1′-0″** (1:96). Overalls
   **1/16″ = 1′-0″** (1:192) when the envelope will not fit. Details **1/4″ /
   1″ / 3″**. Stated scale = graphic bar = what was drawn. Never fit-stretch
   and keep the old note.
3. **Plan viewport is sized to the building at that scale.** 60 m = 197′ =
   24.6″ at 1/8″. Title block is **3.5″** on a 42″ sheet (wrap titles; do
   not grow the column). **Leftover is a section + notes column**, not
   empty model space.
4. **Two buildings, not two halves of one box** when the program is a hall +
   a yard: process building on one sheet, tank farm / utilities / warehouse
   on the next, match-lined.

## Anatomy that must appear (walk this before "done")

| On every work plan | How |
|--------------------|-----|
| Grid bubbles, 4-side arch / 2-side framing | `grid_sides` |
| 3-tier dims outside the cut (overall / bay / feature) | `dim_tiers` |
| Room **name + boxed number + area** | `room_areas` / C5 |
| Door leaf + swing + **mark** (not a generic "D") | `tags` / engine doors |
| Equipment as a **footprint + leader tag**, keyed to a schedule | `tags` + collapse |
| Keynotes (numbered) + legend in the notes column | `keynotes` |
| North arrow + graphic scale in feet | C2 |
| Key plan of *this* coverage | `key_plan` |
| Match line if the building continues | `match_lines` |
| At least one **section or elevation on the same sheet** when leftover ≥ 8″ | Cogen A-110 |

| On MEP overlays | How |
|-----------------|-----|
| Arch / walls screened (background) | `ghost_walls` |
| Every run sized (`24x12`, `4"`, DN) | route tags |
| Diffusers: CFM. Pipe: slope + invert on underground | M/P targets |
| Equipment tag underlined, leader to the unit | Cogen / M sheets |
| Service key on the sheet that uses the symbols | legend |

| On details | How |
|-----------|-----|
| Self-contained module: title, view, leaders, local notes | E1 / Cogen SD1 |
| Two-way callout (`3 / S-006` ↔ detail header) | `callouts` |
| Hatch + material note on every cut | `hatches` |

## Density law

- Work plan: building fills the plan viewport at the stated scale. Notes
  column is *full* (keynotes, zones, door key, SEE sheet). White space on a
  42×36 is waste.
- Do not stamp W12×230 / window type / every column on an overall. Those
  live on the 1/8″ sheet or the schedule.
- One floor, many overlays > twenty sparse unique plans.

## llm-bim API (turn the standard on)

```python
export_construction_set(
    model, out, units="imperial",
    dim_tiers=True, fractional_grids=True, grid_sides=True,
    room_areas=True, key_plan=True, keynotes=True,
    line_weights=True, hatches=True, stamp_block=True,
)
# overall facility: omit include → auto LOD (span>40 m) drops MEP + W-section text
# work crop: tags=True, room_areas=True, include=architectural or the trade
```

Plan scale: `size_work_plan` / `apply_true_scale` in Eigen
`scripts/intec_sheet_scale.py` (port to llm-bim layout when a pack is a
facility). 1:100 snaps to 1/8″; 1:200 to 1/16″.

## Honesty

`[ENGINEERING ESTIMATE]` on every sheet. Walsh / PE stamp zone stays empty
until a human stamps it. This standard is **how the drawing is assembled**,
not a claim that the plant is permitted.

*[REFERENCE BENCHMARK + ENGINEERING ESTIMATE]*
