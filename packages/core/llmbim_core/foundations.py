"""Foundation commands — strip/pad footings, stem walls, slabs-on-grade (WP-SCHAD-S3).

Geometry is derived ONCE here and stored in element params so downstream
consumers (glTF mesh, sections/elevations, IFC, schedules) never re-derive
it. All coordinates are millimetres; Z values (``top_of_footing_mm``,
``top_mm``, ``top_of_slab_mm``) are relative to the element's *level*
elevation, so foundation solids typically sit BELOW the level-0 datum.

Element categories written by this module::

    footing     kind strip | pad     (mark, rebar, path/center + section)
    stem_wall                        (path, height, thickness, rebar)
    slab        kind slab_on_grade   (polygon, thickness, reinforcement, mark)

Honesty: ``rebar`` / ``reinforcement`` callouts are CARRIED DATA from a
design basis (design development) — they are labels on the model, not
engineering calculations performed here.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from llmbim_geometry.primitives import polygon_area_mm2

from llmbim_core.commands import Command, DeleteElement
from llmbim_core.errors import ValidationError
from llmbim_core.ids import new_id
from llmbim_core.model import Element, ProjectModel

REBAR_HONESTY = (
    "Rebar/reinforcement callouts are carried design-basis data "
    "(design development), not engineering calculations"
)


# --- shared helpers (public: reused by drawings/IFC renderers) ----------------


def path_length_mm(path_mm: Sequence[Sequence[float]]) -> float:
    """Total polyline length of a foundation path ``[[x,y],...]``."""
    total = 0.0
    for i in range(len(path_mm) - 1):
        x0, y0 = float(path_mm[i][0]), float(path_mm[i][1])
        x1, y1 = float(path_mm[i + 1][0]), float(path_mm[i + 1][1])
        total += math.hypot(x1 - x0, y1 - y0)
    return total


def strip_segment_rects(
    path_mm: Sequence[Sequence[float]], width_mm: float
) -> list[list[tuple[float, float]]]:
    """Plan rectangles (one per path segment) of a strip element of ``width_mm``.

    Each rectangle is the segment centerline offset ± width/2 perpendicular —
    the same footprint the glTF mesh extrudes. Degenerate segments are skipped.
    """
    rects: list[list[tuple[float, float]]] = []
    half = float(width_mm) / 2.0
    for i in range(len(path_mm) - 1):
        x0, y0 = float(path_mm[i][0]), float(path_mm[i][1])
        x1, y1 = float(path_mm[i + 1][0]), float(path_mm[i + 1][1])
        length = math.hypot(x1 - x0, y1 - y0)
        if length < 1e-6:
            continue
        nx, ny = -(y1 - y0) / length * half, (x1 - x0) / length * half
        rects.append(
            [
                (x0 - nx, y0 - ny),
                (x1 - nx, y1 - ny),
                (x1 + nx, y1 + ny),
                (x0 + nx, y0 + ny),
            ]
        )
    return rects


def rebar_text(spec: Any) -> str:
    """Normalize a rebar spec (dict / str / None) to one schedule string."""
    if spec is None:
        return ""
    if isinstance(spec, dict):
        return "; ".join(f"{k}: {spec[k]}" for k in sorted(spec))
    return str(spec)


def _clean_path(
    path: Sequence[Sequence[float]] | None, what: str
) -> list[list[float]]:
    if not path or len(path) < 2:
        raise ValidationError(f"{what} path needs at least 2 points [[x,y],...]")
    pts = [[float(p[0]), float(p[1])] for p in path]
    if path_length_mm(pts) < 1.0:
        raise ValidationError(f"{what} path is degenerate (zero length)")
    return pts


def _rebar_param(rebar: dict[str, str] | str | None) -> dict[str, str] | str | None:
    if rebar is None:
        return None
    if isinstance(rebar, dict):
        return {str(k): str(v) for k, v in rebar.items()}
    return str(rebar)


# --- commands ----------------------------------------------------------------


@dataclass
class CreateStripFooting(Command):
    """Continuous strip footing along a plan path or under an existing wall.

    ``width_mm`` is the plan width across the path, ``depth_mm`` the vertical
    footing thickness. ``top_of_footing_mm`` is the elevation of the footing
    TOP relative to the level (typically negative — below the datum).
    Exactly one of ``path`` / ``under_wall`` must be given.
    """

    level: str
    width_mm: float
    depth_mm: float
    path: list[tuple[float, float]] | None = None
    under_wall: str | None = None
    top_of_footing_mm: float = 0.0
    rebar: dict[str, str] | str | None = None
    mark: str = ""
    name: str = ""
    op: str = "create_strip_footing"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        lv = model.get_level(self.level)
        if self.width_mm <= 0 or self.depth_mm <= 0:
            raise ValidationError("width_mm and depth_mm must be positive")
        if (self.path is None) == (self.under_wall is None):
            raise ValidationError(
                "Pass exactly one of path=[[x,y],...] or under_wall=<wall element id>"
            )
        if self.under_wall is not None:
            host = model.get_element(self.under_wall)
            if host.category not in {"wall", "stem_wall"}:
                raise ValidationError(
                    "under_wall must reference a wall or stem_wall",
                    host_category=host.category,
                )
            hp = host.params.get("path_mm") or [
                host.params.get("start_mm"),
                host.params.get("end_mm"),
            ]
            pts = _clean_path(hp, "Strip footing (under_wall)")
        else:
            pts = _clean_path(self.path, "Strip footing")
        length = path_length_mm(pts)
        eid = self._element_id or new_id("ftg")
        params: dict[str, Any] = {
            "kind": "strip",
            "path_mm": pts,
            "width_mm": float(self.width_mm),
            "depth_mm": float(self.depth_mm),
            "top_of_footing_mm": float(self.top_of_footing_mm),
            "length_mm": float(length),
            "honesty": REBAR_HONESTY,
        }
        if self.mark:
            params["mark"] = str(self.mark)
        rb = _rebar_param(self.rebar)
        if rb is not None:
            params["rebar"] = rb
        if self.under_wall is not None:
            params["under_wall_id"] = str(self.under_wall)
        el = Element(
            id=eid,
            category="footing",
            name=self.name or (f"Footing-{self.mark}" if self.mark else "Footing-Strip"),
            level_id=lv.id,
            params=params,
        )
        model.add_element(el)
        self._element_id = el.id
        return {
            "element_id": el.id,
            "category": "footing",
            "kind": "strip",
            "mark": self.mark or None,
            "length_mm": length,
            "top_of_footing_mm": float(self.top_of_footing_mm),
        }

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert CreateStripFooting before apply")
        return DeleteElement(element_id=self._element_id)


@dataclass
class CreatePadFooting(Command):
    """Isolated pad footing centered at ``origin`` (plan mm).

    ``w_mm`` × ``d_mm`` is the plan size, ``depth_mm`` the vertical thickness,
    ``top_of_footing_mm`` the top elevation relative to the level.
    """

    level: str
    origin: tuple[float, float]
    w_mm: float
    d_mm: float
    depth_mm: float
    top_of_footing_mm: float = 0.0
    rebar: dict[str, str] | str | None = None
    mark: str = ""
    name: str = ""
    op: str = "create_pad_footing"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        lv = model.get_level(self.level)
        if self.w_mm <= 0 or self.d_mm <= 0 or self.depth_mm <= 0:
            raise ValidationError("w_mm, d_mm and depth_mm must be positive")
        cx, cy = float(self.origin[0]), float(self.origin[1])
        hw, hd = float(self.w_mm) / 2.0, float(self.d_mm) / 2.0
        poly = [
            [cx - hw, cy - hd],
            [cx + hw, cy - hd],
            [cx + hw, cy + hd],
            [cx - hw, cy + hd],
        ]
        eid = self._element_id or new_id("ftg")
        params: dict[str, Any] = {
            "kind": "pad",
            "center_mm": [cx, cy],
            "w_mm": float(self.w_mm),
            "d_mm": float(self.d_mm),
            "depth_mm": float(self.depth_mm),
            "top_of_footing_mm": float(self.top_of_footing_mm),
            "polygon_mm": poly,
            "honesty": REBAR_HONESTY,
        }
        if self.mark:
            params["mark"] = str(self.mark)
        rb = _rebar_param(self.rebar)
        if rb is not None:
            params["rebar"] = rb
        el = Element(
            id=eid,
            category="footing",
            name=self.name or (f"Footing-{self.mark}" if self.mark else "Footing-Pad"),
            level_id=lv.id,
            params=params,
        )
        model.add_element(el)
        self._element_id = el.id
        return {
            "element_id": el.id,
            "category": "footing",
            "kind": "pad",
            "mark": self.mark or None,
            "top_of_footing_mm": float(self.top_of_footing_mm),
        }

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert CreatePadFooting before apply")
        return DeleteElement(element_id=self._element_id)


@dataclass
class CreateStemWall(Command):
    """Concrete stem wall along a plan path.

    The wall TOP sits at ``top_mm`` relative to the level (default 0 — the
    level datum / sill plate line) and extends DOWN ``height_mm`` toward the
    footing below.
    """

    level: str
    path: list[tuple[float, float]]
    height_mm: float
    thickness_mm: float
    top_mm: float = 0.0
    rebar: dict[str, str] | str | None = None
    mark: str = ""
    name: str = ""
    op: str = "create_stem_wall"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        lv = model.get_level(self.level)
        if self.height_mm <= 0 or self.thickness_mm <= 0:
            raise ValidationError("height_mm and thickness_mm must be positive")
        pts = _clean_path(self.path, "Stem wall")
        length = path_length_mm(pts)
        eid = self._element_id or new_id("stm")
        params: dict[str, Any] = {
            "path_mm": pts,
            "height_mm": float(self.height_mm),
            "thickness_mm": float(self.thickness_mm),
            "top_mm": float(self.top_mm),
            "length_mm": float(length),
            "honesty": REBAR_HONESTY,
        }
        if self.mark:
            params["mark"] = str(self.mark)
        rb = _rebar_param(self.rebar)
        if rb is not None:
            params["rebar"] = rb
        el = Element(
            id=eid,
            category="stem_wall",
            name=self.name or (f"Stem-{self.mark}" if self.mark else "Stem-Wall"),
            level_id=lv.id,
            params=params,
        )
        model.add_element(el)
        self._element_id = el.id
        return {
            "element_id": el.id,
            "category": "stem_wall",
            "mark": self.mark or None,
            "length_mm": length,
            "top_mm": float(self.top_mm),
        }

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert CreateStemWall before apply")
        return DeleteElement(element_id=self._element_id)


@dataclass
class CreateSlabOnGrade(Command):
    """Slab-on-grade from a plan polygon (mm).

    ``top_of_slab_mm`` is the slab TOP relative to the level (default 0 —
    finished floor at the level datum); the solid extends ``thickness_mm``
    down from there. ``reinforcement`` (WWM / rebar mat callout) and ``mark``
    are carried once in params for schedules and plans.
    """

    level: str
    polygon: list[tuple[float, float]]
    thickness_mm: float
    top_of_slab_mm: float = 0.0
    reinforcement: dict[str, str] | str | None = None
    mark: str = ""
    name: str = ""
    op: str = "create_slab_on_grade"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        lv = model.get_level(self.level)
        if len(self.polygon) < 3:
            raise ValidationError("Slab-on-grade polygon needs at least 3 points")
        if self.thickness_mm <= 0:
            raise ValidationError("thickness_mm must be positive")
        pts = [(float(p[0]), float(p[1])) for p in self.polygon]
        area = polygon_area_mm2(pts)
        eid = self._element_id or new_id("slb")
        params: dict[str, Any] = {
            "kind": "slab_on_grade",
            "polygon_mm": [[x, y] for x, y in pts],
            "thickness_mm": float(self.thickness_mm),
            "top_of_slab_mm": float(self.top_of_slab_mm),
            "area_mm2": float(area),
            "honesty": REBAR_HONESTY,
        }
        if self.mark:
            params["mark"] = str(self.mark)
        rf = _rebar_param(self.reinforcement)
        if rf is not None:
            params["reinforcement"] = rf
        el = Element(
            id=eid,
            category="slab",
            name=self.name or (f"Slab-{self.mark}" if self.mark else "Slab-On-Grade"),
            level_id=lv.id,
            params=params,
        )
        model.add_element(el)
        self._element_id = el.id
        return {
            "element_id": el.id,
            "category": "slab",
            "kind": "slab_on_grade",
            "mark": self.mark or None,
            "area_mm2": area,
            "top_of_slab_mm": float(self.top_of_slab_mm),
        }

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert CreateSlabOnGrade before apply")
        return DeleteElement(element_id=self._element_id)


# --- schedule ----------------------------------------------------------------


def rebar_schedule(model: ProjectModel) -> list[dict[str, Any]]:
    """Foundation rebar/reinforcement schedule rows (mark-aggregated).

    One row per (mark, type, rebar-spec): qty = element count, plus total
    ``length_m`` (strip footings / stem walls) and ``area_m2`` (pads / slabs).
    Specs are the carried design-basis callouts — see ``REBAR_HONESTY``.
    """
    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for el in model.elements:
        if el.category == "footing":
            kind = str(el.params.get("kind") or "strip")
            typ = "strip_footing" if kind == "strip" else "pad_footing"
            spec = rebar_text(el.params.get("rebar"))
        elif el.category == "stem_wall":
            typ = "stem_wall"
            spec = rebar_text(el.params.get("rebar"))
        elif el.category == "slab" and el.params.get("kind") == "slab_on_grade":
            typ = "slab_on_grade"
            spec = rebar_text(el.params.get("reinforcement"))
        else:
            continue
        mark = str(el.params.get("mark") or "")
        key = (mark, typ, spec)
        row = rows.setdefault(
            key,
            {
                "mark": mark,
                "type": typ,
                "rebar": spec,
                "qty": 0,
                "length_m": 0.0,
                "area_m2": 0.0,
                "element_ids": [],
                "note": REBAR_HONESTY,
            },
        )
        row["qty"] = int(row["qty"]) + 1
        row["element_ids"].append(el.id)
        length_mm = el.params.get("length_mm")
        if length_mm:
            row["length_m"] = round(float(row["length_m"]) + float(length_mm) / 1000.0, 3)
        area_mm2 = el.params.get("area_mm2")
        if area_mm2 is None and el.params.get("kind") == "pad":
            area_mm2 = float(el.params.get("w_mm") or 0) * float(el.params.get("d_mm") or 0)
        if area_mm2:
            row["area_m2"] = round(float(row["area_m2"]) + float(area_mm2) / 1e6, 3)
    return [rows[k] for k in sorted(rows)]
