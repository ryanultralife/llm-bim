"""Parametric building templates — designers start here, agents fill details."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from llmbim import Project

TemplateFn = Callable[..., str]


def _office_bay(p: Project, *, origin: tuple[float, float] = (0, 0), w: float = 12000, d: float = 9000) -> str:
    ox, oy = origin
    p.add_level("L1", 0)
    p.add_level("L2", 3500)
    p.create_rect_shell(
        level="L1", x=ox, y=oy, w=w, d=d, height_mm=3500, thickness_mm=200, name_prefix="OFF"
    )
    p.create_slab(
        level="L1",
        polygon=[(ox, oy), (ox + w, oy), (ox + w, oy + d), (ox, oy + d)],
        thickness_mm=200,
        name="Floor",
    )
    p.create_room(
        level="L1",
        name="Open office",
        boundary=[(ox, oy), (ox + w, oy), (ox + w, oy + d), (ox, oy + d)],
    )
    walls = p.query(category="wall")
    south = next((w for w in walls if w.name == "OFF-S"), None)
    if south:
        p.place_door(host=south.id, offset_mm=w / 2 - 450, width_mm=900, height_mm=2100, name="Entry")
        p.place_window(host=south.id, offset_mm=2000, width_mm=1500, height_mm=1200, sill_mm=900)
    for el in walls:
        p.set_type(el.id, "W-EXT-CMU" if "OFF" in (el.name or "") else "W-INT-GYP")
    return p.model.id


def _warehouse(p: Project, *, origin: tuple[float, float] = (0, 0), w: float = 40000, d: float = 25000) -> str:
    ox, oy = origin
    p.add_level("L0", 0)
    p.create_rect_shell(
        level="L0", x=ox, y=oy, w=w, d=d, height_mm=9000, thickness_mm=300, name_prefix="WH"
    )
    p.create_slab(
        level="L0",
        polygon=[(ox, oy), (ox + w, oy), (ox + w, oy + d), (ox, oy + d)],
        thickness_mm=250,
        name="SOG",
    )
    p.create_room(level="L0", name="Warehouse hall", boundary=[(ox, oy), (ox + w, oy), (ox + w, oy + d), (ox, oy + d)])
    p.add_grid("U", [ox + i * 10000 for i in range(int(w // 10000) + 1)])
    p.add_grid("V", [oy + i * 10000 for i in range(int(d // 10000) + 1)])
    for el in p.query(category="wall"):
        p.set_type(el.id, "W-EXT-CMU")
    return p.model.id


def _hot_cell_bay(p: Project, *, origin: tuple[float, float] = (0, 0)) -> str:
    """Single 3×3 m hot-cell bay with vessel envelope — nuclear facility module."""
    ox, oy = origin
    w, d, h = 3000.0, 3000.0, 9000.0
    p.add_level("L0", 0)
    p.create_rect_shell(
        level="L0", x=ox, y=oy, w=w, d=d, height_mm=h, thickness_mm=600, name_prefix="CELL"
    )
    p.create_slab(
        level="L0",
        polygon=[(ox, oy), (ox + w, oy), (ox + w, oy + d), (ox, oy + d)],
        thickness_mm=1000,
        name="Cell floor",
    )
    p.create_room(level="L0", name="Hot cell", boundary=[(ox, oy), (ox + w, oy), (ox + w, oy + d), (ox, oy + d)])
    p.create_equipment_box(
        level="L0",
        origin=(ox + w / 2, oy + d / 2),
        size=(1200, 610, 610),
        name="Size-B vessel",
        kind="separator_vessel_size_b",
        shape="cylinder",
        centered=True,
        z0_mm=1200 - 305,
    )
    for el in p.query(category="wall"):
        p.set_type(el.id, "W-SHIELD-CONC")
    return p.model.id


def _lab_bench(p: Project) -> str:
    """Empty project ready for Proto10-class equipment."""
    p.add_level("Bench", 0)
    p.create_equipment_box(
        level="Bench",
        origin=(0, 0),
        size=(800, 800, 200),
        name="Pedestal",
        kind="pedestal",
        centered=True,
    )
    p.create_note(level="Bench", text="Place separator assembly on pedestal", position=(0, 600))
    return p.model.id


TEMPLATES: dict[str, dict[str, Any]] = {
    "office_bay": {
        "title": "Office bay 12×9 m",
        "domain": "commercial",
        "fn": _office_bay,
    },
    "warehouse": {
        "title": "Warehouse 40×25 m",
        "domain": "industrial",
        "fn": _warehouse,
    },
    "hot_cell_bay": {
        "title": "Hot cell 3×3 m with vessel",
        "domain": "nuclear_facility",
        "fn": _hot_cell_bay,
    },
    "lab_bench": {
        "title": "Lab bench for equipment",
        "domain": "lab",
        "fn": _lab_bench,
    },
}


def list_templates() -> list[dict[str, str]]:
    return [
        {"id": k, "title": v["title"], "domain": v["domain"]}
        for k, v in TEMPLATES.items()
    ]


def apply_template(name: str, project: Project | None = None, **kwargs: Any) -> Project:
    if name not in TEMPLATES:
        raise KeyError(f"Unknown template {name}. Available: {list(TEMPLATES)}")
    p = project or Project.create(TEMPLATES[name]["title"])
    TEMPLATES[name]["fn"](p, **kwargs)
    return p
