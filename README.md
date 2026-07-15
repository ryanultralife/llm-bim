# LLM-BIM

**Building Information Modeling operated entirely by LLMs.**

No drafting GUI. Agents (Grok, Claude, …) create and edit a real 3D BIM model through Python, CLI, and MCP tools. Drawings and IFC exports are derived from the model.

## Status

Early bootstrap / MVP foundation. See:

- [`docs/DESIGN.md`](docs/DESIGN.md) — architecture
- [`docs/PR_PLAN.md`](docs/PR_PLAN.md) — implementation DAG
- [`AGENTS.md`](AGENTS.md) — how Grok & Claude collaborate
- [`TEAM_STATUS.md`](TEAM_STATUS.md) — live task claims

## Install (dev)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Unix
source .venv/bin/activate

pip install -e ".[dev]"
pytest
```

## Quick taste (as APIs land)

```python
from llmbim import Project

p = Project.create("Demo House")
# ... agent-driven modeling via SDK / MCP ...
p.save("demo.llmbim.json")
```

## Principles

1. Model is source of truth  
2. LLM interface only (structured tools, not freeform geometry invention)  
3. IFC for interchange; JSON project file for git-friendly editing  
4. Multi-agent parallel development via STATUS claims  

## License

TBD
