"""Part types (manufactured / procured items) with materials and BOM lines.

Full BIM for parts: each part has a primary material, optional multi-material
BOM, mass estimate, CSI, and vendor fields. Instances on the model reference
part_id and can override qty/material.

Plumbing / MEP: copper Type L pipe + wrought fittings by NPS so agents can
answer "how many 90° copper elbows of what size?"
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from llmbim_core.materials import MATERIALS, get_material, material_cost, material_mass_kg

Unit = Literal["ea", "m", "m2", "m3", "kg", "L", "set", "ft"]

# Nominal pipe size (inch label) → OD mm (copper Type L approx)
COPPER_NPS: dict[str, dict[str, float]] = {
    "1/2": {"od_mm": 15.9, "id_mm": 13.8, "wall_mm": 1.07, "mass_kg_m": 0.34, "unit_cost_m": 18.0},
    "3/4": {"od_mm": 22.2, "id_mm": 19.9, "wall_mm": 1.14, "mass_kg_m": 0.51, "unit_cost_m": 28.0},
    "1": {"od_mm": 28.6, "id_mm": 26.0, "wall_mm": 1.27, "mass_kg_m": 0.74, "unit_cost_m": 42.0},
    "1-1/4": {"od_mm": 34.9, "id_mm": 32.1, "wall_mm": 1.40, "mass_kg_m": 0.99, "unit_cost_m": 58.0},
    "1-1/2": {"od_mm": 41.3, "id_mm": 38.3, "wall_mm": 1.52, "mass_kg_m": 1.28, "unit_cost_m": 72.0},
    "2": {"od_mm": 54.0, "id_mm": 50.4, "wall_mm": 1.78, "mass_kg_m": 1.96, "unit_cost_m": 110.0},
    "2-1/2": {"od_mm": 66.7, "id_mm": 62.7, "wall_mm": 2.03, "mass_kg_m": 2.78, "unit_cost_m": 165.0},
    "3": {"od_mm": 79.4, "id_mm": 74.8, "wall_mm": 2.29, "mass_kg_m": 3.72, "unit_cost_m": 220.0},
    "4": {"od_mm": 104.8, "id_mm": 99.6, "wall_mm": 2.54, "mass_kg_m": 5.50, "unit_cost_m": 340.0},
}

# Fitting unit costs (ea) by family × nps — rough trade estimates
_FITTING_COST: dict[str, dict[str, float]] = {
    "elbow_90": {"1/2": 4.5, "3/4": 6.0, "1": 9.0, "1-1/4": 14.0, "1-1/2": 18.0, "2": 28.0, "2-1/2": 45.0, "3": 65.0, "4": 110.0},
    "elbow_45": {"1/2": 5.0, "3/4": 7.0, "1": 11.0, "1-1/4": 16.0, "1-1/2": 22.0, "2": 34.0, "2-1/2": 52.0, "3": 78.0, "4": 130.0},
    "tee": {"1/2": 7.0, "3/4": 10.0, "1": 15.0, "1-1/4": 22.0, "1-1/2": 30.0, "2": 48.0, "2-1/2": 75.0, "3": 110.0, "4": 180.0},
    "coupling": {"1/2": 2.5, "3/4": 3.5, "1": 5.0, "1-1/4": 7.5, "1-1/2": 10.0, "2": 16.0, "2-1/2": 25.0, "3": 38.0, "4": 60.0},
    "cap": {"1/2": 2.0, "3/4": 2.8, "1": 4.0, "1-1/4": 6.0, "1-1/2": 8.0, "2": 12.0, "2-1/2": 18.0, "3": 28.0, "4": 45.0},
    "union": {"1/2": 12.0, "3/4": 16.0, "1": 24.0, "1-1/4": 36.0, "1-1/2": 48.0, "2": 75.0, "2-1/2": 110.0, "3": 160.0, "4": 250.0},
    "ball_valve": {"1/2": 28.0, "3/4": 38.0, "1": 55.0, "1-1/4": 85.0, "1-1/2": 110.0, "2": 160.0, "2-1/2": 240.0, "3": 350.0, "4": 550.0},
    "reducer": {"1/2": 6.0, "3/4": 8.0, "1": 12.0, "1-1/4": 18.0, "1-1/2": 24.0, "2": 38.0, "2-1/2": 55.0, "3": 80.0, "4": 120.0},
}

_FITTING_LABELS = {
    "elbow_90": "90° elbow",
    "elbow_45": "45° elbow",
    "tee": "Tee",
    "coupling": "Coupling",
    "cap": "Cap",
    "union": "Union",
    "ball_valve": "Ball valve",
    "reducer": "Reducer",
}


def nps_slug(nps: str) -> str:
    """1/2 → 1_2, 1-1/4 → 1_1_4 for part ids."""
    return nps.replace("-", "_").replace("/", "_")


class BomLine(BaseModel):
    """One line on a part or assembly bill of materials."""

    material_id: str
    qty: float = 1.0
    unit: Unit = "ea"
    description: str = ""
    # if unit is m3/kg, qty is that amount; if ea, count of that material chunk
    volume_m3: float | None = None  # optional explicit volume for cost/mass
    mass_kg: float | None = None


class PartType(BaseModel):
    """Catalog part (type) — reusable definition."""

    id: str
    name: str
    category: str = "part"  # structural | envelope | process | plumbing | electrical | fastener | other
    primary_material_id: str = "generic"
    bom: list[BomLine] = Field(default_factory=list)
    description: str = ""
    manufacturer: str = ""
    model_number: str = ""
    csi_code: str = ""
    unit_cost: float = 0.0  # procured cost per each (overrides material rollup if set)
    default_size_mm: list[float] | None = None  # L,W,H or L,D,D
    shape: str = "box"  # box | cylinder
    specs: dict[str, Any] = Field(default_factory=dict)

    def resolved_bom(self) -> list[BomLine]:
        if self.bom:
            return list(self.bom)
        if self.primary_material_id:
            return [
                BomLine(
                    material_id=self.primary_material_id,
                    qty=1.0,
                    unit="ea",
                    description=f"Primary material for {self.name}",
                )
            ]
        return []


def _register_plumbing_parts(into: dict[str, PartType]) -> None:
    """Copper Type L pipe + wrought copper fittings by NPS."""
    for nps, geom in COPPER_NPS.items():
        slug = nps_slug(nps)
        # pipe — sold per meter; default_size is 1 m stick diameter
        pid = f"PT-CU-PIPE-{slug}"
        into[pid] = PartType(
            id=pid,
            name=f"Copper Type L pipe {nps}\"",
            category="plumbing",
            primary_material_id="copper_C12200",
            csi_code="22 11 16",
            unit_cost=geom["unit_cost_m"],
            shape="cylinder",
            default_size_mm=[1000.0, geom["od_mm"], geom["od_mm"]],
            bom=[
                BomLine(
                    material_id="copper_C12200",
                    qty=1.0,
                    unit="m",
                    description=f"Type L {nps}\" tube per meter",
                    mass_kg=geom["mass_kg_m"],
                )
            ],
            specs={
                "system": "plumbing",
                "material": "copper_C12200",
                "alloy": "C12200",
                "spec": "ASTM B88 Type L",
                "nps": nps,
                "nps_in": nps,
                "fitting_type": "pipe",
                "od_mm": geom["od_mm"],
                "id_mm": geom["id_mm"],
                "wall_mm": geom["wall_mm"],
                "mass_kg_m": geom["mass_kg_m"],
                "unit": "m",
            },
        )
        # fittings (each)
        for ftype, costs in _FITTING_COST.items():
            cost = costs.get(nps, 0.0)
            if not cost:
                continue
            fid = f"PT-CU-{ftype.upper().replace('_', '')}-{slug}"
            # friendlier fixed ids for common queries
            if ftype == "elbow_90":
                fid = f"PT-CU-ELB90-{slug}"
            elif ftype == "elbow_45":
                fid = f"PT-CU-ELB45-{slug}"
            elif ftype == "tee":
                fid = f"PT-CU-TEE-{slug}"
            elif ftype == "coupling":
                fid = f"PT-CU-CPL-{slug}"
            elif ftype == "cap":
                fid = f"PT-CU-CAP-{slug}"
            elif ftype == "union":
                fid = f"PT-CU-UNION-{slug}"
            elif ftype == "ball_valve":
                fid = f"PT-CU-BALL-{slug}"
            elif ftype == "reducer":
                fid = f"PT-CU-RED-{slug}"
            label = _FITTING_LABELS[ftype]
            mat = "brass" if ftype == "ball_valve" else "copper_fitting"
            # rough fitting mass ~ 0.15–0.8 of 0.1 m pipe
            mass = round(geom["mass_kg_m"] * (0.08 if ftype == "cap" else 0.15 if ftype != "ball_valve" else 0.35), 3)
            into[fid] = PartType(
                id=fid,
                name=f"Copper {label} {nps}\"",
                category="plumbing",
                primary_material_id=mat,
                csi_code="22 11 19" if ftype == "ball_valve" else "22 11 16",
                unit_cost=cost,
                shape="box",
                default_size_mm=[geom["od_mm"] * 2, geom["od_mm"] * 2, geom["od_mm"] * 2],
                bom=[
                    BomLine(
                        material_id=mat,
                        qty=1.0,
                        unit="ea",
                        description=f"{label} {nps}\"",
                        mass_kg=mass,
                    )
                ],
                specs={
                    "system": "plumbing",
                    "material": mat,
                    "alloy": "C12200" if mat.startswith("copper") else "brass",
                    "nps": nps,
                    "nps_in": nps,
                    "fitting_type": ftype,
                    "angle_deg": 90 if ftype == "elbow_90" else (45 if ftype == "elbow_45" else None),
                    "od_mm": geom["od_mm"],
                    "unit": "ea",
                },
            )

    # PVC Sch40 sample sizes for drain (gap: not only copper)
    for nps, od, cost_m, mass_m in (
        ("1-1/2", 48.3, 8.0, 0.45),
        ("2", 60.3, 11.0, 0.62),
        ("3", 88.9, 18.0, 1.10),
        ("4", 114.3, 28.0, 1.65),
    ):
        slug = nps_slug(nps)
        pid = f"PT-PVC-PIPE-{slug}"
        into[pid] = PartType(
            id=pid,
            name=f"PVC Sch40 pipe {nps}\"",
            category="plumbing",
            primary_material_id="pvc_sch40",
            csi_code="22 13 16",
            unit_cost=cost_m,
            shape="cylinder",
            default_size_mm=[1000.0, od, od],
            bom=[BomLine(material_id="pvc_sch40", qty=1.0, unit="m", mass_kg=mass_m)],
            specs={
                "system": "plumbing",
                "material": "pvc_sch40",
                "nps": nps,
                "fitting_type": "pipe",
                "od_mm": od,
                "unit": "m",
            },
        )
        for ftype, mult in (("elbow_90", 1.0), ("tee", 1.4), ("coupling", 0.5)):
            fid = f"PT-PVC-{'ELB90' if ftype == 'elbow_90' else ftype.upper()[:3]}-{slug}"
            if ftype == "elbow_90":
                fid = f"PT-PVC-ELB90-{slug}"
            elif ftype == "tee":
                fid = f"PT-PVC-TEE-{slug}"
            else:
                fid = f"PT-PVC-CPL-{slug}"
            into[fid] = PartType(
                id=fid,
                name=f"PVC {_FITTING_LABELS[ftype]} {nps}\"",
                category="plumbing",
                primary_material_id="pvc_sch40",
                csi_code="22 13 16",
                unit_cost=round(cost_m * 0.4 * mult, 2),
                specs={
                    "system": "plumbing",
                    "material": "pvc_sch40",
                    "nps": nps,
                    "fitting_type": ftype,
                    "angle_deg": 90 if ftype == "elbow_90" else None,
                    "unit": "ea",
                },
            )


# --- Built-in catalog (facilities + Proto10-class process) --------------------

PARTS: dict[str, PartType] = {
    "PT-WALL-CMU-200": PartType(
        id="PT-WALL-CMU-200",
        name="CMU wall assembly 200 mm",
        category="envelope",
        primary_material_id="CMU",
        csi_code="04 22 00",
        bom=[
            BomLine(material_id="CMU", qty=1.0, unit="m3", description="CMU volume per m2 × thickness"),
            BomLine(material_id="rigid_insulation", qty=0.05, unit="m3", description="50 mm continuous"),
            BomLine(material_id="gypsum", qty=0.016, unit="m3", description="Interior gyp"),
        ],
    ),
    "PT-SLAB-CONC-200": PartType(
        id="PT-SLAB-CONC-200",
        name="Concrete slab 200 mm",
        category="structural",
        primary_material_id="concrete_4000psi",
        csi_code="03 30 00",
        bom=[BomLine(material_id="concrete_4000psi", qty=0.2, unit="m3", description="per m2 of slab")],
    ),
    "PT-DOOR-HM-900": PartType(
        id="PT-DOOR-HM-900",
        name="Hollow metal door 900×2100",
        category="envelope",
        primary_material_id="steel_A36",
        csi_code="08 11 13",
        unit_cost=1800,
        default_size_mm=[900, 50, 2100],
        specs={"fire_rating": "20-min"},
    ),
    "PT-WIN-1200": PartType(
        id="PT-WIN-1200",
        name="Window 1200×1200",
        category="envelope",
        primary_material_id="aluminum_6061",
        csi_code="08 50 00",
        unit_cost=900,
        default_size_mm=[1200, 100, 1200],
    ),
    "PT-SEP-SHELL-320": PartType(
        id="PT-SEP-SHELL-320",
        name="Separator shell Al6061 320 OD × 500",
        category="process",
        primary_material_id="aluminum_6061",
        csi_code="40 05 00",
        shape="cylinder",
        default_size_mm=[500, 320, 320],
        manufacturer="TBD machine shop",
        bom=[
            BomLine(
                material_id="aluminum_6061",
                qty=1.0,
                unit="kg",
                description="Shell blank (est.)",
                mass_kg=12.5,
            )
        ],
        specs={"od_mm": 320, "length_mm": 500, "alloy": "6061-T6"},
    ),
    "PT-SEP-FLANGE-380": PartType(
        id="PT-SEP-FLANGE-380",
        name="End flange 380 × 25",
        category="process",
        primary_material_id="aluminum_6061",
        csi_code="40 05 13",
        shape="cylinder",
        default_size_mm=[25, 380, 380],
        bom=[BomLine(material_id="aluminum_6061", qty=1.0, unit="kg", mass_kg=7.0)],
        specs={"od_mm": 380, "thk_mm": 25},
    ),
    "PT-SEP-CARTRIDGE-ULTEM": PartType(
        id="PT-SEP-CARTRIDGE-ULTEM",
        name="Ultem 1000 cartridge 298×450",
        category="process",
        primary_material_id="Ultem_1000",
        csi_code="43 41 00",
        shape="cylinder",
        default_size_mm=[450, 298, 298],
        bom=[BomLine(material_id="Ultem_1000", qty=1.0, unit="kg", mass_kg=11.4)],
        specs={"material": "Ultem 1000", "slots": 30},
    ),
    "PT-SEP-MAGNET-N42": PartType(
        id="PT-SEP-MAGNET-N42",
        name="N42 ring magnet 500/340 × 50",
        category="process",
        primary_material_id="NdFeB_N42",
        csi_code="11 90 00",
        shape="cylinder",
        default_size_mm=[50, 500, 500],
        bom=[BomLine(material_id="NdFeB_N42", qty=1.0, unit="ea")],
        unit_cost=2500,
        specs={"grade": "N42", "od_mm": 500, "id_mm": 340},
    ),
    "PT-SEP-YOKE-IRON": PartType(
        id="PT-SEP-YOKE-IRON",
        name="Iron yoke envelope",
        category="process",
        primary_material_id="steel_A36",
        default_size_mm=[590, 560, 300],
        bom=[BomLine(material_id="steel_A36", qty=1.0, unit="kg", mass_kg=180)],
        csi_code="05 12 00",
    ),
    "PT-SEP-PEDESTAL": PartType(
        id="PT-SEP-PEDESTAL",
        name="Pedestal pad 800×800×200",
        category="structural",
        primary_material_id="steel_A36",
        csi_code="05 50 00",
        default_size_mm=[800, 800, 200],
        bom=[BomLine(material_id="steel_A36", qty=1.0, unit="kg", mass_kg=95)],
    ),
    "PT-VESSEL-SIZE-B": PartType(
        id="PT-VESSEL-SIZE-B",
        name="Size-B separator vessel 610 OD × 1200",
        category="process",
        primary_material_id="ss316L",
        shape="cylinder",
        default_size_mm=[1200, 610, 610],
        csi_code="43 41 00",
        bom=[
            BomLine(material_id="ss316L", qty=1.0, unit="kg", mass_kg=280, description="Shell+flanges empty"),
        ],
        specs={"od_mm": 610, "length_mm": 1200, "material": "316L"},
    ),
    "PT-COLUMN-W10x33": PartType(
        id="PT-COLUMN-W10x33",
        name="W10×33 steel column",
        category="structural",
        primary_material_id="steel_A992",
        csi_code="05 12 00",
        bom=[BomLine(material_id="steel_A992", qty=49.1, unit="kg", description="per meter length")],
        specs={"section": "W10x33", "weight_kg_m": 49.1},
    ),
}

_register_plumbing_parts(PARTS)

# Fire, process, framing, structural steel, rebar, fixtures, HVAC/elec
from llmbim_core.catalog_systems import register_all_systems  # noqa: E402

register_all_systems(PARTS)


def get_part(part_id: str) -> PartType | None:
    return PARTS.get(part_id)


def parts_catalog() -> dict[str, Any]:
    return {k: v.model_dump() for k, v in PARTS.items()}


def list_parts(
    *,
    category: str | None = None,
    fitting_type: str | None = None,
    nps: str | None = None,
    material: str | None = None,
    system: str | None = None,
    csi_prefix: str | None = None,
    section: str | None = None,
    bar_size: str | None = None,
) -> list[PartType]:
    """Filter catalog parts by trade attributes."""
    out: list[PartType] = []
    for p in PARTS.values():
        if category and p.category != category:
            continue
        sp = p.specs or {}
        if fitting_type and sp.get("fitting_type") != fitting_type:
            continue
        if nps and str(sp.get("nps") or "") != nps:
            continue
        if section and str(sp.get("section") or "") != section:
            continue
        if bar_size and str(sp.get("bar_size") or sp.get("bar_no") or "") != str(bar_size):
            continue
        if material:
            ml = material.lower()
            mid = (p.primary_material_id or "").lower()
            sm = str(sp.get("material") or "").lower()
            if ml not in mid and ml not in sm and not (
                ml in ("copper", "cu") and "copper" in mid
            ) and not (ml in ("ss", "ss316", "316") and "ss316" in mid):
                continue
        if system and sp.get("system") != system and p.category != system:
            continue
        if csi_prefix and not (p.csi_code or "").startswith(csi_prefix):
            continue
        out.append(p)
    return sorted(out, key=lambda x: x.id)


def resolve_fitting_part_id(
    fitting_type: str,
    nps: str,
    *,
    material: str = "copper",
) -> str | None:
    """Map (elbow_90, 1/2, copper|fire|ss|pvc) → catalog part id."""
    slug = nps_slug(nps)
    mat = material.lower().replace(" ", "_")
    # material / system aliases → part id prefix
    if mat in ("copper", "cu", "c12200", "copper_c12200", "plumbing"):
        prefix = "PT-CU"
    elif "pvc" in mat:
        prefix = "PT-PVC"
    elif mat in ("fire", "fp", "sprinkler", "black_steel", "black", "a53"):
        prefix = "PT-FP"
    elif mat in ("process", "ss", "ss316", "ss316l", "316", "316l", "stainless"):
        prefix = "PT-SS"
    else:
        prefix = None
    if not prefix:
        return None
    type_map = {
        "elbow_90": "ELB90",
        "90": "ELB90",
        "elb90": "ELB90",
        "elbow_45": "ELB45",
        "45": "ELB45",
        "tee": "TEE",
        "coupling": "CPL",
        "cap": "CAP",
        "union": "UNION",
        "ball_valve": "BALL",
        "gate_valve": "GATE",
        "check_valve": "CHK",
        "flange": "FLG",
        "grooved_coupling": "GRV",
        "valve": "BALL",
        "reducer": "RED",
        "pipe": "PIPE",
    }
    code = type_map.get(fitting_type.lower().replace(" ", "_"))
    if not code:
        return None
    pid = f"{prefix}-{code}-{slug}"
    return pid if pid in PARTS else None


def resolve_part_id(
    *,
    kind: str | None = None,
    section: str | None = None,
    bar_size: str | None = None,
    fitting_type: str | None = None,
    nps: str | None = None,
    material: str = "copper",
    name_contains: str | None = None,
) -> str | None:
    """Resolve common trade items to catalog ids.

    Examples:
      resolve_part_id(section=\"W10x33\")
      resolve_part_id(bar_size=\"5\")
      resolve_part_id(kind=\"toilet\")
      resolve_part_id(kind=\"tp_dispenser\")
      resolve_part_id(fitting_type=\"elbow_90\", nps=\"2\", material=\"fire\")
    """
    if fitting_type and nps:
        pid = resolve_fitting_part_id(fitting_type, nps, material=material)
        if pid:
            return pid
    if section:
        # W10x33 → PT-STL-W10x33 or existing PT-COLUMN-W10x33
        sec = section.replace("×", "x").replace(" ", "")
        for cand in (f"PT-STL-{sec}", f"PT-COLUMN-{sec}", f"PT-STL-{sec.replace('/', '_')}"):
            if cand in PARTS:
                return cand
        for p in PARTS.values():
            if (p.specs or {}).get("section") == section or (p.specs or {}).get("section") == sec:
                return p.id
    if bar_size is not None:
        pid = f"PT-RBR-BAR-{bar_size}"
        if pid in PARTS:
            return pid
    if kind:
        k = kind.lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "toilet": "PT-PLB-WC-FLOOR",
            "wc": "PT-PLB-WC-FLOOR",
            "water_closet": "PT-PLB-WC-FLOOR",
            "toilet_ada": "PT-PLB-WC-ADA",
            "urinal": "PT-PLB-URINAL-WALL",
            "lavatory": "PT-PLB-LAV-WALL",
            "lav": "PT-PLB-LAV-WALL",
            "toilet_hose": "PT-PLB-HOSE-WC-BRAID",
            "supply_hose": "PT-PLB-HOSE-WC-BRAID",
            "tp_dispenser": "PT-ACC-TP-DOUBLE",
            "toilet_paper": "PT-ACC-TP-DOUBLE",
            "toilet_paper_dispenser": "PT-ACC-TP-DOUBLE",
            "soap_dispenser": "PT-ACC-SOAP-MAN",
            "grab_bar": "PT-ACC-GRAB-36",
            "hand_dryer": "PT-ACC-HAND-DRY",
            "mirror": "PT-ACC-MIRROR-18X36",
            "sprinkler": "PT-FP-HEAD-PENDENT_5_6_155F",
            "sprinkler_head": "PT-FP-HEAD-PENDENT_5_6_155F",
            "extinguisher": "PT-FP-EXT-ABC-10",
            "floor_drain": "PT-PLB-FD-3",
            "flush_valve": "PT-PLB-FLUSH-VALVE",
            "stud_2x4": "PT-WD-STUD-2X4",
            "metal_stud": "PT-MS-STUD-362-20",
        }
        if k in aliases and aliases[k] in PARTS:
            return aliases[k]
        for p in PARTS.values():
            if (p.specs or {}).get("fitting_type") == k:
                return p.id
            if k in p.id.lower() or k in p.name.lower().replace(" ", "_"):
                return p.id
    if name_contains:
        nc = name_contains.lower()
        for p in PARTS.values():
            if nc in p.name.lower() or nc in p.id.lower():
                return p.id
    return None


def register_part(part: PartType) -> PartType:
    """Agent extension: add custom part to runtime catalog."""
    PARTS[part.id] = part
    return part


def catalog_summary() -> dict[str, Any]:
    by_cat: dict[str, int] = {}
    by_sys: dict[str, int] = {}
    by_csi: dict[str, int] = {}
    for p in PARTS.values():
        by_cat[p.category] = by_cat.get(p.category, 0) + 1
        sys = (p.specs or {}).get("system") or p.category
        by_sys[str(sys)] = by_sys.get(str(sys), 0) + 1
        div = (p.csi_code or "00")[:2]
        by_csi[div] = by_csi.get(div, 0) + 1
    return {
        "parts_count": len(PARTS),
        "by_category": dict(sorted(by_cat.items())),
        "by_system": dict(sorted(by_sys.items())),
        "by_csi_division": dict(sorted(by_csi.items())),
    }


def part_unit_cost(part: PartType) -> float:
    if part.unit_cost > 0:
        return part.unit_cost
    total = 0.0
    for line in part.resolved_bom():
        if line.mass_kg is not None:
            m = get_material(line.material_id)
            if m and m.unit_cost_per_kg:
                total += line.mass_kg * m.unit_cost_per_kg * line.qty
                continue
        if line.volume_m3 is not None:
            total += material_cost(line.material_id, line.volume_m3) * line.qty
            continue
        if line.unit == "kg":
            m = get_material(line.material_id)
            if m and m.unit_cost_per_kg:
                total += line.qty * m.unit_cost_per_kg
        elif line.unit == "m3":
            total += material_cost(line.material_id, line.qty)
    return total


def explode_part_bom(part: PartType, instance_qty: float = 1.0) -> list[dict[str, Any]]:
    """Explode part BOM to material lines with mass/cost."""
    rows = []
    for line in part.resolved_bom():
        mat = get_material(line.material_id)
        mass = line.mass_kg
        vol = line.volume_m3
        if mass is None and vol is not None:
            mass = material_mass_kg(line.material_id, vol)
        if vol is None and mass is not None and mat and mat.density_kg_m3:
            vol = mass / mat.density_kg_m3
        cost = 0.0
        if line.mass_kg is not None and mat and mat.unit_cost_per_kg:
            cost = line.mass_kg * mat.unit_cost_per_kg
        elif vol is not None:
            cost = material_cost(line.material_id, vol)
        elif line.unit == "kg" and mat and mat.unit_cost_per_kg:
            cost = line.qty * mat.unit_cost_per_kg
        elif line.unit == "m3":
            cost = material_cost(line.material_id, line.qty)
            vol = line.qty
            mass = material_mass_kg(line.material_id, line.qty)

        rows.append(
            {
                "part_id": part.id,
                "part_name": part.name,
                "material_id": line.material_id,
                "material_name": mat.name if mat else line.material_id,
                "description": line.description,
                "qty": line.qty * instance_qty,
                "unit": line.unit,
                "volume_m3": round(vol, 6) if vol is not None else None,
                "mass_kg": round(mass, 3) if mass is not None else None,
                "est_cost": round(cost * instance_qty, 2),
                "csi_hint": mat.csi_hint if mat else part.csi_code,
            }
        )
    return rows
