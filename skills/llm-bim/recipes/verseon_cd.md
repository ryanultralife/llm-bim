# Recipe — issue a pack to the Verseon CD bar

Read **`docs/VERSEON_CD_STANDARD.md`** first. Walk
`docs/standards/verseon_cd_checklist.json` before saying done.

1. One overlay per sheet (same cut, different `include` / `tags`).
2. `units="imperial"` + `dim_tiers` + `room_areas` + `key_plan` + `keynotes`.
3. Work plans at **1/8″ = 1′-0″**. Do not fit-stretch. Title block is
   **3.5″** on a 42″ sheet (wrap titles). Leftover sheet width is a
   section + notes column.
4. Overall plans: rooms + grids + match line only. No W-section / window-type
   storm. SEE the 1/8″ sheets.
5. MEP overlays: `ghost_walls=True`, sized runs, equipment leaders.
6. Details: self-contained modules (`kind: details`), two-way callouts.
7. Stamp `[ENGINEERING ESTIMATE]`. Empty PE zone.

Evidence PDFs stay on Ryan's OneDrive (see the standard). Do **not** commit
those PDFs into git.
