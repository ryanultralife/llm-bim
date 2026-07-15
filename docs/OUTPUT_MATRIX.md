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
| Industry BIM interchange | IFC4 `.ifc` | ✅ walls/slabs/**IfcDoor/IfcWindow @ host** + **IfcSpace** + **IfcColumn/IfcBeam** + FlowSegment/Fitting + SpaceContents + Pset_CSIMasterFormat | `llmbim_ifc` |
| 3D review mesh | glTF | ✅ walls + **doors/windows** + equipment + MEP + **system materials** (copper/fire/duct/conduit/door colors) | `llmbim_geometry.mesh` |
| 3D solid exchange | STEP AP203 | ✅ boxes/cylinders + MEP + **LAYER:name** PRODUCT tags (PIPE-CU/FP/DUCT/…) | `llmbim_geometry.step_export` |
| Floor plan | SVG | ✅ walls + openings + equip + **pipes/fittings/fixtures + riser circles + ducts** | `llmbim_drawings.plan` |
| Plan DXF | DXF R12 | ✅ walls/**WALL-TYPES FR** + **DOORS/WINDOWS** + rooms + MEP + COLUMNS/BEAMS + grids | `llmbim_drawings.dxf_export` |
| Elevation DXF | DXF R12 | ✅ walls + **DOORS/WINDOWS** + MEP + COLUMNS/BEAMS + LEVELS | `export_elevation_dxf` |
| Section DXF | DXF R12 | ✅ cut plane + walls + **DOORS/WINDOWS** + MEP + COLUMNS/BEAMS + LEVELS | `export_section_dxf` |
| Section / elevation | SVG | ✅ walls/equip + **doors/windows** (elev + **section cut**) + MEP + columns/beams + storey dims | `llmbim_drawings.section` |
| Floor plan room tags | SVG | ✅ name + **area m² + clear height** | `plan` room-label |
| Construction sheet set | multi SVG + index | ✅ | `llmbim_drawings.construction` |
| Plot set PDF | multi-page PDF | ✅ | `llmbim_drawings.pdf_binder` |
| Schedules | CSV/JSON | ✅ rooms/**zone_areas** (area+height+volume)/doors/windows/walls/equip/MEP/CSI | `llmbim_drawings.schedules` |
| Dimensions / tags / title block | | 🟡 title block + sheet frames | construction sheets |
| True wall joins / layered walls | | ❌ | future |
| Design rules + clash AABB | JSON | ✅ | `llmbim_core.rules` / `clash` |
| BOQ + CSI | JSON/CSV | ✅ real MasterFormat + **locator (level\|RM:\|XY\|Z\|NPS\|RISER)** | `llmbim_core.csi` |
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
| Structural columns | place + BOQ m + plan mark | ✅ | `place_column` CSI 05 12 00 |
| Structural beams | place + BOQ m + plan centerline | ✅ | `place_beam` CSI 05 12 00 |
| Rebar #3–#11 + WWF | takeoff | ✅ | `rebar_takeoff` |
| Fixtures (toilet, hose, TP dispenser) | place + takeoff | ✅ | `place_part` kinds |
| HVAC rectangular duct | place + BOQ m² + **duct_takeoff** + plan/DXF | ✅ | `place_duct` / `duct_takeoff` CSI 23 31 00 |
| Electrical conduit | place + BOQ m + **conduit_takeoff** + plan/DXF | ✅ | `place_conduit` / `conduit_takeoff` CSI 26 05 33 |
| Cable tray | place + BOQ m + takeoff + **schedule CSV** + plan/DXF | ✅ | `place_cable_tray` / `cable_tray_takeoff` CSI 26 05 36 |
| Vertical multi-storey riser | place + IFC/glTF | ✅ | `place_riser(to_level=…)` |
| CSI MasterFormat rollup | JSON/CSV | ✅ | `csi_takeoff` + room locators |
| Pack `materials/` folder | export | ✅ | `export_lists` in deliverables |
| Trade schedule all-in-one | JSON | ✅ | `full_trade_schedule` |

## One-shot pack

```text
Project.export_deliverables(out_dir)
→ model.llmbim.json
→ model.ifc · model.gltf · model.step
→ construction/ or parts/  (+ PLOT_SET.pdf)
→ views/ (plan/elev/section SVG + plan/elev/section DXF)
→ schedules/ (levels, zone_areas, csi, duct, conduit, column, beam, drawing_list, …)
→ materials/ (fitting/pipe/duct/conduit/cable_tray/steel/rebar/csi takeoffs + trade_schedule)
→ boq.json · clash_report.json · design_rules.json
→ index.html (CSI/zone/connections/drawing list/rules samples)
→ deliverables.zip · MANIFEST.json · VERIFY.json
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
| CLI `llmbim` | ✅ pack, **schedule** (level/column/beam/duct…), takeoff, place MEP/structure/**wall/door/window**, csi_instances, modules, VCS |
| Registry ops + `ops.schema.json` | ✅ ~45 tools (duct/conduit/tray/column/beam) |
| MCP stdio | ✅ query + takeoff + place MEP/structure/**door/window** + wall FR + schedule + **verify_pack** + pack phases + modules |
| Skill `skills/llm-bim/SKILL.md` | ✅ |
| Templates | ✅ office_bay, warehouse, hot_cell_bay, lab_bench |
| Cases | ✅ intec, proto10, plumbing_loop, multi_trade, module_machine_host |

## Honesty

Geometry is **parametric BIM + solid envelopes**, not a replacement for Fusion BREP detail or sealed CD packages. Takeoff unit costs are **ENGINEERING ESTIMATE**. Suitable for agent-driven layout, coordination, quantities, and exchange; refine in domain CAD for fabrication / PE stamp.
