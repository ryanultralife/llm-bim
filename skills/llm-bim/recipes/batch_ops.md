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
  {"op": "create_slab", "level": "L1", "polygon": [[0,0],[10000,0],[10000,8000],[0,8000]],
   "thickness_mm": 200},
  {"op": "create_room", "level": "L1", "name": "Hall",
   "boundary": [[0,0],[10000,0],[10000,8000],[0,8000]], "height_mm": 3000},
  {"op": "add_grid", "axis": "U", "positions_mm": [0,5000,10000]},
  {"op": "create_equipment_box", "level": "L1", "origin": [4000,3000],
   "size": [2000,1000,1500], "name": "Skid", "kind": "skid", "centered": True},
  {"op": "create_note", "level": "L1", "text": "See detail 3/A-501", "position": [500,500]},
  {"op": "place_duct", "level": "L1", "start": [0,1000], "end": [8000,1000],
   "width_mm": 400, "height_mm": 250},
  {"op": "place_column", "level": "L1", "origin": [0,0], "section": "W10x33",
   "height_mm": 3000},
])
if host:
    p.op("set_type", id=host, type_id="W-EXT-CMU")
    p.op("set_phase", id=host, phase="new")
p.op("validate")
p.export_deliverables("out/batch")
```

CLI equivalent:

```bash
llmbim place model --kind wall --origin 0,0 --end 10000,0 --fire-rating 1-hr --type-id W-EXT-CMU
llmbim place model --kind door --host <wall_id> --offset 2000 --type-id D-HM-36 --fire-rating "90 min"
llmbim place model --kind window --host <wall_id> --offset 5000 --sill 900
llmbim place model --kind room --origin 0,0 --end 10000,8000 --name Hall
llmbim place model --kind slab --origin 0,0 --end 10000,8000 --width 200
llmbim place model --kind equipment --origin 4000,3000 --size 2000,1000,1500
llmbim place model --kind grid --axis U --positions 0,5000,10000
llmbim place model --kind note --origin 500,500 --text "See A-501"
llmbim query model "category=door fire_rating=90_min"
```

HTTP: `POST /v1/projects/{id}/ops` with `{"ops":[...]}`.  
Registered: `create_wall` · `place_door` · `place_window` · `create_room` · `create_slab` · `create_equipment_box` · `add_grid` · `create_note` · `set_type` · `set_phase` · `place_duct` · `place_column` · …
