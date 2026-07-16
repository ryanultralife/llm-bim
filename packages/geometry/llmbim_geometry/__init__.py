"""LLM-BIM geometry helpers — parametric BIM + optional fab BREP (CadQuery/OCP)."""

from llmbim_geometry.mesh import export_gltf_walls
from llmbim_geometry.primitives import (
    Vec2,
    distance,
    point_along_segment,
    polygon_area_mm2,
    wall_length_mm,
)
from llmbim_geometry.step_export import export_step, export_step_part
from llmbim_geometry.step_import import import_step_as_equipment, parse_step_bbox

try:
    from llmbim_geometry.fab_brep import HAS_CADQUERY, export_fab_step, rebuild_solid
except Exception:  # noqa: BLE001
    HAS_CADQUERY = False

    def export_fab_step(*_a, **_k):  # type: ignore
        raise RuntimeError("cadquery not installed")

    def rebuild_solid(*_a, **_k):  # type: ignore
        raise RuntimeError("cadquery not installed")


__all__ = [
    "HAS_CADQUERY",
    "Vec2",
    "distance",
    "export_fab_step",
    "export_gltf_walls",
    "export_step",
    "export_step_part",
    "import_step_as_equipment",
    "parse_step_bbox",
    "point_along_segment",
    "polygon_area_mm2",
    "rebuild_solid",
    "wall_length_mm",
]
