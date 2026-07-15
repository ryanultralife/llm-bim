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
| PR-00 Bootstrap monorepo + coordination | **Grok** | `main` | `done` | DESIGN, PR plan, packages, 3 smoke tests green |
| PR-01 Core semantic model (harden) | **Grok** | next | `queued` | Base model exists; next: commands package layout, migrate.py, grids type |
| PR-02 Transaction / command bus | Grok (planned) | — | `queued` | Depends PR-01 |
| PR-03 Geometry extrusions + openings | Grok (planned) | — | `queued` | Depends PR-01; primitives started |
| PR-04 Levels, grids polish | **Claude** (suggested) | — | `available` | Levels work; claim grids + level API tests |
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

### Grok → Claude (2026-07-15)

- **Pull `main` immediately.** Coordination protocol is live.
- Read order: `AGENTS.md` → `TEAM_STATUS.md` → `docs/DESIGN.md` → `docs/PR_PLAN.md`
- Working code today:
  - `Project.create/open/save`, `add_level`, `create_wall`, `query`, `stats`
  - `examples/simple_house.py` builds a 10×8 m box
  - Tests: `pytest` → 3 passed
- **Your best first claims:**
  1. Review DESIGN; leave notes in `notes/handoffs/2026-07-15-claude.md` if you disagree
  2. **PR-04:** grids + richer level helpers/tests (don't rewrite wall model)
  3. Or **slabs** on a branch after claiming PR-05 in this file
- Soft ownership: Claude → **drawings + IFC**; Grok → **core commands + geometry**
- **No human drafting GUI.** Exports only.
- Communicate via: this file, `notes/handoffs/`, commits, PRs, GitHub issues.

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
