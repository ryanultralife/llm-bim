# Vision

## What we're building

An LLM-native drafting and BIM platform for authoring buildings — walls, doors, windows,
levels, grids, slabs, rooms — as a live parametric model, drivable by natural language and by
direct manipulation, with drawings and schedules derived from a single source of truth.

## Why this can exceed Revit (and where it won't, yet)

Revit's moats are real: a mature geometry kernel, families ecosystem, MEP/structural depth,
documentation tooling, and 30 years of edge cases. We are not going to out-feature it in a
sprint. We win by attacking the axis it can't easily follow:

| Axis | Revit | llm-bim |
|------|-------|---------|
| Authoring | GUI-first; API is a bolt-on (.NET, out-of-process) | **Command-first**; UI and LLM share one API |
| Natural language | None native | **First-class** — the model *is* the tool surface |
| Auditability | Opaque model state | Every change is a serialized, replayable command |
| Collaboration | Central-file/worksharing | Command log → CRDT/OT-friendly by construction |
| Extensibility | Steep (.NET plugins) | Commands + schema; add an op, get UI + LLM + undo free |
| Platform | Windows desktop | Web-first, headless-capable kernel |

**Where we defer:** MEP, advanced structural analysis, rendering/visualization polish,
construction documentation depth. These are post-foundation.

## Design principles

1. **One model, one command API.** No privileged path. The LLM cannot do anything the UI
   can't, and vice-versa. This keeps the system honest and testable.
2. **Parametric, not drawn.** A wall is a baseline + type + height, not a pile of lines. Doors
   are *hosted* by walls with a position parameter. Change the type, everything updates.
3. **Millimeters, doubles, explicit units at the boundary.** No unit ambiguity internally.
4. **Kernel is pure and headless.** It runs in a test, a server, a worker, or a browser tab
   with zero UI coupling. Rendering and LLM wiring live outside it.
5. **Validation before mutation.** Commands can refuse. A door can't host on a missing wall.
6. **Deterministic.** Same command log → same model. No hidden global state, no wall-clock or
   RNG in the kernel.

## Non-negotiables for "professional-grade"

- Exact, reproducible geometry (no floating drift on repeated ops).
- Full undo/redo across every mutation.
- Referential integrity (deleting a wall handles its hosted elements deliberately).
- Schedules/quantities derive from the model, never hand-maintained.

## Roadmap (living)

- **M0 — Kernel foundation** *(in progress)*: model, command bus w/ undo, geometry, levels,
  walls, hosted openings. Tested.
- **M1 — Agent bridge**: command → LLM tool-schema, NL → command translation, query API.
- **M2 — Web canvas**: 2D plan view, direct manipulation, chat panel wired to the agent.
- **M3 — Documentation**: schedules, dimensions, sheet export.
- **M4 — 3D + collaboration**: derived 3D view, multi-user command sync.
