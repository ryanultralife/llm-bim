"""Public LLM-BIM SDK — the surface agents should import."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmbim_core.commands import (
    AddGrid,
    AddLevel,
    CreateEquipmentBox,
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

    def create_equipment_box(
        self,
        *,
        level: str,
        origin: tuple[float, float],
        size: tuple[float, float, float],
        name: str | None = None,
        kind: str = "equipment",
        centered: bool = False,
        z0_mm: float = 0.0,
        shape: str = "box",
    ) -> str:
        """Place equipment envelope: shape ``box`` or ``cylinder`` (along +X)."""
        result = self._log.execute(
            self._model,
            CreateEquipmentBox(
                level=level,
                origin=origin,
                size=size,
                name=name or "",
                kind=kind,
                centered=centered,
                z0_mm=z0_mm,
                shape=shape,
            ),
        )
        return str(result["result"]["element_id"])

    def create_rect_shell(
        self,
        *,
        level: str,
        x: float,
        y: float,
        w: float,
        d: float,
        height_mm: float,
        thickness_mm: float = 300,
        name_prefix: str = "W",
    ) -> list[str]:
        """Four walls forming a rectangular room/building footprint (mm)."""
        corners = [
            ((x, y), (x + w, y), f"{name_prefix}-S"),
            ((x + w, y), (x + w, y + d), f"{name_prefix}-E"),
            ((x + w, y + d), (x, y + d), f"{name_prefix}-N"),
            ((x, y + d), (x, y), f"{name_prefix}-W"),
        ]
        ids: list[str] = []
        for start, end, nm in corners:
            ids.append(
                self.create_wall(
                    level=level,
                    start=start,
                    end=end,
                    thickness_mm=thickness_mm,
                    height_mm=height_mm,
                    name=nm,
                )
            )
        return ids

    def delete_element(self, element_id: str, *, cascade: bool = True) -> None:
        self._log.execute(self._model, DeleteElement(element_id=element_id, cascade=cascade))

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

    def export_gltf(self, path: str | Path) -> None:
        from llmbim_geometry.mesh import export_gltf_walls

        export_gltf_walls(self._model, path)

    def validate(self) -> list[dict[str, Any]]:
        from llmbim_core.validate import validate_model

        return [i.to_dict() for i in validate_model(self._model)]

    def export_ifc(self, path: str | Path) -> None:
        from llmbim_ifc import export_ifc

        export_ifc(self._model, path)

    def export_step(self, path: str | Path, *, include_walls: bool = True) -> None:
        from llmbim_geometry.step_export import export_step

        export_step(self._model, path, include_walls=include_walls)

    def export_construction_set(
        self, out_dir: str | Path, *, plan_level: str | None = None, plan_scale: float = 0.02
    ) -> dict[str, Any]:
        from llmbim_drawings.construction import export_construction_set

        return export_construction_set(
            self._model, out_dir, plan_level=plan_level, plan_scale=plan_scale
        )

    def export_part_pack(self, out_dir: str | Path, *, scale: float = 0.4) -> dict[str, Any]:
        from llmbim_drawings.parts import export_part_pack

        return export_part_pack(self._model, out_dir, scale=scale)

    def export_deliverables(
        self,
        out_dir: str | Path,
        *,
        mode: str = "auto",
        plan_level: str | None = None,
        plan_scale: float | None = None,
    ) -> dict[str, Any]:
        """Full pack: JSON + IFC + glTF + STEP + construction and/or part sheets."""
        from llmbim_drawings.deliverables import export_deliverables

        return export_deliverables(
            self._model,
            out_dir,
            mode=mode,
            plan_level=plan_level,
            plan_scale=plan_scale,
        )


__all__ = ["Project", "Element", "Level", "ProjectModel", "__version__"]
