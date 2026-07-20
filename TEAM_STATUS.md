# TEAM STATUS — live coordination board

**Last updated:** 2026-07-20 by **Claude** (WP-SCHAD S0–S8 done + merged; WP-CD-ANATOMY in flight)  
**Canonical “who does what right now”:** [`notes/handoffs/NOW.md`](notes/handoffs/NOW.md) ← **read first**  
**Schad transition review (OPEN pending human sign-off vs `docs/CD_COMPLETENESS_STANDARD.md`):** [`docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md`](docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md)

Also: `docs/AGENT_SPEED.md` · `docs/WORK_PACKAGES.md` · `docs/LAUNCH.md`

---

## Lanes (no overlap)

| Agent | Owns now | Next | Stay out of |
|-------|----------|------|-------------|
| **Claude** | **WP-CD-ANATOMY** (drawings: plan/construction + section/layout/sheets) | Close remaining `CD_COMPLETENESS_STANDARD.md` gap rows | Unrelated freezes only if claimed |
| **Grok** | Review merged PRs #8–#14; INTEC adoption of custom register/units | Eigen-side `trl_evidence` links | Claude’s claimed drawings freeze paths |

**Rule:** One agent per freeze zone. Claim in this file before coding. Announce next step in `notes/handoffs/NOW.md` when you change direction.

---

## Active claims

| ID | Owner | Branch | Status | Freeze / paths |
|----|-------|--------|--------|----------------|
| **WP-SCHAD-S0+S1** | **Claude** | `claude/grok-audit-evolution-w4umwh` | **done** (`bbd93b1`) | repo-first harness + residential types; 16 walls retyped, zero CMU |
| **WP-SCHAD-S2** | **Claude** | `claude/grok-audit-evolution-w4umwh` | **done** (`f45619b`) | roofs.py gable/shed/freeform → mesh/sections/IFC/MCP |
| **WP-SCHAD-S5** | **Claude** | `claude/grok-audit-evolution-w4umwh` | **done** (`8ea8312`) | custom `sheets=[...]` register + detail_ops DSL (D01–D12 render) |
| **WP-SCHAD-S3** | **Claude** | `claude/grok-audit-evolution-w4umwh` | **done** (`af515f3`) | foundations.py: footings/stem/slabs + rebar_schedule → mesh/sections/IFC/MCP |
| **WP-SCHAD-S4** | **Claude** | `claude/grok-audit-evolution-w4umwh` | **done** (`55d655b`) | W16x40 + HSS6x6 catalogs, HDR/SSW types + schedule, multi-plate rule fix |
| **WP-SCHAD-S6** | **Claude** | `claude/grok-audit-evolution-w4umwh` | **done** (`8f834a3`) | full content build (127 el) + Gate C 21-sheet register |
| **WP-SCHAD-S7** | **Claude** | `claude/grok-audit-evolution-w4umwh` | **done** (`2395d34`) | imperial units + door/window tags across renderers |
| **WP-SCHAD-S8** | **Claude** | `claude/grok-audit-evolution-w4umwh` | **done** (`cb9845e`) | `llmbim case schad`, CI drift guards, schad_cd recipe, retire-Revit record |
| **WP-CD-ANATOMY** | **Claude** | `claude/grok-audit-evolution-w4umwh` | **claimed** (2 agents in flight) | close `docs/CD_COMPLETENESS_STANDARD.md` gap rows — A: plan.py+construction.py (dim-chain tiers, fractional grids, tag anatomy, key plan); B: section.py+layout.py/sheets.py (line weights, material hatch, poché split, rev clouds, stamp block) |
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
Branch: claude/grok-audit-evolution-w4umwh (merging to main)
Claimed: WP-SCHAD-S0..S8 — ALL DONE
Done: Gate A 6/6, Gate B 4/4, Gate C met (21-sheet register),
      Gate D 5/6. Golden command: `llmbim case schad` →
      output/schad_garage/index.html, VERIFY_OK, exit!=0 on fail.
      411 tests / ruff / mypy strict / verify_all all green.
      Recipe: skills/llm-bim/recipes/schad_cd.md
      Decision record: docs/RETIRING_REVIT_SCHAD.md
Blocked: nothing
Need from Grok: nothing code-side. Remaining Gate D box is the HUMAN
      side-by-side vs sheet_renders/ — Ryan reviews, then Revit
      archives per RETIRING_REVIT_SCHAD.md.
```
