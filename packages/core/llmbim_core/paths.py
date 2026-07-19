"""Default local output paths — agent chat → files on disk."""

from __future__ import annotations

import os
import re
from pathlib import Path


def repo_root() -> Path:
    """Best-effort repo root (cwd if not in a clone)."""
    cwd = Path.cwd().resolve()
    for p in [cwd, *cwd.parents]:
        if (p / "pyproject.toml").is_file() and (p / "packages").is_dir():
            return p
    return cwd


def output_root() -> Path:
    """Root folder for all agent deliverables (default ./output)."""
    env = os.environ.get("LLMBIM_OUTPUT_DIR")
    if env:
        root = Path(env).expanduser().resolve()
    else:
        root = repo_root() / "output"
    root.mkdir(parents=True, exist_ok=True)
    return root


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", name.strip(), flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return s or "project"


def project_output_dir(name: str, *, create: bool = True) -> Path:
    """output/<slug>/ for a named project."""
    d = output_root() / slugify(name)
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def _is_populated_project(d: Path) -> bool:
    """True if ``d`` already holds a real project (committed history or a
    non-empty working model) that must not be silently overwritten."""
    versions = d / ".llmbim" / "versions"
    if versions.is_dir() and any(versions.glob("ver_*.json")):
        return True
    model = d / "model.llmbim.json"
    if model.is_file():
        try:
            import json

            data = json.loads(model.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return True  # unreadable but present — do not clobber
        return bool(data.get("elements") or data.get("levels"))
    return False


def unique_project_dir(name: str) -> Path:
    """output/<slug>/ for a NEW project, but never one that already holds work.

    If the base slug dir already contains a populated project (a name collision
    or a re-run of the same build script), fall back to ``<slug>-2``, ``-3`` …
    so the new project gets its own space instead of destroying the old one.
    """
    base = output_root() / slugify(name)
    if not _is_populated_project(base):
        base.mkdir(parents=True, exist_ok=True)
        return base
    i = 2
    while True:
        cand = output_root() / f"{slugify(name)}-{i}"
        if not _is_populated_project(cand):
            cand.mkdir(parents=True, exist_ok=True)
            return cand
        i += 1
