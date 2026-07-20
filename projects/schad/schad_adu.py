#!/usr/bin/env python3
"""SCHAD ADU — ADA-accessible studio build-out (224 SF, 14'x16').

[USER 2026-07-13] ADA-accessible ADU interior: enlarged floor plan with
furniture + bed, a HALF KITCHEN (cooktop, NO OVEN), accessible bath, and
an ADA-height electrical layout. Drawn on sheet A1.2 at 1/2" = 1'-0".

Local frame: SW corner of the ADU = (0,0); 14' wide (E-W) x 16' deep
(N-S). Entry door D4 on the NORTH wall at local x=7 (model cx=15).
Model placement: ADU is model x 8..22, y 32..48.

ADA basis: CBC 11A/11B + ANSI A117.1 residential accessible unit —
60" turning circles, 32" clear doors, 34" max counters w/ knee
clearance, 15"-48" reach range, roll-in shower. All layout is DESIGN
INTENT; field-verify clearances before construction.
"""

from __future__ import annotations

W, D = 14.0, 16.0     # ADU interior, feet


def adu_zones() -> list[dict]:
    """Functional zones (x,y,w,d local ft; label)."""
    return [
        {'name': 'SLEEPING', 'x': 0.0, 'y': 0.0, 'w': 8.0, 'd': 8.0},
        {'name': 'LIVING', 'x': 8.0, 'y': 0.0, 'w': 6.0, 'd': 8.0},
        {'name': 'KITCHEN (HALF)', 'x': 0.0, 'y': 10.0, 'w': 8.0,
         'd': 6.0},
        {'name': 'BATH (ROLL-IN)', 'x': 8.0, 'y': 9.0, 'w': 6.0,
         'd': 7.0},
    ]


def adu_furniture() -> list[dict]:
    """Furniture + bed (x,y,w,d local ft; label). 36" clear one side of
    bed for ADA transfer."""
    return [
        {'name': 'FULL BED', 'x': 0.5, 'y': 0.5, 'w': 4.5, 'd': 6.25},
        {'name': 'NIGHTSTAND', 'x': 5.2, 'y': 0.5, 'w': 1.5, 'd': 1.5},
        {'name': 'DRESSER (34"H)', 'x': 0.5, 'y': 7.0, 'w': 3.0,
         'd': 1.5},
        {'name': 'SOFA', 'x': 11.5, 'y': 0.5, 'w': 2.2, 'd': 6.0},
        {'name': 'TABLE (30" + 2 CH)', 'x': 8.5, 'y': 3.0, 'w': 2.5,
         'd': 2.5},
        {'name': 'CLOSET (ADA REACH)', 'x': 5.5, 'y': 6.7, 'w': 2.4,
         'd': 1.3},
    ]


def adu_kitchen() -> list[dict]:
    """Half kitchen along the north-west wall (y=16). NO OVEN [USER].
    34" max counter, knee clearance at sink + cooktop for forward
    approach."""
    return [
        {'name': 'BASE + CTR 34"', 'x': 0.0, 'y': 14.0, 'w': 8.0,
         'd': 2.0, 'kind': 'counter'},
        {'name': 'ADA SINK (KNEE CLR)', 'x': 1.0, 'y': 14.6, 'w': 2.0,
         'd': 1.4, 'kind': 'fixture'},
        {'name': 'COOKTOP 2-BURNER (NO OVEN)', 'x': 4.0, 'y': 14.6,
         'w': 2.0, 'd': 1.4, 'kind': 'fixture'},
        {'name': 'MICROWAVE (CTR, ADA HT)', 'x': 6.3, 'y': 14.5,
         'w': 1.5, 'd': 1.2, 'kind': 'appl'},
        {'name': 'U-CTR FRIDGE', 'x': 0.2, 'y': 12.2, 'w': 2.0, 'd': 2.0,
         'kind': 'appl'},
        {'name': 'UPPER CAB (LOWERED)', 'x': 0.0, 'y': 15.7, 'w': 8.0,
         'd': 0.3, 'kind': 'upper'},
    ]


def adu_bath() -> list[dict]:
    """Accessible bath: roll-in shower, WC w/ grab bars, wall-hung lav
    w/ knee clearance, 60" turn circle."""
    return [
        {'name': 'ROLL-IN SHOWER 3x5', 'x': 8.5, 'y': 11.0, 'w': 3.0,
         'd': 4.5, 'kind': 'shower'},
        {'name': 'WC (GRAB BARS)', 'x': 12.2, 'y': 13.5, 'w': 1.7,
         'd': 2.2, 'kind': 'wc'},
        {'name': 'LAV (WALL-HUNG, KNEE)', 'x': 11.8, 'y': 15.2, 'w': 2.0,
         'd': 0.8, 'kind': 'lav'},
    ]


def adu_clearances() -> list[dict]:
    """60" turning circles (r=2.5 ft) + door maneuvering."""
    return [
        {'cx': 9.5, 'cy': 5.0, 'r': 2.5, 'label': "60\" TURN"},
        {'cx': 10.3, 'cy': 12.5, 'r': 2.5, 'label': "60\" TURN (BATH)"},
        {'cx': 4.0, 'cy': 11.5, 'r': 2.5, 'label': "60\" TURN (KIT)"},
    ]


def adu_electrical() -> list[dict]:
    """ADA-height devices. sym: R=recept(15" AFF), GFCI, S=switch(44"),
    L=ceiling light, UC=undercabinet, V=vanity, EX=exhaust, SD=smoke/CO,
    P=panel, TS=stat, TV/DATA. All heights per ADA reach range."""
    d = []

    def a(sym, x, y, note=''):
        d.append({'sym': sym, 'x': x, 'y': y, 'note': note})
    # kitchen counter GFCI (above 34" ctr, reachable)
    a('GFCI', 2.0, 15.4, 'ctr GFCI')
    a('GFCI', 5.5, 15.4, 'ctr GFCI')
    a('R', 0.4, 12.0, 'fridge')
    a('R', 4.0, 15.4, 'cooktop 120V (induction/plug-in, no range ckt)')
    a('R', 6.3, 15.2, 'microwave')
    a('UC', 3.0, 15.6, 'under-cab LED')
    # sleeping/living receptacles @ 15" AFF, AFCI
    a('R', 0.3, 2.0, 'AFCI'); a('R', 0.3, 5.5, 'AFCI')
    a('R', 5.2, 0.4, 'nightstand AFCI'); a('R', 13.6, 3.0, 'AFCI')
    a('R', 13.6, 6.0, 'AFCI'); a('R', 8.5, 0.4, 'AFCI')
    a('TV', 13.6, 1.5, 'TV/DATA')
    # switches @ 44" AFF max
    a('S', 6.2, 15.2, '3-way entry')
    a('S', 0.4, 9.0, 'kitchen')
    a('S', 8.2, 9.5, 'bath (outside)')
    a('S', 13.6, 4.5, 'living')
    # lighting
    a('L', 4.0, 4.0, 'ceiling'); a('L', 10.0, 4.0, 'ceiling')
    a('L', 4.0, 12.0, 'kitchen ceiling')
    a('V', 12.5, 15.4, 'vanity light')
    a('L', 10.3, 12.5, 'bath ceiling (damp)')
    a('L', 6.7, 7.0, 'closet (auto)')
    a('EX', 9.0, 15.4, 'EF-1 bath 50 CFM -> exterior')
    # systems
    a('SD', 5.0, 5.0, 'smoke/CO hardwired interconnect')
    a('P', 0.2, 9.5, 'Subpanel B 100A [RB 21-23]')
    a('TS', 8.2, 2.0, 'radiant stat (ADA ht) - ADU zone')
    return d


def adu_ada_notes() -> list[str]:
    return [
        'ACCESSIBLE UNIT per CBC 11A + ANSI A117.1; all clearances '
        'FIELD-VERIFY before construction',
        'DOORS: 32" min clear (34-36" leaf), lever hardware, <5 lb '
        'force; 18" strike-side clear at entry (D4)',
        'TURNING: 60" dia circle in living, kitchen, and bath (shown)',
        'KITCHEN: 34" max counter; knee+toe clearance at ADA sink + '
        'cooktop (forward approach); NO OVEN [USER]; cooktop controls '
        'front-mounted; 50% shelving within 15-48" reach',
        'BATH: 60" roll-in shower w/ folding seat + hand shower on slide '
        'bar; WC 17-19" w/ side + rear grab bars; wall-hung lav w/ knee '
        'clearance + insulated traps; non-slip floor',
        'ELECTRICAL: receptacles 15" AFF min, switches 44" AFF max; all '
        'per ADA reach range; kitchen + bath GFCI; bedroom AFCI',
        'ALARMS: hardwired smoke/CO w/ battery backup + visual (ADA) '
        'notification; interconnect w/ main house',
        'FLOOR: no thresholds > 1/2"; slip-resistant finish; radiant '
        'heat (boiler-fed), ADU zone stat at accessible height',
    ]


if __name__ == '__main__':
    print('ADU ADA build-out: %d zones, %d furniture, %d kitchen, '
          '%d bath, %d devices, %d clearances, %d notes'
          % (len(adu_zones()), len(adu_furniture()), len(adu_kitchen()),
             len(adu_bath()), len(adu_electrical()),
             len(adu_clearances()), len(adu_ada_notes())))
