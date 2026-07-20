"""Import external STEP (e.g. Fusion export) as locked equipment reference.

Parses CARTESIAN_POINT entities for a bounding box and stores a reference
to the original STEP file. Geometry remains in the external file; BIM holds
envelope + path for exchange packs.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from llmbim_core.ids import new_id
from llmbim_core.model import Element, ProjectModel

_POINT_RE = re.compile(
    r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*([-+eE0-9.]+)\s*,\s*([-+eE0-9.]+)\s*,\s*([-+eE0-9.]+)\s*\)\s*\)",
    re.IGNORECASE,
)


def parse_step_bbox(path: str | Path) -> dict[str, float] | None:
    """Return bbox in metres from CARTESIAN_POINT scan, or None if empty."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for m in _POINT_RE.finditer(text):
        x, y, z = float(m.group(1)), float(m.group(2)), float(m.group(3))
        # skip origin-only noise optionally
        xs.append(x)
        ys.append(y)
        zs.append(z)
    if len(xs) < 2:
        return None
    return {
        "xmin": min(xs),
        "ymin": min(ys),
        "zmin": min(zs),
        "xmax": max(xs),
        "ymax": max(ys),
        "zmax": max(zs),
        "point_count": float(len(xs)),
    }


def import_step_as_equipment(
    model: ProjectModel,
    step_path: str | Path,
    *,
    level: str,
    name: str | None = None,
    kind: str = "step_ref",
    copy_into: str | Path | None = None,
    units_mm_if_small: bool = True,
) -> Element:
    """Create locked equipment from STEP bbox.

    Coordinates in STEP are assumed metres. If the bbox is tiny (< 10 units
    max dim) and units_mm_if_small, treat as millimetres (common Fusion export).
    """
    step_path = Path(step_path)
    if not step_path.is_file():
        raise FileNotFoundError(step_path)

    bbox = parse_step_bbox(step_path)
    if not bbox:
        raise ValueError(f"No CARTESIAN_POINT data in {step_path}")

    dx = bbox["xmax"] - bbox["xmin"]
    dy = bbox["ymax"] - bbox["ymin"]
    dz = bbox["zmax"] - bbox["zmin"]
    max_dim = max(dx, dy, dz, 1e-12)
    # Heuristic: if largest dimension < 50, treat as metres; else millimetres
    if units_mm_if_small and max_dim < 50.0:
        unit_note = "m_scaled_to_mm"
        x0, y0, z0 = bbox["xmin"] * 1000, bbox["ymin"] * 1000, bbox["zmin"] * 1000
        lx, ly, lz = dx * 1000, dy * 1000, dz * 1000
    else:
        unit_note = "mm"
        x0, y0, z0 = bbox["xmin"], bbox["ymin"], bbox["zmin"]
        lx, ly, lz = dx, dy, dz

    stored_path = str(step_path.resolve())
    if copy_into:
        dest_dir = Path(copy_into)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / step_path.name
        shutil.copy2(step_path, dest)
        stored_path = str(dest.resolve())

    lv = model.get_level(level)
    el = Element(
        id=new_id("eqp"),
        category="equipment",
        name=name or step_path.stem,
        level_id=lv.id,
        params={
            "kind": kind,
            "shape": "box",  # envelope; true geometry in step_ref_path
            "locked": True,
            "step_ref_path": stored_path,
            "step_unit_note": unit_note,
            "step_point_count": int(bbox["point_count"]),
            "origin_mm": [x0, y0],
            "size_mm": [max(lx, 1.0), max(ly, 1.0), max(lz, 1.0)],
            "z0_mm": z0,
            "polygon_mm": [
                [x0, y0],
                [x0 + max(lx, 1), y0],
                [x0 + max(lx, 1), y0 + max(ly, 1)],
                [x0, y0 + max(ly, 1)],
            ],
            "bbox_native": bbox,
        },
    )
    model.add_element(el)
    return el


def pack_step_references(model: ProjectModel, pack_dir: str | Path) -> list[dict[str, Any]]:
    """Copy locked STEP refs into pack_dir/step_refs/ and return index."""
    out = Path(pack_dir) / "step_refs"
    out.mkdir(parents=True, exist_ok=True)
    index: list[dict[str, Any]] = []
    for el in model.elements:
        if el.category != "equipment":
            continue
        if not el.params.get("locked") or not el.params.get("step_ref_path"):
            continue
        src = Path(str(el.params["step_ref_path"]))
        if not src.is_file():
            index.append({"id": el.id, "name": el.name, "missing": str(src)})
            continue
        dest = out / f"{el.id[:12]}_{src.name}"
        shutil.copy2(src, dest)
        index.append(
            {
                "id": el.id,
                "name": el.name,
                "file": dest.name,
                "size_mm": el.params.get("size_mm"),
            }
        )
    if index:
        import json

        (out / "INDEX.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return index
