# Equipment 3D, device SSOT, and Proto-10 lessons

**Audience:** Claude, Grok, or any agent working on llm-bim geometry, viewer, examples, or machine-scale packs.  
**Not a handoff.** This is a detailed engineering record of what failed, what was fixed, and what the repo still needs so design and modeling execute reliably.  
**Evidence base:** End-to-end Proto-10 (MB-SEP-PROTO) build from Eigen SSOT → deliverables pack → `viewer3d.html` (2026-07 session).

Related docs: `HONESTY.md` (geometry fidelity class), `LOCAL.md` (run/serve), `CAPABILITY.md`, `skills/llm-bim/SKILL.md`.

---

## 1. Summary

llm-bim’s building and MEP path is usable. **Machine / equipment packs** (hollow tubes, windings, radial ports, multi-system skids) exposed several gaps:

1. A **glTF export bug** made multi-layer models render as a black canvas while the UI claimed success.  
2. The **viewer** assumed building-scale scenes (fog, layer naming, CDN, optional giant HTML embed).  
3. The **geometry API** is axis-aligned and plan-first; radial ports and 3D winding nests require workarounds.  
4. **Device SSOT** (Eigen JSON + Python) was bridged in an example script rather than a reusable contract.  
5. **Process systems** (GAS/VAC/CW/PROC/SIG, phase-colored RMF, skids) needed ad-hoc materials and routing.

The product direction is right: agent-first BIM without a drafting UI. The highest leverage work is **export correctness**, **machine-oriented primitives**, and **a stable device→BIM adapter**—not more building schedules.

---

## 2. Critical bug: black 3D viewer with green VERIFY

### 2.1 Symptom

- Pack built; `VERIFY.json` ok; `viewer3d.html` loaded.  
- Status text could show “Studio ready” with **one layer** named after the project (e.g. `MB-SEP-PROTO Proto10 Separator`).  
- Viewport **completely black** (no floor grid, no solids).

### 2.2 Root cause

In `packages/geometry/llmbim_geometry/mesh.py` → `export_gltf_walls`:

- Positions and normals for all material layers are **packed into one buffer**.  
- Each mesh primitive gets a POSITION accessor with `byteOffset` into that buffer and `count = n_verts` for **that layer only**.  
- Indices were written as **absolute** indices into the packed list (`vert_base + i`).  

Per glTF 2.0, indices address the **primitive’s attribute accessors**, which are already offset. Valid indices for a layer with 288 verts are `0..287`, not `8000..8287`.

Effect: only the first layer’s indices were valid (or loaders produced empty/invalid draws). Later layers were broken. Combined with layer-name collapse, the scene looked empty.

### 2.3 Fix (landed)

- Emit **relative** indices `0..n_verts-1` per layer.  
- Guard: reject out-of-range indices; refuse layers with `n_verts > 65535` under uint16 indices.

### 2.4 Required regression (not optional)

Add a unit test that:

1. Builds a model with **≥2** equipment material keys (e.g. pedestal + shell + magnet).  
2. Exports glTF.  
3. For every mesh primitive, every index `i` satisfies `0 ≤ i < position_accessor.count`.  
4. Overall bbox volume (or extent) is **> 0**.  
5. Prefer: number of materials / nodes ≥ 2.

**VERIFY should fail** if index checks fail. A green VERIFY with a black viewer is worse than a loud export error.

Do **not** reintroduce packing schemes that add a global `vert_base` to indices while keeping per-primitive sliced accessors.

---

## 3. Viewer (`viewer3d.html` / `viewer3d.py`)

### 3.1 What works well

- Orbit / pan / zoom, layer list, opacity, section cut, optional bloom.  
- Studio materials once geometry is valid.  
- Layer toggles (hide yoke/magnets to read winding).  

### 3.2 Problems observed

| Issue | Detail | Direction |
|--------|--------|-----------|
| **file://** | ES modules + fetch need HTTP | Always document: serve pack dir, open `viewer3d.html` only |
| **Two tabs** | Opening index + viewer confuses “does it work?” | CLI/docs: one URL for 3D review |
| **Embedded glTF** | Large models inlined → multi‑MB HTML, slow parse | Default: **fetch** `model.gltf` when file is large |
| **Fog** | `density = 0.28 / maxDim` on a ~0.8 m machine ≈ dense fog | Cap fog for equipment scale (landed heuristic) |
| **Layer names** | Scene title used for every mesh → one bogus layer | Prefer mesh / material names; ignore scene-like titles |
| **CDN** | Three.js from unpkg | Optional vendor under pack `assets/` for offline |
| **Server dies** | Background `http.server` exits → “can’t reach page” | Durable serve recipe in LOCAL.md; or `llmbim serve` points at pack |

### 3.3 Serve recipe (canonical)

```powershell
cd C:\Users\ryanv\llm-bim\output\proto10_separator
python -m http.server 8765
# only:
# http://127.0.0.1:8765/viewer3d.html
```

Do not open `file:///.../viewer3d.html`. Do not require opening `index.html` for 3D review.

### 3.4 Suggested CLI

```text
llmbim case proto10 --open-viewer
# or
llmbim view output/proto10_separator
```

Behavior: ensure pack exists, start or reuse HTTP server, open **one** browser tab to `viewer3d.html`.

---

## 4. Coordinate systems and mental model

### 4.1 Eigen Proto-10 (device)

- Units: mm.  
- +Z along bore, end A → end B.  
- Origin: shell end A face (fab_spec convention).  
- Radial: winding `_xyz(r, θ, z)` → Cartesian `[r cos θ, r sin θ, z]`.  
- SSOT: `scripts/proto10_design_basis.py` (live), `cad/fusion/proto10_params.json`, `cad/picogk/proto10_fab_spec.json`, `scripts/proto10_winding.py` (coils/leads/glands).

### 4.2 llm-bim plan + elev (builder)

Typical map used in `examples/proto10_separator.py`:

| Eigen | llm-bim |
|--------|---------|
| +Z along bore | plan **+X**, origin at shell mid-length |
| Radial X = r cos θ | plan **Y** |
| Radial Y = r sin θ | elevation **z** = bore_axis + r sin θ |
| Pedestal height | lifts bore axis above z = 0 |

Equipment **cylinders** in the mesh exporter run **along plan +X** (good for bore-aligned shells, magnets, flanges). **Radial** KF stubs are not first-class; they are approximated with oriented boxes / short runs.

Honesty class for this pack remains **FAB-INTENT / ENGINEERING ESTIMATE** envelopes and presentation routing—not NQA fab or PE-stamped P&ID.

---

## 5. Geometry API: building-first limits for machines

### 5.1 What works for machines today

- `create_equipment_box(..., shape="cylinder", id_mm=..., wall_mm=...)` → hollow tubes/rings in glTF.  
- Material keys by `kind` (shell, yoke, magnet, cartridge, flange, …).  
- `place_wire` plan start→end at constant elevation; vertical riser if `orientation="vertical"`.  
- `place_pipe` for GAS/VAC/CW/PROC with catalog nps + material.  

### 5.2 Pain points (Proto-10)

1. **Radial ports**  
   KF40 stubs should lie along the shell outward normal. Only +X cylinders exist → AABB / box fakes.  

2. **3D polylines**  
   Eigen coil nests and lead spokes are true 3D polylines. Approximation = many short wire segments (Proto-10 hit **~1100+ wires**). Slow export, heavy glTF, hard to edit.  

3. **Phase identity**  
   Needed explicit materials `wire_phase_a/b/c` and `system`/`phase` on wires. Not in a published catalog for agents.  

4. **Pipe nps strictness**  
   `"1.5"` fails; must be `"1-1/2"`. Error is `Unknown pipe` without listing allowed nps.  

5. **Element count explosion**  
   Decimated winding paths still dominate model size; VERIFY/export time grows.  

### 5.3 Recommended API additions

**A. Oriented tube / port**

```text
place_tube(
  origin_mm, direction_unit, length_mm,
  od_mm, id_mm=None, kind="port", name=...
)
```

Or extend equipment with `axis: "x" | "y" | "z" | (dx,dy,dz)`.

**B. Path wire / tube**

```text
place_wire_path(
  points_mm: [[x,y,z], ...],
  diameter_mm,
  phase="A"|"B"|"C"|None,
  system="RMF_A",
  wire_role="coil"|"lead"|"hose"|"signal",
  name=...
)
```

Implementation options:

- One element + tessellate polyline in `mesh.py` (preferred for glTF size).  
- Or keep multi-segment but batch into one mesh bucket per phase.

**C. nps normalization**

In `place_pipe` / `resolve_fitting_part_id`:

- `1.5` → `1-1/2`, `1.25` → `1-1/4`, trim spaces.  
- On failure, list known nps for that material family.

**D. Stable kind → material map**

Document and freeze (extend `_gltf_material_key` carefully):

| kind / system | material key |
|---------------|--------------|
| shell, yoke, magnet, cartridge, flange | equip_* |
| kf40_port, kf25_port, port | equip_port |
| turbo, pump, roughing | equip_vacuum |
| gauge, rga, probe, sensor | equip_sensor |
| gas, feed | equip_gas |
| collection, canister | equip_collection |
| chiller, manifold | equip_chiller |
| controls, terminal | equip_controls |
| RMF_A / phase A | wire_phase_a |
| RMF_B / phase B | wire_phase_b |
| RMF_C / phase C | wire_phase_c |
| SIG / hose trunk | wire_lead |
| process pipe | pipe_process |
| copper CW | pipe_copper |

---

## 6. Device SSOT → BIM (Proto-10 pattern)

### 6.1 What the example does now

`examples/proto10_separator.py` (requires `EIGEN_ROOT`):

1. Load fab_spec **solids[]** (shell, cart, magnets, spacers, yoke, flanges, collectors).  
2. Prefer live `proto10_design_basis.PROTO10` over frozen JSON.  
3. Import `proto10_winding`: `coil_loops`, `lead_runs`, `gland_table`.  
4. Phase-color paths; route glands → hose break → RMF drive rack.  
5. RFQ **penetration allocation**: named KF40/KF25 roles, ISO63 source/turbo.  
6. Skids: gas rack, chiller, roughing, instrument rack, product canisters.  
7. Pipes/signals: GAS, VAC, CW, PROC, SIG, BIAS.  

### 6.2 What should be in core (not only the example)

A versioned **device pack schema** (JSON or Python dataclass), e.g.:

```yaml
# conceptual — not yet implemented
schema: llmbim.device_pack/v1
meta: { doc, honesty, units: mm }
solids: [ { name, kind: tube|flange_disk|plate, z0, z1, r_inner, r_outer, material } ]
winding: { phases, paths: [ { phase, points: [[x,y,z],...], role } ] }
ports: [ { role, interface: KF40|KF25|ISO63, z, theta_deg, end: A|B } ]
services: [ { system, from, to, medium } ]
skids: [ { id, kind, origin, size } ]
```

Then:

```text
load_eigen_proto10(eigen_root) -> DevicePack
build_device(project, pack) -> stats
export_deliverables(...)
```

Benefits: tests without Eigen on disk (fixture pack), INTEC and other machines reuse the same builder, agents don’t re-invent RFQ roles every session.

### 6.3 Eigen RFQ port map (reference)

From Eigen `docs/Proto10_RFQ_Package.md` (penetration allocation):

**End A (source):** ISO63 = plasma source · KF40 = gas feed, optical viewport, Langmuir/B-dot, spare electrical · KF25 = capacitance manometer · glands = phases A+C power+water.  

**End B (pump/probe):** ISO63 = turbo (~115 L/s) · KF40 = axial probes, RGA, collector bias/signal, viewport · KF25 = wide-range gauge · glands = phase B power+water.

Presentation wiring in the example follows this allocation; it is **not** a PE-stamped P&ID.

---

## 7. Honesty and claims

Align with `HONESTY.md`:

| Claim | OK? |
|--------|-----|
| Agent can produce coordination BIM + presentation 3D for Proto-10 | Yes, when glTF export is correct |
| Dimensions from Eigen SSOT | Yes, when EIGEN_ROOT set |
| Fab-intent hollow envelopes | Yes |
| Full winding nest as true CAD | No — polyline approximations |
| Process lines as construction documents | No — presentation routing |
| VERIFY green ⇒ visually correct 3D | **No until index/bbox checks exist** |

Keep pack meta fields: `honesty`, `form_rules`, `ssot_files`, `params_source`.

---

## 8. Work package suggestions (for Claude or any owner)

Priority order for “design and modeling execute better”:

### P0 — Correctness

1. glTF multi-layer **index + bbox** unit tests; wire into VERIFY.  
2. Do not regress relative indices.  
3. Document single-tab HTTP viewer recipe in `LOCAL.md` and skill recipes.

### P1 — Machine geometry

4. `place_wire_path` (or batched path mesh).  
5. Oriented tube / radial port primitive.  
6. nps normalization + better pipe errors.  

### P2 — Device productization

7. `DevicePack` schema + `build_device()`.  
8. Eigen adapter as thin loader; fixture JSON in `tests/fixtures/`.  
9. Recipe under `skills/llm-bim/recipes/` for Proto-10 / equipment.  

### P3 — Viewer polish

10. Optional vendored Three.js.  
11. Equipment camera presets (iso, end-A, end-B, section through bore).  
12. `llmbim view <pack>` one-shot serve + open.

### Stay out of (unless claimed)

- IFC freeze zone (`packages/ifc/**`) if still reserved for a dedicated IFC work package.  
- Rewriting building drawings MVP for machine packs.

---

## 9. Freeze / ownership notes

From earlier team board practice:

| Area | Risk if concurrent edit |
|------|-------------------------|
| `packages/geometry/llmbim_geometry/mesh.py` | Black viewers; coordinate with any 3D work |
| `packages/drawings/.../viewer3d.py` | Viewer regressions |
| `examples/proto10_separator.py` | Demo script; OK to iterate with Eigen |
| `packages/ifc/**` | Honor freeze if IFC WP is claimed |

Announce claims in team status when touching mesh export or VERIFY schema.

---

## 10. Operational checklist (human or agent)

Before saying “3D is done”:

1. Rebuild pack with current code.  
2. Confirm `model.gltf` materials list has **multiple** expected keys (not one project-title layer).  
3. Serve pack over HTTP; open **only** `viewer3d.html`.  
4. Confirm status is not stuck on “Loading” and viewport is not pure black.  
5. Spot-check hollow magnets/shell, phase colors if winding present, at least one pipe/skid if services wired.  
6. If page won’t load: server died — restart `python -m http.server` from pack directory (not repo root).

---

## 11. File map (session outcomes)

| Path | Role |
|------|------|
| `packages/geometry/llmbim_geometry/mesh.py` | glTF export; relative indices; phase/skid materials |
| `packages/drawings/llmbim_drawings/viewer3d.py` | Studio viewer; fog/layers/embed policy |
| `packages/core/llmbim_core/assignment.py` | `place_wire` vertical + phase/role |
| `examples/proto10_separator.py` | Eigen device build + services wiring |
| `output/proto10_separator/` | Generated pack (not source of truth) |
| Eigen `cad/picogk/proto10_fab_spec.json` | Solids SSOT |
| Eigen `scripts/proto10_winding.py` | Coils, leads, glands |
| Eigen `docs/Proto10_RFQ_Package.md` | Port penetration allocation |

---

## 12. Bottom line for Claude

- The stack can look “complete” (exports, VERIFY, HTML) while **3D is wrong**. Prioritize **glTF validity tests** and machine-scale geometry over new building features when touching this path.  
- **Hollow equipment + phase materials + HTTP viewer** are the right bones; fill in **path tubes, oriented ports, device pack schema**, and **strict VERIFY**.  
- Proto-10 is the stress test: multi-layer meshes, dense paths, multi-system skids. Anything that passes Proto-10 presentation quality will generally pass simpler building packs.  
- Keep honesty language honest: presentation / fab-intent envelopes, Eigen-driven dimensions, not certified fab or PE packages.

When implementing, prefer small PRs: (1) glTF tests + VERIFY, (2) path/oriented primitives, (3) DevicePack + recipe—without mixing IFC freezes or launch-stack churn unless claimed.
