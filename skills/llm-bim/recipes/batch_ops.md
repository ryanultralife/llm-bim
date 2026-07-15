# Recipe: batch ops (agent-friendly)

```python
from llmbim import Project
p = Project.create("Batch")
p.bulk([
  {"op": "add_level", "name": "L1", "elevation_mm": 0},
  {"op": "create_wall", "level": "L1", "start": [0,0], "end": [10000,0],
   "thickness_mm": 200, "height_mm": 3000, "name": "S"},
  {"op": "create_wall", "level": "L1", "start": [10000,0], "end": [10000,8000],
   "thickness_mm": 200, "height_mm": 3000, "name": "E"},
  {"op": "create_generic", "category": "duct", "level": "L1", "name": "SA-1",
   "params": {"diameter_mm": 500}},
])
p.op("validate")
p.export_deliverables("out/batch")
```

HTTP: `POST /v1/projects/{id}/ops` with `{"ops":[...]}`.
