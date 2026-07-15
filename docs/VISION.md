# Vision

## What we're building

An **LLM-native** drafting and BIM platform for authoring buildings — walls, doors, windows,
levels, grids, slabs, rooms — as a live parametric model, driven **only by agents** (natural
language → structured commands via Python SDK / CLI / MCP). Drawings and schedules are derived
from a single 3D model source of truth.

**Product constraint (human, 2026-07-15): entirely LLM-interfaced. No frontend where humans
draft or build.** Review exports (IFC, SVG, PDF, glTF) are fine; interactive CAD UI is out of
scope unless the human reopens it.

## Why this can exceed Revit (and where it won't, yet)

Revit's moats are real: mature geometry kernel, families ecosystem, MEP/structural depth,
documentation tooling, and decades of edge cases. We are not out-featuring it in a sprint.
We win on the axis GUI tools cannot easily follow:

| Axis | Revit | llm-bim |
|------|-------|---------|
| Authoring | GUI-first; API bolt-on | **Command-first**; agents share one API |
| Natural language | None native | **First-class** tool surface |
| Auditability | Opaque model state | Serialized, replayable commands |
| Extensibility | Steep plugins | Add a command → SDK + MCP + undo free |
| Runtime | Desktop GUI | **Headless kernel**; CI and multi-agent |

**Where we defer:** MEP, advanced structural, construction-doc depth, human canvas UI.

## Design principles

1. **One model, one command API.** Agents use the same validated path as tests/CLI.
2. **Parametric, not drawn.** Wall = baseline + type + height; doors hosted with parameters.
3. **Millimeters, doubles; explicit units at the boundary.**
4. **Kernel is pure and headless.** Zero UI coupling.
5. **Validation before mutation.** Commands can refuse.
6. **Deterministic.** Same command log → same model.

## Non-negotiables

- Reproducible geometry (no silent drift).
- Full undo/redo across every mutation.
- Referential integrity (delete wall → hosted openings handled deliberately).
- Schedules/quantities derive from the model.

## Roadmap (living)

- **M0 — Kernel foundation** *(in progress)*: model, command bus + undo, geometry, levels, walls, hosted openings. Tested.
- **M1 — Agent bridge**: LLM tool-schema (MCP), NL → commands, query API, CLI.
- **M2 — Documentation**: plans/sections/elevations SVG/PDF, schedules, sheets.
- **M3 — Interop**: IFC export (then import subset).
- **M4 — Discipline growth**: structure stubs, light MEP, better joins.
- **M? — Optional human review UI**: view-only 3D/plan for humans **if ever requested** — not authoring.

## Alignment

- Authoritative architecture: [`docs/DESIGN.md`](DESIGN.md)
- Execution DAG: [`docs/PR_PLAN.md`](PR_PLAN.md)
- Agent protocol: [`../AGENTS.md`](../AGENTS.md)

### Grok note on prior draft

An earlier VISION draft mentioned web canvas + direct manipulation as M2. That conflicts with
the human's LLM-only directive. Canvas authoring is **parked**. If Claude still wants a
view-only inspector later, open an ADR — do not merge authoring UI without human OK.
