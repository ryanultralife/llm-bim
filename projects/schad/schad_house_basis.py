#!/usr/bin/env python3
"""SCHAD Phase 2 — EXISTING HOUSE record (3730 Chandler Rd residence).

Source [HPLAN]: hand-drawn scaled plans (1/4" = 1'-0", initialed CBM,
photographed 2024-09-30, found 2026-07-12 in OneDrive Ledger Built
"2024-008 Schad Garage/Plans"):
  - "Downstairs Scaled Plan.pdf"  -> main level
  - "Upstairs Scaled Plan.pdf"    -> upper level
  Both carry: "FLOORPLAN for PLANNING ONLY. CONFIRM ALL DIMENSIONS."
Also [TERRAIN]: "Schad Terrain Garage Plan.skp" models the existing house
massing next to the new garage.

STATUS: EXISTING-CONDITIONS record for the Phase 2 remodel. The remodel
SCOPE (contract Exhibit B) is still undefined — these data support
existing-plans sheets (H1.1/H1.2) and the field-verify pass; remodel
drawings start once scope is set. All geometry is approximate (scaled
sketch); field verification required before construction documents.
"""

from __future__ import annotations


def house_rooms() -> list[dict]:
    """Room inventory from the scaled plans (areas approximate)."""
    main = [
        ('LIVING', 'Living Room', 'oil tank + firewood + F/P on N wall'),
        ('KITCHEN', 'Kitchen', '4x12 HDR noted at opening'),
        ('DINING', 'Dining Rm', 'open to kitchen; 3x8 HDR'),
        ('MASTER', 'Master', '2x6 walls (rest of house 2x4 U.O.N.)'),
        ('CHANGING', 'Changing', 'between master and bath'),
        ('MSTRBA', 'Mstr Ba', 'tub + lav'),
        ('BATH1', 'Bath (main)', 'tub/shower + lav + WC'),
        ('GUEST', 'Guest Rm', ''),
        ('LAUNDRY', 'Laundry/Mud', 'exterior door 2-6'),
        ('STAIR', 'Stairs', 'up to bedroom level; DN to deck level'),
    ]
    upper = [
        ('GIRLS', 'Girls Rm', 'dormer'),
        ('BOYS', 'Boys Rm', 'dormer'),
        ('CLOSET', 'Closet', 'between bedrooms'),
        ('ATTIC', 'Attic', 'unfinished'),
        ('STAIRWELL', 'Stairwell', ''),
    ]
    out = []
    for rid, nm, note in main:
        out.append({'id': rid, 'name': nm, 'level': 'Main', 'note': note})
    for rid, nm, note in upper:
        out.append({'id': rid, 'name': nm, 'level': 'Upper', 'note': note})
    return out


def house_exterior_features() -> list[str]:
    return [
        'WOOD DECK (large, SW) + upper WOOD DECK at master',
        'COV. POR. (west) + COVERED PORCH (east, conc. slab)',
        'ELECT MAIN on west wall; 8-0 x 6-6 GAR DOOR (lower level, west)',
        'OIL TANK + FIREWOOD storage + F/P on living room north wall',
    ]


def house_openings() -> list[dict]:
    """Window/door callouts legible on [HPLAN] (W x H, feet-inches)."""
    return [
        {'mark': 'HW1', 'size': "6-0 x 5-0", 'loc': 'Master N'},
        {'mark': 'HW2', 'size': "5-0 x 6-8", 'loc': 'Master W (slider?)'},
        {'mark': 'HW3', 'size': "2-0 x 2-0", 'loc': 'Mstr Ba'},
        {'mark': 'HW4', 'size': "3-0 x 4-6", 'loc': 'Guest Rm E'},
        {'mark': 'HW5', 'size': "2-0 x 4-6 TYP", 'loc': 'Dining/porch band'},
        {'mark': 'HW6', 'size': "4-0 x 5-0", 'loc': 'Living N'},
        {'mark': 'HW7', 'size': "3-0 x 5-0 + 5-0 x 5-0 + 4-0 x 5-0",
         'loc': 'Kitchen S band'},
        {'mark': 'HW8', 'size': "4-0 x 3-0 / 3-0 x 4-6", 'loc': 'Laundry'},
        {'mark': 'HD1', 'size': "3-0 doors TYP", 'loc': 'ext doors'},
        {'mark': 'HD2', 'size': "2-6", 'loc': 'Laundry ext door'},
        {'mark': 'HGD', 'size': "8-0 x 6-6", 'loc': 'lower gar door W'},
    ]


def house_framing() -> dict:
    return {
        'walls': '2x4 U.O.N.; master wing 2x6 [HPLAN]',
        'upper_joists': '2x6 @ 16" OC [HPLAN]',
        'rafters': '2x6 @ 24" OC [HPLAN]',
        'master_roof': 'shed ~2.5:12 over master wing [HPLAN]',
        'main_roof': 'gabled, multiple ridges (main E-W + wings) [HPLAN]',
        'headers': '3x8 HDR (dining), 4x12 HDR (kitchen) noted [HPLAN]',
    }


def remodel_scope() -> dict:
    """Phase 2 scope [USER 2026-07-12]: 'existing house will be — remove
    roof and add bathrooms and bedrooms upstairs' = SECOND-STORY
    ADDITION: demo existing roof, build full upper level w/ new bedrooms
    + bathrooms, new roof above."""
    return {
        'directive': 'Remove existing roof; add bathrooms and bedrooms '
                     'upstairs [USER 2026-07-12]. Design direction [USER '
                     '2026-07-13]: KEEP DORMERS + OPEN-TO-BELOW where '
                     'possible (1.5-story character retained); plus a '
                     'single-story MASTER SUITE ADDITION at the back top '
                     'left (NW) of the plan — master bedroom + bathroom + '
                     'walk-in closet, VAULTED ceiling, no second story '
                     'above. PROGRAM CONFIRMED [USER 2026-07-13b]: 4 BED '
                     '/ 2 BATH UPSTAIRS + MASTER BED/BATH DOWNSTAIRS '
                     '(the NW suite) = house totals 5 BR / 3 BA minimum.',
        'design_directives': [
            'Upstairs: dormered 1.5-story massing (NOT full-height '
            'walls); open-to-below volumes where structure allows '
            '(stair, entry) [USER 2026-07-13]',
            'NW ADDITION (first floor): master bedroom + bath + walk-in '
            'closet; vaulted ceiling; single story; ties into Living '
            'Room wing at the back top left of the existing plan',
            'Existing master wing converts to DEN / OFFICE / WORKOUT '
            '[USER 2026-07-13] — light-touch: finishes + layout; its 2x6 '
            'walls + shed roof remain (outside the re-roof scope unless '
            'field verify says otherwise)',
            'Drawing detail benchmark = Sierra Star dimension-plan '
            'standard [REF: Andrews/Plans & Specs]: full dimension '
            'strings, door tags w/ lockset legend, area summary table, '
            'room tags on every plan',
        ],
        'work': [
            'DEMO: existing roof structure (2x6 rafters @ 24"), dormers, '
            'and ceiling of upper half-story; protect main level '
            '(weather-in plan REQUIRED — Quincy snow country)',
            'NEW FLOOR SYSTEM: existing 2x6 @ 16" ceiling joists are NOT '
            'a bedroom floor (2x6 DF#2 ~9\'-9" max @ 40 psf LL) — new '
            'engineered joists (I-joist/LVL) or full sistering, per EOR',
            'NEW UPPER WALLS: full-height 2x6 @ 16" (R-21), windows per '
            'egress (CRC R310) in every bedroom',
            'NEW ROOF: trusses 24" OC @ 75 psf, 6:12 to match garage '
            '(PROPOSED), standing-seam metal, 18" overhangs + 1x6 T&G '
            'pine soffit to match garage [USER decisions]',
            'BATHROOMS: plumbing stacks aligned over existing main-level '
            'wet walls where possible; septic capacity re-check REQUIRED',
            'ELECTRICAL: AFCI bedroom circuits, smoke/CO each bedroom + '
            'hall + interconnect whole house (CRC R314/R315)',
            'HEAT: extend hydronic/heat-pump strategy or ductless heads '
            'upstairs — coordinate w/ HP-1/HP-2 design',
        ],
        'structural_flags': [
            'Existing 2x4 bearing walls: verify stud grade/spacing + '
            'plate continuity for added story (compression usually OK; '
            'SHEAR is the concern — plan plywood shear retrofit)',
            'Foundation: verify footings under bearing lines for added '
            'story load (field-verify item 2)',
            'Seismic: added story raises W significantly — lateral '
            'design by EOR, holdown retrofit likely',
            'Master-wing shed roof (~2.5:12) interface with new upper '
            'level: confirm whether wing is inside or outside the '
            'addition footprint',
        ],
        'owner_questions': [
            'RESOLVED 2026-07-13: 4 BEDROOMS + 2 BATHROOMS upstairs '
            '[USER]; concept on H2.2 — confirm room assignments',
            'RESOLVED 2026-07-13: dormers + open-to-below (not full '
            'height); NW master suite addition is FIRST floor, vaulted, '
            'no second story above it',
            'RESOLVED 2026-07-13: existing master wing converts to '
            'DEN / OFFICE / WORKOUT [USER]; house totals 5 BR / 3 BA',
            'Reuse existing stairwell location? (code: 6\'-8" headroom, '
            'R311)',
            'Occupied during construction? (drives phasing/weather-in)',
            'Roof form/material match garage (6:12 charcoal standing '
            'seam) — confirm',
            'RESOLVED 2026-07-13: NW addition dims CONFIRMED — 16x24 '
            'bed + 10x12 bath + 10x10 WIC [USER]',
        ],
    }


def concept_upper() -> list[dict]:
    """PROPOSED upper-level concept [USER 2026-07-13: 4 BR + 2 BA;
    dormers + open-to-below]. House-local feet, origin SW of the upper
    band; band ESTIMATED ~60' x 24' from [HPLAN] proportions — FIELD
    DIMS GOVERN. Ridge E-W at y=12; kneewalls at the long edges."""
    r = []

    def add(nm, x, y, w, d, note=''):
        r.append({'name': nm, 'x': x, 'y': y, 'w': w, 'd': d,
                  'note': note})
    add('BED 1', 0, 0, 13, 12, 'S dormer + egress')
    add('BED 2', 0, 12, 13, 12, 'N dormer + egress')
    add('BATH 1', 13, 14, 7, 10, 'over kitchen wet wall')
    add('LINEN', 13, 10, 7, 4, '')
    add('BATH 2', 13, 0, 7, 10, 'stacks w/ main bath')
    add('HALL', 20, 8, 8, 8, 'full-height zone at ridge')
    add('STAIR (E)', 28, 8, 10, 8, 'existing stairwell reused')
    add('OPEN TO BELOW', 38, 8, 8, 8, 'over entry [USER]')
    add('BED 3', 46, 0, 14, 12, 'S dormer + egress')
    add('BED 4', 46, 12, 14, 12, 'N dormer + egress')
    return r


def concept_suite() -> list[dict]:
    """NW master suite addition (single story, VAULTED, no second
    floor). DIMS CONFIRMED [USER 2026-07-13]: 16x24 bed + 10x12 bath +
    10x10 WIC. Local feet; attaches at the house NW/living-room wing."""
    return [
        {'name': 'MASTER BED (vaulted)', 'x': 0, 'y': 0, 'w': 16,
         'd': 24, 'note': 'vaulted clg; no 2nd story'},
        {'name': 'MASTER BATH', 'x': 16, 'y': 12, 'w': 10, 'd': 12,
         'note': 'double vanity + shower'},
        {'name': 'W.I.C.', 'x': 16, 'y': 2, 'w': 10, 'd': 10, 'note': ''},
    ]


def concept_notes() -> list[str]:
    return [
        'CONCEPT ONLY — band estimated ~60\'x24\' from the scaled plan; '
        'FIELD DIMENSIONS GOVERN; confirm with owners',
        'HOUSE PROGRAM [USER 2026-07-13]: 4 BR + 2 BA UPSTAIRS + master '
        'bed/bath/WIC DOWNSTAIRS (NW vaulted suite) = 5 BR / 3 BA total '
        'minimum; dormered 1.5-story massing, open-to-below over entry',
        'EGRESS: every bedroom gets a dormer egress window per CRC R310 '
        '(5.7 SF net clear, 44" max sill)',
        'Baths stack over main-level wet walls to shorten DWV runs; '
        'septic capacity re-check REQUIRED before permit',
        'Smoke/CO in each BR + hall + interconnect whole house '
        '(R314/R315)',
        'New floor system per EOR (existing 2x6 @ 16" is not a bedroom '
        'floor); new roof trusses @ 75 psf, 6:12 metal to match garage',
        'NW MASTER SUITE: single-story, vaulted, no second story above; '
        'ties to living-room wing; window/door layout at design',
        'EXISTING MASTER WING converts to DEN / OFFICE / WORKOUT [USER '
        '2026-07-13]; house program: 4BR/2BA up + NW master suite down '
        '= 5 BR / 3 BA total',
    ]


def house_field_verify() -> list[str]:
    """Existing-conditions capture list before remodel CDs."""
    return [
        'Laser-measure all rooms; reconcile vs scaled plan (plan is '
        'PLANNING ONLY per its own note)',
        'Foundation type/condition under each wing (deck-level story?)',
        'Roof framing + condition at 2x6 rafters @ 24" (75 psf snow '
        'country: likely UNDERSIZED by modern code — flag for PE)',
        'Electrical service size at ELECT MAIN; panel schedule',
        'Oil tank: capacity/age/containment; heating appliance inventory',
        'Plumbing: supply material, DWV routing, water source (well?)',
        'Insulation levels walls/attic; window U-factors',
        'Septic location + capacity vs added ADU fixture load',
    ]


if __name__ == '__main__':
    print('SCHAD existing house: %d rooms, %d opening records'
          % (len(house_rooms()), len(house_openings())))
