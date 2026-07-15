"""IFC4 export API — contract frozen for WP-IFC (Claude)."""

from __future__ import annotations

from pathlib import Path

from llmbim_core.errors import NotImplementedBimError
from llmbim_core.model import ProjectModel


def export_ifc(model: ProjectModel, path: str | Path) -> None:
    """Write IFC4 file from project model."""
    raise NotImplementedBimError(
        "export_ifc not implemented — claim WP-IFC",
        package="ifc",
    )
