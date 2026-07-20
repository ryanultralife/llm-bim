# AGENTS.md — Multi-agent collaboration + decentralized use

This repository is built **by LLMs, for LLMs**. There is no human drafting UI.
Humans review exports (IFC, PDF, SVG, glTF) and drive agents via chat/CLI.

## Decentralized skill (any LLM on any machine)

| Artifact | Path |
|----------|------|
| **Skill (primary)** | [`skills/llm-bim/SKILL.md`](skills/llm-bim/SKILL.md) |
| **Op schema** | `llmbim ops --schema` → `skills/llm-bim/ops.schema.json` |
| **Recipes** | [`skills/llm-bim/recipes/`](skills/llm-bim/recipes/) |
| **Local install** | [`docs/LOCAL.md`](docs/LOCAL.md) · `scripts/install_local.ps1` |
| **MCP example** | [`skills/llm-bim/mcp.example.json`](skills/llm-bim/mcp.example.json) |

Users run the **kernel on their device** and point **their** LLM (Grok, Claude, Gemini, local, …) at the skill + MCP. Hosting is optional.

**The agent needs shell + Python execution** (an agentic CLI, IDE agent, or
MCP client) — a browser-only chat cannot run the kernel and therefore cannot
produce output. This is a harness requirement, not a model-capability tier.
Entry context files per harness: `CLAUDE.md` (Claude Code), `GEMINI.md`
(Gemini CLI), this file (`AGENTS.md` — Codex/Grok and the shared protocol).
No local machine needed — see [`docs/MOBILE.md`](docs/MOBILE.md) for
phone-only paths (Claude Code web, `@gemini-cli` Actions trigger, Jules,
Codespaces).

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

## Operating principle: autonomy inside gates

Each agent picks its own method — the repo prescribes **outcomes**, not steps.
Recipes (`skills/llm-bim/recipes/`) are proven patterns, not mandates. What is
non-negotiable is the gate set: CI (`pytest` / `ruff` / `mypy` /
`scripts/verify_all.py`), `verify_pack` on every deliverable, drift-pin tests
on golden cases, and the honesty rules (traceable numbers, flagged
assumptions, no PE claims). Work that passes the gates stands on its own;
work that doesn't isn't done, regardless of how it was produced.

## Hard product rules

1. **No human drafting frontend.** Headless exports only (IFC, glTF, SVG, PDF).
2. **Model is source of truth.** Drawings are derived views.
3. **LLMs never invent geometry without the kernel.** All mutations go through validated API commands.
4. **Units:** millimeters internally unless a project sets otherwise; API accepts explicit units.
5. **IDs:** stable ULIDs/UUIDs on every element; never reuse deleted IDs.
6. **Git-friendly project JSON** is primary editable store; IFC is interchange + validation target.

## Code ownership (hard lanes while claimed — no overlap)

**Live assignment:** always check [`notes/handoffs/NOW.md`](notes/handoffs/NOW.md) and [`TEAM_STATUS.md`](TEAM_STATUS.md) before editing.

| Package / path | Default owner | Notes |
|----------------|---------------|-------|
| `packages/core/` | **Grok** | Semantic model, commands — Claude does not rewrite |
| `packages/geometry/` | **Grok** | Primitives — Claude does not rewrite |
| `packages/server/` | **Grok** | FastAPI launch surface |
| `packages/cli/` | **Grok** | `llmbim` CLI |
| `packages/mcp_server/` | **Grok** | MCP stdio |
| `Dockerfile`, `railway.toml`, `.github/` | **Grok** | Deploy / CI |
| `packages/drawings/` | **Grok MVP done**; Claude only via **WP-DRAWINGS-V2** claim | Improve, don’t fork a second API |
| `packages/ifc/` | **Claude (WP-IFC)** | Grok will not implement while Claude claimed |
| `packages/sdk/` | **Grok** | Thin facade; Claude may ask for re-exports via handoff |
| `docs/LAUNCH.md` | **Grok** | |
| `AGENTS.md`, `TEAM_STATUS.md`, `notes/handoffs/NOW.md` | **either** | Always update when claiming / changing direction |

### Before you change direction

1. Update `notes/handoffs/NOW.md` with what you will do next and what you will **not** touch.  
2. Update the claims table in `TEAM_STATUS.md`.  
3. Only then write code.

If you must edit outside your lane: **stop**, write a handoff asking the other agent, or claim a new freeze zone in STATUS first.

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
