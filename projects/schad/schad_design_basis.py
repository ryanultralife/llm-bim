#!/usr/bin/env python3
"""SCHAD design basis — the single source of truth for the Revit thread.

Phase 1: Garage / ADU / Workshop complex, 3730 Chandler Rd, Quincy CA 95971
(Plumas County, APN 005-350-001-000). Owner: Joey & Karen Schad. Designer:
Ryan Vukich, Ledger Built LLC.

Every dimension here is TRANSCRIBED ONCE from the project record and cited:
  [RB]      Schads_Permit_Set.rb (permit-set generator, the drawn plan;
            its PDF output Garage_ADU_Workshop_Permit_Set.pdf verified
            identical, dated 09/30/2025)
  [BOM]     "SCHAD Materials & Construction Bill of Materials" (Google Doc)
  [HANDOFF] "SCHAD CAD Conversion Handoff Notes" (Google Doc)
  [SKP]     Plans/Schad Garage Plan.skp (SketchUp 2024, Medeek-framed
            model, July 2024 — framing reference; finishes superseded)
Downstream (bridge -> JSON -> Revit builder) only transforms; it never
retypes a number. Conflicts between sources are NOT silently resolved —
they are recorded in open_questions() and the chosen value marked.

UNITS: feet (the project record is imperial). The bridge converts to metres
for the JSON; the Revit builder converts metres to internal feet — same
convention as the proven INTEC thread.

COORDS: origin at the SW corner of the MAIN building; +x East, +y North,
+z up. The Bay 2 projection extends to y = -2 (south of origin).

Phase 2 (House Remodel) has no design record yet — see open_questions().
"""

from __future__ import annotations

IN = 1.0 / 12.0     # inches -> feet

# Ledger Built project number [SKP meta: original path
# "...\Ledger Built\2024-008 Schad Garage\Plans\Schad Garage Plan.skp"]
PROJECT_CODE = '2024-008'


# --------------------------------------------------------------------------- #
# scalars                                                                      #
# --------------------------------------------------------------------------- #
def build_scalars() -> dict:
    return {
        # footprint [RB @main_width/@main_depth/@rear_*; BOM "48' x 32' with
        # Bay 2 projecting 2' forward"]
        'main_L': 48.0,          # E-W [RB]
        'main_W': 32.0,          # N-S [RB]
        'rear_L': 32.0,          # rear addition E-W [RB]
        'rear_W': 16.0,          # rear addition N-S [RB]
        'rear_off_x': 8.0,       # rear addition west offset [RB]
        'bay2_proj': 2.0,        # Bay 2 projects south [BOM; absent in RB]
        'adu_L': 14.0,           # ADU width within rear addition [RB]
        'workshop_L': 18.0,      # workshop width within rear addition [RB]
        'bay_L': 16.0,           # bay module: 3 bays x 16' = 48' [RB beams]

        # heights [USER 2026-07-12: "middle bay 14, plate height 10 around
        # everything" — resolves Q-PLATE. RB section A3.1: "18' RIDGE".
        # The shed keeps its drawn 2' fall (RB north elev), so with the
        # north plate at 10' it bears at 12' on the main wall — Q-SHED]
        'plate_main': 10.0,       # [USER 2026-07-12]
        'plate_bay2': 14.0,       # middle bay [USER 2026-07-12; BOM 2x6-14]
        'plate_rear_high': 12.0,  # shed bearing at main wall (y=32), derived
        'plate_rear_low': 10.0,   # rear north eave plate [USER 2026-07-12]
        'ridge': 18.0,           # ridge E-W at y = main_W/2, 6:12 [RB/HANDOFF]
        'roof_pitch': 6.0 / 12.0,  # [HANDOFF]
        'roof_t': 0.75,          # massing thickness of the roof plate
        'overhang': 1.5,         # 18" eaves/rakes [USER 2026-07-12]
        'soffit': '1x6 T&G pine, vented; soffit lighting '
                  '[USER 2026-07-12]',

        # wall assemblies [RB framing notes: 2x6 @ 16" OC ext; HANDOFF 2x4 int]
        'wall_t_ext': 6.5 * IN,  # 2x6 stud + 5/8" structural DF siding
        'wall_t_int': 4.5 * IN,  # 2x4 partition
        'stud_ext': '2x6 DF-L @ 16" OC',
        'stud_int': '2x4 DF-L @ 16" OC',

        # foundation [RB foundation notes]
        'footing_w': 18.0 * IN,
        'footing_d': 12.0 * IN,
        'stem_front': 8.0 * IN,
        'stem_typ': 6.0 * IN,
        'slab_garage_t': 4.0 * IN,   # w/ radiant [RB / BOM]
        'slab_adu_t': 3.0 * IN,      # for tile [BOM]

        # structure [RB framing sheet/notes]
        'beam': 'W16x40',        # 2 EA, N-S at bay lines [RB/BOM]
        'beam_depth': 16.0 * IN,
        'beam_width': 7.0 * IN,
        'ssw_w': 2.0,            # Simpson Strong-Wall panel width (24")
        'ssw_t': 6.0 * IN,
        'truss_spacing': 2.0,    # 24" OC [RB/HANDOFF]
        'snow_psf': 75.0,        # [RB framing notes]

        # areas as published on the cover sheet [RB A0.1] — checked by tests
        'area_total': 2080.0,
        'area_garage': 1568.0,
        'area_adu': 224.0,
        'area_workshop': 224.0,   # published; drawn gross is 288 (Q-MECH)
        'area_mech': 32.0,
    }


# --------------------------------------------------------------------------- #
# placements — rooms/bays (x, y = SW corner; w, d = extents; feet)             #
# --------------------------------------------------------------------------- #
def build_placements() -> list[dict]:
    s = build_scalars()
    bay, W, proj = s['bay_L'], s['main_W'], s['bay2_proj']
    rx, ry = s['rear_off_x'], s['main_W']
    return [
        {'id': 'BAY1', 'name': 'Garage Bay 1', 'kind': 'garage',
         'x': 0.0, 'y': 0.0, 'w': bay, 'd': W,
         'req': 'U occ / V-B; 4" slab w/ radiant; GFCI receptacles'},
        {'id': 'BAY2', 'name': 'Garage Bay 2', 'kind': 'garage',
         'x': bay, 'y': -proj, 'w': bay, 'd': W + proj,
         'req': 'U occ / V-B; 12\' clear door; 4" slab w/ radiant; GFCI'},
        {'id': 'BAY3', 'name': 'Garage Bay 3', 'kind': 'garage',
         'x': 2 * bay, 'y': 0.0, 'w': bay, 'd': W,
         'req': 'U occ / V-B; 4" slab w/ radiant; GFCI; EV NEMA 14-50'},
        {'id': 'ADU', 'name': 'ADU', 'kind': 'adu',
         'x': rx, 'y': ry, 'w': s['adu_L'], 'd': s['rear_W'],
         'req': 'R-3 occ; 1-hr sep from garage; ADA; 3" slab; AFCI'},
        {'id': 'WORKSHOP', 'name': 'Workshop', 'kind': 'workshop',
         'x': rx + s['adu_L'], 'y': ry, 'w': s['workshop_L'],
         'd': s['rear_W'],
         'req': 'U occ; 4" slab; incl. planned 32 SF mech closet (Q-MECH)'},
        # utility room in Bay 3 NE corner [USER 2026-07-13]: 1/2 bath +
        # dog wash + well pressure vessel + radiant boilers. 9'x12' = 108
        # SF; uses existing E wall (x=48) + N wall (y=32); new W & S
        # partitions. Bay 3 becomes an L around it.
        {'id': 'MECHBATH', 'name': 'Mech / Bath', 'kind': 'utility',
         'x': 39.0, 'y': 20.0, 'w': 9.0, 'd': 12.0,
         'req': 'U occ; 4" slab w/ FLOOR DRAIN (dog wash); 1/2 bath '
                '(WC+lav); radiant boiler room + well pressure vessel; '
                'combustion air + boiler flue per CMC; GFCI'},
    ]


def footprint() -> list[tuple]:
    """Exterior face-of-stud polygon, CCW from origin [RB floor plan,
    plus the Bay 2 projection per BOM]."""
    s = build_scalars()
    L, W, p = s['main_L'], s['main_W'], s['bay2_proj']
    b = s['bay_L']
    rx, rL, rW = s['rear_off_x'], s['rear_L'], s['rear_W']
    return [
        (0.0, 0.0), (b, 0.0), (b, -p), (2 * b, -p), (2 * b, 0.0),
        (L, 0.0), (L, W), (rx + rL, W), (rx + rL, W + rW),
        (rx, W + rW), (rx, W), (0.0, W),
    ]


# --------------------------------------------------------------------------- #
# walls — native Revit walls, pass 1                                           #
# --------------------------------------------------------------------------- #
def build_walls() -> list[dict]:
    """Exterior shell traced from footprint() + the two drawn interior
    walls [RB floor plan]. Centerlines on face-of-stud for pass 1 (all
    plan dims are to face of stud per RB general note 2); assign real wall
    types + centerline offsets live in Revit later."""
    s = build_scalars()
    pts = footprint()
    b, W, p, L = s['bay_L'], s['main_W'], s['bay2_proj'], s['main_L']
    rx, rL = s['rear_off_x'], s['rear_L']

    def seg_height(x1, y1, x2, y2):
        # Bay 2 projection segments (touching y < 0) get the Bay 2 plate
        if min(y1, y2) < 0.0:
            return s['plate_bay2'], 'exterior-bay2'
        # rear-addition segments (y > main_W) get the shed low plate
        if min(y1, y2) >= W and max(y1, y2) > W:
            return s['plate_rear_low'], 'exterior-rear'
        return s['plate_main'], 'exterior-main'

    walls = []
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        h, kind = seg_height(x1, y1, x2, y2)
        walls.append({'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
                      'base': 'L1 - Slab', 'height': h,
                      'thick': s['wall_t_ext'], 'kind': kind})
    # interior: garage/rear-addition separation = 1-hr fire wall [RB note 4]
    # — runs to the shed bearing (12') so the separation is continuous to
    # the roof plane above the garage plate
    walls.append({'x1': rx, 'y1': W, 'x2': rx + rL, 'y2': W,
                  'base': 'L1 - Slab', 'height': s['plate_rear_high'],
                  'thick': s['wall_t_ext'], 'kind': 'fire-separation-1hr'})
    # interior: ADU / workshop partition [RB floor plan]
    xw = rx + s['adu_L']
    walls.append({'x1': xw, 'y1': W, 'x2': xw, 'y2': W + s['rear_W'],
                  'base': 'L1 - Slab', 'height': s['plate_rear_low'],
                  'thick': s['wall_t_int'], 'kind': 'interior-2x4'})
    # Mech/Bath utility room partitions [USER 2026-07-13]: W wall x=39
    # (y 20..32) + S wall y=20 (x 39..48), in Bay 3 NE corner
    walls.append({'x1': 39.0, 'y1': 20.0, 'x2': 39.0, 'y2': W,
                  'base': 'L1 - Slab', 'height': s['plate_main'],
                  'thick': s['wall_t_int'], 'kind': 'interior-2x4'})
    walls.append({'x1': 39.0, 'y1': 20.0, 'x2': s['main_L'], 'y2': 20.0,
                  'base': 'L1 - Slab', 'height': s['plate_main'],
                  'thick': s['wall_t_int'], 'kind': 'interior-2x4'})
    return walls


# --------------------------------------------------------------------------- #
# openings — door & window schedules [RB A4.1] + placements (Q-LOC where       #
# the plan does not fix a location; positions carry pos_assumed=True)          #
# --------------------------------------------------------------------------- #
def build_doors() -> list[dict]:
    s = build_scalars()
    b, p, W, rW = s['bay_L'], s['bay2_proj'], s['main_W'], s['rear_W']

    def oh(mark, bay_cx, y, w, h):
        return {'mark': mark, 'w': w, 'h': h, 'type': 'OVERHEAD GARAGE',
                'remarks': 'INSULATED, GLASS PANELS',
                'cx': bay_cx, 'cy': y, 'wall': 'front',
                'pos_assumed': False}   # centered in its bay per elevations

    return [
        oh('D1', b / 2.0, 0.0, 12.0, 9.0),               # Bay 1 [RB]
        oh('D2', b * 1.5, -p, 12.0, 12.0),               # Bay 2 [RB]
        oh('D3', b * 2.5, 0.0, 12.0, 9.0),               # Bay 3 [RB]
        {'mark': 'D4', 'w': 3.0, 'h': 6.0 + 8 * IN, 'type': 'ENTRY',
         'remarks': 'SOLID CORE, ADA COMPLIANT',          # ADU entry [RB]
         'cx': s['rear_off_x'] + s['adu_L'] / 2.0, 'cy': W + rW,
         'wall': 'rear-north', 'pos_assumed': True},
        {'mark': 'D5', 'w': 3.0, 'h': 6.0 + 8 * IN, 'type': 'ENTRY',
         'remarks': 'SOLID CORE',                         # workshop ext [RB]
         'cx': s['rear_off_x'] + s['adu_L'] + s['workshop_L'] / 2.0,
         'cy': W + rW, 'wall': 'rear-north', 'pos_assumed': True},
        {'mark': 'D6', 'w': 2.5, 'h': 6.0 + 8 * IN, 'type': 'ENTRY',
         'remarks': 'HOLLOW METAL',       # garage->workshop [RB, loc Q-LOC]
         'cx': s['rear_off_x'] + s['adu_L'] + 4.0, 'cy': W,
         'wall': 'fire-separation-1hr', 'pos_assumed': True},
    ]


def build_windows() -> list[dict]:
    """[RB A4.1]: 4x vinyl casement 4'x4', U 0.30. Locations not drawn on
    the plan (Q-LOC): assumed ADU north/west + workshop north, sill 3'."""
    s = build_scalars()
    W, rW, rx = s['main_W'], s['rear_W'], s['rear_off_x']
    base = {'w': 4.0, 'h': 4.0, 'type': 'VINYL CASEMENT, DOUBLE PANE',
            'u_factor': 0.30, 'sill': 3.0, 'pos_assumed': True}
    return [
        dict(base, mark='W1', cx=rx + 3.0, cy=W + rW, wall='rear-north'),
        dict(base, mark='W2', cx=rx, cy=W + rW / 2.0, wall='rear-west'),
        dict(base, mark='W3', cx=rx + s['adu_L'] + 4.0, cy=W + rW,
             wall='rear-north'),
        dict(base, mark='W4', cx=rx + s['adu_L'] + 13.0, cy=W + rW,
             wall='rear-north'),
    ]


# --------------------------------------------------------------------------- #
# structure — beams + Simpson Strong-Walls [RB S2.1; BOM Division 05]          #
# --------------------------------------------------------------------------- #
def build_structure() -> dict:
    s = build_scalars()
    b, W, rW, p = s['bay_L'], s['main_W'], s['rear_W'], s['bay2_proj']
    beams = [  # W16x40, N-S at the bay lines, full depth [RB S2.1]
        {'id': 'B1', 'section': s['beam'], 'x': b, 'y1': 0.0, 'y2': W + rW},
        {'id': 'B2', 'section': s['beam'], 'x': 2 * b, 'y1': 0.0,
         'y2': W + rW},
    ]
    # Strong-Walls flank each overhead door [BOM: 4x SSW24x9 + 2x SSW24x12;
    # exact stations are the truss/foundation engineer's — pos_assumed]
    ssw = []
    for i, (x0, y, h, model) in enumerate((
            (0.0, 0.0, 9.0, 'SSW24x9'), (b - s['ssw_w'], 0.0, 9.0,
                                         'SSW24x9'),
            (b, -p, 12.0, 'SSW24x12'), (2 * b - s['ssw_w'], -p, 12.0,
                                        'SSW24x12'),
            (2 * b, 0.0, 9.0, 'SSW24x9'), (3 * b - s['ssw_w'], 0.0, 9.0,
                                           'SSW24x9'))):
        ssw.append({'id': 'SW%d' % (i + 1), 'model': model, 'x': x0,
                    'y': y, 'h': h, 'pos_assumed': True})
    return {'beams': beams, 'strong_walls': ssw}


# --------------------------------------------------------------------------- #
# notes & schedules [RB, verbatim]                                             #
# --------------------------------------------------------------------------- #
def build_notes() -> dict:
    return {
        'general': [
            'ALL WORK TO COMPLY WITH 2022 CALIFORNIA BUILDING CODE',
            'ALL DIMENSIONS TO FACE OF STUD U.N.O.',
            'VERIFY ALL DIMENSIONS IN FIELD',
            'FIRE SEPARATION: 1-HOUR RATED BETWEEN GARAGE & ADU',
            'ALL LUMBER: DF-L #2 OR BETTER',
            'CONCRETE: 3,500 PSI @ 28 DAYS',
            'REINFORCEMENT: GRADE 60',
            'INSULATION: R-21 WALLS, R-38 CEILING [USER 2026-07-12]',
            'ROOF OVERHANG: 18" EAVES & RAKES; SOFFIT 1x6 T&G PINE, '
            'VENTED, W/ SOFFIT LIGHTING [USER 2026-07-12]',
        ],
        'foundation': [
            'FOOTINGS: 18" WIDE x 12" DEEP',
            'STEM WALLS: 8" AT GARAGE FRONT, 6" TYPICAL',
            'SLABS: 4" THICK GARAGE, 3" ADU',
            'VAPOR BARRIER: 10 MIL UNDER ALL SLABS',
            'GRAVEL: 4" CLEAN GRAVEL UNDER SLABS',
            'ANCHOR BOLTS: 5/8" DIA @ 6\'-0" O.C.',
            'STRONG-WALLS: SIMPSON PER SCHEDULE',
            'REBAR: (2) #4 CONTINUOUS IN FOOTINGS',
        ],
        'framing': [
            'STUDS: 2x6 DF-L @ 16" O.C.',
            'PLATES: DOUBLE TOP, PT SILL',
            'STEEL BEAMS: W16x40 (2 REQUIRED)',
            'STRONG-WALLS: SIMPSON SSW PER SCHEDULE',
            'SHEATHING: 5/8" DF STRUCTURAL SIDING PER ENGINEERING MEMO '
            '(supersedes RB 7/16" OSB note — Q-SHTG)',
            'TRUSSES: 24" O.C., ENGINEERED',
            'SNOW LOAD: 75 PSF',
        ],
        'electrical': [   # [RB MEP-101]
            'ALL WORK PER 2023 CALIFORNIA ELECTRICAL CODE',
            'MAIN SERVICE: 200A MINIMUM',
            'ALL GARAGE RECEPTACLES: GFCI PROTECTED',
            'ADU HABITABLE ROOMS: AFCI PROTECTED',
            'EV CHARGING: NEMA 14-50 RECEPTACLE',
            'KITCHEN: (2) 20A CIRCUITS',
            'SMOKE/CO ALARMS: HARDWIRED WITH BATTERY',
        ],
        'plumbing': [     # [RB MEP-201]
            'ALL WORK PER 2022 CALIFORNIA PLUMBING CODE',
            'WATER SUPPLY: 3/4" MINIMUM',
            'HOT/COLD WATER: TYPE L COPPER',
            'DRAIN/WASTE: SCHEDULE 40 PVC',
            'WATER HEATER: 50 GAL ELECTRIC (Q-WH)',
            'LOW-FLOW FIXTURES: EPA WATERSENSE',
            'BACKFLOW PREVENTION: AT HOSE BIBS',
        ],
        'mechanical': [   # [RB MEP-301]
            'ALL WORK PER 2022 CALIFORNIA MECHANICAL CODE',
            'RADIANT FLOOR: 1/2" PEX @ 9" O.C. IN SLAB',
            'INSULATION: R-10 UNDER ADU SLAB',
            'MANIFOLD: STEEL WITH FLOW METERS',
            'WATER TEMP: 120 DEG F MAX',
            'THERMOSTAT: PROGRAMMABLE 7-DAY',
            'BATHROOM EXHAUST: 50 CFM',
            'ENERGY COMPLIANCE: TITLE 24-2022',
        ],
    }


def electrical_panel() -> list[tuple]:
    return [  # (ckt, description, amps) [RB MEP-101]
        ('1/3', 'Garage Lights - Bay 1', 15),
        ('2/4', 'Garage Recept - Bay 1 (GFCI)', 20),
        ('5/7', 'Garage Lights - Bay 2', 15),
        ('6/8', 'Garage Recept - Bay 2 (GFCI)', 20),
        ('9/11', 'Garage Lights - Bay 3', 15),
        ('10/12', 'Garage Recept - Bay 3 (GFCI)', 20),
        ('13/15', 'EV Charging Station', 50),
        ('14/16', 'Workshop 240V', 30),
        ('21-23', 'SUB-PANEL FEED - ADU', 100),
    ]


def plumbing_fixtures() -> list[tuple]:
    return [  # (mark, fixture, FU) [RB MEP-201 + USER 2026-07-13]
        ('KS', 'Kitchen Sink (ADU)', 2.0), ('LAV', 'Lavatory (ADU)', 1.0),
        ('WC', 'Water Closet (1.28 GPF)', 3.0),
        ('SHR', 'Shower (2.0 GPM, ADU)', 2.0),
        ('US', 'Utility Sink', 2.0),
        ('WC2', 'Water Closet - Mech/Bath 1/2 bath (1.28 GPF)', 3.0),
        ('LAV2', 'Lavatory - Mech/Bath', 1.0),
        ('DW', 'DOG WASH - tiled basin w/ hand shower + floor drain '
         '[USER 2026-07-13]', 3.0),
        ('WH', 'DHW Tank - indirect off boiler OR 83-gal HPWH (Q-DHW) '
         'in Mech/Bath', None),
    ]


def mech_equipment() -> list[tuple]:
    return [  # (mark, equipment, capacity) [RB MEP-301 + USER updates]
        ('RF-1', 'Radiant Floor (1/2" PEX @ 9" O.C.), 8 loops', '—'),
        ('B-1', 'PROPANE BOILER - radiant heat source, Mech/Bath room '
         '[USER 2026-07-13]; sealed-combustion, direct-vent',
         '~52 MBH input (size to design loss)'),
        ('B-2', 'PROPANE BOILER - lead/lag / standby (2 units for '
         'turndown + reliability)', 'per B-1'),
        ('WH-1', 'TANKLESS (INSTANT) PROPANE WATER HEATER + small buffer '
         'tank [USER 2026-07-13]; direct-vent', '~120-150 MBH / ~10 gal '
         'buffer'),
        ('PT-1', 'WELL PRESSURE VESSEL - 60-GAL VERTICAL bladder tank + '
         'pump controls, Mech/Bath [USER 2026-07-13]', '60 gal vertical'),
        ('MAN', 'Radiant manifold w/ flow meters, Mech/Bath', '8 loops'),
        ('EF-1', 'Bath Exhaust Fan (ADU + Mech/Bath 1/2 bath)', '50 CFM'),
    ]


def sheet_register() -> list[dict]:
    """The permit-set index [RB A0.1], one entry per sheet. Sign-off per
    the project record: Ryan Vukich / Ledger Built LLC is designer of
    record; structural PE spot is RESERVED (by others per HANDOFF)."""
    idx = [
        ('A0.1', 'COVER SHEET & SITE PLAN', 'AS NOTED', 'A'),
        ('C1.1', 'SITE PLAN', '1" = 30\'-0"', 'C'),
        ('A1.1', 'FLOOR PLAN', '1/4" = 1\'-0"', 'A'),
        ('A1.2', 'ADU - ENLARGED PLAN, FURNITURE & ELECTRICAL (ADA)',
         '3/4" = 1\'-0"', 'A'),
        ('A2.1', 'EXTERIOR ELEVATIONS - SOUTH & NORTH', '1/4" = 1\'-0"',
         'A'),
        ('A2.2', 'EXTERIOR ELEVATIONS - EAST & WEST', '1/4" = 1\'-0"',
         'A'),
        ('A3.1', 'BUILDING SECTIONS', '1/4" = 1\'-0"', 'A'),
        ('S1.1', 'FOUNDATION PLAN', '1/4" = 1\'-0"', 'S'),
        ('S2.1', 'ROOF FRAMING PLAN', '1/8" = 1\'-0"', 'S'),
        ('S3.1', 'STRUCTURAL DETAILS - SECTIONS & BEARINGS', 'AS NOTED',
         'S'),
        ('S3.2', 'STRUCTURAL DETAILS - FRAMING TRANSITIONS', 'AS NOTED',
         'S'),
        ('S3.3', 'STRUCTURAL DETAILS - CONNECTIONS & ENVELOPE',
         'AS NOTED', 'S'),
        ('A4.1', 'DOOR & WINDOW SCHEDULES', '-', 'A'),
        ('MEP-101', 'ELECTRICAL PLAN', '1/4" = 1\'-0"', 'MEP'),
        ('MEP-201', 'PLUMBING PLAN', '1/4" = 1\'-0"', 'MEP'),
        ('MEP-301', 'MECHANICAL PLAN', '1/4" = 1\'-0"', 'MEP'),
        ('H1.1', 'EXISTING HOUSE - MAIN LEVEL', '1/4" = 1\'-0"', 'H'),
        ('H1.2', 'EXISTING HOUSE - UPPER LEVEL', '1/4" = 1\'-0"', 'H'),
        ('H2.1', 'HOUSE REMODEL - SCOPE & DESIGN CRITERIA', '-', 'H'),
        ('H2.2', 'HOUSE REMODEL - CONCEPT PLANS (PROPOSED)',
         '1/4" = 1\'-0"', 'H'),
    ]
    return [{'number': n, 'title': t, 'scale': sc, 'discipline': d,
             'drawn_by': 'Ryan Vukich — Ledger Built LLC',
             'checked_by': '-',
             'approved_by': 'PE (reserved — structural by others)'}
            for n, t, sc, d in idx]


# --------------------------------------------------------------------------- #
# open questions — conflicts in the record; NEVER silently resolved            #
# --------------------------------------------------------------------------- #
def open_questions() -> list[dict]:
    return [
        {'id': 'Q-LEN', 'status': 'resolved',
         'q': 'HANDOFF says 42\' length; RB + BOM + cover-sheet areas say '
              '48\'. Using 48\'.'},
        {'id': 'Q-PLATE', 'status': 'resolved',
         'q': 'USER 2026-07-12: middle bay (Bay 2) plate 14\'; 10\' plate '
              'around everything else (rejects HANDOFF 12\' eave; '
              'supersedes RB rear 8\' north eave).'},
        {'id': 'Q-BAY2ROOF', 'status': 'proposed',
         'q': 'Bay 2 roof: PROPOSED (2026-07-12) front-facing cross-gable '
              'over the 16\' bay — 6:12 from the 14\' plate peaks at 18\', '
              'exactly the main ridge height (ridge N-S at x=24, dies into '
              'the main roof). Geometry is in the massing; confirm before '
              'elevations print.'},
        {'id': 'Q-WIN', 'status': 'open',
         'q': 'Windows: RB schedule = 4x 4\'x4\' casement; BOM = 2x 3\'x4\' '
              'casement + 1x 4\'x6\' fixed + 1x 2\'x3\' awning. Using RB.'},
        {'id': 'Q-WH', 'status': 'resolved',
         'q': 'USER 2026-07-12: HEAT PUMP. 2x 83-gal heat-pump water '
              'tanks per HANDOFF (garage utility + ADU mech); supersedes '
              'RB 50-gal electric.'},
        {'id': 'Q-INSUL', 'status': 'resolved',
         'q': 'USER 2026-07-12: R-21 walls / R-38 ceilings.'},
        {'id': 'Q-SHTG', 'status': 'open',
         'q': 'RB framing note says 7/16" OSB sheathing; the engineering '
              'structural-change memo makes 5/8" DF siding the structural '
              'layer. Memo governs; RB note superseded.'},
        {'id': 'Q-MECH', 'status': 'superseded',
         'q': 'Prior rear-addition mech closet SUPERSEDED [USER '
              '2026-07-13] by the new 9\'x12\' MECH/BATH room in Bay 3 NE '
              'corner (1/2 bath + dog wash + boilers + well pressure '
              'vessel). Rear addition = full workshop now.'},
        {'id': 'Q-FUEL', 'status': 'resolved',
         'q': 'PROPANE [USER 2026-07-13]. Radiant boilers B-1/B-2 +'
              ' tankless DHW are propane, sealed-combustion direct-vent; '
              'exterior propane tank on site (see C1.1) w/ gas line to '
              'Mech/Bath; NFPA 58 setbacks apply.'},
        {'id': 'Q-DHW', 'status': 'resolved',
         'q': 'TANKLESS/INSTANT propane water heater + small (~10 gal) '
              'buffer tank [USER 2026-07-13]; direct-vent, in Mech/Bath '
              '(WH-1). Not indirect-off-boiler, not HPWH.'},
        {'id': 'Q-WELL', 'status': 'resolved',
         'q': '60-GALLON VERTICAL well pressure vessel [USER '
              '2026-07-13] in Mech/Bath w/ pump controls. Still locate '
              'well head + confirm existing vs new pump.'},
        {'id': 'Q-PROPANE', 'status': 'resolved',
         'q': 'EXISTING 250-GAL propane tank [USER 2026-07-13]; '
              'expandable (add a 2nd tank if peak load requires). '
              'Locate existing tank on the survey; verify vaporization '
              'rate + regulator/line sizing for the added boiler + '
              'tankless load (lead/lag boilers + intermittent tankless '
              'ease the peak). NFPA 58 setbacks confirmed at existing '
              'tank.'},
        {'id': 'Q-SHED', 'status': 'open',
         'q': 'Rear shed: north plate 10\' (USER 2026-07-12) + the drawn '
              '2\' fall -> bears at 12\' on the main north wall (1.5:12), '
              '2\' above the main 10\' eave — bearing/curb detail needed; '
              'verify pitch with truss fab against 75 PSF snow.'},
        {'id': 'Q-LOC', 'status': 'open',
         'q': 'Personnel door + window locations are not dimensioned in the '
              'record; placements flagged pos_assumed=True need owner/'
              'designer confirmation.'},
        {'id': 'Q-OVERHANG', 'status': 'resolved',
         'q': 'USER 2026-07-12: 18" overhang, eaves + rakes; soffit 1x6 '
              'T&G pine w/ soffit lighting (supersedes HANDOFF 24" '
              'suggestion). In the roof massing.'},
        {'id': 'Q-HOUSE', 'status': 'scoped',
         'q': 'Phase 2 SCOPED: remove roof, add beds/baths upstairs '
              '[USER 2026-07-12]; dormers + open-to-below, plus NW '
              'first-floor master suite addition (bed/bath/WIC, vaulted, '
              'single story) [USER 2026-07-13]. Existing plans on H1.1/'
              'H1.2; criteria on H2.1; concepts on H2.2. PROGRAM '
              'CONFIRMED: 4BR/2BA upstairs + NW master suite downstairs '
              '= 5 BR / 3 BA; old master wing -> DEN/OFFICE/WORKOUT '
              '[USER 2026-07-13]. Remaining: NW suite dims + field '
              'verify. Benchmark: Sierra Star standard.'},
        {'id': 'Q-SETBACK', 'status': 'open',
         'q': 'APN 005-350-001 is 0.63 ac, ~263\' x ~112\' (county GIS '
              '2026-07-13) — 30/40\' setbacks cannot fit 112\' depth. '
              'OWNERS ALSO OWN THE ADJACENT PARCEL [USER 2026-07-13] -> '
              'options: (a) confirm actual zone setbacks and build '
              'within -001, (b) lot-line adjustment, (c) merger. '
              'Identify adjacent APN w/ assessor, talk to Plumas '
              'planning, commission survey. Garage anchor (150\', 35\') '
              'adjusts to the chosen path.'},
        {'id': 'Q-HANDOFF10', 'status': 'open',
         'q': 'The 10 owner-preference questions in HANDOFF (stain color, '
              'batten finish, gutters, fixtures...) remain unanswered.'},
        {'id': 'Q-ROOFMAT', 'status': 'resolved',
         'q': 'SKP (July 2024) carries Cambridge Weatherwood shingle + '
              'HardiPlank/cedar materials — an earlier finish scheme. The '
              'later BOM/HANDOFF standing-seam 24ga charcoal + 5/8" DF '
              'board-and-batten govern. SKP remains the framing reference '
              '(Medeek walls/trusses/electrical layers).'},
    ]


if __name__ == '__main__':
    s = build_scalars()
    print('SCHAD design basis — Phase 1 Garage/ADU/Workshop')
    print('  footprint: %d pts, %.0f x %.0f main + %.0f x %.0f rear'
          % (len(footprint()), s['main_L'], s['main_W'],
             s['rear_L'], s['rear_W']))
    print('  rooms: %d | walls: %d | doors: %d | windows: %d | sheets: %d'
          % (len(build_placements()), len(build_walls()),
             len(build_doors()), len(build_windows()),
             len(sheet_register())))
    print('  open questions: %d (%d resolved)'
          % (len(open_questions()),
             sum(1 for q in open_questions() if q['status'] == 'resolved')))
