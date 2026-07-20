#!/usr/bin/env python3
"""SCHAD MEP design basis + calcs + device layouts (Phase 1 garage/ADU).

Electrical service/feeder calc (NEC 220), circuit + device layout;
plumbing DFU/WSFU sizing (CPC tables, approximate); mechanical radiant
loop + ventilation sizing. Positions are DESIGN-INTENT (schematic,
coordinate in field); values marked (ASSUMED) need confirmation.
Sources: [RB] MEP sheets (panel schedule, fixtures, equipment),
[HANDOFF] (200A service, heat pumps — Q-WH), [BOM].
"""

from __future__ import annotations

import schad_design_basis as basis


# ---- electrical -----------------------------------------------------------
def electrical_service_calc() -> list[str]:
    adu_general = 224 * 3.0                       # VA, NEC 220.12
    adu_sa = 2 * 1500.0 + 1500.0                  # small appliance + laundry
    adu_sub = adu_general + adu_sa                # 5,172 VA
    wh = 4500.0
    rf = 5500.0                                   # RF-1 radiant [RB]
    adu_conn = adu_sub + wh
    adu_demand = min(adu_conn, 10000.0) + max(0.0, adu_conn - 10000.0) * .4
    ev = 9600.0                                   # NEMA 14-50 @ 40A cont
    shop240 = 30 * 240.0                          # workshop 240V ckt
    gar_lts = 2000.0
    gar_rcpt = 3000.0
    soffit = 500.0                                # soffit lighting [USER]
    hp2 = 4500.0 * 0.75      # 2nd HPWH backup element, NEC 220.53 75%
    total = (adu_demand + ev * 1.25 + shop240 + gar_lts + gar_rcpt + rf
             + soffit + hp2)
    amps = total / 240.0
    return [
        'ADU (NEC 220.82-style): general %d + SA/laundry %d + HPWH '
        'backup-element %d = %d VA conn -> demand %d VA (~%dA on 100A '
        'subfeed OK)' % (adu_general, adu_sa, wh, adu_conn + 0,
                         adu_demand, adu_demand / 240),
        'GARAGE: EV 9.6 kVA (x1.25 cont) + workshop 7.2 + lights 2.0 + '
        'soffit ltg 0.5 + receptacles 3.0 + radiant 5.5 + HPWH-1 backup '
        '%.1f kVA (75%% per 220.53)' % (hp2 / 1000.0),
        'WATER HEATING = 2x 83-gal HEAT-PUMP tanks [USER 2026-07-12]; '
        'compressor draw ~0.7 kW each, backup elements sized above '
        '(conservative)',
        'TOTAL DEMAND ~%.1f kVA -> %.0f A @ 240V vs 200A service -> OK '
        '(%.0f%% loaded)' % (total / 1000.0, amps, amps / 200.0 * 100),
        'FEEDERS: service 200A; ADU subpanel 100A [RB ckt 21-23]; EV 50A '
        '[RB 13/15]; workshop 30A-240V [RB 14/16]',
        '(ASSUMED): EV load 40A continuous; verify charger + HPWH specs.',
    ]


def electrical_devices() -> list[dict]:
    """Schematic device layout (x, y feet; garage origin). sym legend:
    R=recept 120 GFCI, R240=240V, EV=NEMA14-50, L=luminaire, S=switch,
    P=panel, SD=smoke/CO, EF=exhaust fan."""
    d = []

    def add(sym, x, y, ckt, note=''):
        d.append({'sym': sym, 'x': x, 'y': y, 'ckt': ckt, 'note': note})
    # panels
    add('P', 39.0, 47.4, 'SVC', 'Panel A 200A (workshop N wall)')
    add('P', 21.0, 47.4, '21-23', 'ADU subpanel B 100A (mech)')
    # garage receptacles (GFCI) — >=1 per bay, NEC 210.52(G)
    for x, y, c in ((0.6, 8.0, '2/4'), (0.6, 24.0, '2/4'),
                    (47.4, 8.0, '10/12'), (47.4, 24.0, '10/12'),
                    (8.0, 31.4, '2/4'), (24.0, 31.4, '6/8'),
                    (40.0, 31.4, '10/12')):
        add('R', x, y, c)
    add('EV', 47.4, 4.0, '13/15', 'NEMA 14-50')
    add('R240', 39.5, 40.0, '14/16', 'workshop machine outlet')
    # garage/workshop luminaires (2 rows per bay + workshop)
    for x in (8.0, 24.0, 40.0):
        for y, c in ((10.7, '1/3'), (21.3, '5/7' if x == 24 else '9/11')):
            add('L', x, y, c, 'LED high-bay')
    add('L', 27.0, 40.0, '9/11')
    add('L', 36.0, 40.0, '9/11')
    add('S', 26.5, 32.5, '1/3', '3-way at D6')
    # ADU
    for x, y in ((9.0, 47.4), (11.5, 47.4)):
        add('R', x, y, 'B-SA', 'kitchen counter SA')
    for x, y in ((8.6, 36.0), (14.0, 33.6), (21.4, 40.0)):
        add('R', x, y, 'B-GEN', 'AFCI')
    add('SD', 15.0, 40.0, 'B-SD', 'smoke/CO hardwired')
    add('EF', 12.0, 46.0, 'B-EF', 'bath fan 50 CFM')
    add('L', 15.0, 42.0, 'B-LT')
    # exterior sconces at man doors
    add('L', 15.0, 48.5, 'B-LT', 'ext sconce D4')
    add('S', 31.0, 48.4, '9/11', 'ext sconce D5')
    # soffit lighting in the 18" eaves [USER 2026-07-12]: front eave over
    # the door bays + rear eave at ADU/workshop entries
    for x in (4.0, 12.0, 20.0, 28.0, 36.0, 44.0):
        add('L', x, -0.9, '1/3', 'soffit recessed')
    add('L', 15.0, 48.9, 'B-LT', 'soffit recessed')
    add('L', 31.0, 48.9, '9/11', 'soffit recessed')
    return d


# ---- plumbing ----------------------------------------------------------------
def plumbing_calc() -> list[str]:
    dfu = {'WC': 3.0, 'LAV': 1.0, 'SHR': 2.0, 'KS': 2.0, 'US': 2.0}
    wsfu = {'WC': 2.5, 'LAV': 1.0, 'SHR': 2.0, 'KS': 1.5, 'US': 1.5,
            'HB x2': 5.0}
    return [
        'DFU total %.0f (WC3+LAV1+SHR2+KS2+US2) -> 3" building drain @ '
        '1/4"/ft (CPC 703, 42 DFU cap) OK; 2" vents' % sum(dfu.values()),
        'WSFU total %.1f -> 3/4" service/main OK to ~60 ft dev. length '
        'at 46-60 psi (CPC 610) — (ASSUMED) verify WELL system pressure '
        'tank setting on site' % sum(wsfu.values()),
        'WH: 50-gal electric [RB] in ADU mech closet; T&P to exterior; '
        'seismic straps x2 (Q-WH: HANDOFF heat-pump option open)',
        'DWV: schedule 40 ABS/PVC; slope 1/4"/ft; cleanouts at ends of '
        'runs + grade; septic connection — verify capacity for added '
        'fixtures (see site/field-verify list)',
        'Radiant slab loops are CLOSED LOOP (no potable cross-connect); '
        'backflow at fill per CPC 603',
    ]


def plumbing_fixtures_layout() -> list[dict]:
    return [
        {'sym': 'KS', 'x': 10.0, 'y': 47.0, 'note': 'ADU kitchen sink'},
        {'sym': 'LAV', 'x': 12.2, 'y': 46.6, 'note': 'ADU bath'},
        {'sym': 'WC', 'x': 13.4, 'y': 46.6, 'note': 'ADU bath'},
        {'sym': 'SHR', 'x': 15.0, 'y': 46.6, 'note': 'ADU shower'},
        {'sym': 'US', 'x': 23.0, 'y': 33.6, 'note': 'workshop utility'},
        {'sym': 'HB', 'x': 0.4, 'y': 16.0, 'note': 'hose bib W'},
        {'sym': 'HB', 'x': 47.6, 'y': 16.0, 'note': 'hose bib E'},
        # Mech/Bath room fixtures [USER 2026-07-13]
        {'sym': 'WC', 'x': 46.5, 'y': 30.5, 'note': '1/2 bath WC'},
        {'sym': 'LAV', 'x': 44.5, 'y': 31.0, 'note': '1/2 bath lav'},
        {'sym': 'DW', 'x': 40.5, 'y': 30.0, 'note': 'DOG WASH basin + '
         'floor drain'},
        {'sym': 'FD', 'x': 41.5, 'y': 27.0, 'note': 'floor drain (mech)'},
        {'sym': 'WH', 'x': 42.0, 'y': 26.0, 'note': 'DHW tank (Q-DHW)'},
    ]


# ---- mechanical -----------------------------------------------------------------
def mechanical_calc() -> list[str]:
    s = basis.build_scalars()
    gar_sf = 1850.0                     # radiant slab area [BOM]
    adu_sf = s['area_adu']
    total_sf = gar_sf + adu_sf
    pex_lf = total_sf / 0.75           # 9" OC -> 1.33 lf/sf
    loops = int(pex_lf // 300.0) + 1
    design_loss = total_sf * 25.0      # BTU/h @ ~25 BTU/SF (ASSUMED)
    return [
        'RADIANT: 1/2" PEX @ 9" OC [RB]: ~%d LF -> %d loops @ <=300 ft; '
        'manifold w/ flow meters in the new MECH/BATH room' % (pex_lf,
                                                               loops),
        'HEAT SOURCE [USER 2026-07-13]: 2x PROPANE BOILERS B-1/B-2 '
        '(sealed-combustion, direct-vent, lead/lag) in Mech/Bath feed '
        'the radiant loops. Design loss ~%d MBH over %d SF (~25 BTU/SF '
        'ASSUMED); ~52 MBH/boiler input — confirm final size w/ Manual-J'
        % (design_loss / 1000.0, total_sf),
        'DHW [USER 2026-07-13]: TANKLESS/INSTANT PROPANE water heater '
        'WH-1 + small (~10 gal) buffer tank, direct-vent, in Mech/Bath',
        'WELL PRESSURE VESSEL PT-1 = 60-GAL VERTICAL bladder tank + pump '
        'controls in Mech/Bath [USER 2026-07-13]',
        'PROPANE: EXISTING 250-gal tank [USER 2026-07-13] (expandable, '
        'room for a 2nd) w/ buried line to Mech/Bath; sediment trap + '
        'shutoff at each appliance; direct-vent thru exterior wall '
        '(combustion air + flue per mfr/CMC); CO alarm. Verify '
        'vaporization rate + regulator/line size for boiler+tankless '
        'peak (lead/lag boilers + intermittent tankless ease demand)',
        'MECH/BATH ROOM: FLOOR DRAIN for dog wash + boiler/T&P relief; '
        '1/2-bath EF-1; propane appliances direct-vent (no interior '
        'combustion-air louver needed w/ sealed combustion)',
        'ADU: radiant %d SF ~ %.1f MBH zone; programmable stats per '
        'zone [RB]; kitchen recirc hood (ASSUMED)'
        % (adu_sf, adu_sf * 25.0 / 1000.0),
        'ENERGY: Title 24-2022 [RB]; R-10 under ADU slab [RB]; slab edge '
        'R-15 (HANDOFF)',
    ]


def mech_equipment_layout() -> list[dict]:
    # Mech/Bath room x39-48, y20-32 [USER 2026-07-13]
    return [
        {'sym': 'B', 'x': 40.0, 'y': 22.0, 'note': 'B-1 propane boiler '
         '(direct-vent)'},
        {'sym': 'B', 'x': 40.0, 'y': 24.0, 'note': 'B-2 propane boiler'},
        {'sym': 'PT', 'x': 42.0, 'y': 21.0, 'note': 'PT-1 well pressure '
         'vessel - 60gal VERTICAL'},
        {'sym': 'MAN', 'x': 40.5, 'y': 26.0, 'note': 'radiant manifold'},
        {'sym': 'WH', 'x': 42.5, 'y': 26.0, 'note': 'WH-1 tankless '
         'propane + buffer'},
        {'sym': 'G', 'x': 47.6, 'y': 22.0, 'note': 'propane line in + '
         'shutoff (from ext tank)'},
        {'sym': 'T', 'x': 26.0, 'y': 16.0, 'note': 'stat - garage zone'},
        {'sym': 'T', 'x': 16.0, 'y': 40.0, 'note': 'stat - ADU zone'},
        {'sym': 'EF', 'x': 46.5, 'y': 31.0, 'note': 'EF-1 1/2 bath'},
        {'sym': 'CO', 'x': 41.0, 'y': 25.0, 'note': 'CO alarm - boiler'},
    ]


if __name__ == '__main__':
    for ln in (electrical_service_calc() + plumbing_calc()
               + mechanical_calc()):
        print(' *', ln)
    print('devices:', len(electrical_devices()), '| plumb fixtures:',
          len(plumbing_fixtures_layout()), '| mech:',
          len(mech_equipment_layout()))
