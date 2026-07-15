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

    # Accessibility: door clear width 815 mm preferred (ADA-ish)
    for el in model.query(category="door"):
        w = float(el.params.get("width_mm") or 0)
        if 800 <= w < 815:
            findings.append(
                {
                    "rule": "ADA_DOOR_CLEAR",
                    "severity": "info",
                    "message": f"Door {w:.0f} mm is tight for accessible clear width (~815+)",
                    "element_id": el.id,
                    "domain": "accessibility",
                }
            )

    # Equipment clearance: equipment within 300 mm of wall gets warning
    from llmbim_core.clash import element_aabb

    walls = [(el, element_aabb(el, model)) for el in model.query(category="wall")]
    for eq in model.query(category="equipment"):
        eb = element_aabb(eq, model)
        if not eb:
            continue
        for wall, wb in walls:
            if not wb:
                continue
            # expand wall AABB by 300 mm clearance
            gap = 300.0
            near = not (
                eb.xmax < wb.xmin - gap
                or eb.xmin > wb.xmax + gap
                or eb.ymax < wb.ymin - gap
                or eb.ymin > wb.ymax + gap
            )
            # but not intersecting heavily (that's clash)
            if near and not eb.intersects(wb, tol=50):
                findings.append(
                    {
                        "rule": "EQUIP_CLEARANCE_300",
                        "severity": "info",
                        "message": f"Equipment {eq.name or eq.id} within 300 mm of wall {wall.name or wall.id}",
                        "element_id": eq.id,
                        "domain": "constructability",
                    }
                )
                break

    # Dual egress: rooms > 50 m² should have >= 2 doors on level (heuristic)
    for room in model.query(category="room"):
        area = float(room.params.get("area_mm2") or 0) / 1e6
        if area < 50:
            continue
        doors = [d for d in model.query(category="door") if d.level_id == room.level_id]
        if len(doors) < 2:
            findings.append(
                {
                    "rule": "DUAL_EGRESS_HEURISTIC",
                    "severity": "warning",
                    "message": f"Large room {room.name!r} ({area:.0f} m²) has < 2 doors on level",
                    "element_id": room.id,
                    "domain": "life_safety",
                }
            )

    # Locked STEP refs must exist on disk
    for el in model.query(category="equipment"):
        if el.params.get("locked") and el.params.get("step_ref_path"):
            from pathlib import Path

            if not Path(str(el.params["step_ref_path"])).is_file():
                findings.append(
                    {
                        "rule": "MISSING_STEP_REF",
                        "severity": "error",
                        "message": f"Locked equipment missing STEP file: {el.params['step_ref_path']}",
                        "element_id": el.id,
                        "domain": "integrity",
                    }
                )

    # Level count
    if len(model.levels) == 1 and any(el.category == "wall" for el in model.elements):
        for el in model.query(category="wall"):
            if float(el.params.get("height_mm") or 0) > 6000:
                findings.append(
                    {
                        "rule": "TALL_WALL_SINGLE_LEVEL",
                        "severity": "info",
                        "message": "Tall walls with single level — consider intermediate levels",
                        "element_id": el.id,
                        "domain": "design",
                    }
                )
                break

    return findings


def rules_summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    s = {"error": 0, "warning": 0, "info": 0}
    for f in findings:
        sev = f.get("severity", "info")
        if sev in s:
            s[sev] += 1
    s["total"] = len(findings)
    return s
