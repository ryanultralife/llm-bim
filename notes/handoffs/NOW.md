# NOW — active lanes (read every session)

**Updated:** 2026-07-15 by **Grok**  
**Claude status:** may be rate-limited / AFK — will rejoin when free. **IFC still reserved for Claude.**

**Rule:** If it is not in your lane, do not edit it.

---

## Grok continuing (Claude AFK)

| # | Work | Paths | Status |
|---|------|-------|--------|
| G1 | Launch stack | server, cli, mcp, docker, railway, CI | **done** on main |
| G2 | Validate + glTF + import/export API polish | `packages/core/validate.py`, `packages/geometry/mesh.py`, `packages/server/**`, SDK, CLI | **done** |
| G3 | **INTEC site + Proto10 separator test cases** | `examples/intec_site.py`, `examples/proto10_separator.py`, equipment box cmd, plan equip draw | **this session** |
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
5. **Good fixtures for IFC tests:** `examples/output/intec/intec_site.llmbim.json` and `examples/output/proto10/proto10_separator.llmbim.json` (run `python examples/intec_site.py` / `proto10_separator.py` first)  
6. If you need `POST /exports/ifc`, leave a handoff — Grok will wire the one-liner  

### Do not re-author

- INTEC arrangement (Grok owns `examples/intec_site.py` unless you claim a docs-only fix)  
- Proto10 envelopes (`examples/proto10_separator.py`) — improve IFC mapping, not re-layout  


---

## Collaboration shape while Claude is away

Grok ships launch quality (validate, glTF review mesh, API).  
Claude’s IFC package stays empty stubs so no merge conflict when they return.
