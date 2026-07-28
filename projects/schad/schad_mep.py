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
        'FEEDERS: service 200A; ADU subpanel 100A [RB ckt 21-23] in %s" '
        'EMT; EV 50A [RB 13/15] in %s" EMT; workshop 30A-240V [RB 14/16] '
        'in %s" EMT (NEC Ch.9 fill via mep_sizing — the same source '
        'route_mep draws)' % (_feeder_trade(100.0), _feeder_trade(50.0),
                              _feeder_trade(30.0)),
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
# Fixture-unit tables [RB MEP-201 + USER 2026-07-13] — the ONLY fixture-unit
# source; plumbing_calc() text and route_mep() geometry both derive from these
# (drawing == takeoff == calc).
_DCW_WSFU = {'WC': 2.5, 'LAV': 1.0, 'SHR': 2.0, 'KS': 1.5, 'US': 1.5,
             'HB x2': 5.0}
_SAN_DFU = {'WC': 3.0, 'LAV': 1.0, 'SHR': 2.0, 'KS': 2.0, 'US': 2.0}
# CPC 703 building drain (DFU-based; single source for calc text + routing —
# DWV sizing is a code-table lookup, not a mep_sizing hydraulic calc)
_SAN_MAIN_NPS = '3'


def _dcw_main_sizing() -> dict:
    """DCW service/main sizing — the ONE source for calc text AND routing.

    Hunter's-curve WSFU -> flow + velocity-limit copper size from
    ``llmbim_core.mep_sizing`` (engineering estimate, not a stamped design).
    """
    from llmbim_core import mep_sizing as sz

    return sz.size_pipe(sz.wsfu_to_lps(sum(_DCW_WSFU.values())),
                        material='copper')


def _feeder_trade(amps: float) -> str:
    """Feeder EMT trade size (NEC Ch.9 fill) — one source for calc + routing."""
    from llmbim_core import mep_sizing as sz

    return str(sz.feeder_conduit(amps)['trade_size'])


def plumbing_calc() -> list[str]:
    dcw = _dcw_main_sizing()
    return [
        'DFU total %.0f (WC3+LAV1+SHR2+KS2+US2) -> %s" building drain @ '
        '1/4"/ft (CPC 703, 42 DFU cap) OK; 2" vents'
        % (sum(_SAN_DFU.values()), _SAN_MAIN_NPS),
        'WSFU total %.1f -> %.2f L/s (Hunter) -> %s" copper service/main '
        '(%.2f m/s <= 2.4 m/s; sized by mep_sizing — the same source '
        'route_mep draws) OK to ~60 ft dev. length at 46-60 psi (CPC '
        '610) — (ASSUMED) verify WELL system pressure tank setting on '
        'site' % (sum(_DCW_WSFU.values()), dcw['flow_lps'], dcw['nps'],
                  dcw['velocity_ms']),
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


# ---- routed systems (real geometry, sized from mep_sizing) ------------------
_FT_MM = 304.8


def _ft(v: float) -> float:
    return float(v) * _FT_MM


# Catalog part where an exact match exists; other fixtures are honest generic
# boxes (category 'fixture' -> IfcFlowTerminal in the IFC), sizes ASSUMED.
_FIXTURE_PART = {'WC': 'PT-PLB-WC-FLOOR', 'LAV': 'PT-PLB-LAV-WALL',
                 'FD': 'PT-PLB-FD-3'}


def route_mep(p: object, *, level: str = 'L1') -> dict:
    """Route real MEP systems through the Manhattan A* engine (mep_autoroute).

    Every run goes through ``p.mep_autoroute`` — axis-aligned (orthogonal)
    segments with elbows at every bend, wall/equipment obstacles respected via
    the grid A*; where walls fully enclose a target the engine honestly falls
    back to an orthogonal dogleg (the run penetrates the wall — schematic).
    NO diagonal plan runs are placed. Real flow-terminal elements (category
    ``fixture`` -> IfcFlowTerminal) are placed at the plumbing-fixture basis
    positions and used as route endpoints, so the routed graph
    (``model.meta['mep_graph']``/``connections``) links terminals to runs and
    feeds connections.json + IfcDistributionPort emission in the IFC export.

    Sizes come from ``llmbim_core.mep_sizing`` through the SAME module-level
    helpers the calc text prints (``_dcw_main_sizing`` / ``_feeder_trade`` /
    ``_SAN_MAIN_NPS``) — drawing == takeoff == calc. Fire protection is NOT
    routed per the basis (CRC R313 detached-accessory exemption,
    ``build_notes()['fire_protection']``); the exemption is threaded into
    ``model.meta['fire_basis_note']`` so the empty fire takeoff carries the
    reason. Schematic — coordinate in field. Additive: call once after
    equipment/fixtures are placed.
    """
    from llmbim_core import mep_sizing as sz
    from llmbim_core.errors import ValidationError

    n = {'pipe': 0, 'duct': 0, 'conduit': 0, 'fitting': 0, 'terminal': 0,
         'runs': 0}

    def _pt(a):
        # (x, y) feet -> mm, or pass an element id through untouched
        return a if isinstance(a, str) else (_ft(a[0]), _ft(a[1]))

    def AUTO(kind, a, b, *, system, name, nps='2', material='copper',
             z=None, w=400.0, h=250.0, trade='3/4'):
        try:
            res = p.mep_autoroute(
                level=level, start=_pt(a), end=_pt(b), kind=kind, nps=nps,
                material=material, system=system, z0_mm=z, width_mm=w,
                height_mm=h, trade_size=trade, name=name)
        except ValidationError:
            return None  # endpoints coincide (fixture sits ON the main)
        n[kind] += len(res['segment_ids']) + (1 if res.get('riser_id') else 0)
        n['fitting'] += len(res['fitting_ids'])
        n['runs'] += 1
        return res

    def TEE(nps: str, at: tuple[float, float], material: str, system: str) -> None:
        p.place_fitting(level=level, fitting_type='tee', nps=nps,
                        origin=(_ft(at[0]), _ft(at[1])), material=material,
                        system=system)
        n['fitting'] += 1

    # ---- flow terminals at the plumbing-fixture basis positions --------------
    terminals: dict[tuple[str, float, float], str] = {}
    for fi in plumbing_fixtures_layout():
        sym = str(fi['sym'])
        if sym == 'WH':
            continue  # DHW tank already placed as Mech/Bath equipment (WH-1)
        origin = (_ft(fi['x']), _ft(fi['y']))
        pid = _FIXTURE_PART.get(sym)
        if pid:
            eid = p.place_part(level=level, part_id=pid, origin=origin,
                               name=f"{sym}: {fi['note']}"[:60])
        else:
            r = p.op('create_generic', category='fixture', level=level,
                     name=f"{sym}: {fi['note']}"[:60],
                     params={'origin_mm': [origin[0], origin[1]],
                             'size_mm': [500.0, 500.0, 400.0],
                             'shape': 'box', 'z0_mm': 0.0, 'system': 'DCW',
                             'fixture': sym, 'size_assumed': True})
            eid = str(r['id'])
        terminals[(sym, float(fi['x']), float(fi['y']))] = eid
        n['terminal'] += 1

    def T(sym: str, x: float, y: float) -> str:
        return terminals[(sym, x, y)]

    mech = (42.0, 26.0)          # Mech/Bath plant node (ft)
    panel_a = (39.0, 47.4)       # 200A service
    panel_b = (21.0, 47.4)       # ADU 100A subpanel

    # ---- DOMESTIC COLD WATER (copper), main sized from total WSFU ------------
    dcw_nps = str(_dcw_main_sizing()['nps'])
    AUTO('pipe', (42.0, 21.0), mech, nps=dcw_nps, system='DCW',
         name='DCW main from PT-1', z=600.0)
    AUTO('pipe', mech, (42.0, 47.0), nps=dcw_nps, system='DCW',
         name='DCW riser to spine', z=2900.0)
    AUTO('pipe', (42.0, 47.0), (9.0, 47.0), nps=dcw_nps, system='DCW',
         name='DCW spine (rear wall)', z=2600.0)
    for fx, fy, label in ((10.0, 47.0, 'KS'), (12.2, 46.6, 'LAV'),
                          (13.4, 46.6, 'WC'), (15.0, 46.6, 'SHR')):
        AUTO('pipe', (fx, 47.0), T(label, fx, fy), nps='1/2', system='DCW',
             name=f'DCW branch {label}', z=2600.0)
        TEE(dcw_nps, (fx, 47.0), 'copper', 'DCW')
    for a, b, label in ((mech, T('LAV', 44.5, 31.0), '1/2-bath lav'),
                        (T('LAV', 44.5, 31.0), T('WC', 46.5, 30.5),
                         '1/2-bath WC'),
                        (mech, T('DW', 40.5, 30.0), 'dog wash'),
                        (mech, T('US', 23.0, 33.6), 'workshop util'),
                        (mech, T('HB', 0.4, 16.0), 'hose bib W'),
                        (mech, T('HB', 47.6, 16.0), 'hose bib E')):
        AUTO('pipe', a, b, nps='1/2', system='DCW',
             name=f'DCW branch {label}', z=2600.0)

    # ---- SANITARY DWV (ABS/PVC), building drain + fixture branches -----------
    AUTO('pipe', (15.0, 46.6), (42.0, 46.6), nps=_SAN_MAIN_NPS, material='pvc',
         system='SAN', name='3in building drain', z=-300.0)
    AUTO('pipe', (42.0, 46.6), (42.0, 20.0), nps=_SAN_MAIN_NPS, material='pvc',
         system='SAN', name='3in drain to septic', z=-400.0)
    for sym, fx, fy, nps, on_horiz in (
            ('KS', 10.0, 47.0, '2', True),
            ('LAV', 12.2, 46.6, '1-1/2', True),
            ('WC', 13.4, 46.6, _SAN_MAIN_NPS, True),
            ('SHR', 15.0, 46.6, '2', True),
            ('US', 23.0, 33.6, '2', False),
            ('FD', 41.5, 27.0, '2', False),
            ('DW', 40.5, 30.0, '2', False),
            ('WC', 46.5, 30.5, _SAN_MAIN_NPS, False),
            ('LAV', 44.5, 31.0, '1-1/2', False)):
        tap = (fx, 46.6) if on_horiz else (42.0, fy)
        AUTO('pipe', T(sym, fx, fy), tap, nps=nps, material='pvc',
             system='SAN', name='waste branch', z=-250.0)
        TEE(_SAN_MAIN_NPS, tap, 'pvc', 'SAN')
    # 2" vents up through the roof at the two WC risers
    for fx, fy in ((13.4, 46.6), (46.5, 30.5)):
        p.place_riser(level=level, nps='2', origin=(_ft(fx), _ft(fy)),
                      z0_mm=0.0, z1_mm=4200.0, material='pvc', system='V',
                      name='vent through roof')
        n['pipe'] += 1

    # ---- RADIANT PEX (copper NPS proxy), supply/return mains from manifold ---
    man = (40.5, 26.0)
    for a, b, name in ((man, (24.0, 16.0), 'radiant PEX supply - garage'),
                       ((24.5, 16.0), man, 'radiant PEX return - garage'),
                       (man, (15.0, 40.0), 'radiant PEX supply - ADU'),
                       ((15.5, 40.0), man, 'radiant PEX return - ADU')):
        AUTO('pipe', a, b, nps='3/4', system='RAD', name=name, z=2600.0)

    # ---- MECHANICAL ductwork (galv), sized from CFM --------------------------
    ef = sz.size_duct(50.0 * 1.699)          # 50 CFM bath exhaust -> m3/h
    AUTO('duct', (46.5, 31.0), (47.6, 31.0), system='EA',
         name='EF-1 bath exhaust to exterior', z=2700.0,
         w=float(ef['width_mm']), h=float(ef['height_mm']))
    sa = sz.size_duct(120.0 * 1.699)         # ~120 CFM ADU ventilation
    AUTO('duct', (40.0, 33.0), (16.0, 40.0), system='SA',
         name='ADU supply trunk', z=2700.0,
         w=float(sa['width_mm']), h=float(sa['height_mm']))
    AUTO('duct', (16.0, 41.0), (40.0, 34.0), system='RA',
         name='ADU return trunk', z=2700.0,
         w=float(sa['width_mm']), h=float(sa['height_mm']))

    # ---- POWER conduit feeders, trade size from NEC Ch.9 fill -----------------
    for a, b, amps, name in ((panel_a, panel_b, 100.0, 'ADU subfeed 100A'),
                             (panel_a, (47.4, 4.0), 50.0, 'EV feeder 50A'),
                             (panel_a, (39.5, 40.0), 30.0, 'workshop 240V 30A'),
                             (panel_a, (40.0, 26.0), 23.0, 'radiant RF circuit')):
        AUTO('conduit', a, b, system='PWR', name=name, z=2800.0,
             trade=_feeder_trade(amps))
    # branch-circuit homeruns (20A) to device clusters
    hr_trade = str(sz.size_conduit([('12', 3)])['trade_size'])
    for a, b, name in ((panel_a, (8.0, 31.4), 'garage recept HR'),
                       (panel_b, (14.0, 33.6), 'ADU branch HR'),
                       (panel_a, (24.0, 10.7), 'garage lighting HR')):
        AUTO('conduit', a, b, system='LTG' if 'lighting' in name else 'PWR',
             name=name, z=2800.0, trade=hr_trade)

    # ---- FIRE PROTECTION: none routed, per basis (CRC R313 exemption) --------
    # Threaded into model meta so material_lists.fire_takeoff can report the
    # empty takeoff as "n/a per basis" instead of "not modeled".
    fire_notes = basis.build_notes().get('fire_protection') or []
    if fire_notes:
        p.model.meta['fire_basis_note'] = fire_notes[0]

    return n


if __name__ == '__main__':
    for ln in (electrical_service_calc() + plumbing_calc()
               + mechanical_calc()):
        print(' *', ln)
    print('devices:', len(electrical_devices()), '| plumb fixtures:',
          len(plumbing_fixtures_layout()), '| mech:',
          len(mech_equipment_layout()))
