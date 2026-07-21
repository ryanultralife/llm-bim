# NOW — current state and active work

**Updated:** 2026-07-21 by Claude

## OPEN WORK ORDERS — unclaimed, any LLM may execute

The drawing engine now meets the full `docs/CD_COMPLETENESS_STANDARD.md`
anatomy (zero open gap rows). Two rebuilds are queued; claim one in
`TEAM_STATUS.md`, execute, gate, commit, PR.

### WP-SCHAD-ANATOMY-REBUILD (this repo)

Turn the full anatomy ON in the Schad register and rebuild the golden case.

1. Read `skills/llm-bim/recipes/schad_cd.md` + `docs/CD_COMPLETENESS_STANDARD.md`.
2. In `projects/schad/build_llmbim.py` `build_pack()`: add to the
   `export_construction_set` call (or its register entries):
   `dim_tiers=True, fractional_grids=True, grid_sides=True, room_areas=True,
   key_plan=True, keynotes=True, line_weights=True, hatches=True,
   stamp_block=True`. Plan entries covering details (D01–D12 live on
   S3.1–S3.3) may add `callouts=[{x, y, detail: "D07"}, ...]` where the
   basis fixes the location — never invent coordinates.
3. Revision clouds: the build commits staged history — demonstrate the loop
   with `revisions={"clouds": p.revision_clouds(since="<first-stage version
   from p.log()>"), "delta": "1"}` OR omit if it adds noise; your call,
   state it.
4. Gates: `llmbim case schad` exit 0 · `python -m pytest -q` all green ·
   `python scripts/verify_all.py` ALL PACKS OK · sheet count still 21 ·
   drift pins unchanged (areas / ridge / counts — the basis did NOT change).
5. Commit `[<agent>] WP-SCHAD-ANATOMY-REBUILD: ...`, push, PR to main.

### WP-INTEC-ANATOMY-REBUILD (Eigen repo → pointed at llm-bim)

From the Eigen repo (`scripts/intec_llmbim_build.py`), adopt the custom
`sheets=[...]` register and enable the same anatomy options for the INTEC
set (`units` stays metric where the basis is metric). Same gates: VERIFY ok,
zero rule errors, discipline counts stated. Follow
`docs/INTEC_CD_detail_calibration.md` (in Eigen) for discipline targets.

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
