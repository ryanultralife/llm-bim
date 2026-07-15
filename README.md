# LLM-BIM

**Building Information Modeling operated entirely by LLMs.**

No drafting GUI. Agents create and edit a real 3D BIM model through **HTTP API**, **Python SDK**, **CLI**, and **MCP**. Import DXF/IFC/STEP/CSV/scripts; export IFC/STEP/glTF/DXF/SVG/PDF/BOQ. Humans **review** (including 3D). Built to handle **open-ended** building, site, and equipment work — not only demos.

Capability: [`docs/CAPABILITY.md`](docs/CAPABILITY.md) · Honesty: [`docs/HONESTY.md`](docs/HONESTY.md)

## Launch (local)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev,server]"

llmbim demo --out examples/output   # model + plan/section/elevation SVG
llmbim case intec                   # facility pack → examples/output/intec/
llmbim case proto10                 # part pack → examples/output/proto10/
llmbim pack path.json --out ./pack  # full BIM+IFC+STEP+glTF+sheets+BOQ
llmbim template office_bay --out ./out
llmbim boq model.llmbim.json
llmbim clash model.llmbim.json
llmbim rules model.llmbim.json -v
llmbim serve --port 8000            # API + 3D review pages
```

Builder/designer guide: [`docs/BUILDER_DESIGNER.md`](docs/BUILDER_DESIGNER.md) · Depth passes: [`docs/DEPTH_PASSES.md`](docs/DEPTH_PASSES.md)

```bash
llmbim pdf examples/output/intec/construction --out plot.pdf
llmbim import-step path/to/part.step --level L1 --out ./fusion_ref
```

### Deliverables pack (what you get)

| Output | File |
|--------|------|
| BIM model | `model.llmbim.json` |
| IFC4 | `model.ifc` |
| 3D mesh | `model.gltf` |
| 3D solids | `model.step` (+ per-part STEP under `parts/step/`) |
| Construction set | `construction/G-001…A-604_*.svg` |
| Part drawings | `parts/drawings/P-###_*.svg` |
| Schedules | `schedules/*.csv` |
| Index | `MANIFEST.json` |

See [`docs/OUTPUT_MATRIX.md`](docs/OUTPUT_MATRIX.md).
- Health: http://127.0.0.1:8000/health  
- API docs: http://127.0.0.1:8000/docs  
- Review: http://127.0.0.1:8000/  
- Seed: `curl -X POST http://127.0.0.1:8000/v1/demo/simple-house`

**Production:** Railway + Docker volume — see [`docs/LAUNCH.md`](docs/LAUNCH.md).

## Agent API (quick)

```http
POST /v1/projects
POST /v1/projects/{id}/levels
POST /v1/projects/{id}/walls
POST /v1/projects/{id}/slabs
POST /v1/projects/{id}/doors
GET  /v1/projects/{id}/exports/plan/L1.svg
POST /v1/demo/simple-house
```

Optional header: `X-API-Key: $LLMBIM_API_KEY`

## Python SDK

```python
from llmbim import Project

p = Project.create("Demo House")
p.add_level("L1", 0)
wid = p.create_wall(level="L1", start=(0, 0), end=(10000, 0), thickness_mm=200, height_mm=3000)
p.place_door(host=wid, offset_mm=2000, width_mm=900, height_mm=2100)
p.export_plan("L1", "plan.svg")
p.save("demo.llmbim.json")
```

## Repo map

| Path | Role |
|------|------|
| `packages/core` | Semantic model + command bus |
| `packages/geometry` | Parametric helpers |
| `packages/drawings` | Plan / section / elevation SVG |
| `packages/sdk` | `llmbim.Project` |
| `packages/server` | FastAPI agent API |
| `packages/mcp_server` | MCP tools |
| `packages/cli` | `llmbim` CLI |
| `docs/LAUNCH.md` | Deploy Railway / Docker |
| `docs/AGENT_SPEED.md` | Grok fast / Claude deep protocol |

## Multi-agent

See [`AGENTS.md`](AGENTS.md) and [`TEAM_STATUS.md`](TEAM_STATUS.md).

## License

MIT
