# Shareability audit — is llm-bim safe to open publicly?

**Date:** 2026-07-28 · **Auditor:** Grok  
**Repo visibility at audit:** **PUBLIC** (`https://github.com/ryanultralife/llm-bim`)  
**Verdict (honest):** **Not fully stripped.** The **kernel + skills** are fine to share as MIT OSS.  
**`projects/schad` (and related docs)** still carried **real client site identity** until the redaction pass below. **Git history still retains pre-redaction strings** until rewritten. **`projects/intec`** is company facility IP (engineering estimates) — suitable as a *demo case* only if you accept publishing that class of design-basis data.

---

## Executive answer

| Layer | Share as public OSS? | Notes |
|-------|----------------------|--------|
| `packages/**` kernel | **Yes** | No secrets; pure modeling stack |
| `skills/**`, install scripts, CI | **Yes** | Generic agent instructions |
| `examples/` office/warehouse templates | **Yes** | Generic |
| `projects/schad/**` | **Only after PII redaction** | Was real address / owners / APN / designer name |
| `projects/intec/**` | **Business judgment** | ATR-SNF separation facility design-basis case (not PE-stamped, but proprietary domain) |
| `output/**` | **N/A** | gitignored; never commit packs |
| `.env` / API keys | **Clean** | `.env` gitignored; only empty `.env.example` |
| Git **history** | **Not clean** | Pre-redaction commits still contain client strings |

**Bottom line for “can others clone this?”**  
- **Technically:** yes — already public, MIT, installs, CI green.  
- **Privacy / client ethics:** **not clean enough before redaction**; after HEAD redaction, still **warn that history is not scrubbed**.  
- **Competitive IP (INTEC / MB facility):** share only if intentional.

---

## What we checked

### Secrets / credentials
| Check | Result |
|-------|--------|
| `.env` in tree | Absent |
| `.env.example` | Empty placeholders only (`LLMBIM_API_KEY=`) |
| Hardcoded API keys / tokens | None found in tracked source |
| `output/` tracked | **0** files |
| Private key / PEM files | None in current tree |

### Client / PII (Schad case) — **failed before redaction**
Present on `main` prior to the 2026-07-28 sanitization pass (categories only —
this doc deliberately does NOT repeat the redacted values; they remain in git
history until a scrub):

| Data class | What was present |
|------------|------------------|
| Street address | full site street address + town + ZIP |
| Parcel | county assessor parcel number (+ neighbors) |
| Owners | client couple's personal names |
| Designer personal name | designer-of-record's personal name |
| Firm / project no. | design firm name + internal project number |
| Local paths (docs) | contributor home-dir and personal cloud-drive paths |
| Site GIS narrative | county parcel geometry notes |

### Company / facility cases
| Case | Risk |
|------|------|
| INTEC / MB-INT-CAD-001 | Full 128-sheet design-basis facility pack + frozen Eigen systems snapshot — **not personal PII**, but **business/process IP** if you treat it as proprietary |
| Proto10 separator | Equipment geometry class shared with Fusion/Eigen threads — engineering estimate |

### Commit author emails (history)
Visible via `git log`: the maintainer's personal commit email, GitHub noreply, and agent noreply addresses. Normal for OSS; switch to GitHub noreply going forward if preferred (past commits keep the old address unless history is rewritten).

---

## Grok residual board (for Claude)

Drawings-lane residuals **#3–5, #9–10, #13–14** closed on `main` (`f44eee4`, `6f3c4de`).  
INTEC Gate C landed (`7a14389`).  
text-to-cad adoption partial (review packet + repair refs); **`llmbim inspect`** still open.

---

## Recommended share postures

### A — Public OSS product (recommended default)
1. Keep `packages/`, `skills/`, generic `examples/`, CI public.  
2. **Redact** Schad identity to demo placeholders (this pass).  
3. Either keep INTEC as labeled **[ENGINEERING ESTIMATE] demo** or move to a **private** repo.  
4. Optional: `git filter-repo` history purge of address/owner strings (coordinate; force-push).  
5. Add `SECURITY.md` + this doc to README “Privacy” section.

### B — Public kernel, private projects
1. Split `projects/schad` + `projects/intec` to private org repo.  
2. Public repo ships only synthetic fixtures under `examples/`.  
3. History rewrite or new clean root commit for public side.

### C — Private / customer-only
1. Make GitHub repo **private** until redaction + history scrub complete.  
2. Fastest stopgap if client confidentiality is non-negotiable **right now**.

---

## What redaction does *not* fix

- **Git history** still contains old blobs until rewritten.  
- **Forks / mirrors / CI logs / local clones** may retain pre-redaction copies.  
- **Generated packs** under `output/` on developer machines (gitignored) may still have old title blocks — delete or rebuild.  
- **INTEC** remains a full facility case (IP judgment, not PII).

---

## Checklist before inviting external collaborators

- [x] Repo MIT-licensed  
- [x] No API secrets in tree  
- [x] `output/` not tracked  
- [x] Schad PII redacted on **HEAD** — Grok pass 2026-07-28 + Claude residue pass same day
      (firm name, city, cloud-drive/home paths, audit-JSON paths, title-block firm string;
      this doc no longer repeats redacted values verbatim; verified by tracked-tree sweep:
      0 hits on all client-identity patterns)  
- [x] **History scrubbed — 2026-07-28 (human-approved).** `git filter-repo
      --replace-text` rewrote all 330 commits (client identity → the same synthetic
      demo values used on HEAD); force-pushed. **Verified by fresh clone from GitHub:
      0 hits on every pattern across the entire history.** Merged side branches +
      the backup tag were deleted from the public remote first.
- [x] **Full-fidelity preservation:** complete pre-scrub mirror (all branches, tags,
      unredacted history incl. Schad + INTEC) archived to the **PRIVATE** repo
      `ryanultralife/llm-bim-archive`. Do not make it public.
- [x] INTEC decision (human): **keep in the public repo** as a labeled
      engineering-estimate demo case; real archive is private.
- [x] Case name: **"Schad" stays** (human decision) — address/owners/designer are
      synthetic everywhere; the name alone no longer links to a person or place.
- [x] README points to this doc  

### Residual exposure after the scrub (honest)

- **GitHub `refs/pull/N/head` are immutable** — old PR refs still reference
  pre-scrub objects on GitHub's servers until their GC (a GitHub Support request
  can purge them explicitly). They are not in any clone of `main`.
- **Anyone who cloned/forked before 2026-07-28** has the pre-scrub history.
- ⚠️ **AGENTS: do not push any branch created before 2026-07-28** — it carries
  pre-scrub history and would resurrect the redacted data on the public remote.
  This includes **Grok's isolation worktree (`llm-bim-schad`)**: rebase your work
  onto the new `main` (`git fetch && git rebase --onto origin/main <old-base>`)
  or cherry-pick; never plain-push from an old base.
