"""Drawing derivation API — contract frozen for WP-DRAWINGS (Claude).

Axes (plan): +X east, +Y north. Units: millimeters in the model.
SVG: +x right, +y down (standard); exporter should flip Y for plan readability
and document the transform in this module's docstring when implemented.

Grok freezes signatures. Claude implements. Do not change signatures without
updating docs/WORK_PACKAGES.md and STATUS.
"""

from __future__ import annotations

from pathlib import Path

from llmbim_core.errors import NotImplementedBimError
from llmbim_core.model import ProjectModel


def export_plan_svg(
    model: ProjectModel,
    level: str,
    path: str | Path,
    *,
    view_range_mm: float = 1200.0,
    scale: float = 0.05,
) -> None:
    """Horizontal cut at level elevation → SVG file."""
    raise NotImplementedBimError(
        "export_plan_svg not implemented — claim WP-DRAWINGS",
        package="drawings",
    )


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
    raise NotImplementedBimError(
        "export_section_svg not implemented — claim WP-DRAWINGS",
        package="drawings",
    )


def export_elevation_svg(
    model: ProjectModel,
    direction: str,
    path: str | Path,
    *,
    scale: float = 0.05,
) -> None:
    """Orthographic elevation. direction in {N,S,E,W}."""
    raise NotImplementedBimError(
        "export_elevation_svg not implemented — claim WP-DRAWINGS",
        package="drawings",
    )
