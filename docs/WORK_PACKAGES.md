# Sealed work packages (for Claude)

Grok maintains this file. Claude claims **at most one** `ready` package at a time in `TEAM_STATUS.md`.

Status: `draft` → `ready` → `claimed` → `in_review` → `done`

---

## WP-DRAWINGS — Plan / section / elevation SVG (DONE — MVP on main)

| Field | Value |
|-------|--------|
| Status | **done** (Grok shipped MVP for launch) |
| Suggested owner | ~~Claude~~ → optional **WP-DRAWINGS-V2** later |
| Freeze zone | n/a for MVP |
| Note | Claude: **do not reimplement**. Prefer **WP-IFC**. Quality pass = separate claim WP-DRAWINGS-V2 |

### Goal

Derive 2D drawings from `ProjectModel` with **no GUI**. Agents call export functions; humans only open the SVG/PDF.

### Non-goals

- Dimension strings / tags (later)
- PDF multi-sheet title blocks (SVG sheets OK if simple)
- Pretty CAD lineweights library
- 3D mesh

### Frozen public API (implement exactly)

```python
# packages/drawings/llmbim_drawings/api.py

from pathlib import Path
from llmbim_core.model import ProjectModel

def export_plan_svg(
    model: ProjectModel,
    level: str,              # name or id
    path: str | Path,
    *,
    view_range_mm: float = 1200.0,
    scale: float = 0.05,     # mm model → SVG units multiplier (tune; document choice)
) -> None:
    """Horizontal cut at level elevation; walls as thick strokes or filled bands;
    doors/windows as breaks/ticks; rooms as labels at centroid if boundary present.
    """

def export_section_svg(
    model: ProjectModel,
    p0: tuple[float, float],  # plan-view segment defining cut plane
    p1: tuple[float, float],
    path: str | Path,
    *,
    depth_mm: float = 500.0,
    scale: float = 0.05,
) -> None:
    """Vertical section along p0→p1."""

def export_elevation_svg(
    model: ProjectModel,
    direction: str,  # "N" | "S" | "E" | "W"
    path: str | Path,
    *,
    scale: float = 0.05,
) -> None:
    """Orthographic elevation looking N means toward +Y (document axes in module docstring)."""
```

Wire thin wrappers on SDK (Grok may add stubs that call these once package lands; Claude should implement drawings package only unless brief extended).

### Fixtures

- Use `examples/simple_house.py` output model, or build in tests via SDK.
- After Grok lands doors/rooms, re-pull `main` before implementing symbols.

### Acceptance tests (make these pass)

Files (Grok seeds failing tests if not present — Claude implements):

- `tests/unit/test_drawings_plan.py` — plan SVG exists, contains `<svg`, has wall-related geometry, non-trivial file size
- Golden optional: normalize floats if flaky; prefer structural assertions over exact bytes first

### Definition of done

- [ ] API functions above implemented  
- [ ] Tests green  
- [ ] Module docstring: axes, units, scale convention  
- [ ] No dependency on GUI / display server  
- [ ] Handoff note in `notes/handoffs/`  
- [ ] STATUS → done  

### How to claim

1. Pull latest `main`  
2. Set TEAM_STATUS: WP-DRAWINGS → Claude, `claimed`, branch `feature/wp-drawings`  
3. Work only in freeze zone  
4. Open PR when green  

---

## WP-IFC — IFC4 export (**DONE — Claude, merged PR #1 2026-07-19**)

| Field | Value |
|-------|--------|
| Status | **done** |
| Owner | Claude |
| Landed | `main` via PR #1 (audit branch) |

### What shipped

- Spatial tree (Project/Site/Building/Storey) with storey-relative element
  placement — multi-storey elevations flow through the placement chain
- IFC4-exact attribute counts (IfcDoor/IfcWindow 13, wall/column/beam
  PredefinedType) — strict readers (ifcopenshell/Revit) accept the file
- Hosted openings: `IfcOpeningElement` punched wall-local through hosts via
  `IfcRelVoidsElement`, leaf fills via `IfcRelFillsElement`
- Wall corner joins: solids extend half the adjacent wall's thickness at
  shared endpoints so L/T corners close
- Correct profile offsets (solids run start→end, not straddling the origin);
  CSI psets; space containment
- Acceptance tests hand-parse the SPF (attribute counts, ref integrity,
  storey Z, voids/fills wiring, join dims) — no ifcopenshell required;
  optional ifcopenshell round-trip test skips if not installed

### Remaining ideas (new claim if wanted)

- IfcMaterialLayerSet from wall types; IfcQuantitySets (needs area/volume
  units aligned); MVD-strict ReferenceView tightening

---

## WP-DRAWINGS-V2 — drawings quality (**DONE — Claude, merged PR #1 2026-07-19**)

Landed as part of the audit branch: dimensions render on-canvas everywhere
(pad-aware viewBox through sheets), opposite elevations mirrored with
near-face opening culling, equipment hidden-line ghosting on elevations,
PDF binder honors `scale()`, opening schedules carry derived coordinates.

---

## WP-MEP-TAP — multi-run systems + tee-tapping (**DONE — Claude**)

`mep_tap` (split an existing run at the nearest point, insert a catalog tee,
autoroute the branch to a target) and `mep_trunk_branch` (trunk + N taps).
Freeze: `core/mep_route.py` + registry/SDK/MCP wiring, `tests/unit/test_mep_tap.py`.

## WP-IFC-IMPORT — round-trip import (**DONE — Claude**)

Real geometry recovery from our IFC4 files (levels, walls, hosted openings via
RelVoids/Fills, slabs, equipment, spaces, flow segments) replacing the
placeholder subset importer. Freeze: `packages/ifc/**`, `core/io_import.py`,
`tests/unit/test_ifc_roundtrip.py`.

## WP-MEP-SIZING — hydraulic pipe + duct sizing (**DONE — Claude**)

Flow/WSFU-based pipe NPS selection (velocity + Hazen-Williams), equal-friction
duct sizing with rectangular equivalents, run validation reports. Engineering
estimate — not stamped design. Freeze: NEW `core/mep_sizing.py`,
`tests/unit/test_mep_sizing.py`.

## WP-MEP-ROUTE — obstacle-avoiding autoroute (**DONE — Claude, merged PR #2**)

| Field | Value |
|-------|--------|
| Status | **claimed** (branch `claude/grok-audit-evolution-w4umwh`) |
| Freeze zone | `packages/core/llmbim_core/mep_route.py` + registry/SDK/MCP wiring, `tests/unit/test_mep_autoroute.py` |

Manhattan-grid autoroute between points/fittings avoiding wall footprints and
equipment (clearance-aware), auto elbow insertion at bends, optional vertical
transition with riser, mep_graph chaining, surfaced as op `mep_autoroute` +
`Project.mep_autoroute` + MCP tool. Honesty unchanged: geometric coordination
routing, not hydraulic design.

---

## WP-VIEWER-RICH — review 3D upgrades (**DONE — Claude, merged PR #2**)

| Field | Value |
|-------|--------|
| Status | **claimed** (branch `claude/grok-audit-evolution-w4umwh`) |
| Freeze zone | `packages/drawings/llmbim_drawings/viewer3d.py`, `packages/geometry/llmbim_geometry/mesh.py`, `tests/unit/test_viewer3d_rich.py` |

Element metadata into glTF node extras (id/name/category/system/level),
click-to-inspect panel, category + level visibility filters, measure tool.
View-only review — not an authoring canvas.

---

## WP-SCHEDULES — door/window/room CSV (draft)

Status: `draft` — Grok will flesh after openings/rooms solid on main.

---

## WP-SCHAD — Revit → llm-bim transition (OPEN until Gate D)

**Canonical review:** [`docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md`](SCHAD_REVIT_TO_LLMBIM_TRANSITION.md)  
**Human directive:** same or better quality than Revit Schad CD path; retire `.rvt` after Gate D.  
**Owner:** Claude (primary). Claim **one** S-package at a time in `TEAM_STATUS.md`.  
**Fixture:** `examples/schad_garage.py` → evolve to `examples/schad_build.py`; pack `output/schad_garage/`.

| ID | Status | Freeze (approx) | Goal |
|----|--------|-----------------|------|
| **WP-SCHAD-S0** | **ready** | `projects/schad/**`, `examples/schad_*.py` | Port pure SSOT from G: Schad Revit thread into repo; build harness; drift tests |
| **WP-SCHAD-S1** | **ready** | `types_catalog.py`, `annotations.py` set_type | Residential wall/door/window types; stop CMU mapping; Schad uses wood + 1-hr sep |
| **WP-SCHAD-S2** | **ready** | core roof cmds, mesh, section/elev | Gable/shed/cross-gable roofs, eaves; elev/section real |
| **WP-SCHAD-S3** | **ready** | footing ops, slabs | Dual slabs, strip/pad footings, stem, rebar marks |
| **WP-SCHAD-S4** | **ready** | assignment/catalog | Headers, HSS posts, typed SSW, W16x40 catalog |
| **WP-SCHAD-S5** | **ready** | `construction.py`, detail SVG | Configurable 20-sheet register; detail ops DSL renderer (D01–D12) |
| **WP-SCHAD-S6** | **ready** | schad modules + drawings | ADU A1.2, site C1.1, MEP sheets, house H sheets, calcs MD |
| **WP-SCHAD-S7** | **ready** | plan/sheets | Sierra-Star dims/tags (imperial), room area tags |
| **WP-SCHAD-S8** | **ready** | cli case, CI, skill recipe | `llmbim case schad`, CI smoke, recipe, archive Revit doc |

**Order:** S0+S1 → S2+S3 → S4+S5 → S6+S7 → S8.  
**Do not port:** any `Schad_*.py` Revit API adapters.  
**Close review when:** Gate D criteria in transition doc are met.

---

## Packages Grok will NOT assign to Claude

- Command bus growth, MCP, CLI, CI plumbing, thin SDK methods  
- Anything needed to keep agents modeling without drawings  

Those stay on the fast path. (Exception: Claude may add thin SDK/CLI for Schad roof/footing/sheet ops inside WP-SCHAD freezes.)
