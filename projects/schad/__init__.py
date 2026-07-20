"""SCHAD pure design SSOT + note-driven CD generators.

Ported from the Demo Studio / Schad Revit digital thread (portable modules
only). No Revit API. Numbers live in schad_design_basis and friends.

Build note-driven pack (no llm-bim kernel required):
  python -m projects.schad.build_notes_cd
  # or:  python projects/schad/build_notes_cd.py
"""

from __future__ import annotations

__all__ = ["SCHAD_PROJECT"]

SCHAD_PROJECT = {
    "number": "2024-008",
    "name": "SCHAD Garage / ADU / Workshop",
    "address": "100 Example Way, Sample County CA 90000",
    "status": "[DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION]",
}
