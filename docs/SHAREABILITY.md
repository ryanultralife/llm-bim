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
Present on `main` prior to 2026-07-28 sanitization pass:

| Data | Examples |
|------|----------|
| Street address | `100 Example Way, Sample County CA 90000` |
| Parcel | APN `000-000-000` (+ neighbors) |
| Owners | `the Owners` |
| Designer personal name | `the Designer` |
| Firm / project no. | Demo Studio · 2024-008 |
| Local paths (docs) | `<HOME>\…`, `<LOCAL_ARCHIVE>\Schad Garage\…` |
| Site GIS narrative | [COUNTY] parcel geometry notes |

### Company / facility cases
| Case | Risk |
|------|------|
| INTEC / MB-INT-CAD-001 | Full 128-sheet design-basis facility pack + frozen Eigen systems snapshot — **not personal PII**, but **business/process IP** if you treat it as proprietary |
| Proto10 separator | Equipment geometry class shared with Fusion/Eigen threads — engineering estimate |

### Commit author emails (history)
Visible via `git log`: `ryan@example.com`, GitHub noreply, agent noreply addresses. Normal for OSS; use GitHub noreply only if preferred.

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
- [ ] Schad PII redacted on **HEAD** (see next commit)  
- [ ] History scrub **or** accept residual disclosure risk  
- [ ] Explicit decision on INTEC public vs private  
- [ ] README points to this doc  
