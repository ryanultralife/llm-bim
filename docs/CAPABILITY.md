# Capability model — “whatever you throw at it”

LLM-BIM is built to **accept open-ended work**, not only house/INTEC demos.

## Principles

1. **Open element vocabulary** — any `category` string is valid (`create_generic`).
2. **Registered ops** — agents call `project.op("name", **params)`; list with `ops()`.
3. **Multi-format I/O** — import by extension; export full deliverables pack.
4. **Units at the boundary** — `create_wall(..., unit="ft")` converts to mm storage.
5. **Query language** — `project.query("category=wall param.thickness_mm>200")`.
6. **Repair & migrate** — open old files; `repair()` fixes orphans/degenerates.
7. **Scripts** — trusted Python `build(project)` runners for generative design.
8. **Bulk** — JSON op lists for batch agent edits.

## Import matrix

| Format | Extension | Behavior |
|--------|-----------|----------|
| Project JSON | `.llmbim.json` / schema JSON | merge or open |
| Op batch | `.json` with `ops` | apply mutations |
| Points | `.csv` | equipment markers |
| CAD lines | `.dxf` | walls (or lines) |
| BIM | `.ifc` | storeys + named walls/spaces (coordination) |
| Solids | `.step`/`.stp` | locked equipment + file ref |

```bash
llmbim import file.dxf --out examples/output/from_dxf --pack
llmbim import file.ifc --out examples/output/from_ifc
llmbim import-step part.step --level L1
llmbim script my_building.py --pack examples/output/scripted
llmbim query model.llmbim.json "category=equipment kind=shell"
llmbim op repair --path model.llmbim.json --save model.llmbim.json
```

## Export matrix

Always available via `export_deliverables` / `llmbim pack`:

JSON · IFC · glTF · STEP · SVG sheets · DXF · PDF plot set · BOQ (CSI) · clash · rules · ZIP  
**Materials package:** `materials/fitting_takeoff.*` · `pipe_takeoff.*` · exploded BOM · part assignments  
**Plumbing:** `schedules/plumbing_takeoff.json` — copper 90° elbows counted by NPS

## Parts & materials BIM

| Need | API |
|------|-----|
| Assign material | `p.assign_material(id, "copper_C12200")` |
| Assign catalog part | `p.assign_part(id, "PT-CU-ELB90-1_2")` |
| Place fitting | `p.place_fitting(level=..., fitting_type="elbow_90", nps="1/2")` |
| Place pipe | `p.place_pipe(level=..., nps="3/4", start=..., end=...)` |
| Count 90° copper by size | `p.fitting_takeoff(fitting_type="elbow_90", material="copper")` |
| Full plumbing schedule | `p.plumbing_schedule()` |
| Export lists | `p.export_material_lists()` / pack `materials/` |

Ops: `assign_material`, `assign_part`, `place_fitting`, `place_pipe`, `place_part`, `fitting_takeoff`, `system_takeoff`, `csi_takeoff`, `auto_assign`, `materials`, `parts`.

### Trade catalogs (~430 parts)

| System | Examples | CSI |
|--------|----------|-----|
| Plumbing | copper/PVC pipe+fittings, toilets, hoses, TP dispensers | 22 / 10 28 |
| Fire | black steel FP pipe, 90s, heads, OS&Y, extinguishers | 21 |
| Process | SS316L pipe/fittings/valves/strainers | 40 05 |
| Structural steel | W8–W30, HSS, C, L, plate, A325 bolts, deck | 05 12 |
| Rebar | #3–#11, WWF, chairs, couplers | 03 20 |
| Framing | 2x4/2x6, metal studs/track, plywood/OSB | 06 / 09 22 |
| HVAC / Electrical | diffusers, VAV, panels, luminaires, EMT | 23 / 26 |

```python
p.place_part(level="L1", kind="toilet")
p.place_part(level="L1", kind="tp_dispenser")
p.place_part(level="L1", section="W10x33", length_m=3.5)
p.place_part(level="L1", bar_size="5", length_m=120)
p.place_fitting(level="L1", fitting_type="elbow_90", nps="2", material="fire")
p.csi_takeoff()  # by MasterFormat
```

## Modules / blocks / machines

Import drawings and fabrications into one another:

| Mode | Use |
|------|-----|
| `native` | Explode into host elements — editable fabrication design |
| `block` | CAD-like instance + definition library |
| `linked` | Block with `source_path` for re-sync |

```python
machine.export_module("output/modules/skid", kind="machine")
host.import_module("output/modules/skid", level="L0", origin=(8000,6000), mode="native")
host.import_module("output/modules/skid", level="L0", origin=(16000,6000), mode="block")
host.define_port(id, "FEED", role="process", medium="slurry")
host.connect(machine_id, "FEED", header_id, "DROP_A", medium="slurry")
host.explode_block(block_instance_id)
```

Ops: `import_module`, `export_module`, `explode_block`, `define_port`, `connect`, `list_modules`.

## CSI MasterFormat + locators

Every element can resolve a **real MasterFormat section** (e.g. `22 11 16` Domestic Water Piping, `22 42 13` Commercial Water Closets, `21 13 13` Wet-Pipe Sprinkler) plus a **locator** so you can find it:

```text
csi_code:     22 11 16
csi_instance: 22 11 16 @ L1|RM:Restroom_A|X1200Y3400|Z900|NPS3/4
level / room / x_mm / y_mm / z_mm / height_mm / nps / RISER
```

Locator tokens (pipe-separated): `level` · `RM:RoomName` (point-in-polygon) · `X…Y…` · `Z…` · `Zabs…` · `H…` · `NPS…` · section · `RISER`.

```python
p.csi_instances()   # one row per element (includes room + locator)
p.csi_takeoff()     # rollup by section + instance list
# pack writes materials/csi_instances.csv + schedules/csi.csv
# CLI: llmbim takeoff PATH --kind csi_instances
# CLI place: llmbim place PATH --kind riser --origin 1500,2000 --z0 0 --z1 3000 --nps 2
# CLI schedule: llmbim schedule PATH --kind zone --out zones.csv
#               llmbim schedule PATH --kind csi|connection|room|door
p.set_phase(wall_id, "existing")
p.export_deliverables(out, phases="new")  # IFC/BOQ/views = new only; full model still saved
```

## What “complete” means here

| Layer | Completeness |
|-------|----------------|
| Agent API surface | Extensible — unknown domains use `create_generic` + params |
| Facility documentation | Construction set + PDF binder + schedules |
| Equipment | Box/cylinder + external STEP lock |
| Builder tools | BOQ/CSI, clash, rules, phases |
| Designer tools | Templates, types, notes, DXF |
| Geometry kernel | Parametric solids sufficient for coordination & fabrication envelopes |

**Not claimed:** replacing Revit families ecosystem, full BREP boolean kernel, or legal sealed CD certification. The system is built so **any new requirement is an op + params + export**, not a rewrite.

## Adding a new capability (for agents)

```python
from llmbim_core.registry import register

@register("my_op", description="Does a thing")
def my_op(model, params):
    ...
    return {"ok": True}
```

Then: `project.op("my_op", foo=1)`.
