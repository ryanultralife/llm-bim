"""MEP connection graph — auto-place runs between fittings/equipment/ports.

Honesty: straight plan runs (optional orthogonal dogleg). Not hydraulic sizing
or full 3D routing/clash-free pathfinding.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from llmbim_core.errors import ValidationError
from llmbim_core.ids import new_id
from llmbim_core.model import ProjectModel

RouteKind = Literal["pipe", "duct", "conduit"]


def _xy_of(model: ProjectModel, element_id: str, port: str | None = None) -> tuple[float, float, float, str]:
    """Return plan XY, z0_mm, level name for an element (or named port)."""
    el = model.get_element(element_id)
    z0 = float(el.params.get("z0_mm") or 0)
    level = "L1"
    if el.level_id:
        for lv in model.levels:
            if lv.id == el.level_id:
                level = lv.name
                break
    # port position on element
    if port:
        for p in el.params.get("ports") or []:
            if str(p.get("name") or "").upper() == str(port).upper():
                pos = p.get("position_mm") or p.get("origin_mm")
                if pos and len(pos) >= 2:
                    return float(pos[0]), float(pos[1]), float(p.get("z0_mm") or z0), level
    if el.params.get("origin_mm"):
        o = el.params["origin_mm"]
        return float(o[0]), float(o[1]), z0, level
    if el.params.get("start_mm") and el.params.get("end_mm"):
        s, e = el.params["start_mm"], el.params["end_mm"]
        return (
            (float(s[0]) + float(e[0])) / 2,
            (float(s[1]) + float(e[1])) / 2,
            z0,
            level,
        )
    if el.params.get("position_mm"):
        p = el.params["position_mm"]
        return float(p[0]), float(p[1]), z0, level
    raise ValidationError("Cannot resolve plan XY for element", element_id=element_id)


def mep_route(
    model: ProjectModel,
    from_id: str,
    to_id: str,
    *,
    kind: RouteKind = "pipe",
    nps: str = "2",
    material: str = "copper",
    system: str = "CW",
    from_port: str | None = None,
    to_port: str | None = None,
    orthogonal: bool = True,
    z0_mm: float | None = None,
    width_mm: float = 400.0,
    height_mm: float = 250.0,
    trade_size: str = "3/4",
    name: str = "",
) -> dict[str, Any]:
    """Connect two elements with one or two straight MEP segments + graph edge.

    If orthogonal and not axis-aligned, places a dogleg (two segments via elbow).
    """
    from llmbim_core.assignment import place_conduit, place_duct, place_fitting, place_pipe

    x0, y0, z_a, level = _xy_of(model, from_id, from_port)
    x1, y1, z_b, level_b = _xy_of(model, to_id, to_port)
    if level_b != level:
        # still route on from-level (honesty: multi-storey riser separate)
        pass
    z = float(z0_mm) if z0_mm is not None else max(z_a, z_b, 0.0)
    if abs(x1 - x0) < 1 and abs(y1 - y0) < 1:
        raise ValidationError("MEP endpoints coincide — nothing to route", from_id=from_id, to_id=to_id)

    segments: list[dict[str, Any]] = []
    fitting_ids: list[str] = []

    def _place_run(sx: float, sy: float, ex: float, ey: float) -> dict[str, Any]:
        if kind == "duct":
            return place_duct(
                model,
                level=level,
                start=(sx, sy),
                end=(ex, ey),
                width_mm=width_mm,
                height_mm=height_mm,
                system_tag=system,
                z0_mm=z,
                name=name or None,
            )
        if kind == "conduit":
            return place_conduit(
                model,
                level=level,
                start=(sx, sy),
                end=(ex, ey),
                trade_size=trade_size,
                system_tag=system,
                z0_mm=z,
                name=name or None,
            )
        return place_pipe(
            model,
            level=level,
            nps=nps,
            start=(sx, sy),
            end=(ex, ey),
            material=material,
            system_tag=system,
            z0_mm=z,
            name=name or None,
        )

    axis_aligned = abs(x1 - x0) < 1 or abs(y1 - y0) < 1
    if orthogonal and not axis_aligned:
        # dogleg via corner (x1, y0)
        mx, my = x1, y0
        r1 = _place_run(x0, y0, mx, my)
        r2 = _place_run(mx, my, x1, y1)
        segments.append(r1)
        segments.append(r2)
        # elbow at corner if pipe
        if kind == "pipe":
            try:
                fr = place_fitting(
                    model,
                    level=level,
                    fitting_type="elbow_90",
                    nps=nps,
                    origin=(mx, my),
                    material=material,
                    system_tag=system,
                )
                fitting_ids.append(str(fr["element_id"]))
            except Exception:  # noqa: BLE001
                pass
    else:
        segments.append(_place_run(x0, y0, x1, y1))

    length_m = math.hypot(x1 - x0, y1 - y0) / 1000.0
    if orthogonal and not axis_aligned:
        length_m = (abs(x1 - x0) + abs(y1 - y0)) / 1000.0

    cid = new_id("mepc")
    edge = {
        "id": cid,
        "kind": "mep_route",
        "route_kind": kind,
        "from_id": from_id,
        "to_id": to_id,
        "from_port": from_port,
        "to_port": to_port,
        "medium": system,
        "nps": nps if kind == "pipe" else trade_size if kind == "conduit" else f"{width_mm}x{height_mm}",
        "material": material if kind == "pipe" else None,
        "length_m": round(length_m, 3),
        "segment_ids": [str(s.get("element_id")) for s in segments],
        "fitting_ids": fitting_ids,
        "orthogonal": bool(orthogonal and not axis_aligned),
        "z0_mm": z,
        "level": level,
        "name": name or f"{kind}:{from_id[:8]}→{to_id[:8]}",
    }
    model.meta.setdefault("mep_graph", [])
    model.meta["mep_graph"].append(edge)
    # also mirror into connections for existing schedules
    model.meta.setdefault("connections", [])
    model.meta["connections"].append(
        {
            "id": cid,
            "name": edge["name"],
            "from_id": from_id,
            "from_port": from_port or "OUT",
            "to_id": to_id,
            "to_port": to_port or "IN",
            "medium": system,
            "kind": "mep_route",
            "segment_ids": edge["segment_ids"],
        }
    )
    return {
        "connection_id": cid,
        "kind": kind,
        "length_m": edge["length_m"],
        "segment_ids": edge["segment_ids"],
        "fitting_ids": fitting_ids,
        "from": {"id": from_id, "xy": [x0, y0]},
        "to": {"id": to_id, "xy": [x1, y1]},
        "edge": edge,
    }


def mep_graph(model: ProjectModel) -> list[dict[str, Any]]:
    return list(model.meta.get("mep_graph") or [])
