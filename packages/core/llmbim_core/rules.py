"""Design & constructability rules for designers and builders."""

from __future__ import annotations

from typing import Any

from llmbim_core.model import ProjectModel
from llmbim_core.quantities import wall_area_m2
from llmbim_core.validate import validate_model


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
                # Intentionally tall walls — multi-plate / balloon-framed
                # (stacked top plates, garage high bays) — declare it on the
                # element: params.multi_plate / params.balloon_framed, or an
                # explicit params.plate_height_mm covering the wall height.
                declared = float(el.params.get("plate_height_mm") or 0)
                intentional = bool(
                    el.params.get("multi_plate") or el.params.get("balloon_framed")
                ) or (declared > 0 and ht <= declared + 50)
                if intentional:
                    findings.append(
                        {
                            "rule": "WALL_MULTI_PLATE",
                            "severity": "info",
                            "message": (
                                f"Wall height {ht} > story clear {clear} mm — declared "
                                f"multi-plate/balloon framing "
                                f"(plate_height_mm={declared or ht:.0f})"
                            ),
                            "element_id": el.id,
                            "domain": "constructability",
                        }
                    )
                    continue
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

    # --- MEP coordination rules ---
    findings.extend(_mep_design_rules(model))

    return findings


def _mep_design_rules(model: ProjectModel) -> list[dict[str, Any]]:
    """Pipes, fittings, fixtures, module ports — constructability heuristics."""
    from llmbim_core.clash import element_aabb

    findings: list[dict[str, Any]] = []
    walls = [(el, element_aabb(el, model)) for el in model.query(category="wall")]
    pipes = [
        el
        for el in model.elements
        if el.category in {"pipe", "plumbing_pipe"} or el.params.get("fitting_type") == "pipe"
    ]
    fittings = [
        el
        for el in model.elements
        if el.category in {"fitting", "fittings"}
        or (
            el.params.get("fitting_type")
            and el.params.get("fitting_type") != "pipe"
            and el.category not in {"pipe", "plumbing_pipe"}
        )
    ]

    for el in pipes:
        mid = str(el.params.get("material_id") or "")
        sys = str(el.params.get("system") or "").upper()
        nps = el.params.get("nps")
        if not nps:
            findings.append(
                {
                    "rule": "PIPE_MISSING_NPS",
                    "severity": "warning",
                    "message": f"Pipe {el.name or el.id} has no NPS size",
                    "element_id": el.id,
                    "domain": "mep",
                }
            )
        if not mid:
            findings.append(
                {
                    "rule": "PIPE_MISSING_MATERIAL",
                    "severity": "warning",
                    "message": f"Pipe {el.name or el.id} has no material_id",
                    "element_id": el.id,
                    "domain": "mep",
                }
            )
        # fire system should be black steel (not copper)
        if sys in ("FP", "FIRE") or "fire" in (el.name or "").lower():
            if "copper" in mid.lower() or mid in ("copper_C12200", "copper_fitting"):
                findings.append(
                    {
                        "rule": "FIRE_PIPE_MATERIAL",
                        "severity": "error",
                        "message": f"Fire pipe {el.name or el.id} uses copper — expect black steel (21 13 13)",
                        "element_id": el.id,
                        "domain": "mep",
                    }
                )
        # very low domestic pipe may conflict with floor finishes
        z0 = float(el.params.get("z0_mm") or 0)
        if z0 < 50 and mid and "copper" in mid.lower():
            findings.append(
                {
                    "rule": "PIPE_LOW_Z",
                    "severity": "info",
                    "message": f"Pipe {el.name or el.id} at z0={z0:.0f} mm — check floor slab embed vs hang",
                    "element_id": el.id,
                    "domain": "mep",
                }
            )
        # pipe centerline inside wall band (embedding / conflict)
        pb = element_aabb(el, model)
        if not pb:
            continue
        for wall, wb in walls:
            if not wb or el.level_id != wall.level_id:
                continue
            if pb.intersects(wb, tol=1.0):
                findings.append(
                    {
                        "rule": "PIPE_IN_WALL",
                        "severity": "warning",
                        "message": (
                            f"Pipe {el.name or el.id} intersects wall {wall.name or wall.id} "
                            f"(sleeve/core or route conflict)"
                        ),
                        "element_id": el.id,
                        "domain": "mep",
                    }
                )
                break

    # Duct / conduit / cable tray vs wall (sleeve / fire damper location)
    ducts = [
        el
        for el in model.elements
        if el.category in {"duct", "hvac"} or el.params.get("fitting_type") == "duct"
    ]
    conduits = [
        el
        for el in model.elements
        if el.category == "conduit" or el.params.get("fitting_type") == "conduit"
    ]
    trays = [
        el
        for el in model.elements
        if el.category == "cable_tray" or el.params.get("fitting_type") == "cable_tray"
    ]
    for el, rule, label in (
        *[(d, "DUCT_IN_WALL", "Duct") for d in ducts],
        *[(c, "CONDUIT_IN_WALL", "Conduit") for c in conduits],
        *[(t, "TRAY_IN_WALL", "Cable tray") for t in trays],
    ):
        pb = element_aabb(el, model)
        if not pb:
            continue
        # low hang under 2.1 m clear is a constructability note
        if rule == "DUCT_IN_WALL":
            z0 = float(el.params.get("z0_mm") or 0)
            h = float(el.params.get("height_mm") or 250)
            if z0 + h < 2100:
                findings.append(
                    {
                        "rule": "DUCT_LOW_CLEARANCE",
                        "severity": "info",
                        "message": (
                            f"Duct {el.name or el.id} bottom/top z0={z0:.0f} H={h:.0f} mm "
                            f"— check headroom / door swing"
                        ),
                        "element_id": el.id,
                        "domain": "mep",
                    }
                )
        if rule == "TRAY_IN_WALL":
            z0 = float(el.params.get("z0_mm") or 0)
            h = float(el.params.get("height_mm") or 100)
            if z0 < 2100:
                findings.append(
                    {
                        "rule": "TRAY_LOW_CLEARANCE",
                        "severity": "info",
                        "message": (
                            f"Cable tray {el.name or el.id} z0={z0:.0f} H={h:.0f} mm "
                            f"— check headroom / lighting zone"
                        ),
                        "element_id": el.id,
                        "domain": "mep",
                    }
                )
        for wall, wb in walls:
            if not wb or el.level_id != wall.level_id:
                continue
            if pb.intersects(wb, tol=1.0):
                findings.append(
                    {
                        "rule": rule,
                        "severity": "warning",
                        "message": (
                            f"{label} {el.name or el.id} intersects wall {wall.name or wall.id} "
                            f"(provide sleeve / damper / firestop)"
                        ),
                        "element_id": el.id,
                        "domain": "mep",
                    }
                )
                break

    for el in fittings:
        ftype = str(el.params.get("fitting_type") or "")
        if ftype and ftype != "sprinkler_head" and not el.params.get("nps"):
            findings.append(
                {
                    "rule": "FITTING_MISSING_NPS",
                    "severity": "warning",
                    "message": f"Fitting {el.name or el.id} ({ftype}) has no NPS",
                    "element_id": el.id,
                    "domain": "mep",
                }
            )
        # elbow near wall (clearance for wrench)
        fb = element_aabb(el, model)
        if not fb:
            continue
        for wall, wb in walls:
            if not wb or el.level_id != wall.level_id:
                continue
            gap = 75.0  # mm fitting-to-wall finish clearance heuristic
            near = not (
                fb.xmax < wb.xmin - gap
                or fb.xmin > wb.xmax + gap
                or fb.ymax < wb.ymin - gap
                or fb.ymin > wb.ymax + gap
            )
            if near and ftype in ("elbow_90", "elbow_45", "tee", "ball_valve", "gate_valve"):
                findings.append(
                    {
                        "rule": "FITTING_WALL_CLEARANCE",
                        "severity": "info",
                        "message": (
                            f"Fitting {el.name or el.id} within ~{gap:.0f} mm of wall "
                            f"{wall.name or wall.id} — check wrench clearance"
                        ),
                        "element_id": el.id,
                        "domain": "mep",
                    }
                )
                break

    # fixtures should have material or part assignment for takeoff
    for el in model.elements:
        if el.category not in {"fixture", "accessory"}:
            continue
        if not el.params.get("part_id") and not el.type_id:
            findings.append(
                {
                    "rule": "FIXTURE_NO_PART",
                    "severity": "info",
                    "message": f"Fixture {el.name or el.id} has no catalog part_id",
                    "element_id": el.id,
                    "domain": "mep",
                }
            )

    # broken connection graph
    for conn in model.meta.get("connections") or []:
        if not isinstance(conn, dict):
            continue
        for key in ("from_id", "to_id"):
            rid = conn.get(key)
            if not rid:
                continue
            try:
                model.get_element(str(rid))
            except Exception:  # noqa: BLE001
                findings.append(
                    {
                        "rule": "BROKEN_CONNECTION",
                        "severity": "error",
                        "message": f"Connection {conn.get('id') or conn.get('name')} missing {key}={rid}",
                        "element_id": None,
                        "domain": "mep",
                    }
                )

    # machines / module roots without ports
    for el in model.elements:
        if el.category not in {"module_root", "module_instance"} and el.params.get("kind") not in (
            "machine",
            "separator_skid",
            "skid",
        ):
            continue
        ports = el.params.get("ports") or []
        if el.params.get("kind") in ("machine", "separator_skid", "skid") and not ports:
            # check children for ports
            child_ports = any(
                c.params.get("ports") for c in model.elements if c.parent_id == el.id
            )
            if not child_ports and not ports:
                findings.append(
                    {
                        "rule": "MACHINE_NO_PORTS",
                        "severity": "info",
                        "message": f"Machine/module {el.name or el.id} has no connection ports defined",
                        "element_id": el.id,
                        "domain": "mep",
                    }
                )

    # Structural steel constructability
    columns = [
        el
        for el in model.elements
        if el.category == "column" or el.params.get("fitting_type") == "column"
    ]
    beams = [
        el
        for el in model.elements
        if el.category == "beam" or el.params.get("fitting_type") == "beam"
    ]
    for el in columns:
        if not el.params.get("section"):
            findings.append(
                {
                    "rule": "COLUMN_MISSING_SECTION",
                    "severity": "warning",
                    "message": f"Column {el.name or el.id} has no steel section mark",
                    "element_id": el.id,
                    "domain": "structure",
                }
            )
        cb = element_aabb(el, model)
        if not cb:
            continue
        for wall, wb in walls:
            if not wb or el.level_id != wall.level_id:
                continue
            if cb.intersects(wb, tol=1.0):
                findings.append(
                    {
                        "rule": "COLUMN_IN_WALL",
                        "severity": "warning",
                        "message": (
                            f"Column {el.name or el.id} intersects wall {wall.name or wall.id} "
                            f"(embed / chase conflict)"
                        ),
                        "element_id": el.id,
                        "domain": "structure",
                    }
                )
                break
    for el in beams:
        if not el.params.get("section"):
            findings.append(
                {
                    "rule": "BEAM_MISSING_SECTION",
                    "severity": "warning",
                    "message": f"Beam {el.name or el.id} has no steel section mark",
                    "element_id": el.id,
                    "domain": "structure",
                }
            )
        z0 = float(el.params.get("z0_mm") or 0)
        depth = float(el.params.get("height_mm") or el.params.get("depth_mm") or 300)
        # bottom of beam under 2.1 m clear is headroom note
        if z0 < 2100:
            findings.append(
                {
                    "rule": "BEAM_LOW_CLEARANCE",
                    "severity": "info",
                    "message": (
                        f"Beam {el.name or el.id} z0={z0:.0f} mm depth={depth:.0f} mm "
                        f"— check headroom / door swing"
                    ),
                    "element_id": el.id,
                    "domain": "structure",
                }
            )
        bb = element_aabb(el, model)
        if not bb:
            continue
        for wall, wb in walls:
            if not wb or el.level_id != wall.level_id:
                continue
            if bb.intersects(wb, tol=1.0):
                findings.append(
                    {
                        "rule": "BEAM_IN_WALL",
                        "severity": "warning",
                        "message": (
                            f"Beam {el.name or el.id} intersects wall {wall.name or wall.id} "
                            f"(bearing / opening conflict)"
                        ),
                        "element_id": el.id,
                        "domain": "structure",
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
