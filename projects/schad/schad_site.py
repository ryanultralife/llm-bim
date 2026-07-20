#!/usr/bin/env python3
"""SCHAD site design basis — 3730 Chandler Rd, Quincy CA.

v2 (2026-07-13): GEOREFERENCED. Parcel geometry from the Plumas County
Parcels feature service (7/2025 layer — county notes it is informational,
NOT a legal survey); building/driveway positions measured from Esri World
Imagery aerial (~0.23 m/px, fetched 2026-07-13). Geocoder pin for the
address was ~800 ft off; the contract APN 005-350-001 parcel was located
via county GIS and confirmed against the [HPLAN] house massing (angled
master wing visible in the aerial).

FACTS:
  APN 005-350-001 = 0.63 ac, ~263 ft (E-W) x ~112 ft (N-S)
  Surroundings: USFS parcel 005-330-USA (6,995 ac) + large private
  parcels (005-350-011 12.6 ac etc.); meadow west; Chandler Rd ~300 ft NE
  House sits in the SW third; open thinned ground east = garage site
  KEY CONFLICT: the 30/40 ft setback assumption CANNOT hold on a 112 ft
  deep lot -> Q-SETBACK (confirm zoning setbacks w/ Plumas planning)

Local frame: garage SW corner = (0,0), +x East, +y North (model frame).
Garage anchor chosen at parcel-local (150 ft E, 35 ft N of the parcel SW
corner) — centered in the open east yard; ADJUSTABLE pending setbacks.
"""

from __future__ import annotations

import math

# WGS84 parcel ring, Plumas County GIS 7/2025 (lon, lat), closed
PARCEL_RING_LL = [
    (-120.9121329, 39.9684127),   # SE
    (-120.9130736, 39.9683972),   # SW
    (-120.9130690, 39.9687155),   # NW
    (-120.9121281, 39.9687231),   # NE
    (-120.9121329, 39.9684127),
]
# garage SW anchor (parcel-local 150 E, 35 N of SW corner)
ANCHOR_LL = (-120.9125376, 39.9684932)
_LAT0 = 39.96855
FT_PER_DEG_LON = math.cos(math.radians(_LAT0)) * 111320.0 * 3.28084
FT_PER_DEG_LAT = 111132.0 * 3.28084


def _ft(lon: float, lat: float) -> tuple:
    """WGS84 -> model-frame feet (garage SW = origin)."""
    return (round((lon - ANCHOR_LL[0]) * FT_PER_DEG_LON, 1),
            round((lat - ANCHOR_LL[1]) * FT_PER_DEG_LAT, 1))


def site_basis() -> dict:
    ring = [_ft(lo, la) for lo, la in PARCEL_RING_LL]
    return {
        'apn': '005-350-001 (0.63 ac, ~263\' x ~112\')',
        'address': '3730 Chandler Rd, Quincy, CA 95971',
        'latlon': (39.96850, -120.91260),
        'jurisdiction': 'Plumas County Building Dept.',
        'zone': 'R-1 [RB] — CONFIRM for this parcel (Q-SETBACK)',
        'sources': 'Parcel: Plumas County GIS 7/2025 (informational, not '
                   'a survey). Features: Esri World Imagery ~0.23 m/px, '
                   'read 2026-07-13. Survey supersedes.',
        'parcel_ring': ring,
        'setback_tbd': True,   # 30/40 assumption invalid on 112' depth
        'garage': {'x': 0.0, 'y': -2.0, 'w': 48.0, 'd': 50.0,
                   'label': 'NEW GARAGE / ADU / WORKSHOP (2,080 SF) — '
                            'placement pending setback confirm'},
        'house': {'x': -130.0, 'y': -35.0, 'w': 105.0, 'd': 65.0,
                  'label': 'EXISTING RESIDENCE (aerial-derived envelope '
                           'incl. decks — field verify)',
                  'assumed': False},
        'driveway': {'pts': [(-95.0, 30.0), (-40.0, 25.0), (10.0, 5.0),
                             (24.0, -2.0)],
                     'label': 'existing drive/parking N of house, extend '
                              'to garage apron (aerial)'},
        'access': {'pts': [(-60.0, -300.0), (-75.0, -120.0),
                           (-95.0, -40.0), (-95.0, 30.0)],
                   'label': 'access lane from S (to Chandler Rd via '
                            'compound lane) — VERIFY easement/route'},
        'utilities': [
            {'sym': 'E', 'x': -128.0, 'y': -5.0,
             'label': 'ELECT MAIN at house W wall [HPLAN]; new feeder '
                      'to garage Panel A (trench ~150\')'},
            {'sym': 'W', 'x': -60.0, 'y': 45.0,
             'label': 'WELL (loc UNKNOWN — locate + 50/100\' seps)'},
            {'sym': 'S', 'x': -30.0, 'y': -60.0,
             'label': 'SEPTIC (loc UNKNOWN — locate; capacity re-check '
                      'for ADU + house addition)'},
            {'sym': 'LP', 'x': 62.0, 'y': 10.0,
             'label': 'EXISTING 250-GAL PROPANE TANK [USER 2026-07-13] '
                      '(expandable — room for 2nd tank); locate on '
                      'survey; buried line to Mech/Bath (E side Bay 3); '
                      'verify vaporization + line size for boiler+'
                      'tankless load; NFPA 58 setbacks'},
        ],
        'context': [
            'Surrounded by USFS parcel 005-330-USA (6,995 ac) — '
            'defensible space per PRC 4291 CRITICAL',
            'Meadow/ranch parcels west; Chandler Rd ~300 ft NE '
            '(paved); neighbors 005-350-011 (12.6 ac) etc.',
            'OWNERS ALSO HOLD THE ADJACENT PARCEL [USER 2026-07-13] — '
            'identify APN w/ assessor (candidates: 005-350-011 12.6 ac '
            'adjoining). Opens setback strategies: lot-line adjustment '
            'or merger instead of squeezing the 112\' depth',
        ],
        'notes': [
            'PARCEL LINES FROM COUNTY GIS — NOT A SURVEY; commission '
            'survey before permit site plan is final',
            'SETBACKS TBD (Q-SETBACK): 112\' lot depth cannot take '
            '30\'+40\'; confirm zone setbacks w/ Plumas planning; '
            'garage anchor (150\',35\') adjusts accordingly',
            'GRADING: slope slab 1/8"/ft to doors; perimeter drain to '
            'daylight [RB]; site slopes gently W toward meadow (aerial)',
            'FIRE: PRC 4291 defensible space; Class A roof (metal) both '
            'buildings; address posting per county std',
        ],
        'aerial': 'C1_1_aerial.png',
    }


if __name__ == '__main__':
    s = site_basis()
    print('APN', s['apn'])
    print('parcel ring (model-frame ft):')
    for p in s['parcel_ring']:
        print('  ', p)
