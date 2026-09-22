# INTEC → llm-bim methodology (going forward)

**Audience:** any agent building industrial / machine facilities with llm-bim
(INTEC FP Separation Facility, Proto10 separators, Walsh design-intent packs).

**Evidence base:** Eigen `claude/intec-g4-collab` pipeline (2026-07…08) —
multi-part densifiers, imperial display, plan label budget, proto10 machine
import. This doc is the **llm-bim-side contract** so future packs do not
regress to bare boxes, metric-only sheets, or label soup.

Related: `EQUIPMENT_3D_AND_DEVICE_SSOT.md`, `CD_COMPLETENESS_STANDARD.md`,
`HONESTY.md`, `skills/llm-bim/SKILL.md`.

---

## 1. Units SSOT vs display

| Layer | Unit | Rule |
|-------|------|------|
| Project model store | **millimetres** | Always. `Project.create(...)` stores mm. |
| Eigen engine / fusion bridge | **metres** | Facility SSOT; pack multiplies by 1000. |
| Construction sheets | **metric** (default) or **imperial** | Display only — ft-in dimension strings, imperial scale notes. |

### API (wired)

```python
p.export_deliverables(out_dir, units="imperial")   # Walsh / US review
p.export_construction_set(out_dir, units="imperial")
# export_deliverables(..., units=) → construction.export_construction_set
```

Do **not** convert model geometry to feet. Do **not** invent dual geometry
stores. Dim text and scale notes switch; solid origins stay mm.

---

## 2. Multi-part machines, not single boxes

Bare `create_equipment_box` envelopes are **LOD0 placeholders**. Production
machines must densify into named parts:

| Shape (engine solids) | Meaning | llm-bim placement |
|-----------------------|---------|-------------------|
| `box` | Skid, pedestal, panel, manifold | `create_equipment_box(shape="box")` |
| `xcyl` | Vessel / tube along +X | `create_equipment_box(shape="cylinder")` +X |
| `zcyl` | Vertical cylinder | box footprint 2r×2r×L (kernel cyl is +X-only) or `axis_dir` tube API |
| `ycyl` | Cylinder along +Y | box envelope until oriented-cyl primitive is first-class |

### Kind → material (PBR)

Alias process roles onto kernel kinds so glTF studio colour-codes systems:

- `vessel` → `shell` (hollow tube defaults when `wall_mm` / `id_mm` set)
- `saddle` / `footing` → `pedestal`
- `port` → `port`
- `manifold` → `manifold`
- `panel` → `controls`

### Import pattern (full machine from a detailed pack)

When a machine already has a high-detail llm-bim pack (e.g. Proto10
`mb-sep-proto_proto10_separator-*/model.llmbim.json` with ~65 equipment solids):

1. Load template parts relative to shell centerline.
2. Anisotropic scale: axial = vessel_L / shell_L; radial = vessel_OD / shell_OD.
3. Place every solid at each bay tag (SEP-01…08).
4. Append facility-only interfaces (spine double-door port, etc.).
5. Honesty: `[ENGINEERING ESTIMATE]` scaled design-intent — not PE fab STEP.

Eigen implementation: `scripts/intec_sep_proto10_import.py` →
`generate_intec_sep_component_set.densified_solids` →
`intec_fusion_bridge.build_solids` → `cad/llmbim/intec_facility_pack.py`.

**Do not** re-author the machine as a single cylinder when a multi-part pack
exists.

---

## 3. Plan / sheet readability (pipeline corrections)

### 3.1 Equipment label budget

Plans with 1k+ equipment parts must **not** label every solid.

- Skip micro parts: skid posts/rails, bolts, footings, sensor rails, JB boxes.
- Skip footprints &lt; ~0.25 m².
- Cap untagged labels (~48 largest-first); tagged leaders ~60.
- Collision nudge (`_LabelNudge`) so labels do not stack.

Implemented in `llmbim_drawings.plan` (commit lineage: equip label budget).

### 3.2 Room names

Room tags: clean name over boxed number — **no** `"NUMBER Name"` double-print.
Strip redundant leading numeric tokens when the room number is already boxed.

### 3.3 Schedule sheet IDs

Overflow schedule pages use **numeric** suffixes (`A-501-02`, …), never
invalid path characters (`A-501[`).

### 3.4 Enlarged / station plans (engine side)

When Eigen emits enlarged station sheets: **centroid-clip** to the station
envelope; keep note windows from overwriting plan geometry. (Engine concern;
llm-bim construction crops honor explicit sheet windows.)

---

## 4. Drawing export completeness

For industrial design-intent (G4, not PE CDs):

| Artifact | Expectation |
|----------|-------------|
| Construction SVG set | A/S/M/P/E discipline sheets + equipment arrangement |
| Imperial dims | When `units="imperial"` |
| Equipment schedule | Multi-page safe IDs |
| glTF / viewer3d | Multi-material; hollow shells when wall/id set |
| VERIFY.json | Must fail if glTF index checks fail (see EQUIPMENT_3D) |
| Honesty | `[ENGINEERING ESTIMATE]` / design-intent; no PE fiction |

---

## 5. Facility pack checklist (agent)

1. **SSOT path:** engine → bridge JSON (metres) → facility_pack → llm-bim (mm).
   No retyped dimensions.
2. **Densify machines** before pack export (assemblies + imported packs).
3. **Export** with `units="imperial"` for US contractor / Walsh review.
4. **Label budget** already default in plan.py — do not re-enable full equip
   name dump on A-101.
5. **Dual-check:** part counts (SEP bay ≈ 65+ solids), VERIFY green, spot-check
   A-101 not soup, IMP detail sheets if Eigen engine regen ran.
6. **Owner split:** MB owns equipment; building envelope coordination only
   where contract says so.

---

## 6. What not to do

- Invent PE-stamped CDs or “as-built” language for design-intent packs.
- Drop multi-part densifiers back to one box per station for “simplicity.”
- Convert the project store to feet/inches.
- Label every micro skid part on the floor plan.
- Ship a black 3D viewer with green VERIFY (index bug class — see
  `EQUIPMENT_3D_AND_DEVICE_SSOT.md`).

---

## 7. Quick references (Eigen)

| Topic | Path |
|-------|------|
| Proto10 import | `Eigen/scripts/intec_sep_proto10_import.py` |
| SEP densify | `Eigen/scripts/generate_intec_sep_component_set.py` |
| Assemblies | `Eigen/scripts/intec_component_assemblies.py` |
| Facility pack | `Eigen/cad/llmbim/intec_facility_pack.py` |
| Imperial engine | `Eigen/scripts/intec_imperial.py` |
| Proto10 pack | `Eigen/output/mb-sep-proto_proto10_separator-*/model.llmbim.json` |
