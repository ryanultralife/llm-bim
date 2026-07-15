"""Public LLM-BIM SDK — the surface agents should import."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmbim_core.commands import AddLevel, CreateWall, DeleteElement, TransactionLog
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


__all__ = ["Project", "Element", "Level", "ProjectModel", "__version__"]
