"""Model repair — fix orphan refs, zero lengths, missing params."""

from __future__ import annotations

from typing import Any

from llmbim_geometry.primitives import distance

from llmbim_core.model import ProjectModel


def repair_model(model: ProjectModel) -> dict[str, Any]:
    actions: list[str] = []
    level_ids = {lv.id for lv in model.levels}
    element_ids = {el.id for el in model.elements}

    # Drop elements with missing levels (or reassign to first)
    keep = []
    for el in model.elements:
        if el.level_id and el.level_id not in level_ids:
            if model.levels:
                el.level_id = model.levels[0].id
                actions.append(f"reassigned {el.id} to level {model.levels[0].name}")
            else:
                actions.append(f"dropped {el.id} (no levels)")
                continue
        if el.host_id and el.host_id not in element_ids:
            el.host_id = None
            actions.append(f"cleared orphan host on {el.id}")
        # recompute wall length
        if el.category == "wall":
            try:
                s = el.params["start_mm"]
                e = el.params["end_mm"]
                length = distance((float(s[0]), float(s[1])), (float(e[0]), float(e[1])))
                if length < 1.0:
                    actions.append(f"removed degenerate wall {el.id}")
                    continue
                el.params["length_mm"] = length
            except (KeyError, TypeError, ValueError):
                actions.append(f"removed invalid wall {el.id}")
                continue
        el.params.setdefault("phase", "new")
        keep.append(el)
    model.elements = keep

    # Second pass: a host wall may have been dropped *during* the loop above
    # (degenerate/invalid), which the initial snapshot could not see — that
    # leaves hosted openings pointing at a now-removed element, so repair would
    # otherwise emit a model that fails validation's HOST_MISSING. Re-clear.
    kept_ids = {el.id for el in keep}
    for el in keep:
        if el.host_id and el.host_id not in kept_ids:
            el.host_id = None
            actions.append(f"cleared orphan host on {el.id} (host removed during repair)")

    # Sort levels
    model.levels.sort(key=lambda lv: lv.elevation_mm)
    actions.append(f"levels sorted ({len(model.levels)})")

    return {"actions": actions, "element_count": len(model.elements), "ok": True}
