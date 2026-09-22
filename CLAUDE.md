# CLAUDE.md — point Claude (or any agent) at this repo

You are working in the **llm-bim** repository. Goal: the user chats with you; you produce **real BIM models and drawings on disk** under `./output/`.

## First steps (every session)

1. Read `skills/llm-bim/SKILL.md` (full rules and recipes).
2. Ensure install works:
   ```bash
   pip install -e ".[dev,server]"
   llmbim version
   ```
3. Default all deliverables to **`output/<project_slug>/`** in the repo root (create if needed).

## How you create work

Use the **kernel**, never freehand IFC/SVG/STEP in chat. A device and a site are the same path: one `Project`, then `export_deliverables`. A lid is `place_shield_slab`. A buried conduit bank is `place_duct_bank`. Sheets and the glTF use the stored width, height, and elevation.

```python
from llmbim import Project
from pathlib import Path

out = Path("output/my_building")
out.mkdir(parents=True, exist_ok=True)

p = Project.create("My Building")
p.add_level("L1", 0)
p.create_rect_shell(level="L1", x=0, y=0, w=12000, d=9000, height_mm=3500, thickness_mm=200, name_prefix="B")
# ... doors, equipment, notes ...
man = p.export_deliverables(out)
assert man.get("ok"), man
print("Wrote", out.resolve())
```

Or CLI:

```bash
llmbim template office_bay --out output/office
llmbim case intec
# copies to examples/output/intec — prefer also packing to output/
llmbim pack path.llmbim.json --out output/name
```

## Hard rules

- Mutations only via SDK / CLI / MCP / `project.op`.
- Do not invent geometry in prose.
- Run `validate`, `rules`, `clash` before calling work “done”.
- **Always end work with a re-engage link** (clickable pack HTML), not a file-tree tour:
  - Prefer `http://127.0.0.1:8766/<slug>/` after `OPEN.bat` / `python examples/open_packs.py <slug>`
  - MineClean default: `OPEN_MINECLEAN.bat` → `http://127.0.0.1:8766/mineclean_studio/`
  - Fallback only: absolute `…/output/<slug>/index.html`
  - Never hand `viewer3d.html` alone (duplicate tabs — it's linked from the pack index).
- **Version control (mandatory):** after each meaningful batch of model edits,  
  `p.commit("clear message of what changed")`.  
  Check `p.status()` — do not say “done” while dirty unless the user said not to commit.  
  Use `p.diff()` / `p.log()` / `p.checkout(version_id)` for true model history — **not chat scrollback**.  
  See `docs/VERSION_CONTROL.md`.

## MCP (optional)

If the user has MCP: run `llmbim mcp` with cwd = this repo. Tools: `project_create`, `wall_create`, `project_export_pack`, `ops_catalog`, …

## Recipes

See `skills/llm-bim/recipes/`. Templates: `office_bay`, `warehouse`, `hot_cell_bay`, `lab_bench`.

For a **complete plan/CD set** (building, addition, facility): follow
`skills/llm-bim/recipes/design_program.md` — design-basis module as the only
number source (engineering/rooms/loads developed in parallel with coordinates),
staged harness with model-VCS commits, occupancy-matched types (residential
work never uses `W-EXT-CMU`), explicit `sheets=[...]` register with
`units="imperial"` where appropriate, drift-pin tests. Worked instance:
`llmbim case schad` + `skills/llm-bim/recipes/schad_cd.md`.

### Machines / field products / vehicle arrays (platform doctrine)

If the user asks for a **product**, **launcher**, **pod**, **field unit**,
**vehicle array**, **skid**, **apparatus**, or **fab-ready** machine:

1. Read **`docs/MACHINE_ENGINEERING_BAR.md`** (engineering + drawing law) and
   **`docs/FIELD_DEVICE_FAB.md`** (PN / layer / fab law) +
   `skills/llm-bim/recipes/field_device_fab.md` · `recipes/machine_ga.md`.
2. Call `p.authoring_checklist("field_device_fab")` and
   `p.validate_intent("field_device_fab")` before export — the intent scores both bars.
3. **Do not** ship a single equipment box, a floating header/tray, a diagonal
   service run, or a matplotlib colored-box GA. Use a design-basis **parts[]**
   catalog, distinct `kind` per family (including hardware), connected orthogonal
   services with fittings at bends, `export_deliverables(mode="part")` (machine_set),
   and the **human product name** on titles (P/Ns stay document IDs).
4. State **scale posture** out loud: field/vehicle ≠ plant rack ≠ lab bench unless asked.
5. Worked examples: `examples/mineclean_component_apparatus.py` (engineering bar);
   `examples/pal_launcher.py` (field-array PN depth).

## Materials / parts / plumbing

```python
p.place_fitting(level="L1", fitting_type="elbow_90", nps="1/2", origin=(0,0), material="copper")
p.place_pipe(level="L1", nps="3/4", start=(0,0), end=(4000,0))
print(p.fitting_takeoff(fitting_type="elbow_90", material="copper"))  # qty by size
print(p.plumbing_schedule())
p.auto_assign()  # shell/flange/magnet → Proto10 parts; wall types → materials
p.export_material_lists()  # or included in export_deliverables → materials/
```

CLI: `llmbim takeoff <project> --kind plumbing` · `llmbim parts --fitting-type elbow_90`

## Group HQ pointer (added 2026-08-30)

This repo is one project inside a multi-company portfolio — UltraLife, Client+, Mechanical Battery, League+, SprayMapCA — under the Group (name TBD). Fleet-wide rules (queue, honesty blocks, handoffs, marketing) live in the **hq** repo: seeded today at `./hq/`, destined for `github.com/ryanultralife/hq` (move it out of this repo before pushing: it should live as its own repo, e.g. `C:\Users\ryanv\hq`). Before cross-project or company-level work, read `hq/AGENTS.md`. Everything below still governs work inside this repo.
