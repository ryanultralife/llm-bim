# NOW — Schad Revit → llm-bim transition (OPEN)

**Updated:** 2026-07-19 by Grok

## Human directive

> Transition away from Revit to our own llm-bim at the **same or better** quality and execution.

**Canonical review (work until resolved):**  
[`docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md`](../../docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md)

Status: **OPEN** until Gates A–D in that doc are complete. Do not treat shell pack as CDs.

## Claude — primary

1. Read the transition review end-to-end.
2. Claim **WP-SCHAD-S0** (then S1) in `TEAM_STATUS.md` — one package at a time preferred.
3. Work packages listed in `docs/WORK_PACKAGES.md` under **WP-SCHAD-***.
4. Start fixture: `examples/schad_garage.py` (loads basis; currently CMU types + no roofs).
5. SSOT source (portable only): `G:\My Drive\Schad Garage\Revit\schad_*.py` pure modules — **not** `Schad_*.py` Revit adapters.
6. Each PR: platform feature **and** Schad build/pack update; `ruff` + `mypy` + `pytest` + rebuild pack.
7. Leave handoff notes when stopping; update Gate checkboxes when criteria land.
8. **Continue until Gate D** (retire Revit workflow) or human redirects.

### First claim suggested

**WP-SCHAD-S0 + WP-SCHAD-S1** together if small enough: port SSOT into `projects/schad/`, register wood wall types, kill CMU mapping on Schad walls, rebuild pack.

## Grok

- Pushed this review + WP list + `examples/schad_garage.py` shell.
- Launch/CI/CLI help for `llmbim case schad` when Claude needs it (S8).
- Stay out of Claude’s claimed Schad freeze zones.

## Background (merged earlier)

PR #1 audit / IFC / drawings quality; MEP autoroute + rich viewer — see git history. CI gates ruff + mypy strict.

## Decentralized surface

- `skills/llm-bim/SKILL.md` · `llmbim ops --schema` · `docs/LOCAL.md` · MCP: `llmbim mcp`
