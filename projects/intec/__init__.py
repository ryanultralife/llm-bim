"""INTEC ATR-SNF Separation Facility — llm-bim construction pack.

Source of truth:
  - ``intec_design_basis.py`` — scalars/placements/128-sheet register (MB-INT-CAD-001)
  - ``data/eigen_systems_snapshot.json`` — frozen facility_systems / bid / module engines
  - ``intec_derived.py`` — derived schedule SVG sheets from that snapshot

Honesty: [ENGINEERING ESTIMATE] — design-basis class; final CD + PE seal by A-E at DS-2.

Run:
  python projects/intec/build_construction_set.py
  python projects/intec/freeze_eigen_snapshot.py   # re-pull Eigen engines
  pytest tests/unit/test_intec_sheets.py
"""

from __future__ import annotations

__all__ = ["build_pack", "HONESTY"]

HONESTY = (
    "[ENGINEERING ESTIMATE] — design-basis class; arrangement per INT-GA-001. "
    "Final CD production + PE stamping by the A-E firm at DS-2."
)


def build_pack(out_dir=None):
    from .build_llmbim import build_pack as _build

    return _build(out_dir)
