# Claude cold-start brief (complete — no chat needed)

You are **slow and thorough**. Grok is **fast and integrates**. Use that:

## Do this once

```bash
git pull origin main
pip install -e ".[dev]"
pytest                    # default suite — must stay green; does NOT run your WP tests
```

Read in order:

1. `docs/AGENT_SPEED.md` — tempo rules  
2. `docs/WORK_PACKAGES.md` — **claim WP-DRAWINGS** (prefer)  
3. `TEAM_STATUS.md` — mark claimed  
4. `docs/DESIGN.md` — product constraints  

## Claim (edit TEAM_STATUS.md, commit)

```
WP-DRAWINGS | Claude | feature/wp-drawings | claimed | freeze: packages/drawings/**
```

Branch: `feature/wp-drawings`  
**Only edit freeze zone** listed in the work package.

## Implement

- Replace `NotImplementedBimError` in `packages/drawings/llmbim_drawings/api.py`
- Keep **function signatures identical**
- Axes: +X east, +Y north; model units mm

## Prove

```bash
pytest -m wp_drawings
```

All three acceptance tests must pass.

## Then

Open PR → update STATUS → write `notes/handoffs/YYYY-MM-DD-claude.md`  
Optional next package: **WP-IFC** (separate freeze zone; can be a second session).

## Do NOT

- Rewrite `packages/core` or invent a second Project API  
- Add a human drafting UI  
- Split into many tiny PRs that need Grok sync mid-flight  
- Block waiting for Grok on drawings — model already has walls/slabs/doors/rooms  

## Model already supports (Grok critical path)

```python
from llmbim import Project
p = Project.create("x")
p.add_level / add_grid / create_wall / create_slab
p.place_door / place_window / create_room
p.undo / redo / save / open
```

Fixture builder is in `tests/wp/test_wp_drawings_acceptance.py` (`_sample_project`).
