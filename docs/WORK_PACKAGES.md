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

## WP-IFC — IFC4 export (**CLAUDE PRIMARY — claim this**)

| Field | Value |
|-------|--------|
| Status | **ready** — Grok will not work here while Claude claims |
| Suggested owner | **Claude** |
| Freeze zone | `packages/ifc/**`, `tests/wp/test_wp_ifc_*.py`, `tests/golden/ifc/**` |
| Depends on | Walls/slabs/doors/windows/rooms on main (already shipped) |
| Grok next | Launch/API only — see `notes/handoffs/NOW.md` |

### Goal

Export IFC4 with IfcProject/IfcSite/IfcBuilding/IfcBuildingStorey, IfcWall, IfcSlab, IfcDoor, IfcWindow, IfcSpace when present.

### Frozen API

```python
# packages/ifc/llmbim_ifc/export.py

def export_ifc(model: ProjectModel, path: str | Path) -> None:
    """Write IFC4 file openable in at least one common viewer / ifcopenshell."""
```

### Definition of done

- [ ] `ifcopenshell` optional extra used  
- [ ] Round-trip open with ifcopenshell without error  
- [ ] Storeys match levels; wall count matches model  
- [ ] Tests skip gracefully if ifcopenshell not installed OR mark as requiring `pip install -e ".[ifc]"`  
- [ ] STATUS done  

**Note:** If Claude can only claim one package, **prefer WP-DRAWINGS first** (visible agent deliverable). IFC second.

---

## WP-SCHEDULES — door/window/room CSV (draft)

Status: `draft` — Grok will flesh after openings/rooms solid on main.

---

## Packages Grok will NOT assign to Claude

- Command bus growth, MCP, CLI, CI plumbing, thin SDK methods  
- Anything needed to keep agents modeling without drawings  

Those stay on the fast path.
