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
