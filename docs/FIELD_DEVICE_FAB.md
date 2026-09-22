# Field device / vehicle-array fab packs — platform doctrine

**Audience:** every agent (Grok, Claude, Gemini, Codex) authoring **machines, pods, launchers, skids, or field arrays** in llm-bim.  
**Status:** **platform law** — not a one-off example note.  
**Worked instance:** `examples/pal_launcher.py` · Eigen `cad/design_basis/pal_launcher_basis.json` · pack `examples/output/pal_launcher/`.

Related: **`docs/MACHINE_ENGINEERING_BAR.md`** (connected services, fittings, hardware layers, model-cut GA — **also required**) · `docs/EQUIPMENT_3D_AND_DEVICE_SSOT.md` · `docs/HONESTY.md` · `docs/DIGITAL_TWIN_TRL.md` · `docs/HERO_PRODUCT_RENDER.md` · `skills/llm-bim/recipes/field_device_fab.md`.

---

## 1. What the platform expects

When the user asks for a **product**, **launcher**, **pod**, **field unit**, **vehicle array**, or **fab-ready machine**, agents **must not**:

1. Drop a single grey equipment box and call it done.  
2. Invent plant-scale racks (1–2 m cabinets) for a **personal / field / small-vehicle** physics cell.  
3. Invent lab-benchtop furniture when the product is **field-deployable**.  
4. Export a pack without **per-component layers** and **per-PN sheets**.

Agents **must**:

| Gate | Bar |
|------|-----|
| **SSOT** | Design-basis JSON (or `device_pack` v1) is the only number source |
| **PN catalog** | Dozens of unique PNs (`parts[]`) — target ≥20 fab-intent, ≥40 preferred |
| **Layers** | Distinct `kind` per component family → glTF viewer layer toggles |
| **Solids** | One coordination solid per PN/instance (`create_equipment_box`) |
| **Fab** | `create_fab_part` + features + GD&T for machined PNs (`llmbim[fab]`) |
| **Sheets** | `export_deliverables(mode="part")` → `parts/drawings/*`, `fab/*` |
| **BOM / layers index** | Pack root: `BOM.csv`, `BOM.json`, `LAYERS.json`, `design_basis.json` |
| **Scale** | State product class out loud; envelopes match mission (field ≠ plant ≠ bench) |
| **Honesty** | FAB-INTENT / ENGINEERING ESTIMATE — not PE shop release unless user seals |
| **Re-engage** | One clickable `index.html` (portal preferred) |

Authoring contract:

```python
print(p.authoring_checklist("field_device_fab"))
print(p.validate_intent("field_device_fab"))
```

This checklist also scores **`docs/MACHINE_ENGINEERING_BAR.md`**: connected
headers/trays, orthogonal doglegs, fittings at bends, hardware `kind`s,
model-cut `machine_set` GA, human product name. A dense PN catalog that
still floats a coolant return or issues a matplotlib box plan **fails**.

---

## 2. Product classes (scale posture)

| `product_class` | Scale cue | Wrong if… |
|-----------------|-----------|-----------|
| `field_deployable_vehicle_array` | Modular pods on UGV / light truck / trailer tray | Lab pedestals, 1.2 m power racks |
| `modular_pod` | Single rugged unit ~0.5–1 m class | Facility skid halls |
| `personal_benchtop` | Desk apparatus | Vehicle trays, hardpoints |
| `industrial_skid` | Process skid meters-class | Fist-sized physics cell drawn plant-scale |

**Physics defaults are not packaging defaults.** A 100 mm bore × 500 mm barrel is **vehicle-pod scale**; packaging must not silently grow into plant furniture.

---

## 3. Layer model (viewer)

glTF / `viewer3d.html` layers key off **equipment `kind`** (and fab material keys).  
Frozen map: `llmbim_geometry.mesh.EQUIP_KIND_MATERIAL` · `docs/EQUIPMENT_3D_AND_DEVICE_SSOT.md` §5.3D.

**Rules:**

1. Every visible part has a **kind** from the equipment map (or an approved ADD).  
2. Prefer many kinds over one `equipment` dump — users toggle rails vs coil vs PFN.  
3. Set `params.system` (STRUCT, RAIL, BORE, COIL, MAG, PWR, DIAG, ARRAY, …).  
4. Set `params.pn` (or `part`) = catalog PN.  
5. Emit `LAYERS.json`: kind → list of `{id, name, pn, material, system}`.

Scene nodes are **per-element** (inspect by name); layer panel is **by material/kind**.

---

## 4. PN catalog (design basis)

Canonical shape (extend freely):

```json
{
  "product_class": "field_deployable_vehicle_array",
  "design": { "bore_id_mm": 100, "accel_length_mm": 500 },
  "cad_envelopes_mm": { "pod_L_mm": 720, "tray_L_mm": 1600 },
  "parts": [
    {
      "pn": "MB-PAL-200-001",
      "name": "Cu rail port",
      "kind": "rail",
      "material": "copper_C12200",
      "system": "RAIL",
      "shape": "bar",
      "size_mm": [500, 12, 25],
      "qty_per_pod": 1
    }
  ]
}
```

- **Never retype** a driven dimension from chat memory — import basis.  
- Array qty: primary pod full detail; other pods **instances** of the same PNs (BOM ×N).  
- Schematic-only parts: flag `"schematic": true` and stamp notes.

---

## 5. Dual representation (coordination + fab)

| Track | API | Role |
|-------|-----|------|
| Coordination | `create_equipment_box(..., kind=, part=, mark=)` | Layers, plan/elev, part SVG sheets, clash |
| Fab BREP | `create_fab_part` + `fab_box` / `fab_cylinder` / `fab_hole` + `gdt_*` | STEP + GD&T orthos under `fab/` |
| Assembly | `create_fab_assembly` + `fab_assembly_add` | Multi-body fab index |

**Export:**

```python
p.export_deliverables(out, mode="part", plan_level="Deck", plan_scale=0.28)
# optional: p.export_part_pack(out / "parts")
```

**CadQuery caution:** dense multi-hole bolt circles can hang export. Prefer **bore + GD&T bolt-circle callout** (`bolt_n`, `bolt_bc_mm` on params) unless holes are few. Do not use `fab_thread` in bulk export loops without smoke-testing.

---

## 6. Done checklist (agents)

Before saying “fab-ready” or “product pack done”:

1. `validate_intent("field_device_fab")` → `ok` (or every missing item explained).  
2. `verify_pack` / `llmbim verify <pack>` → `ok`, glTF valid, mesh_count ≫ 1.  
3. `parts/drawings/` has **many** SVGs (one family per instance/PN).  
4. `fab/` has STEP (+ GD&T) for machined PNs when fab enabled.  
5. `BOM.csv` + `LAYERS.json` + `design_basis.json` present.  
6. Honesty note on model notes + meta JSON.  
7. Re-engage: `http://127.0.0.1:8766/<slug>/` or `OPEN.bat`.  
8. Hero still optional via `export_hero_pipeline` / `docs/HERO_PRODUCT_RENDER.md`.  
9. **Engineering bar** (`docs/MACHINE_ENGINEERING_BAR.md`): services land both
   ends; no diagonal runs; fittings at corners; hardware families as layers;
   EQ-101 is a model cut; title uses the human product name.

---

## 7. Worked example — PAL

| Artifact | Path |
|----------|------|
| Basis | Eigen `cad/design_basis/pal_launcher_basis.json` (`v4-fab-layers`) |
| Builder | `examples/pal_launcher.py` |
| Pack | `examples/output/pal_launcher/` |
| Product class | `field_deployable_vehicle_array` |
| Depth | ~50+ unique PNs · 20+ layer kinds · part sheets + fab STEP |

```bash
set EIGEN_ROOT=...   # repo with pal_launcher_basis.json
python examples/pal_launcher.py
python examples/open_packs.py pal_launcher
```

---

## 8. What this is not

- PE-stamped fabrication package or NQA traveler  
- PERFORMANCE / muzzle self-wire from campaign physics (Eigen doctrine separate)  
- Single-mesh “pretty render” without sheets  

Geometry and sheets are **fab-intent coordination**. Physics grades live in the driver repo (Eigen); the twin **carries** claims via `trl` / `trl_evidence` / `verification` params (`docs/DIGITAL_TWIN_TRL.md`).
