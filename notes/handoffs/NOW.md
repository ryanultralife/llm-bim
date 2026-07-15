# NOW — active lanes (read every session)

**Updated:** 2026-07-15 by **Grok**  
**Rule:** If it is not in your lane, do not edit it. Collaborate via STATUS + this file, not by “helping” in the other agent’s tree.

---

## Grok is doing next (my lane — do not parallel)

| # | Work | Paths I will touch | Status |
|---|------|--------------------|--------|
| G1 | Finish **launch stack** on `main` | `packages/server/**`, `packages/cli/**`, `packages/mcp_server/**`, `Dockerfile`, `railway.toml`, `.github/**`, `docs/LAUNCH.md`, `README.md`, `pyproject.toml`, `tests/unit/test_api.py` | **in progress → commit now** |
| G2 | Keep API green / deploy docs | same as G1 + `docs/LAUNCH.md` | after G1 |
| G3 | Optional thin SDK glue only if launch broken | `packages/sdk/llmbim/__init__.py` (export helpers only) | only if needed |
| G4 | **Not** deepening drawings quality | — | stopped after MVP |

**Grok will NOT touch while Claude works:**

- `packages/ifc/**` (Claude’s primary next package)
- New golden drawing refactors under Claude’s claim (see below)
- Claude’s feature branches

---

## Claude should do next (your lane — Grok will stay out)

### Primary claim: **WP-IFC** (recommended)

| Field | Value |
|-------|--------|
| Package | WP-IFC |
| Branch | `feature/wp-ifc` |
| Freeze zone | `packages/ifc/**`, `tests/wp/test_wp_ifc_*.py`, `tests/golden/ifc/**` (if you add) |
| DoD | `pip install -e ".[ifc]"` then `pytest -m wp_ifc` green; IFC opens in ifcopenshell |
| Contract | `packages/ifc/llmbim_ifc/export.py` → `export_ifc(model, path)` — **keep signature** |

### Optional later (only after IFC or if you prefer drawings polish)

| Field | Value |
|-------|--------|
| Package | WP-DRAWINGS-V2 (quality pass) |
| Branch | `feature/wp-drawings-v2` |
| Freeze zone | `packages/drawings/**` **except** do not break public API in `api.py` |
| Scope | Better door/window symbols, section accuracy, golden SVGs, docs in module |
| Note | **MVP drawings already ship on main** (Grok). Do not rewrite from zero — improve. |

### Claude must NOT touch (Grok owns)

```
packages/server/**
packages/cli/**
packages/mcp_server/**
packages/core/**
packages/geometry/**
Dockerfile
railway.toml
.github/**
docs/LAUNCH.md
```

If you need a server hook for IFC export, **write a handoff note** asking Grok to add one line of glue — do not rewrite the FastAPI app.

---

## How to claim (Claude)

1. `git pull origin main`
2. Edit `TEAM_STATUS.md`: set WP-IFC Owner=`Claude`, Status=`claimed`, Branch=`feature/wp-ifc`
3. Commit that STATUS change first on your branch
4. Implement only freeze zone
5. When done: PR + update STATUS + short note under `notes/handoffs/`

---

## Collaboration shape

```
        ┌─────────────┐
        │    main     │  always shippable modeling + API
        └──────┬──────┘
               │
     ┌─────────┴─────────┐
     │                   │
 Grok launch/API      Claude IFC
 (server, deploy)     (packages/ifc)
     │                   │
     └─────────┬─────────┘
               │ merge when green
```

No overlapping PRs on the same files. If conflict risk appears, **STATUS wins** — the claimed freeze zone owner keeps the files.

---

## Already on / landing with Grok (context for Claude)

- Kernel: levels, grids, walls, slabs, doors, windows, rooms, undo/redo
- Drawings MVP: plan / section / elevation SVG
- Schedules CSV/JSON helpers
- FastAPI agent API + read-only review pages
- CLI: `llmbim demo | serve | mcp`
- Docker + Railway + CI scaffolding

Claude does **not** need to re-build any of that.
