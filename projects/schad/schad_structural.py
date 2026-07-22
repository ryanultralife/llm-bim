#!/usr/bin/env python3
"""SCHAD structural design basis + member checks (Phase 1 garage).

DESIGN-SUPPORT CALCULATIONS by the designer of record (Ryan Vukich,
Ledger Built LLC). NOT a substitute for the structural PE review the
record reserves ("PE stamp and approval" by others, [HANDOFF]); every
ASSUMED value is flagged and must be confirmed by the EOR.

Sources: [RB] permit set (75 PSF snow, member callouts), [BOM] member
list (W16x40 32', HSS6x6x1/4, SSW24x9 x4 + SSW24x12 x2, trusses),
[HANDOFF] (bearing 1,320 plf, SF 2.27, direct-dig footings).
"""

from __future__ import annotations

import re

import schad_design_basis as basis

_REBAR_SPEC_RE = re.compile(r"\((\d+)\)\s*#(\d+)")

# ---- loads ----------------------------------------------------------------
SNOW_PSF = 75.0            # roof snow [RB framing notes]
ROOF_DL_PSF = 15.0         # metal roof + trusses + insul (ASSUMED)
WALL_DL_PSF = 12.0         # 2x6 + 5/8 DF siding + gyp (ASSUMED)
WIND_V_MPH = 115.0         # CBC basic wind, Exp C (ASSUMED — site TBD)
SDS = 1.0                  # seismic, SDC D (ASSUMED — site-specific TBD)
R_WOOD_SW = 6.5            # light-frame wood shear wall system
SOIL_Q_ALLOW_PSF = 1500.0  # presumptive, CBC 1806.2 (ASSUMED — no geotech)

# ---- member properties ------------------------------------------------------
W16X40 = {'Zx_in3': 73.0, 'Ix_in4': 518.0, 'Fy_ksi': 50.0, 'wt_plf': 40.0}
SSW_ASD_LB = {'SSW24x9': 3025.0, 'SSW24x12': 2610.0}
# Simpson catalog seismic ASD (ASSUMED from ESR-2652 class values — the
# EOR must verify model/anchorage capacities for the final lateral check)


def beam_check() -> dict:
    """W16x40 @ bay lines, 32' span [BOM], trib 8' (ASSUMED half-bay)."""
    s = basis.build_scalars()
    span = 32.0
    trib = s['bay_L'] / 2.0
    w = (SNOW_PSF + ROOF_DL_PSF) * trib + W16X40['wt_plf']  # plf, ASD
    M = w * span ** 2 / 8.0 / 1000.0                        # k-ft
    Mallow = W16X40['Fy_ksi'] * W16X40['Zx_in3'] / 1.67 / 12.0
    E, I = 29000.0, W16X40['Ix_in4']
    ws = SNOW_PSF * trib / 12.0 / 1000.0                    # k/in
    dl = span * 12.0
    defl = 5.0 * ws * dl ** 4 / (384.0 * E * I)             # in, snow only
    return {
        'member': 'W16x40, A992', 'span_ft': span, 'trib_ft': trib,
        'w_plf': round(w), 'M_kft': round(M, 1),
        'M_allow_kft': round(Mallow, 1), 'DCR': round(M / Mallow, 2),
        'defl_in': round(defl, 2), 'defl_limit_in': round(dl / 240.0, 2),
        'ok': M <= Mallow and defl <= dl / 240.0,
    }


def post_check() -> dict:
    """HSS6x6x1/4 posts under beam ends [BOM]."""
    b = beam_check()
    P = b['w_plf'] * b['span_ft'] / 2.0 / 1000.0            # kips
    Pallow = 50.0   # k, HSS6x6x1/4 @ KL~12' (ASSUMED catalog value)
    return {'member': 'HSS 6x6x1/4', 'P_k': round(P, 1),
            'P_allow_k': Pallow, 'DCR': round(P / Pallow, 2),
            'ok': P <= Pallow}


def strip_footing_check() -> dict:
    """18" x 12" direct-dig strip under bearing walls [RB/HANDOFF]."""
    s = basis.build_scalars()
    truss_rxn = (SNOW_PSF + ROOF_DL_PSF) * s['main_W'] / 2.0  # plf
    wall = WALL_DL_PSF * s['plate_main']
    w = truss_rxn + wall                                      # plf
    q = w / s['footing_w']                                    # psf
    return {'element': '18"x12" strip footing',
            'load_plf': round(w), 'record_plf': 1320.0,
            'q_psf': round(q), 'q_allow_psf': SOIL_Q_ALLOW_PSF,
            'SF_record': 2.27, 'ok': q <= SOIL_Q_ALLOW_PSF}


def point_footing_check() -> dict:
    """36"x36"x30" point footings under posts [BOM]."""
    p = post_check()
    q = p['P_k'] * 1000.0 / 9.0
    return {'element': '36"x36" point footing', 'P_k': p['P_k'],
            'q_psf': round(q), 'q_allow_psf': SOIL_Q_ALLOW_PSF,
            'ok': q <= SOIL_Q_ALLOW_PSF}


def lateral_check() -> dict:
    """Front-line seismic vs Strong-Walls (E-W). SIMPLIFIED ELF."""
    s = basis.build_scalars()
    W = (ROOF_DL_PSF * s['area_total']
         + WALL_DL_PSF * s['plate_main'] * 160.0 / 2.0) / 1000.0  # kips
    Cs = SDS / R_WOOD_SW * 1.0                                # Ie=1
    V = Cs * W                                                # kips
    v_front = V / 2.0                                         # front line
    cap = (2 * SSW_ASD_LB['SSW24x9'] + 2 * SSW_ASD_LB['SSW24x12']) / 1000.0
    # front line carries 2x SSW24x9 (bays 1/3) + 2x SSW24x12 (bay 2)
    return {'W_k': round(W, 1), 'Cs': round(Cs, 3), 'V_k': round(V, 1),
            'v_front_k': round(v_front, 1),
            'cap_front_k': round(cap, 1),
            'DCR': round(v_front / cap, 2), 'ok': v_front <= cap}


def header_schedule() -> list[dict]:
    return [
        {'mark': 'HDR-1', 'member': '4x8 DF#2', 'span': "up to 4'-0\"",
         'use': 'ADU/workshop windows + man doors'},
        {'mark': 'HDR-2', 'member': '(2) LVL 1.75x16 [BOM]',
         'span': "12'-0\" overhead doors",
         'use': 'garage door openings (verify w/ SSW system geometry)'},
        {'mark': 'HDR-E', 'member': '3x8 / 4x12 (existing house, [HPLAN])',
         'span': 'existing', 'use': 'house — field verify, no change'},
    ]


def structural_notes() -> list[str]:
    n = basis.build_notes()
    extra = [
        'ROOF TRUSSES: DEFERRED SUBMITTAL — engineered by fabricator '
        '(modified scissor 32\' 6/12-6/12; 34\' 10/12-6/12; shed @ rear) '
        '[BOM]; truss calcs to building dept. prior to erection',
        'LATERAL SYSTEM: Simpson Strong-Wall per schedule + 5/8" DF '
        'structural siding (engineering memo governs over OSB note)',
        'ALL STRUCTURAL VALUES MARKED (ASSUMED) REQUIRE EOR CONFIRMATION; '
        'PE approval reserved per contract',
    ]
    return n['framing'] + n['foundation'] + extra


def calc_summary() -> list[str]:
    b, p = beam_check(), post_check()
    sf, pf = strip_footing_check(), point_footing_check()
    lt = lateral_check()
    F = lambda ok: 'OK' if ok else 'NG — REVISE'
    return [
        'DESIGN LOADS: snow %d psf [RB]; roof DL %d psf (ASSUMED); wind '
        '%d mph Exp C (ASSUMED); seismic SDC D, SDS=%.1f (ASSUMED)'
        % (SNOW_PSF, ROOF_DL_PSF, WIND_V_MPH, SDS),
        'BEAM %s: span %d ft, w=%d plf -> M=%.1f k-ft vs %.1f allow '
        '(DCR %.2f); defl %.2f in vs L/240=%.2f -> %s'
        % (b['member'], b['span_ft'], b['w_plf'], b['M_kft'],
           b['M_allow_kft'], b['DCR'], b['defl_in'], b['defl_limit_in'],
           F(b['ok'])),
        'POST %s: P=%.1f k vs %.0f k allow (DCR %.2f) -> %s'
        % (p['member'], p['P_k'], p['P_allow_k'], p['DCR'], F(p['ok'])),
        'STRIP FTG: %d plf (record %d) -> q=%d psf vs %d presumptive -> %s'
        % (sf['load_plf'], sf['record_plf'], sf['q_psf'],
           sf['q_allow_psf'], F(sf['ok'])),
        'POINT FTG 36x36: q=%d psf vs %d -> %s'
        % (pf['q_psf'], pf['q_allow_psf'], F(pf['ok'])),
        'LATERAL (E-W, simplified ELF): W=%.1f k, Cs=%.3f, V=%.1f k; '
        'front line %.1f k vs SSW capacity %.1f k (DCR %.2f) -> %s'
        % (lt['W_k'], lt['Cs'], lt['V_k'], lt['v_front_k'],
           lt['cap_front_k'], lt['DCR'], F(lt['ok'])),
    ]


def place_foundation_rebar(p: object, *, level: str = 'L1') -> dict:
    """Place foundation rebar as CSI 03 20 00 parts from the basis specs carried
    on footing/stem/slab elements (schematic quantity → non-empty rebar takeoff).

    HONESTY: only reinforcement the record actually specifies is quantified. The
    basis fixes ``(2) #4 CONTINUOUS`` in the strip footings and Grade 60
    [schad_design_basis foundation notes]; stems, pads and slabs carry no bar
    callout in the record and are left UNQUANTIFIED (not invented). Continuous
    bars bill count x element length. Design-development, not a bar-bending
    schedule — the EOR's stamped rebar shop drawings govern.
    """
    placed = {'elements': 0, 'bars': 0, 'length_m': 0.0}
    for el in list(p.model.elements):
        if el.category not in ('footing', 'stem_wall', 'slab'):
            continue
        spec = str(el.params.get('rebar') or el.params.get('reinforcement') or '')
        m = _REBAR_SPEC_RE.search(spec)
        if not m:
            continue
        count = int(m.group(1))
        size = m.group(2)
        length_mm = float(el.params.get('length_mm') or 0.0)
        if count <= 0 or length_mm <= 0.0:
            continue
        total_len_m = round(count * length_mm / 1000.0, 3)
        pts = el.params.get('path_mm') or []
        origin = (
            el.params.get('origin_mm')
            or el.params.get('position_mm')
            or (pts[0] if pts else [0.0, 0.0])
        )
        mark = str(el.params.get('mark') or el.category)
        p.place_part(
            level=level,
            kind='rebar',
            bar_size=size,
            origin=(float(origin[0]), float(origin[1])),
            length_m=total_len_m,
            name=f'{mark} rebar #{size}',
        )
        placed['elements'] += 1
        placed['bars'] += count
        placed['length_m'] = round(placed['length_m'] + total_len_m, 3)
    return placed


if __name__ == '__main__':
    for line in calc_summary():
        print(' *', line)
