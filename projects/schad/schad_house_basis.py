#!/usr/bin/env python3
"""SCHAD Phase 2 — existing house, resolved from the scaled sheet.

Source [HPLAN]: hand-drawn plans at 1/4" = 1'-0", initialed CBM,
photographed 2024-09-30. The photo on file is
``H1_1_main_level.png`` / ``H1_2_upper_level.png`` (the Revit thread).
Both sheets say: "FLOORPLAN for PLANNING ONLY. CONFIRM ALL DIMENSIONS."

Scale used here [USER 2026-09-25, "the house plans are scaled"]:
  The main-level photo is 4032 px wide and the sheet fills the frame at
  about 160 px per inch, so 1/4 inch on the sheet is 40 px and one foot.
  Rooms below are that measurement, rounded to the nearest foot.
  Tolerance is about a foot: the photo is not a flatbed scan.
  Origin is the living-room northwest corner (electrical main / lower
  garage door). +x runs toward the guest wing (sheet right). +y runs
  toward the wood deck (sheet down).

Decisions [USER 2026-09-25]:
  Existing stairs stay. Nobody lives in the house during construction.
  The new roof matches the garage (6:12, charcoal standing seam, 18"
  overhang, 1x6 T&G soffit) and reaches the garage through an open
  breezeway.
"""

from __future__ import annotations

PX_PER_FT = 40.0


def _room(rid, name, level, x, y, w, d, note=''):
    return {
        'id': rid, 'name': name, 'level': level,
        'x': float(x), 'y': float(y), 'w': float(w), 'd': float(d),
        'note': note,
    }


def house_rooms() -> list[dict]:
    """Existing rooms, nearest foot off the 1/4" sheet."""
    main = [
        _room('LIVING', 'Living Room', 'Main', 0, 0, 24, 16,
              'oil tank + firewood + F/P on the north wall'),
        _room('DECK', 'Wood Deck', 'Main', 0, 16, 26, 12,
              'large deck south of the living room'),
        _room('STAIR-W', 'Stair to deck', 'Main', 22, -7, 7, 5,
              'labeled 5\'-0" x 7\'-0" on the sheet; DN to deck level'),
        _room('BATH-W', 'Bath', 'Main', 26, -8, 10, 9,
              'tub/shower + lav + WC, north of the living room'),
        _room('MASTER', 'Master', 'Main', 36, -28, 20, 13,
              '2x6 walls; becomes den / office / workout'),
        _room('CLO-M', 'Master closet', 'Main', 36, -15, 9, 8, ''),
        _room('CHANGING', 'Changing', 'Main', 36, -7, 14, 12,
              'between master and dining'),
        _room('MSTRBA', 'Mstr Ba', 'Main', 50, -12, 8, 10, 'tub + lav'),
        _room('STAIR', 'Stairs', 'Main', 56, -10, 5, 7,
              'existing stair to the upper floor — KEEP'),
        _room('BATH1', 'Bath', 'Main', 62, -10, 9, 9,
              'tub/shower + lav + WC'),
        _room('GUEST', 'Guest Rm', 'Main', 68, -12, 18, 13, ''),
        _room('CLO-G', 'Guest closet', 'Main', 68, -12, 6, 5, ''),
        _room('DINING', 'Dining Rm', 'Main', 24, 2, 12, 14,
              'open to kitchen; 3x8 header'),
        _room('KITCHEN', 'Kitchen', 'Main', 36, 8, 12, 18,
              '4x12 header at the west opening'),
        _room('PORCH', 'Covered Porch', 'Main', 48, 10, 22, 8,
              'depth 8\'-0" labeled on the sheet; concrete slab'),
        _room('LAUNDRY', 'Laundry/Mud', 'Main', 71, 1, 14, 16,
              'exterior door 2\'-6"'),
    ]
    upper = [
        _room('GIRLS', 'Girls Rm', 'Upper', 36, -4, 14, 10,
              'dormer; sits over the changing room'),
        _room('CLOSET', 'Closet', 'Upper', 50, -2, 8, 6,
              'between the bedrooms'),
        _room('BOYS', 'Boys Rm', 'Upper', 62, -4, 14, 10,
              'dormer; sits over the guest wing'),
        _room('STAIRWELL', 'Stairwell', 'Upper', 56, -10, 5, 7,
              'same stair as the main floor — KEEP'),
        _room('ATTIC', 'Attic', 'Upper', 36, 6, 40, 8,
              'unfinished, south of the bedroom bar'),
    ]
    return main + upper


def house_exterior_features() -> list[str]:
    return [
        'WOOD DECK (large, south of living) + upper deck at the master',
        'Covered porch west of living + covered porch east, concrete slab, 8 ft deep',
        'ELECT MAIN on the living west wall; 8-0 x 6-6 garage door (lower level, west)',
        'OIL TANK + FIREWOOD + fireplace on the living-room north wall',
    ]


def house_openings() -> list[dict]:
    """Window and door callouts written on the sheet (W x H)."""
    return [
        {'mark': 'HW1', 'size': "6-0 x 5-0", 'loc': 'Master N'},
        {'mark': 'HW2', 'size': "5-0 x 6-8", 'loc': 'Master W'},
        {'mark': 'HW3', 'size': "2-0 x 2-0", 'loc': 'Mstr Ba'},
        {'mark': 'HW4', 'size': "3-0 x 4-6", 'loc': 'Guest Rm E'},
        {'mark': 'HW5', 'size': "2-0 x 4-6 TYP", 'loc': 'Dining / porch band'},
        {'mark': 'HW6', 'size': "4-0 x 5-0", 'loc': 'Living N'},
        {'mark': 'HW7', 'size': "3-0 x 5-0 + 5-0 x 5-0 + 4-0 x 5-0",
         'loc': 'Kitchen S band'},
        {'mark': 'HW8', 'size': "4-0 x 3-0 / 3-0 x 4-6", 'loc': 'Laundry'},
        {'mark': 'HD1', 'size': "3-0 doors TYP", 'loc': 'exterior doors'},
        {'mark': 'HD2', 'size': "2-6", 'loc': 'Laundry exterior door'},
        {'mark': 'HGD', 'size': "8-0 x 6-6", 'loc': 'lower garage door, west'},
    ]


def house_framing() -> dict:
    return {
        'walls': '2x4 U.O.N.; master wing 2x6 [HPLAN]',
        'upper_joists': '2x6 @ 16" OC [HPLAN] — not a bedroom floor',
        'rafters': '2x6 @ 24" OC [HPLAN] — removed with the re-roof',
        'master_roof': 'existing shed over the master wing — replaced '
                       'in the re-roof [USER 2026-09-25]',
        'main_roof': 'new 6:12 to match the garage, through the breezeway',
        'headers': '3x8 header at dining, 4x12 header at kitchen [HPLAN]',
    }


def breezeway() -> dict:
    """Open link from the house to the garage west wall.

    Garage frame: origin at the garage southwest corner, +x east, +y north.
    The east end of the breezeway lands on the garage west wall (x = 0).
    """
    return {
        'x': -18.0,
        'y': 12.0,
        'w': 18.0,
        'd': 8.0,
        'plate': 10.0,
        'pitch': 6.0 / 12.0,
        'posts': '6x6 PT at corners and midspan, on piers',
        'roof': '6:12 charcoal standing seam, 18 in overhang, '
                '1x6 T&G pine soffit — same as the garage',
        'walls': 'none',
    }


def remodel_scope() -> dict:
    return {
        'directive': 'Remove the existing roof and build the upper floor '
                     'as a dormered 1.5-story, plus a single-story vaulted '
                     'master suite at the northwest. The new roof matches '
                     'the garage and connects to it through an open '
                     'breezeway [USER 2026-09-25]. Program: 4 bedrooms and '
                     '2 baths upstairs, master bed/bath/closet downstairs, '
                     '5 bedrooms and 3 baths in all. The old master wing '
                     'becomes den / office / workout.',
        'design_directives': [
            'Upstairs stays dormered, with an open-to-below at the entry',
            'Northwest addition: 16x24 bed, 10x12 bath, 10x10 closet, '
            'vaulted, no second story above it',
            'Existing stair stays where it is (main-floor stair at '
            'x=56, y=-10)',
            'House is vacant during construction',
            'Roof: 6:12, 75 psf trusses, charcoal standing seam, 18 in '
            'overhangs, 1x6 T&G soffit, continuous in material across '
            'the open breezeway to the garage',
        ],
        'work': [
            'DEMO: existing roof, dormers, and the upper half-story '
            'ceiling. The house is empty, so the weather-in is a '
            'construction sequence, not a lived-in phasing plan.',
            'NEW FLOOR: the existing 2x6 joists at 16 in are not a '
            'bedroom floor. New I-joists or LVLs, per the engineer.',
            'NEW UPPER WALLS: 2x6 at 16 in, R-21, egress window in '
            'every bedroom',
            'NEW ROOF: trusses 24 in OC at 75 psf, 6:12, standing-seam '
            'charcoal, matching the garage, carried across the breezeway',
            'BATHROOMS stack on the existing wet walls where they can. '
            'Septic capacity still has to be rechecked.',
            'ELECTRICAL: AFCI in the bedrooms, smoke and CO in each '
            'bedroom and the hall, interconnected',
        ],
        'structural_flags': [
            'Existing 2x4 walls: shear is the question under the added '
            'story. Plan on plywood or OSB shear panels.',
            'Foundations under the new bearing lines are a field check',
            'Added story raises seismic weight. Hold-downs are likely.',
            'Breezeway roof is open on both sides. Posts are 6x6 on piers, '
            'not part of the garage shear line.',
        ],
        'owner_questions': [
            'RESOLVED 2026-07-13: 4 bedrooms and 2 baths upstairs',
            'RESOLVED 2026-07-13: dormers and an open-to-below; northwest '
            'suite is one story and vaulted',
            'RESOLVED 2026-07-13: old master wing becomes den / office / '
            'workout. House is 5 bedrooms and 3 baths.',
            'RESOLVED 2026-07-13: northwest suite is 16x24 + 10x12 + 10x10',
            'RESOLVED 2026-09-25: existing stairs stay',
            'RESOLVED 2026-09-25: nobody lives in the house during '
            'construction',
            'RESOLVED 2026-09-25: roof matches the garage through an '
            'open breezeway',
            'RESOLVED 2026-09-25: existing plan taken off the 1/4" sheet '
            'to the nearest foot',
        ],
    }


def concept_upper() -> list[dict]:
    """Proposed upper floor, seated on the scaled main footprint.

    The bedroom bar runs from the changing room across to the guest wing.
    The existing stair is the hole in that bar. Sizes are the confirmed
    program, not a new measurement.
    """
    return [
        {'name': 'BED 1', 'x': 36, 'y': -8, 'w': 13, 'd': 12,
         'note': 'dormer + egress'},
        {'name': 'BATH 1', 'x': 49, 'y': -6, 'w': 7, 'd': 10,
         'note': 'over the kitchen wet wall'},
        {'name': 'STAIR (KEEP)', 'x': 56, 'y': -10, 'w': 5, 'd': 7,
         'note': 'existing stair'},
        {'name': 'HALL', 'x': 56, 'y': -3, 'w': 8, 'd': 6, 'note': ''},
        {'name': 'BATH 2', 'x': 61, 'y': -10, 'w': 7, 'd': 8,
         'note': 'stacks on the main bath'},
        {'name': 'BED 2', 'x': 68, 'y': -8, 'w': 12, 'd': 12,
         'note': 'dormer + egress'},
        {'name': 'BED 3', 'x': 36, 'y': 4, 'w': 14, 'd': 11,
         'note': 'dormer + egress'},
        {'name': 'OPEN TO BELOW', 'x': 50, 'y': 4, 'w': 8, 'd': 8,
         'note': 'over the entry'},
        {'name': 'BED 4', 'x': 62, 'y': 4, 'w': 14, 'd': 11,
         'note': 'dormer + egress'},
    ]


def concept_suite() -> list[dict]:
    """Northwest master suite. Dims confirmed 2026-07-13.

    Local feet, attached at the north side of the existing master
    (which becomes the den).
    """
    return [
        {'name': 'MASTER BED (vaulted)', 'x': 36, 'y': -52, 'w': 16,
         'd': 24, 'note': 'vaulted; no second story'},
        {'name': 'MASTER BATH', 'x': 52, 'y': -40, 'w': 10, 'd': 12,
         'note': 'double vanity + shower'},
        {'name': 'W.I.C.', 'x': 52, 'y': -50, 'w': 10, 'd': 10, 'note': ''},
    ]


def concept_notes() -> list[str]:
    return [
        'Existing plan scaled off the 1/4" sheet to the nearest foot. '
        'The sheet still says confirm all dimensions.',
        'Stairs stay. House is empty during construction.',
        'New roof matches the garage and crosses an open 8 ft x 18 ft '
        'breezeway. No walls on the breezeway.',
        '4 bedrooms and 2 baths upstairs, master suite downstairs, '
        '5 bedrooms and 3 baths in all.',
        'Every bedroom gets an egress window (5.7 sf clear, sill at 44 in).',
        'Baths stack on the existing wet walls. Septic gets rechecked.',
        'New floor framing per the engineer. Existing 2x6 joists stay '
        'as ceiling framing only.',
        'Northwest suite is one story, vaulted, 16x24 + 10x12 + 10x10.',
    ]


def house_field_verify() -> list[str]:
    return [
        'Scaled dims are the sheet, plus or minus about a foot. A tape '
        'on site still governs before construction.',
        'Foundation type under each wing',
        'Existing roof comes off; confirm what is left at the plates',
        'Electrical service size at the main',
        'Oil tank age and containment',
        'Septic location and capacity against the added fixtures',
    ]


if __name__ == '__main__':
    print('SCHAD house: %d rooms' % len(house_rooms()))
    print('breezeway', breezeway())
