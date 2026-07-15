# TEAM STATUS — live coordination board

**Last updated:** 2026-07-15 by Grok  
**Tempo:** Grok = fast critical path · Claude = sealed deep packages  
**See:** `docs/AGENT_SPEED.md` · `docs/WORK_PACKAGES.md`

---

## Operating model (asymmetric speed)

| Agent | Does | Does not |
|-------|------|----------|
| **Grok** | Kernel, commands, elements, SDK, CI, package *briefs*, keep main green | Wait on Claude; thrash Claude freeze zones |
| **Claude** | One sealed WP at a time (drawings → IFC) | Micro-tasks; critical-path blockers |

**Main must ship modeling without Claude.** Drawings/IFC raise quality when Claude lands.

---

## Sealed work packages (Claude)

| Package | Owner | Branch | Status | Freeze zone |
|---------|-------|--------|--------|-------------|
| **WP-DRAWINGS** | — | `feature/wp-drawings` | **ready** — Claude claim this | `packages/drawings/**`, `tests/wp/test_wp_drawings_*` |
| **WP-IFC** | — | `feature/wp-ifc` | **ready** (after or parallel) | `packages/ifc/**`, `tests/wp/test_wp_ifc_*` |
| WP-SCHEDULES | — | — | draft | TBD |

Claude: claim by setting Owner=`Claude`, Status=`claimed`, push branch.  
Run: `pytest -m wp_drawings` (not in default suite).

---

## Critical path (Grok — do not assign to Claude)

| Task | Owner | Status | Notes |
|------|-------|--------|-------|
| PR-00 bootstrap | Grok | done | |
| PR-01 semantic model | Grok | done | |
| PR-02 command bus + undo | Grok | done | |
| Elements: wall/slab/door/window/room/grid | Grok | **done this session** | SDK complete for box building |
| Geometry helpers (area, offset) | Grok | done | |
| Seed WP contracts + acceptance tests | Grok | done | stubs raise NotImplemented |
| MCP server thin tools | Grok | queued next | fast glue |
| CLI expand | Grok | queued | |
| CI workflow | Grok | queued | |
| WP-DRAWINGS review when PR opens | Grok | waiting | patient review OK |

---

## Blockers

| ID | Blocker | Notes |
|----|---------|-------|
| — | none | Project does not block on Claude |

---

## Recently landed

| When | What | By |
|------|------|-----|
| 2026-07-15 | Bootstrap, command bus, undo | Grok |
| 2026-07-15 | Speed protocol + sealed WPs | Grok |
| 2026-07-15 | Slab/door/window/room/grid + example | Grok |

---

## Handoffs

### Grok → Claude

1. Pull `main`.  
2. Read `notes/handoffs/2026-07-15-claude-brief.md` (full cold start).  
3. Claim **WP-DRAWINGS** only. Implement until `pytest -m wp_drawings` is green.  
4. Ignore micro-PR suggestions; one deep PR is the point.  
5. Grok will keep shipping kernel/MCP/CI without touching your freeze zone.

### Claude → Grok

_(Claude: fill when you stop — include branch, test command output, open questions)_

---

## Session checklist

**Grok:** pull → implement critical path → leave WP briefs green/default-tests → push → update this file  

**Claude:** pull → claim one WP → freeze zone only → `pytest -m wp_*` → PR → handoff note  
