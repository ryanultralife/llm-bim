"""Model validation — agent-callable QA."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from llmbim_core.model import ProjectModel

Severity = Literal["error", "warning", "info"]


@dataclass
class Issue:
    code: str
    severity: Severity
    message: str
    element_id: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if d["details"] is None:
            del d["details"]
        return d


def validate_model(model: ProjectModel) -> list[Issue]:
    """Return structural issues agents can fix."""
    issues: list[Issue] = []
    level_ids = {lv.id for lv in model.levels}
    level_names = {lv.name for lv in model.levels}
    element_ids = {el.id for el in model.elements}

    if not model.levels:
        issues.append(
            Issue("NO_LEVELS", "error", "Project has no levels; add at least one level")
        )

    # Duplicate level names
    seen_names: set[str] = set()
    for lv in model.levels:
        if lv.name in seen_names:
            issues.append(
                Issue(
                    "DUPLICATE_LEVEL_NAME",
                    "error",
                    f"Duplicate level name {lv.name!r}",
                    details={"level_id": lv.id},
                )
            )
        seen_names.add(lv.name)

    for el in model.elements:
        if el.level_id and el.level_id not in level_ids:
            issues.append(
                Issue(
                    "ORPHAN_LEVEL",
                    "error",
                    "Element references missing level_id",
                    element_id=el.id,
                    details={"level_id": el.level_id},
                )
            )
        if el.host_id:
            if el.host_id not in element_ids:
                issues.append(
                    Issue(
                        "HOST_MISSING",
                        "error",
                        "Hosted element references missing host",
                        element_id=el.id,
                        details={"host_id": el.host_id},
                    )
                )
            else:
                host = next(h for h in model.elements if h.id == el.host_id)
                if el.category in {"door", "window"} and host.category != "wall":
                    issues.append(
                        Issue(
                            "HOST_NOT_WALL",
                            "error",
                            f"{el.category} host is not a wall",
                            element_id=el.id,
                            details={"host_category": host.category},
                        )
                    )
                if el.category in {"door", "window"}:
                    wall_len = float(host.params.get("length_mm") or 0)
                    off = float(el.params.get("offset_mm") or 0)
                    width = float(el.params.get("width_mm") or 0)
                    if wall_len and off + width > wall_len + 1e-3:
                        issues.append(
                            Issue(
                                "OPENING_OVERFLOW",
                                "error",
                                "Opening extends past host wall length",
                                element_id=el.id,
                                details={
                                    "offset_mm": off,
                                    "width_mm": width,
                                    "wall_length_mm": wall_len,
                                },
                            )
                        )

        if el.category == "wall":
            length = float(el.params.get("length_mm") or 0)
            if length < 1:
                issues.append(
                    Issue(
                        "DEGENERATE_WALL",
                        "error",
                        "Wall length is near zero",
                        element_id=el.id,
                    )
                )
            th = float(el.params.get("thickness_mm") or 0)
            if th <= 0:
                issues.append(
                    Issue(
                        "INVALID_THICKNESS",
                        "error",
                        "Wall thickness must be positive",
                        element_id=el.id,
                    )
                )

        if el.category == "slab":
            poly = el.params.get("polygon_mm") or []
            if len(poly) < 3:
                issues.append(
                    Issue(
                        "DEGENERATE_SLAB",
                        "error",
                        "Slab polygon has fewer than 3 points",
                        element_id=el.id,
                    )
                )

        if el.category == "room":
            boundary = el.params.get("boundary_mm") or []
            if len(boundary) < 3:
                issues.append(
                    Issue(
                        "DEGENERATE_ROOM",
                        "warning",
                        "Room boundary has fewer than 3 points",
                        element_id=el.id,
                    )
                )
            if not el.name:
                issues.append(
                    Issue(
                        "UNNAMED_ROOM",
                        "info",
                        "Room has empty name",
                        element_id=el.id,
                    )
                )

    walls = [el for el in model.elements if el.category == "wall"]
    if model.levels and not walls:
        issues.append(
            Issue("NO_WALLS", "warning", "Project has levels but no walls")
        )

    # Unused — keep names referenced for future name-based checks
    _ = level_names
    return issues
