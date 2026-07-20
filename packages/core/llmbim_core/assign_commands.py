"""Commands for material/part assignment (undoable via journal, simple apply)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from llmbim_core.assignment import assign_material, assign_part
from llmbim_core.commands import Command
from llmbim_core.errors import ValidationError
from llmbim_core.model import ProjectModel


@dataclass
class AssignMaterial(Command):
    element_id: str
    material_id: str
    role: str = "primary"
    op: str = "assign_material"
    _prev: dict[str, Any] = field(default_factory=dict)

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        el = model.get_element(self.element_id)
        self._prev = {
            "material_id": el.params.get("material_id"),
            "material_assignments": list(el.params.get("material_assignments") or []),
            "material_role": el.params.get("material_role"),
        }
        return assign_material(model, self.element_id, self.material_id, role=self.role)

    def invert(self) -> Command:
        return _RestoreParams(element_id=self.element_id, params=self._prev, op_name="assign_material")


@dataclass
class AssignPart(Command):
    element_id: str
    part_id: str
    qty: float | None = None  # None = preserve existing qty/length
    apply_geometry: bool = False
    op: str = "assign_part"
    _prev: dict[str, Any] = field(default_factory=dict)

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        el = model.get_element(self.element_id)
        self._prev = {
            "part_id": el.params.get("part_id"),
            "part_qty": el.params.get("part_qty"),
            "type_id": el.type_id,
            "material_id": el.params.get("material_id"),
            "bom": el.params.get("bom"),
            "size_mm": el.params.get("size_mm"),
            "shape": el.params.get("shape"),
            "polygon_mm": el.params.get("polygon_mm"),
        }
        return assign_part(
            model,
            self.element_id,
            self.part_id,
            qty=self.qty,
            apply_geometry=self.apply_geometry,
        )

    def invert(self) -> Command:
        return _RestoreParams(element_id=self.element_id, params=self._prev, op_name="assign_part")


@dataclass
class _RestoreParams(Command):
    element_id: str
    params: dict[str, Any]
    op_name: str = "restore_params"
    op: str = "restore_params"

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        el = model.get_element(self.element_id)
        for k, v in self.params.items():
            if k == "type_id":
                el.type_id = v
            elif v is None:
                el.params.pop(k, None)
            else:
                el.params[k] = v
        return {"element_id": self.element_id, "restored": list(self.params)}

    def invert(self) -> Command:
        raise ValidationError("Cannot invert restore")
