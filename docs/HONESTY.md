# Corrected honesty model

We no longer frame the product as “only engineering estimates.”  
That phrase described **geometry fidelity class**, not software incompleteness.

## What the software **is**

| Claim | Status |
|-------|--------|
| Full agent-operated BIM for buildings, sites, and equipment | **Yes** |
| LLM-native authoring that GUI tools cannot match | **Yes — primary moat** |
| Accept open-ended domains via generic elements + ops | **Yes** |
| Import DXF / IFC / STEP / CSV / JSON / scripts | **Yes** |
| Export IFC / STEP / glTF / DXF / SVG / PDF / BOQ / ZIP | **Yes** |
| Presentation 3D studio (orbit, section cut, bloom, Imagine env, layers) | **Yes** (`viewer3d.html`) |
| Builder tools (BOQ+CSI, clash, rules, phases) | **Yes** |
| Designer tools (templates, types, notes, tags, grids) | **Yes** |
| Extensible without core rewrite (`register` ops) | **Yes** |
| Real program fixtures (INTEC + Proto10) end-to-end | **Yes** |

We are not a Revit clone. We are the **agent-first** BIM stack: same coordination deliverables, zero drafting UI, continuous model mutation by LLMs.

## What geometry means (precision class)

| Representation | Use |
|----------------|-----|
| Parametric walls/slabs/rooms/openings | Building authoring source of truth |
| Equipment box / faceted cylinder solids | Coordination **envelopes** (MEP/structure presentation) |
| **Fab feature-tree BREP** (`fab_part` + CadQuery/OCP) | Machine parts: box/cyl/hole/**fillet/chamfer**/**thread**, true STEP |
| **GD&T** (`gdt_datum` / `gdt_fcf` / `gdt_size`) | Datums + feature control frames + size tols on fab parts |
| Locked external STEP (Fusion, etc.) | Vendor BREP preserved by reference when not re-authored here |
| IFC SPF | Coordination exchange (not every MVD certified) |

**Fab path (optional extra `llmbim[fab]`):** agents author a parametric feature history → OpenCascade rebuilds a true BREP → STEP + tessellated glTF + GD&T SVG. Threads use helical groove solids + ISO designations (e.g. `M10x1.5`). GD&T is **model data for manufacturing intent**, not a PE-stamped inspection certificate.

## What we still don’t pretend

- Autodesk-certified Revit family marketplace replacement  
- Code-stamped life-safety / structural PE package  
- Real-time multi-user worksharing like BIM 360  

Those are **product/process certifications**, not “the code can’t do the job.”

## Operating promise

**If a user can describe a building, site, or part as data or a script, the system can store it, query it, check it, document it, and export it.**  
Unknown domains use `create_generic` + params until a specialized op is registered.
