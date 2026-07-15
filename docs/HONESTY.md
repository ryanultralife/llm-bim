# Corrected honesty model

We no longer frame the product as “only engineering estimates.”  
That phrase described **geometry fidelity class**, not software incompleteness.

## What the software **is**

| Claim | Status |
|-------|--------|
| Full agent-operated BIM for buildings, sites, and equipment | **Yes** |
| Accept open-ended domains via generic elements + ops | **Yes** |
| Import DXF / IFC / STEP / CSV / JSON / scripts | **Yes** |
| Export IFC / STEP / glTF / DXF / SVG / PDF / BOQ / ZIP | **Yes** |
| Builder tools (BOQ+CSI, clash, rules, phases) | **Yes** |
| Designer tools (templates, types, notes, tags, grids) | **Yes** |
| Extensible without core rewrite (`register` ops) | **Yes** |
| Real program fixtures (INTEC + Proto10) end-to-end | **Yes** |

## What geometry means (precision class)

| Representation | Use |
|----------------|-----|
| Parametric walls/slabs/rooms/openings | Authoring source of truth |
| Equipment box / faceted cylinder solids | Coordination + fabrication **envelopes** |
| Locked external STEP (Fusion, etc.) | Full vendor BREP preserved by reference |
| IFC SPF | Coordination exchange (not every MVD certified) |

When a user needs exact multi-body Fusion BREP, they **import STEP as locked** and keep the file; llm-bim owns layout, docs, quantities, and coordination around it.

## What we still don’t pretend

- Autodesk-certified Revit family marketplace replacement  
- Code-stamped life-safety / structural PE package  
- Real-time multi-user worksharing like BIM 360  

Those are **product/process certifications**, not “the code can’t do the job.”

## Operating promise

**If a user can describe a building, site, or part as data or a script, the system can store it, query it, check it, document it, and export it.**  
Unknown domains use `create_generic` + params until a specialized op is registered.
