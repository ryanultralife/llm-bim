# text-to-cad ("CAD Skills") vs llm-bim — Research Report (2026-07-22)

Reference requested by the human: https://github.com/earthtojake/text-to-cad
Sources actually read by the research agent: the live repo at commit `fdbb4b4`
("Publish 0.3.9", 2026-07-10) — README.md, AGENTS.md, CONTRIBUTING.md,
`skills/cad/SKILL.md`, `skills/cad/references/{repair-loop,inspection-and-validation,
snapshot-review,cad-brief,parameters}.md`, `skills/{step-parts,sendcutsend,bambu-labs}/SKILL.md`,
`packages/cadpy/src/cadpy/` (source_hash.py, step_hash.py, validators.py,
generation_status.py), `benchmarks/10-planetary-gear-stage.md`,
`tests/python/global/test_skill_self_containment.py`, cadskills.xyz. Grounding on our
side: README.md, docs/VISION.md, docs/DESIGN.md, skills/llm-bim/ops.schema.json,
packages/sdk, llmbim_core/repair.py.

## What it is

**Not a prototype.** "CAD Skills" is a mature, actively-released **agent skills
library for mechanical CAD, robotics, and fabrication** — 11.4k stars, 1.2k forks,
MIT, versioned releases (plugin v0.3.9), docs site, live demo, Discord, and
provider-native plugins for Codex and Claude Code. ~1,660 files; the shared Python
runtime `cadpy` is ~16k LOC across 30+ modules.

Eleven skills: **cad** (build123d parts/assemblies → STEP), **cad-viewer**,
**step-parts** (hosted catalog of purchasable parts), **dxf**, **urdf/srdf/sdf**
(robots + MoveIt + simulators), **sendcutsend** (fab preflight), **gcode** (real
slicer CLIs), **bambu-labs** (LAN print jobs w/ confirm gates), **implicit-cad**.

**Scope boundary is explicit and complementary to ours**: their SKILL.md says
verbatim "Do not use this skill for … architectural BIM." They do parts,
assemblies, and robots; we do buildings, sheets, and takeoffs. Zero collision.

## Architecture

- **IR = LLM-authored Python source** (build123d script exposing `gen_step()`);
  STEP is the primary artifact, GLB/topology sidecars derived. The **opposite bet
  from ours**: we constrain agents to a typed op set with validation-before-
  mutation; they let the agent freehand code and **verify post-hoc**.
- **Verification tooling is the crown jewel.** `scripts/step` (generate),
  `scripts/inspect {refs|diff|frame|measure|align|worker|batch}`,
  `scripts/snapshot` (PNG/GIF packets). Selector-ref syntax (`#o1.2.f1` =
  occurrence.shape.face) gives agents stable-ish addresses into BREP topology.
- **Mandatory visual review**: after any visible geometry change the agent MUST
  render *two opposed isometric views* ("every face appears in at least one
  image") + top + front, then "convert every visual concern into a deterministic
  geometry check before it becomes a validation claim."
- **10-step required workflow** incl. a written CAD brief ("a technical drawing is
  a dimensioned contract" — every callout becomes a parameter AND a validation
  target) and a 7-class **failure taxonomy** (repair-loop.md) with smallest-fix
  guidance per class.
- **Determinism**: sha256 of generator source + STEP output in manifests; git as
  VCS. **No command bus, no transactions, no undo, no model-state VCS** — validity
  via generate→inspect→repair loops, not refused mutations. Benchmarks are manual
  capability demos (prompt + expected-result tables + GIFs), not CI.
- **Distribution engineering**: skills-marketplace installs, AST-enforced skill
  self-containment, vendoring, generated plugins, public docs site.

## Strengths vs llm-bim (what they do better)

1. **Post-generation geometric verification for agents** — `inspect
   measure/align/frame/diff` + selector refs asserts *resulting geometry*. Our ops
   catalog has only `query`/`validate` in that space; nothing checks "is the door
   actually 900 mm from the corner as the spec said."
2. **Mandatory snapshot-review policy** — nothing in our CLAUDE.md/SKILL.md forces
   the agent to look at renders and convert findings into checks.
3. **Requirement intake from drawings/images** (cad-brief.md): title block first,
   sections are truth for internal features, `4X`/`TYP.` expand into
   features+checks, never scale undimensioned geometry, flag conflicts.
4. **Real supply chain + fab handoff**: checksummed vendor STEP catalog ("search
   before placeholder, record the miss"), SendCutSend preflight, real slicers,
   layered confirm flags for physical actions.
5. **Distribution and packaging** (why they have 11.4k stars).
6. **Context economy**: progressive reference loading keeps SKILL.md short.

## Weaknesses vs llm-bim (where we're stronger)

1. **No constrained IR / kernel-owned semantics** — nothing refuses invalid
   mutations; our typed command bus + structured error codes + undo/transactions +
   referential-integrity repair are machine-recoverable by design.
2. **No model version control** (git-over-source only; we have true model VCS).
3. **No semantic building model** — levels, hosted openings, rooms, schedules,
   BOQ/CSI, clash, design rules, IFC4, CD sheets, PDF binders all out of scope.
4. **Heavier runtime** (OpenCASCADE native deps vs our pure-stdlib kernel).
5. **Benchmarks aren't CI** — ours regression-lock behavior; theirs are demos.
6. **Different problems, honestly** — both are defensible optima for their domains.

## Adoption ideas (ranked — actionable in llm-bim)

1. **Agent-facing geometry assertion CLI: `llmbim inspect measure|align|diff`** —
   measure distances/clearances between elements/faces/datums, assert spec
   dimensions, geometric diff between model versions. New
   `llmbim_core/inspect.py` + CLI + 2-3 ops in ops.schema.json; SKILL.md step
   "verify every user-specified dimension." Closes our biggest verification gap.
   Effort: M.
2. **Mandatory review-packet policy** — after `export_deliverables`, emit a fixed
   packet (plan + two opposed axonometrics + one elevation; SVG fine — we now have
   render_hero) and require agents to review it and convert every visual concern
   into a deterministic check before "done." Effort: S-M.
3. **Progressive reference loading for our skill** — split SKILL.md into a short
   core + trigger-loaded `references/*.md` (drawing-intake, repair-loop, takeoffs,
   VCS, imperial/CD). Effort: S.
4. **Failure-taxonomy repair reference** — map each structured error code (and
   common validate/rules/clash findings) to likely causes + smallest-fix
   procedures; we have the machine codes they lack, they have the playbook pattern
   we lack. Effort: S.
5. **Public benchmark specs with test tables + GIFs** — 8-10 `benchmarks/NN-*.md`
   (studio apartment, office bay, warehouse, two-story addition…): prompt,
   expected-result table (checkable via validate/BOQ/inspect), viewer GIF. Doubles
   as agent eval set + growth artifact; unlike theirs, ours can run in CI. Effort: S-M.
6. **Checksummed part sourcing** — sha256 on imported STEP/DXF parts, alias/fuzzy
   catalog search, "search the catalog before inventing placeholder geometry;
   record the miss." Effort: M.

## Draft reply for the author (human sends this personally; do not post from repo)

> Really impressive work — I build in an adjacent space (LLM-driven BIM, so
> buildings rather than brackets) and your inspect/snapshot/repair loop is the
> best post-generation verification discipline I've seen in an agent CAD project.
> A few suggestions from lessons we learned the hard way, in case any are useful:
>
> 1. **Turn the benchmarks into CI regression tests using your own `inspect`
>    output as the golden.** The 10 benchmark specs already have testable
>    expected-result tables, and `scripts/inspect refs --facts` already emits
>    machine-readable facts. Pinning those facts JSONs (with tolerances, via your
>    `validators.assert_close`) would regression-lock generator behavior across
>    build123d/OCP upgrades — STEP bytes won't survive an OCCT bump, but facts will.
> 2. **Make the failure taxonomy machine-readable.** `references/repair-loop.md`
>    classifies failures well, but the agent has to re-read prose to use it.
>    Emitting a structured failure class + hint from `scripts/step` (e.g.
>    `{"error": "FILLET_EXCEEDS_LOCAL_GEOMETRY", "hint": "reduce radius or narrow
>    edge selection"}`) lets agents branch on codes instead of diagnosing from
>    tracebacks. Structured error codes cut our agents' repair loops dramatically.
> 3. **Persist the brief's validation targets as a checks file.** Every spec
>    dimension becomes a validation target in your CAD-brief pattern — but those
>    targets live only in one-off `measure`/`align` invocations. Since `inspect`
>    already has a `batch` mode, a `part.checks.json` next to `part.py`, re-run on
>    every regeneration, would turn the spec into a durable test instead of a
>    one-session memory.
> 4. **Record toolchain versions in artifact manifests.** You already store
>    `source_hash` and STEP sha256 — adding build123d/OCP/OCCT versions makes hash
>    drift diagnosable ("same source, different STEP" is almost always a library
>    bump, painful to reconstruct after the fact).
> 5. **Consider a ref-stability map in `inspect diff`** (if it doesn't already do
>    this). repair-loop.md flags selector fragility (`#o1.2.f1` shifting after
>    fillets/booleans); emitting an old-ref → new-ref correspondence for surviving
>    faces/edges would let agents repair selector-based checks automatically.
>
> Happy to compare notes anytime — again, great project.

**Calibration:** suggestions 1-4 are grounded in specific files read; #5 is the
most speculative (soften with "if it doesn't already" when posting). Nothing was
posted anywhere; no files in their repo were touched.
