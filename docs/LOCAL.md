# Run on your machine (local-first)

No Railway, Vercel, or API key required for modeling.

## 5-minute setup

```bash
git clone https://github.com/ryanultralife/llm-bim.git
cd llm-bim
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev,server]"
pytest -q
llmbim version
```

## Connect any LLM

### Option A — MCP (recommended)

Point Claude Desktop, Cursor, or any MCP client at:

```json
{
  "mcpServers": {
    "llm-bim": {
      "command": "llmbim",
      "args": ["mcp"],
      "cwd": "/absolute/path/to/llm-bim"
    }
  }
}
```

Load the skill: `skills/llm-bim/SKILL.md` (or copy into your agent’s skill folder).

### Option B — CLI only

You (or the agent) run shell commands: `llmbim template`, `import`, `pack`, etc.

### Option C — Python in the agent’s sandbox

```python
from llmbim import Project
p = Project.from_template("warehouse")
p.export_deliverables("out")
```

### Option D — Optional local HTTP

```bash
llmbim serve --port 8000
# open http://127.0.0.1:8000/docs
```

Still on localhost — not a required cloud.

## Op catalog for tool-calling models

```bash
llmbim ops --json > skills/llm-bim/ops.schema.json
# or
llmbim ops --schema
```

Regenerate after pulling new versions so tools stay in sync.

## Real fixtures

```bash
python scripts/verify_all.py
# → examples/output/intec  (facility)
# → examples/output/proto10 (equipment)
```

Open `examples/output/intec/index.html` in a browser to review (no install UI).

## Viewing a pack (one tab, durable serve)

```bash
llmbim view output/<slug>          # serves the pack on 127.0.0.1, prints the
                                   # URL, opens exactly ONE tab; Ctrl-C stops
llmbim view output/<slug> --print-only   # agents: just the URL
llmbim case intec --open-viewer          # build then view in one step
```

Small models embed their 3D data, so double-clicking `viewer3d.html`
(`file://`) also works offline. Packs whose glTF exceeds ~3.5 MB fetch
`model.gltf` instead — those need the HTTP serve above (`file://` cannot
fetch; the viewer's error banner says exactly this). Never open
`index.html` and `viewer3d.html` in separate tabs — `index.html` links
the 3D studio.

## Decentralized product shape

| You provide | They provide |
|-------------|--------------|
| Kernel (`pip install`) | Their LLM (Grok, Claude, local, …) |
| Skill pack (`skills/llm-bim`) | Their MCP client / IDE |
| Schemas & recipes | Their project files on disk |

You host: GitHub + package docs. They host: their models and data.
