# Repair loop (failure taxonomy → smallest fix)

Map kernel / export failures to actions. Prefer **smallest** fix; never invent geometry.

| Class | Signals | Smallest fix |
|-------|---------|--------------|
| `VALIDATION_FAILED` | validate errors | Fix params (thickness, host, level); re-validate |
| `GEOMETRY_DEGENERATE` | zero-length wall, bad poly | Correct endpoints / boundary; delete bad element |
| Orphan host | door without wall | `p.repair()` or delete children first |
| Clash | AABB pairs | Move equipment, thin walls, re-route MEP |
| Export STEP skip | CadQuery/OCP missing | Ship glTF/IFC/drawings; note STEP optional honestly |
| Blank 3D | glTF tiny / missing | Re-export; open viewer3d not raw glTF |
| Empty takeoff | no fittings | Place fittings or annotate n/a per basis |
| Untyped walls | `walls_untyped` | `set_type` for occupancy |
| Diagonal MEP | residual #6 | Use `mep_autoroute` / orthogonal routes |

After each fix: `validate` → `export_deliverables` → review packet
(`references/review_packet.md`).
