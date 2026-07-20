"""SCHAD Phase 1 — repo-first build harness (WP-SCHAD-S0).

Basis → Project → model VCS commit → output/schad_garage/ construction set.

The design basis is imported ONLY from ``projects/schad`` — the in-repo SSOT.
No ``SCHAD_ROOT`` / G:-drive lookup: the repo is the CI source of truth.
(``examples/schad_garage.py`` stays as-is for local G:-drive sync use.)

Wall/door/window types are the WP-SCHAD-S1 residential registry — no Schad
wall maps to the industrial W-EXT-CMU / W-INT-GYP catalog (transition §8).

Honesty: [DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION].

Run (from anywhere):
  python examples/schad_build.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "output" / "schad_garage"


def _bootstrap() -> None:
    """Make ``projects.schad`` importable when run as a script."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


def build_schad_model() -> Any:
    """Basis → Project only (no VCS dir, no export). Used by the unit tests."""
    _bootstrap()
    from projects.schad.build_llmbim import build_model

    return build_model()


def build_schad(out_dir: Path | None = None) -> Any:
    """Full pack: build, commit to model VCS, export construction set."""
    _bootstrap()
    from projects.schad.build_llmbim import build_pack

    project, _verify = build_pack(out_dir or DEFAULT_OUT)
    return project


def main() -> int:
    build_schad()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
