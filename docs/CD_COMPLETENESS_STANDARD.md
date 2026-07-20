# CD Completeness Standard — what "a real set of documents" means

The acceptance bar for any deliverable set produced with llm-bim. Calibrated
against two professional, human-produced construction-document sets supplied
as references — **not** against any authoring tool:

- **Sierra Star** — 1532 Sierra Star residence, Incline Village NV (Ryan Group
  Architects; CFBR Structural, PE/SE stamped). Top-tier residential CD detail.
- **Verseon** — pharmaceutical lab building, full multi-discipline CD set
  (A/S/M/P/E/FP/LV/doors). The lab/industrial analog with heavy MEP + process.

Evidence class: **[REFERENCE BENCHMARKS]** for drawing detail and anatomy —
never for engineering claims, which stay governed by `docs/HONESTY.md`.

---

## 1. Universal sheet anatomy (every model-derived plan/section)

| Element | Reference behavior | llm-bim status |
|---|---|---|
| Grid bubbles | all/3–4 sides on arch plans, 2 on framing; round heads, dash-dot centerlines; **fractional intermediates** (L.2, 1.9) where members land off-grid; skip letter "I" | bubbles ✓; fractional grids + per-discipline sides **gap** |
| Dimension chains | multi-tier, tick/slash terminators (not arrows), placed OUTSIDE the plan: (1) overall → (2) grid-to-grid bay string → (3) room/feature strings; "4 EQ. SPACES" style; "written dimensions govern" | grid + wall dims ✓ (imperial ✓); full 3-tier layering **gap** |
| Wall poché | cut walls double-line, NEW = heavy solid fill, existing lighter; glazing distinct | wall fills by type ✓; new/existing weight split **gap** |
| Material hatch | concrete/CMU fine stipple; plywood 45° diagonal; gravel/earth/insulation hatches in sections; leader note per hatch | **gap** (sections are outline-only) |
| Line-weight hierarchy | 3-tier: heavy cut/new → medium existing → light reference; dashed = hidden/demo/above ("ABV.") | uniform weights **gap** |
| Room tags | name over boxed number, every space; area | name+number ✓; area **gap** |
| Door / window tags | door = oval w/ number (A/B/C multi-leaf); window = hexagon; wall-type = diamond w/ code | hexagon door / diamond window tags ✓ (shape swap vs ref is acceptable — consistency governs) |
| Equipment / fixture tags | tagged, keyed to schedules (VAV-DD-1 style, underlined w/ leader) | equipment named ✓; leader tags keyed to schedules **gap** |
| Keynotes | numbered squares/diamonds on leaders → keynote legend | partial ✓ |
| Section / detail callouts | split circle detail#-over-sheet# (`9/A7.1`) | section marks ✓; detail bubbles w/ sheet refs **gap** |
| North arrow + graphic scale bar | every plan | ✓ (title block) |
| Key plan | reduced building on each plan sheet, coverage zone shaded, mini grid | **gap** |
| Match lines | labeled where plans split across sheets | **gap** (single crop today) |
| Revision clouds + deltas | scalloped clouds + Δ triangles + dated revision schedule | rev block ✓; clouds/deltas **gap** |
| Title block | discipline-appropriate; PE/SE **stamp block reserved** on structural | CD frame ✓; reserved stamp block **gap** |

## 2. Overlay-plan pattern (Verseon key insight)

One floor-plan geometry, **many annotated overlays**, each its own sheet:
`Dimensional · Notational/keynote · Egress · Finish · MEP-coordination · RCP ·
Demolition`. The cut is identical; only the annotation set differs. In llm-bim
this maps to the custom `sheets=[...]` register: several `plan` entries on the
same level with different `include` groups, `tags`, and dimension options.

## 3. Discipline targets

- **A**: partitions w/ cut poché, doors w/ leaf+swing+tag, layered dim chains,
  finish tags, area block, door/window schedules.
- **S**: member size tags (W/HSS callouts) + marks keyed to schedule,
  footing/concrete hatch, fractional grids at frame lines, PE-stamp reserved
  block, connection detail bubbles.
- **M/P/H**: duct size callouts (`24x12` / `nØ`) on every run, CFM on every
  diffuser, pipe size + slope + invert elevations, riser diagrams, equipment
  tags → schedule.
- **E/LV**: device symbols, homeruns, panel + circuit tags, one-line,
  lighting by type + switching + emergency.
- **FP**: mains/branches, head symbols + spacing chains (6'-5'-5'), riser,
  hydraulic reference nodes.
- **Process/N (no ref analog — hold to the same anatomy)**: zone poché,
  shielding hatch by material/thickness, penetration tags, boundary linework.

## 4. What this standard is for

1. **The agent's self-check**: before calling a set done, walk the anatomy
   table against your sheets. Every "gap" row you can't produce yet must be
   visible in your handoff, not silent.
2. **The kernel roadmap**: the "gap" cells above ARE the drawing-engine work
   packages (see `TEAM_STATUS.md`).
3. **The human review**: acceptance of a set is a review against THIS
   standard — professional doc-set anatomy — not against any prior tool's
   output.
