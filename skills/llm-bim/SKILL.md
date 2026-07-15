---
name: llm-bim
description: >
  LLM-native Building Information Modeling. Use when designing buildings, sites,
  facilities, equipment layouts, construction packs, BOQ, clash, IFC/STEP/DXF export,
  or agent-driven CAD/BIM without a drafting GUI. Local kernel via Python/CLI/MCP.
---

# LLM-BIM — agent skill (portable)

You are operating **llm-bim**: a deterministic BIM **kernel**. You never invent final geometry in prose.

## End goal

User points you at this repo and chats. You write **real files** under **`output/<project>/`** on their machine (models, drawings, PDF, BOQ). No cloud required.

Also read **`CLAUDE.md`** in the repo root when present.

## Install (user's machine — no cloud required)

```bash
git clone https://github.com/ryanultralife/llm-bim.git
cd llm-bim
# Windows:  .\scripts\install_local.ps1
# Unix:     bash scripts/install_local.sh
# or:
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate
pip install -e ".[dev,server]"
llmbim version
llmbim ops --schema
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
9. **True version control (not chat):** after each meaningful edit batch,  
   `project.commit("message")`. Use `status` / `diff` / `log` / `checkout`.  
   Chat is not history — commits under `output/<project>/.llmbim/versions/` are.

## Primary workflows

### A. Start from template (default path = output/<name>/)

```python
from llmbim import Project
p = Project.from_template("office_bay")  # warehouse | hot_cell_bay | lab_bench
man = p.export_deliverables()  # → output/office_bay/  (or project name slug)
print("OPEN:", man["output_dir"] + "/index.html")
```

CLI: `llmbim template office_bay`  → `output/office_bay/`

**Always tell the user the absolute path** to `index.html` and `PLOT_SET.pdf`.

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
llmbim query model.llmbim.json "room~Restroom category=fitting"
llmbim query model.llmbim.json "csi~22_11"          # MasterFormat (use _ for spaces)
llmbim query model.llmbim.json "vertical=true nps=2"  # risers
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

### G. Version control (true model versions)

```python
p = Project.create("Office")          # creates output/office/ + initial commit
# ... edits ...
p.commit("Shell and levels")
p.create_wall(...)
print(p.diff())                       # uncommitted changes
p.commit("North wall")
print(p.log())
p.tag("for_client")
# p.checkout("ver_…") or p.checkout("for_client")
```

CLI: `llmbim status|diff|commit|log|checkout|tag|journal <project_dir>`

### H. Materials, parts, plumbing takeoff

Full BIM lists — answer *“how many 90° copper fittings of what size?”*:

```python
p = Project.create("Plumb")
p.add_level("L1", 0)
p.place_pipe(level="L1", nps="3/4", start=(0,0), end=(5000,0), material="copper")
p.place_riser(level="L1", nps="2", origin=(2500,1000), z0_mm=0, z1_mm=3500, material="copper")  # vertical
p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(0,0), material="copper")
p.place_fitting(level="L1", fitting_type="elbow_90", nps="1/2", origin=(100,0), material="copper")
print(p.fitting_takeoff(fitting_type="elbow_90", material="copper"))
print(p.pipe_takeoff())  # includes riser length_m
print(p.plumbing_schedule()["copper_90_elbows_by_size"])
print(p.csi_instances()[:3])  # MasterFormat + L1|RM:Room|X|Y|Z|NPS|RISER locators
p.assign_part(equip_id, "PT-SEP-SHELL-320")
p.assign_material(wall_id, "CMU")
p.auto_assign()  # equipment kind → part; wall type → materials
man = p.export_deliverables()  # includes materials/ + schedules/plumbing_takeoff.json
```

```bash
llmbim parts --fitting-type elbow_90 --material copper
llmbim takeoff model.llmbim.json --kind plumbing
llmbim takeoff model.llmbim.json --fitting-type elbow_90 --material copper
llmbim takeoff model.llmbim.json --kind csi_instances   # MF code + room + XY locator
llmbim schedule model.llmbim.json --kind zone --out zones.csv
llmbim schedule model.llmbim.json --kind connection
llmbim place model.llmbim.json --kind riser --origin 2500,1000 --nps 2 --z0 0 --z1 3500
llmbim place model.llmbim.json --kind fitting --origin 0,0 --fitting-type elbow_90 --nps 3/4
llmbim pack model.llmbim.json --out output/pack --phases new
llmbim materials model.llmbim.json --out output/lists
python examples/plumbing_loop.py   # demo → output/plumbing_loop/COPPER_90_ELBOWS.json
```

Catalog: copper Type L pipe + 90/45 elbows, tees, couplings, caps, unions, ball valves (NPS ½–4"); PVC Sch40 subset. Part ids like `PT-CU-ELB90-1_2`, `PT-CU-PIPE-3_4`.

### I. All trades (fire, process, steel, rebar, framing, fixtures)

```python
# Fire sprinkler black steel
p.place_pipe(level="L1", nps="4", start=(0,0), end=(20000,0), material="fire")
p.place_fitting(level="L1", fitting_type="elbow_90", nps="2", origin=(0,0), material="fire")
p.place_part(level="L1", part_id="PT-FP-HEAD-PENDENT_5_6_155F", origin=(1000,1000))
print(p.fire_takeoff())

# Process SS316
p.place_fitting(level="L1", fitting_type="tee", nps="2", origin=(0,0), material="process")

# Structural steel + rebar
p.place_part(level="L1", section="W10x33", length_m=3.5)
p.place_part(level="L1", bar_size="5", length_m=120)

# Restroom: toilets, hoses, TP dispensers
p.place_part(level="L1", kind="toilet", origin=(0,0))
p.place_part(level="L1", kind="toilet_hose", origin=(0,0))
p.place_part(level="L1", kind="tp_dispenser", origin=(100,100))
p.place_part(level="L1", kind="grab_bar", origin=(100,200))

print(p.csi_takeoff())           # by CSI MasterFormat
print(p.trade_schedule())        # all trades
print(p.system_takeoff("fixture"))
```

```bash
llmbim parts --system fire --fitting-type elbow_90
llmbim takeoff model --kind fire
llmbim takeoff model --kind steel
llmbim takeoff model --kind rebar
llmbim takeoff model --kind csi
llmbim takeoff model --kind trades
python examples/multi_trade_catalog.py
```

Systems: `plumbing` · `fire` · `process` · `structural_steel` · `rebar` · `framing` · `fixture` / accessories · `hvac` · `electrical`. CSI divisions 03–10, 21–23, 26, 40, 43.

```python
# HVAC duct + electrical conduit/tray + multi-storey riser
p.place_duct(level="L1", start=(0,0), end=(8000,0), width_mm=600, height_mm=350)  # CSI 23 31 00
p.place_conduit(level="L1", start=(0,500), end=(8000,500), trade_size="1")        # CSI 26 05 33
p.place_cable_tray(level="L1", start=(0,800), end=(8000,800), width_mm=450)       # CSI 26 05 36
p.place_part(level="L1", kind="vav", origin=(2000,2000))            # CSI 23 36 00
p.place_part(level="L1", kind="fire_damper", origin=(4000,2000))    # CSI 23 33 00
p.place_part(level="L1", kind="diffuser", origin=(6000,2000))       # CSI 23 37 00
p.add_level("L2", 3500)
p.place_riser(level="L1", nps="2", origin=(4000,0), to_level="L2")  # spans storeys
p.place_part(level="L1", part_id="PT-ELEC-PANEL-42", origin=(500,500))
print(p.duct_takeoff())
print(p.conduit_takeoff())
print(p.cable_tray_takeoff())
# find items: room~Mech  csi~23_31  vertical=true
print(p.clash()[:5])  # duct vs pipe AABB included
```

```bash
llmbim place model --kind duct --origin 0,0 --end 8000,0 --width 600 --height 350
llmbim place model --kind conduit --origin 0,500 --end 8000,500 --nps 1
llmbim place model --kind cable_tray --origin 0,800 --end 8000,800 --width 450
llmbim place model --kind riser --origin 4000,0 --to-level L2 --nps 2
llmbim takeoff model --kind duct
llmbim takeoff model --kind conduit
llmbim takeoff model --kind cable_tray
llmbim schedule model --kind hvac_device
llmbim query model "csi~26_05"
```

### J. Modules / blocks / machines (import into one another)

Nest drawings and fabrications into a host model:

```python
# Export a machine design as a reusable module package
machine.export_module("output/modules/sep_skid", kind="machine")

# Import into facility host
host.import_module("output/modules/sep_skid", level="L0", origin=(8000, 6000),
                   mode="native")   # editable elements in host
host.import_module("output/modules/sep_skid", level="L0", origin=(16000, 6000),
                   mode="block")    # CAD-like block instance
host.import_module(path, level="L0", origin=(0,0), mode="linked")  # re-syncable

# Ports + connections (process / power / drain)
host.define_port(equip_id, "FEED", role="process", medium="slurry", position=(x,y))
host.connect(machine_el, "FEED", header_id, "DROP_A", medium="slurry")
host.explode_block(instance_id)   # block → native
print(host.modules())             # library + instances + connections
```

```bash
llmbim export-module model.llmbim.json --out output/modules/skid --kind machine
llmbim import-module output/modules/skid --mode native --origin 8000,6000 --pack
llmbim modules output/module_demo/host_pack
python examples/module_machine_host.py
```

| mode | Behavior |
|------|----------|
| `native` | Copy elements into host (fabrication design, fully editable) |
| `block` | Single instance + definition in `meta.module_library` |
| `linked` | Block that stores `source_path` for `resync_module` |

Exports expand blocks to solids for IFC/STEP/glTF; the saved host model keeps instances.

### K. Scripted generative design

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
- `materials/` — assignments, exploded BOM, **fitting_takeoff**, pipe_takeoff  
- `schedules/plumbing_takeoff.json` · fitting/pipe/part/material CSVs  
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
