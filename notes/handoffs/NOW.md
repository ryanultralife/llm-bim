# NOW — post-audit feature push

**Updated:** 2026-07-19 by Claude

## Just merged to `main` (PR #1)

Full audit + fixes: IFC4 validity (13-attr entities, hosted openings via
RelVoids/RelFills, wall corner joins, multi-storey placement), drawings
(dimensions on-canvas, mirrored/culled elevations, hidden-line equipment,
PDF scale), takeoffs (BOM mass×qty, steel tonnage + double-count fix),
Project.create collision safety, VERIFY ordering, journal ranges.
**CI now gates `ruff check` + `mypy --strict` + pytest + pack scripts** —
rebase before pushing and keep both clean (zero `type: ignore` policy).

## In flight (Claude, branch `claude/grok-audit-evolution-w4umwh`)

- **WP-MEP-ROUTE** — obstacle-avoiding Manhattan autoroute with auto elbow
  insertion + vertical transitions; op `mep_autoroute` + SDK + MCP.
  Freeze: `core/mep_route.py` + wiring, `tests/unit/test_mep_autoroute.py`.
- **WP-VIEWER-RICH** — glTF node extras (element metadata), click-to-inspect,
  category/level filters, measure tool in `viewer3d.html`.
  Freeze: `drawings/viewer3d.py`, `geometry/mesh.py`,
  `tests/unit/test_viewer3d_rich.py`.
- Roadmap docs synced: `docs/VISION.md` (M3 revalidated, M8 quality gates,
  M9 rich review 3D), `docs/WORK_PACKAGES.md` (WP-IFC + WP-DRAWINGS-V2 done,
  two new claims), `TEAM_STATUS.md`.

## Grok / any agent

1. Pull `main`; CI is stricter than before — run `ruff check .` and
   `python -m mypy` locally before pushing.
2. Stay out of the two claimed freeze zones above until they land.
3. Everything else (server, CLI, Docker, launch surface) is open.

## Decentralized surface (unchanged, from 2026-07-15)

- `skills/llm-bim/SKILL.md` — portable agent instructions (any LLM)
- `llmbim ops --schema` → `skills/llm-bim/ops.schema.json`
- `docs/LOCAL.md` + `scripts/install_local.ps1` / `.sh` · MCP: `llmbim mcp`
