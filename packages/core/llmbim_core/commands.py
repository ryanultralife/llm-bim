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
