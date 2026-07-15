# AGENTS.md — Multi-agent collaboration (Grok + Claude)

This repository is built **by LLMs, for LLMs**. There is no human drafting UI.
Humans review exports (IFC, PDF, SVG, glTF) and drive agents via chat/CLI.

## Tempo (read this first)

**Claude is much slower than Grok.** That is intentional leverage — see
[`docs/AGENT_SPEED.md`](docs/AGENT_SPEED.md).

| | Grok | Claude |
|--|------|--------|
| Role | Fast path: kernel, unblock, integrate, keep `main` green | Deep path: sealed packages (drawings, IFC, hard correctness) |
| Work unit | Small commits anytime | **One** sealed package from [`docs/WORK_PACKAGES.md`](docs/WORK_PACKAGES.md) |
| Waiting | **Never** wait on Claude for critical path | Needs complete briefs; zero chat dependency |

## Team

| Agent | Role | How you identify yourself |
|-------|------|---------------------------|
| **Grok** (xAI) | Critical path + package briefs + freeze zones | Commit prefix `[grok]` |
| **Claude** (Anthropic) | Sealed work packages only while claimed | Commit prefix `[claude]` |

Prefer merging Grok small PRs continuously; Claude lands larger isolated PRs.

## Communication protocol (through the repo only)

1. **Read first** (every session start):
   - `TEAM_STATUS.md` — live claims, blockers, next actions
   - `docs/DESIGN.md` — architecture source of truth
   - `docs/PR_PLAN.md` — ordered PR DAG and ownership
   - Open PRs / issues on GitHub

2. **Claim work** before coding:
   - Edit `TEAM_STATUS.md`: set your name, task ID, branch, status=`in_progress`
   - Do not claim a task already `in_progress` by the other agent
   - Prefer tasks marked for your agent; `either` tasks are free if unclaimed

3. **Leave handoffs** when you stop:
   - Update `TEAM_STATUS.md` with what landed, what's next, blockers
   - Write `notes/handoffs/YYYY-MM-DD-<agent>.md` for non-trivial context
   - Never rely on chat history the other agent cannot see

4. **PRs are the integration surface**:
   - One PR ≈ one PR-plan item when possible
   - Title format: `PR-XX: short title`
   - Description must list files touched and tests run
   - Do not force-push `main`

## Hard product rules

1. **No human drafting frontend.** Headless exports only (IFC, glTF, SVG, PDF).
2. **Model is source of truth.** Drawings are derived views.
3. **LLMs never invent geometry without the kernel.** All mutations go through validated API commands.
4. **Units:** millimeters internally unless a project sets otherwise; API accepts explicit units.
5. **IDs:** stable ULIDs/UUIDs on every element; never reuse deleted IDs.
6. **Git-friendly project JSON** is primary editable store; IFC is interchange + validation target.

## Code ownership (soft — reduce merge conflicts)

| Package / path | Prefer owner | Notes |
|----------------|--------------|-------|
| `packages/core/` | Grok | Semantic model, transactions, commands |
| `packages/geometry/` | Grok | Solids, extrusions, openings |
| `packages/drawings/` | Claude | Plans/sections/elevations, SVG/PDF |
| `packages/ifc/` | Claude | IFC import/export via ifcopenshell |
| `packages/sdk/` | either | Thin public Python API over core |
| `packages/mcp_server/` | either | MCP tools for Grok/Claude clients |
| `packages/cli/` | either | `llmbim` CLI |
| `tests/` | whoever owns code under test | Golden files need careful merges |
| `examples/` | either | Scripted buildings |
| `docs/` | either | Design changes: discuss in STATUS first |
| `AGENTS.md`, `TEAM_STATUS.md` | either | Always update STATUS when claiming |

If you must edit outside your lane, claim it in STATUS and keep the diff minimal.

## Branch & PR conventions

```
main                 # always green; protected by tests
feature/PR-01-...    # matches docs/PR_PLAN.md IDs
```

- Rebase or merge main before opening PR
- Keep PRs reviewable in < ~400 LOC when practical
- CI must pass: `pytest`, `ruff`, typecheck

## Local setup (Windows / cross-platform)

```bash
cd llm-bim
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix:    source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Definition of done (any PR)

- [ ] Tests added/updated for new behavior
- [ ] No human-UI code introduced
- [ ] Public API changes reflected in `packages/sdk` + MCP tool schemas if applicable
- [ ] `TEAM_STATUS.md` updated
- [ ] Commit messages prefixed with agent tag

## Conflict resolution

1. Prefer the agent who claimed the file in STATUS
2. If both edited: later PR rebases; keep both intents if possible
3. Architecture disputes: update DESIGN with a short ADR in `docs/adrs/` and note in STATUS for the human if still blocked
