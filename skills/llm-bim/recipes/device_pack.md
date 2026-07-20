# Device pack — device SSOT → BIM (Proto-10 pattern)

One JSON file is the machine's source of truth: params + components (kind, shape,
position, axis). Schema `llmbim.device_pack/v1` in `llmbim_core/device_pack.py`:

```json
{"schema": "llmbim.device_pack/v1", "name": "Proto10", "units": "mm",
 "origin_mode": "center", "params": {"bore_axis_z_mm": 900},
 "components": [
  {"id": "shell", "kind": "shell", "shape": "tube", "center_mm": [0, 0, 900],
   "axis": "x", "od_mm": 400, "id_mm": 380, "length_mm": 1200, "system": "PROC"},
  {"id": "coil_a", "kind": "coil", "shape": "wire_path", "phase": "A",
   "system": "RMF_A", "diameter_mm": 8, "points_mm": [[-300, 0, 1130], [-300, 230, 900]]}]}
```

Shapes: `box` (size_mm w,d,h) · `cylinder`/`tube` (od/id/length, axis x|y|z|[dx,dy,dz])
· `wire_path` (points_mm). Units `"m"` scale ×1000. Example: `tests/fixtures/device_pack_minimal.json`.

```python
from llmbim_core.device_pack import build_device, load_device_pack
pack = load_device_pack("tests/fixtures/device_pack_minimal.json")
res = build_device(p.model, pack, level="L1", origin_mm=(5000, 5000), name_prefix="P10-")
assert res["ok"], res["skipped"]  # element ids per component, warnings, honesty note
```

You get: equipment envelopes with glTF materials by kind/phase (shell, magnet,
kf40_port, wire_phase_a/b/c), EQ sheets, schedules and takeoffs via `export_deliverables`.
Tube/wire_path use the `place_tube`/`place_wire_path` ops when registered; otherwise the
builder falls back to +X cylinders / box envelopes / generic polylines and says so in
`res["warnings"]`. Fidelity: engineering estimate envelopes — not fab CAD (HONESTY.md).
