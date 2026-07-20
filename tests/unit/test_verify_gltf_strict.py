"""SSOT §2.4 regression: strict glTF verification must catch the
"green VERIFY, black viewer" bug class (docs/EQUIPMENT_3D_AND_DEVICE_SSOT.md).

Indices must be LOCAL to each primitive's POSITION accessor (0 <= i < count).
Reintroducing a global ``vert_base`` packing scheme must turn VERIFY red.
"""

from __future__ import annotations

import base64
import json
import shutil
import struct
from pathlib import Path

from llmbim import Project
from llmbim_drawings.deliverables import _verify_gltf_strict, verify_pack

_INDEX_FMT = {5121: ("<B", 1), 5123: ("<H", 2), 5125: ("<I", 4)}


def _equipment_project() -> Project:
    """>= 2 equipment material keys (shell + magnet) plus a pipe (SSOT §2.4.1)."""
    p = Project.create("Gltf Strict Rig")
    p.add_level("L1", 0)
    p.create_equipment_box(
        level="L1",
        origin=(0, 0),
        size=(500, 320, 320),
        name="Shell",
        kind="shell",
        centered=True,
    )
    p.create_equipment_box(
        level="L1",
        origin=(1200, 0),
        size=(400, 400, 200),
        name="Magnet",
        kind="magnet",
        centered=True,
    )
    p.place_pipe(level="L1", nps="3/4", start=(0, 800), end=(2000, 800))
    return p


def _corrupt_add_vert_base(gltf_path: Path) -> None:
    """Rewrite ONE primitive's indices as absolute (index + vert_base beyond the
    primitive's POSITION count) — the exact §2.2 bug shape."""
    data = json.loads(gltf_path.read_text(encoding="utf-8"))
    accessors = data["accessors"]
    buffer_views = data["bufferViews"]
    for mesh in data.get("meshes") or []:
        for prim in mesh.get("primitives") or []:
            if "indices" not in prim or "POSITION" not in (prim.get("attributes") or {}):
                continue
            pos_acc = accessors[int(prim["attributes"]["POSITION"])]
            vert_base = int(pos_acc["count"])
            idx_acc = accessors[int(prim["indices"])]
            fmt, size = _INDEX_FMT[int(idx_acc["componentType"])]
            bv = buffer_views[int(idx_acc["bufferView"])]
            buf_i = int(bv.get("buffer", 0))
            buf = data["buffers"][buf_i]
            uri = str(buf["uri"])
            assert uri.startswith("data:"), "expected embedded base64 buffer"
            head, b64 = uri.split(",", 1)
            blob = bytearray(base64.b64decode(b64))
            off = int(bv.get("byteOffset", 0)) + int(idx_acc.get("byteOffset", 0))
            n = int(idx_acc["count"])
            assert n > 0 and vert_base > 0
            for k in range(n):
                (val,) = struct.unpack_from(fmt, blob, off + k * size)
                struct.pack_into(fmt, blob, off + k * size, val + vert_base)
            buf["uri"] = head + "," + base64.b64encode(bytes(blob)).decode("ascii")
            gltf_path.write_text(json.dumps(data), encoding="utf-8")
            return
    raise AssertionError("no indexed primitive found to corrupt")


def test_verify_reports_strict_gltf_green(tmp_path: Path) -> None:
    p = _equipment_project()
    out = tmp_path / "pack"
    man = p.export_deliverables(out)
    verify = json.loads((out / "VERIFY.json").read_text(encoding="utf-8"))
    # §2.4.3: every index local to its primitive's POSITION accessor
    assert verify["gltf_valid"] is True
    assert verify["gltf_index_errors"] == 0
    # §2.4.5: materials / meshes >= 2 (shell, magnet, pipe are distinct keys)
    assert verify["gltf_material_count"] >= 2
    assert verify["gltf_mesh_count"] >= 2
    # §2.4.4: overall bbox extent > 0
    assert verify["gltf_bbox_extent_mm"] > 0
    # a green strict check flows into the manifest
    assert man["verification"]["gltf_valid"] is True


def test_absolute_indices_fail_strict_check_and_verify_pack(tmp_path: Path) -> None:
    p = _equipment_project()
    good = tmp_path / "pack"
    p.export_deliverables(good)
    assert verify_pack(good)["ok"] is True, "baseline pack must verify green"

    bad = tmp_path / "pack_bad"
    shutil.copytree(good, bad)
    _corrupt_add_vert_base(bad / "model.gltf")

    g = _verify_gltf_strict(bad / "model.gltf")
    assert g["gltf_valid"] is False
    assert g["gltf_index_errors"] > 0
    assert any("out of range" in f for f in g["failures"])

    # §2.4: VERIFY must fail — a green VERIFY with a black viewer is worse
    # than a loud export error.
    v = verify_pack(bad)
    assert v["gltf_valid"] is False
    assert v["ok"] is False
