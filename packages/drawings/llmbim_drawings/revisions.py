"""Auto-clouding from model version diffs (WP-CD-ANATOMY-2).

Pure functions — no file I/O, no SVG. Diff two ``ProjectModel`` states
(prior issue vs current) and turn the added / changed / removed element set
into plan-space (mm) revision-cloud rectangles per level, plus revision-table
row data. Sheet registers map the mm rects into sheet coordinates and hand
them to the existing primitives (``llmbim_drawings.sheets.revision_cloud`` /
``compose_sheet(..., clouds=[...])``); this module never renders.

Diff semantics follow ``llmbim_core.versioning.diff_models``: an element is
*added* / *removed* by id set difference between the two models, and
*changed* when its serialized dict (params/geometry, name, category,
level_id, host_id, type_id) differs. Cloud placement:

- **added** — clouded at its bbox in the current model;
- **changed** — clouded over the union of old + new bboxes, so a moved
  wall's cloud covers both positions;
- **removed** — clouded at its OLD bbox (that is where the prior issue
  showed it).

Overlapping or nearby boxes (within ``merge_gap_mm``, default 500 mm) on the
same level merge into one cloud, mirroring drafting practice of one cloud
per revised area rather than per element.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from llmbim_core.clash import element_aabb
from llmbim_core.errors import NotFoundError
from llmbim_core.model import Element, ProjectModel
from llmbim_core.versioning import diff_models

#: default merge distance — boxes closer than this (mm, per axis) join one cloud
MERGE_GAP_MM = 500.0

_BBox = tuple[float, float, float, float]


@dataclass
class _Box:
    x0: float
    y0: float
    x1: float
    y1: float
    ids: list[str] = field(default_factory=list)

    def near(self, other: _Box, gap: float) -> bool:
        return (
            self.x0 - gap <= other.x1
            and other.x0 - gap <= self.x1
            and self.y0 - gap <= other.y1
            and other.y0 - gap <= self.y1
        )

    def absorb(self, other: _Box) -> None:
        self.x0 = min(self.x0, other.x0)
        self.y0 = min(self.y0, other.y0)
        self.x1 = max(self.x1, other.x1)
        self.y1 = max(self.y1, other.y1)
        self.ids = sorted(set(self.ids) | set(other.ids))


def _plan_bbox(el: Element, model: ProjectModel) -> _BBox | None:
    """Plan-space bbox (mm) of an element; ``None`` when it has no footprint."""
    box = element_aabb(el, model)
    if box is not None:
        return (box.xmin, box.ymin, box.xmax, box.ymax)
    # rooms / slab-like elements carry an explicit plan polygon
    poly = el.params.get("polygon_mm") or []
    try:
        xs = [float(p[0]) for p in poly]
        ys = [float(p[1]) for p in poly]
    except (TypeError, ValueError, IndexError):
        return None
    if len(xs) < 2:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _union(a: _BBox | None, b: _BBox | None) -> _BBox | None:
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _level_name(el: Element, model: ProjectModel) -> str:
    """Level name for an element (hosted openings resolve via their host)."""
    lid = el.level_id
    if not lid and el.host_id:
        try:
            lid = model.get_element(el.host_id).level_id
        except NotFoundError:
            lid = None
    for lv in model.levels:
        if lv.id == lid:
            return lv.name
    return ""


def _merge_boxes(boxes: list[_Box], gap: float) -> list[_Box]:
    """Union-merge boxes closer than ``gap`` until stable; deterministic order."""
    merged = sorted(boxes, key=lambda b: (b.x0, b.y0, b.x1, b.y1))
    changed = True
    while changed:
        changed = False
        out: list[_Box] = []
        for b in merged:
            hit = next((o for o in out if o.near(b, gap)), None)
            if hit is None:
                out.append(b)
            else:
                hit.absorb(b)
                changed = True
        merged = out
    return sorted(merged, key=lambda b: (b.x0, b.y0, b.x1, b.y1))


def revision_cloud_rects(
    model: ProjectModel,
    prior_model: ProjectModel,
    *,
    level: str | None = None,
    merge_gap_mm: float = MERGE_GAP_MM,
) -> dict[str, list[dict[str, Any]]]:
    """Revision-cloud rectangles (plan mm) for changes since ``prior_model``.

    Returns ``{level_name: [{"x0","y0","x1","y1","element_ids": [...]}, …]}``.
    ``level`` filters to one level by name; elements whose level cannot be
    resolved group under ``""``. Elements with no computable plan footprint
    (e.g. notes) are skipped. Identical models → ``{}``.
    """
    diff = diff_models(prior_model.to_dict(), model.to_dict())
    entries: list[tuple[str, _BBox, str]] = []

    for row in diff["added"]:
        el = model.get_element(str(row["id"]))
        bb = _plan_bbox(el, model)
        if bb is not None:
            entries.append((_level_name(el, model), bb, el.id))

    for row in diff["removed"]:
        el = prior_model.get_element(str(row["id"]))
        bb = _plan_bbox(el, prior_model)
        if bb is not None:
            entries.append((_level_name(el, prior_model), bb, el.id))

    for row in diff["changed"]:
        el = model.get_element(str(row["id"]))
        old = prior_model.get_element(str(row["id"]))
        bb = _union(_plan_bbox(el, model), _plan_bbox(old, prior_model))
        if bb is not None:
            entries.append((_level_name(el, model), bb, el.id))

    by_level: dict[str, list[_Box]] = {}
    for lname, (x0, y0, x1, y1), eid in entries:
        if level is not None and lname != level:
            continue
        by_level.setdefault(lname, []).append(_Box(x0, y0, x1, y1, [eid]))

    return {
        lname: [
            {"x0": b.x0, "y0": b.y0, "x1": b.x1, "y1": b.y1, "element_ids": list(b.ids)}
            for b in _merge_boxes(boxes, merge_gap_mm)
        ]
        for lname, boxes in sorted(by_level.items())
    }


def revision_rows(
    model: ProjectModel,
    prior_model: ProjectModel,
    *,
    delta: str | int,
    date: str,
    description: str | None = None,
) -> list[dict[str, Any]]:
    """Revision-table row data for the change set since ``prior_model``.

    One row per issue: Δ number, date, description (auto —
    ``"3 ELEMENTS REVISED"`` — unless given) plus added/changed/removed
    counts. No model changes → ``[]`` (nothing to schedule). Feed into the
    title-block table as ``(row["delta"], row["description"], row["date"])``.
    """
    summary = diff_models(prior_model.to_dict(), model.to_dict())["summary"]
    added = int(summary["added"])
    changed = int(summary["changed"])
    removed = int(summary["removed"])
    total = added + changed + removed
    if total == 0:
        return []
    if description is None:
        description = f"{total} ELEMENT{'' if total == 1 else 'S'} REVISED"
    return [
        {
            "delta": str(delta),
            "date": str(date),
            "description": description,
            "added": added,
            "changed": changed,
            "removed": removed,
        }
    ]
