# Recipe: import user files

```bash
# CAD lines → walls
llmbim import survey.dxf --level L1 --out out/from_dxf --pack

# Coordination IFC
llmbim import consultant.ifc --out out/from_ifc --pack

# Fusion / vendor STEP as locked equipment
llmbim import-step machine.step --level L1 --name "Skid A" --out out/skid --copy-into out/skid/refs

# Point cloud-ish CSV (x,y,z,name)
llmbim import points.csv --level L1 --out out/pts
```

```python
p = Project.create("Import")
p.add_level("L1", 0)
p.import_file("survey.dxf", level="L1")
p.import_step("part.step", level="L1", name="Vendor", copy_into="refs")
p.repair()
p.export_deliverables("out/pack")
```
