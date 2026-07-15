"""Public LLM-BIM SDK — the surface agents should import."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmbim_core.commands import (
    AddGrid,
    AddLevel,
    CreateRoom,
    CreateSlab,
    CreateWall,
    DeleteElement,
    PlaceDoor,
    PlaceWindow,
    TransactionLog,
)
from llmbim_core.model import Element, Level, ProjectModel

__version__ = "0.1.0a0"


class Project:
    """Agent-facing project facade.

    All mutations go through the command bus so undo/redo stays consistent.
    """

    def __init__(self, model: ProjectModel, log: TransactionLog | None = None) -> None:
        self._model = model
        self._log = log or TransactionLog()

    @classmethod
    def create(cls, name: str = "Untitled", units: str = "mm") -> Project:
        if units != "mm":
            raise ValueError("MVP only supports units='mm'")
        return cls(ProjectModel(name=name, units=units))

    @classmethod
    def open(cls, path: str | Path) -> Project:
        return cls(ProjectModel.open(path))

    def save(self, path: str | Path) -> None:
        self._model.save(path)

    @property
    def name(self) -> str:
        return self._model.name

    @property
    def model(self) -> ProjectModel:
        """Low-level model (prefer high-level methods in agent code)."""
        return self._model

    def execute(self, command: Any) -> dict[str, Any]:
        """Apply a low-level command (advanced agents / tests)."""
        return self._log.execute(self._model, command)

    def add_level(self, name: str, elevation_mm: float) -> str:
        result = self._log.execute(self._model, AddLevel(name=name, elevation_mm=elevation_mm))
        return str(result["result"]["level_id"])

    def add_grid(self, axis: str, positions_mm: list[float], name: str | None = None) -> str:
        result = self._log.execute(
            self._model,
            AddGrid(axis=axis, positions_mm=positions_mm, name=name or ""),
        )
        return str(result["result"]["element_id"])

    def create_wall(
        self,
        *,
        level: str,
        start: tuple[float, float],
        end: tuple[float, float],
        thickness_mm: float,
        height_mm: float,
        name: str | None = None,
    ) -> str:
        result = self._log.execute(
            self._model,
            CreateWall(
                level=level,
                start=start,
                end=end,
                thickness_mm=thickness_mm,
                height_mm=height_mm,
                name=name or "",
            ),
        )
        return str(result["result"]["element_id"])

    def create_slab(
        self,
        *,
        level: str,
        polygon: list[tuple[float, float]],
        thickness_mm: float,
        name: str | None = None,
    ) -> str:
        result = self._log.execute(
            self._model,
            CreateSlab(
                level=level,
                polygon=polygon,
                thickness_mm=thickness_mm,
                name=name or "",
            ),
        )
        return str(result["result"]["element_id"])

    def place_door(
        self,
        *,
        host: str,
        offset_mm: float,
        width_mm: float,
        height_mm: float,
        name: str | None = None,
    ) -> str:
        result = self._log.execute(
            self._model,
            PlaceDoor(
                host=host,
                offset_mm=offset_mm,
                width_mm=width_mm,
                height_mm=height_mm,
                name=name or "",
            ),
        )
        return str(result["result"]["element_id"])

    def place_window(
        self,
        *,
        host: str,
        offset_mm: float,
        width_mm: float,
        height_mm: float,
        sill_mm: float,
        name: str | None = None,
    ) -> str:
        result = self._log.execute(
            self._model,
            PlaceWindow(
                host=host,
                offset_mm=offset_mm,
                width_mm=width_mm,
                height_mm=height_mm,
                sill_mm=sill_mm,
                name=name or "",
            ),
        )
        return str(result["result"]["element_id"])

    def create_room(
        self,
        *,
        level: str,
        name: str,
        boundary: list[tuple[float, float]],
    ) -> str:
        result = self._log.execute(
            self._model,
            CreateRoom(level=level, name=name, boundary=boundary),
        )
        return str(result["result"]["element_id"])

    def delete_element(self, element_id: str) -> None:
        self._log.execute(self._model, DeleteElement(element_id=element_id))

    def undo(self) -> dict[str, Any]:
        return self._log.undo(self._model)

    def redo(self) -> dict[str, Any]:
        return self._log.redo(self._model)

    def query(self, **filters: str) -> list[Element]:
        return self._model.query(**filters)  # type: ignore[arg-type]

    def stats(self) -> dict[str, int]:
        return self._model.stats()

    def levels(self) -> list[Level]:
        return list(self._model.levels)

    def export_plan(self, level: str, path: str | Path, **opts: Any) -> None:
        from llmbim_drawings import export_plan_svg

        export_plan_svg(self._model, level, path, **opts)

    def export_section(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        path: str | Path,
        **opts: Any,
    ) -> None:
        from llmbim_drawings import export_section_svg

        export_section_svg(self._model, p0, p1, path, **opts)

    def export_elevation(self, direction: str, path: str | Path, **opts: Any) -> None:
        from llmbim_drawings import export_elevation_svg

        export_elevation_svg(self._model, direction, path, **opts)


__all__ = ["Project", "Element", "Level", "ProjectModel", "__version__"]
