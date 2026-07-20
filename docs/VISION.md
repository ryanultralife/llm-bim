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

**Where we defer:** full MEP routing/hydraulics, advanced structural analysis, sealed CD depth, human *authoring* canvas.  
**Where we already ship multi-trade data:** fire/process/plumbing catalogs, steel/rebar, fixtures, CSI takeoffs (catalog + quantities — not PE design).  
**Where we must win visually:** presentation 3D (orbit, PBR materials, layer ghosting) that makes coordination *obvious* — not a CAD grey box.

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

- **M0 — Kernel foundation** ✅: model, command bus + undo, geometry, levels, walls, hosted openings.
- **M1 — Agent bridge** ✅: ops registry, MCP, CLI, SDK, skill pack, query language, scripts/bulk.
- **M2 — Documentation** ✅: plans/sections/elevations SVG, construction sheets, PDF binder, schedules, HTML index, ZIP.
- **M3 — Interop** ✅ *(re-validated 2026-07-19, PR #1)*: IFC4 export with correct IFC4 attribute counts, storey-relative placement (multi-storey Z), hosted openings as real `IfcOpeningElement` + `IfcRelVoidsElement`/`IfcRelFillsElement`, wall corner joins; STEP export/import (locked), DXF, glTF; IFC import subset.
- **M4 — Discipline growth** 🟡: multi-trade catalogs + **place_duct/conduit/cable_tray/column/beam** + openings/structure agent surfaces (door/window/room/slab/equipment/grid/note/shell), CSI+locators (RM/XY/Z/NPS/section/FR/SYS), BOQ, clash, rules, phases, zone/levels/drawing_list schedules; steel takeoff carries real tonnage (kg/m + mass). Wall joins done (plan + IFC). Obstacle-avoiding MEP autoroute in progress (`mep_autoroute`); hydraulic sizing still out of scope.
- **M5 — True model VCS** ✅: commit/log/checkout/diff/journal under `output/<project>/.llmbim/`.
- **M6 — Nested modules** ✅: import drawings/machines as block|native|linked; ports + connect; explode/expand for export.
- **M7 — Fab BREP + GD&T** ✅ (optional `llmbim[fab]`): CadQuery/OCP feature trees — hole/fillet/chamfer/machine thread, true STEP, GD&T datums/FCFs, machining SVG.
- **M8 — Quality gates** ✅ *(2026-07-19, PR #1)*: CI enforces `ruff` + `mypy --strict` (kernel packages, zero `type: ignore`) + full pytest + real-case pack verification; deliverables VERIFY runs after all artifacts exist.
- **M9 — Rich review 3D** 🟡: presentation viewer gains element metadata (glTF extras), click-to-inspect, category/level filters, measure tool — view-only review, still not an authoring canvas.
- **M? — Optional human review UI**: view-only 3D/plan **if ever requested** — not authoring (parked; M9 covers review needs).

## Alignment

- Authoritative architecture: [`docs/DESIGN.md`](DESIGN.md)
- Execution DAG: [`docs/PR_PLAN.md`](PR_PLAN.md)
- Agent protocol: [`../AGENTS.md`](../AGENTS.md)

### Grok note on prior draft

An earlier VISION draft mentioned web canvas + direct manipulation as M2. That conflicts with
the human's LLM-only directive. Canvas authoring is **parked**. If Claude still wants a
view-only inspector later, open an ADR — do not merge authoring UI without human OK.
