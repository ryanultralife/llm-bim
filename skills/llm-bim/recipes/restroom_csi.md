# Recipe: restroom + CW loop + CSI room locators

Build a restroom with fixtures, copper CW piping, a vertical riser, then export
MasterFormat instances that include **RM:RoomName** locators.

```python
from llmbim import Project
from pathlib import Path

p = Project.create("Restroom Pack")
p.add_level("L1", 0)
p.create_rect_shell(level="L1", x=0, y=0, w=5000, d=4000, height_mm=3000, thickness_mm=200)
p.create_room(
    level="L1",
    name="Restroom A",
    boundary=[(200, 200), (4800, 200), (4800, 3800), (200, 3800)],
)

# Fixtures
p.place_part(level="L1", kind="toilet", origin=(1200, 1500))
p.place_part(level="L1", kind="tp_dispenser", origin=(900, 1500))
p.place_part(level="L1", kind="grab_bar", origin=(1500, 1200))

# CW rough-in + riser
p.place_pipe(level="L1", nps="3/4", start=(500, 1500), end=(2500, 1500), material="copper")
p.place_fitting(level="L1", fitting_type="elbow_90", nps="3/4", origin=(500, 1500))
p.place_fitting(level="L1", fitting_type="tee", nps="3/4", origin=(1200, 1500))
p.place_riser(level="L1", nps="2", origin=(2500, 1500), z0_mm=0, z1_mm=3000, material="copper")

p.commit("Restroom rough-in")

# CSI instances with room
for row in p.csi_instances():
    if row.get("room"):
        print(row["csi_code"], row["locator"])
# → 22 42 13 @ L1|RM:Restroom_A|X1200Y1500|...
# → 22 11 16 @ L1|RM:Restroom_A|X500Y1500|NPS3/4|...

out = Path("output/restroom_pack")
man = p.export_deliverables(out)
print("OPEN:", man["output_dir"] + "/index.html")
print("CSI:", man["output_dir"] + "/materials/csi_instances.csv")
```

CLI:

```bash
python -c "exec(open('skills/llm-bim/recipes/restroom_csi.md').read())"  # or paste recipe
llmbim takeoff output/restroom_pack --kind csi_instances
llmbim query output/restroom_pack "room~Restroom"
llmbim query output/restroom_pack "vertical=true"
```

Query tokens: `room~Name`, `csi~22_11` (underscore for spaces), `vertical=true`, `nps=2`.
