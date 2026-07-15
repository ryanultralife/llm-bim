# Recipe: copper plumbing + fitting takeoff

```python
from llmbim import Project
from pathlib import Path

p = Project.create("CW Loop")
p.add_level("L1", 0)
p.create_rect_shell(level="L1", x=0, y=0, w=6000, d=4000, height_mm=3000, thickness_mm=200)

# Pipe runs (length from geometry)
p.place_pipe(level="L1", nps="3/4", start=(500, 500), end=(5500, 500), material="copper")
p.place_pipe(level="L1", nps="1/2", start=(2000, 500), end=(2000, 200), material="copper")

# Fittings
p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(500, 500))
p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(5500, 500))
p.place_fitting(level="L1", fitting_type="tee", nps="3/4", origin=(2000, 500))
p.place_fitting(level="L1", fitting_type="elbow_90", nps="1/2", origin=(2000, 200))
p.place_fitting(level="L1", fitting_type="ball_valve", nps="3/4", origin=(500, 800))

p.commit("CW rough-in")
print("90° copper by size:", p.fitting_takeoff(fitting_type="elbow_90", material="copper"))
# → [{'nps': '1/2', 'qty': 1, ...}, {'nps': '3/4', 'qty': 2, ...}]

out = Path("output/cw_loop")
p.export_deliverables(out)
# open materials/fitting_takeoff.csv and schedules/plumbing_takeoff.json
```

CLI after export:

```bash
llmbim takeoff output/cw_loop --kind plumbing
llmbim takeoff output/cw_loop --fitting-type elbow_90 --material copper
```
