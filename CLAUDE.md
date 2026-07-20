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

Use the **kernel**, never freehand IFC/SVG/STEP in chat:

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
- Hand the user **exactly one path**: `output/<slug>/index.html` — the 3D viewer, PDF, sheets, and schedules are linked from it. Never open/point to `viewer3d.html` separately (duplicate tabs).
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
