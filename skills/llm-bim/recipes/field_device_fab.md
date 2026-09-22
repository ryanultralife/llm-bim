# Recipe: field device / vehicle-array fab pack

**When:** user wants a machine, pod, launcher, field unit, vehicle array, skid, apparatus, or “fab-ready” product — **not** a building CD set.  
**Platform doctrine:** `docs/FIELD_DEVICE_FAB.md` (PN / layers / fab) **and** `docs/MACHINE_ENGINEERING_BAR.md` (connected services, fittings, hardware, model-cut GA).  
**Checklist:** `p.authoring_checklist("field_device_fab")` · `p.validate_intent("field_device_fab")`.

## 0. Interrogate scale first

Ask or declare:

1. **Mission** — field deployable? vehicle array? bench? plant skid?  
2. **Host** — UGV tray, light truck, trailer, VTOL bay, bench  
3. **Physics cell size** — bore, length, mass class (from basis, not invented packaging)  
4. **Array** — 1×1 LRIP vs 2×2 / 1×4  

Do **not** default to industrial racks or lab furniture. State `product_class` in the reply.

## 1. Basis SSOT

```text
design_basis/<product>_basis.json
  product_class
  design{} / cad_envelopes_mm{}
  parts[]  → pn, name, kind, material, system, shape, sizes, qty
```

Every mm comes from the basis. Expand `parts[]` until you have **dozens** of unique PNs.

## 2. Model pattern

```python
from llmbim import Project

p = Project.create("MB-XXX Field Product")
p.add_level("Deck", 0)
print(p.authoring_checklist("field_device_fab"))

# Per PN — coordination solid (viewer layer = kind)
eid = p.create_equipment_box(
    level="Deck",
    origin=(0, 0),
    size=(L, W, H),  # or cylinder size=(L, OD, OD)
    name=f"{pn} {name}",
    kind="rail",  # rail|coil|magnet|flange|shell|electrical|probe|…
    shape="box",  # or cylinder + orientation="x"
    part=pn,
    mark=mark,
    equipment="MB-XXX",
    centered=True,
    z0_mm=z0,
)
p.assign_material(eid, "copper_C12200")
p.op("set_param", id=eid, key="pn", value=pn)
p.op("set_param", id=eid, key="system", value="RAIL")
p.op("set_param", id=eid, key="product_class", value="field_deployable_vehicle_array")
p.op("set_param", id=eid, key="twin_fidelity", value="F1")

# Per machined PN — fab BREP
fid = p.create_fab_part(name=f"{pn} {name}", material="copper_C12200", level="Deck")
p.fab_box(fid, size_mm=(L, W, H))
p.gdt_datum(fid, label="A", face="bottom")
p.gdt_size(fid, dimension="L", nominal=L, tol_plus=0.2, tol_minus=0.2)

print(p.validate_intent("field_device_fab"))
# If this model has pipes/trays: they must be orthogonal, fitted at bends, and connected.
# Hardware families (bolt, flange, door, hinge, nameplate, …) are distinct kinds.
man = p.export_deliverables(out, mode="part", plan_level="Deck")
print("OPEN:", man.get("output_dir"), "/index.html")
```

Services: `place_pipe` / `place_riser` / `place_cable_tray` / `place_fitting` /
`mep_route(orthogonal=True)` / `connect()`. Never a diagonal segment or a
centered envelope pretending to be a header. Issued plan: `recipes/machine_ga.md`.

## 3. Arrays

- **POD-01** (or unit 1): full PN tree  
- **POD-02…N**: shells / hardpoints only **or** module instances — same PN BOM ×N  
- Tray / bus / control = array-level PNs (`system=ARRAY`)

## 4. Pack artifacts (mandatory)

| File | Role |
|------|------|
| `index.html` | Re-engage cover |
| `viewer3d.html` | Layer toggles |
| `parts/drawings/*.svg` | Per-component sheets |
| `fab/*.step` + `*_gdt.svg` | Fab-intent BREP |
| `BOM.csv` / `BOM.json` | PN rollup |
| `LAYERS.json` | kind → components |
| `design_basis.json` | SSOT copy |
| `model.gltf` / `model.step` | Assembly |

## 5. Honesty

Stamp notes: **FAB-INTENT · ENGINEERING ESTIMATE**.  
Do not claim PE release or campaign PERFORMANCE wires from geometry alone.

## 6. Worked example

```bash
set EIGEN_ROOT=path/to/repo_with_basis
python examples/pal_launcher.py
python examples/open_packs.py pal_launcher
```

Also: `examples/mineclean_component_apparatus.py` (engineering bar — connected
CW, fittings, hardware layers, machine_set GA), `examples/proto10_separator.py`.
