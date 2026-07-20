"""Outcome-quality signals in verify_pack.

The autonomy contract: agents choose their method, the pack surfaces the
outcome. These signals are informational (never flip ``ok``) but must be
present and accurate so any agent — or a project-level guard — can judge
whether a deliverable is actually done.
"""

from __future__ import annotations

from llmbim import Project
from llmbim_drawings.deliverables import verify_pack


def _build(tmp_path):
    p = Project.create("VerifyOutcomes", vcs=False)
    p.add_level("L1", 0)
    typed = p.create_wall(
        level="L1", start=(0, 0), end=(6000, 0), thickness_mm=171, height_mm=3000
    )
    p.set_type(typed, "W-EXT-2x6-BNB")
    p.create_wall(level="L1", start=(0, 0), end=(0, 4000), thickness_mm=114, height_mm=3000)
    p.op("set_param", id=typed, key="height_assumed", value=True)
    out = tmp_path / "pack"
    man = p.export_deliverables(out)
    assert man.get("ok"), man
    return out


def test_verify_surfaces_wall_typing_and_assumptions(tmp_path):
    out = _build(tmp_path)
    checks = verify_pack(out)
    assert checks["ok"] is True
    assert checks["walls_total"] == 2
    assert checks["walls_untyped"] == 1
    assert checks["assumption_flags"] == 1


def test_signals_are_informational_not_fatal(tmp_path):
    # An untyped wall must NOT fail the pack — project-level guards decide.
    out = _build(tmp_path)
    checks = verify_pack(out)
    assert checks["walls_untyped"] > 0
    assert checks["ok"] is True


def test_fully_typed_pack_reports_zero_untyped(tmp_path):
    p = Project.create("VerifyTyped", vcs=False)
    p.add_level("L1", 0)
    w = p.create_wall(level="L1", start=(0, 0), end=(5000, 0), thickness_mm=171, height_mm=3000)
    p.set_type(w, "W-EXT-2x6-BNB")
    out = tmp_path / "pack2"
    man = p.export_deliverables(out)
    assert man.get("ok"), man
    checks = verify_pack(out)
    assert checks["walls_total"] == 1
    assert checks["walls_untyped"] == 0
    assert checks["assumption_flags"] == 0
