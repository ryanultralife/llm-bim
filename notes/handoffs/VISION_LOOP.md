# Vision ↔ codebase alignment loop

**Started:** 2026-07-15 (session)  
**Cadence:** every 5 minutes  
**Duration:** 2 hours (~24 passes max)  
**End:** stop after 24 passes or when wall-clock ≥ start + 2h  

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
| 5 | T+20m | IFC pipe/fitting/fixture | IFC only walls/equip | BuildingElementProxy for pipe/fitting/fixture/module | 70 unit pass | (pending) |

## Backlog (living — pull highest impact each pass)

1. ~~OUTPUT_MATRIX incomplete~~ (pass 1)
2. ~~VISION roadmap stale~~ (pass 1)
3. ~~BOQ unit for linear steel `m`~~ (pass 2)
4. ~~Verify pack materials/~~ (pass 3)
5. ~~MCP tools for place_part / takeoff~~ (pass 1)
6. ~~IFC export fittings/pipe~~ (pass 5)
7. glTF for pipe/fitting markers (optional)
8. Skill SKILL.md section order (H2 awkward)
9. chat_smoke covers multi-trade ops
10. ~~CSI division 00 on process parts~~ (pass 4, related)
11. ~~part_summary unit for linear m parts~~ (pass 2)
12. ~~Process separator CSI~~ (pass 4)
13. MCP tools for import_module / connect (modules via project_op only)
14. ~~OUTPUT_MATRIX modules~~ (pass 4)

**Next suggested focus:** #13 MCP module tools or #7 glTF pipe markers

## Rules for each scheduled pass

1. Read this file + `docs/VISION.md` + `docs/CAPABILITY.md` + `docs/OUTPUT_MATRIX.md`
2. Pick **one** highest-impact gap from backlog or a new discovered gap
3. Implement fix in repo `C:\Users\ryanv\llm-bim`
4. Run focused tests (`pytest tests/unit -q` or subset)
5. Commit if green: `[grok] vision-loop N: <summary>`
6. Append pass row to this log; update backlog
7. If pass_count ≥ 24 or past end time → stop, do not schedule more work, write FINAL summary
