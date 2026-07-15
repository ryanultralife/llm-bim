# Output matrix — audit vs target

**Audit date:** 2026-07-15 (vision-loop pass 1)  
**Goal:** LLM-native BIM kernel — facilities + parts + multi-trade takeoffs → local `./output/`

## Status legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented and tested |
| 🟡 | Partial / engineering estimate quality |
| ❌ | Missing |

## Facilities & buildings (INTEC, houses)

| Deliverable | Format | Status | Module |
|-------------|--------|--------|--------|
| Semantic BIM model | `.llmbim.json` | ✅ | `llmbim_core` |
| Industry BIM interchange | IFC4 `.ifc` | ✅ pure SPF: walls/slabs/doors/spaces + **proxy for equip/pipe/fitting/fixture/module** | `llmbim_ifc` |
| 3D review mesh | glTF | ✅ walls + equipment + **pipe/fitting/fixture/module boxes** | `llmbim_geometry.mesh` |
| 3D solid exchange | STEP AP203 | ✅ boxes/cylinders + **pipe/fitting/fixture envelopes** | `llmbim_geometry.step_export` |
| Floor plan | SVG | ✅ walls + openings + equip + **pipes/fittings/fixtures** | `llmbim_drawings.plan` |
| Section / elevation | SVG | ✅ walls/equip + **pipe marks on elev/section** | `llmbim_drawings.section` |
| Construction sheet set | multi SVG + index | ✅ | `llmbim_drawings.construction` |
| Plot set PDF | multi-page PDF | ✅ | `llmbim_drawings.pdf_binder` |
| Schedules | CSV/JSON | ✅ rooms/doors/windows/walls/equip/fitting/pipe/part/material | `llmbim_drawings.schedules` |
| Dimensions / tags / title block | | 🟡 title block + sheet frames | construction sheets |
| True wall joins / layered walls | | ❌ | future |
| Design rules + clash AABB | JSON | ✅ | `llmbim_core.rules` / `clash` |
| BOQ + CSI | JSON/CSV | ✅ | `llmbim_core.quantities` / `csi` |
| True model VCS | `.llmbim/versions` | ✅ | `llmbim_core.versioning` |

## Parts / equipment (Proto10 separator)

| Deliverable | Format | Status | Module |
|-------------|--------|--------|--------|
| Part envelopes in BIM | equipment boxes/cylinders | ✅ | commands + parts catalog |
| Part type assignment | `part_id` / auto_assign | ✅ | `assignment` |
| Part 2D drawing pack | SVG GA + views | ✅ | `llmbim_drawings.parts` |
| Part / assembly STEP | STEP | ✅ | step_export per equipment + assembly |
| Locked Fusion STEP import | file ref + envelope | ✅ | `step_import` |
| Full Fusion body fidelity (118 solids) | | ❌ | import STEP as locked; not authoring kernel |
| Machining drawings w/ GD&T | | ❌ | future |

## Materials / multi-trade takeoff (CSI)

| Deliverable | Format | Status | Module |
|-------------|--------|--------|--------|
| Materials catalog | id → density/cost/CSI | ✅ | `materials` (~40 materials) |
| Parts catalog | ~430 parts | ✅ | `parts_catalog` + `catalog_systems` |
| Plumbing copper fittings by NPS | takeoff | ✅ | `fitting_takeoff` |
| Fire sprinkler + heads | takeoff | ✅ | `fire_takeoff` |
| Process SS piping | catalog + place | ✅ | material=`process` |
| Structural steel W/HSS/bolts | takeoff | ✅ | `steel_takeoff` |
| Rebar #3–#11 + WWF | takeoff | ✅ | `rebar_takeoff` |
| Fixtures (toilet, hose, TP dispenser) | place + takeoff | ✅ | `place_part` kinds |
| CSI MasterFormat rollup | JSON/CSV | ✅ | `csi_takeoff` |
| Pack `materials/` folder | export | ✅ | `export_lists` in deliverables |
| Trade schedule all-in-one | JSON | ✅ | `full_trade_schedule` |

## One-shot pack

```text
Project.export_deliverables(out_dir)
→ model.llmbim.json
→ model.ifc · model.gltf · model.step
→ construction/ or parts/  (+ PLOT_SET.pdf)
→ views/ (SVG + DXF)
→ schedules/ (+ plumbing_takeoff.json)
→ materials/ (assignments, fitting/pipe/steel/rebar/csi takeoffs)
→ boq.json · clash_report.json · design_rules.json
→ index.html · deliverables.zip · MANIFEST.json · VERIFY.json
```

## Modules / blocks / machines

| Deliverable | Status | Module |
|-------------|--------|--------|
| Export project as module package | ✅ | `export_module` → dir or `.llmbim.json` + `MODULE.json` |
| Import as **native** (editable) | ✅ | `import_module(..., mode="native")` |
| Import as **block** instance | ✅ | `mode="block"` + `meta.module_library` |
| Import as **linked** (re-sync) | ✅ | `mode="linked"` + `resync_module` |
| Ports + connect machines to host | ✅ | `define_port` / `connect` |
| Explode block → native | ✅ | `explode_block` |
| Expand blocks on IFC/STEP/glTF | ✅ | `expand_block_for_export` in pack |
| Full MEP routing / P&ID solver | ❌ | semantic ports only (honesty) |

## Agent surfaces

| Surface | Status |
|---------|--------|
| Python SDK `llmbim.Project` | ✅ |
| CLI `llmbim` | ✅ pack, takeoff, parts, materials, import-module, VCS, … |
| Registry ops + `ops.schema.json` | ✅ ~40 tools |
| MCP stdio | ✅ takeoff/parts + import_module/connect/define_port/csi_instances |
| Skill `skills/llm-bim/SKILL.md` | ✅ |
| Templates | ✅ office_bay, warehouse, hot_cell_bay, lab_bench |
| Cases | ✅ intec, proto10, plumbing_loop, multi_trade, module_machine_host |

## Honesty

Geometry is **parametric BIM + solid envelopes**, not a replacement for Fusion BREP detail or sealed CD packages. Takeoff unit costs are **ENGINEERING ESTIMATE**. Suitable for agent-driven layout, coordination, quantities, and exchange; refine in domain CAD for fabrication / PE stamp.
