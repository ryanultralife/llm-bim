# Agent speed protocol (Grok fast · Claude slow)

Human directive: Claude is much slower. **Use that as an advantage**, not a liability.

## Roles by tempo

| | **Grok (fast)** | **Claude (slow / deep)** |
|--|-----------------|---------------------------|
| Cadence | Many small commits; keep `main` green hourly | Few large, high-quality landings |
| Best work | Critical path, glue, unblocking, integration, thin vertical slices | Deep domains that benefit from careful design: drawings correctness, IFC mapping, hard validators |
| Batch size | PR-sized, < few hundred LOC | **Sealed work packages** (multi-file, hours of Claude time, one PR) |
| Coordination | Updates STATUS often; never waits on Claude for MVP blockers | Claims **one** package; stays in its freeze zone until PR |

## Rules that make slowness an advantage

1. **Grok never blocks the project on Claude.**  
   If something is on the critical path (walls/slabs/doors/SDK/tests), Grok does it. Claude is not a gate.

2. **Claude never gets micro-tasks.**  
   No “add one grid helper” errands. Only sealed packages in `docs/WORK_PACKAGES.md` with:
   - frozen public contracts
   - acceptance tests (often failing red → Claude makes green)
   - explicit **file freeze zone** Grok will not edit
   - complete brief so Claude needs zero clarification round-trips

3. **Interface-first handoff.**  
   Grok freezes APIs + writes failing tests + example data. Claude implements behind the interface. Merge is green tests, not debate.

4. **File freeze while Claude is `in_progress`.**  
   Grok must not touch Claude’s freeze paths except emergency (documented in STATUS). If Grok needs a change there, extend the contract in a *new* file outside the freeze, or wait for Claude’s PR.

5. **Claude’s strength = depth.**  
   Prefer Claude for: SVG plan/section correctness, IFC entity mapping, schedule edge cases, property-based tests, doc clarity.  
   Prefer Grok for: command bus growth, element CRUD, repo plumbing, CI, MCP/CLI glue, rapid example scripts.

6. **Main stays shippable without Claude.**  
   Every Grok session leaves `pytest` green and a usable SDK path. Claude packages are additive quality (drawings/IFC), not load-bearing for “can an agent model a box.”

7. **Handoffs are complete essays, not pings.**  
   Because Claude starts cold and slow, every package brief includes: goal, non-goals, file list, API signatures, fixtures, commands to run, definition of done. No “see chat.”

## Conflict avoidance

```
packages/drawings/**     → Claude zone when WP-DRAWINGS claimed
packages/ifc/**          → Claude zone when WP-IFC claimed
packages/core/**         → Grok default
packages/geometry/**     → Grok default (openings helpers may be co-owned if frozen)
packages/sdk/**          → Grok owns; Claude may add thin re-exports only if brief says so
packages/mcp_server/**   → Grok default (fast glue)
packages/cli/**          → Grok default
```

## When Claude is mid-package

Grok continues:
- more element types, validation, geometry
- SDK / MCP / CLI
- examples, CI, golden *model* JSON (not SVG if freeze)
- reviewing Claude’s PR when it appears (patient, thorough review is fine)

Grok does **not**:
- “helpfully” rewrite drawings/ifc mid-flight
- split Claude’s package into smaller competing branches
- demand daily sync commits from Claude

## Success metric

- Project velocity ≈ Grok’s speed on kernel  
- Project *quality ceiling* raised by Claude’s deep packages without slowing kernel  
- Zero idle-wait where Grok sits blocked on Claude  
