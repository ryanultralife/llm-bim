# GEMINI.md — point Gemini (CLI / any agentic harness) at this repo

You are working in **llm-bim**: a deterministic BIM kernel. The user chats with
you; you produce **real models, drawings, and packs on disk** under
`./output/`. This requires shell + Python execution — a browser-only session
cannot do this work.

## First steps (every session)

1. Read **`skills/llm-bim/SKILL.md`** — the full skill: rules, APIs, recipes.
2. Read **`CLAUDE.md`** (same contract, agent-neutral) and **`AGENTS.md`**
   (multi-agent protocol, autonomy contract).
3. Ensure install works:
   ```bash
   pip install -e ".[dev,server]"
   llmbim version
   ```

## Non-negotiables (summary — SKILL.md governs)

- All geometry mutations go through the kernel (SDK / CLI / MCP / `project.op`).
  Never freehand IFC/SVG/STEP in chat.
- Every number traceable to a stated source; unknowns carried as `*_assumed`
  params or `Q-` notes — never silently resolved. No PE/code claims.
- Run `validate` / `rules` / `clash`; finish with `export_deliverables` and a
  green `verify_pack`.
- Version control: `p.commit("...")` after meaningful batches; `p.log()` is
  history, not chat.
- Hand the user **exactly one path**: `output/<slug>/index.html`.

## Full plan/CD sets

Follow `skills/llm-bim/recipes/design_program.md` (basis-module SSOT, staged
harness, typed assemblies, explicit sheet register, drift-pin tests). Worked
instance: `llmbim case schad`.

## From a phone / no local CLI

See `docs/MOBILE.md`. Fastest Gemini path: a collaborator comments
`@gemini-cli <request>` on any issue/PR — `.github/workflows/gemini-assist.yml`
runs Gemini CLI in Actions with the kernel installed (requires the
`GEMINI_API_KEY` repo secret). Jules (jules.google.com) also works from a
mobile browser.

## MCP (optional)

`~/.gemini/settings.json`:

```json
{ "mcpServers": { "llm-bim": { "command": "llmbim", "args": ["mcp"] } } }
```
