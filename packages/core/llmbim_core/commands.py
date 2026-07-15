"""Command bus with undo/redo (PR-02 foundation)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from llmbim_core.errors import ValidationError
from llmbim_core.ids import new_id
from llmbim_core.model import Element, ProjectModel
from llmbim_geometry.primitives import wall_length_mm


class Command(ABC):
    """A single reversible mutation."""

    op: str

    @abstractmethod
    def apply(self, model: ProjectModel) -> dict[str, Any]:
        """Mutate model; return result payload for agents."""

    @abstractmethod
    def invert(self) -> Command:
        """Return a command that undoes this one (after apply)."""


@dataclass
class AddLevel(Command):
    name: str
    elevation_mm: float
    op: str = "add_level"
    _level_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        # Preserve id across redo so agent references stay stable.
        if self._level_id and any(lv.id == self._level_id for lv in model.levels):
            raise ValidationError("Level id already exists", id=self._level_id)
        if self._level_id:
            from llmbim_core.model import Level

            if any(lv.name == self.name for lv in model.levels):
                raise ValidationError("Level name already exists", name=self.name)
            level = Level(id=self._level_id, name=self.name, elevation_mm=float(self.elevation_mm))
            model.levels.append(level)
            model.levels.sort(key=lambda lv: lv.elevation_mm)
        else:
            level = model.add_level(self.name, self.elevation_mm)
            self._level_id = level.id
        return {"level_id": level.id, "name": level.name, "elevation_mm": level.elevation_mm}

    def invert(self) -> Command:
        if not self._level_id:
            raise ValidationError("Cannot invert AddLevel before apply")
        return RemoveLevel(level_id=self._level_id)


@dataclass
class RemoveLevel(Command):
    level_id: str
    op: str = "remove_level"
    _snapshot: dict[str, Any] | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        level = model.get_level(self.level_id)
        # Refuse if elements reference this level
        using = [el.id for el in model.elements if el.level_id == level.id]
        if using:
            raise ValidationError(
                "Cannot remove level while elements reference it",
                level_id=level.id,
                element_ids=using,
            )
        self._snapshot = level.model_dump()
        model.levels = [lv for lv in model.levels if lv.id != level.id]
        return {"removed_level_id": level.id}

    def invert(self) -> Command:
        if not self._snapshot:
            raise ValidationError("Cannot invert RemoveLevel before apply")
        return RestoreLevel(snapshot=self._snapshot)


@dataclass
class RestoreLevel(Command):
    snapshot: dict[str, Any]
    op: str = "restore_level"

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        from llmbim_core.model import Level

        level = Level.model_validate(self.snapshot)
        if any(lv.id == level.id for lv in model.levels):
            raise ValidationError("Level id already exists", id=level.id)
        model.levels.append(level)
        model.levels.sort(key=lambda lv: lv.elevation_mm)
        return {"level_id": level.id}

    def invert(self) -> Command:
        return RemoveLevel(level_id=self.snapshot["id"])


@dataclass
class CreateWall(Command):
    level: str
    start: tuple[float, float]
    end: tuple[float, float]
    thickness_mm: float
    height_mm: float
    name: str = ""
    op: str = "create_wall"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        lv = model.get_level(self.level)
        length = wall_length_mm(self.start, self.end)
        if self.thickness_mm <= 0 or self.height_mm <= 0:
            raise ValidationError("thickness_mm and height_mm must be positive")
        eid = self._element_id or new_id("wal")
        el = Element(
            id=eid,
            category="wall",
            name=self.name,
            level_id=lv.id,
            params={
                "start_mm": [float(self.start[0]), float(self.start[1])],
                "end_mm": [float(self.end[0]), float(self.end[1])],
                "thickness_mm": float(self.thickness_mm),
                "height_mm": float(self.height_mm),
                "length_mm": float(length),
            },
        )
        model.add_element(el)
        self._element_id = el.id
        return {"element_id": el.id, "category": "wall", "length_mm": length}

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert CreateWall before apply")
        return DeleteElement(element_id=self._element_id)


@dataclass
class CreateSlab(Command):
    level: str
    polygon: list[tuple[float, float]]
    thickness_mm: float
    name: str = ""
    op: str = "create_slab"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        from llmbim_geometry.primitives import polygon_area_mm2

        lv = model.get_level(self.level)
        if len(self.polygon) < 3:
            raise ValidationError("Slab polygon needs at least 3 points")
        if self.thickness_mm <= 0:
            raise ValidationError("thickness_mm must be positive")
        area = polygon_area_mm2(self.polygon)
        eid = self._element_id or new_id("slb")
        el = Element(
            id=eid,
            category="slab",
            name=self.name,
            level_id=lv.id,
            params={
                "polygon_mm": [[float(x), float(y)] for x, y in self.polygon],
                "thickness_mm": float(self.thickness_mm),
                "area_mm2": float(area),
            },
        )
        model.add_element(el)
        self._element_id = el.id
        return {"element_id": el.id, "category": "slab", "area_mm2": area}

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert CreateSlab before apply")
        return DeleteElement(element_id=self._element_id)


@dataclass
class PlaceDoor(Command):
    host: str
    offset_mm: float
    width_mm: float
    height_mm: float
    name: str = ""
    op: str = "place_door"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        host = model.get_element(self.host)
        if host.category != "wall":
            raise ValidationError("Door host must be a wall", host_category=host.category)
        wall_len = float(host.params.get("length_mm", 0))
        if self.width_mm <= 0 or self.height_mm <= 0:
            raise ValidationError("Door width/height must be positive")
        if self.offset_mm < 0 or self.offset_mm + self.width_mm > wall_len + 1e-6:
            raise ValidationError(
                "Door does not fit on host wall",
                offset_mm=self.offset_mm,
                width_mm=self.width_mm,
                wall_length_mm=wall_len,
            )
        eid = self._element_id or new_id("dor")
        el = Element(
            id=eid,
            category="door",
            name=self.name,
            level_id=host.level_id,
            host_id=host.id,
            params={
                "offset_mm": float(self.offset_mm),
                "width_mm": float(self.width_mm),
                "height_mm": float(self.height_mm),
            },
        )
        model.add_element(el)
        self._element_id = el.id
        return {"element_id": el.id, "category": "door", "host_id": host.id}

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert PlaceDoor before apply")
        return DeleteElement(element_id=self._element_id)


@dataclass
class PlaceWindow(Command):
    host: str
    offset_mm: float
    width_mm: float
    height_mm: float
    sill_mm: float
    name: str = ""
    op: str = "place_window"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        host = model.get_element(self.host)
        if host.category != "wall":
            raise ValidationError("Window host must be a wall", host_category=host.category)
        wall_len = float(host.params.get("length_mm", 0))
        wall_h = float(host.params.get("height_mm", 0))
        if self.width_mm <= 0 or self.height_mm <= 0:
            raise ValidationError("Window width/height must be positive")
        if self.sill_mm < 0:
            raise ValidationError("sill_mm must be non-negative")
        if self.sill_mm + self.height_mm > wall_h + 1e-6:
            raise ValidationError(
                "Window exceeds wall height",
                sill_mm=self.sill_mm,
                height_mm=self.height_mm,
                wall_height_mm=wall_h,
            )
        if self.offset_mm < 0 or self.offset_mm + self.width_mm > wall_len + 1e-6:
            raise ValidationError(
                "Window does not fit on host wall",
                offset_mm=self.offset_mm,
                width_mm=self.width_mm,
                wall_length_mm=wall_len,
            )
        eid = self._element_id or new_id("wnd")
        el = Element(
            id=eid,
            category="window",
            name=self.name,
            level_id=host.level_id,
            host_id=host.id,
            params={
                "offset_mm": float(self.offset_mm),
                "width_mm": float(self.width_mm),
                "height_mm": float(self.height_mm),
                "sill_mm": float(self.sill_mm),
            },
        )
        model.add_element(el)
        self._element_id = el.id
        return {"element_id": el.id, "category": "window", "host_id": host.id}

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert PlaceWindow before apply")
        return DeleteElement(element_id=self._element_id)


@dataclass
class CreateRoom(Command):
    level: str
    name: str
    boundary: list[tuple[float, float]]
    op: str = "create_room"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        from llmbim_geometry.primitives import polygon_area_mm2

        lv = model.get_level(self.level)
        if len(self.boundary) < 3:
            raise ValidationError("Room boundary needs at least 3 points")
        area = polygon_area_mm2(self.boundary)
        eid = self._element_id or new_id("rom")
        el = Element(
            id=eid,
            category="room",
            name=self.name,
            level_id=lv.id,
            params={
                "boundary_mm": [[float(x), float(y)] for x, y in self.boundary],
                "area_mm2": float(area),
            },
        )
        model.add_element(el)
        self._element_id = el.id
        return {"element_id": el.id, "category": "room", "area_mm2": area}

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert CreateRoom before apply")
        return DeleteElement(element_id=self._element_id)


@dataclass
class AddGrid(Command):
    """Orthogonal grid: axis 'U' (lines of constant X) or 'V' (constant Y)."""

    axis: str
    positions_mm: list[float]
    name: str = ""
    op: str = "add_grid"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        axis = self.axis.upper()
        if axis not in {"U", "V"}:
            raise ValidationError("Grid axis must be 'U' or 'V'", axis=self.axis)
        if len(self.positions_mm) < 2:
            raise ValidationError("Grid needs at least 2 positions")
        eid = self._element_id or new_id("grd")
        el = Element(
            id=eid,
            category="grid",
            name=self.name or f"Grid-{axis}",
            params={
                "axis": axis,
                "positions_mm": [float(p) for p in self.positions_mm],
            },
        )
        model.grids.append(el)
        self._element_id = el.id
        return {"element_id": el.id, "axis": axis}

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert AddGrid before apply")
        return RemoveGrid(element_id=self._element_id)


@dataclass
class RemoveGrid(Command):
    element_id: str
    op: str = "remove_grid"
    _snapshot: dict[str, Any] | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        for i, g in enumerate(model.grids):
            if g.id == self.element_id:
                self._snapshot = g.model_dump()
                model.grids.pop(i)
                return {"deleted_id": self.element_id}
        raise ValidationError("Grid not found", id=self.element_id)

    def invert(self) -> Command:
        if not self._snapshot:
            raise ValidationError("Cannot invert RemoveGrid before apply")
        return RestoreGrid(snapshot=self._snapshot)


@dataclass
class RestoreGrid(Command):
    snapshot: dict[str, Any]
    op: str = "restore_grid"

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        el = Element.model_validate(self.snapshot)
        model.grids.append(el)
        return {"element_id": el.id}

    def invert(self) -> Command:
        return RemoveGrid(element_id=self.snapshot["id"])


@dataclass
class DeleteElement(Command):
    element_id: str
    op: str = "delete_element"
    _snapshot: dict[str, Any] | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        el = model.get_element(self.element_id)
        hosted = [h.id for h in model.elements if h.host_id == el.id]
        if hosted:
            raise ValidationError(
                "Cannot delete element with hosted children; delete children first",
                element_id=el.id,
                hosted_ids=hosted,
            )
        self._snapshot = el.model_dump()
        model.elements = [e for e in model.elements if e.id != el.id]
        return {"deleted_id": el.id, "category": el.category}

    def invert(self) -> Command:
        if not self._snapshot:
            raise ValidationError("Cannot invert DeleteElement before apply")
        return RestoreElement(snapshot=self._snapshot)


@dataclass
class RestoreElement(Command):
    snapshot: dict[str, Any]
    op: str = "restore_element"

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        el = Element.model_validate(self.snapshot)
        model.add_element(el)
        return {"element_id": el.id}

    def invert(self) -> Command:
        return DeleteElement(element_id=self.snapshot["id"])


@dataclass
class TransactionLog:
    """Undo/redo stacks of applied commands."""

    undo_stack: list[Command] = field(default_factory=list)
    redo_stack: list[Command] = field(default_factory=list)

    def execute(self, model: ProjectModel, command: Command) -> dict[str, Any]:
        result = command.apply(model)
        self.undo_stack.append(command)
        self.redo_stack.clear()
        return {"ok": True, "op": command.op, "result": result}

    def undo(self, model: ProjectModel) -> dict[str, Any]:
        if not self.undo_stack:
            raise ValidationError("Nothing to undo")
        cmd = self.undo_stack.pop()
        inverse = cmd.invert()
        result = inverse.apply(model)
        self.redo_stack.append(cmd)
        return {"ok": True, "op": "undo", "undid": cmd.op, "result": result}

    def redo(self, model: ProjectModel) -> dict[str, Any]:
        if not self.redo_stack:
            raise ValidationError("Nothing to redo")
        cmd = self.redo_stack.pop()
        result = cmd.apply(model)
        self.undo_stack.append(cmd)
        return {"ok": True, "op": "redo", "redid": cmd.op, "result": result}
