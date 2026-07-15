"""Building product types — wall assemblies, door types, materials.

Builders use these for quantities and specs; designers assign type_id on elements.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MaterialLayer(BaseModel):
    material: str
    thickness_mm: float
    function: str = "structure"  # structure | insulation | finish | membrane
    density_kg_m3: float = 0.0
    unit_cost_per_m3: float = 0.0  # optional budget estimate


class WallType(BaseModel):
    id: str
    name: str
    layers: list[MaterialLayer] = Field(default_factory=list)
    fire_rating: str = ""
    description: str = ""

    @property
    def total_thickness_mm(self) -> float:
        return sum(L.thickness_mm for L in self.layers)


class DoorType(BaseModel):
    id: str
    name: str
    width_mm: float = 900
    height_mm: float = 2100
    material: str = "hollow_metal"
    fire_rating: str = ""
    unit_cost: float = 0.0


class WindowType(BaseModel):
    id: str
    name: str
    width_mm: float = 1200
    height_mm: float = 1200
    u_value: float | None = None
    unit_cost: float = 0.0


# Built-in catalog for agents
DEFAULT_WALL_TYPES: dict[str, WallType] = {
    "W-EXT-CMU": WallType(
        id="W-EXT-CMU",
        name="Exterior CMU + insulation",
        layers=[
            MaterialLayer(material="CMU", thickness_mm=200, function="structure", density_kg_m3=1800, unit_cost_per_m3=250),
            MaterialLayer(material="rigid_insulation", thickness_mm=50, function="insulation", density_kg_m3=30, unit_cost_per_m3=400),
            MaterialLayer(material="gypsum", thickness_mm=16, function="finish", density_kg_m3=800, unit_cost_per_m3=120),
        ],
        fire_rating="2-hr",
        description="Typical industrial exterior",
    ),
    "W-INT-GYP": WallType(
        id="W-INT-GYP",
        name="Interior stud + gyp",
        layers=[
            MaterialLayer(material="metal_stud", thickness_mm=92, function="structure", density_kg_m3=100, unit_cost_per_m3=80),
            MaterialLayer(material="batt_insulation", thickness_mm=90, function="insulation", density_kg_m3=20, unit_cost_per_m3=60),
            MaterialLayer(material="gypsum", thickness_mm=16, function="finish", density_kg_m3=800, unit_cost_per_m3=120),
        ],
        fire_rating="1-hr",
    ),
    "W-SHIELD-CONC": WallType(
        id="W-SHIELD-CONC",
        name="Bioshield concrete",
        layers=[
            MaterialLayer(material="concrete_shield", thickness_mm=600, function="structure", density_kg_m3=3500, unit_cost_per_m3=550),
            MaterialLayer(material="ss316L", thickness_mm=6, function="finish", density_kg_m3=8000, unit_cost_per_m3=12000),
        ],
        fire_rating="4-hr",
        description="Hot-cell / tunnel shielding wall",
    ),
    "W-GENERIC-200": WallType(
        id="W-GENERIC-200",
        name="Generic 200 mm wall",
        layers=[MaterialLayer(material="generic", thickness_mm=200, function="structure", density_kg_m3=1000, unit_cost_per_m3=150)],
    ),
}

DEFAULT_DOOR_TYPES: dict[str, DoorType] = {
    "D-HM-36": DoorType(id="D-HM-36", name="HM 3'-0\" x 7'-0\"", width_mm=900, height_mm=2100, unit_cost=1800),
    "D-HM-72": DoorType(id="D-HM-72", name="HM pair 6'-0\"", width_mm=1800, height_mm=2100, unit_cost=3200),
    "D-SHIELD-PLUG": DoorType(id="D-SHIELD-PLUG", name="Shield plug door", width_mm=1200, height_mm=2000, material="steel_plug", unit_cost=45000),
}

DEFAULT_WINDOW_TYPES: dict[str, WindowType] = {
    "WIN-VIEW-24x24": WindowType(id="WIN-VIEW-24x24", name="View window", width_mm=600, height_mm=600, unit_cost=2500),
    "WIN-STD-48x48": WindowType(id="WIN-STD-48x48", name="Standard window", width_mm=1200, height_mm=1200, unit_cost=900),
}


def catalog_dict() -> dict[str, Any]:
    from llmbim_core.materials import materials_catalog
    from llmbim_core.parts_catalog import PARTS

    plumbing = [p.id for p in PARTS.values() if p.category == "plumbing"]
    return {
        "wall_types": {k: v.model_dump() for k, v in DEFAULT_WALL_TYPES.items()},
        "door_types": {k: v.model_dump() for k, v in DEFAULT_DOOR_TYPES.items()},
        "window_types": {k: v.model_dump() for k, v in DEFAULT_WINDOW_TYPES.items()},
        "materials": materials_catalog(),
        "parts_count": len(PARTS),
        "parts_by_category": {
            cat: sum(1 for p in PARTS.values() if p.category == cat)
            for cat in sorted({p.category for p in PARTS.values()})
        },
        "plumbing_part_ids_sample": plumbing[:20],
        "plumbing_part_ids_count": len(plumbing),
    }
