"""Machine / skid construction set — Sierra Star anatomy on equipment packs.

Wall-less models (MineClean, Proto-10, field skids) used to skip the
construction register and emit only part sheets + an un-annotated AABB plan.
This module is the default register for that class: one model cut, then
grids / dim chains / instance tags / elevations / equipment schedule.

Used automatically by ``export_construction_set`` when the model has
equipment and no walls, and by ``export_deliverables(mode="part")``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmbim_core.model import ProjectModel

from llmbim_drawings.construction import export_construction_set
from llmbim_drawings.layout import table_view
from llmbim_drawings.view import DrawingView

MACHINE_HONESTY = (
    "[ENGINEERING ESTIMATE] — model-cut GA; not PE sealed; not for construction issue"
)

DEFAULT_COVER_NOTES = [
    "WRITTEN DIMENSIONS GOVERN — DO NOT SCALE.",
    MACHINE_HONESTY,
    "Sheet graphics are projected from the 3-D model. Annotation sits on the cut.",
    "Instance tags (M- / EQ-) key to the equipment schedule on EQ-501.",
]


def _level_name(model: ProjectModel, plan_level: str | None) -> str:
    if plan_level:
        return plan_level
    if model.levels:
        return model.levels[0].name
    return "L1"


def _meta_notes(model: ProjectModel) -> list[str]:
    meta = model.meta or {}
    raw = meta.get("process_notes") or meta.get("honesty_notes") or meta.get("cover_notes")
    notes: list[str] = []
    if isinstance(raw, str) and raw.strip():
        notes.append(raw.strip())
    elif isinstance(raw, (list, tuple)):
        notes.extend(str(x).strip() for x in raw if str(x).strip())
    honesty = meta.get("honesty")
    if isinstance(honesty, str) and honesty.strip() and honesty.strip() not in notes:
        notes.append(honesty.strip())
    return notes


def machine_schedule_view(model: ProjectModel) -> DrawingView:
    """One row per parent machine tag (not every part)."""
    rows_by: dict[str, dict[str, Any]] = {}
    for el in model.elements:
        if el.category != "equipment":
            continue
        pr = el.params or {}
        tag = str(
            pr.get("equipment_tag") or pr.get("equipment") or pr.get("tag") or ""
        ).strip()
        if not tag:
            tag = str(el.name or el.id)[:24]
        rec = rows_by.get(tag)
        if rec is None:
            rows_by[tag] = {
                "tag": tag,
                "name": str(pr.get("equipment_name") or pr.get("label") or el.name or tag)[:48],
                "kind": str(pr.get("kind") or ""),
                "parts": 1,
            }
        else:
            rec["parts"] += 1
            full = str(pr.get("equipment_name") or "")
            if full and len(full) > len(str(rec.get("name") or "")):
                rec["name"] = full[:48]
    rows = [
        [r["tag"], r["name"], r["kind"], str(r["parts"])]
        for r in sorted(rows_by.values(), key=lambda x: str(x["tag"]))
    ]
    return table_view(
        ["TAG", "EQUIPMENT", "KIND", "N PARTS"],
        rows or [["—", "(no equipment)", "", ""]],
        title="Equipment — parent machines",
    )


def machine_sheet_register(
    model: ProjectModel,
    *,
    plan_level: str | None = None,
    notes: list[str] | None = None,
    callouts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Custom construction register for a machine / skid pack.

    EQ-101 is the Sierra Star–style GA plan (grids, 3-tier dims, leader tags).
    """
    level = _level_name(model, plan_level)
    cover_notes = list(notes or [])
    cover_notes.extend(_meta_notes(model))
    seen = set(cover_notes)
    for n in DEFAULT_COVER_NOTES:
        if n not in seen:
            cover_notes.append(n)
            seen.add(n)
    return [
        {
            "no": "G-001",
            "title": "COVER / DRAWING LIST",
            "kind": "cover",
            "subtitle": "MACHINE / SKID GENERAL ARRANGEMENT",
            "notes": cover_notes,
        },
        {
            "no": "EQ-101",
            "title": "GENERAL ARRANGEMENT — PLAN",
            "kind": "plan",
            "level": level,
            "include": [
                "equipment",
                "pipes",
                "grids",
                "columns",
                "beams",
                "notes",
                "slabs",
            ],
            "tags": True,
            "dim_tiers": True,
            "grid_dims": True,
            "keynotes": True,
            "auto_grid": True,
            "collapse_equipment": True,
            "dimensions": True,
            "grid_sides": "framing",
            "callouts": list(callouts or []),
        },
        {
            "no": "EQ-201",
            "title": "ELEVATIONS — SOUTH & EAST",
            "kind": "elevations",
            "pair": ["S", "E"],
        },
        {
            "no": "EQ-301",
            "title": "SECTION — LONGITUDINAL",
            "kind": "sections",
        },
        {
            "no": "EQ-501",
            "title": "EQUIPMENT SCHEDULE",
            "kind": "custom_svg",
            "provider": machine_schedule_view,
        },
    ]


def export_machine_set(
    model: ProjectModel,
    out_dir: str | Path,
    *,
    plan_level: str | None = None,
    plan_scale: float = 0.06,
    units: str = "metric",
    notes: list[str] | None = None,
    callouts: list[dict[str, Any]] | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    """Write the machine/skid GA set into ``out_dir`` (usually ``construction/``)."""
    return export_construction_set(
        model,
        out_dir,
        plan_level=plan_level,
        plan_scale=plan_scale,
        units=units,
        date=date,
        dim_tiers=True,
        keynotes=True,
        stamp_block=True,
        sheets=machine_sheet_register(
            model, plan_level=plan_level, notes=notes, callouts=callouts
        ),
    )
