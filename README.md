# LLM-BIM

**Building Information Modeling operated entirely by LLMs.**

No drafting GUI. Agents create and edit a real 3D BIM model through **HTTP API**, **Python SDK**, **CLI**, and **MCP**. Drawings (SVG) and schedules are derived from the model. Humans only **review** exports.

## Launch (local)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev,server]"

llmbim demo --out examples/output   # model + plan/section/elevation SVG
llmbim serve --port 8000            # API + review pages
```

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
