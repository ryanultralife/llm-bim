"""One-shot deliverables pack: BIM + 3D + 2D + STEP + sheets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llmbim_core.model import ProjectModel
from llmbim_drawings.construction import export_construction_set
from llmbim_drawings.parts import export_part_pack
from llmbim_drawings.plan import write_plan_svg
from llmbim_drawings.schedules import export_schedule_csv
from llmbim_drawings.section import write_elevation_svg, write_section_svg
from llmbim_geometry.mesh import export_gltf_walls
from llmbim_geometry.step_export import export_step
from llmbim_ifc.export import export_ifc


def export_deliverables(
    model: ProjectModel,
    out_dir: str | Path,
    *,
    mode: str = "auto",
    plan_level: str | None = None,
    plan_scale: float | None = None,
) -> dict[str, Any]:
    """Write a full output pack.

    mode:
      - ``facility`` — construction sheets + facility STEP/IFC/glTF
      - ``part`` — part drawing pack + assembly STEP
      - ``auto`` — facility if any walls, else part pack; always both 3D formats
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    has_walls = any(el.category == "wall" for el in model.elements)
    has_equip = any(el.category == "equipment" for el in model.elements)
    if mode == "auto":
        mode = "facility" if has_walls else "part"

    level = plan_level or (model.levels[0].name if model.levels else "L1")
    if plan_scale is None:
        # crude auto scale from bbox
        plan_scale = 0.01 if has_walls else 0.4

    # Always: model, IFC, glTF, STEP assembly
    model_path = out / "model.llmbim.json"
    # ProjectModel.save expects ProjectModel — use model.save
    model.save(model_path)

    ifc_path = out / "model.ifc"
    export_ifc(model, ifc_path)

    gltf_path = out / "model.gltf"
    export_gltf_walls(model, gltf_path)

    step_path = out / "model.step"
    export_step(model, step_path, include_walls=has_walls)

    # Quick single views
    views = out / "views"
    views.mkdir(exist_ok=True)
    try:
        write_plan_svg(model, level, views / f"plan_{level}.svg", scale=plan_scale)
    except Exception as exc:  # noqa: BLE001
        (views / "plan_error.txt").write_text(str(exc), encoding="utf-8")
    try:
        write_elevation_svg(model, "S", views / "elev_S.svg", scale=plan_scale)
        write_elevation_svg(model, "E", views / "elev_E.svg", scale=plan_scale)
    except Exception:
        pass

    schedules = out / "schedules"
    schedules.mkdir(exist_ok=True)
    for kind in ("room", "door", "window", "wall"):
        try:
            export_schedule_csv(model, kind, schedules / f"{kind}.csv")
        except Exception:
            pass

    result: dict[str, Any] = {
        "mode": mode,
        "model": str(model_path.name),
        "ifc": str(ifc_path.name),
        "gltf": str(gltf_path.name),
        "step": str(step_path.name),
        "views": "views/",
        "schedules": "schedules/",
    }

    if mode in {"facility", "both"} or has_walls:
        cd = export_construction_set(
            model, out / "construction", plan_level=level, plan_scale=plan_scale
        )
        result["construction"] = cd

    if mode in {"part", "both"} or has_equip:
        parts = export_part_pack(model, out / "parts", scale=max(plan_scale, 0.2))
        result["parts"] = parts

    # dual mode for hybrid models (INTEC has both)
    if has_walls and has_equip and mode == "auto":
        parts = export_part_pack(model, out / "parts", scale=0.15)
        result["parts"] = parts

    manifest = {
        "project": model.name,
        "honesty": "ENGINEERING ESTIMATE — LLM-BIM agent deliverables pack",
        "outputs": result,
        "stats": model.stats(),
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
