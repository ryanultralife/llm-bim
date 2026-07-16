#!/usr/bin/env python3
"""Deterministic health check for the llm-bim vision alignment loop.

Run by the OVERSEER agent every ~30 minutes (or manually):

  python scripts/vision_overseer_check.py
  python scripts/vision_overseer_check.py --json
  python scripts/vision_overseer_check.py --pytest

Exit codes:
  0  healthy (or healthy-with-notes)
  1  unhealthy — action required
  2  script error
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VISION = ROOT / "notes" / "handoffs" / "VISION_LOOP.md"
OVERSEER_LOG = ROOT / "notes" / "handoffs" / "OVERSEER_LOG.md"
MAX_PASSES = 120
# If no vision-loop commit in this many minutes while still under pass cap → stale
STALE_MINUTES = 45
# Hard window (matches VISION_LOOP started session + 10h)
WINDOW_HOURS = 10


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _git(*args: str, timeout: int = 60) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out.strip()
    except Exception as e:  # noqa: BLE001
        return 2, str(e)


def parse_vision_loop() -> dict:
    """Extract pass count and last pass row from VISION_LOOP.md."""
    info: dict = {
        "path": str(VISION),
        "exists": VISION.is_file(),
        "pass_count": 0,
        "last_pass": None,
        "max_passes": MAX_PASSES,
        "started_hint": None,
    }
    if not VISION.is_file():
        return info
    text = VISION.read_text(encoding="utf-8")
    # pass table rows: | N | ...
    nums = []
    last_row = None
    for line in text.splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|", line)
        if m:
            n = int(m.group(1))
            nums.append(n)
            last_row = line
        if line.startswith("**Started:**"):
            info["started_hint"] = line.split("**Started:**", 1)[-1].strip()
    if nums:
        info["pass_count"] = max(nums)
        info["last_pass"] = last_row
    return info


def recent_vision_commits(limit: int = 15) -> list[dict]:
    code, out = _git("log", f"-{limit}", "--format=%H|%ci|%s")
    if code != 0:
        return []
    rows = []
    for line in out.splitlines():
        if not line.strip() or "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        sha, ci, subj = parts[0], parts[1], parts[2]
        is_vl = "[grok] vision-loop" in subj or "vision-loop" in subj.lower()
        rows.append({"sha": sha[:10], "date": ci, "subject": subj, "vision_loop": is_vl})
    return rows


def minutes_since_last_vision_commit(commits: list[dict]) -> float | None:
    for c in commits:
        if not c.get("vision_loop"):
            continue
        # git %ci like 2026-07-15 12:34:56 -0700
        try:
            # parse first 19 chars as naive local; use fromisoformat with fix
            raw = c["date"]
            # normalize: "2026-07-15 19:30:00 +0000" → iso
            raw = raw.replace(" ", "T", 1)
            # if trailing +0000 without colon
            raw = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", raw)
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (_utc_now() - dt.astimezone(timezone.utc)).total_seconds() / 60.0
        except Exception:  # noqa: BLE001
            continue
    return None


def working_tree_dirty() -> bool:
    code, out = _git("status", "--porcelain")
    return code == 0 and bool(out.strip())


def branch_status() -> dict:
    code, out = _git("status", "-sb")
    ahead = behind = 0
    branch = "unknown"
    if code == 0 and out:
        first = out.splitlines()[0]
        # ## main...origin/main [ahead 2, behind 1]
        m = re.match(r"##\s+(\S+)", first)
        if m:
            branch = m.group(1).split("...")[0]
        am = re.search(r"ahead\s+(\d+)", first)
        bm = re.search(r"behind\s+(\d+)", first)
        if am:
            ahead = int(am.group(1))
        if bm:
            behind = int(bm.group(1))
    return {"branch": branch, "ahead": ahead, "behind": behind, "raw": out.splitlines()[0] if out else ""}


def run_pytest(timeout: int = 180) -> dict:
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)
    try:
        r = subprocess.run(
            [str(py), "-m", "pytest", "tests/unit", "-q", "--tb=line"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        tail = "\n".join((r.stdout or "").splitlines()[-8:])
        # parse "N passed"
        passed = failed = 0
        m = re.search(r"(\d+)\s+passed", r.stdout or "")
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+)\s+failed", r.stdout or "")
        if m:
            failed = int(m.group(1))
        return {
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "passed": passed,
            "failed": failed,
            "tail": tail,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": -1, "passed": 0, "failed": 0, "tail": "pytest timeout"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "returncode": 2, "passed": 0, "failed": 0, "tail": str(e)}


def assess(include_pytest: bool) -> dict:
    vl = parse_vision_loop()
    commits = recent_vision_commits()
    mins = minutes_since_last_vision_commit(commits)
    branch = branch_status()
    dirty = working_tree_dirty()

    issues: list[str] = []
    notes: list[str] = []
    actions: list[str] = []

    if not vl["exists"]:
        issues.append("VISION_LOOP.md missing")
        actions.append("Restore notes/handoffs/VISION_LOOP.md from git")

    pass_count = int(vl.get("pass_count") or 0)
    done = pass_count >= MAX_PASSES
    if done:
        notes.append(f"Pass count {pass_count} ≥ {MAX_PASSES} — vision loop should STOP")
    elif mins is None:
        issues.append("No vision-loop commits found in recent history")
        actions.append("Verify 5m scheduler still registered; run a vision-loop pass")
    elif mins > STALE_MINUTES and not done:
        issues.append(
            f"Stale: last vision-loop commit was {mins:.0f}m ago (threshold {STALE_MINUTES}m)"
        )
        actions.append(
            "Investigate why 5m loop stalled; fix blockers; run one vision-loop pass if green"
        )
    else:
        notes.append(f"Last vision-loop commit {mins:.0f}m ago (ok)" if mins is not None else "")

    if branch.get("behind", 0) > 0:
        issues.append(f"Branch behind origin by {branch['behind']}")
        actions.append("git pull --ff-only (or rebase) before next pass")

    if dirty:
        notes.append("Working tree has uncommitted changes")
        # not always an issue — mid-pass is ok; ignore after budget (pass ≥ 120)
        if mins is not None and mins > 20 and not done:
            issues.append("Dirty tree with no recent vision commit — possible abandoned pass")
            actions.append("Finish or stash WIP; commit if tests green")

    pytest_result = None
    if include_pytest:
        pytest_result = run_pytest()
        if not pytest_result.get("ok"):
            issues.append(
                f"Unit tests failing ({pytest_result.get('failed')} failed, "
                f"{pytest_result.get('passed')} passed)"
            )
            actions.append("Fix failing tests before more vision-loop feature work")
        else:
            notes.append(f"pytest unit ok: {pytest_result.get('passed')} passed")

    # health file existence for overseer log
    status = "unhealthy" if issues else "healthy"
    if not issues and any("STOP" in n for n in notes):
        status = "complete"

    report = {
        "ts_utc": _utc_now().isoformat(),
        "status": status,
        "repo": str(ROOT),
        "vision_loop": vl,
        "branch": branch,
        "dirty": dirty,
        "minutes_since_last_vision_commit": mins,
        "stale_threshold_minutes": STALE_MINUTES,
        "recent_commits": commits[:8],
        "pytest": pytest_result,
        "issues": [i for i in issues if i],
        "notes": [n for n in notes if n],
        "actions": actions,
        "overseer_log": str(OVERSEER_LOG),
    }
    return report


def append_log(report: dict) -> None:
    OVERSEER_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not OVERSEER_LOG.is_file():
        OVERSEER_LOG.write_text(
            "# Overseer health log\n\n"
            "Append-only. Written by `scripts/vision_overseer_check.py` "
            "and the 30m OVERSEER agent.\n\n",
            encoding="utf-8",
        )
    status = report["status"]
    issues = report.get("issues") or []
    actions = report.get("actions") or []
    pytest_ = report.get("pytest") or {}
    line = (
        f"## {report['ts_utc'][:19]}Z — **{status.upper()}**\n\n"
        f"- pass_count: `{report['vision_loop'].get('pass_count')}` / {MAX_PASSES}\n"
        f"- last_vision_commit_age_min: `{report.get('minutes_since_last_vision_commit')}`\n"
        f"- branch: `{report['branch'].get('raw')}`\n"
        f"- dirty: `{report.get('dirty')}`\n"
    )
    if pytest_:
        line += (
            f"- pytest: ok=`{pytest_.get('ok')}` "
            f"passed=`{pytest_.get('passed')}` failed=`{pytest_.get('failed')}`\n"
        )
    if issues:
        line += "- **issues:**\n" + "".join(f"  - {i}\n" for i in issues)
    if actions:
        line += "- **actions:**\n" + "".join(f"  - {a}\n" for a in actions)
    notes = report.get("notes") or []
    if notes:
        line += "- notes:\n" + "".join(f"  - {n}\n" for n in notes)
    line += "\n"
    with OVERSEER_LOG.open("a", encoding="utf-8") as f:
        f.write(line)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Vision loop overseer health check")
    ap.add_argument("--json", action="store_true", help="Print full JSON report")
    ap.add_argument("--pytest", action="store_true", default=True, help="Run unit tests (default)")
    ap.add_argument("--no-pytest", action="store_true", help="Skip unit tests")
    ap.add_argument("--no-log", action="store_true", help="Do not append OVERSEER_LOG.md")
    args = ap.parse_args(argv)

    include_pytest = not args.no_pytest
    try:
        report = assess(include_pytest=include_pytest)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"status": "error", "error": str(e)}), file=sys.stderr)
        return 2

    if not args.no_log:
        try:
            append_log(report)
        except Exception as e:  # noqa: BLE001
            report.setdefault("notes", []).append(f"log append failed: {e}")

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"status: {report['status']}")
        print(f"pass_count: {report['vision_loop'].get('pass_count')}/{MAX_PASSES}")
        print(f"minutes_since_vl: {report.get('minutes_since_last_vision_commit')}")
        print(f"branch: {report['branch'].get('raw')}")
        if report.get("pytest"):
            p = report["pytest"]
            print(f"pytest: ok={p.get('ok')} passed={p.get('passed')} failed={p.get('failed')}")
        for i in report.get("issues") or []:
            print(f"ISSUE: {i}")
        for a in report.get("actions") or []:
            print(f"ACTION: {a}")
        for n in report.get("notes") or []:
            print(f"note: {n}")
        print(f"log: {OVERSEER_LOG}")

    return 0 if report["status"] in ("healthy", "complete") else 1


if __name__ == "__main__":
    raise SystemExit(main())
