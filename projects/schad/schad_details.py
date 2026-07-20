#!/usr/bin/env python3
"""SCHAD framing/construction details — data-driven 2D detail geometry.

Each detail is a dict {id, title, scale, ops} drawn in DETAIL-LOCAL FEET
(x right, y up). Member sizes come from the design basis — never retyped.
Ops:  ('l',x1,y1,x2,y2) line   ('d',x1,y1,x2,y2) dashed line
      ('r',x,y,w,h) rect       ('c',cx,cy,r) circle
      ('h',x,y,w,h) hatch      ('t',x,y,w,'text') label (w=wrap width)

Scales: 12 = 1"=1'-0"; 8 = 1-1/2"=1'-0".
Covers the QA-audited transitions (curb, valley, eave trim) + the
standard framing set. [DESIGN SUPPORT — EOR to verify all connectors.]
"""

from __future__ import annotations

import schad_design_basis as basis

IN = 1.0 / 12.0
S = basis.build_scalars()
WT = S['wall_t_ext']          # 6.5" wall
FW, FD = S['footing_w'], 1.0  # 18" x 12" footing
SLAB = S['slab_garage_t']     # 4"
OV = S['overhang']            # 18"
PIT = S['roof_pitch']


def _rect(ops, x, y, w, h):
    ops.append(('r', x, y, w, h))


def _wall_studs(ops, x, y0, y1):
    """2x6 wall in section: two face lines + plate ticks."""
    ops.append(('l', x, y0, x, y1))
    ops.append(('l', x + WT, y0, x + WT, y1))


def d01_wall_section() -> dict:
    ops = []
    # footing + stem + slab
    _rect(ops, -FW / 2 + WT / 2, -1.9, FW, FD)
    ops.append(('h', -FW / 2 + WT / 2, -1.9, FW, FD))
    ops.append(('c', WT / 2 - 0.25, -1.6, 0.03))
    ops.append(('c', WT / 2 + 0.25, -1.6, 0.03))
    _rect(ops, 0.0, -0.9, WT, 0.9)              # stem 6"
    _rect(ops, WT, -SLAB, 2.6, SLAB)            # slab 4"
    ops.append(('d', WT, -SLAB - 0.33, 3.6, -SLAB - 0.33))   # gravel
    # sill + anchor bolt + studs to plate
    _rect(ops, 0.0, 0.0, WT, 0.125)
    ops.append(('l', WT / 2, -0.4, WT / 2, 0.3))
    _wall_studs(ops, 0.0, 0.125, 10.0 - 0.25)
    _rect(ops, 0.0, 10.0 - 0.25, WT, 0.25)      # dbl top plate
    # truss heel + roof plane + overhang + soffit
    ops.append(('l', 0.0, 10.0, -OV, 10.0 - OV * PIT))       # tail
    ops.append(('l', -OV, 10.0 - OV * PIT, -OV, 10.0 - OV * PIT + 0.6))
    ops.append(('l', 3.0, 10.0 + 3.0 * PIT + 0.4, -OV,
                10.0 - OV * PIT + 0.4))          # sheathing/metal line
    ops.append(('l', -OV + 0.1, 10.0 - OV * PIT + 0.15, -0.05, 10.0))
    ops.append(('l', 0.0, 10.0, 3.0, 10.0 + 3.0 * PIT))
    # labels
    ops.append(('t', 1.2, 11.6, 0.5, '24GA STANDING SEAM METAL ON ICE '
                '& WATER SHIELD ON 5/8" SHTG; TRUSS @ 24" OC'))
    ops.append(('t', -3.6, 9.0, 0.5, '18" OVERHANG: 2x SUB-FASCIA; 1x6 '
                'T&G PINE VENTED SOFFIT W/ CONT. STRIP VENT + RECESSED '
                'SOFFIT LIGHTS [USER]'))
    ops.append(('t', 1.1, 5.2, 0.5, '2x6 DF-L @ 16" OC; R-21 BATTS; '
                '5/8" DF STRUCTURAL SIDING (SHEAR) W/ 1x3 BATTENS @ 16"; '
                '5/8" GYP INT'))
    ops.append(('t', 1.2, -1.0, 0.5, '4" SLAB W/ RADIANT PEX @ 9" OC, '
                'FIBER MESH, 10-MIL VB, 4" GRAVEL; R-10 EDGE'))
    ops.append(('t', -3.4, -1.7, 0.5, '18"x12" FOOTING W/ (2) #4 CONT; '
                '6" STEM; 5/8" AB @ 6\'-0" OC'))
    return {'id': 'D01', 'title': 'TYPICAL WALL SECTION @ EAVE',
            'scale': 16, 'ops': ops}


def d02_shed_curb() -> dict:
    ops = []
    _wall_studs(ops, 0.0, 6.5, 9.75)             # main wall upper part
    _rect(ops, 0.0, 9.75, WT, 0.25)              # dbl plate @ 10'
    _wall_studs(ops, 0.0, 10.0, 11.875)          # 2x6 curb
    _rect(ops, 0.0, 11.875, WT, 0.125)           # curb plate @ 12'
    ops.append(('l', -0.2, 12.0, 3.4, 12.0 - 3.6 * 0.125))   # shed slope
    ops.append(('l', -0.2, 12.3, 3.4, 12.3 - 3.6 * 0.125))
    ops.append(('l', 0.0, 10.0, -1.2, 10.0))     # main roof line beyond
    ops.append(('d', -1.2, 10.0, -2.2, 10.0))
    ops.append(('t', 1.4, 12.9, 0.5, 'SHED TRUSS @ 24" OC W/ H2.5A EA '
                'BRG; 2x6 CURB @ 16" OC, CS16 STRAP EA STUD TO MAIN '
                'WALL STUDS'))
    ops.append(('t', 1.5, 10.6, 0.5, 'MAIN EAVE TRIMMED @ SHED BAND '
                '(QA-03); SELF-ADHERED FLASHING UP CURB MIN 6" UNDER '
                'SHED UNDERLAYMENT'))
    ops.append(('t', 1.5, 8.0, 0.5, '1-HR GYP (GARAGE SIDE) CONTINUOUS '
                'TO SHED DECK @ FIRE WALL'))
    return {'id': 'D02', 'title': 'SHED BEARING CURB @ GRID B '
            '(10\'->12\')', 'scale': 16, 'ops': ops}


def d03_valley() -> dict:
    ops = []
    ops.append(('l', -3.0, 0.0, 3.0, 0.0))       # main truss TC line
    ops.append(('l', -3.0, 0.4, 3.0, 0.4))       # main sheathing
    ops.append(('l', -2.4, 0.4, 0.0, 2.6))       # bay gable slope L
    ops.append(('l', 0.0, 2.6, 2.4, 0.4))        # slope R
    ops.append(('l', -2.0, 0.4, 0.0, 2.2))       # valley board line
    ops.append(('l', 0.0, 2.2, 2.0, 0.4))
    ops.append(('t', -3.3, 3.3, 0.5, 'CALIFORNIA (OVERLAY) VALLEY: 2x8 '
                'VALLEY PLATES FLAT ON MAIN SHTG; BAY-2 VALLEY JACKS @ '
                '24" OC BEAR ON PLATES'))
    ops.append(('t', 0.6, 1.9, 0.5, 'ICE & WATER FULL VALLEY WIDTH + '
                '24GA W-VALLEY FLASHING; NO FASTENERS IN VALLEY '
                'CENTER 6"'))
    ops.append(('t', -3.2, -0.7, 0.5, 'MAIN ROOF SHEATHING CONTINUOUS '
                'UNDER OVERLAY (QA-02 VALLEY GEOMETRY)'))
    return {'id': 'D03', 'title': 'VALLEY @ BAY-2 CROSS-GABLE',
            'scale': 8, 'ops': ops}


def d04_rake() -> dict:
    ops = []
    _wall_studs(ops, 0.0, 0.0, 3.0)
    ops.append(('l', -OV, 3.55, 2.5, 3.55))      # rake top
    ops.append(('l', -OV, 3.3, 2.5, 3.3))        # lookout line
    _rect(ops, -OV, 3.1, 0.2, 0.65)              # rake/fascia board
    ops.append(('t', 0.9, 4.3, 0.5, '2x4 LOOKOUTS @ 24" OC INTO GABLE '
                'TRUSS; 2x SUB-FASCIA + 1x RAKE BD; 1x6 T&G SOFFIT '
                'RETURN'))
    ops.append(('t', 0.9, 1.4, 0.5, 'GABLE-END TRUSS W/ DIAGONAL '
                'BRACING PER FAB; SIDING+BATTENS DIE INTO SOFFIT'))
    return {'id': 'D04', 'title': 'RAKE @ GABLE END (18" O.H.)',
            'scale': 8, 'ops': ops}


def d05_plate_step() -> dict:
    ops = []
    _wall_studs(ops, 0.0, 0.0, 9.75)             # 10' wall
    _rect(ops, 0.0, 9.75, WT, 0.25)
    _wall_studs(ops, 1.4, 0.0, 13.75)            # 14' bay wall
    _rect(ops, 1.4, 13.75, WT, 0.25)
    ops.append(('d', WT, 9.9, 1.4, 9.9))
    ops.append(('t', 2.6, 12.4, 0.5, 'BAY-2 2x6 @ 16" OC FULL-HEIGHT '
                '(14\') — BALLOON FRAME; BLOCK @ 10\' LINE'))
    ops.append(('t', 2.6, 8.2, 0.5, 'CS16 STRAP MAIN DBL PLATE TO BAY '
                'STUDS (SHEAR TRANSFER); FIRE-BLOCK @ PLATE STEP'))
    return {'id': 'D05', 'title': 'PLATE STEP @ BAY 2 (10\'/14\')',
            'scale': 16, 'ops': ops}


def d06_ssw_anchor() -> dict:
    ops = []
    _rect(ops, -1.0, -1.5, 2.0 + 2 * 0.09, 1.5)  # pad 24x26x18
    ops.append(('h', -1.0, -1.5, 2.18, 1.5))
    _rect(ops, 0.0, 0.0, 2.0, 3.2)               # SSW panel (partial ht)
    ops.append(('l', 0.35, -1.2, 0.35, 0.9))     # SSTB anchors
    ops.append(('l', 1.65, -1.2, 1.65, 0.9))
    ops.append(('t', 2.5, 2.4, 0.5, 'SIMPSON SSW24 PER PLAN; SSTB '
                'ANCHORS PER ESR-2652 — EMBED + EDGE DIST PER MFR; '
                'EOR VERIFY'))
    ops.append(('t', 2.5, -0.9, 0.5, 'PAD 24"x26"x18" W/ (3) #4 EW; '
                'SHEAR ANCHORAGE AT SILL PER SSW SCHEDULE'))
    return {'id': 'D06', 'title': 'STRONG-WALL ANCHORAGE',
            'scale': 12, 'ops': ops}


def d07_beam_bearing() -> dict:
    ops = []
    _rect(ops, -1.5, -2.5, 3.0, 2.5)             # point footing 36x30
    ops.append(('h', -1.5, -2.5, 3.0, 2.5))
    _rect(ops, -0.33, 0.0, 0.67, 0.08)           # base PL 8x8x1
    _rect(ops, -0.25, 0.08, 0.5, 8.5)            # HSS 6x6
    _rect(ops, -0.33, 8.58, 0.67, 0.04)          # cap PL
    _rect(ops, -0.29, 8.62, 0.58, 1.33)          # W16x40
    ops.append(('t', 1.1, 9.4, 0.5, 'W16x40 ON HSS6x6x1/4; CAP PL '
                '1/2" W/ (4) 3/4" A325; STIFFENERS IF REQ\'D PER EOR'))
    ops.append(('t', 1.1, 4.5, 0.5, 'HSS COL PRIMED; BASE PL 8x8x1 W/ '
                '(4) 3/4" AB ON 1" GROUT'))
    ops.append(('t', 1.1, -1.6, 0.5, 'FOOTING 36"x36"x30" W/ (4) #4 EW '
                'BOTT (q=1,356 PSF < 1,500 OK)'))
    return {'id': 'D07', 'title': 'BEAM BEARING @ HSS POST',
            'scale': 12, 'ops': ops}


def d08_firewall() -> dict:
    ops = []
    _wall_studs(ops, 0.0, 0.0, 10.0)
    ops.append(('l', -0.05, 0.0, -0.05, 10.0))   # gyp garage side
    ops.append(('l', WT + 0.05, 0.0, WT + 0.05, 10.0))
    ops.append(('l', -0.4, 10.6, 2.4, 10.6 - 2.8 * 0.125))   # shed deck
    ops.append(('t', 1.3, 7.0, 0.5, '1-HR SEPARATION [RB]: 5/8" TYPE X '
                'GYP BOTH SIDES, CONTINUOUS SLAB TO ROOF DECK (QA-08); '
                'JOINTS STAGGERED + TAPED'))
    ops.append(('t', 1.3, 3.4, 0.5, 'PENETRATIONS FIRE-CAULKED; D6 '
                'DOOR 20-MIN SELF-CLOSING; NO OPEN CHASES'))
    return {'id': 'D08', 'title': 'FIRE SEPARATION @ GARAGE/ADU',
            'scale': 16, 'ops': ops}


def d09_radiant_edge() -> dict:
    ops = []
    _rect(ops, 0.0, -0.9, WT, 0.9)               # stem
    _rect(ops, WT, -SLAB, 3.0, SLAB)
    for i in range(4):
        ops.append(('c', WT + 0.5 + i * 0.75, -SLAB / 2, 0.03))
    ops.append(('l', WT, -SLAB - 0.02, WT + 3.0, -SLAB - 0.02))  # R-10
    ops.append(('l', WT - 0.08, -0.9, WT - 0.08, 0.0))           # edge ins
    ops.append(('t', 1.5, 0.9, 0.5, '1/2" PEX @ 9" OC TIED TO MESH, '
                '3/4" MIN COVER; SLEEVE @ JOINTS/PENETRATIONS'))
    ops.append(('t', 1.5, -1.4, 0.5, 'R-10 XPS UNDER + R-15 EDGE '
                '[HANDOFF]; 10-MIL VB LAPPED/TAPED; ISOLATION JT @ '
                'STEM'))
    return {'id': 'D09', 'title': 'RADIANT SLAB EDGE',
            'scale': 12, 'ops': ops}


def d10_door_header() -> dict:
    ops = []
    _rect(ops, 0.0, 9.0, 0.35, 1.33)             # jamb/trimmer pack
    _rect(ops, 5.6, 9.0, 0.35, 1.33)
    _rect(ops, 0.0, 10.33, 5.95, 0.3)            # header (2)LVL over 12'
    ops.append(('d', 0.35, 9.0, 5.6, 9.0))       # door head line
    ops.append(('t', 1.2, 11.4, 0.5, '(2) 1-3/4"x16" LVL HDR [BOM] '
                'OVER 12\' OPENING; TRIMMERS PER SSW LAYOUT — VERIFY '
                'W/ STRONG-WALL GEOMETRY (EOR)'))
    ops.append(('t', 1.2, 8.2, 0.5, 'TRACK BLOCKING PER DOOR MFR; '
                'HEAD FLASHING + DRIP OVER TRIM'))
    return {'id': 'D10', 'title': 'OVERHEAD DOOR HEADER (12\' CLR)',
            'scale': 16, 'ops': ops}


def d11_ridge() -> dict:
    ops = []
    ops.append(('l', -3.0, 0.0, 0.0, 1.5))       # top chords
    ops.append(('l', 0.0, 1.5, 3.0, 0.0))
    ops.append(('l', -3.0, 0.35, 0.0, 1.85))     # sheathing
    ops.append(('l', 0.0, 1.85, 3.0, 0.35))
    _rect(ops, -0.08, 1.5, 0.16, 0.35)           # ridge blocking
    ops.append(('l', -0.7, 2.15, 0.7, 2.15))     # ridge cap
    ops.append(('t', 1.1, 2.6, 0.5, 'VENTED RIDGE: STANDING-SEAM RIDGE '
                'CAP W/ PROFILE CLOSURES + EXT. VENT MAT; 2x BLOCKING '
                'BETWEEN TRUSSES'))
    ops.append(('t', 1.1, 0.4, 0.5, 'SCISSOR TRUSS PEAK PER FAB '
                '(DEFERRED SUBMITTAL); H1 TIES @ BRG'))
    return {'id': 'D11', 'title': 'RIDGE @ SCISSOR TRUSS',
            'scale': 8, 'ops': ops}


def d12_batten_corner() -> dict:
    ops = []
    ops.append(('l', 0.0, 0.0, 0.0, 3.0))        # corner
    ops.append(('l', 0.0, 0.0, 3.0, 0.0))
    ops.append(('l', -0.054, -0.054, -0.054, 3.0))   # siding faces
    ops.append(('l', -0.054, -0.054, 3.0, -0.054))
    for i in range(3):
        _rect(ops, 0.6 + i * 1.33, -0.14, 0.25, 0.08)  # battens (plan)
    ops.append(('t', 1.0, 1.8, 0.5, '5/8" DF SIDING = SHEAR LAYER: '
                'EDGE NAILING PER EOR SCHEDULE; SS FASTENERS [HANDOFF]'))
    ops.append(('t', 1.0, -1.1, 0.5, '1x3 BATTENS @ 16" OC; 2x CORNER '
                'BOARDS; WRB BEHIND; FLASH @ OPENINGS'))
    return {'id': 'D12', 'title': 'STRUCTURAL SIDING/BATTEN @ CORNER '
            '(PLAN)', 'scale': 12, 'ops': ops}


def build_details() -> list:
    return [d01_wall_section(), d02_shed_curb(), d03_valley(),
            d04_rake(), d05_plate_step(), d06_ssw_anchor(),
            d07_beam_bearing(), d08_firewall(), d09_radiant_edge(),
            d10_door_header(), d11_ridge(), d12_batten_corner()]


if __name__ == '__main__':
    ds = build_details()
    print('%d details, %d ops total'
          % (len(ds), sum(len(d['ops']) for d in ds)))
