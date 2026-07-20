# Point and chat — any LLM, any device, no setup

The rule: **no API keys, no config**. A person points the LLM they already
use at this repo and gets real output. The kernel's modeling and full pack
export are **pure standard-library Python** — no pip install is needed to run
it, which is what makes the paths below work.

## The pointer prompt (paste into any LLM)

> You are operating the **llm-bim** kernel from
> https://github.com/ryanultralife/llm-bim. Get the repo (clone it, or I'll
> attach the ZIP), run `import bootstrap` from its root (no pip install — the
> kernel is pure stdlib Python 3.11+), then read `skills/llm-bim/SKILL.md`
> and follow it exactly. Build what I describe with the `Project` API, run
> validate/rules/clash, `export_deliverables`, and give me the output folder.
> Hand me exactly one entry file: `index.html`.

## Path A — chat apps with a code sandbox (phone or desktop, zero accounts to wire)

Works in ChatGPT, Gemini, Claude — any chat that can run Python on attached
files, even with **no internet in the sandbox**:

1. On the repo page: **Code → Download ZIP** (works in a mobile browser).
2. Attach the ZIP to your chat and paste the pointer prompt above.
3. The LLM unzips, `import bootstrap`, models, exports, and returns the pack
   (or its zip) for download. Open `index.html` in your browser — the 3D
   viewer is fully self-contained and works offline on a phone.

## Path B — vendor-hosted coding agents (login only, full autonomy)

These give the LLM a cloud machine with shell + git; you just connect the
repo and chat. No API keys — your existing login is the whole setup:

| Your LLM | Point it here | Entry context it reads |
|----------|---------------|------------------------|
| Claude | claude.ai/code (web or mobile app) → connect the GitHub repo | `CLAUDE.md` |
| Gemini | jules.google.com → connect the repo, give a task | mention `GEMINI.md` in the task |
| ChatGPT | Codex (chatgpt.com) → connect the repo | mention `AGENTS.md` |
| Copilot | assign the issue to Copilot coding agent | `AGENTS.md` |

These can commit, push, open PRs, and run the full gate set — use them for
anything you want to land in the repo rather than just receive as files.

## Path C — your computer

```bash
git clone https://github.com/ryanultralife/llm-bim.git && cd llm-bim
python -c "import bootstrap; from llmbim import Project; print('kernel ok')"
# then run any agentic CLI here (claude, gemini, codex, ...) — it reads its
# entry file (CLAUDE.md / GEMINI.md / AGENTS.md) automatically
```

`pip install -e ".[dev,server]"` is only needed for the `llmbim` CLI,
server/MCP, and the test suite — never for modeling itself.

## What browser-only chat (no sandbox) can still do

Draft the **design basis** — requirements, room program, loads, dimensions —
in conversation, as a Python basis module per
`skills/llm-bim/recipes/design_program.md`. Then hand that file to any path
above to execute. Splitting design conversation from execution this way is
the intended workflow, not a workaround.
