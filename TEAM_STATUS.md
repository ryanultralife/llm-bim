# TEAM STATUS — live coordination board

**Last updated:** 2026-07-19 by **Grok** (Schad Revit→llm-bim transition review OPEN for Claude)  
**Canonical “who does what right now”:** [`notes/handoffs/NOW.md`](notes/handoffs/NOW.md) ← **read first**  
**Schad transition review (OPEN until Gate D):** [`docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md`](docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md)

Also: `docs/AGENT_SPEED.md` · `docs/WORK_PACKAGES.md` · `docs/LAUNCH.md`

---

## Lanes (no overlap)

| Agent | Owns now | Next | Stay out of |
|-------|----------|------|-------------|
| **Claude** | **WP-SCHAD-*** series — claim S0 first | Work until Gate D in transition review | Unrelated freezes only if claimed |
| **Grok** | Launch/CI/CLI assist for Schad case; review PRs | `llmbim case schad` when S8 | Claude’s claimed Schad freeze paths |

**Rule:** One agent per freeze zone. Claim in this file before coding. Announce next step in `notes/handoffs/NOW.md` when you change direction.

---

## Active claims

| ID | Owner | Branch | Status | Freeze / paths |
|----|-------|--------|--------|----------------|
| **WP-SCHAD-S0** | **Claude** (to claim) | — | **ready** | `projects/schad/**`, `examples/schad_*.py` |
| **WP-SCHAD-S1** | **Claude** (to claim) | — | **ready** | `types_catalog.py`, set_type / `annotations.py` |
| **WP-SCHAD-S2…S8** | Claude | — | **ready** | see WORK_PACKAGES.md + transition doc |
| LAUNCH | Grok | `main` | **done** | server/cli/mcp/docker |
| WP-IFC / drawings / MEP / viewer | Claude | `main` | **done** | prior PRs |

### Claude claim recipe

```
| WP-SCHAD-S0 | Claude | feature/wp-schad-s0 | claimed | projects/schad/** examples/schad_*.py |
```

Then implement until Gate criteria + tests pass. Update this table when claiming.

---

## Grok → Claude (this handoff)

1. **Read** `docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md` — full gap analysis, gates, APIs, not-to-do.  
2. **Do not** port Revit API scripts; port pure `schad_*.py` basis only.  
3. **Do not** leave Schad on `W-EXT-CMU` after S1.  
4. Shell starter: `examples/schad_garage.py` (already loads G: basis).  
5. Work **until Gate D** or human says stop.  
6. Rebuild pack every meaningful PR; print OPEN_* paths.

## Claude → Grok reply slot

```
Branch: …
Claimed: WP-SCHAD-S…
Done: …
Blocked: …
Need from Grok: …
```
