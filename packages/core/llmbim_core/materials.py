"""Engineering materials library — densities, strengths, default costs.

Used by BOQ, type layers, and agent material assignments.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


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
    "copper_C12200": Material(
        id="copper_C12200",
        name="Copper tube ASTM B88 Type L (C12200)",
        category="metal",
        density_kg_m3=8940,
        E_GPa=117.0,
        unit_cost_per_kg=12.0,
        notes="Domestic water / process tubing",
        csi_hint="22 11 16",
    ),
    "copper_fitting": Material(
        id="copper_fitting",
        name="Wrought copper fitting (C12200)",
        category="metal",
        density_kg_m3=8940,
        unit_cost_per_kg=18.0,
        csi_hint="22 11 16",
    ),
    "brass": Material(
        id="brass",
        name="Brass valve body",
        category="metal",
        density_kg_m3=8500,
        unit_cost_per_kg=15.0,
        csi_hint="22 11 19",
    ),
    "pvc_sch40": Material(
        id="pvc_sch40",
        name="PVC Schedule 40",
        category="polymer",
        density_kg_m3=1400,
        unit_cost_per_kg=3.5,
        csi_hint="22 13 16",
    ),
    "pex": Material(
        id="pex",
        name="PEX tubing",
        category="polymer",
        density_kg_m3=940,
        unit_cost_per_kg=8.0,
        csi_hint="22 11 16",
    ),
    "cast_iron": Material(
        id="cast_iron",
        name="Cast iron soil pipe",
        category="metal",
        density_kg_m3=7200,
        unit_cost_per_kg=2.5,
        csi_hint="22 13 16",
    ),
    "metal_stud": Material(
        id="metal_stud",
        name="Light-gauge metal stud",
        category="steel",
        density_kg_m3=100,  # effective assembly density for layer takeoff
        unit_cost_per_m3=80,
        csi_hint="09 22 16",
    ),
    "solder": Material(
        id="solder",
        name="Lead-free solder (plumbing joints)",
        category="metal",
        density_kg_m3=8500,
        unit_cost_per_kg=45.0,
        csi_hint="22 11 16",
    ),
    # --- Fire / process metals ---
    "black_steel": Material(
        id="black_steel",
        name="Black steel pipe ASTM A53",
        category="steel",
        density_kg_m3=7850,
        E_GPa=200.0,
        fy_MPa=240.0,
        unit_cost_per_kg=1.5,
        notes="Fire sprinkler / standpipe",
        csi_hint="21 13 13",
    ),
    "galv_steel": Material(
        id="galv_steel",
        name="Galvanized steel sheet/pipe",
        category="steel",
        density_kg_m3=7850,
        unit_cost_per_kg=1.8,
        csi_hint="23 31 00",
    ),
    "steel_A500": Material(
        id="steel_A500",
        name="HSS steel ASTM A500 Gr B",
        category="steel",
        density_kg_m3=7850,
        E_GPa=200.0,
        fy_MPa=317.0,
        unit_cost_per_kg=1.6,
        csi_hint="05 12 00",
    ),
    "steel_A325": Material(
        id="steel_A325",
        name="High-strength bolt A325",
        category="steel",
        density_kg_m3=7850,
        unit_cost_per_kg=8.0,
        csi_hint="05 12 23",
    ),
    "steel_A490": Material(
        id="steel_A490",
        name="High-strength bolt A490",
        category="steel",
        density_kg_m3=7850,
        unit_cost_per_kg=10.0,
        csi_hint="05 12 23",
    ),
    "steel_A653": Material(
        id="steel_A653",
        name="Galvanized deck steel A653",
        category="steel",
        density_kg_m3=7850,
        unit_cost_per_kg=1.7,
        csi_hint="05 31 00",
    ),
    "rebar_G60": Material(
        id="rebar_G60",
        name="Reinforcing bar ASTM A615 Grade 60",
        category="steel",
        density_kg_m3=7850,
        fy_MPa=414.0,
        unit_cost_per_kg=1.1,
        csi_hint="03 20 00",
    ),
    "rebar_epoxy": Material(
        id="rebar_epoxy",
        name="Epoxy-coated rebar Grade 60",
        category="steel",
        density_kg_m3=7850,
        fy_MPa=414.0,
        unit_cost_per_kg=1.6,
        csi_hint="03 20 00",
    ),
    # --- Framing / wood ---
    "lumber_SPF": Material(
        id="lumber_SPF",
        name="SPF dimension lumber",
        category="wood",
        density_kg_m3=500,
        unit_cost_per_m3=450,
        csi_hint="06 10 00",
    ),
    "plywood": Material(
        id="plywood",
        name="Structural plywood",
        category="wood",
        density_kg_m3=550,
        unit_cost_per_m3=600,
        csi_hint="06 16 00",
    ),
    "osb": Material(
        id="osb",
        name="Oriented strand board",
        category="wood",
        density_kg_m3=600,
        unit_cost_per_m3=400,
        csi_hint="06 16 00",
    ),
    "hdpe": Material(
        id="hdpe",
        name="HDPE plastic",
        category="polymer",
        density_kg_m3=950,
        unit_cost_per_kg=3.0,
        csi_hint="06 60 00",
    ),
    # --- Fixtures finishes ---
    "vitreous_china": Material(
        id="vitreous_china",
        name="Vitreous china sanitary ware",
        category="finish",
        density_kg_m3=2300,
        unit_cost_per_kg=4.0,
        csi_hint="22 40 00",
    ),
    "ss304": Material(
        id="ss304",
        name="Stainless steel 304",
        category="metal",
        density_kg_m3=8000,
        E_GPa=193.0,
        fy_MPa=205.0,
        unit_cost_per_kg=5.5,
        csi_hint="05 50 00",
    ),
    "terrazzo": Material(
        id="terrazzo",
        name="Terrazzo / mop basin",
        category="finish",
        density_kg_m3=2400,
        unit_cost_per_m3=800,
        csi_hint="09 66 00",
    ),
    "ductile_iron": Material(
        id="ductile_iron",
        name="Ductile iron pipe",
        category="metal",
        density_kg_m3=7100,
        unit_cost_per_kg=2.2,
        csi_hint="33 11 00",
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
