#!/usr/bin/env python3
"""Generate the SCHAD engineering + specification documents.

Writes (to this folder):
  STRUCTURAL_CALCS.md — loads, member checks, footing/lateral checks
  MEP_CALCS.md        — electrical service calc, plumbing, mechanical
  SPECIFICATIONS.md   — CSI-division outline spec (from BOM/record)

Run:  python generate_schad_docs.py
"""

from __future__ import annotations

import os

import schad_design_basis as basis
import schad_house_basis as house
import schad_mep as mep
import schad_site as site
import schad_structural as struct

HERE = os.path.dirname(os.path.abspath(__file__))
HDR = ('**Project:** SCHAD Garage/ADU/Workshop + House Remodel — 3730 '
       'Chandler Rd, Quincy CA (APN 005-350-001-000) · **Ledger Built '
       '2024-008** · Designer: Ryan Vukich\n\n> DESIGN-SUPPORT DOCUMENT '
       '— values marked (ASSUMED) require confirmation; structural PE '
       'review reserved per contract. NOT FOR CONSTRUCTION.\n')


def write(name: str, lines: list[str]) -> str:
    p = os.path.join(HERE, name)
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    return p


def structural_doc() -> list[str]:
    L = ['# SCHAD Structural Calculations (Phase 1 Garage)', '', HDR, '']
    L += ['## Member & foundation checks', '']
    L += ['- %s' % s for s in struct.calc_summary()]
    L += ['', '## Header schedule', '']
    for h in struct.header_schedule():
        L.append('- **%s** %s — %s (%s)' % (h['mark'], h['member'],
                                            h['use'], h['span']))
    L += ['', '## Structural notes (for S-sheets)', '']
    L += ['- %s' % n for n in struct.structural_notes()]
    L += ['', '## Existing house framing (Phase 2 record, [HPLAN])', '']
    for k, v in sorted(house.house_framing().items()):
        L.append('- **%s**: %s' % (k, v))
    rm = house.remodel_scope()
    L += ['', '## Phase 2 — SECOND-STORY ADDITION (scoped %s)'
          % '[USER 2026-07-12]', '', '> %s' % rm['directive'], '',
          '### Scope of work', '']
    L += ['%d. %s' % (i + 1, w) for i, w in enumerate(rm['work'])]
    L += ['', '### Structural flags for the EOR', '']
    L += ['- %s' % f for f in rm['structural_flags']]
    L += ['', '### Owner decisions needed before design', '']
    L += ['%d. %s' % (i + 1, q)
          for i, q in enumerate(rm['owner_questions'])]
    L += ['', '## Field verification before Phase 2 CDs', '']
    L += ['- %s' % v for v in house.house_field_verify()]
    return L


def mep_doc() -> list[str]:
    L = ['# SCHAD MEP Calculations (Phase 1 Garage/ADU)', '', HDR, '']
    L += ['## Electrical (NEC 220)', '']
    L += ['- %s' % s for s in mep.electrical_service_calc()]
    L += ['', '### Panel schedule [RB MEP-101]', '',
          '| CKT | Description | A |', '|---|---|---|']
    L += ['| %s | %s | %s |' % r for r in basis.electrical_panel()]
    L += ['', '## Plumbing (CPC)', '']
    L += ['- %s' % s for s in mep.plumbing_calc()]
    L += ['', '## Mechanical (CMC / Title 24)', '']
    L += ['- %s' % s for s in mep.mechanical_calc()]
    L += ['', '## Device counts', '',
          '- electrical devices: %d' % len(mep.electrical_devices()),
          '- plumbing fixtures: %d' % len(mep.plumbing_fixtures_layout()),
          '- mech equipment: %d' % len(mep.mech_equipment_layout())]
    return L


def spec_doc() -> list[str]:
    n = basis.build_notes()
    L = ['# SCHAD Outline Specifications (CSI format)', '', HDR, '']
    div = [
        ('01 GENERAL REQUIREMENTS', [
            '2022 CBC/CRC, 2022 CPC/CMC, 2023 CEC, Title 24-2022 [RB]',
            'Verify all dimensions in field; RFIs to designer',
            'Deferred submittals: roof trusses (fab-engineered)',
            'Cost-plus contract, Ledger Built LLC [CONTRACT]']),
        ('03 CONCRETE', [
            '3,500 psi @ 28 days [RB] (BOM budget notes 3,000-4,000 psi; '
            'freeze climate: air entrain 5-7%, slump 4" +/- 1)',
            'Footings 18"x12" direct-dig; stem 8" front / 6" typ [RB]',
            'Slabs: 4" garage w/ radiant + fiber mesh; 3" ADU [RB/BOM]',
            '10-mil vapor barrier + 4" gravel under slabs [RB]',
            'Anchor bolts 5/8" @ 6\'-0" OC; SSTB anchors at SSW [RB/BOM]']),
        ('05 METALS', [
            'W16x40 A992 beams (2); HSS6x6x1/4 posts (4); base plates '
            '8x8x1 [BOM]; shop prime',
            'Simpson SSW24x9 (4) + SSW24x12 (2) w/ HDU hold-downs [BOM]']),
        ('06 WOOD & COMPOSITES', [
            '2x6 DF-L #2 studs @ 16" OC ext; 2x4 int; DBL top plates, PT '
            'sills [RB]',
            'Trusses 24" OC engineered [RB/BOM]; LVL 1.75x16 headers',
            '5/8" DF structural siding = shear layer per engineering '
            'memo (supersedes OSB note)',
            '18" overhangs, eaves + rakes; soffit 1x6 T&G pine, clear '
            'sealed, VENTED (maintain net free area per CRC R806) w/ '
            'recessed soffit lighting [USER 2026-07-12]']),
        ('07 THERMAL & MOISTURE', [
            'R-21 walls, R-38 ceiling [USER 2026-07-12 — resolved], '
            'R-30 vaulted, R-10 under ADU slab [BOM/RB]',
            'Standing-seam 24ga metal roof, dark charcoal; ice & water '
            'shield; vapor-open WRB [BOM/HANDOFF]',
            'Board-and-batten: 1x3 battens @ 16" OC, SS fasteners']),
        ('08 OPENINGS', [
            'Overhead doors: 2x 12x9 + 1x 12x12 glass-panel, insulated, '
            'WiFi operators [RB/BOM]',
            'Man doors: 3-0x6-8 solid core (ADA at ADU); 2-6 HM [RB]',
            'Windows: 4x 4-0x4-0 vinyl casement U<=0.30 [RB] (Q-WIN: '
            'BOM lists different mix — resolve before order)']),
        ('09 FINISHES', [
            '5/8" Type X gyp at garage/ADU separation (1-hr) + ADU '
            'interior; polished concrete floors [RB/HANDOFF]']),
        ('22 PLUMBING', mep.plumbing_calc()),
        ('23 HVAC', mep.mechanical_calc()),
        ('26 ELECTRICAL', mep.electrical_service_calc()),
        ('31/32 SITE', site.site_basis()['notes']),
    ]
    for title, items in div:
        L += ['## DIVISION %s' % title, '']
        L += ['- %s' % i for i in items]
        L.append('')
    L += ['## OPEN QUESTIONS CARRIED FROM THE RECORD', '']
    L += ['- **%s** (%s): %s' % (q['id'], q['status'], q['q'])
          for q in basis.open_questions()]
    return L


def main() -> None:
    for name, gen in (('STRUCTURAL_CALCS.md', structural_doc),
                      ('MEP_CALCS.md', mep_doc),
                      ('SPECIFICATIONS.md', spec_doc)):
        p = write(name, gen())
        print('  wrote', os.path.basename(p))


if __name__ == '__main__':
    main()
