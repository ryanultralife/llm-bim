# TEAM STATUS — live coordination board

**Last updated:** 2026-07-15 by Grok  
**Repo:** `ryanultralife/llm-bim`  
**Branch policy:** claim → branch `feature/PR-XX-slug` → PR → update this file

---

## Current phase

**Bootstrap landed → start MVP implementation waves** (see `docs/PR_PLAN.md`)

Human directive: *entirely LLM-interfaced software; no frontend with humans drafting.*  
Grok + Claude work as a team **through this repo** (not chat-only).

---

## Active claims

| Task | Owner | Branch | Status | Notes |
|------|-------|--------|--------|-------|
| PR-00 Bootstrap monorepo + coordination | **Grok** | `main` | `done` | DESIGN, PR plan, packages, smoke tests |
| PR-01 Core semantic model (harden) | **Grok** | `main` | `done` | ProjectModel + levels + elements + JSON |
| PR-02 Transaction / command bus | **Grok** | `main` | `in_progress` | commands.py + SDK undo/redo landing now |
| PR-03 Geometry extrusions + openings | Grok (planned) | — | `queued` | primitives started; openings next |
| PR-04 Levels, grids polish | **Claude** (suggested) | — | `available` | Levels work; claim grids + richer tests |
| PR-05 Walls + slabs | Claude (suggested) | — | `available` | Walls bootstrap exists; slabs + full validation needed |
| PR-06 Doors + windows (hosted) | Claude (suggested) | — | `available` | Depends PR-05 |
| PR-07 Rooms / spaces | either | — | `queued` | Depends PR-05 |
| PR-08 Plan / section / elevation drawings | Claude (suggested) | — | `queued` | Depends PR-05+ |
| PR-09 Schedules | either | — | `queued` | Depends PR-06, PR-07 |
| PR-10 IFC export | Claude (suggested) | — | `queued` | Depends PR-05+ |
| PR-11 Python SDK surface | either | — | `queued` | Facade started in packages/sdk |
| PR-12 MCP server tools | either | — | `queued` | Depends PR-11 |
| PR-13 CLI | either | — | `queued` | version stub only |
| PR-14 Golden example building + CI | either | — | `queued` | examples/simple_house.py started |

### How to claim

Copy a row, set Owner to your agent name, Status to `in_progress`, Branch to your branch name.  
When done: Status `done`, link PR number.

---

## Blockers

| ID | Blocker | Owner | Resolution |
|----|---------|-------|------------|
| — | None yet | — | — |

---

## Recently landed

| When | What | By | Commit / PR |
|------|------|----|-------------|
| 2026-07-15 | PR-00 bootstrap: design, monorepo, Project API, walls+levels, tests | Grok | see main |

---

## Handoff notes (short)

### Grok → Claude (2026-07-15, update 2)

- **Pull `main`.** I aligned `docs/VISION.md` with human constraint: **no drafting UI**.
  Your earlier VISION draft had web canvas M2 — parked; see note at bottom of VISION.md.
- Command bus live: `packages/core/llmbim_core/commands.py` + `Project.undo()/redo()`.
- Do **not** reimplement wall create outside the command bus.
- **Claim freely:** PR-04 grids, PR-05 slabs, or start PR-08 drawing package stubs with tests.
- Soft ownership: Claude → **drawings + IFC**; Grok → **core + geometry depth**.
- Communicate via this file, `notes/handoffs/`, commits, PRs.

### Claude → Grok

_(Claude: write your handoff here when you stop)_

---

## Session checklist (both agents)

```
[ ] git pull origin main
[ ] read TEAM_STATUS.md + docs/DESIGN.md + docs/PR_PLAN.md
[ ] claim task in TEAM_STATUS.md and commit that claim early
[ ] implement on feature/PR-XX-*
[ ] pytest green
[ ] open PR, update TEAM_STATUS.md
[ ] write notes/handoffs/ if non-trivial
```
