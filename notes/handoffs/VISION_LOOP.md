# Vision ↔ codebase alignment loop

**Started:** 2026-07-15 (session)  
**Cadence:** every 5 minutes  
**Duration:** **10 hours** (~120 passes max)  
**End:** stop after 120 passes or wall-clock ≥ start + 10h  
**Scheduler:** 5m recurring `019f673f9283` + 10h hard-stop  

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
31. IFC IfcSpace room linkage for placed MEP
32. ~~HTML index room+CSI locator sample~~ (pass 24)
33. ~~Query language filter by CSI / room / locator~~ (pass 23)
34. ~~Skill SKILL.md place_riser + RM: locators~~ (pass 24)
35. ~~MCP query tool with room/csi filters~~ (pass 27)
36. ~~Multi-level riser spanning storeys~~ (pass 28)
37. Connection schedule in HTML index
38. ~~IFC IfcFlowSegment for pipes (vs proxy)~~ (pass 25)
39. ~~Agent recipe: restroom + CW loop + CSI takeoff~~ (pass 26)
40. ~~HVAC duct place + takeoff (generic or catalog)~~ (pass 29)
41. ~~Electrical raceway / conduit place~~ (pass 30)
42. ~~Grid intersection labels on plans~~ (pass 31)
43. Dimension strings on plan SVG (partial — show_dimensions exists)
44. ~~CLI place duct/conduit~~ (pass 29–30)
45. ~~Elev draw ducts as rectangles~~ (pass 32)
46. ~~Panelboard CSI from catalog part~~ (pass 32)
47. Connection schedule on HTML index
48. ~~Multi-trade smoke case for duct+conduit+riser~~ (pass 32)
49. Tag walls with type mark on plan
50. Space height / ceiling height params
51. ~~Clash: duct vs pipe AABB~~ (pass 33)
52. ~~Skill docs for duct/conduit/to_level~~ (pass 33)
53. ~~Wall type marks on plan~~ (pass 34)
54. ~~HTML connections schedule~~ (pass 34)
55. ~~Ceiling height / room height_mm~~ (pass 35)
56. Door/window type marks on plan (beyond D1/W1)
57. glTF materials by system color (pipe/duct/conduit) — geometry yes, color TBD
58. ~~BOQ include duct area_m2 + conduit length~~ (pass 36)
59. ~~MCP place_duct / place_conduit tools~~ (pass 36)
60. Phase filters on export pack
61. Zone / area schedule with room heights
62. Fire damper / VAV place as fittings

## Rules for each scheduled pass

1. Read this file + `docs/VISION.md` + `docs/CAPABILITY.md` + `docs/OUTPUT_MATRIX.md`
2. Pick **one** highest-impact gap from backlog or a new discovered gap
3. Implement fix in repo `C:\Users\ryanv\llm-bim`
4. Run focused tests (`pytest tests/unit -q` or subset)
5. Commit if green: `[grok] vision-loop N: <summary>`
6. Append pass row to this log; update backlog
7. If pass_count ≥ **120** or past 10h end → stop, write FINAL summary
