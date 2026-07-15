# Vision ↔ codebase alignment loop

**Started:** 2026-07-15 (session)  
**Cadence:** every 5 minutes  
**Duration:** **10 hours** (~120 passes max)  
**End:** stop after 120 passes or wall-clock ≥ start + 10h  
**Scheduler:** 5m recurring `019f673f9283` + 10h hard-stop  
**Overseer:** every **30m** — see `notes/handoffs/OVERSEER_LOOP.md` + `scripts/vision_overseer_check.py` → log `OVERSEER_LOG.md`

**CSI upgrade (user):** every takeoff line should carry a **real MasterFormat** `csi_code` (e.g. `22 11 16`) plus a **locator** (level | X | Y | Z/height | NPS) so agents can find the item in the model — not vague divisions alone.

## Vision anchors (must match output)

1. **LLM-only authoring** — no human drafting GUI (`docs/VISION.md`)
2. **One model → full pack** — IFC/STEP/glTF/SVG/PDF/BOQ/clash/materials (`export_deliverables`)
3. **Open domains** — generic elements + ops registry (`docs/CAPABILITY.md`)
4. **True model VCS** — commits under `output/<slug>/.llmbim/`, not chat
5. **Parts/materials/CSI takeoffs** — fire, process, steel, rebar, fixtures, plumbing
6. **Honesty** — envelopes + coordination grade; not PE-stamped Revit replacement (`docs/HONESTY.md`)
7. **Local-first** — `./output/`, skill + CLI + MCP

## Pass log

| # | Time | Focus | Gaps found | Changes | Tests | Commit |
|---|------|-------|------------|---------|-------|--------|
| 0 | setup | loop infrastructure | — | VISION_LOOP + scheduler 5m + stop 2h | — | setup |
| 1 | T+0 | docs + MCP agent surface | matrix/vision stale; MCP lacked takeoff | OUTPUT_MATRIX, VISION roadmap, MCP place/takeoff/parts | 60 unit pass | 3a3da9a |
| 2 | T+5m | BOQ/takeoff units | steel/rebar listed as ea | quantities + part_assignment unit m/m2; test | 61 unit pass | 6463cca |
| 3 | T+10m | verify materials pack | verify ignored materials/ | require_materials + CLI flag + tests | 62 unit pass | 6c683b1 |
| 4 | T+15m | CSI process + matrix modules | sep parts CSI empty; modules undoc'd | flange/cartridge/magnet/pedestal CSI; OUTPUT_MATRIX M6 | 68 unit pass | b5143a5 |
| 5 | T+20m | IFC pipe/fitting/fixture | IFC only walls/equip | BuildingElementProxy for pipe/fitting/fixture/module | 70 unit pass | 6af664a |
| 6 | T+~30m | CSI real codes + locators | codes too coarse; no XY/Z | csi_instance L1\|X\|Y\|Z; MF 22 42 13 toilets etc | 72 unit pass | 62a9f96 |
| 7 | T+~35m | MCP modules + CSI | modules only via project_op | import_module/connect/ports/csi_instances MCP tools | 72 unit pass | a6eda34 |
| 8 | continue | glTF MEP + chat_smoke | glTF walls/equip only; smoke no multi-trade | pipe/fitting/fixture mesh; smoke step 4 | 73 unit + smoke ok | 9889df7 |
| 9 | continue | skill section order | H2/H3 awkward | SKILL sections H–K sequential | — | 4fda52f |
| 10 | continue | STEP MEP + connections export | STEP walls/equip only | pipe/fitting STEP solids; materials/connections | 74 unit | 69e887b |
| 11 | continue | plan SVG MEP | plans ignored pipes | pipes/fittings/fixtures on plan SVG | 75 unit | 3ce4ab0 |
| 12 | continue | MEP design rules | no pipe/wall/fire checks | PIPE_IN_WALL, FIRE_PIPE_MATERIAL, NPS, connections | 79 unit | d709e42 |
| 13 | continue | elev/section pipes + clash | elev no MEP; clash no pipe | elev/section pipe draw; find_clashes includes MEP | 82 unit | 0804cf2 |
| 14 | continue | DXF MEP layers | DXF walls/equip only | PIPE-CU/FP/SS + FITTINGS layers | 82 unit | d2242fa |
| 15 | continue | HTML CSI/MEP index | index thin on takeoff | csi sample table + MEP legend | 82 unit | 23e4994 |
| 16 | continue | vertical pipe risers | pipes horizontal-only | place_riser + plan/elev/AABB + ops schema | 84 unit | 4353a8f |
| 17 | continue | riser 3D + MCP | STEP/glTF/MCP missing risers | STEP/glTF vertical solids; MCP place_pipe/riser | 85 unit | 95025a7 |
| 18 | continue | schedules CSI+locator | schedules no MF codes | door/pipe/fitting/equip CSI+locator; schedules/csi.csv | 87 unit | 190cda6 |
| 19 | continue | CSI room in locator | locator lacked room | room_containing PIP + RM:RoomName; RISER token | 88 unit | d715459 |
| 20 | continue | DXF vertical risers | DXF zero-length pipe line | CIRCLE riser plan symbol + PIPE layer | 91 unit | d528f75 |
| 21 | continue | CLI place + csi_instances | no CLI place_riser/fitting | `llmbim place` + takeoff --kind csi_instances | 91 unit | d528f75 |
| 22 | continue | schedule room column | schedules lacked room | `_annotate_csi` room field | 94 unit | (this) |
| 23 | continue | query room/csi/vertical | query only wall attrs | room~, csi~, nps, vertical=true | 94 unit | (this) |
| 24 | continue | skill + HTML RM: docs | skill stale locators | SKILL place/csi_instances; HTML room col | 94 unit | 96580b5 |
| 25 | continue | IFC FlowSegment + riser | risers missing from IFC; only proxy | IfcFlowSegment/Fitting/Terminal; vertical Z | 95 unit | 0115b91 |
| 26 | continue | restroom CSI recipe | no end-to-end RM: demo | examples/restroom_csi + skill recipe | 95 unit | 0115b91 |
| 27 | continue | MCP query CSI enrich | query returned id only | room/csi/locator on project_query | 96 unit | (this) |
| 28 | continue | multi-storey to_level riser | risers single-storey only | place_riser(to_level=L2/L3) | 96 unit | 2bd3ec6 |
| 29 | continue | HVAC place_duct | no duct authoring | place_duct + plan/DXF/CSI 23 31 00 | 98 unit | 857c12c |
| 30 | continue | electrical conduit | no conduit place | place_conduit CSI 26 05 33 + plan/DXF | 99 unit | 52c86e9 |
| 31 | continue | grid bubble labels | grids were unlabeled lines | plan A/B + 1/2 bubbles; labels= | 100 unit | dcab713 |
| 32 | continue | multi-MEP + elev duct | elev ignored duct/conduit; panel CSI wrong | elev MEP; smoke duct/riser/conduit/panel; part CSI fix | 101 unit | 26d56fa |
| 33 | continue | duct-pipe clash + skill | clash ignored duct; skill stale | AABB duct/conduit; SKILL place duct/conduit/to_level | 102 unit | c01d0e8 |
| 34 | continue | wall types + HTML conn | plan no type marks | wall-types class; connections table in index | 103 unit | f0eaac0 |
| 35 | continue | room ceiling height | rooms area-only | height_mm/ceiling_height_mm on room + schedule | 104 unit | d72f0c0 |
| 36 | continue | BOQ+MCP duct/conduit | BOQ skipped MEP duct; MCP no place | BOQ m2/m; MCP place_duct/conduit; glTF | 105 unit | cfd2ae5 |
| 37 | continue | door/window type marks | plan only D1/W1 | type_id on place + opening-type on plan; matrix duct/conduit | 106 unit | d8b3d09 |
| 38 | continue | glTF system colors | one gray mesh for all MEP | multi-material glTF copper/fire/duct/conduit | 107 unit | ed4e990 |
| 39 | continue | VAV + fire damper | no HVAC device place/plan | kind=vav/fire_damper CSI 23 36/33; plan FD/VAV | 109 unit | 45fd538 |
| 40 | continue | phase filter export | pack always all phases | filter_by_phase + export_deliverables(phases=) | 111 unit | 57c9f35 |
| 41 | continue | zone schedule + pack phases | no area/volume sched; CLI no --phases | zone_areas.csv; pack --phases | 112 unit | 66a1c49 |
| 42 | continue | IFC SpaceContents MEP | MEP not linked to IfcSpace | room pass + SpaceContents rel by point-in-poly | 113 unit | f097492 |
| 43 | continue | MCP pack phases | MCP export lacked phase filter | project_export_pack phases + set_phase tool | 114 unit | e0a9cee |
| 44 | continue | plan MEP dimensions | dims walls only | pipe/duct/conduit length dims on plan | 115 unit | 52807c1 |
| 45 | continue | connection schedule | HTML only raw ports; no names | connection_schedule locator; schedules/connections.csv | 115 unit | d776fea |
| 46 | continue | STEP system layers | STEP products untagged | PRODUCT names PIPE-CU/FP/DUCT/CONDUIT:… | 116 unit | 838ca91 |
| 47 | continue | CLI/MCP schedule | no schedule agent surface | llmbim schedule + project_schedule MCP | 117 unit | 8abcefd |
| 48 | continue | duct/conduit design rules | only pipe-in-wall rules | DUCT_IN_WALL, CONDUIT_IN_WALL, DUCT_LOW_CLEARANCE | 118 unit | bbe2c2a |
| 49 | continue | elev storey dims + zone HTML | elev no level dims; index no zone | level-dims; zone_areas sample | 119 unit | 3b707e7 |
| 50 | continue | section storey dims | section lacked level dims | level-dims + storey-height on section SVG | 120 unit | 9873377 |
| 51 | continue | elev DXF CAD handoff | only plan DXF | export_elevation_dxf S/E in pack; SDK | 121 unit | bcab845 |
| 52 | continue | query phase= | phase query incomplete docs | phase=new\|existing filter tests | 122 unit | bcab845 |
| 53 | continue | full multi-trade pack smoke | chat path thin | elev DXF+zone+CSI+IFC space+STEP layers | 123 unit | 77868eb |
| 54 | continue | DXF grid bubbles | plan DXF grids unlabeled | CIRCLE + A/B/1 labels on GRIDS | 124 unit | c8b4ad4 |
| 55 | continue | duct/conduit takeoff | only BOQ qty; no trade takeoff API | duct_takeoff/conduit_takeoff + CLI/MCP + pack | 126 unit | 2cfbdeb |
| 56 | continue | duct/conduit schedules | no duct.csv/conduit.csv | schedule_rows + pack CSVs + HTML links | 129 unit | (this) |
| 57 | continue | room area tags on plan | name-only room labels | area m² + clear height H#### | 129 unit | (this) |
| 58 | continue | section DXF CAD handoff | only plan+elev DXF | export_section_dxf + pack views/section.dxf | 129 unit | d0f38c7 |
| 59 | continue | DXF room area tags | DXF rooms name-only | area m2 + H#### on ROOMS layer | 132 unit | (this) |
| 60 | continue | HVAC device schedule | VAV/diffuser/panel not scheduled | hvac_device rows + pack CSV | 132 unit | (this) |
| 61 | continue | IFC CSI property sets | IFC had no CSI props | Pset_CSIMasterFormat CSI_Code+Locator | 132 unit | 5167cd6 |
| 62 | continue | cable tray place+takeoff | only conduit raceway | place_cable_tray CSI 26 05 36 + plan/DXF/BOQ | (this) | (this) |
| 63 | continue | skill takeoff docs | skill lacked duct/tray takeoff | SKILL place+takeoff duct/conduit/tray | 135 unit | f1fb83f |
| 64 | continue | level schedule | no storey floor-to-floor | schedule kind level + levels.csv | (this) | (this) |
| 65 | continue | drawing list index | pack had no sheet inventory | schedules/drawing_list.csv + JSON | 137 unit | 5354d92 |
| 66 | continue | door fire_rating | door sched no rating | place_door fire_rating + schedule col | (this) | (this) |
| 67 | continue | glTF/STEP cable tray | tray missing 3D colors | cable_tray material + CABLE-TRAY STEP | (this) | (this) |
| 68 | continue | HTML drawing list | index no sheet table | drawing list sample in index.html | 138 unit | 85a064f |
| 69 | continue | structural columns | only place_part steel | place_column W-section + plan/BOQ/CSI | 139 unit | ef60bf4 |
| 70 | continue | structural beams | no beam place API | place_beam start→end + plan/BOQ/CSI | 140 unit | 6ab7036 |
| 71 | continue | beam MCP/IFC/STEP + ops | agent surface incomplete | MCP place_beam; IFC/STEP; ops.schema 45 | 140 unit | b4561be |
| 72 | continue | wall fire_rating + beam sched | walls lacked rating; no beam.csv | create_wall fire_rating; pack beam.csv | 140 unit | 9496d71 |
| 73 | continue | skill/capability structure | agent docs lag code | SKILL column/beam/fire; CAPABILITY trades | 140 unit | 8edcfad |
| 74 | continue | DXF structure + clash | plan DXF no COLUMNS/BEAMS; clash skip | COLUMNS/BEAMS layers; AABB clash | 142 unit | 41bf481 |
| 75 | continue | elev DXF structure + steel takeoff | elev no COLUMNS/BEAMS; steel missed place_* | elev COLUMNS/BEAMS; steel_takeoff merge | 144 unit | 2820a1c |
| 76 | continue | elev/section SVG structure | elev SVG no columns | columns-elev tags; beam depth; section cut | 145 unit | 76fa760 |
| 77 | continue | section DXF structure | section DXF no COLUMNS/BEAMS | COLUMNS/BEAMS on cut + cable tray | 146 unit | 9b95995 |
| 78 | continue | multi-trade pack smoke | smoke thin on structure/tray | column/beam/tray + takeoffs + pack DXF | 146 unit | 5d324e4 |
| 79 | continue | query section + structure rules | no section=; no steel rules | section/trade_size query; COLUMN_IN_WALL | 148 unit | c80bfaa |
| 80 | continue | MCP query enrichment | query rows thin on section/system | section/trade_size/fire/phase + docs | 149 unit | d8b6bad |
| 81 | continue | plan FR tags + rules HTML | fire_rating not on plan; index no rules | wall/door FR marks; design_rules sample | 151 unit | 40cf5c3 |
| 82 | continue | DXF wall FR + chat_smoke | plan DXF no WALL-TYPES; smoke thin | WALL-TYPES FR; multi-trade structure smoke | 152 unit | (this) |

## Backlog (living — pull highest impact each pass)

1. ~~OUTPUT_MATRIX incomplete~~ (pass 1)
2. ~~VISION roadmap stale~~ (pass 1)
3. ~~BOQ unit for linear steel `m`~~ (pass 2)
4. ~~Verify pack materials/~~ (pass 3)
5. ~~MCP tools for place_part / takeoff~~ (pass 1)
6. ~~IFC export fittings/pipe~~ (pass 5)
7. ~~glTF pipe/fitting markers~~ (pass 8)
8. ~~Skill SKILL.md section order~~ (pass 9)
9. ~~chat_smoke multi-trade~~ (pass 8)
10. ~~CSI division 00 on process parts~~ (pass 4, related)
11. ~~part_summary unit for linear m parts~~ (pass 2)
12. ~~Process separator CSI~~ (pass 4)
13. ~~MCP module import/connect~~ (pass 7)
14. ~~OUTPUT_MATRIX modules~~ (pass 4)
15. ~~CSI MasterFormat + level/XY/Z locators~~ (pass 6)
16. ~~STEP export for pipe/fitting envelopes~~ (pass 10)
17. ~~Connection schedule in materials pack export~~ (pass 10)

18. ~~Plan SVG pipes/fittings~~ (pass 11)
19. ~~Design rules for MEP clearances / pipe in wall~~ (pass 12)
20. ~~Elevation/section draw pipe risers~~ (pass 13)
21. ~~Pipe-pipe clash in clash.py~~ (pass 13)
22. ~~DXF export pipes~~ (pass 14)
23. ~~HTML index legend for CSI/MEP~~ (pass 15)
24. ~~Vertical pipe risers place_riser~~ (pass 16)
25. ~~Riser STEP/glTF + MCP place_pipe/riser~~ (pass 17)
26. ~~Schedules CSI + locator columns~~ (pass 18)
27. ~~CSI locator room name (RM:)~~ (pass 19)
28. ~~DXF plan riser CIRCLE symbols~~ (pass 20)
29. ~~CLI place fitting/pipe/riser/part + csi_instances~~ (pass 21)
30. ~~Room column in schedules CSV~~ (pass 22)
31. ~~IFC IfcSpace room linkage for placed MEP~~ (pass 42)
32. ~~HTML index room+CSI locator sample~~ (pass 24)
33. ~~Query language filter by CSI / room / locator~~ (pass 23)
34. ~~Skill SKILL.md place_riser + RM: locators~~ (pass 24)
35. ~~MCP query tool with room/csi filters~~ (pass 27)
36. ~~Multi-level riser spanning storeys~~ (pass 28)
37. ~~Connection schedule in HTML index~~ (pass 45)
38. ~~IFC IfcFlowSegment for pipes (vs proxy)~~ (pass 25)
39. ~~Agent recipe: restroom + CW loop + CSI takeoff~~ (pass 26)
40. ~~HVAC duct place + takeoff (generic or catalog)~~ (pass 29)
41. ~~Electrical raceway / conduit place~~ (pass 30)
42. ~~Grid intersection labels on plans~~ (pass 31)
43. ~~Dimension strings on plan SVG (walls + MEP runs)~~ (pass 44)
44. ~~CLI place duct/conduit~~ (pass 29–30)
45. ~~Elev draw ducts as rectangles~~ (pass 32)
46. ~~Panelboard CSI from catalog part~~ (pass 32)
47. ~~Connection schedule on HTML index~~ (pass 45)
48. ~~Multi-trade smoke case for duct+conduit+riser~~ (pass 32)
49. ~~Tag walls with type mark on plan~~ (pass 34)
50. ~~Space height / ceiling height params~~ (pass 35)
51. ~~Clash: duct vs pipe AABB~~ (pass 33)
52. ~~Skill docs for duct/conduit/to_level~~ (pass 33)
53. ~~Wall type marks on plan~~ (pass 34)
54. ~~HTML connections schedule~~ (pass 34 / enriched 45)
55. ~~Ceiling height / room height_mm~~ (pass 35)
56. ~~Door/window type marks on plan (beyond D1/W1)~~ (pass 37)
57. ~~glTF materials by system color (pipe/duct/conduit)~~ (pass 38)
58. ~~BOQ include duct area_m2 + conduit length~~ (pass 36)
59. ~~MCP place_duct / place_conduit tools~~ (pass 36)
60. ~~Phase filters on export pack~~ (pass 40)
61. ~~Zone / area schedule with room heights~~ (pass 41)
62. ~~Fire damper / VAV place as fittings~~ (pass 39)
63. ~~OUTPUT_MATRIX duct/conduit/MCP place~~ (pass 37)
64. ~~Phase filters on export pack~~ (pass 40)
65. ~~Zone schedule room heights + area~~ (pass 41)
66. ~~CLI pack --phases new~~ (pass 41)
67. ~~IFC IfcSpace room linkage for placed MEP~~ (pass 42)
68. ~~STEP layer by system (PRODUCT LAYER:name)~~ (pass 46)
69. ~~MCP export_pack phases arg~~ (pass 43)
70. ~~MCP set_phase tool~~ (pass 43)
71. ~~CLI schedule + MCP project_schedule~~ (pass 47)
72. ~~Design rule: duct/conduit through wall~~ (pass 48)
73. ~~Elev dimension strings for storey heights~~ (pass 49)
74. ~~HTML zone_areas sample on index~~ (pass 49)
75. ~~Section cut storey height dims (mirror elev)~~ (pass 50)
76. ~~VISION M4 status refresh~~ (pass 50)
77. ~~DXF elevation export~~ (pass 51)
78. ~~Example multi-trade full pack smoke~~ (pass 53)
79. ~~Query filter by phase=~~ (pass 52)
80. ~~Duct/conduit dedicated takeoff API~~ (pass 55)
81. ~~Duct/conduit schedule CSVs in pack~~ (pass 56)
82. ~~Room area + height tags on plan~~ (pass 57)
83. ~~Section DXF export~~ (pass 58)
84. ~~DXF room area/height tags~~ (pass 59)
85. ~~HVAC/electrical device schedule~~ (pass 60)
86. ~~IFC Pset_CSIMasterFormat~~ (pass 61)
87. ~~Cable tray place + takeoff~~ (pass 62)
88. ~~Skill docs duct/conduit/tray takeoffs~~ (pass 63)
89. ~~Level / storey schedule~~ (pass 64)
90. ~~Drawing list sheet index~~ (pass 65)
91. ~~Door fire_rating on place + schedule~~ (pass 66)
92. ~~glTF/STEP cable tray~~ (pass 67)
93. ~~HTML drawing list sample~~ (pass 68)
94. ~~Structural place_column~~ (pass 69)
95. ~~Structural place_beam~~ (pass 70)
96. ~~Beam MCP/IFC/STEP + ops schema~~ (pass 71)
97. ~~Wall fire_rating + beam schedule~~ (pass 72)
98. ~~Skill/capability structure docs~~ (pass 73)
99. ~~Plan DXF columns/beams + structure clash~~ (pass 74)
100. ~~Elev DXF columns/beams + steel_takeoff place_*~~ (pass 75)
101. ~~Elev/section SVG columns + beam depth~~ (pass 76)
102. ~~Section DXF columns/beams + tray~~ (pass 77)
103. ~~Multi-trade pack smoke structure+tray~~ (pass 78)
104. ~~Query section= + structure design rules~~ (pass 79)
105. ~~MCP query enrichment section/system~~ (pass 80)
106. ~~Plan fire_rating tags + design_rules HTML~~ (pass 81)
107. ~~Plan DXF WALL-TYPES FR + chat_smoke multi-trade~~ (pass 82)
108. Keep closing residual gaps until pass 120 / 10h

## Rules for each scheduled pass

1. Read this file + `docs/VISION.md` + `docs/CAPABILITY.md` + `docs/OUTPUT_MATRIX.md`
2. Pick **one** highest-impact gap from backlog or a new discovered gap
3. Implement fix in repo `C:\Users\ryanv\llm-bim`
4. Run focused tests (`pytest tests/unit -q` or subset)
5. Commit if green: `[grok] vision-loop N: <summary>`
6. Append pass row to this log; update backlog
7. If pass_count ≥ **120** or past 10h end → stop, write FINAL summary
