# Machine engineering bar — platform law

**Audience:** every agent authoring a **machine, skid, apparatus, process train, or field product** in llm-bim.  
**Status:** **platform law** — not a MineClean one-off. Required of every project pointed at `skills/llm-bim/SKILL.md`.  
**Companion:** `docs/FIELD_DEVICE_FAB.md` is the PN / layer / fab-BREP bar. **This file is the engineering + drawing bar those packs must also meet.**  
**Worked instance:** `examples/mineclean_component_apparatus.py` → `examples/output/mineclean_studio/`.

Related: `skills/llm-bim/recipes/machine_ga.md` · `docs/CD_COMPLETENESS_STANDARD.md` §3 machine/skid · `docs/HONESTY.md`.

---

## 1. Why this exists

`field_device_fab` already forbids a single grey box. It did **not** stop the next failure mode: a pile of envelopes that look like a product but are not engineering.

Typical misses this bar exists to reject:

| Failure | What the reviewer sees |
|---------|------------------------|
| Floating services | Coolant return / cable tray hover; neither end lands on a nozzle or cabinet |
| Diagonal “pipe” | One segment jumps X and Y; no elbow, no landing |
| Envelope-only 3D | Colored AABBs, no fittings, bolts, doors, hinges, nameplates |
| Ink GA | matplotlib / `product_views` colored-box plan issued as the arrangement |
| PN-as-name | Sheet title `MB-MCLEAN` instead of the product humans asked for |
| Speech ≠ freeze | Notes or tags claim a rejected process (e.g. liquid MHD after ECO-MC-002) |

The model is the source of truth. Drawings are **cuts of that model**. Detail is **parts with kinds**, not denser ink.

---

## 2. Gates (required)

| Gate | Bar |
|------|-----|
| **Display name** | `Project.create("MineClean")` / `meta.product` is the human product. File stems and P/Ns (`MB-MC-100-001`, `MB-MCLEAN-S1.png`) stay **document IDs**. |
| **Model first** | Issued GA / elevations / section come from `export_deliverables(mode="part")` → `machine_set` (or an explicit construction register). Never a freehand or matplotlib sheet as the plan. |
| **Connected services** | Every header, return, tray, and drop **lands on both ends**. Orthogonal doglegs only (`place_pipe` / `place_riser` / `mep_route(orthogonal=True)`). Call `connect()` / record `mep_graph`. |
| **Fittings** | Elbow, tee, union, or flange at **every** bend and nozzle. No free-air corner. |
| **Hardware layers** | Distinct `kind` per family so the viewer has real layers — bolts, collars/flanges, doors, hinges, latches, nameplates, valve stems/handwheels, glands, louvers, grating clips, kickplates, feet, twistlocks. Add kinds; never collapse them into `equipment`. |
| **Parent tags** | Every solid carries `equipment=` (parent tag) + `part=` / `pn` so EQ-101 can collapse and leader-tag. |
| **Process notes** | `model.meta["process_notes"]` matches the design freeze. Do not label leftover envelopes with a rejected function. |
| **Honesty** | ENGINEERING ESTIMATE / FAB-INTENT. No PE seal. CAD lag is allowed; **speech and sheets are not**. |

Authoring contract:

```python
print(p.authoring_checklist("field_device_fab"))
print(p.validate_intent("field_device_fab"))
# validate_intent scores this bar when pipes/trays exist (fittings, orthogonality, connections)
# and warns when hardware kinds, display name, grids, or process_notes are missing.
```

---

## 3. Display name vs document IDs

| Surface | Use |
|---------|-----|
| Project name, pack title, sheet title block, 3D studio heading | **Product** — `MineClean`, not `MB-MCLEAN` |
| Filename, drawing number, part number, `params.pn` | **Document ID** — `MB-MC-100-001`, `EQ-101` |

Set `p.model.meta["product"]` when the project name must stay a file slug.

---

## 4. Connected services

1. Route **centerline to nozzle**, not a box centered in space.  
2. Change direction with a **dogleg** (X then Y, or riser) plus a fitting at the corner.  
3. Land both ends: chiller supply **and** return, tray origin **and** terminal, drops onto the cabinet they feed.  
4. Record the graph: `p.connect(...)` or `p.mep_route(...)`. Orphan pipes fail this bar.  
5. Headers and trays are **routed solids** (`place_pipe` / `place_cable_tray`), not a single long equipment envelope.

`validate_intent("field_device_fab")` **fails** when two or more pipes/trays exist without fittings, or any run changes both X and Y in one segment.

---

## 5. Layers beyond envelopes

A machine is not “enough boxes.” It is the parts a fabricator and an operator can point at.

**Minimum families** (use the frozen `kind` → material map in `llmbim_geometry.mesh.EQUIP_KIND_MATERIAL`; ADD only):

| Family | Example kinds |
|--------|----------------|
| Pressure boundary | `shell`, `chamber`, `lid`, `flange`, `gasket`, `gland` |
| Routed services | `pipe`, `elbow`, `tee`, `header`, `hose` |
| Fasteners | `bolt`, `nut`, `washer`, `stud`, `clamp` |
| Access | `door_leaf`, `hinge`, `latch`, `louver`, `vent` |
| Identity / operators | `nameplate`, `handwheel`, `stem` |
| Skid finish | `grating`, `clip`, `kickplate`, `foot`, `twistlock` |

Each family is a **viewer layer**. If the user cannot hide doors and still see hinges, the model is under-detailed.

---

## 6. Drawings

Wall-less equipment packs emit the machine register automatically (`llmbim_drawings.machine_set`):

| Sheet | Content |
|-------|---------|
| G-001 | Cover + drawing list + `process_notes` |
| EQ-101 | Plan: grids, 3-tier dims, one footprint per parent tag, leader tags, pipe centerlines |
| EQ-201 | South + east elevations |
| EQ-301 | Longitudinal section |
| EQ-501 | Equipment schedule (parent tags, not every bolt) |

Author bay grids when you know them; otherwise EQ-101 synthesizes from equipment centers.

**Do not:**

- Issue `product_views` / matplotlib colored boxes as the GA.  
- Hybrid STEP photo + bay boxes on one PNG.  
- Hand-draw a sheet that cannot be re-cut from the model.

Recipe: `skills/llm-bim/recipes/machine_ga.md`. Anatomy: `docs/CD_COMPLETENESS_STANDARD.md`.

---

## 7. Done checklist

Before saying a machine pack is done:

1. `validate_intent("field_device_fab")` → `ok` (or every missing item explained).  
2. Display name is the product; P/Ns are only IDs.  
3. No floating header, return, or tray — both ends land.  
4. No diagonal service runs; fittings at every corner.  
5. Viewer layers include hardware families, not one `equipment` dump.  
6. Pack contains `construction/EQ-101*.svg` (or the machine register), not a matplotlib stand-in.  
7. `process_notes` match the freeze.  
8. `verify_pack` ok; re-engage the pack `index.html`.

---

## 8. What this is not

- A second PN catalog — that stays in `docs/FIELD_DEVICE_FAB.md`.  
- A PE-stamped shop package.  
- Permission to invent process function for leftover CAD.

Geometry may lag a freeze. **Titles, tags, notes, and speech may not.**
