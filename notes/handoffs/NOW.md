# NOW — current state and active work

**Updated:** 2026-07-28 by Grok

## Active — excellence residuals (Grok drawings lane) CLOSED this session

| # | Item | Status |
|---|------|--------|
| 1 | MEP sheets draw routed geometry | ✅ Grok `fbf7d29` |
| 2 | hero.svg in pack | ✅ Claude PR #33 |
| 3 | PDF stroke-width / dashes / fills / arcs | ✅ this session |
| 4 | Imperial graphic scale bar (ft) | ✅ this session |
| 5 | PDF MediaBox ANSI B for imperial | ✅ this session |
| 6–8, 11–12, 15 | Kernel / connectivity / textures | ✅ Claude wave 2 |
| 9 | LINE LEGEND bottom gutter | ✅ this session |
| 10 | SHEET_INDEX order + human cover rows | ✅ this session |
| 13 | A1-1 annotation collision | open (low) |
| 14 | Photoreal ceiling | open (low / either) |

Tests: `tests/unit/test_pdf_residuals.py` · prior `test_mep_sheets_draw_routed_geometry`

## Also landed this session

- **WP-INTEC** — `projects/intec/` + 13 Gate C tests + `llmbim case intec` → full 128-sheet pack
  (`7a14389`). OPEN: `output/intec_construction/index.html` after rebuild.

## Remaining (low priority)

- **#13** annotation collision nudge on A1-1
- **#14** HDR IBL / true AO / raster hero
- **text-to-cad** reference writeup (Claude pointer)

## Standing contracts

- Entry: `skills/llm-bim/SKILL.md` (+ `CLAUDE.md` / `AGENTS.md`)
- Excellence queue: `docs/EXCELLENCE_AUDIT_2026-07-21.md`
- Acceptance: `docs/CD_COMPLETENESS_STANDARD.md`
