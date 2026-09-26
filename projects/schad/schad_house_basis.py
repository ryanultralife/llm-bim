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
        # Sizes are the scaled sheet. Origins are shifted so shared
        # walls touch instead of the boxes overlapping.
        _room('LIVING', 'Living', 'Main', 0, 0, 24, 16,
              'oil tank + firewood + F/P on the north wall'),
        _room('DECK', 'Wood Deck', 'Main', 0, 16, 26, 12,
              'south of the living room'),
        _room('STAIR-W', 'DN Deck', 'Main', 17, -5, 7, 5,
              '5\'-0" x 7\'-0" on the sheet'),
        _room('BATH-W', 'Bath', 'Main', 24, -9, 10, 9,
              'tub/shower + lav + WC'),
        _room('DINING', 'Dining', 'Main', 24, 0, 12, 14,
              '3x8 header at the living opening'),
        _room('MASTER', 'Master', 'Main', 36, -28, 20, 13,
              '2x6 walls; becomes den / office / workout'),
        _room('CLO-M', 'Clo.', 'Main', 36, -15, 9, 8, ''),
        _room('CHANGING', 'Changing', 'Main', 36, -7, 14, 12, ''),
        _room('MSTRBA', 'Mstr Ba', 'Main', 50, -15, 8, 10, 'tub + lav'),
        _room('STAIR', 'Stair', 'Main', 58, -12, 5, 7,
              'to the upper floor — KEEP'),
        _room('BATH1', 'Bath', 'Main', 63, -12, 9, 9,
              'tub/shower + lav + WC'),
        _room('GUEST', 'Guest', 'Main', 72, -12, 18, 13, ''),
        _room('CLO-G', 'Clo.', 'Main', 72, -12, 6, 5, 'inside the guest room'),
        _room('KITCHEN', 'Kitchen', 'Main', 36, 5, 12, 18,
              '4x12 header at the dining opening; south windows fill the wall'),
        _room('PORCH', 'Cov. Porch', 'Main', 48, 10, 22, 8,
              '8\'-0" deep, written on the sheet; concrete slab'),
        _room('LAUNDRY', 'Laundry', 'Main', 76, 1, 14, 16,
              '2\'-6" exterior door'),
    ]
    upper = [
        _room('GIRLS', 'Girls', 'Upper', 36, -7, 14, 10,
              'dormer; over the changing room'),
        _room('CLOSET', 'Clo.', 'Upper', 50, -4, 8, 6,
              'between the bedrooms'),
        _room('STAIRWELL', 'Stair', 'Upper', 58, -12, 5, 7,
              'same stair as the main floor — KEEP'),
        _room('BOYS', 'Boys', 'Upper', 72, -12, 14, 10,
              'dormer; over the guest room'),
        _room('ATTIC', 'Attic', 'Upper', 36, 4, 40, 8,
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


def _op(mark, kind, x1, y1, x2, y2, label, swing=''):
    return {
        'mark': mark, 'kind': kind,
        'x1': float(x1), 'y1': float(y1), 'x2': float(x2), 'y2': float(y2),
        'label': label, 'swing': swing,
    }


def existing_openings() -> list[dict]:
    """Openings on the tiled main plan.

    Sizes written on the sheet stay as written. A 3-foot passage door is
    the sheet's "3-0 doors TYP" where a room otherwise has no way in.
    The kitchen south wall is 12 feet, and the three written windows are
    3 + 5 + 4, so they fill that wall.
    """
    return [
        _op('HGD', 'door', 0, 4, 0, 12, '8\'-0" x 6\'-6"', 'out'),
        _op('HW6', 'window', 3, 0, 7, 0, '4\'-0" x 5\'-0"'),
        _op('HD-L', 'door', 10, 16, 13, 16, '3\'-0"', 'out'),
        _op('HW1', 'window', 43, -28, 49, -28, '6\'-0" x 5\'-0"'),
        _op('HW2', 'window', 36, -24, 36, -19, '5\'-0" x 6\'-8"'),
        _op('HW3', 'window', 58, -14, 58, -12, '2\'-0" x 2\'-0"'),
        _op('HW4', 'window', 90, -8, 90, -5, '3\'-0" x 4\'-6"'),
        _op('HW7a', 'window', 36, 23, 39, 23, '3\'-0" x 5\'-0"'),
        _op('HW7b', 'window', 39, 23, 44, 23, '5\'-0" x 5\'-0"'),
        _op('HW7c', 'window', 44, 23, 48, 23, '4\'-0" x 5\'-0"'),
        _op('HW5', 'window', 55, 18, 57, 18, '2\'-0" x 4\'-6" TYP'),
        _op('HW5b', 'window', 63, 18, 65, 18, '2\'-0" x 4\'-6"'),
        _op('HD-P', 'door', 70, 12, 70, 15, '3\'-0"', 'in'),
        _op('HW8a', 'window', 90, 6, 90, 9, '3\'-0" x 4\'-6"'),
        _op('HW8b', 'window', 78, 17, 82, 17, '4\'-0" x 3\'-0"'),
        _op('HD2', 'door', 84, 17, 86.5, 17, '2\'-6"', 'out'),
        _op('OP-D', 'cased', 24, 4, 24, 9, '3x8 HDR'),
        _op('OP-K', 'cased', 36, 8, 36, 14, '4x12 HDR'),
        _op('D-MB', 'door', 51, -15, 54, -15, '3\'-0"', 'in'),
        _op('D-CL', 'door', 38, -7, 40.5, -7, '2\'-6"', 'in'),
        _op('D-GS', 'door', 72, -8, 72, -5, '3\'-0"', 'in'),
        _op('D-LY', 'door', 80, 1, 83, 1, '3\'-0"', 'in'),
        _op('D-KP', 'door', 48, 12, 48, 15, '3\'-0"', 'in'),
    ]


def proposed_openings() -> list[dict]:
    """New work. Egress is a 3-foot by 4-foot casement, sill at 44 inches.
    Passage doors are 3-foot. Bath windows are high awnings.
    """
    return [
        _op('E1', 'window', 36, -12, 36, -9, '3\'-0" x 4\'-0" EGRESS'),
        _op('E2', 'window', 88, -12, 88, -9, '3\'-0" x 4\'-0" EGRESS'),
        _op('E3', 'window', 40, 12, 43, 12, '3\'-0" x 4\'-0" EGRESS'),
        _op('E4', 'window', 64, 12, 67, 12, '3\'-0" x 4\'-0" EGRESS'),
        _op('NE', 'window', 38, -52, 44, -52, '6\'-0" x 5\'-0"'),
        _op('NE2', 'window', 36, -48, 36, -45, '3\'-0" x 5\'-0" EGRESS'),
        _op('P1', 'door', 40, -5, 43, -5, '3\'-0"', 'in'),
        _op('P2', 'door', 78, -5, 81, -5, '3\'-0"', 'in'),
        _op('P3', 'door', 40, 1, 43, 1, '3\'-0"', 'in'),
        _op('P4', 'door', 64, 1, 67, 1, '3\'-0"', 'in'),
        _op('PB', 'door', 52, -36, 52, -33, '3\'-0"', 'in'),
        _op('PW', 'door', 52, -48, 52, -45.5, '2\'-6"', 'in'),
        _op('BA1', 'window', 52, -13, 54, -13, '2\'-0" x 3\'-0" AWN'),
        _op('BA2', 'window', 66, -13, 68, -13, '2\'-0" x 3\'-0" AWN'),
        _op('BD', 'door', 42, -28, 45, -28, '3\'-0"', 'in'),
    ]


def house_symbols() -> list[dict]:
    """Fixtures and stair marks. Not dimensioned on the sheet."""
    return [
        {'kind': 'fp', 'x': 8, 'y': 0.3, 'w': 5, 'd': 1.6, 'label': 'F/P'},
        {'kind': 'note', 'x': 1, 'y': -1.2, 'label': 'OIL + WOOD'},
        {'kind': 'stair', 'x': 58, 'y': -12, 'w': 5, 'd': 7, 'label': 'UP  KEEP'},
        {'kind': 'stair', 'x': 17, 'y': -5, 'w': 7, 'd': 5, 'label': 'DN'},
        {'kind': 'tub', 'x': 51, 'y': -14, 'w': 2.5, 'd': 5, 'label': ''},
        {'kind': 'tub', 'x': 25, 'y': -8, 'w': 2.5, 'd': 5, 'label': ''},
        {'kind': 'tub', 'x': 64, 'y': -11, 'w': 2.5, 'd': 5, 'label': ''},
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
        {'name': 'BED 1', 'x': 36, 'y': -17, 'w': 14, 'd': 12,
         'note': 'egress west; 3-0 to hall'},
        {'name': 'BATH 1', 'x': 50, 'y': -13, 'w': 8, 'd': 8,
         'note': 'high awning'},
        {'name': 'STAIR (KEEP)', 'x': 58, 'y': -12, 'w': 5, 'd': 7,
         'note': 'existing stair'},
        {'name': 'BATH 2', 'x': 63, 'y': -13, 'w': 9, 'd': 8,
         'note': 'high awning'},
        {'name': 'BED 2', 'x': 72, 'y': -17, 'w': 16, 'd': 12,
         'note': 'egress east'},
        {'name': 'HALL', 'x': 36, 'y': -5, 'w': 52, 'd': 6, 'note': ''},
        {'name': 'BED 3', 'x': 36, 'y': 1, 'w': 14, 'd': 11,
         'note': 'egress south'},
        {'name': 'OPEN BELOW', 'x': 50, 'y': 1, 'w': 8, 'd': 8,
         'note': 'rail at the entry'},
        {'name': 'BED 4', 'x': 58, 'y': 1, 'w': 16, 'd': 11,
         'note': 'egress south'},
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


# Garage-frame location of house-local (0, 0). +x east, +y on the sheet is south.
# East face at local x=90 meets the breezeway west end (garage x=-18).
# Local y=9 (laundry) meets the breezeway center (garage y=16).
HOUSE_ORIGIN_FT = (-108.0, 25.0)
HOUSE_PLATE_FT = 8.0          # assumed; the sheet does not give a plate height
HOUSE_FLOOR_TO_FLOOR_FT = 9.0  # assumed main-to-upper


def to_site_ft(x: float, y: float) -> tuple[float, float]:
    ox, oy = HOUSE_ORIGIN_FT
    return ox + x, oy - y


def wall_segments(rooms: list[dict], *, twox6: set[str] | None = None) -> list[dict]:
    """Unique wall pieces from room boxes. Shared edges are interior."""
    twox6 = twox6 or set()
    horiz: dict[float, list[tuple[float, float, str]]] = {}
    vert: dict[float, list[tuple[float, float, str]]] = {}
    for r in rooms:
        x, y, w, d = r["x"], r["y"], r["w"], r["d"]
        name = r.get("id") or r["name"]
        horiz.setdefault(round(y, 2), []).append((x, x + w, name))
        horiz.setdefault(round(y + d, 2), []).append((x, x + w, name))
        vert.setdefault(round(x, 2), []).append((y, y + d, name))
        vert.setdefault(round(x + w, 2), []).append((y, y + d, name))

    def emit(groups, horizontal: bool) -> list[dict]:
        out = []
        for fixed, spans in groups.items():
            cuts = sorted({p for a, b, _n in spans for p in (min(a, b), max(a, b))})
            for i in range(len(cuts) - 1):
                a, b = cuts[i], cuts[i + 1]
                if b - a < 0.4:
                    continue
                mid = (a + b) / 2
                owners = [
                    n for lo, hi, n in spans
                    if min(lo, hi) - 0.05 <= mid <= max(lo, hi) + 0.05
                ]
                if not owners:
                    continue
                interior = len(owners) >= 2
                if (not interior) and any(n in twox6 for n in owners):
                    type_id, thick = "W-EXT-2x6-BNB", 6.5 / 12
                elif not interior:
                    type_id, thick = "W-EXT-2x6-BNB", 3.5 / 12
                else:
                    type_id, thick = "W-INT-2x4", 3.5 / 12
                if horizontal:
                    x1, y1, x2, y2 = a, fixed, b, fixed
                else:
                    x1, y1, x2, y2 = fixed, a, fixed, b
                out.append({
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "kind": "interior" if interior else "exterior",
                    "type_id": type_id, "thick": thick,
                })
        return out

    return emit(horiz, True) + emit(vert, False)


def _skip_outdoor(rooms: list[dict]) -> list[dict]:
    skip = {"DECK", "PORCH", "STAIR-W"}
    return [r for r in rooms if r.get("id") not in skip and "Deck" not in r["name"] and "Porch" not in r["name"]]


def existing_main_walls() -> list[dict]:
    rooms = _skip_outdoor([r for r in house_rooms() if r["level"] == "Main"])
    return wall_segments(rooms, twox6={"MASTER"})


def existing_upper_walls() -> list[dict]:
    rooms = [r for r in house_rooms() if r["level"] == "Upper"]
    return wall_segments(rooms)


def proposed_upper_walls() -> list[dict]:
    return wall_segments(concept_upper(), twox6=set())


def suite_walls() -> list[dict]:
    return wall_segments(concept_suite(), twox6={"MASTER BED"})


if __name__ == '__main__':
    print('SCHAD house: %d rooms' % len(house_rooms()))
    print('breezeway', breezeway())
