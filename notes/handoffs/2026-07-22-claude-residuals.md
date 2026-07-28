# Handoff — Claude — 2026-07-22 (post re-grade B)

Authoritative work queue: **§Re-grade residuals** table in
`docs/EXCELLENCE_AUDIT_2026-07-21.md` (15 ranked items, lanes assigned).
Full evidence: `docs/audit/2026-07-22-regrade.json`.

## Claude is executing NOW (parallel worktree branches → PRs)

| Item | Scope |
|------|-------|
| #7 + #15 | `size_route` accepts `kind='conduit'` (mep_sizing.py:733); `fab_brep.py` mypy-strict |
| #6 + #8 + calc-unify | `route_mep` rework: Manhattan A* via `mep_autoroute` (kill diagonal runs), ports/terminals/`IfcRelConnectsPorts` in IFC, fire-sprinkler exemption recorded in basis (not invented), calc strings generated from the SAME `mep_sizing` results the routing uses (fixes 3/4" calc vs NPS-1 takeoff drift) |
| #2 | wire `render_hero_svg` into `export_deliverables` + index.html (rank-2, "either" lane — claiming; minimal diff in deliverables.py) |
| #12 + #11 | detail textures for MEP/equipment material keys; emissive luminaire keys where genuine |

## Grok's lane — please claim from the residuals table

- **#1 (BLOCKER): MEP-101/201/301 draw the routed model geometry** — the model now
  carries 30 pipes / 3 ducts / 7 conduits (soon A*-routed + ports); the sheets still
  render note-overlay dots. Switch the register entries from `svg_plans.mep_plan_svg`
  custom SVGs to plan-kind with an MEP include-set + symbols/tags/legend.
- #3 pdf_binder lineweights/dashes/fills/arcs · #4 imperial scale bar (sheets.py:82)
  · #5 PDF MediaBox + scale note honesty · #9 legend occlusion on A2-1/A2-2/A3-1
  · #10 SHEET_INDEX pagination + cover rows · #13 A1-1 annotation collisions.

If any of Claude's PRs conflict with your in-flight work, comment on the PR — do not
force-push over it. Reference project under review: https://github.com/earthtojake/text-to-cad
(analysis will land in `docs/REFERENCE_TEXT_TO_CAD.md`).
