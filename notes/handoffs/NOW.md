# NOW — active lanes (read every session)

**Updated:** 2026-07-15 by **Grok**  
**Claude status:** may be rate-limited / AFK — will rejoin when free. **IFC still reserved for Claude.**

**Rule:** If it is not in your lane, do not edit it.

---

## Grok continuing (Claude AFK)

| # | Work | Paths | Status |
|---|------|-------|--------|
| G1 | Launch stack | server, cli, mcp, docker, railway, CI | **done** on main |
| G2 | Validate + glTF + import/export API polish | `packages/core/validate.py`, `packages/geometry/mesh.py`, `packages/server/**`, SDK, CLI | **done** (15 tests) |
| G3 | Keep `main` green; deploy docs | tests, LAUNCH | ongoing |
| G4 | **NOT** implementing IFC | `packages/ifc/**` | **reserved for Claude** |

When Claude returns: Grok will not have touched IFC. Claude claims WP-IFC as before.

---

## Claude when free (unchanged assignment)

### Claim **WP-IFC**

| Field | Value |
|-------|--------|
| Branch | `feature/wp-ifc` |
| Freeze | `packages/ifc/**`, `tests/wp/test_wp_ifc_*.py` |
| DoD | `pytest -m wp_ifc` green with ifcopenshell |
| Contract | `export_ifc(model, path)` signature stay stable |

### Do not touch (Grok)

```
packages/server/**  packages/cli/**  packages/mcp_server/**
packages/core/**    packages/geometry/**
Dockerfile  railway.toml  .github/**
```

### Re-entry checklist for Claude

1. `git pull origin main`  
2. Read this file + `TEAM_STATUS.md`  
3. Claim WP-IFC if still open  
4. Implement IFC only  
5. If you need `POST /exports/ifc`, leave a handoff — Grok will wire the one-liner  

---

## Collaboration shape while Claude is away

Grok ships launch quality (validate, glTF review mesh, API).  
Claude’s IFC package stays empty stubs so no merge conflict when they return.
