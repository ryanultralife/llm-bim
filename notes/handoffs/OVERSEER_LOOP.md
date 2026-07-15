# Vision-loop OVERSEER (30-minute health agent)

**Role:** Watchdog for the 5-minute vision alignment loop — not a feature builder.  
**Repo:** `C:\Users\ryanv\llm-bim`  
**Cadence:** every **30 minutes**  
**Companion loop:** `notes/handoffs/VISION_LOOP.md` (5m builder, ~120 passes / 10h)  
**Health log:** `notes/handoffs/OVERSEER_LOG.md` (append-only)

## Why this exists

The 5m vision loop can stall (scheduler drop, red tests, dirty abandoned WIP, no commits).  
This overseer **detects** that within ~30m and **repairs or escalates**.

## Hard rules

1. **Do not** start a new mega-feature just because you are awake — that is the 5m loop’s job.
2. **Do** run the health script first and follow its `actions`.
3. **Do** fix broken tests / stuck WIP if the loop is unhealthy.
4. **Do** commit health-log updates: `[grok] overseer: <status>`.
5. **Stop supervising** when pass_count ≥ 120 or the 10h hard-stop has fired (status `complete`).
6. User instruction: builders keep going without “Next:” teasers; overseer only **summarizes health**.

## Every fire — checklist

```text
1. cd C:\Users\ryanv\llm-bim
2. python scripts/vision_overseer_check.py --json
   (uses .venv if present: .\.venv\Scripts\python.exe scripts\vision_overseer_check.py --json)
3. Read notes/handoffs/VISION_LOOP.md last 5 pass rows
4. git log -10 --oneline ; git status -sb
5. If status == healthy or complete → append nothing extra beyond script log; optional empty commit of log; push
6. If status == unhealthy → execute actions (fix tests, finish/stash WIP, kick one vision pass if stalled)
7. Re-run health script; commit OVERSEER_LOG (+ fixes); push origin main
8. Short status only — no “Next:” feature teaser
```

## Health criteria (script-enforced)

| Check | Unhealthy if |
|-------|----------------|
| Vision commits | No `[grok] vision-loop` commit for **>45 minutes** while pass_count < 120 |
| Tests | `pytest tests/unit` fails |
| Remote | Branch **behind** origin |
| WIP | Dirty tree **and** no vision commit for >20m (abandoned pass) |
| Loop file | `VISION_LOOP.md` missing |

## Scheduler ids

| Job | Interval | Purpose | Scheduler id |
|-----|----------|---------|--------------|
| Vision builder | 5m | Gap fix / feature pass | `019f673f9283` |
| **Overseer (this)** | **30m** | Health / repair | `019f676dfd70` |
| Hard stop | 10h once | End vision window | (same family / 10h task) |

## Manual run

```powershell
cd C:\Users\ryanv\llm-bim
.\.venv\Scripts\python.exe scripts\vision_overseer_check.py --json
```

## On unhealthy — preferred repair order

1. `pytest tests/unit -q --tb=short` → fix failures → commit
2. `git status` → finish mid-pass or stash noise
3. If stale only (tests green, clean tree): perform **one** vision-loop pass (highest backlog gap), commit, push
4. If 5m scheduler appears dead (many stale oversights): note in OVERSEER_LOG; recreate is a human/Grok scheduler action

## Done condition

When `pass_count ≥ 120` or hard-stop has run: log `complete`, do not spawn more vision work.
