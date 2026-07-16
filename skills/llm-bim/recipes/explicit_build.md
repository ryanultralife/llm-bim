# Recipe: explicit build (collect detail before geometry)

LLMs must **not invent** critical product detail silently. Collect or declare defaults first.

## 1. Call the checklist

```python
from llmbim import Project
p = Project.create("Demo")
print(p.authoring_checklist("building_shell"))
print(p.authoring_checklist("mep_run"))
print(p.authoring_checklist("fab_part"))
```

CLI: `llmbim op authoring_checklist --params '{"product":"building_shell"}'`

## 2. Required fields by product (minimum)

| Product | Must have |
|---------|-----------|
| **building_shell** | name, levels+elevations, plan extents, wall height+thickness or type_id |
| **openings** | host wall id, offset, width, height, type_id |
| **mep_run** | level, start→end or mep_route(from,to), size (NPS/WxH/trade), system |
| **structure** | level, W-section, column origin or beam start→end |
| **fab_part** | name, solid feature(s) with mm sizes; recommend GD&T + export_fab_step |
| **deliverables_pack** | export path; always tell user `index.html` + `viewer3d.html` |

## 3. State defaults out loud

If the user is vague, reply with:

> Using defaults: L1 @ 0 mm, 200 mm exterior walls (W-EXT-CMU), 3500 mm height, copper CW ¾" — say if you want different.

Then model.

## 4. Validate before pack

```python
print(p.validate_intent("building_shell"))
print(p.validate_intent("mep_run"))
man = p.export_deliverables()
print("OPEN", man.get("output_dir") or "output/<slug>/index.html")
```

## 5. Layered walls

```python
w = p.create_wall(level="L1", start=(0,0), end=(8000,0), thickness_mm=200, height_mm=3000)
p.set_type(w, "W-EXT-CMU")  # stores wall_layers → multi-band plan + glTF layers
```

## 6. MEP graph route

```python
a = p.place_fitting(level="L1", fitting_type="elbow_90", nps="2", origin=(0,0), material="copper")
b = p.place_fitting(level="L1", fitting_type="tee", nps="2", origin=(5000,3000), material="copper")
p.mep_route(a, b, kind="pipe", nps="2", material="copper", system="CW", orthogonal=True)
print(p.mep_graph())
```
