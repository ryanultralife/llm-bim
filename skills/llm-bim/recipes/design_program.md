# Recipe: Full design program — brief → basis → model → sheet set

Use this when the ask is a **complete plan or construction set** (a building,
an addition, a facility), not a one-off model. This is the pattern that took a
real residential project from Revit to llm-bim end-to-end; the worked instance
is [`schad_cd.md`](schad_cd.md) (`llmbim case schad`). The acceptance bar is
[`docs/CD_COMPLETENESS_STANDARD.md`](../../../docs/CD_COMPLETENESS_STANDARD.md).

## 0. The interrogation (before any geometry)

You are the architect / machinist on this job: **ask every question a
professional would need answered before drawing**, in one pass, at the start.
The conversation happens at AI speed — you read the repo and docs in seconds;
spend the saved time interrogating the design, not skipping the questions.

Battery (adapt per project type; every item ends up ANSWERED in the basis
module or FLAGGED as `Q-`/`*_assumed` — never silently defaulted):

- **Site / governing**: location, setbacks, frost depth, snow/wind/seismic,
  applicable code + jurisdiction, utility points of connection.
- **Program**: every room/space — use, occupants, area, adjacencies,
  clearances, ceiling heights; loads (live, equipment, process).
- **Envelope**: wall/roof assemblies, ratings, glazing, insulation targets.
- **Structure**: system (wood/steel/CMU), spans, member preferences, tall-wall
  conditions, lateral system.
- **Openings**: full door/window schedule intent — sizes, types, hardware,
  ratings, ADA.
- **MEP**: fixture counts, equipment list, service sizes, routing constraints,
  ventilation/pressurization needs.
- **Machines/devices** (machinist mode): materials, tolerances, threads,
  finishes, mating parts, fabrication method, test/acceptance criteria.
- **Deliverable scope**: plan set vs full CD set, sheet list expectations,
  units, schedules and details required, who reviews.

If the designer can't answer, that's an answer: record the assumption
explicitly and keep building. The interrogation is complete when nothing in
the model will ever need a number that isn't in the basis or flagged.

## 1. Design basis module = the only number source

Create `projects/<slug>/<slug>_design_basis.py` and put **every** number in it:
site dims, room program (types, areas, clearances), loads/needs, wall/opening
schedule, structural members, MEP equipment. Develop engineering, room types,
and loads **in parallel with coordinates** — geometry is derived from
requirements, not sketched first.

- Never retype a dimension in chat, kernel code, or sheets — import it.
- Anything the record does not fix gets an explicit flag: `*_assumed` params
  on elements and `Q-...` open-question notes on sheets. Never silently resolve.
- Imperial sources: convert **once** in the basis (ft → mm, 1 ft = 304.8 mm).

## 2. Staged build harness

`projects/<slug>/build_llmbim.py` with two functions:

```python
def build_model() -> Project:   # stages: shell → structure → foundations → roofs → MEP/content
    ...                         # p.commit("<stage>") after each stage → real model VCS history
def build_pack(out_dir) -> (project, verify):
    ...                         # export with the sheet register below; assert verify["ok"]
```

Thin runner in `examples/<slug>_build.py` so CI and `llmbim case` can call it.

## 3. Types, not thicknesses

Assign registered types that match the occupancy — **residential work never
uses industrial types** (`W-EXT-CMU`/`W-INT-GYP` are industrial):

```python
p.set_type(w, "W-EXT-2x6-BNB")            # wood-framed ext | W-INT-2x4 | W-1HR-GAR-ADU fire sep
p.place_door(host=w, offset_mm=..., type_id="D-SC-36-ADA")   # or D-OH-12x9 overhead, D-HM-30
p.place_window(host=w, ..., type_id="WIN-CASE-48x48")
# structure: catalog sections + typed headers/shear panels (see SKILL.md §"Structure, roofs, foundations")
```

Register new types via `llmbim_core.types_catalog` (`register_wall_type`, …)
rather than raw thickness params.

## 4. Explicit sheet register

Define the full set in `build_pack` — don't rely on the default register for a
deliverable set:

```python
from llmbim_drawings.construction import export_construction_set
export_construction_set(p.model, out, units="imperial", sheets=[
    {"no": "A0.1", "title": "COVER SHEET",  "kind": "cover"},
    {"no": "A1.1", "title": "FLOOR PLAN",   "kind": "plan", "level": "L1", "tags": True},
    {"no": "A2.1", "title": "ELEVATIONS",   "kind": "elevations", "pair": ["S", "N"]},
    {"no": "A3.1", "title": "SECTIONS",     "kind": "sections"},
    {"no": "A4.1", "title": "SCHEDULES",    "kind": "schedule", "schedule": ["door", "window"]},
    {"no": "S3.1", "title": "DETAILS",      "kind": "details", "details": [...]},  # ops DSL, 4-up
    {"no": "H2.1", "title": "GENERAL NOTES","kind": "doc", "text": notes_md},
])
```

Details are data (`{id, title, scale, ops}` — line/rect/circle/hatch/text/dim
ops) rendered by the kernel, never freehand SVG.

## 5. Gates before "done"

- Drift-pin tests in `tests/unit/test_<slug>_*.py`: assert key basis-derived
  invariants as literals (areas within 1%, ridge heights, element counts) so
  silent basis/kernel drift fails CI.
- `validate` / `rules` / `clash` clean (or every finding explained on a sheet).
- `verify_pack` ok — strict glTF check included.
- Optionally register a golden command (`llmbim case <slug>`) + a
  `scripts/verify_all.py` check.

## 6. Honesty + output contract

- Stamp every pack `[DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION]` unless a
  human PE process says otherwise. No PE/code-compliance claims; rebar/header
  callouts are carried design data, not calculations.
- Hand the user **exactly one path**: `output/<slug>/index.html`.
