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
10. **Explicit product detail:** before large models, call  
    `p.authoring_checklist("building_shell"|"mep_run"|"fab_part"|…)`  
    and either ask the user for **required** fields or **state defaults in the reply**.  
    After modeling: `p.validate_intent(...)`. See `recipes/explicit_build.md`.

## Act like the architect / machinist on the job

Before modeling a deliverable set, run **the interrogation**
(`recipes/design_program.md` §0): ask every question a professional would
need answered — site, program, envelope, structure, openings, MEP, tolerances,
deliverable scope — in one pass, at AI speed. Every answer lands in the basis;
every non-answer becomes a flagged assumption. Completeness of the finished
set is judged against **`docs/CD_COMPLETENESS_STANDARD.md`** (professional
doc-set anatomy, calibrated on real stamped reference sets) — walk its
anatomy table before saying done.

## Autonomy contract (method is yours; outcomes are checked)

You choose the approach — order of modeling, decomposition, iteration style.
The repo judges only **outcomes**, and you self-check them before saying done:

1. `validate` / `rules` / `clash` clean, or every finding explained on a sheet.
2. `verify_pack` ok — including strict glTF (blank 3D = failed pack, not a shrug).
3. Every number traceable to a stated source (user, basis module, catalog) —
   never retyped from memory; unknowns carried as `*_assumed` params or `Q-` notes,
   never silently resolved. `verify_pack` surfaces `assumption_flags` so honesty
   is visible, and `walls_untyped` so a massing study can't pass as a deliverable.
4. Types match occupancy (see Wall types) on anything handed over as a design.
5. Model VCS commits at meaningful stages — `p.log()` is the history, not chat.
6. Exactly one path handed over: `output/<slug>/index.html`.

If your output passes these, nobody second-guesses how you got there.

## Authoring contract (what the LLM must know)

Vague user ask → **you** make parameters explicit. Never silently invent PE ratings or critical sizes.

| Product | Required (minimum) | Recommended |
|---------|-------------------|-------------|
| Building shell | levels+elevations, plan L×W or wall loop, wall height + thickness **or** `type_id` | fire_rating, slab, grids, phase |
| Openings | host wall id, offset, W×H, type_id | fire_rating, sill |
| MEP run | level, start→end **or** `mep_route(from,to)`, size, system | material, z0_mm, orthogonal dogleg |
| Structure | level, section `W10x33`, origin or beam ends | beam z0 (TOS) |
| Roof | level, footprint, pitch + plate height (or both plate heights for shed) | ridge axis/offset, overhang, thickness |
| Foundation | level, footing W×D, slab thickness | rebar callouts (carried data), stem walls, marks F1/S1 |
| Fab part | name + solid feature(s) in mm | fillet selector, thread designation, GD&T, host knit |
| Full plan/CD set | design-basis module (ALL numbers), explicit sheet register | drift-pin tests, staged VCS commits — see `recipes/design_program.md` |
| Pack | `export_deliverables` | verify; hand over exactly ONE path: `<abs>/index.html` |

```python
print(p.authoring_checklist("building_shell"))
print(p.validate_intent("building_shell"))
# MEP graph (auto pipe between fittings):
p.mep_route(fit_a, fit_b, kind="pipe", nps="2", material="copper", orthogonal=True)
# Layered wall assembly (plan bands + glTF wall_structure/insulation/finish):
p.set_type(wall_id, "W-EXT-CMU")
```


## Primary workflows

### A. Start from template (default path = output/<name>/)

```python
from llmbim import Project
p = Project.from_template("office_bay")  # warehouse | hot_cell_bay | lab_bench
man = p.export_deliverables()  # → output/office_bay/  (or project name slug)
print("OPEN:", man["output_dir"] + "/index.html")
```

CLI: `llmbim template office_bay`  → `output/office_bay/`

## Output contract (any agent, any environment)

The deliverable is **one HTML file**: `output/<slug>/index.html`.

- Tell the user (or open) **exactly that one absolute path** — nothing else.
  The 3D viewer, PDF plot set, sheets, schedules, and takeoffs are all linked
  from it. Do **not** also open `viewer3d.html` — that causes duplicate tabs.
- `viewer3d.html` is fully self-contained (three.js bundled inline): it works
  offline, from `file://`, with no CDN or network. If a user reports a blank
  3D view, their pack predates this — regenerate with current `main`
  (old packs carried a glTF indexing bug; new packs also show errors in a
  visible banner instead of a black page).

### B. Freeform model

```python
p = Project.create("My Building")
p.add_level("L1", 0)
p.add_level("L2", 3500)
p.create_wall(level="L1", start=(0,0), end=(12000,0), thickness_mm=200, height_mm=3500, name="W-S", fire_rating="2-hr")
# or imperial:
p.create_wall(level="L1", start=(0,0), end=(40,0), thickness=0.67, height=10, unit="ft")
w = p.create_wall(level="L1", start=(0,0), end=(8000,0), thickness_mm=200, height_mm=3000)
p.place_door(host=w, offset_mm=2000, width_mm=900, height_mm=2100, type_id="D-HM-36", fire_rating="90 min")
p.place_window(host=w, offset_mm=5000, width_mm=1200, height_mm=900, sill_mm=900, type_id="WIN-VIEW")
p.create_slab(level="L1", polygon=[(0,0),(12000,0),(12000,9000),(0,9000)], thickness_mm=200)
p.create_room(level="L1", name="Hall", boundary=[(0,0),(12000,0),(12000,9000),(0,9000)], height_mm=3500)
p.add_grid(axis="U", positions_mm=[0,6000,12000], labels=["1","2","3"])
p.create_equipment_box(level="L1", origin=(5000,4000), size=(2000,1000,1500), name="AHU-1", kind="ahu", centered=True)
p.create_rect_shell(level="L1", x=0, y=0, w=12000, d=9000, height_mm=3500, thickness_mm=200, name_prefix="B")
p.set_type(w, "W-EXT-CMU")  # industrial; residential → W-EXT-2x6-BNB | W-INT-2x4 | W-1HR-GAR-ADU (see Wall types) — also op set_type / MCP set_type
p.set_phase(w, "new")       # new|existing|demo|temp — pack --phases filter
p.create_note(level="L1", text="Fire rating TBD", position=(1000, 1000))
p.export_deliverables("out/pack")
# agents: MCP shell_create · place_door/window · room/slab/equipment/grid/note · set_type/phase · element_delete
# CLI: place --kind shell|wall|door|window|room|slab|equipment|grid|note
# ops: create_rect_shell/create_wall/place_door/window/create_room/slab/equipment/add_grid/create_note/set_type/set_phase/delete
```

### B2. Structure, roofs, foundations (residential + heavy)

```python
# Roofs — one element per plane set; ridge/valley/eave math stored in params, never re-derived
p.create_gable_roof(level="L1", footprint=[(0,0),(14630,0),(14630,9754),(0,9754)],
                    ridge_axis="x", plate_mm=3048, pitch=6/12, overhang_mm=457)
p.create_shed_roof(level="L1", footprint=..., high_side="N", plate_low_mm=3048, plate_high_mm=3658)
# Foundations — rebar callouts are CARRIED design data, not calculations
p.create_strip_footing(level="L1", under_wall=w, width_mm=457, depth_mm=305,
                       rebar={"long": "(2) #4 CONT"}, mark="F1")
p.create_stem_wall(level="L1", path=[(0,0),(14630,0)], height_mm=900, thickness_mm=203)
p.create_pad_footing(level="L1", origin=(3000,3000), w_mm=914, d_mm=914, depth_mm=762, mark="F2")
p.create_slab_on_grade(level="L1", rect=(0,0,14630,9754), thickness_mm=102, mark="SOG-4")
print(p.rebar_schedule())                    # rows by mark/type/spec
# Structural: catalog sections (W16x40, HSS6x6x1/4, ...), typed headers + shear panels
p.place_beam(level="L1", start=(0,0), end=(6100,0), section="W16x40")
p.op("create_generic", category="header", level="L1", params={"type_id": "HDR-2"})  # LVL headers
from llmbim_core.material_lists import shear_wall_schedule
print(shear_wall_schedule(p.model))          # typed SSW panels (set_type + mark params)
# Tall walls on purpose (garage / balloon framing): declare it, or rules will flag
p.op("set_param", id=wall_id, key="multi_plate", value=True)  # WALL_EXCEEDS_STORY → info, not error
# MCP: roof_gable_create · roof_shed_create · footing_strip_create · footing_pad_create ·
#      stem_wall_create · slab_on_grade_create · rebar_schedule
```

### B3. Sheet sets: plan vs construction, custom register, imperial

`export_deliverables` emits the default register. For a **deliverable set**,
control it explicitly:

```python
from llmbim_drawings.construction import export_construction_set
export_construction_set(p.model, out, set_type="plan")          # permit/plan set
export_construction_set(p.model, out, set_type="construction")  # full CD default register
export_construction_set(p.model, out, units="imperial", sheets=[   # custom register
    {"no": "A0.1", "title": "COVER SHEET",   "kind": "cover"},
    {"no": "A1.1", "title": "FLOOR PLAN",    "kind": "plan", "level": "L1", "tags": True},
    {"no": "A2.1", "title": "ELEVATIONS S/N","kind": "elevations", "pair": ["S", "N"]},
    {"no": "A3.1", "title": "SECTIONS",      "kind": "sections"},
    {"no": "A4.1", "title": "SCHEDULES",     "kind": "schedule", "schedule": ["door", "window"]},
    {"no": "S3.1", "title": "DETAILS",       "kind": "details",
     "details": [{"id": "D01", "title": "FOOTING", "scale": 16, "ops": [...]}]},  # ops DSL, 4-up
    {"no": "H2.1", "title": "GENERAL NOTES", "kind": "doc", "text": notes_md},
])
```

- `units="imperial"` → feet-inches dims (`24'-0"`), `EL. +0'-0"` datums, SF areas,
  architectural scale notes; per-sheet or export-wide. Metric is the default.
- `tags: True` on plan sheets → door/window tag bubbles from element `mark` params.
- Detail `ops` DSL (`llmbim_drawings.detail_ops`): `l`/`d` lines, `r` rect, `c` circle,
  `h` hatch, `t` text, `dim` — data in, drafted SVG out. Never freehand SVG.
- CLI: `llmbim pack ... --set plan|construction`.

### B4. Full design program (a complete plan/CD set from a brief)

Follow **`recipes/design_program.md`**: all numbers in a design-basis module
(engineering, room types, loads developed in parallel with coordinates; never
retype a number), staged build harness with model-VCS commits, registered
types matching occupancy, explicit sheet register, drift-pin tests, honesty
stamps. Worked instance: `recipes/schad_cd.md` (`llmbim case schad` → 21-sheet
imperial CD set, CI-guarded).

### C. Import whatever the user has

```bash
llmbim import site.dxf --pack
llmbim import model.ifc --out out/ifc
llmbim import-step part.step --level Bench --out out/step
llmbim import points.csv --level L1
```

#### Engineering dataset import (primitives)

External repos often emit primitive lists: `{prim: "box"|"pipe", x, y, z, w/d/h | axis/len/r, name, sys, attrs}` in metres, grouped under keys like `placements/steel/doors/utilities/underground`. Import them directly — no bridge script:

```bash
llmbim import site_params.json   # auto-detected → columns/beams, typed doors on nearest wall, pipes/risers, ducts/trays, equipment; unknowns preserved as generic
```

```python
from llmbim_core.primitives_import import import_primitives
import_primitives(p.model, data)  # returns {created, skipped, warnings}
import_primitives(p.model, data, mapping={"services": {"CWS": {"kind": "pipe", "material": "fire", "system": "CWS"}}})  # also: nps_by_mm, wall_types, door_types
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
llmbim query model.llmbim.json "category=column section=W10x33"
llmbim query model.llmbim.json "category=conduit trade_size=1"
llmbim query model.llmbim.json "category=door fire_rating=90_min"
llmbim query model.llmbim.json "fire_rating~2"   # walls/doors with 2-hr etc.
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
p.op("set_type", id=wall_id, type_id="W-EXT-CMU")
p.op("set_phase", id=wall_id, phase="existing")
p.op("create_note", level="L1", text="See A-501", position=[1000, 1000])
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
print(p.csi_instances()[:3])  # MF + L1|RM:|XY|Z|NPS|section|SYS|FR|COLUMN|RISER
p.assign_part(equip_id, "PT-SEP-SHELL-320")
p.assign_material(wall_id, "CMU")
p.auto_assign()  # equipment kind → part; wall type → materials
man = p.export_deliverables()  # includes materials/ + schedules/plumbing_takeoff.json
```

```bash
llmbim parts --fitting-type elbow_90 --material copper
llmbim takeoff model.llmbim.json --kind plumbing
llmbim takeoff model.llmbim.json --fitting-type elbow_90 --material copper
llmbim takeoff model.llmbim.json --kind csi_instances   # MF code + room + XY + FR/SYS locator
llmbim schedule model.llmbim.json --kind zone --out zones.csv
llmbim schedule model.llmbim.json --kind connection
llmbim place model.llmbim.json --kind riser --origin 2500,1000 --nps 2 --z0 0 --z1 3500
llmbim place model.llmbim.json --kind fitting --origin 0,0 --fitting-type elbow_90 --nps 3/4
llmbim pack model.llmbim.json --out output/pack --phases new
llmbim verify output/pack --require-materials
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
p.place_column(level="L1", origin=(0,0), section="W10x33", height_mm=3500)  # CSI 05 12 00
p.place_beam(level="L1", start=(0,0), end=(8000,0), section="W12x26")       # CSI 05 12 00
p.place_part(level="L1", section="W10x33", length_m=3.5)
p.place_part(level="L1", bar_size="5", length_m=120)
p.create_wall(level="L1", start=(0,0), end=(8000,0), thickness_mm=200, height_mm=3500, fire_rating="2-hr")

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
llmbim place model --kind wall --origin 0,0 --end 8000,0 --width 200 --height 3000 --fire-rating 2-hr
llmbim place model --kind door --host <wall_id> --offset 2000 --width 900 --height 2100 --type-id D-HM-36 --fire-rating "90 min"
llmbim place model --kind window --host <wall_id> --offset 5000 --sill 900 --type-id WIN-VIEW
llmbim place model --kind shell --origin 0,0 --end 12000,9000 --height 3500 --thickness 200 --name B
llmbim place model --kind room --origin 0,0 --end 8000,6000 --name Office --height 2700
llmbim place model --kind slab --origin 0,0 --end 8000,6000 --width 200
llmbim place model --kind equipment --origin 2000,2000 --size 1200,800,1500 --name Skid --part-kind shell
llmbim place model --kind grid --axis U --positions 0,6000,12000 --labels 1,2,3
llmbim place model --kind note --origin 500,500 --text "Coordination note"
llmbim op set_type --path model --id <wall_id> --params '{"type_id":"W-EXT-CMU"}'
llmbim takeoff model --kind duct
llmbim takeoff model --kind conduit
llmbim takeoff model --kind cable_tray
llmbim schedule model --kind hvac_device
llmbim schedule model --kind door
llmbim query model "csi~26_05"
llmbim verify output/pack --require-materials
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
- `views/*.dxf` (plan/elev/section) · `boq.json` (CSI) · `clash_report.json` · `design_rules.json`  
- `materials/` — assignments, exploded BOM, **fitting/pipe/duct/conduit/steel/csi** takeoffs  
- `schedules/` — doors.csv · windows.csv · levels · drawing_list · duct · column · CSI · zone_areas  
- **`index.html`** — the ONE file to open; links the 3D studio (`viewer3d.html`: self-contained/offline, inspect · measure · filters · section cut · bloom), PDF, sheets, schedules  
- `deliverables.zip` · `MANIFEST.json` · `VERIFY.json`  
- `verify_pack`: has_doors_schedule · has_windows_schedule · elev/section DXF · materials package  

## Wall types (catalog)

**Match types to occupancy.** Industrial types on residential work (or vice
versa) is a modeling error — pick from the right family, or register a new
type via `llmbim_core.types_catalog` (`register_wall_type` / `register_door_type`
/ `register_window_type`).

| id | Family | Use |
|----|--------|-----|
| W-EXT-CMU | industrial | Exterior industrial |
| W-INT-GYP | industrial | Interior partitions (commercial/industrial) |
| W-SHIELD-CONC | industrial | Hot-cell / tunnel shield |
| W-EXT-2x6-BNB | residential | Wood-framed exterior (board & batten) |
| W-INT-2x4 | residential | Wood-framed interior partition |
| W-1HR-GAR-ADU | residential | 1-hr fire separation (garage/dwelling) |
| W-GENERIC-200 | — | Default |

Door types: `D-HM-36`, `D-HM-72`, `D-SHIELD-PLUG` (industrial) ·
`D-SC-36-ADA`, `D-HM-30`, `D-OH-12x9`, `D-OH-12x12` overhead (residential).
Window: `WIN-CASE-48x48`. Headers: `HDR-1`, `HDR-2` (LVL). Shear panels:
`SSW24x9`, `SSW24x12`.

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
- `skills/llm-bim/recipes/` — worked examples; **`design_program.md`** = full
  plan/CD-set workflow, **`schad_cd.md`** = worked residential CD instance  
- `docs/CAPABILITY.md` · `docs/HONESTY.md` · `docs/LOCAL.md` · `docs/RETIRING_REVIT_SCHAD.md`  
- `docs/DIGITAL_TWIN_TRL.md` — twin fidelity levels (F0–F3), TRL→artifact
  mapping for device development, `trl`/`trl_evidence`/`verification` param
  convention (carried claims with evidence pointers, never certifications)  
- `examples/intec_site.py` · `examples/proto10_separator.py` · `examples/schad_build.py`  
