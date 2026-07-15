# NOW — decentralized skill + continued features

**Updated:** 2026-07-15 by Grok

## Shipped

### Decentralized product surface
- `skills/llm-bim/SKILL.md` — portable agent instructions (any LLM)
- `llmbim ops --schema` → `skills/llm-bim/ops.schema.json`
- `docs/LOCAL.md` + `scripts/install_local.ps1` / `.sh`
- MCP server simplified for offline clients
- Recipes under `skills/llm-bim/recipes/`

### Features continued
- Assemblies + **design options** (clone elements)
- Registry ops: ql, add_level, create_assembly, export_pack, design_option, catalog
- Universal import/export/query/script stack (prior commits)

## Claude / any agent on a user device

1. `scripts/install_local.*`
2. Load `skills/llm-bim/SKILL.md`
3. MCP: `llmbim mcp` (see mcp.example.json)
4. Work offline; optional `llmbim serve` only for local review UI
