"""In-memory semantic project model (JSON-serializable)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from llmbim_core.errors import NotFoundError, ValidationError
from llmbim_core.ids import new_id
from llmbim_core.migrate import CURRENT as SCHEMA_VERSION


class Level(BaseModel):
    id: str
    name: str
    elevation_mm: float


class Element(BaseModel):
    id: str
    category: str  # open vocabulary: wall, slab, door, custom, ...
    name: str = ""
    level_id: str | None = None
    host_id: str | None = None
    type_id: str | None = None
    parent_id: str | None = None  # assembly hierarchy
    params: dict[str, Any] = Field(default_factory=dict)


class Assembly(BaseModel):
    """Named group of element ids (design options, packages, zones)."""

    id: str
    name: str
    element_ids: list[str] = Field(default_factory=list)
    kind: str = "group"  # group | option | zone | system
    params: dict[str, Any] = Field(default_factory=dict)


class ProjectModel(BaseModel):
    """Serializable project document."""

    schema_version: int = SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("prj"))
    name: str = "Untitled"
    units: str = "mm"  # storage unit (always mm); display may differ
    levels: list[Level] = Field(default_factory=list)
    grids: list[Element] = Field(default_factory=list)
    elements: list[Element] = Field(default_factory=list)
    assemblies: list[Assembly] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    # --- levels -----------------------------------------------------------------

    def add_level(self, name: str, elevation_mm: float) -> Level:
        if any(lv.name == name for lv in self.levels):
            raise ValidationError("Level name already exists", name=name)
        level = Level(id=new_id("lvl"), name=name, elevation_mm=float(elevation_mm))
        self.levels.append(level)
        self.levels.sort(key=lambda lv: lv.elevation_mm)
        return level

    def get_level(self, name_or_id: str) -> Level:
        for lv in self.levels:
            if lv.id == name_or_id or lv.name == name_or_id:
                return lv
        raise NotFoundError("Level not found", ref=name_or_id)

    # --- elements ---------------------------------------------------------------

    def add_element(self, element: Element) -> Element:
        if any(el.id == element.id for el in self.elements):
            raise ValidationError("Element id already exists", id=element.id)
        self.elements.append(element)
        return element

    def get_element(self, element_id: str) -> Element:
        for el in self.elements:
            if el.id == element_id:
                return el
        raise NotFoundError("Element not found", id=element_id)

    def query(
        self,
        *,
        category: str | None = None,
        level: str | None = None,
        host_id: str | None = None,
    ) -> list[Element]:
        level_id: str | None = None
        if level is not None:
            level_id = self.get_level(level).id
        out: list[Element] = []
        for el in self.elements:
            if category is not None and el.category != category:
                continue
            if level_id is not None and el.level_id != level_id:
                continue
            if host_id is not None and el.host_id != host_id:
                continue
            out.append(el)
        return out

    def filter_by_phase(
        self,
        phases: str | list[str] | tuple[str, ...] | None,
        *,
        default_phase: str = "new",
    ) -> ProjectModel:
        """Return a shallow copy with only elements whose phase is in ``phases``.

        Grids and levels are kept. Elements without a phase param default to
        ``default_phase`` (usually ``new``). Pass ``None`` or empty → full copy.
        Hosted doors/windows kept only if both they and their host pass the filter
        (orphan hosts are dropped).
        """
        if not phases:
            return self.model_copy(deep=True)
        if isinstance(phases, str):
            allowed = {p.strip().lower() for p in phases.split(",") if p.strip()}
        else:
            allowed = {str(p).strip().lower() for p in phases if str(p).strip()}
        if not allowed:
            return self.model_copy(deep=True)

        def _phase(el: Element) -> str:
            return str(el.params.get("phase") or default_phase).lower()

        keep_ids = {el.id for el in self.elements if _phase(el) in allowed}
        # drop hosted openings whose host was filtered out
        filtered_els: list[Element] = []
        for el in self.elements:
            if el.id not in keep_ids:
                continue
            if el.host_id and el.host_id not in keep_ids:
                continue
            filtered_els.append(el.model_copy(deep=True))
        # assemblies: keep ids that remain
        filtered_asm: list[Assembly] = []
        for a in self.assemblies:
            ids = [i for i in a.element_ids if i in keep_ids]
            if ids:
                na = a.model_copy(deep=True)
                na.element_ids = ids
                filtered_asm.append(na)
        return ProjectModel(
            schema_version=self.schema_version,
            id=self.id,
            name=self.name,
            units=self.units,
            levels=[lv.model_copy(deep=True) for lv in self.levels],
            grids=[g.model_copy(deep=True) for g in self.grids],
            elements=filtered_els,
            assemblies=filtered_asm,
            meta={
                **(self.meta or {}),
                "phase_filter": sorted(allowed),
                "phase_filter_source_elements": len(self.elements),
            },
        )

    # --- persistence ------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectModel:
        from llmbim_core.migrate import migrate

        data = migrate(dict(data))
        return cls.model_validate(data)

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.schema_version = SCHEMA_VERSION
        p.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def open(cls, path: str | Path) -> ProjectModel:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def get_assembly(self, name_or_id: str) -> Assembly:
        for a in self.assemblies:
            if a.id == name_or_id or a.name == name_or_id:
                return a
        raise NotFoundError("Assembly not found", ref=name_or_id)

    def stats(self) -> dict[str, int]:
        counts: dict[str, int] = {"levels": len(self.levels), "elements": len(self.elements)}
        for el in self.elements:
            counts[el.category] = counts.get(el.category, 0) + 1
        return counts
