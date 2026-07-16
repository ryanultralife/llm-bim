"""Text notes and design annotations stored as elements."""

from __future__ import annotations

from typing import Any

from llmbim_core.commands import Command, DeleteElement
from llmbim_core.errors import ValidationError
from llmbim_core.ids import new_id
from llmbim_core.model import Element, ProjectModel
from dataclasses import dataclass


@dataclass
class CreateNote(Command):
    level: str
    text: str
    position: tuple[float, float]
    name: str = ""
    op: str = "create_note"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        lv = model.get_level(self.level)
        if not self.text.strip():
            raise ValidationError("Note text required")
        eid = self._element_id or new_id("nte")
        el = Element(
            id=eid,
            category="note",
            name=self.name or "Note",
            level_id=lv.id,
            params={
                "text": self.text,
                "position_mm": [float(self.position[0]), float(self.position[1])],
            },
        )
        model.add_element(el)
        self._element_id = el.id
        return {"element_id": el.id}

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert CreateNote before apply")
        return DeleteElement(element_id=self._element_id)


@dataclass
class SetElementPhase(Command):
    element_id: str
    phase: str  # new | existing | demo | temp
    op: str = "set_phase"
    _old: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        el = model.get_element(self.element_id)
        self._old = str(el.params.get("phase", "new"))
        el.params["phase"] = self.phase
        return {"element_id": el.id, "phase": self.phase}

    def invert(self) -> Command:
        return SetElementPhase(element_id=self.element_id, phase=self._old or "new")


@dataclass
class SetElementType(Command):
    element_id: str
    type_id: str
    op: str = "set_type"
    _old: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        el = model.get_element(self.element_id)
        self._old = el.type_id
        el.type_id = self.type_id
        # auto-sync thickness from wall type if applicable
        if el.category == "wall":
            from llmbim_core.types_catalog import DEFAULT_WALL_TYPES

            wt = DEFAULT_WALL_TYPES.get(self.type_id)
            if wt and wt.total_thickness_mm > 0:
                el.params["thickness_mm"] = wt.total_thickness_mm
            if wt and wt.layers:
                el.params["wall_layers"] = [L.model_dump() for L in wt.layers]
                if wt.fire_rating and not el.params.get("fire_rating"):
                    el.params["fire_rating"] = wt.fire_rating
        return {"element_id": el.id, "type_id": self.type_id}

    def invert(self) -> Command:
        return SetElementType(element_id=self.element_id, type_id=self._old or "")
