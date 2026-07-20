# Digital twins and TRL advancement — canonical vocabulary

How llm-bim models relate to device/component development maturity. This is
the **thin layer that belongs in the kernel repo**: shared vocabulary and
status carriage. Requirements, calculations, test data, and TRL *evidence*
live in the driver repo (e.g. Eigen) that points at llm-bim.

## The twin

A **digital twin** here = three artifacts, regenerated together:

1. **Basis module** — the only number source (requirements, room/loads program,
   member sizes). Engineering develops in parallel with coordinates.
2. **Model** — `model.llmbim.json` + its VCS history (`p.log()`).
3. **Pack** — 3D (glTF viewer), 2D (sheet register, PDF), STEP/IFC, BOQ,
   schedules, takeoffs — all derived, never hand-drawn.

The loop that makes it a *twin* rather than a drawing set: **basis → model →
3D/2D/STEP → prototype → test → basis update → regenerate.** Test results flow
back into the basis; the twin is rebuilt, never patched by hand.

## Twin fidelity levels

| Level | Name | Contents | Typical gate |
|-------|------|----------|--------------|
| F0 | Concept massing | Shells, generic boxes, notes | `verify_pack` ok (untyped walls expected) |
| F1 | Design development | Typed assemblies, structure, MEP routes, register | rules/clash clean, `walls_untyped == 0`, `[DESIGN DEVELOPMENT]` stamp |
| F2 | Construction / fab documents | Full CD register, details, schedules, drift-pin tests | golden command + CI guards (see `recipes/design_program.md`) |
| F3 | As-built / as-tested | F2 + test-driven basis updates, `verification` params set | evidence linked in driver repo |

## TRL mapping (device / component development)

TRL is a claim about **test evidence**. llm-bim never asserts a TRL — it
records the claim and points at the evidence. Artifact expectations per stage:

| TRL | Stage | llm-bim artifacts expected | Evidence (driver repo) |
|-----|-------|---------------------------|------------------------|
| 1–2 | Concept | F0 model, notes, `Q-` flags | literature, basis rationale |
| 3 | Proof of concept | Component model + **STEP** for bench prototype, BOM | bench data |
| 4 | Lab validation | **DevicePack** (`recipes/device_pack.md`), fab pack, takeoffs | lab test records |
| 5 | Relevant environment | Module (`export_module`) **integrated into facility twin** (`import_module`), clash clean | environment test data |
| 6 | System demo | Full facility twin, rules + hydraulic/duct sizing validated, F2 pack | system test campaign |
| 7–9 | Field / proven | F3 as-built twin updated from field data | field/ops records |

## Status carriage convention (params, not prose)

Set on the element (device, module instance, or system equipment):

```python
p.op("set_param", id=eid, key="trl", value=4)
p.op("set_param", id=eid, key="trl_evidence", value="eigen://tests/sep_skid/2026-07-bench.md")
p.op("set_param", id=eid, key="verification", value="bench_tested")
#   verification ∈ modeled | analyzed | bench_tested | field_tested
p.op("set_param", id=eid, key="twin_fidelity", value="F1")
```

Honesty rules apply exactly as everywhere else: these are **carried claims
with pointers**, queryable (`llmbim query model "category=equipment"` →
params) and schedulable — not certifications. A TRL param without a
`trl_evidence` pointer is an open question, not a fact.

## What does NOT belong in llm-bim

Test procedures and results, requirement traceability matrices, calc packages,
program schedules, TRL review board records. Those live in the driver repo;
the twin references them via `trl_evidence` pointers and doc sheets. Keep the
kernel a geometry + documentation engine.
