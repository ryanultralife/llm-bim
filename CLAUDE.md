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
- Tell the user the **folder path** with drawings (`index.html`, `PLOT_SET.pdf`, `construction/`, etc.).

## MCP (optional)

If the user has MCP: run `llmbim mcp` with cwd = this repo. Tools: `project_create`, `wall_create`, `project_export_pack`, `ops_catalog`, …

## Recipes

See `skills/llm-bim/recipes/`. Templates: `office_bay`, `warehouse`, `hot_cell_bay`, `lab_bench`.
