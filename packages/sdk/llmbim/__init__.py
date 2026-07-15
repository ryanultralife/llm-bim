"""Public LLM-BIM SDK — the surface agents should import."""

from __future__ import annotations

from pathlib import Path

from llmbim_core.ids import new_id
from llmbim_core.model import Element, Level, ProjectModel
from llmbim_geometry.primitives import wall_length_mm

__version__ = "0.1.0a0"


class Project:
    """Agent-facing project facade.

    Mutations grow with PR-02+ command bus. MVP bootstrap exposes levels +
    simple walls and persistence so parallel work can land against a real API.
    """

    def __init__(self, model: ProjectModel) -> None:
        self._model = model

    @classmethod
    def create(cls, name: str = "Untitled", units: str = "mm") -> Project:
        if units != "mm":
            # Imperial conversion lands later; keep agents on mm for MVP.
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

    def add_level(self, name: str, elevation_mm: float) -> str:
        return self._model.add_level(name, elevation_mm).id

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
        lv = self._model.get_level(level)
        length = wall_length_mm(start, end)
        if thickness_mm <= 0:
            raise ValueError("thickness_mm must be positive")
        if height_mm <= 0:
            raise ValueError("height_mm must be positive")
        el = Element(
            id=new_id("wal"),
            category="wall",
            name=name or "",
            level_id=lv.id,
            params={
                "start_mm": [float(start[0]), float(start[1])],
                "end_mm": [float(end[0]), float(end[1])],
                "thickness_mm": float(thickness_mm),
                "height_mm": float(height_mm),
                "length_mm": float(length),
            },
        )
        self._model.add_element(el)
        return el.id

    def query(self, **filters: str) -> list[Element]:
        return self._model.query(**filters)  # type: ignore[arg-type]

    def stats(self) -> dict[str, int]:
        return self._model.stats()

    def levels(self) -> list[Level]:
        return list(self._model.levels)


__all__ = ["Project", "Element", "Level", "ProjectModel", "__version__"]
