# Recipe: batch ops (agent-friendly)

```python
from llmbim import Project
p = Project.create("Batch")
p.bulk([
  {"op": "add_level", "name": "L1", "elevation_mm": 0},
  {"op": "create_wall", "level": "L1", "start": [0,0], "end": [10000,0],
   "thickness_mm": 200, "height_mm": 3000, "name": "S", "fire_rating": "1-hr",
   "type_id": "W-EXT-CMU"},
  {"op": "create_wall", "level": "L1", "start": [10000,0], "end": [10000,8000],
   "thickness_mm": 200, "height_mm": 3000, "name": "E"},
])
# Hosted openings need host wall id from previous bulk/create
walls = p.query("category=wall name~S")  # or p.query(category="wall")
host = walls[0].id if walls else None
if host:
    p.bulk([
      {"op": "place_door", "host": host, "offset_mm": 2000, "width_mm": 900,
       "height_mm": 2100, "type_id": "D-HM-36", "fire_rating": "90 min"},
      {"op": "place_window", "host": host, "offset_mm": 5000, "width_mm": 1200,
       "height_mm": 900, "sill_mm": 900, "type_id": "WIN-VIEW"},
    ])
p.bulk([
  {"op": "place_duct", "level": "L1", "start": [0,1000], "end": [8000,1000],
   "width_mm": 400, "height_mm": 250},
  {"op": "place_column", "level": "L1", "origin": [0,0], "section": "W10x33",
   "height_mm": 3000},
])
p.op("validate")
p.export_deliverables("out/batch")
```

CLI equivalent:

```bash
llmbim place model --kind wall --origin 0,0 --end 10000,0 --fire-rating 1-hr --type-id W-EXT-CMU
llmbim place model --kind door --host <wall_id> --offset 2000 --type-id D-HM-36 --fire-rating "90 min"
llmbim place model --kind window --host <wall_id> --offset 5000 --sill 900
llmbim query model "category=door fire_rating=90_min"
```

HTTP: `POST /v1/projects/{id}/ops` with `{"ops":[...]}`.
Registered: `create_wall` · `place_door` · `place_window` · `place_duct` · `place_column` · …
