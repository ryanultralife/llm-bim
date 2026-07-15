---
name: llm-bim
description: >
  LLM-native Building Information Modeling. Use when designing buildings, sites,
  facilities, equipment layouts, construction packs, BOQ, clash, IFC/STEP/DXF export,
  or agent-driven CAD/BIM without a drafting GUI. Local kernel via Python/CLI/MCP.
---

# LLM-BIM — agent skill (portable)

You are operating **llm-bim**: a deterministic BIM **kernel**. You never invent final geometry in prose.

## Install (user's machine — no cloud required)

```bash
git clone https://github.com/ryanultralife/llm-bim.git
cd llm-bim
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev,server]"
pytest -q
llmbim version
```

Optional MCP (Claude Desktop / Cursor / any MCP client):

```json
{
  "mcpServers": {
    "llm-bim": {
      "command": "llmbim",
      "args": ["mcp"]
    }
  }
}
```

Or HTTP (optional): `llmbim serve --port 8000` → docs at `/docs`.

## Hard rules

1. **All geometry mutations go through the kernel** (SDK, CLI, MCP, or `project.op`).
2. **Never write IFC/STEP/SVG by hand** in chat — call export APIs.
3. **Units:** storage is millimetres. Accept `unit="m"|"ft"|"in"` on walls; convert at boundary.
4. **IDs:** use returned element ids; never invent stable ids unless creating via API.
5. **Unknown domain** (ducts, trays, process skids): `create_generic(category, ...)` then params.
6. **Exact Fusion BREP:** `import_step` / `llmbim import-step` as **locked** equipment; keep the file.
7. **Honesty:** coordination + documentation grade; PE seals / code certification are human processes.
8. Prefer **small transactional steps** + `validate` / `rules` / `clash` after batches.

## Primary workflows

### A. Start from template

```python
from llmbim import Project
p = Project.from_template("office_bay")  # warehouse | hot_cell_bay | lab_bench
p.export_deliverables("out/pack")
```

CLI: `llmbim template office_bay --out out/pack`

### B. Freeform model

```python
p = Project.create("My Building")
p.add_level("L1", 0)
p.add_level("L2", 3500)
p.create_wall(level="L1", start=(0,0), end=(12000,0), thickness_mm=200, height_mm=3500, name="W-S")
# or imperial:
p.create_wall(level="L1", start=(0,0), end=(40,0), thickness=0.67, height=10, unit="ft")
p.create_rect_shell(level="L1", x=0, y=0, w=12000, d=9000, height_mm=3500, thickness_mm=200, name_prefix="B")
p.set_type(wall_id, "W-EXT-CMU")  # W-INT-GYP | W-SHIELD-CONC
p.create_note(level="L1", text="Fire rating TBD", position=(1000, 1000))
p.export_deliverables("out/pack")
```

### C. Import whatever the user has

```bash
llmbim import site.dxf --pack
llmbim import model.ifc --out out/ifc
llmbim import-step part.step --level Bench --out out/step
llmbim import points.csv --level L1
```

### D. Builder checks

```bash
llmbim boq model.llmbim.json
llmbim clash model.llmbim.json
llmbim rules model.llmbim.json -v
llmbim verify out/pack --require-parts
```

### E. Query

```bash
llmbim query model.llmbim.json "category=wall param.thickness_mm>200"
llmbim query model.llmbim.json "category=equipment kind=shell"
```

### F. Extensible ops

```bash
llmbim ops --json          # full catalog
llmbim op repair --path model.llmbim.json --save model.llmbim.json
llmbim op stats --path model.llmbim.json
```

```python
p.op("create_generic", category="duct", level="L1", name="SA-1", params={"diameter_mm": 600})
p.op("set_param", id=eid, key="fire_rating", value="2-hr")
p.repair()
```

### G. Scripted generative design

```python
# build.py
def build(project):
    project.add_level("L1", 0)
    for i in range(5):
        project.create_wall(level="L1", start=(i*3000,0), end=(i*3000+2500,0),
                            thickness_mm=200, height_mm=3000)
```

```bash
llmbim script build.py --pack out/gen
```

## Deliverables pack contents

`export_deliverables` / `llmbim pack` produces:

- `model.llmbim.json` — source of truth  
- `model.ifc` · `model.step` · `model.gltf`  
- `construction/` or `parts/` SVG sheets + `PLOT_SET.pdf`  
- `views/*.dxf` · `boq.json` (CSI) · `clash_report.json` · `design_rules.json`  
- `index.html` · `deliverables.zip` · `MANIFEST.json`  

## Wall types (catalog)

| id | Use |
|----|-----|
| W-EXT-CMU | Exterior industrial |
| W-INT-GYP | Interior partitions |
| W-SHIELD-CONC | Hot-cell / tunnel shield |
| W-GENERIC-200 | Default |

Door types: `D-HM-36`, `D-HM-72`, `D-SHIELD-PLUG`.

## Recovery protocol

1. On `VALIDATION_FAILED` / `GEOMETRY_DEGENERATE` — fix params, don't invent geometry.  
2. On orphan hosts — `p.repair()` or delete children first.  
3. On clash errors — move equipment or thin walls; re-run `clash`.  
4. On large model — batch with `bulk([...])` and intermediate `save`.  
5. Always end with `export_deliverables` + `verify` when user wants files.

## What you must not do

- Claim PE/code stamps  
- Freehand SVG/IFC/STEP in the reply  
- Require a cloud host for modeling (local kernel is enough)  
- Build a human drafting GUI  

## Reference files in repo

- `skills/llm-bim/ops.schema.json` — op catalog (regenerate: `llmbim ops --schema`)  
- `skills/llm-bim/recipes/` — worked examples  
- `docs/CAPABILITY.md` · `docs/HONESTY.md` · `docs/LOCAL.md`  
- `examples/intec_site.py` · `examples/proto10_separator.py`  
