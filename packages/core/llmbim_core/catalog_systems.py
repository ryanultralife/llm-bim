"""Expanded CSI-aligned part catalogs: fire, process, framing, steel, rebar, fixtures.

Registers into PARTS. ENGINEERING ESTIMATE unit costs — not a bid.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llmbim_core.parts_catalog import PartType

# Shared NPS table (steel pipe OD approx — ASTM A53)
STEEL_NPS: dict[str, dict[str, float]] = {
    "1/2": {"od_mm": 21.3, "mass_kg_m": 1.27, "unit_cost_m": 12.0},
    "3/4": {"od_mm": 26.7, "mass_kg_m": 1.69, "unit_cost_m": 15.0},
    "1": {"od_mm": 33.4, "mass_kg_m": 2.50, "unit_cost_m": 22.0},
    "1-1/4": {"od_mm": 42.2, "mass_kg_m": 3.39, "unit_cost_m": 30.0},
    "1-1/2": {"od_mm": 48.3, "mass_kg_m": 4.05, "unit_cost_m": 38.0},
    "2": {"od_mm": 60.3, "mass_kg_m": 5.44, "unit_cost_m": 52.0},
    "2-1/2": {"od_mm": 73.0, "mass_kg_m": 8.63, "unit_cost_m": 78.0},
    "3": {"od_mm": 88.9, "mass_kg_m": 11.3, "unit_cost_m": 105.0},
    "4": {"od_mm": 114.3, "mass_kg_m": 16.1, "unit_cost_m": 155.0},
    "6": {"od_mm": 168.3, "mass_kg_m": 28.3, "unit_cost_m": 280.0},
    "8": {"od_mm": 219.1, "mass_kg_m": 42.5, "unit_cost_m": 420.0},
}

_FTYPE_CODES = {
    "elbow_90": "ELB90",
    "elbow_45": "ELB45",
    "tee": "TEE",
    "coupling": "CPL",
    "cap": "CAP",
    "union": "UNION",
    "ball_valve": "BALL",
    "gate_valve": "GATE",
    "check_valve": "CHK",
    "flange": "FLG",
    "reducer": "RED",
    "pipe": "PIPE",
    "grooved_coupling": "GRV",
}

_FTYPE_LABELS = {
    "elbow_90": "90° elbow",
    "elbow_45": "45° elbow",
    "tee": "Tee",
    "coupling": "Coupling",
    "cap": "Cap",
    "union": "Union",
    "ball_valve": "Ball valve",
    "gate_valve": "Gate valve",
    "check_valve": "Check valve",
    "flange": "Weld-neck flange",
    "reducer": "Reducer",
    "pipe": "Pipe",
    "grooved_coupling": "Grooved coupling",
}

# Relative cost mult vs pipe $/m for fittings (ea)
_FTYPE_MULT = {
    "elbow_90": 0.35,
    "elbow_45": 0.40,
    "tee": 0.55,
    "coupling": 0.20,
    "cap": 0.15,
    "union": 0.90,
    "ball_valve": 4.0,
    "gate_valve": 3.5,
    "check_valve": 3.0,
    "flange": 1.2,
    "reducer": 0.45,
    "grooved_coupling": 0.50,
}


def _nps_slug(nps: str) -> str:
    return nps.replace("-", "_").replace("/", "_")


def _pipe_family(
    into: dict,
    *,
    prefix: str,
    nps_table: dict[str, dict[str, float]],
    material_id: str,
    category: str,
    system: str,
    csi_pipe: str,
    csi_fit: str,
    name_prefix: str,
    ftypes: list[str],
    cost_scale: float = 1.0,
    PartType: type,
    BomLine: type,
) -> None:
    from llmbim_core.parts_catalog import nps_slug

    for nps, geom in nps_table.items():
        slug = nps_slug(nps)
        cost_m = geom["unit_cost_m"] * cost_scale
        pid = f"{prefix}-PIPE-{slug}"
        into[pid] = PartType(
            id=pid,
            name=f"{name_prefix} pipe {nps}\"",
            category=category,
            primary_material_id=material_id,
            csi_code=csi_pipe,
            unit_cost=cost_m,
            shape="cylinder",
            default_size_mm=[1000.0, geom["od_mm"], geom["od_mm"]],
            bom=[
                BomLine(
                    material_id=material_id,
                    qty=1.0,
                    unit="m",
                    mass_kg=geom["mass_kg_m"],
                    description=f"{name_prefix} {nps}\" per m",
                )
            ],
            specs={
                "system": system,
                "material": material_id,
                "nps": nps,
                "fitting_type": "pipe",
                "od_mm": geom["od_mm"],
                "mass_kg_m": geom["mass_kg_m"],
                "unit": "m",
                "csi_code": csi_pipe,
            },
        )
        for ftype in ftypes:
            code = _FTYPE_CODES[ftype]
            fid = f"{prefix}-{code}-{slug}"
            mult = _FTYPE_MULT.get(ftype, 0.5)
            fcost = round(cost_m * mult, 2)
            mass = round(geom["mass_kg_m"] * (0.12 if ftype != "pipe" else 1.0), 3)
            into[fid] = PartType(
                id=fid,
                name=f"{name_prefix} {_FTYPE_LABELS[ftype]} {nps}\"",
                category=category,
                primary_material_id=material_id,
                csi_code=csi_fit if ftype != "pipe" else csi_pipe,
                unit_cost=fcost,
                shape="box",
                default_size_mm=[geom["od_mm"] * 2] * 3,
                bom=[
                    BomLine(
                        material_id=material_id,
                        qty=1.0,
                        unit="ea",
                        mass_kg=mass,
                        description=f"{_FTYPE_LABELS[ftype]} {nps}\"",
                    )
                ],
                specs={
                    "system": system,
                    "material": material_id,
                    "nps": nps,
                    "fitting_type": ftype,
                    "angle_deg": 90 if ftype == "elbow_90" else (45 if ftype == "elbow_45" else None),
                    "od_mm": geom["od_mm"],
                    "unit": "ea",
                    "csi_code": csi_fit,
                },
            )


def register_fire_protection(into: dict, PartType: type, BomLine: type) -> None:
    """CSI 21 — sprinkler black steel + heads + devices."""
    ftypes = [
        "elbow_90",
        "elbow_45",
        "tee",
        "coupling",
        "cap",
        "grooved_coupling",
        "gate_valve",
        "check_valve",
        "reducer",
        "pipe",
    ]
    # pipe family already adds "pipe" as ftype in loop — pass without pipe in ftypes for fittings only
    fit_only = [f for f in ftypes if f != "pipe"]
    _pipe_family(
        into,
        prefix="PT-FP",
        nps_table={k: v for k, v in STEEL_NPS.items() if k in ("1", "1-1/4", "1-1/2", "2", "2-1/2", "3", "4", "6", "8")},
        material_id="black_steel",
        category="fire_protection",
        system="fire",
        csi_pipe="21 13 13",
        csi_fit="21 13 13",
        name_prefix="Sch40 black steel FP",
        ftypes=fit_only,
        cost_scale=1.1,
        PartType=PartType,
        BomLine=BomLine,
    )
    # Sprinkler heads
    for kind, k, temp, cost in (
        ("pendent", "5.6", "155F", 18.0),
        ("upright", "5.6", "155F", 18.0),
        ("sidewall", "5.6", "155F", 22.0),
        ("pendent", "8.0", "200F", 28.0),
        ("concealed", "5.6", "155F", 45.0),
        ("ESFR", "14.0", "165F", 95.0),
    ):
        slug = f"{kind}_{k.replace('.', '_')}_{temp}".upper()
        pid = f"PT-FP-HEAD-{slug}"
        into[pid] = PartType(
            id=pid,
            name=f"Sprinkler head {kind} K{k} {temp}",
            category="fire_protection",
            primary_material_id="brass",
            csi_code="21 13 13",
            unit_cost=cost,
            default_size_mm=[50, 50, 80],
            specs={
                "system": "fire",
                "fitting_type": "sprinkler_head",
                "head_type": kind,
                "k_factor": k,
                "temp_rating": temp,
                "unit": "ea",
            },
        )
    # Devices
    devices = [
        ("PT-FP-OSY-4", "OS&Y gate valve 4\"", "gate_valve", "4", 850.0, "21 12 00"),
        ("PT-FP-BFV-4", "Butterfly valve 4\" wafer", "butterfly_valve", "4", 420.0, "21 12 00"),
        ("PT-FP-ALARM-CHK", "Alarm check valve 4\"", "alarm_check", "4", 2200.0, "21 12 00"),
        ("PT-FP-FDC-SIAMESE", "FDC siamese inlet", "fdc", "", 1800.0, "21 12 00"),
        ("PT-FP-HOSE-CAB", "Fire hose cabinet 1.5\"", "hose_cabinet", "1-1/2", 650.0, "21 12 00"),
        ("PT-FP-EXT-ABC-10", "Fire extinguisher ABC 10 lb", "extinguisher", "", 85.0, "10 44 00"),
        ("PT-FP-EXT-CO2-15", "Fire extinguisher CO2 15 lb", "extinguisher", "", 140.0, "10 44 00"),
        ("PT-FP-STANDPIPE-2.5", "Standpipe outlet 2.5\"", "standpipe_outlet", "2-1/2", 320.0, "21 12 00"),
    ]
    for pid, name, ftype, nps, cost, csi in devices:
        into[pid] = PartType(
            id=pid,
            name=name,
            category="fire_protection",
            primary_material_id="black_steel" if "EXT" not in pid else "steel_A36",
            csi_code=csi,
            unit_cost=cost,
            specs={
                "system": "fire",
                "fitting_type": ftype,
                "nps": nps or None,
                "unit": "ea",
            },
        )


def register_process_piping(into: dict, PartType: type, BomLine: type) -> None:
    """CSI 40 — SS316L process pipe + fittings + instruments."""
    fit_only = [
        "elbow_90",
        "elbow_45",
        "tee",
        "coupling",
        "cap",
        "union",
        "ball_valve",
        "flange",
        "reducer",
        "gate_valve",
        "check_valve",
    ]
    nps = {k: {**v, "unit_cost_m": v["unit_cost_m"] * 6.5, "mass_kg_m": v["mass_kg_m"] * 1.02}
           for k, v in STEEL_NPS.items() if k in ("1/2", "3/4", "1", "1-1/2", "2", "3", "4", "6")}
    _pipe_family(
        into,
        prefix="PT-SS",
        nps_table=nps,
        material_id="ss316L",
        category="process_piping",
        system="process",
        csi_pipe="40 05 13",
        csi_fit="40 05 13",
        name_prefix="SS316L Sch40 process",
        ftypes=fit_only,
        cost_scale=1.0,
        PartType=PartType,
        BomLine=BomLine,
    )
    extras = [
        ("PT-SS-GASKET-2", "Spiral-wound gasket 2\"", "gasket", "2", 28.0, "ss316L"),
        ("PT-SS-GASKET-4", "Spiral-wound gasket 4\"", "gasket", "4", 48.0, "ss316L"),
        ("PT-SS-DIAPH-1", "Diaphragm valve 1\" PTFE", "diaphragm_valve", "1", 480.0, "ss316L"),
        ("PT-SS-SAMPLE-1_2", "Sample valve 1/2\"", "sample_valve", "1/2", 320.0, "ss316L"),
        ("PT-SS-PRESS-GAUGE", "Pressure gauge 0-150 psi", "instrument", "", 95.0, "ss316L"),
        ("PT-SS-TEMP-WELL", "Thermowell 1/2\" NPT", "instrument", "1/2", 75.0, "ss316L"),
        ("PT-SS-STRAINER-2", "Y-strainer 2\"", "strainer", "2", 280.0, "ss316L"),
    ]
    for pid, name, ftype, nps_v, cost, mat in extras:
        into[pid] = PartType(
            id=pid,
            name=name,
            category="process_piping",
            primary_material_id=mat,
            csi_code="40 05 13",
            unit_cost=cost,
            specs={"system": "process", "fitting_type": ftype, "nps": nps_v or None, "unit": "ea"},
        )


def register_framing(into: dict, PartType: type, BomLine: type) -> None:
    """CSI 06 / 09 — wood + light-gauge framing."""
    wood = [
        ("PT-WD-STUD-2X4", "Wood stud 2×4 SPF", "stud", "2x4", 38, 89, 3.2, "lumber_SPF", "06 10 00"),
        ("PT-WD-STUD-2X6", "Wood stud 2×6 SPF", "stud", "2x6", 38, 140, 4.8, "lumber_SPF", "06 10 00"),
        ("PT-WD-PLT-2X4", "Wood plate 2×4", "plate", "2x4", 38, 89, 3.2, "lumber_SPF", "06 10 00"),
        ("PT-WD-PLT-2X6", "Wood plate 2×6", "plate", "2x6", 38, 140, 4.8, "lumber_SPF", "06 10 00"),
        ("PT-WD-BLK-2X4", "Blocking 2×4", "blocking", "2x4", 38, 89, 2.5, "lumber_SPF", "06 10 00"),
        ("PT-WD-PLY-12", "Plywood sheathing 12 mm", "sheathing", "12mm", 1220, 2440, 28.0, "plywood", "06 16 00"),
        ("PT-WD-OSB-11", "OSB sheathing 11 mm", "sheathing", "11mm", 1220, 2440, 22.0, "osb", "06 16 00"),
        ("PT-WD-LEDGER-2X10", "Ledger 2×10", "ledger", "2x10", 38, 235, 8.5, "lumber_SPF", "06 10 00"),
    ]
    for pid, name, ftype, size, t, d, cost, mat, csi in wood:
        into[pid] = PartType(
            id=pid,
            name=name,
            category="framing",
            primary_material_id=mat,
            csi_code=csi,
            unit_cost=cost,
            default_size_mm=[2440, t, d] if "PLY" not in pid and "OSB" not in pid else [t, d, 12],
            bom=[BomLine(material_id=mat, qty=1.0, unit="ea" if "PLY" in pid or "OSB" in pid else "m")],
            specs={
                "system": "framing",
                "fitting_type": ftype,
                "size": size,
                "material": mat,
                "unit": "ea" if ftype == "sheathing" else "m",
            },
        )
    metal = [
        ("PT-MS-STUD-362-20", "Metal stud 3-5/8\" 20 ga", "stud", "3-5/8", 92, 2.8, "metal_stud", "09 22 16"),
        ("PT-MS-STUD-600-20", "Metal stud 6\" 20 ga", "stud", "6", 152, 4.2, "metal_stud", "09 22 16"),
        ("PT-MS-TRK-362", "Metal track 3-5/8\"", "track", "3-5/8", 92, 2.5, "metal_stud", "09 22 16"),
        ("PT-MS-TRK-600", "Metal track 6\"", "track", "6", 152, 3.8, "metal_stud", "09 22 16"),
        ("PT-MS-FURR-78", "Hat channel furring 7/8\"", "furring", "7/8", 22, 1.8, "metal_stud", "09 22 16"),
        ("PT-MS-CLIP", "Deflection clip", "clip", "", 0, 2.5, "steel_A36", "09 22 16"),
    ]
    for pid, name, ftype, size, depth, cost, mat, csi in metal:
        into[pid] = PartType(
            id=pid,
            name=name,
            category="framing",
            primary_material_id=mat,
            csi_code=csi,
            unit_cost=cost,
            default_size_mm=[3000, depth, 35] if depth else [50, 50, 50],
            specs={
                "system": "framing",
                "fitting_type": ftype,
                "size": size or None,
                "material": mat,
                "unit": "ea" if ftype == "clip" else "m",
            },
        )


def register_structural_steel(into: dict, PartType: type, BomLine: type) -> None:
    """CSI 05 12 — wide flange, HSS, channel, angle, plate, bolts."""
    # section, kg/m, cost $/m (fabricated rough)
    wf = [
        ("W8x18", 26.8, 85),
        ("W8x31", 46.1, 140),
        ("W10x22", 32.7, 100),
        ("W10x33", 49.1, 150),
        ("W12x26", 38.7, 120),
        ("W12x50", 74.4, 220),
        ("W14x22", 32.7, 105),
        ("W14x82", 122.0, 380),
        ("W16x26", 38.7, 125),
        ("W18x35", 52.1, 165),
        ("W21x44", 65.5, 210),
        ("W24x55", 81.8, 265),
        ("W27x84", 125.0, 400),
        ("W30x90", 134.0, 430),
    ]
    for sec, kg_m, cost in wf:
        slug = sec.replace("×", "x").replace(" ", "")
        pid = f"PT-STL-{slug}"
        into[pid] = PartType(
            id=pid,
            name=f"Wide flange {sec}",
            category="structural_steel",
            primary_material_id="steel_A992",
            csi_code="05 12 00",
            unit_cost=cost,
            bom=[BomLine(material_id="steel_A992", qty=kg_m, unit="kg", description="per meter")],
            specs={
                "system": "structural_steel",
                "fitting_type": "wide_flange",
                "section": sec,
                "weight_kg_m": kg_m,
                "unit": "m",
            },
        )
    hss = [
        ("HSS4x4x1/4", 22.7, 95),
        ("HSS6x6x3/8", 51.2, 180),
        ("HSS8x8x1/2", 89.3, 310),
        ("HSS10x6x3/8", 58.0, 210),
    ]
    for sec, kg_m, cost in hss:
        pid = f"PT-STL-{sec.replace('/', '_')}"
        into[pid] = PartType(
            id=pid,
            name=f"HSS {sec}",
            category="structural_steel",
            primary_material_id="steel_A500",
            csi_code="05 12 00",
            unit_cost=cost,
            bom=[BomLine(material_id="steel_A500", qty=kg_m, unit="kg")],
            specs={
                "system": "structural_steel",
                "fitting_type": "hss",
                "section": sec,
                "weight_kg_m": kg_m,
                "unit": "m",
            },
        )
    misc = [
        ("PT-STL-C10x15.3", "Channel C10×15.3", "channel", "C10x15.3", 22.8, 75, "steel_A36"),
        ("PT-STL-C12x20.7", "Channel C12×20.7", "channel", "C12x20.7", 30.8, 100, "steel_A36"),
        ("PT-STL-L4x4x3_8", "Angle L4×4×3/8", "angle", "L4x4x3/8", 14.6, 48, "steel_A36"),
        ("PT-STL-L6x4x1_2", "Angle L6×4×1/2", "angle", "L6x4x1/2", 24.1, 78, "steel_A36"),
        ("PT-STL-PL-1_2", "Plate 1/2\" A36 (per m2)", "plate", "1/2", 98.0, 180, "steel_A36"),
        ("PT-STL-PL-1", "Plate 1\" A36 (per m2)", "plate", "1", 196.0, 340, "steel_A36"),
        ("PT-STL-BASE-PL-20", "Base plate 500×500×20", "base_plate", "20mm", 39.0, 120, "steel_A36"),
        ("PT-STL-BOLT-A325-3_4", "HS bolt A325 3/4\" w/ nuts", "bolt", "3/4", 0.25, 4.5, "steel_A325"),
        ("PT-STL-BOLT-A490-1", "HS bolt A490 1\" w/ nuts", "bolt", "1", 0.45, 8.0, "steel_A490"),
        ("PT-STL-SHEAR-STUD-3_4", "Shear stud 3/4×4\"", "shear_stud", "3/4", 0.15, 2.2, "steel_A36"),
        ("PT-STL-DECK-3VLI", "Steel deck 3\" VL composite", "deck", "3VLI", 12.0, 45, "steel_A653"),
    ]
    for pid, name, ftype, size, mass, cost, mat in misc:
        unit = "ea" if ftype in ("bolt", "shear_stud", "base_plate") else ("m2" if ftype in ("plate", "deck") else "m")
        into[pid] = PartType(
            id=pid,
            name=name,
            category="structural_steel",
            primary_material_id=mat,
            csi_code="05 12 00" if ftype != "deck" else "05 31 00",
            unit_cost=cost,
            bom=[BomLine(material_id=mat, qty=mass, unit="kg" if unit != "ea" else "ea", mass_kg=mass if unit == "ea" else None)],
            specs={
                "system": "structural_steel",
                "fitting_type": ftype,
                "section": size,
                "size": size,
                "weight_kg_m": mass if unit == "m" else None,
                "unit": unit,
            },
        )


def register_rebar(into: dict, PartType: type, BomLine: type) -> None:
    """CSI 03 20 — reinforcing steel bars + mesh."""
    # bar #, diameter mm, kg/m, $/m
    bars = [
        ("3", 9.5, 0.560, 1.4),
        ("4", 12.7, 0.994, 2.2),
        ("5", 15.9, 1.552, 3.2),
        ("6", 19.1, 2.235, 4.5),
        ("7", 22.2, 3.042, 6.0),
        ("8", 25.4, 3.973, 7.8),
        ("9", 28.7, 5.060, 9.8),
        ("10", 32.3, 6.404, 12.2),
        ("11", 35.8, 7.907, 14.8),
    ]
    for num, dia, kg_m, cost in bars:
        pid = f"PT-RBR-BAR-{num}"
        into[pid] = PartType(
            id=pid,
            name=f"Rebar #{num} Grade 60",
            category="rebar",
            primary_material_id="rebar_G60",
            csi_code="03 20 00",
            unit_cost=cost,
            shape="cylinder",
            default_size_mm=[1000, dia, dia],
            bom=[BomLine(material_id="rebar_G60", qty=kg_m, unit="kg", description="per meter")],
            specs={
                "system": "rebar",
                "fitting_type": "rebar",
                "bar_size": num,
                "bar_no": num,
                "diameter_mm": dia,
                "weight_kg_m": kg_m,
                "grade": "60",
                "unit": "m",
            },
        )
    mesh = [
        ("PT-RBR-WWF-6X6-W1_4", "WWF 6×6 W1.4/W1.4", "6x6-W1.4", 1.5, 4.5),
        ("PT-RBR-WWF-6X6-W2_9", "WWF 6×6 W2.9/W2.9", "6x6-W2.9", 2.9, 7.5),
        ("PT-RBR-WWF-4X4-W4_0", "WWF 4×4 W4.0/W4.0", "4x4-W4.0", 4.0, 11.0),
    ]
    for pid, name, size, kg_m2, cost in mesh:
        into[pid] = PartType(
            id=pid,
            name=name,
            category="rebar",
            primary_material_id="rebar_G60",
            csi_code="03 20 00",
            unit_cost=cost,
            bom=[BomLine(material_id="rebar_G60", qty=kg_m2, unit="kg")],
            specs={
                "system": "rebar",
                "fitting_type": "wwf",
                "size": size,
                "weight_kg_m2": kg_m2,
                "unit": "m2",
            },
        )
    accessories = [
        ("PT-RBR-DOWEL-1X18", "Smooth dowel 1\"×18\"", "dowel", 8.0),
        ("PT-RBR-CHAIR-3", "Bar chair 3\"", "chair", 0.35),
        ("PT-RBR-TIE-WIRE", "Tie wire 16 ga (per kg)", "tie_wire", 4.5),
        ("PT-RBR-COUPLER-8", "Mechanical coupler #8", "coupler", 18.0),
        ("PT-RBR-EPOXY-5", "Epoxy-coated rebar #5 (prem.)", "rebar_epoxy", 4.8),
    ]
    for pid, name, ftype, cost in accessories:
        into[pid] = PartType(
            id=pid,
            name=name,
            category="rebar",
            primary_material_id="rebar_G60" if "EPOXY" not in pid else "rebar_epoxy",
            csi_code="03 20 00",
            unit_cost=cost,
            specs={"system": "rebar", "fitting_type": ftype, "unit": "ea" if ftype != "tie_wire" else "kg"},
        )


def register_fixtures(into: dict, PartType: type, BomLine: type) -> None:
    """CSI 22 40 / 10 28 — toilets, accessories, dispensers, hoses."""
    fixtures = [
        # toilets & fixtures
        ("PT-PLB-WC-FLOOR", "Water closet floor-mount elongated", "toilet", 420.0, "vitreous_china", "22 42 13", [700, 400, 750]),
        ("PT-PLB-WC-WALL", "Water closet wall-mount elongated", "toilet", 580.0, "vitreous_china", "22 42 13", [600, 400, 550]),
        ("PT-PLB-WC-ADA", "Water closet ADA floor-mount", "toilet", 520.0, "vitreous_china", "22 42 13", [750, 420, 800]),
        ("PT-PLB-URINAL-WALL", "Urinal wall-hang vitreous", "urinal", 380.0, "vitreous_china", "22 42 19", [400, 350, 700]),
        ("PT-PLB-LAV-WALL", "Lavatory wall-mount 20×18", "lavatory", 280.0, "vitreous_china", "22 42 16", [500, 450, 200]),
        ("PT-PLB-LAV-COUNT", "Lavatory countertop oval", "lavatory", 220.0, "vitreous_china", "22 42 16", [480, 400, 180]),
        ("PT-PLB-SINK-SS-1", "SS kitchen sink single bowl", "sink", 350.0, "ss304", "22 42 16", [600, 500, 200]),
        ("PT-PLB-SINK-SS-2", "SS kitchen sink double bowl", "sink", 480.0, "ss304", "22 42 16", [800, 500, 200]),
        ("PT-PLB-MOP-SINK", "Mop service basin 24×24", "mop_sink", 420.0, "terrazzo", "22 42 16", [600, 600, 300]),
        ("PT-PLB-FD-2", "Floor drain 2\" nickel bronze", "floor_drain", 95.0, "cast_iron", "22 13 00", [150, 150, 100]),
        ("PT-PLB-FD-3", "Floor drain 3\"", "floor_drain", 140.0, "cast_iron", "22 13 00", [180, 180, 120]),
        ("PT-PLB-FD-4", "Floor drain 4\"", "floor_drain", 180.0, "cast_iron", "22 13 00", [200, 200, 140]),
        ("PT-PLB-WH-40G", "Water heater 40 gal electric", "water_heater", 650.0, "steel_A36", "22 33 00", [500, 500, 1400]),
        ("PT-PLB-WH-50G", "Water heater 50 gal gas", "water_heater", 780.0, "steel_A36", "22 34 00", [550, 550, 1500]),
        ("PT-PLB-EWC", "Electric water cooler dual", "water_cooler", 1200.0, "ss304", "22 47 00", [450, 400, 1100]),
        # supplies & hoses
        ("PT-PLB-HOSE-WC-3_8", "Toilet supply hose 3/8\"×12\"", "toilet_hose", 8.5, "ss304", "22 11 19", [300, 15, 15]),
        ("PT-PLB-HOSE-WC-BRAID", "Toilet braided supply 3/8\"×20\"", "toilet_hose", 12.0, "ss304", "22 11 19", [500, 15, 15]),
        ("PT-PLB-ANGLE-STOP-3_8", "Angle stop 3/8\" chrome", "angle_stop", 14.0, "brass", "22 11 19", [50, 40, 60]),
        ("PT-PLB-P-TRAP-1_1_4", "P-trap 1-1/4\" chrome", "p_trap", 18.0, "brass", "22 13 00", [150, 100, 80]),
        ("PT-PLB-P-TRAP-1_1_2", "P-trap 1-1/2\" chrome", "p_trap", 22.0, "brass", "22 13 00", [160, 110, 90]),
        ("PT-PLB-FLUSH-VALVE", "Flush valve 1.28 gpf", "flush_valve", 185.0, "brass", "22 11 19", [200, 100, 250]),
        ("PT-PLB-FLUSH-SENSOR", "Sensor flush valve", "flush_valve", 420.0, "brass", "22 11 19", [200, 100, 280]),
        ("PT-PLB-FAUCET-LAV", "Lavatory faucet 0.5 gpm", "faucet", 95.0, "brass", "22 42 16", [150, 50, 150]),
        ("PT-PLB-FAUCET-SENSOR", "Sensor lavatory faucet", "faucet", 280.0, "brass", "22 42 16", [150, 50, 180]),
        # toilet accessories / dispensers CSI 10 28
        ("PT-ACC-TP-SINGLE", "Toilet paper dispenser single roll", "tp_dispenser", 28.0, "ss304", "10 28 13", [150, 130, 50]),
        ("PT-ACC-TP-DOUBLE", "Toilet paper dispenser dual roll", "tp_dispenser", 42.0, "ss304", "10 28 13", [280, 130, 50]),
        ("PT-ACC-TP-JUMBO", "Toilet paper jumbo roll dispenser", "tp_dispenser", 65.0, "ss304", "10 28 13", [300, 300, 120]),
        ("PT-ACC-STSEAT", "Toilet seat cover dispenser", "seat_cover_dispenser", 55.0, "ss304", "10 28 13", [400, 80, 300]),
        ("PT-ACC-SOAP-MAN", "Soap dispenser manual 800 ml", "soap_dispenser", 35.0, "ss304", "10 28 13", [100, 80, 250]),
        ("PT-ACC-SOAP-AUTO", "Soap dispenser automatic", "soap_dispenser", 95.0, "ss304", "10 28 13", [120, 100, 280]),
        ("PT-ACC-PTWEL-C", "Paper towel dispenser C-fold", "towel_dispenser", 48.0, "ss304", "10 28 13", [300, 120, 350]),
        ("PT-ACC-PTWEL-R", "Paper towel roll dispenser", "towel_dispenser", 72.0, "ss304", "10 28 13", [320, 220, 350]),
        ("PT-ACC-HAND-DRY", "Hand dryer high-speed", "hand_dryer", 450.0, "ss304", "10 28 13", [280, 170, 320]),
        ("PT-ACC-MIRROR-18X36", "Mirror 18×36 stainless frame", "mirror", 85.0, "ss304", "10 28 13", [450, 20, 900]),
        ("PT-ACC-MIRROR-24X36", "Mirror 24×36 stainless frame", "mirror", 110.0, "ss304", "10 28 13", [600, 20, 900]),
        ("PT-ACC-GRAB-36", "Grab bar 36\" SS", "grab_bar", 55.0, "ss304", "10 28 13", [900, 40, 80]),
        ("PT-ACC-GRAB-42", "Grab bar 42\" SS", "grab_bar", 62.0, "ss304", "10 28 13", [1050, 40, 80]),
        ("PT-ACC-GRAB-18", "Grab bar 18\" SS vertical", "grab_bar", 38.0, "ss304", "10 28 13", [450, 40, 80]),
        ("PT-ACC-NAPKIN", "Sanitary napkin disposal", "napkin_disposal", 75.0, "ss304", "10 28 13", [200, 120, 350]),
        ("PT-ACC-HOOK", "Robe / coat hook SS", "hook", 12.0, "ss304", "10 28 13", [50, 40, 80]),
        ("PT-ACC-SHELF-16", "Utility shelf 16\" SS", "shelf", 45.0, "ss304", "10 28 13", [400, 120, 50]),
        ("PT-ACC-BABY-CHG", "Baby changing station", "changing_station", 380.0, "hdpe", "10 28 13", [900, 100, 550]),
        ("PT-ACC-WASTE-12", "Waste receptacle 12 gal SS", "waste", 120.0, "ss304", "10 28 13", [350, 350, 600]),
    ]
    for pid, name, ftype, cost, mat, csi, size in fixtures:
        into[pid] = PartType(
            id=pid,
            name=name,
            category="fixture" if pid.startswith("PT-PLB") else "accessory",
            primary_material_id=mat,
            csi_code=csi,
            unit_cost=cost,
            default_size_mm=size,
            specs={
                "system": "plumbing_fixture" if pid.startswith("PT-PLB") else "toilet_accessory",
                "fitting_type": ftype,
                "unit": "ea",
                "csi_code": csi,
            },
        )


def register_hvac_electrical_misc(into: dict, PartType: type, BomLine: type) -> None:
    """Light CSI 23 / 26 catalog so divisions aren't empty."""
    items = [
        ("PT-HVAC-DIFF-24", "Ceiling diffuser 24×24", "diffuser", 85.0, "aluminum_6061", "23 37 00", "hvac", [600, 600, 100]),
        ("PT-HVAC-GRILLE-12", "Return grille 12×12", "grille", 45.0, "aluminum_6061", "23 37 00", "hvac", [300, 300, 50]),
        ("PT-HVAC-VAV-8", "VAV box 8\" inlet", "vav", 1200.0, "steel_A36", "23 36 00", "hvac", [800, 500, 400]),
        ("PT-HVAC-FDAMPER-24", "Fire damper 24×12", "fire_damper", 450.0, "galv_steel", "23 33 00", "hvac", [600, 300, 150]),
        ("PT-HVAC-SDAMPER-12", "Smoke damper 12×12", "smoke_damper", 380.0, "galv_steel", "23 33 00", "hvac", [300, 300, 150]),
        ("PT-HVAC-DUCT-RECT", "Rect duct Galv (per m2)", "duct", 55.0, "galv_steel", "23 31 00", "hvac", None),
        ("PT-HVAC-FLEX-8", "Flex duct 8\" (per m)", "flex_duct", 18.0, "galv_steel", "23 31 00", "hvac", None),
        ("PT-ELEC-PANEL-42", "Panelboard 42-ckt 208Y/120", "panel", 2800.0, "steel_A36", "26 24 16", "electrical", [600, 150, 1200]),
        ("PT-ELEC-LT-2X4", "LED troffer 2×4", "luminaire", 95.0, "aluminum_6061", "26 51 00", "electrical", [1200, 600, 100]),
        ("PT-ELEC-REC-DUP", "Duplex receptacle 20A", "receptacle", 12.0, "generic", "26 27 26", "electrical", [100, 50, 50]),
        ("PT-ELEC-SW-SP", "Single-pole switch", "switch", 8.0, "generic", "26 27 26", "electrical", [80, 40, 100]),
        ("PT-ELEC-CONDUIT-3_4", "EMT conduit 3/4\" (per m)", "conduit", 4.5, "steel_A36", "26 05 33", "electrical", None),
        ("PT-ELEC-WIRE-12", "THHN #12 Cu (per m)", "wire", 1.2, "copper_C12200", "26 05 19", "electrical", None),
    ]
    for row in items:
        pid, name, ftype, cost, mat, csi, system = row[:7]
        size = row[7] if len(row) > 7 else None
        into[pid] = PartType(
            id=pid,
            name=name,
            category=system,
            primary_material_id=mat,
            csi_code=csi,
            unit_cost=cost,
            default_size_mm=size,
            specs={"system": system, "fitting_type": ftype, "unit": "ea", "csi_code": csi},
        )


def register_all_systems(into: dict) -> None:
    from llmbim_core.parts_catalog import BomLine, PartType

    register_fire_protection(into, PartType, BomLine)
    register_process_piping(into, PartType, BomLine)
    register_framing(into, PartType, BomLine)
    register_structural_steel(into, PartType, BomLine)
    register_rebar(into, PartType, BomLine)
    register_fixtures(into, PartType, BomLine)
    register_hvac_electrical_misc(into, PartType, BomLine)
