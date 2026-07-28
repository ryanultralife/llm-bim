"""INTEC design basis — SSOT for the llm-bim construction pack (MB-INT-CAD-001).

Transcribed from:
  - Eigen/cad/fusion/intec_fusion_params.json  (params_version 2026-06-13.site5)
  - Eigen/docs/INTEC_Construction_Drawing_Register.md  (128-sheet spine)
  - Downloads/INTEC_Construction_Set.pdf  (reference CD graphics)

UNITS: metres in this module (project record is metric). Downstream converts to mm.
COORDS: origin at SW corner of main building; +x East (length), +y North (width).

Honesty: [ENGINEERING ESTIMATE] — design-basis class. Never invent geometry here
without a citation; open questions stay open.
"""

from __future__ import annotations

from typing import Any

DOC = "MB-INT-CAD-001"
PARAMS_VERSION = "2026-06-13.site5"
ENGINE_SHA = "7778d68c375e271a"
PROJECT_NAME = "INTEC ATR-SNF Separation Facility"
OWNER = "Mechanical Battery LLC"
SITE = "Idaho Nuclear Technology and Engineering Center (INTEC), INL"
HONESTY = (
    "[ENGINEERING ESTIMATE] — design-basis class; arrangement per INT-GA-001. "
    "Final CD production + PE stamping by the A-E firm at DS-2."
)


# --------------------------------------------------------------------------- #
# scalars                                                                      #
# --------------------------------------------------------------------------- #
def build_scalars() -> dict[str, Any]:
    """Facility scalars [fusion params 2026-06-13.site5]."""
    return {
        "bldg_W": 35.0,  # N-S m
        "bldg_L": 48.0,  # E-W m
        "bldg_H": 12.0,
        "wall_t": 0.3,
        "roof_t": 0.3,
        "slab_t": 1.0,
        "tun_W": 19.3,
        "tun_L": 36.5,
        "tun_H": 9.0,
        "shield_t": 1.5,  # bioshield concrete thickness m
        "liner_t_mm": 6.0,
        "spine_W": 4.0,
        "cell_W": 3.0,
        "cell_L": 3.0,
        "n_cells": 8,
        "n_active_cells": 6,
        "crane_clear_H": 9.0,
        "vessel_OD": 0.61,  # Size-B production [MB-INTEC-FAB-001] ~Ø610
        "vessel_LEN": 1.20,
        "vessel_cl_z": 1.2,
        "stack_R": 0.6,
        "stack_H_above_roof": 9.0,
        "annex_D": 11.0,  # south annex depth (llm-bim / examples use 11)
        "annex_L": 31.0,  # receipt annex length (x from ~1 m)
        "annex_H": 10.0,
        "annex_x0": 1.0,
        "roof_shield_t": 1.0,
        "basis_tunnel_concrete_m3": 2910.6,
        "basis_bldg_footprint_m2": 1713.0,
        "col_section": "W14x90",
        "beam_section": "W18x50",
        "crane_runway": "W24x84",
        "grid_spacing_m": 8.0,  # structural bay ~8 m E-W (PDF S-002)
        "footing_sq_m": 1.4,
        "service_kv": 13.8,
        "service_mw": 10.25,
        "site_commit_ac": 2.0,
    }


# --------------------------------------------------------------------------- #
# placements — station boxes (same ids as fusion bridge)                       #
# --------------------------------------------------------------------------- #
def build_placements() -> list[dict[str, Any]]:
    """Station envelopes [fusion params placements]."""
    return [
        {"id": "TUNNEL", "name": "Hot cell tunnel", "kind": "tunnel",
         "x": 5.5, "y": 2.5, "w": 36.5, "d": 19.3, "h": 9.0,
         "shielded": True, "sp": "SP-2"},
        {"id": "SPINE", "name": "Robotic spine", "kind": "corridor",
         "x": 5.5, "y": 10.15, "w": 36.5, "d": 4.0, "h": 9.0,
         "shielded": False, "sp": "SP-5"},
        {"id": "EBEAM", "name": "E-beam hub", "kind": "ebeam",
         "x": 5.5, "y": 4.0, "w": 7.0, "d": 16.3, "h": 9.0,
         "shielded": True, "sp": "SP-6"},
        {"id": "UNCASK", "name": "Cask unloading", "kind": "uncask",
         "x": 1.0, "y": -10.0, "w": 8.0, "d": 10.0, "h": 10.0,
         "shielded": True, "sp": "SP-3"},
        {"id": "CELL-1", "name": "Sep cell 1 active", "kind": "cell",
         "x": 13.0, "y": 16.475, "w": 3.0, "d": 3.0, "h": 9.0,
         "shielded": True, "sp": "SP-6", "vessel": True},
        {"id": "CELL-2", "name": "Sep cell 2 active", "kind": "cell",
         "x": 20.0, "y": 16.475, "w": 3.0, "d": 3.0, "h": 9.0,
         "shielded": True, "sp": "SP-6", "vessel": True},
        {"id": "CELL-3", "name": "Sep cell 3 active", "kind": "cell",
         "x": 27.0, "y": 16.475, "w": 3.0, "d": 3.0, "h": 9.0,
         "shielded": True, "sp": "SP-6", "vessel": True},
        {"id": "CELL-4", "name": "Sep cell 4 reserved", "kind": "cell",
         "x": 34.0, "y": 16.475, "w": 3.0, "d": 3.0, "h": 9.0,
         "shielded": True, "sp": "SP-6"},
        {"id": "CELL-5", "name": "Sep cell 5 active", "kind": "cell",
         "x": 13.0, "y": 4.825, "w": 3.0, "d": 3.0, "h": 9.0,
         "shielded": True, "sp": "SP-6", "vessel": True},
        {"id": "CELL-6", "name": "Sep cell 6 active", "kind": "cell",
         "x": 20.0, "y": 4.825, "w": 3.0, "d": 3.0, "h": 9.0,
         "shielded": True, "sp": "SP-6", "vessel": True},
        {"id": "CELL-7", "name": "Sep cell 7 active", "kind": "cell",
         "x": 27.0, "y": 4.825, "w": 3.0, "d": 3.0, "h": 9.0,
         "shielded": True, "sp": "SP-6", "vessel": True},
        {"id": "CELL-8", "name": "Sep cell 8 reserved", "kind": "cell",
         "x": 34.0, "y": 4.825, "w": 3.0, "d": 3.0, "h": 9.0,
         "shielded": True, "sp": "SP-6"},
        {"id": "DOWNBLEND", "name": "Down-blend", "kind": "box",
         "x": 1.0, "y": 26.0, "w": 13.0, "d": 8.0, "h": 8.0,
         "shielded": True, "sp": "SP-6"},
        {"id": "ROBMAINT", "name": "Robot maint", "kind": "box",
         "x": 16.0, "y": 26.0, "w": 12.0, "d": 8.0, "h": 6.0,
         "shielded": True, "sp": "SP-7", "occupied": True},
        {"id": "WASTE", "name": "Waste handling", "kind": "box",
         "x": 30.0, "y": 26.0, "w": 13.0, "d": 8.0, "h": 9.0,
         "shielded": True, "sp": "SP-3"},
        {"id": "DECLAD", "name": "Declad / shear", "kind": "box",
         "x": 10.0, "y": -10.0, "w": 8.0, "d": 10.0, "h": 10.0,
         "shielded": True, "sp": "SP-3"},
        {"id": "CASKBAY", "name": "Cask receipt", "kind": "box",
         "x": 20.0, "y": -10.0, "w": 9.0, "d": 10.0, "h": 10.0,
         "shielded": False, "sp": "SP-4"},
        {"id": "CASKING", "name": "Product casking", "kind": "box",
         "x": 31.0, "y": -10.0, "w": 14.0, "d": 10.0, "h": 10.0,
         "shielded": True, "sp": "SP-4"},
        {"id": "STACK", "name": "Off-gas stack", "kind": "stack",
         "x": 18.0, "y": 32.0, "w": 1.2, "d": 1.2, "h": 21.0,
         "shielded": False, "sp": "SP-8"},
        {"id": "CONTROL", "name": "Control room", "kind": "box",
         "x": 44.0, "y": 2.5, "w": 3.8, "d": 9.5, "h": 4.5,
         "shielded": False, "sp": "SP-9", "occupied": True},
        {"id": "DECON", "name": "Personnel decon", "kind": "box",
         "x": 44.0, "y": 13.0, "w": 3.8, "d": 6.0, "h": 4.5,
         "shielded": False, "sp": "SP-7", "occupied": True},
        {"id": "HP", "name": "Health physics", "kind": "box",
         "x": 44.0, "y": 20.0, "w": 3.8, "d": 6.0, "h": 4.5,
         "shielded": False, "sp": "SP-7", "occupied": True},
        {"id": "MCA", "name": "MCA", "kind": "box",
         "x": 44.0, "y": 27.0, "w": 3.8, "d": 7.0, "h": 4.5,
         "shielded": False, "sp": "SP-10", "occupied": True},
    ]


def eq_stations() -> list[tuple[str, str]]:
    """EQ-001..EQ-016 station list (equipment arrangement sheets)."""
    return [
        ("TUNNEL", "hall crane + vapor manifold"),
        ("SPINE", "transfer rails, gantry robots, bogie"),
        ("EBEAM", "hearth, e-guns, cryopanels, feed airlock"),
        ("UNCASK", "docking collar, grapple, staging rack, lid tooling"),
        ("DECLAD", "shear cartridge, magazine, hull bin"),
        ("CELL", "vessel, RMF drive, ICRH, collectors, vacuum, gate pair (×8)"),
        ("DOWNBLEND", "glovebox lines, melt furnace, DU feeder, scale"),
        ("ROBMAINT", "repair benches, decon pit, tool crib, jib"),
        ("WASTE", "packaging turret, conveyor, staging, lid welder, assay"),
        ("CASKBAY", "transfer trolley, laydown, portal monitors"),
        ("CASKING", "cask stands, lidding, leak test, scale, decon ring"),
        ("STACK", "CAM + isokinetic sampling appurtenances"),
        ("CONTROL", "console + workstation rows"),
        ("DECON", "shower/sink set, frisker portal"),
        ("HP", "Pb count cave, fume hood"),
        ("MCA", "NDA bench, records vault"),
    ]


# --------------------------------------------------------------------------- #
# construction sequence (SP-1..SP-10) — from INT-CSQ-001                       #
# --------------------------------------------------------------------------- #
def construction_phases() -> list[dict[str, Any]]:
    """Week bars + cost bands [ENGINEERING ESTIMATE / Class 4-5]."""
    return [
        {"id": "SP-1", "name": "SITEWORK & CIVIL", "w0": 0, "w1": 8, "cost_m": 2.5},
        {"id": "SP-9", "name": "BUILDING SHELL & BOP", "w0": 4, "w1": 26, "cost_m": 7.5},
        {"id": "SP-2", "name": "HOT CELL TUNNEL", "w0": 10, "w1": 28, "cost_m": 3.6},
        {"id": "SP-5", "name": "REMOTE HANDLING", "w0": 14, "w1": 38, "cost_m": 3.6,
         "critical": True},
        {"id": "SP-7", "name": "ELECTRICAL", "w0": 16, "w1": 32, "cost_m": 5.8},
        {"id": "SP-8", "name": "MECH / HVAC / COOLING", "w0": 18, "w1": 36, "cost_m": 5.2},
        {"id": "SP-3", "name": "DECLAD & WASTE", "w0": 18, "w1": 36, "cost_m": 5.3},
        {"id": "SP-4", "name": "CASK HANDLING", "w0": 20, "w1": 36, "cost_m": 4.5},
        {"id": "SP-6", "name": "PROCESS MACHINES", "w0": 18, "w1": 40, "cost_m": 17.7},
        {"id": "SP-10", "name": "FIRE / SAFETY / I&C", "w0": 24, "w1": 40, "cost_m": 1.8},
    ]


# --------------------------------------------------------------------------- #
# general notes / abbreviations                                                #
# --------------------------------------------------------------------------- #
def general_notes() -> list[str]:
    return [
        "1. All work per the project specifications and applicable codes "
        "(IBC, ACI 349, ANSI/ANS-6.4, 10 CFR 20/50/70).",
        "2. Dimensions in metres unless noted; do not scale drawings.",
        "3. Geometry is [ENGINEERING ESTIMATE], design-basis class; verify "
        "with the A-E firm at DS-2 before construction.",
        "4. Shielding, confinement and criticality controls govern over "
        "architectural intent where they conflict.",
        "5. Hot-cell penetrations to be streaming-controlled.",
        "6. Separator vessels appear as black-box envelopes with utility "
        "connections only — no drive-mechanism enabling detail.",
    ]


def deferred_analyses() -> list[str]:
    return [
        "Shielding: 1.5 m bioshield is a gamma TVL screen only — no neutron "
        "source term, no penetration/streaming analysis (MCNP/SCALE-MAVRIC, DS-3).",
        "Criticality: no keff calculation performed; favourable-geometry + mass "
        "control is qualitative pending KENO/MCNP (SP-10 / DS-3).",
        "Decay heat: per-vessel / per-canister decay-heat removal and loss-of-power "
        "passive cooling not yet sized (DS-3).",
        "Confinement: ventilation balance, dP / leak-rate and accident-mode HVAC "
        "(DOE-HDBK-1169) not yet performed.",
    ]


def abbreviations() -> str:
    return (
        "SNF spent nuclear fuel · HEPA high-eff. particulate air · "
        "CAM continuous air monitor · keff effective multiplication · "
        "TVL tenth-value layer · MCC motor control centre · "
        "RMF rotating magnetic field · ATR Advanced Test Reactor · "
        "BOP balance of plant · PA protected area"
    )


def code_summary() -> list[str]:
    return [
        "Design basis: DR-010 / INTEC_Build_Package — plasma separation demo line.",
        "Structural: IBC (as adopted by DOE-ID) + ACI 349 (nuclear safety-related concrete).",
        "Shielding: ANSI/ANS-6.4; dose criteria per 10 CFR 20 / DOE-STD-1196.",
        "Seismic: DOE-STD-1020 site hazard for INTEC (Walsh Engineering analysis).",
        "Confinement: DOE-HDBK-1169 cascade; negative pressure C3→C2→C1→stack.",
        "Electrical: NEC / IEEE; site service 13.8 kV, ~10.25 MW coincident estimate.",
        "Fire: NFPA; water exclusion in fissile closed-atmosphere cells.",
        "Life safety: IBC egress; unoccupied robotic block doctrine for hall.",
    ]


# --------------------------------------------------------------------------- #
# full sheet register — 128 sheets, 13 disciplines                             #
# --------------------------------------------------------------------------- #
def sheet_register() -> list[dict[str, Any]]:
    """MB-INT-CAD-001 construction drawing register (full spine).

    Numbers/titles match Eigen/docs/INTEC_Construction_Drawing_Register.md.
    Section covers (*-000) are first in each discipline.
    """
    rows: list[tuple[str, str, str, str]] = []

    def add(disc: str, items: list[tuple[str, str, str]]) -> None:
        for no, title, scale in items:
            rows.append((no, title, scale, disc))

    # G — General (13)
    add("G", [
        ("G-000", "Section cover & material notes — General", "-"),
        ("G-001", "Cover sheet, project data, vicinity map", "-"),
        ("G-002", "Drawing index & sheet list + KEY PLAN", "-"),
        ("G-003", "General notes, abbreviations, symbols & legends", "-"),
        ("G-004", "Code summary & design basis", "-"),
        ("G-005", "Radiation area & contamination zoning — overall", "1:150"),
        ("G-006", "Engineering calculations index (derived)", "-"),
        ("G-007", "Equipment specifications index (basis-of-design)", "-"),
        ("G-008", "Fuel receipt basis — multi-campaign envelope", "-"),
        ("G-009", "Construction sequence & phasing", "-"),
        ("G-010", "Bid quantities — model takeoff (derived)", "-"),
        ("G-011", "Scope matrix + bid clarifications (derived)", "-"),
        ("G-012", "Room crosswalk — as-modeled vs program basis", "-"),
    ])
    # C — Civil (7)
    add("C", [
        ("C-000", "Section cover & material notes — Civil / Site", "-"),
        ("C-001", "Overall site plan & cask laydown", "1:150"),
        ("C-002", "Grading & drainage plan", "1:150"),
        ("C-003", "Site utilities plan (incoming services)", "1:150"),
        ("C-004", "Yard piping & duct bank plan", "1:150"),
        ("C-005", "Ops site plan — 2-acre commit (derived)", "1:150"),
        ("C-006", "Site context — INTEC aerial + siting candidate", "AS NOTED"),
    ])
    # S — Structural (17)
    add("S", [
        ("S-000", "Section cover & material notes — Structural", "-"),
        ("S-001", "Foundation / mat plan — model projection", "1:150"),
        ("S-002", "Ground-floor framing plan", "1:100"),
        ("S-003", "Roof framing plan", "1:100"),
        ("S-004", "Braced-frame elevations & sections", "1:100"),
        ("S-005", "Bioshield wall structural sections", "1:50"),
        ("S-006", "Typical connection & embed details", "1:10"),
        ("S-007", "Structural steel schedule", "-"),
        ("S-008", "Vessel-hall structural basis (recursion)", "-"),
        ("S-009", "Bioshield wall section — typical (detail)", "1:25"),
        ("S-010", "Mat foundation + vessel saddle / anchorage (detail)", "1:25"),
        ("S-011", "Roof shield-plug + penetration labyrinth (detail)", "1:25"),
        ("S-012", "General structural / construction notes", "-"),
        ("S-013", "Wall & slab type assemblies (derived)", "-"),
        ("S-014", "3-D structural views — foundation + roof framing", "-"),
        ("S-015", "Module construction + connections", "AS NOTED"),
        ("S-016", "Station construction matrix — every box", "-"),
    ])
    # EQ — Station equipment (17)
    eq = [("EQ-000", "Section cover & material notes — Equipment", "-")]
    for i, (st, what) in enumerate(eq_stations(), 1):
        eq.append((f"EQ-{i:03d}", f"Station equipment — {st} (derived)", "AS NOTED"))
        _ = what  # callouts live in register metadata / EQ sheets
    add("EQ", eq)
    # A — Architectural (19)
    add("A", [
        ("A-000", "Section cover & material notes — Architectural", "-"),
        ("A-001", "Ground-floor plan — overall", "1:100"),
        ("A-002", "Separator hall enlarged plan", "1:50"),
        ("A-003", "Annex plan — receipt / casking", "1:100"),
        ("A-004", "Roof plan", "1:100"),
        ("A-005", "Building elevations (N/S/E/W)", "1:100"),
        ("A-006", "Building section — hot-cell transverse", "1:100"),
        ("A-007", "Wall & shield-door sections", "1:20"),
        ("A-008", "Door, hatch & penetration schedule", "-"),
        ("A-009", "Room finish & area schedule", "-"),
        ("A-010", "Enlarged separator hall plan (projected)", "1:75"),
        ("A-011", "Room requirements & finish schedule (derived)", "-"),
        ("A-012", "Support program + door & window schedule (derived)", "-"),
        ("A-013", "Door leaf schedule + hardware sets (derived)", "-"),
        ("A-014", "Reflected ceiling plans — support stack (derived)", "AS NOTED"),
        ("A-015", "Interior elevations — toilet/decon (ADA heights)", "AS NOTED"),
        ("A-016", "Building section — longitudinal (active vessel row)", "1:100"),
        ("A-017", "Building section — head-end transverse", "1:100"),
        ("A-018", "Building section — robotic transfer spine", "1:100"),
    ])
    # N — Nuclear (14)
    add("N", [
        ("N-000", "Section cover & material notes — Nuclear", "-"),
        ("N-001", "Radiation zoning plans (operate / shutdown)", "1:100"),
        ("N-002", "Shielding plans & wall/penetration sections", "1:100"),
        ("N-003", "Confinement boundary & ventilation zoning", "1:100"),
        ("N-004", "Criticality control plan", "1:100"),
        ("N-005", "Cask handling & UNCASKING sequence", "AS NOTED"),
        ("N-006", "Remote-handling & crane coverage plan", "1:100"),
        ("N-007", "Equipment removal / jumper routes", "1:100"),
        ("N-008", "Shielding design basis (dose → wall)", "-"),
        ("N-009", "Thermal / criticality / confinement design basis", "-"),
        ("N-010", "Source-term inventory & materials-suitability matrix", "-"),
        ("N-011", "Separation cascade design basis (hub-and-spoke)", "-"),
        ("N-012", "Criticality segregation — fissile flow", "-"),
        ("N-013", "Cask & material-handling flow (product/cladding fork)", "-"),
    ])
    # H — HVAC (6)
    add("H", [
        ("H-000", "Section cover & material notes — HVAC", "-"),
        ("H-001", "Confinement ventilation flow diagram", "-"),
        ("H-002", "Ductwork plans (supply & exhaust)", "1:100"),
        ("H-003", "HEPA / filter train sections & details", "AS NOTED"),
        ("H-004", "HVAC equipment schedule (derived)", "-"),
        ("H-005", "Airflow schedule + confinement cascade (derived)", "-"),
    ])
    # P — Process (11)
    add("P", [
        ("P-000", "Section cover & material notes — Process & Piping", "-"),
        ("P-001", "Process flow diagram (PFD)", "-"),
        ("P-002", "P&IDs (per service)", "-"),
        ("P-003", "Piping plans — tunnel & stations", "1:100"),
        ("P-004", "Underground process piping plan", "1:100"),
        ("P-005", "Pipe support & hanger details", "AS NOTED"),
        ("P-006", "Line list & valve schedule", "-"),
        ("P-007", "Hub-and-spoke process flow + contained transfer", "-"),
        ("P-008", "Plumbing fixtures + emergency fixtures (derived)", "-"),
        ("P-009", "Plumbing riser + fixture connection schedule", "-"),
        ("P-010", "Valve schedule (BOD)", "-"),
    ])
    # E — Electrical (9)
    add("E", [
        ("E-000", "Section cover & material notes — Electrical", "-"),
        ("E-001", "Electrical one-line (13.8 kV / 10.25 MW)", "-"),
        ("E-002", "Power plans (normal & standby)", "1:100"),
        ("E-003", "Lighting & emergency lighting plans", "1:100"),
        ("E-004", "Grounding & lightning protection plan", "1:100"),
        ("E-005", "Raceway / cable-tray plans", "1:100"),
        ("E-006", "Panel & equipment schedules — NEC panel cards", "-"),
        ("E-007", "Lighting plan + fixture schedule (derived)", "1:100"),
        ("E-008", "Power one-line + panel schedule (derived)", "-"),
    ])
    # I — I&C (6)
    add("I", [
        ("I-000", "Section cover & material notes — I&C", "-"),
        ("I-001", "Control system architecture", "-"),
        ("I-002", "Instrument loop diagrams", "-"),
        ("I-003", "Radiation & criticality monitoring plan", "1:100"),
        ("I-004", "Instrument index", "-"),
        ("I-005", "Rad monitoring + CAAS + control I/O (derived)", "1:100"),
    ])
    # F — Fire (4)
    add("F", [
        ("F-000", "Section cover & material notes — Fire Protection", "-"),
        ("F-001", "Fire protection plans", "1:100"),
        ("F-002", "FP riser & system diagram", "-"),
        ("F-003", "Fire suppression selection per room (derived)", "-"),
    ])
    # L — Logistics (2)
    add("L", [
        ("L-000", "Section cover & material notes — Logistics", "-"),
        ("L-001", "Receive / ship / store / move / charge (derived)", "-"),
    ])
    # LS — Life safety (3)
    add("LS", [
        ("LS-000", "Section cover & material notes — Life Safety", "-"),
        ("LS-001", "Egress + occupant loads (derived)", "-"),
        ("LS-002", "Egress plan (exits, routes, EM light/signs)", "1:100"),
    ])

    return [
        {
            "number": n,
            "title": t,
            "scale": sc,
            "discipline": d,
            "drawn_by": "Mechanical Battery LLC — llm-bim",
            "checked_by": "-",
            "approved_by": "PE (reserved — A-E at DS-2)",
            "doc": DOC,
            "params_version": PARAMS_VERSION,
            "engine_sha": ENGINE_SHA,
        }
        for n, t, sc, d in rows
    ]


def discipline_counts() -> dict[str, int]:
    reg = sheet_register()
    out: dict[str, int] = {}
    for r in reg:
        out[r["discipline"]] = out.get(r["discipline"], 0) + 1
    return out


def open_questions() -> list[dict[str, Any]]:
    return [
        {
            "id": "Q-ANNEX",
            "status": "open",
            "q": "Annex length: fusion params annex_L=48 m vs llm-bim demo 31 m "
                 "receipt strip. Using 31 m for the south cask annex strip "
                 "(UNCASK..CASKING span); full-width annex is DS-2 massing.",
        },
        {
            "id": "Q-CELLS",
            "status": "resolved",
            "q": "n_cells in fusion scalars was 5 (legacy tunnel cells); "
                 "as-modeled placement is 8 sep cells (6 active / 2 reserved). "
                 "As-modeled governs.",
        },
        {
            "id": "Q-VESSEL",
            "status": "resolved",
            "q": "Size-B production vessel Ø610×1200 mm [MB-INTEC-FAB-001] used "
                 "in llm-bim; fusion params listed 0.66×1.5 m prototype envelope.",
        },
        {
            "id": "Q-SEAL",
            "status": "open",
            "q": "No PE/SE seal — design-basis only. DS-2 A-E firm stamps CDs.",
        },
    ]
