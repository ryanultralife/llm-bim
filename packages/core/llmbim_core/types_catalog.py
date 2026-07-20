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


# imperial helpers for residential (US) assemblies
_IN_MM = 25.4
_FT_MM = 304.8

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
    # --- residential wood types (WP-SCHAD-S1, docs/SCHAD_REVIT_TO_LLMBIM_TRANSITION.md §7.1)
    "W-EXT-2x6-BNB": WallType(
        id="W-EXT-2x6-BNB",
        name='Exterior 2x6 + 5/8" DF board-and-batten',
        layers=[
            # 5/8" DF board-and-batten siding IS the structural/shear layer
            # (engineering memo governs over the OSB note — Schad Q-SHTG)
            MaterialLayer(material="df_bnb_siding", thickness_mm=0.625 * _IN_MM, function="structure", density_kg_m3=550),
            # 2x6 DF-L studs @ 16" OC, R-21 batt in cavity
            MaterialLayer(material="wood_stud_2x6", thickness_mm=5.5 * _IN_MM, function="structure", density_kg_m3=150),
            MaterialLayer(material="gypsum", thickness_mm=0.625 * _IN_MM, function="finish", density_kg_m3=800, unit_cost_per_m3=120),
        ],
        description='2x6 DF-L @ 16" OC; 5/8" DF board-and-batten structural siding; R-21 batt cavity; 5/8" gyp interior',
    ),
    "W-INT-2x4": WallType(
        id="W-INT-2x4",
        name="Interior 2x4 partition",
        layers=[
            MaterialLayer(material="gypsum", thickness_mm=0.5 * _IN_MM, function="finish", density_kg_m3=800, unit_cost_per_m3=120),
            MaterialLayer(material="wood_stud_2x4", thickness_mm=3.5 * _IN_MM, function="structure", density_kg_m3=150),
            MaterialLayer(material="gypsum", thickness_mm=0.5 * _IN_MM, function="finish", density_kg_m3=800, unit_cost_per_m3=120),
        ],
        description='2x4 DF-L @ 16" OC; 1/2" gyp both sides',
    ),
    "W-1HR-GAR-ADU": WallType(
        id="W-1HR-GAR-ADU",
        name="1-hr garage/ADU fire separation",
        layers=[
            MaterialLayer(material="gypsum_type_x", thickness_mm=0.625 * _IN_MM, function="finish", density_kg_m3=800, unit_cost_per_m3=140),
            MaterialLayer(material="wood_stud_2x6", thickness_mm=5.5 * _IN_MM, function="structure", density_kg_m3=150),
            MaterialLayer(material="gypsum_type_x", thickness_mm=0.625 * _IN_MM, function="finish", density_kg_m3=800, unit_cost_per_m3=140),
        ],
        fire_rating="1-hr",
        description='1-hr rated separation: 5/8" Type X gyp both sides of 2x6 DF-L studs',
    ),
}

DEFAULT_DOOR_TYPES: dict[str, DoorType] = {
    "D-HM-36": DoorType(id="D-HM-36", name="HM 3'-0\" x 7'-0\"", width_mm=900, height_mm=2100, unit_cost=1800),
    "D-HM-72": DoorType(id="D-HM-72", name="HM pair 6'-0\"", width_mm=1800, height_mm=2100, unit_cost=3200),
    "D-SHIELD-PLUG": DoorType(id="D-SHIELD-PLUG", name="Shield plug door", width_mm=1200, height_mm=2000, material="steel_plug", unit_cost=45000),
    # --- residential door types (WP-SCHAD-S1)
    "D-OH-12x9": DoorType(
        id="D-OH-12x9",
        name="Overhead sectional 12'-0\" x 9'-0\", insulated w/ glass panels",
        width_mm=12 * _FT_MM,
        height_mm=9 * _FT_MM,
        material="overhead_sectional",
    ),
    "D-OH-12x12": DoorType(
        id="D-OH-12x12",
        name="Overhead sectional 12'-0\" x 12'-0\", insulated w/ glass panels",
        width_mm=12 * _FT_MM,
        height_mm=12 * _FT_MM,
        material="overhead_sectional",
    ),
    "D-SC-36-ADA": DoorType(
        id="D-SC-36-ADA",
        name="Solid core 3'-0\" x 6'-8\" entry, ADA compliant",
        width_mm=3 * _FT_MM,
        height_mm=(6 * 12 + 8) * _IN_MM,
        material="solid_core_wood",
    ),
    "D-HM-30": DoorType(
        id="D-HM-30",
        name="Hollow metal 2'-6\" x 6'-8\"",
        width_mm=2.5 * _FT_MM,
        height_mm=(6 * 12 + 8) * _IN_MM,
        material="hollow_metal",
    ),
}

DEFAULT_WINDOW_TYPES: dict[str, WindowType] = {
    "WIN-VIEW-24x24": WindowType(id="WIN-VIEW-24x24", name="View window", width_mm=600, height_mm=600, unit_cost=2500),
    "WIN-STD-48x48": WindowType(id="WIN-STD-48x48", name="Standard window", width_mm=1200, height_mm=1200, unit_cost=900),
    # --- residential window types (WP-SCHAD-S1)
    "WIN-CASE-48x48": WindowType(
        id="WIN-CASE-48x48",
        name="Vinyl casement 4'-0\" x 4'-0\", double pane, U-0.30",
        width_mm=4 * _FT_MM,
        height_mm=4 * _FT_MM,
        u_value=0.30,
    ),
}


def register_wall_type(wt: WallType) -> WallType:
    """Register a wall type into the shared catalog (project/agent-defined).

    Registered types get the same ``set_type`` sync (thickness_mm + wall_layers
    + fire_rating) as the shipped ``DEFAULT_WALL_TYPES``.
    """
    DEFAULT_WALL_TYPES[wt.id] = wt
    return wt


def register_door_type(dt: DoorType) -> DoorType:
    DEFAULT_DOOR_TYPES[dt.id] = dt
    return dt


def register_window_type(wt: WindowType) -> WindowType:
    DEFAULT_WINDOW_TYPES[wt.id] = wt
    return wt


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
