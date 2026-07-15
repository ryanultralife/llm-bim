# LLM-BIM

**Point any coding agent at this repo. Chat. Get real drawings and models in a local folder.**

No drafting GUI. No required cloud host. Your LLM (Claude, Grok, Cursor, local, …) drives a deterministic BIM **kernel** on your machine. Output lands under `./output/`.

[![CI](https://github.com/ryanultralife/llm-bim/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanultralife/llm-bim/actions/workflows/ci.yml)

## 60-second start

```bash
git clone https://github.com/ryanultralife/llm-bim.git
cd llm-bim

# Windows
.\scripts\install_local.ps1
# macOS / Linux
bash scripts/install_local.sh
```

Then open this folder in **Claude Code / Cursor / Grok / any agent** and say something like:

> Read `CLAUDE.md` and `skills/llm-bim/SKILL.md`. Create a two-story office building and write all drawings and models to `output/demo_office/`.

Or without an agent UI:

```bash
llmbim template office_bay --out output/demo_office
# open output/demo_office/index.html
```

## What you get in `output/.../`

| File / folder | Contents |
|---------------|----------|
| `model.llmbim.json` | BIM source of truth |
| `model.ifc` | IFC4 coordination model |
| `model.step` | 3D solids (assembly) |
| `model.gltf` | 3D review mesh |
| `construction/` or `parts/` | SVG drawing sheets |
| `PLOT_SET.pdf` | Multi-page plot set |
| `views/*.dxf` | CAD handoff |
| `boq.json` | Quantities + CSI cost codes |
| `clash_report.json` / `design_rules.json` | Coordination checks |
| `index.html` | Clickable review index |
| `deliverables.zip` | Whole pack |

## Chat / agent setup

| File | Role |
|------|------|
| **[`CLAUDE.md`](CLAUDE.md)** | Drop-in instructions when the agent is pointed at the repo |
| **[`skills/llm-bim/SKILL.md`](skills/llm-bim/SKILL.md)** | Full portable skill (any product that supports skills) |
| **[`skills/llm-bim/ops.schema.json`](skills/llm-bim/ops.schema.json)** | Tool catalog (`llmbim ops --schema`) |
| **[`docs/LOCAL.md`](docs/LOCAL.md)** | Local-first + MCP wiring |

### MCP (Claude Desktop, Cursor, etc.)

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

See `skills/llm-bim/mcp.example.json`.

## Common commands

```bash
llmbim template --list
llmbim template warehouse --out output/warehouse
llmbim case intec                    # full facility fixture
llmbim case proto10                  # equipment fixture
llmbim import drawing.dxf --out output/from_dxf --pack
llmbim import-step part.step --level L1 --out output/part
llmbim pack model.llmbim.json --out output/pack
llmbim boq output/pack/model.llmbim.json
llmbim clash output/pack/model.llmbim.json
llmbim rules output/pack/model.llmbim.json -v
llmbim serve --port 8000             # optional local review API
```

## Python (what agents usually run)

```python
from pathlib import Path
from llmbim import Project

out = Path("output/my_project")
p = Project.create("My Project")
p.add_level("L1", 0)
p.create_rect_shell(
    level="L1", x=0, y=0, w=12000, d=9000,
    height_mm=3500, thickness_mm=200, name_prefix="B",
)
p.create_room(
    level="L1", name="Open office",
    boundary=[(0, 0), (12000, 0), (12000, 9000), (0, 9000)],
)
man = p.export_deliverables(out)
print(out.resolve(), "ok=", man.get("ok"))
```

## Architecture (why this works in chat)

```text
You ──chat──► Agent (any LLM)
                 │  reads CLAUDE.md / skill
                 │  runs Python / CLI / MCP
                 ▼
            llm-bim kernel (local)
                 │
                 ▼
            ./output/<project>/   drawings · models · BOQ · PDF
```

The LLM **orchestrates**. The kernel **owns geometry, IDs, validation, and files**.

## Docs

| Doc | Topic |
|-----|--------|
| [LOCAL.md](docs/LOCAL.md) | Install, MCP, offline |
| [CAPABILITY.md](docs/CAPABILITY.md) | What you can throw at it |
| [HONESTY.md](docs/HONESTY.md) | What “done” means |
| [BUILDER_DESIGNER.md](docs/BUILDER_DESIGNER.md) | Builder vs designer flows |
| [DEPTH_PASSES.md](docs/DEPTH_PASSES.md) | STEP/PDF/CSI/import details |

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, point agents at it.
