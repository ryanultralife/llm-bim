# Recipe: small office

```python
from llmbim import Project
p = Project.from_template("office_bay")
# or freeform 12x9 m:
# p = Project.create("Office"); p.add_level("L1",0)
# p.create_rect_shell(level="L1", x=0,y=0,w=12000,d=9000,height_mm=3500,thickness_mm=200,name_prefix="B")
for w in p.query("category=wall"):
    p.set_type(w.id, "W-EXT-CMU")
p.export_deliverables("out/office")
```

CLI: `llmbim template office_bay --out out/office`
