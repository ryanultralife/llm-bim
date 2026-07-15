# Claude cold-start brief (updated — no overlap with Grok)

**Read first:** [`NOW.md`](NOW.md) then [`TEAM_STATUS.md`](../../TEAM_STATUS.md)

You are **slow and deep**. Grok is **fast and owns launch/API**. Do not redo Grok’s work.

## Your assignment (only this)

### Claim **WP-IFC**

| | |
|--|--|
| Branch | `feature/wp-ifc` |
| Freeze | `packages/ifc/**`, `tests/wp/test_wp_ifc_*.py` |
| API to implement | `export_ifc(model: ProjectModel, path: str \| Path) -> None` in `packages/ifc/llmbim_ifc/export.py` |
| Prove | `pip install -e ".[dev,ifc]"` then `pytest -m wp_ifc` |
| Do not edit | `packages/server/**`, `cli/**`, `mcp_server/**`, `core/**`, `geometry/**`, Docker, Railway, CI |

### Optional later (not first)

**WP-DRAWINGS-V2** — improve symbols/goldens in `packages/drawings/**`. MVP already works on main. Prefer IFC first.

## Already done (Grok) — do not rebuild

- Semantic model + command bus + undo  
- Walls, slabs, doors, windows, rooms, grids  
- Plan / section / elevation SVG (MVP)  
- FastAPI (`llmbim serve`), review pages, demo endpoint  
- CLI / MCP / Docker / Railway docs  

Pull latest `main` so you see all of that.

## Claim steps

```bash
git pull origin main
git checkout -b feature/wp-ifc
# edit TEAM_STATUS.md → WP-IFC claimed by Claude
git add TEAM_STATUS.md notes/handoffs/NOW.md  # if you update NOW
git commit -m "[claude] claim WP-IFC"
# implement packages/ifc only
pytest -m wp_ifc
```

## Need something outside freeze zone?

Write `notes/handoffs/YYYY-MM-DD-claude.md` with:

```
Need from Grok: e.g. POST /v1/projects/{id}/exports/ifc wiring
```

Do not implement it yourself in server.

## Product rules (unchanged)

- No human drafting UI  
- Model source of truth  
- Mutations only via validated commands/SDK  
