"""Engineering materials library — densities, strengths, default costs.

Used by BOQ, type layers, and agent material assignments.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Material(BaseModel):
    id: str
    name: str
    category: str = "general"  # concrete | steel | masonry | insulation | finish | metal | polymer | other
    density_kg_m3: float = 0.0
    E_GPa: float | None = None  # Young's modulus
    fy_MPa: float | None = None  # yield strength
    fc_MPa: float | None = None  # concrete compressive
    thermal_k: float | None = None  # W/mK
    unit_cost_per_m3: float = 0.0
    unit_cost_per_kg: float = 0.0
    notes: str = ""
    csi_hint: str = ""


MATERIALS: dict[str, Material] = {
    "concrete_4000psi": Material(
        id="concrete_4000psi",
        name="Normalweight concrete 28 MPa (≈4000 psi)",
        category="concrete",
        density_kg_m3=2400,
        E_GPa=30.0,
        fc_MPa=28.0,
        unit_cost_per_m3=350,
        csi_hint="03 30 00",
    ),
    "concrete_shield": Material(
        id="concrete_shield",
        name="High-density shielding concrete",
        category="concrete",
        density_kg_m3=3500,
        E_GPa=35.0,
        fc_MPa=35.0,
        unit_cost_per_m3=550,
        notes="Hot-cell / tunnel bioshield",
        csi_hint="03 30 00",
    ),
    "steel_A36": Material(
        id="steel_A36",
        name="Carbon steel ASTM A36",
        category="steel",
        density_kg_m3=7850,
        E_GPa=200.0,
        fy_MPa=250.0,
        unit_cost_per_kg=1.2,
        csi_hint="05 12 00",
    ),
    "steel_A992": Material(
        id="steel_A992",
        name="Structural steel ASTM A992",
        category="steel",
        density_kg_m3=7850,
        E_GPa=200.0,
        fy_MPa=345.0,
        unit_cost_per_kg=1.4,
        csi_hint="05 12 00",
    ),
    "ss316L": Material(
        id="ss316L",
        name="Stainless steel 316L",
        category="metal",
        density_kg_m3=8000,
        E_GPa=193.0,
        fy_MPa=170.0,
        unit_cost_per_kg=8.0,
        notes="Vacuum / process / liner",
        csi_hint="05 50 00",
    ),
    "aluminum_6061": Material(
        id="aluminum_6061",
        name="Aluminum 6061-T6",
        category="metal",
        density_kg_m3=2700,
        E_GPa=69.0,
        fy_MPa=276.0,
        unit_cost_per_kg=4.5,
        csi_hint="05 50 00",
    ),
    "CMU": Material(
        id="CMU",
        name="Concrete masonry unit",
        category="masonry",
        density_kg_m3=1800,
        unit_cost_per_m3=250,
        csi_hint="04 22 00",
    ),
    "gypsum": Material(
        id="gypsum",
        name="Gypsum board",
        category="finish",
        density_kg_m3=800,
        unit_cost_per_m3=120,
        csi_hint="09 21 00",
    ),
    "rigid_insulation": Material(
        id="rigid_insulation",
        name="Rigid foam insulation",
        category="insulation",
        density_kg_m3=30,
        thermal_k=0.03,
        unit_cost_per_m3=400,
        csi_hint="07 21 00",
    ),
    "batt_insulation": Material(
        id="batt_insulation",
        name="Batt insulation",
        category="insulation",
        density_kg_m3=20,
        thermal_k=0.04,
        unit_cost_per_m3=60,
        csi_hint="07 21 00",
    ),
    "PEEK": Material(
        id="PEEK",
        name="PEEK polymer",
        category="polymer",
        density_kg_m3=1300,
        unit_cost_per_kg=120,
        notes="Process cartridge (production)",
        csi_hint="06 60 00",
    ),
    "Ultem_1000": Material(
        id="Ultem_1000",
        name="Ultem 1000 (PEI)",
        category="polymer",
        density_kg_m3=1270,
        unit_cost_per_kg=90,
        notes="Proto10 cartridge material",
        csi_hint="06 60 00",
    ),
    "NdFeB_N42": Material(
        id="NdFeB_N42",
        name="Neodymium N42 magnet",
        category="other",
        density_kg_m3=7500,
        unit_cost_per_kg=80,
        csi_hint="11 90 00",
    ),
    "generic": Material(
        id="generic",
        name="Generic construction material",
        category="general",
        density_kg_m3=1000,
        unit_cost_per_m3=150,
        csi_hint="01 00 00",
    ),
}


def get_material(material_id: str) -> Material | None:
    return MATERIALS.get(material_id)


def materials_catalog() -> dict[str, Any]:
    return {k: v.model_dump() for k, v in MATERIALS.items()}


def material_mass_kg(material_id: str, volume_m3: float) -> float:
    m = MATERIALS.get(material_id)
    if not m:
        return 0.0
    return m.density_kg_m3 * volume_m3


def material_cost(material_id: str, volume_m3: float) -> float:
    m = MATERIALS.get(material_id)
    if not m:
        return 0.0
    if m.unit_cost_per_m3:
        return m.unit_cost_per_m3 * volume_m3
    if m.unit_cost_per_kg:
        return m.unit_cost_per_kg * material_mass_kg(material_id, volume_m3)
    return 0.0
