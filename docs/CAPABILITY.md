# Capability model — “whatever you throw at it”

LLM-BIM is built to **accept open-ended work**, not only house/INTEC demos.

## Principles

1. **Open element vocabulary** — any `category` string is valid (`create_generic`).
2. **Registered ops** — agents call `project.op("name", **params)`; list with `ops()`.
3. **Multi-format I/O** — import by extension; export full deliverables pack.
4. **Units at the boundary** — `create_wall(..., unit="ft")` converts to mm storage.
5. **Query language** — `project.query("category=wall param.thickness_mm>200")`.
6. **Repair & migrate** — open old files; `repair()` fixes orphans/degenerates.
7. **Scripts** — trusted Python `build(project)` runners for generative design.
8. **Bulk** — JSON op lists for batch agent edits.

## Import matrix

| Format | Extension | Behavior |
|--------|-----------|----------|
| Project JSON | `.llmbim.json` / schema JSON | merge or open |
| Op batch | `.json` with `ops` | apply mutations |
| Points | `.csv` | equipment markers |
| CAD lines | `.dxf` | walls (or lines) |
| BIM | `.ifc` | storeys + named walls/spaces (coordination) |
| Solids | `.step`/`.stp` | locked equipment + file ref |

```bash
llmbim import file.dxf --out examples/output/from_dxf --pack
llmbim import file.ifc --out examples/output/from_ifc
llmbim import-step part.step --level L1
llmbim script my_building.py --pack examples/output/scripted
llmbim query model.llmbim.json "category=equipment kind=shell"
llmbim op repair --path model.llmbim.json --save model.llmbim.json
```

## Export matrix

Always available via `export_deliverables` / `llmbim pack`:

JSON · IFC · glTF · STEP · SVG sheets · DXF · PDF plot set · BOQ (CSI) · clash · rules · ZIP

## What “complete” means here

| Layer | Completeness |
|-------|----------------|
| Agent API surface | Extensible — unknown domains use `create_generic` + params |
| Facility documentation | Construction set + PDF binder + schedules |
| Equipment | Box/cylinder + external STEP lock |
| Builder tools | BOQ/CSI, clash, rules, phases |
| Designer tools | Templates, types, notes, DXF |
| Geometry kernel | Parametric solids sufficient for coordination & fabrication envelopes |

**Not claimed:** replacing Revit families ecosystem, full BREP boolean kernel, or legal sealed CD certification. The system is built so **any new requirement is an op + params + export**, not a rewrite.

## Adding a new capability (for agents)

```python
from llmbim_core.registry import register

@register("my_op", description="Does a thing")
def my_op(model, params):
    ...
    return {"ok": True}
```

Then: `project.op("my_op", foo=1)`.
