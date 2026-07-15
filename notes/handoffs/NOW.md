# NOW — evolution for builders & designers

**Updated:** 2026-07-15 by Grok

## Shipped this evolution

- Product **types** catalog (wall/door/window assemblies + costs)
- **BOQ** quantities + est. cost (`boq.json` / CLI / API / MCP)
- **Clash** AABB reports
- **Design rules** (egress width, wall height, shield wall types, …)
- **DXF** plan export for CAD handoff
- **Templates**: office_bay, warehouse, hot_cell_bay, lab_bench
- **Notes**, **phases**, **set_type**
- Review UI: **Three.js glTF** + plan + BOQ/clash badges
- Pack includes boq, clash, rules, dxf, zip, index.html

## Claude when free

- Optional: IFC quality / MVD
- Optional: deeper rules library
- Do not rewrite BOQ/clash/deliverables without STATUS claim

## Commands

```
llmbim template --list
llmbim template hot_cell_bay
python scripts/verify_all.py
```
