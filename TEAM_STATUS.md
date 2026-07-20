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
| **WP-SCHAD-S0+S1** | **Claude** | `claude/grok-audit-evolution-w4umwh` | **claimed** | `projects/schad/**`, `examples/schad_*.py`, `types_catalog.py`, set_type sync |
| **WP-SCHAD-S2…S8** | **Claude** | `claude/grok-audit-evolution-w4umwh` | **queued** (S2+S5 next, then S3+S4, S6..S8) | see WORK_PACKAGES.md + transition doc |
| GROK-SSOT-P0/P1/P2 | Claude | `main` (PR #7) | **done** | strict glTF VERIFY + llmbim view, place_tube/place_wire_path/material map/nps, DevicePack + fixture + recipe, viewer presets/auto-rotate/embed-auto |
| LAUNCH / LAUNCH-POLISH | Grok | `main` | **done** | server/cli/mcp/docker |
| WP-IFC / WP-DRAWINGS-V2 / AUDIT-2026-07 | Claude | `main` (PR #1) | **done** | see git history |
| WP-MEP-ROUTE / WP-VIEWER-RICH | Claude | `main` (PR #2) | **done** | autoroute; glTF extras + inspect/filters/measure |
| WP-MEP-TAP / WP-IFC-IMPORT / WP-MEP-SIZING | Claude | `main` (PR #3) | **done** | tee-tapping; round-trip import; hydraulic sizing |
| Drawing sets + drafting sheets + EQ/N/C/H parity | Claude | `main` (PR #4/#5/#7) | **done** | plan vs construction; CD title blocks; discipline emitters |
| auto_place / import_primitives | Claude | `main` (PR #7) | **done** | requirements-driven placement; dataset ingest |
| core/commands/elements | Grok | `main` | **done** | Claude: do not reimplement |

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
