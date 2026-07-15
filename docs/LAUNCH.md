# Launch guide — LLM-BIM

## What you get when launched

| Surface | URL / command | Who uses it |
|---------|----------------|-------------|
| Health | `GET /health` | Load balancers |
| OpenAPI | `/docs` | Agents & humans inspecting API |
| Review (read-only) | `/` and `/review/{id}` | Humans **viewing** exports only |
| Agent API | `/v1/...` | Grok, Claude, scripts |
| MCP | `llmbim mcp` | Local Claude/Cursor tool bridge |
| CLI | `llmbim demo` / `llmbim serve` | Local |

**No drafting UI.** Modeling only via API / SDK / MCP / CLI.

---

## Local launch (2 minutes)

```bash
git clone https://github.com/ryanultralife/llm-bim.git
cd llm-bim
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev,server]"

# Build demo files
llmbim demo --out examples/output

# Start API
llmbim serve --port 8000
```

Open:

- http://127.0.0.1:8000/health  
- http://127.0.0.1:8000/docs  
- http://127.0.0.1:8000/  

Seed a house:

```bash
curl -X POST http://127.0.0.1:8000/v1/demo/simple-house
```

Optional API key:

```bash
set LLMBIM_API_KEY=secret   # Windows
export LLMBIM_API_KEY=secret
# then send header: X-API-Key: secret
```

Data dir (projects): `LLMBIM_DATA_DIR` (default `./data`).

---

## Railway (recommended for the API)

1. Push `main` to GitHub (already done if following Grok).
2. [railway.app](https://railway.app) → New Project → Deploy from GitHub → `llm-bim`.
3. Railway detects `Dockerfile` / `railway.toml`.
4. Variables (optional):

| Variable | Purpose |
|----------|---------|
| `LLMBIM_API_KEY` | Protect mutation endpoints |
| `LLMBIM_DATA_DIR` | `/data` (default in Docker) |
| `PORT` | Set by Railway automatically |

5. Add a **Volume** mounted at `/data` so projects survive restarts.
6. Generate domain → open `https://YOUR-APP.up.railway.app/health`.

CLI one-liner (if Railway CLI installed):

```bash
railway login
railway init
railway up
railway volume add  # mount /data
```

---

## Docker (any host)

```bash
docker build -t llmbim .
docker run --rm -p 8000:8000 -v llmbim-data:/data -e LLMBIM_API_KEY=secret llmbim
```

---

## Vercel

**Not recommended for the BIM API** (stateful FastAPI + filesystem/volume).

Use Vercel later only for a static marketing / docs site that links to the Railway API.

---

## Supabase (optional later)

Current store is **filesystem JSON** (simple, Railway volume).

To add Supabase later:

1. Table `projects (id text pk, name text, model jsonb, updated_at timestamptz)`
2. Implement `SupabaseProjectStore` behind the same `ProjectStore` interface
3. Env: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

Not required for first launch.

---

## Agent smoke script

```bash
# create demo
curl -s -X POST http://127.0.0.1:8000/v1/demo/simple-house | python -m json.tool

# list
curl -s http://127.0.0.1:8000/v1/projects | python -m json.tool
```

Python:

```python
from llmbim import Project
p = Project.create("Local")
p.add_level("L1", 0)
p.create_wall(level="L1", start=(0,0), end=(5000,0), thickness_mm=200, height_mm=3000)
p.export_plan("L1", "plan.svg")
```

---

## MCP (Claude desktop / Cursor)

```json
{
  "mcpServers": {
    "llm-bim": {
      "command": "llmbim",
      "args": ["mcp"]
    }
  }
}
```

Requires `pip install -e ".[mcp,server]"`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Import errors | `pip install -e ".[dev,server]"` from repo root |
| Empty projects after restart | Mount Railway volume at `/data` |
| 401 on API | Set/pass `LLMBIM_API_KEY` or leave unset for open local |
| Port bind | `llmbim serve --port 8001` |
