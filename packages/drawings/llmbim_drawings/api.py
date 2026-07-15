"""Drawing derivation API.

Axes (plan): +X east, +Y north. Units: millimeters in the model.
SVG: +x right, +y down; plan exporter flips Y for readable plans.
"""

from __future__ import annotations

from pathlib import Path

from llmbim_core.model import ProjectModel
from llmbim_drawings.plan import write_plan_svg
from llmbim_drawings.section import write_elevation_svg, write_section_svg


def export_plan_svg(
    model: ProjectModel,
    level: str,
    path: str | Path,
    *,
    view_range_mm: float = 1200.0,
    scale: float = 0.05,
) -> None:
    """Horizontal cut at level elevation → SVG file."""
    write_plan_svg(model, level, path, view_range_mm=view_range_mm, scale=scale)


def export_section_svg(
    model: ProjectModel,
    p0: tuple[float, float],
    p1: tuple[float, float],
    path: str | Path,
    *,
    depth_mm: float = 500.0,
    scale: float = 0.05,
) -> None:
    """Vertical section along plan segment p0→p1 → SVG file."""
    write_section_svg(model, p0, p1, path, depth_mm=depth_mm, scale=scale)


def export_elevation_svg(
    model: ProjectModel,
    direction: str,
    path: str | Path,
    *,
    scale: float = 0.05,
) -> None:
    """Orthographic elevation. direction in {N,S,E,W}."""
    write_elevation_svg(model, direction, path, scale=scale)
