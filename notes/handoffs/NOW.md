# NOW — current state and active work

**Updated:** 2026-07-28 by Grok

## Active (Grok) — excellence residual #1 CLOSED this session

- **Done:** MEP-101/201/301 switched from `svg_plans.mep_plan_svg` overlays to
  **plan-kind** with discipline include-sets + ghost walls (`projects/schad/build_llmbim.py`).
  Test: `test_mep_sheets_draw_routed_geometry`.
- **Next Grok drawings lane:** residual #3–5, #9–10, #13 (PDF fidelity / imperial scale).
- Claude residual handoff: `notes/handoffs/2026-07-22-claude-residuals.md`
- **Also noted:** Claude pointed at reference repo `earthtojake/text-to-cad` for analysis → `docs/REFERENCE_TEXT_TO_CAD.md` (not started).

## OPEN WORK ORDERS

### WP-SCHAD-ANATOMY-REBUILD (this repo) — unclaimed

Full anatomy ON in Schad register + rebuild golden case. See prior Claude brief in git history / `docs/CD_COMPLETENESS_STANDARD.md`.

### WP-INTEC — in-progress local tree (untracked `projects/intec/`)

INTEC 128-sheet register port lives under `projects/intec/` (not Eigen `intec_llmbim_build.py`). `build_model()` smoke: 208 elements / 96 walls. Land + gate when ready.

---

## State: Schad transition COMPLETE through Gate D (minus human sign-off)

The WP-SCHAD-S0…S8 program is **done and merged to main** (PRs #8–#14).
`llmbim case schad` rebuilds the full 21-sheet imperial CD set from the basis
in one command; CI drift guards pin the invariants. See
`docs/RETIRING_REVIT_SCHAD.md`.

- **Open (human):** review the pack against
  `docs/CD_COMPLETENESS_STANDARD.md` (professional doc-set anatomy — Sierra
  Star / Verseon calibrated; Revit renders are reference only, not the bar).
  Until signed, the transition review stays OPEN.

## Active: WP-CD-ANATOMY (Claude, claimed)

Closing the "gap" rows of `docs/CD_COMPLETENESS_STANDARD.md` in the drawing
engine, two parallel slices:

- **A** (`plan.py` + `construction.py`): 3-tier dimension chains w/ tick
  terminators, fractional grid intermediates, room-area / wall-type /
  equipment tags, key plan.
- **B** (`section.py` + `layout.py` / `sheets.py`): line-weight hierarchy +
  "ABV." dashed, material hatches, new/existing poché split, reserved
  PE-stamp block, revision clouds, legend block.

Stay out of those files until the claim clears in `TEAM_STATUS.md`.

## Standing contracts (read once, they govern everything)

- Entry: `skills/llm-bim/SKILL.md` (+ `CLAUDE.md` / `GEMINI.md` / `AGENTS.md`)
- Full-set workflow: `skills/llm-bim/recipes/design_program.md`
  (interrogation §0 → basis SSOT → staged harness → register → gates)
- Acceptance: `docs/CD_COMPLETENESS_STANDARD.md`
- Access: `docs/MOBILE.md` — free to point at, no keys, user's own tokens
- Autonomy: method free, outcomes gated (`AGENTS.md` operating principle)

## Grok — useful next (unclaimed)

- Review merged PRs #8–#14; kick `llmbim case schad` on a fresh clone.
- INTEC: adopt the custom `sheets=[...]` register + `units` where useful;
  Eigen-side evidence links for `trl_evidence` params
  (`docs/DIGITAL_TWIN_TRL.md`).

## Decentralized surface

- `skills/llm-bim/SKILL.md` · `llmbim ops --schema` · `docs/LOCAL.md` · MCP: `llmbim mcp`
