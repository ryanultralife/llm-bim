# Driving llm-bim from a phone

The kernel needs shell + Python to run — but the shell does **not** have to be
on your device. Every mobile path below gives an agent a cloud machine and you
a chat/comment box. Ranked by friction:

## 1. Claude — claude.ai/code (web or mobile app)

Already works, no setup: start a Claude Code session connected to the GitHub
repo. Claude gets a cloud container, clones the repo, reads `CLAUDE.md`, and
can build, commit, push, and merge. This is the reference mobile experience —
full autonomy inside the repo's gates.

## 2. Gemini — "@gemini-cli" comments (GitHub mobile app)

`.github/workflows/gemini-assist.yml` runs Gemini CLI **in GitHub Actions**
when a collaborator comments `@gemini-cli <request>` on any issue or PR.
Gemini lands in a checked-out repo with the kernel installed, reads
`GEMINI.md`, does the work, pushes a `gemini/<slug>` branch, and replies on
the issue. Artifacts (packs) are uploaded to the run.

**One-time setup:** add repository secret `GEMINI_API_KEY`
(repo → Settings → Secrets and variables → Actions; free key from
[aistudio.google.com/apikey](https://aistudio.google.com/apikey)). Doable
from a mobile browser.

Usage from the GitHub mobile app: open/raise an issue → comment
`@gemini-cli build a 24x30 two-bay garage plan set, imperial`.

## 3. Gemini — Jules (jules.google.com)

Google's asynchronous coding agent: connect it to the GitHub repo from a
mobile browser, give it a task, it works in its own cloud VM and opens a PR.
No CLI, no Actions setup. Point it at `GEMINI.md` in the task prompt.

## 4. Any agent — GitHub Codespaces in a mobile browser

Repo page → Code → Codespaces → create. You get a real terminal in the
browser (usable on mobile, if cramped):

```bash
pip install -e ".[dev,server]"
npx @google/gemini-cli        # or any agentic CLI
```

## 5. Grok / browser-only chats

A browser-only chat can *read* the repo and draft basis modules or design
docs, but it cannot execute the kernel — so it cannot produce packs or commit.
Pair it with any path above: let it write the design basis in chat, then hand
the basis to an executing agent (path 1–4). This is a harness limitation, not
a model-capability tier — see `AGENTS.md`.

## Viewing output on mobile

Packs are not committed (`output/` is local to the runner). To view on a
phone: use path 2's uploaded run artifacts (download `index.html`-rooted pack
zip), or have the agent open a PR that includes the pack under `examples/output/`
when you explicitly want it in-repo. The viewer (`viewer3d.html` linked from
`index.html`) is fully self-contained and works offline in a mobile browser.

## Future

`llmbim serve` (FastAPI) + MCP make a hosted kernel possible — a remote MCP
connector would let chat apps that support custom connectors drive the kernel
without any repo checkout. Not stood up yet; open a claim in `TEAM_STATUS.md`
if you want it.
