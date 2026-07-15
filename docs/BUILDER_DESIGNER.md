# Builder & Designer playbook (LLM-BIM evolution)

LLM-BIM is **agent-operated**. Humans review packs; Grok/Claude design and coordinate.

## Personas

| Persona | Primary tools | Outputs |
|---------|---------------|---------|
| **Designer** | templates, types, notes, design_rules, plans | layout, types, construction sheets, DXF |
| **Builder** | BOQ, clash, rules, phases, STEP/IFC | quantities, cost estimate, clash report, fabrication exchange |
| **Agent** | SDK / MCP / HTTP API | everything above, headless |

## Designer workflow

```bash
llmbim template --list
llmbim template office_bay --out examples/output/my_office
# or in Python:
from llmbim import Project
p = Project.from_template("hot_cell_bay")
p.create_note(level="L0", text="Shield plug north", position=(1500, 3200))
for w in p.query(category="wall"):
    p.set_type(w.id, "W-SHIELD-CONC")
p.export_deliverables("out/cell")
```

Templates: `office_bay`, `warehouse`, `hot_cell_bay`, `lab_bench`.

Catalog wall types: `W-EXT-CMU`, `W-INT-GYP`, `W-SHIELD-CONC`, `W-GENERIC-200`.

## Builder workflow

```bash
llmbim boq model.llmbim.json --out boq.csv
llmbim clash model.llmbim.json
llmbim rules model.llmbim.json -v
llmbim pack model.llmbim.json --out ./pack
```

Pack now includes: `boq.json`, `clash_report.json`, `design_rules.json`, `views/*.dxf`.

## Review (human)

```bash
llmbim serve --port 8000
# open project review: 3D glTF orbit + plan SVG + BOQ/clash badges
```

Still **no drafting UI** — review only.

## Real program cases

```bash
python examples/intec_site.py      # facility
python examples/proto10_separator.py  # equipment
python scripts/verify_all.py
```
