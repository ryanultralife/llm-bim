# Excellence Audit & Remediation — 2026-07-21

Adversarially-verified 9-dimension audit of the flagship Schad CD deliverable against the
north star: **anyone can create AE-quality renderings and CD sheets with FULL MEP and other
trades.** 74 agents, 63/64 findings survived verification. Full raw result archived at
`docs/audit/2026-07-21-excellence-audit.json` (also in run transcript).

## Verdict: **B-** — A-grade kernel, C-grade flagship

The engines are real and tested (Manhattan-A* MEP routing, Hazen-Williams/Darcy/Hunter sizing,
correct IFC4 with hosted-opening voids, element-aware glTF viewer, layered SVG drafting). The
flagship Schad build **does not exercise them where it matters**, so all three north-star legs
(CD sheets, renderings, full MEP) miss the bar. Fixes are **wiring / output-fidelity /
rendering**, not new science.

## Workstreams (ranked by north-star impact)

| # | Workstream | Impact | Effort | Owner | Status |
|---|------------|--------|--------|-------|--------|
| 1 | Wire routing+sizing engine into flagship (real MEP + trades) | **critical** | XL | **Claude** | ✅ done — PR #21 + #22 merged |
| 2 | CD plot-set fidelity (legibility, lineweights, scale, pagination) | **critical** | L | **Grok** | ✅ done — PR #20 merged |
| 3 | Discipline-sheet depth (symbols, underlay, schedule columns) | high | XL | Grok/drawings (after WS1) | queued (WS1 MEP geometry now on main) |
| 4 | Presentation rendering (textured PBR, material ext, AO, hero) | high | XL | **Claude** | 🟡 textured PBR done — PR #25 merged; material-ext/AO/hero remain (viewer lane) |
| + | IFC fidelity: IfcMaterial associations | med | S | **Claude** | ✅ done — PR #23 merged |

Lane split (observed from live git log 2026-07-21): **Grok owns `packages/drawings/**` + schad
plan-anatomy (WS2/WS3).** **Claude owns `packages/core` + `packages/geometry` kernel lanes
(WS1 engine + WS4 glTF).** Producer/consumer: Claude produces routed MEP geometry + IFC MEP
entities + takeoffs; Grok draws them.

---

## WS1 — Wire the routing+sizing engine into the flagship  *(Claude)*

**The #1 gap.** `*_takeoff.json` are all `[]`; `model.ifc` has zero MEP entities; the build
never calls a routing/sizing function. `schad_mep.py` hand-types sizes as literal strings.

Confirmed findings:
- BLOCKER: Schad CD has ZERO routed MEP — duct/pipe/conduit/cable_tray/rebar/connections
  takeoffs all `[]`; no `place_pipe|place_duct|place_conduit|mep_autoroute` call in projects/schad.
- BLOCKER: `model.ifc` has no MEP (no IfcPipeSegment/IfcDuctSegment/IfcFlowTerminal/IfcSystem).
- HIGH: `schad_mep.py` is a disconnected data/string layer; `mep_sizing` has zero callers in projects.
- HIGH: no conduit-fill (NEC Ch.9); `size_route` rejects `kind='conduit'` (mep_sizing.py:~561).
- MEDIUM: rebar unquantified for 17 footings+slab; `csi_takeoff` missing Div 03 20 00.

Seam: `build_llmbim.py::_build_mep_content()` (line 646) uses `schad_mep` layouts as notes only.
Plan: add `schad_mep.route_mep(p, ctx)` (new fn, additive) that routes DWV + domestic water +
radiant PEX + supply/return duct + feeders/branch conduit + sprinkler, anchored to the existing
fixture (x,y) layouts, sized from `mep_sizing`; hook with ONE call in `_build_mep_content`.
Kernel: conduit-fill in `mep_sizing.py`; IfcSystem + MEP entities in `ifc/export.py`; rebar
takeoff from foundations geometry; drift-pin test that flagship takeoffs are non-empty + IFC MEP > 0.

### WS1 checklist
**WS1a (MEP routing + IFC — the two blockers) — DONE, on branch `claude/ws1-mep-routing`:**
- [x] conduit-fill sizing (NEC Ch.9 Table 4/5, 240.4(D), 250.122) in `mep_sizing.py`
      (`conductor_for_amps`/`egc_for_amps`/`size_conduit`/`feeder_conduit`)
- [x] `schad_mep.route_mep()` routes DCW/SAN/vent/radiant/duct/power (30 pipe, 3 duct,
      7 conduit, 13 fittings); sizes from `mep_sizing` (WSFU→Hunter→size_pipe, CFM→size_duct,
      NEC fill→trade size)
- [x] one-line hook in `build_llmbim._build_mep_content`
- [x] IFC concrete IFC4 subtypes (IfcPipeSegment×30 / IfcDuctSegment×3 / IfcCableCarrierSegment×7)
      + `IfcSystem` grouping ×9 (DCW/SAN/RAD/SA/RA/EA/PWR/LTG/V) w/ IfcRelServicesBuildings
- [x] IFC importer recognizes the concrete subtypes (round-trip preserved)
- [x] drift-pin test `tests/unit/test_schad_mep_routed.py`
- [~] gates: ruff clean, mypy clean (only pre-existing fab_brep → WS4); full pytest re-running on branch

**WS1b (follow-on) — remaining:**
- [ ] rebar takeoff (Div 03 20 00) from footings/slab/stem-wall geometry (`rebar_takeoff` == [])
- [ ] extend `size_route` to accept `kind='conduit'` (fill functions exist; wire the whitelist)
- [ ] feed computed sizes back into `schad_mep` calc strings (drawing==takeoff==calc)

## WS4 — Presentation-grade rendering  *(Claude)*

- HIGH: glTF has zero textures/UVs (all POSITION+NORMAL) — flat pastels.
- HIGH: no glTF material extensions (glass = fake alpha; no emissive; no KHR_lights_punctual).
- MEDIUM: no AO/contact shadows in viewer; IBL from LDR JPEG.
- MEDIUM: no baked hero raster anywhere in the pack.
- LOW: 10 dead material-aggregate meshes bloat every glTF; fab_brep mypy-strict errors.

### WS4 checklist
- [ ] `mesh.py`: emit TEXCOORD_0 + TANGENT; tiling PBR texture sets (concrete/drywall/metal/wood)
- [ ] KHR_materials_transmission glass, emissive luminaires, KHR_lights_punctual rig
- [ ] drop dead aggregate meshes when element metadata present
- [ ] headless hero raster into pack + index.html/PDF cover (approach TBD in WS4)
- [ ] fab_brep.py mypy-strict clean (4 errors)
- [ ] gates green + commit

---

## Execution log
- 2026-07-21: audit complete (B-); Claude claims WS1+WS4 (kernel lanes); Grok live on WS2 (drawings).
- 2026-07-21: **WS1a merged (PR #21)** — route_mep places 30 pipe / 3 duct / 7 conduit / 13
  fittings sized from mep_sizing (+ NEC Ch.9 conduit fill); IFC gains concrete IFC4 subtypes
  (IfcPipeSegment/DuctSegment/CableCarrierSegment) in 9 IfcSystem trades. Full pytest 503.
- 2026-07-21: **WS1b merged (PR #22)** — footing rebar `(2) #4 CONT` quantified as CSI 03 20 00
  (139 m #4 Grade 60); unspecified stem/pad/slab bars left unquantified (not invented).
- 2026-07-22: **IFC materials merged (PR #23)** — 13 IfcMaterial + 132 IfcRelAssociatesMaterial
  (wall→Wood Framing, pipe→Copper, footing→Concrete…). Full pytest 510.
- 2026-07-22: **WS2 merged (PR #20, Grok)** — CD plot-set fidelity (path rendering, keynote gutter,
  scale). WS3 (discipline-sheet depth) now unblocked — WS1 routed MEP geometry is on main for Grok.
- 2026-07-22: **WS4 textured PBR merged (PR #25)** — new `gltf_textures.py` (pure-stdlib procedural
  concrete/drywall/metal/wood detail PNGs) + triplanar `TEXCOORD_0` UVs + `baseColorTexture` on
  architectural material layers. UVs appended at blob end (offsets unchanged); 0 buffer-bounds
  violations. Full pytest 513. glTF surfaces no longer flat pastels.
- 2026-07-22: Grok `pdf_binder` (PR #24) merged. Shared-tree race resolved — Grok isolated its tree.

## Remaining (next)
- **WS4 rendering (Claude, high, XL):** glTF textured PBR (TEXCOORD_0 UVs + tiling normal/roughness
  textures) is the biggest render win. Analyzed injection points: add a UV bufferView after nrm in
  the blob, a TEXCOORD_0 accessor per primitive in BOTH node loops (aggregate + per-element), and
  images/textures/samplers on materials. Risk: binary buffer offsets + `mesh.py` is a churned file
  (recent glTF commits) + the viewer (`viewer3d.py`, Grok's lane) consumes it. Do with worktree
  isolation or coordinated with Grok. Material extensions (KHR transmission/lights) risk regressing
  the in-app viewer's own light rig — coordinate before adding.
- **IFC follow-ons (Claude, low/med):** IfcMaterialLayerSet for multi-layer walls; georeferencing
  (IfcMapConversion) only if the basis carries a site CRS (else don't invent).
- **Coordination note:** the shared working tree races with a live Grok (a commit-race was
  untangled 2026-07-22). Prefer git worktrees for concurrent work.
