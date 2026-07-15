# Recipe: hot cell bay + vessel

```python
from llmbim import Project
p = Project.from_template("hot_cell_bay")
for w in p.query("category=wall"):
    p.set_type(w.id, "W-SHIELD-CONC")
p.create_note(level="L0", text="Shield plug north wall", position=(1500, 3100))
p.export_deliverables("out/cell")
print(p.boq()["summary"])
print(p.design_rules()["summary"])
```
