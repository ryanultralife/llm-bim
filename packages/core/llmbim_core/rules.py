"""Design & constructability rules for designers and builders."""

from __future__ import annotations

from typing import Any

from llmbim_core.model import ProjectModel
from llmbim_core.quantities import wall_area_m2
from llmbim_core.validate import Issue, validate_model


def run_design_rules(model: ProjectModel) -> list[dict[str, Any]]:
    """Return rule findings (errors / warnings / info)."""
    findings: list[dict[str, Any]] = []

    # Baseline validation
    for issue in validate_model(model):
        findings.append(
            {
                "rule": issue.code,
                "severity": issue.severity,
                "message": issue.message,
                "element_id": issue.element_id,
                "domain": "integrity",
            }
        )

    # Corridor / room minimum areas
    for el in model.query(category="room"):
        area_m2 = float(el.params.get("area_mm2") or 0) / 1e6
        name = (el.name or "").lower()
        if "corridor" in name or "spine" in name or "hall" in name:
            if area_m2 < 5.0:
                findings.append(
                    {
                        "rule": "MIN_CORRIDOR_AREA",
                        "severity": "warning",
                        "message": f"Circulation space {el.name!r} is only {area_m2:.1f} m²",
                        "element_id": el.id,
                        "domain": "design",
                    }
                )
        if area_m2 > 0 and area_m2 < 1.0 and "stack" not in name:
            findings.append(
                {
                    "rule": "TINY_ROOM",
                    "severity": "warning",
                    "message": f"Room {el.name!r} under 1 m²",
                    "element_id": el.id,
                    "domain": "design",
                }
            )

    # Door clear width for egress (simple)
    for el in model.query(category="door"):
        w = float(el.params.get("width_mm") or 0)
        if w > 0 and w < 800:
            findings.append(
                {
                    "rule": "EGRESS_DOOR_WIDTH",
                    "severity": "warning",
                    "message": f"Door width {w:.0f} mm may be below egress minimum",
                    "element_id": el.id,
                    "domain": "life_safety",
                }
            )

    # Wall height vs level spacing
    levels = sorted(model.levels, key=lambda lv: lv.elevation_mm)
    for i, lv in enumerate(levels[:-1]):
        clear = levels[i + 1].elevation_mm - lv.elevation_mm
        for el in model.query(category="wall", level=lv.name):
            ht = float(el.params.get("height_mm") or 0)
            if ht > clear + 50:
                findings.append(
                    {
                        "rule": "WALL_EXCEEDS_STORY",
                        "severity": "error",
                        "message": f"Wall height {ht} > story clear {clear} mm",
                        "element_id": el.id,
                        "domain": "constructability",
                    }
                )

    # Equipment not on a level with walls (orphan equipment ok)
    # Large wall areas without openings (info)
    for el in model.query(category="wall"):
        area = wall_area_m2(el)
        openings = model.query(host_id=el.id)
        if area > 30 and not openings:
            findings.append(
                {
                    "rule": "BLANK_WALL_LARGE",
                    "severity": "info",
                    "message": f"Large wall ({area:.0f} m²) has no doors/windows",
                    "element_id": el.id,
                    "domain": "design",
                }
            )

    # Missing fire-rated type on shield walls by name
    for el in model.query(category="wall"):
        nm = (el.name or "").upper()
        if any(k in nm for k in ("SHIELD", "CELL", "TUNNEL", "HOT")):
            if not el.type_id or "SHIELD" not in (el.type_id or ""):
                findings.append(
                    {
                        "rule": "SHIELD_WALL_TYPE",
                        "severity": "warning",
                        "message": f"Wall {el.name!r} looks shielded but type_id is not W-SHIELD-*",
                        "element_id": el.id,
                        "domain": "nuclear_facility",
                    }
                )

    return findings


def rules_summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    s = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        sev = f.get("severity", "info")
        if sev in s:
            s[sev] += 1
    s["total"] = len(findings)
    return s
