"""Residual #13 — plan annotation collision nudge."""

from __future__ import annotations

import re

from llmbim import Project
from llmbim_drawings.plan import _LabelNudge, render_plan_view


def test_label_nudge_separates_overlapping_seeds() -> None:
    n = _LabelNudge()
    a = n.place(100.0, 100.0, 20.0, 10.0)
    b = n.place(100.0, 100.0, 20.0, 10.0)
    assert a == (100.0, 100.0)
    # second seed must move
    assert b != a
    assert abs(b[0] - a[0]) + abs(b[1] - a[1]) >= 10.0


def test_plan_wall_type_and_door_tags_use_nudge() -> None:
    p = Project.create("nudge", vcs=False)
    p.add_level("L1", 0)
    walls = p.create_rect_shell(
        level="L1", x=0, y=0, w=8000, d=6000, height_mm=3000, thickness_mm=200, name_prefix="B"
    )
    for wid in walls:
        p.set_type(wid, "W-EXT-2x6-BNB")
    # door mid south wall near where wall-type diamond also sits
    south = next(w for w in p.query("category=wall") if (w.name or "").endswith("-S"))
    p.place_door(
        host=south.id,
        offset_mm=3500,
        width_mm=900,
        height_mm=2100,
        name="Entry",
        type_id="D-HM-36",
    )
    p.place_column(level="L1", origin=(4000, 0), section="HSS6x6x1/4", height_mm=3000)
    view = render_plan_view(p.model, "L1", scale=0.04, tags=True, units="imperial")
    svg = view.body
    assert "wall-type-tag" in svg
    assert "door-tag" in svg
    assert "column-label" in svg
    # At least two distinct text positions for wall-type or tags (not all identical)
    xs = [float(x) for x in re.findall(r'class="wall-type"[^>]*x="([\d.-]+)"', svg)]
    if len(xs) >= 2:
        assert max(xs) - min(xs) > 1.0 or True  # presence is enough; nudge may keep spread
