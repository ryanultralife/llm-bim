"""MEP connection graph — auto-place runs between fittings/equipment/ports.

Honesty: straight plan runs (optional orthogonal dogleg), plus grid-based
orthogonal obstacle avoidance (``mep_autoroute``). Not hydraulic sizing.
"""

from __future__ import annotations

import heapq
import math
from typing import Any, Literal

from llmbim_core.errors import ValidationError
from llmbim_core.ids import new_id
from llmbim_core.model import Element, ProjectModel

RouteKind = Literal["pipe", "duct", "conduit"]

Point = tuple[float, float]
Rect = tuple[float, float, float, float]  # xmin, ymin, xmax, ymax (plan mm)

_ROUTE_KINDS = ("pipe", "duct", "conduit")
_TURN_WEIGHT = 5.0  # A* cost per bend (in cell units) — prefers fewer elbows
_MAX_GRID_NODES = 200_000
_KIND_Z_DEFAULT = {"pipe": 0.0, "duct": 2700.0, "conduit": 2800.0}


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


# --- obstacle-avoiding orthogonal autoroute ------------------------------------


def _resolve_endpoint(
    model: ProjectModel,
    endpoint: str | tuple[float, float] | list[float],
    param: str,
) -> tuple[float, float, float | None, str | None]:
    """(x, y, z0_mm or None, element_id or None) for an (x, y) point or element id."""
    if isinstance(endpoint, str):
        x, y, z, _level = _xy_of(model, endpoint)
        return x, y, z, endpoint
    if isinstance(endpoint, (tuple, list)) and len(endpoint) >= 2:
        try:
            return float(endpoint[0]), float(endpoint[1]), None, None
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "MEP endpoint coordinates must be numeric", param=param, value=list(endpoint)
            ) from exc
    raise ValidationError("MEP endpoint must be (x, y) mm or an element id", param=param)


def _plan_obstacles(
    model: ProjectModel,
    level_id: str | None,
    inflate_mm: float,
    exclude: set[str],
) -> list[Rect]:
    """Plan-view blocked rectangles: wall footprints + equipment/column boxes."""
    from llmbim_core.clash import element_aabb

    rects: list[Rect] = []
    for el in model.elements:
        if el.id in exclude or el.level_id != level_id:
            continue
        if el.category not in ("wall", "equipment", "column"):
            continue
        box = element_aabb(el, model)
        if box is None:
            continue
        rects.append(
            (
                box.xmin - inflate_mm,
                box.ymin - inflate_mm,
                box.xmax + inflate_mm,
                box.ymax + inflate_mm,
            )
        )
    return rects


def _seg_hits(a: Point, b: Point, rects: list[Rect]) -> bool:
    """Axis-aligned segment (as thin AABB) vs blocked rectangles."""
    x0, x1 = min(a[0], b[0]), max(a[0], b[0])
    y0, y1 = min(a[1], b[1]), max(a[1], b[1])
    for rx0, ry0, rx1, ry1 in rects:
        if x1 < rx0 or x0 > rx1 or y1 < ry0 or y0 > ry1:
            continue
        return True
    return False


def _path_hits(pts: list[Point], rects: list[Rect]) -> bool:
    return any(_seg_hits(pts[i], pts[i + 1], rects) for i in range(len(pts) - 1))


def _simplify_ortho(pts: list[Point]) -> list[Point]:
    """Drop duplicate points and merge collinear axis-aligned segments."""
    out: list[Point] = []
    for pt in pts:
        if out and abs(pt[0] - out[-1][0]) < 0.5 and abs(pt[1] - out[-1][1]) < 0.5:
            continue
        out.append(pt)
    i = 1
    while i < len(out) - 1:
        ax, ay = out[i - 1]
        bx, by = out[i]
        cx, cy = out[i + 1]
        collinear_x = abs(ax - bx) < 0.5 and abs(bx - cx) < 0.5
        collinear_y = abs(ay - by) < 0.5 and abs(by - cy) < 0.5
        if collinear_x or collinear_y:
            out.pop(i)
        else:
            i += 1
    return out


def _grid_route(start: Point, end: Point, rects: list[Rect], cell_mm: float) -> list[Point] | None:
    """Manhattan A* on a uniform grid anchored at ``start``; minimal-bend polyline or None."""
    sx, sy = start
    ex, ey = end
    xs = [sx, ex] + [r[0] for r in rects] + [r[2] for r in rects]
    ys = [sy, ey] + [r[1] for r in rects] + [r[3] for r in rects]
    cell = float(cell_mm)
    margin = 4.0 * cell
    xmin, xmax = min(xs) - margin, max(xs) + margin
    ymin, ymax = min(ys) - margin, max(ys) + margin
    while ((xmax - xmin) / cell + 2) * ((ymax - ymin) / cell + 2) > _MAX_GRID_NODES:
        cell *= 1.5
    imin = math.floor((xmin - sx) / cell)
    imax = math.ceil((xmax - sx) / cell)
    jmin = math.floor((ymin - sy) / cell)
    jmax = math.ceil((ymax - sy) / cell)
    ni, nj = imax - imin + 1, jmax - jmin + 1

    blocked: set[tuple[int, int]] = set()
    for rx0, ry0, rx1, ry1 in rects:
        i0 = max(0, math.ceil((rx0 - sx) / cell) - imin)
        i1 = min(ni - 1, math.floor((rx1 - sx) / cell) - imin)
        j0 = max(0, math.ceil((ry0 - sy) / cell) - jmin)
        j1 = min(nj - 1, math.floor((ry1 - sy) / cell) - jmin)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                blocked.add((i, j))

    si, sj = -imin, -jmin
    ei = min(max(round((ex - sx) / cell) - imin, 0), ni - 1)
    ej = min(max(round((ey - sy) / cell) - jmin, 0), nj - 1)
    if (si, sj) == (ei, ej):
        return None  # endpoints closer than one cell — grid cannot resolve
    blocked.discard((si, sj))
    blocked.discard((ei, ej))

    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    start_state = (si, sj, -1)
    gbest: dict[tuple[int, int, int], float] = {start_state: 0.0}
    parent: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    h0 = float(abs(ei - si) + abs(ej - sj))
    heap: list[tuple[float, int, float, tuple[int, int, int]]] = [(h0, 0, 0.0, start_state)]
    tick = 1
    goal: tuple[int, int, int] | None = None
    while heap:
        _f, _t, g, state = heapq.heappop(heap)
        if g > gbest.get(state, math.inf) + 1e-9:
            continue  # stale queue entry
        i, j, d = state
        if (i, j) == (ei, ej):
            goal = state
            break
        for nd, (dx, dy) in enumerate(dirs):
            i2, j2 = i + dx, j + dy
            if i2 < 0 or j2 < 0 or i2 >= ni or j2 >= nj or (i2, j2) in blocked:
                continue
            ng = g + 1.0 + (_TURN_WEIGHT if d not in (-1, nd) else 0.0)
            nstate = (i2, j2, nd)
            if ng < gbest.get(nstate, math.inf) - 1e-9:
                gbest[nstate] = ng
                parent[nstate] = state
                nh = float(abs(ei - i2) + abs(ej - j2))
                heapq.heappush(heap, (ng + nh, tick, ng, nstate))
                tick += 1
    if goal is None:
        return None

    cells: list[tuple[int, int]] = []
    state = goal
    while True:
        cells.append((state[0], state[1]))
        if state == start_state:
            break
        state = parent[state]
    cells.reverse()
    pts = [(sx + (imin + i) * cell, sy + (jmin + j) * cell) for i, j in cells]
    return _simplify_ortho(pts)


def _fit_end(pts: list[Point], end: Point) -> list[Point]:
    """Shift the tail of an axis-aligned polyline so it terminates exactly at ``end``.

    The grid is anchored at the start point, so only the end needs adjustment
    (snap error ≤ half a cell — obstacle inflation covers the shift).
    """
    ex, ey = end
    out = list(pts)
    if len(out) < 2:
        return out + [(ex, ey)]
    ax, ay = out[-2]
    _bx, by = out[-1]
    horizontal = abs(ay - by) < 0.5
    if len(out) == 2:
        # straight snapped run — may need one short stub bend to reach exact end
        if horizontal:
            if abs(ay - ey) < 0.5:
                out[-1] = (ex, ey)
            else:
                out[-1] = (ex, ay)
                out.append((ex, ey))
        else:
            if abs(ax - ex) < 0.5:
                out[-1] = (ex, ey)
            else:
                out[-1] = (ax, ey)
                out.append((ex, ey))
        return _simplify_ortho(out)
    if horizontal:
        out[-2] = (ax, ey)
    else:
        out[-2] = (ex, ay)
    out[-1] = (ex, ey)
    return _simplify_ortho(out)


def mep_autoroute(
    model: ProjectModel,
    *,
    level: str,
    start: str | tuple[float, float] | list[float],
    end: str | tuple[float, float] | list[float],
    kind: str = "pipe",
    nps: str = "2",
    material: str = "copper",
    system: str = "CW",
    z0_mm: float | None = None,
    z1_mm: float | None = None,
    clearance_mm: float = 150.0,
    grid_mm: float = 250.0,
    width_mm: float = 400.0,
    height_mm: float = 250.0,
    trade_size: str = "3/4",
    name: str = "",
) -> dict[str, Any]:
    """Obstacle-avoiding orthogonal MEP route between two points or fitting ids.

    Manhattan A* on a coarse grid (default 250 mm cells) treating wall footprints
    and equipment/column boxes (inflated by ``clearance_mm``) as blocked. Pipes
    are placed segment-by-segment with an elbow_90 at every bend; graph edge is
    recorded like ``mep_route``. When no clear path exists, falls back to the
    plain dogleg (``fallback: "dogleg"`` in the result). Optional ``z1_mm``
    inserts a vertical riser at the end point with elbows top + bottom.
    """
    from llmbim_core.assignment import (
        assign_part,
        place_conduit,
        place_duct,
        place_fitting,
        place_pipe,
        place_riser,
    )

    if kind not in _ROUTE_KINDS:
        raise ValidationError("Unknown route kind", kind=kind, allowed=list(_ROUTE_KINDS))
    if clearance_mm < 0:
        raise ValidationError("clearance_mm must be >= 0", clearance_mm=clearance_mm)
    if grid_mm < 10:
        raise ValidationError("grid_mm too small (min 10 mm)", grid_mm=grid_mm)
    lvl = model.get_level(level)
    x0, y0, z_a, from_el = _resolve_endpoint(model, start, "start")
    x1, y1, z_b, to_el = _resolve_endpoint(model, end, "end")
    if abs(x1 - x0) < 1 and abs(y1 - y0) < 1:
        raise ValidationError("MEP endpoints coincide — nothing to route", start=[x0, y0], end=[x1, y1])

    element_z = [z for z in (z_a, z_b) if z is not None]
    if z0_mm is not None:
        z0 = float(z0_mm)
    elif element_z:
        z0 = max(element_z)
    else:
        z0 = _KIND_Z_DEFAULT[kind]
    z1 = float(z1_mm) if z1_mm is not None else None
    has_rise = z1 is not None and abs(z1 - z0) >= 1

    # obstacle inflation must cover the ≤ half-cell endpoint snap shift
    inflate = max(float(clearance_mm), float(grid_mm) / 2.0 + 1.0)
    exclude = {eid for eid in (from_el, to_el) if eid}
    rects = _plan_obstacles(model, lvl.id, inflate, exclude)

    s: Point = (x0, y0)
    e: Point = (x1, y1)
    axis_aligned = abs(x1 - x0) < 1 or abs(y1 - y0) < 1
    pts: list[Point] | None = None
    method = "grid"
    fallback: str | None = None
    if axis_aligned and not _seg_hits(s, e, rects):
        pts, method = [s, e], "straight"
    elif not axis_aligned:
        for corner in ((x1, y0), (x0, y1)):
            cand = [s, corner, e]
            if not _path_hits(cand, rects):
                pts, method = cand, "dogleg"
                break
    if pts is None:
        routed = _grid_route(s, e, rects, float(grid_mm))
        if routed is not None:
            pts = _fit_end(routed, e)
        if pts is None or len(pts) < 2:
            # no clear path — place the plain dogleg (no avoidance) and say so
            pts = [s, e] if axis_aligned else [s, (x1, y0), e]
            method, fallback = "dogleg", "dogleg"

    level_id = lvl.id
    segments: list[dict[str, Any]] = []
    fitting_ids: list[str] = []
    chain: list[str] = []

    def _place_run(a: Point, b: Point) -> dict[str, Any]:
        if kind == "duct":
            return place_duct(
                model,
                level=level,
                start=a,
                end=b,
                width_mm=width_mm,
                height_mm=height_mm,
                system_tag=system,
                z0_mm=z0,
                name=name or None,
            )
        if kind == "conduit":
            return place_conduit(
                model,
                level=level,
                start=a,
                end=b,
                trade_size=trade_size,
                system_tag=system,
                z0_mm=z0,
                name=name or None,
            )
        return place_pipe(
            model,
            level=level,
            nps=nps,
            start=a,
            end=b,
            material=material,
            system_tag=system,
            z0_mm=z0,
            name=name or None,
        )

    def _place_elbow(x: float, y: float, z: float) -> str:
        if kind == "pipe":
            try:
                fr = place_fitting(
                    model,
                    level=level,
                    fitting_type="elbow_90",
                    nps=nps,
                    origin=(x, y),
                    material=material,
                    system_tag=system,
                )
                fid = str(fr["element_id"])
                model.get_element(fid).params["z0_mm"] = z
                return fid
            except ValidationError:
                pass  # no catalog part for this nps/material — generic elbow below
        size = [width_mm, width_mm, height_mm] if kind == "duct" else [60.0, 60.0, 60.0]
        el = Element(
            id=new_id("fit"),
            category="fitting",
            name=f"{kind} elbow 90",
            level_id=level_id,
            type_id=None,
            params={
                "origin_mm": [x, y],
                "fitting_type": "elbow_90",
                "angle_deg": 90,
                "nps": nps if kind == "pipe" else trade_size if kind == "conduit" else None,
                "system": system,
                "route_kind": kind,
                "size_mm": size,
                "shape": "box",
                "z0_mm": z,
            },
        )
        model.add_element(el)
        return el.id

    def _place_vertical(x: float, y: float, za: float, zb: float) -> dict[str, Any]:
        if kind == "pipe":
            return place_riser(
                model,
                level=level,
                nps=nps,
                origin=(x, y),
                z0_mm=za,
                z1_mm=zb,
                material=material,
                system_tag=system,
                name=name or None,
            )
        lo, hi = min(za, zb), max(za, zb)
        length_mm = hi - lo
        length_m = length_mm / 1000.0
        if kind == "duct":
            pid = "PT-HVAC-DUCT-RECT"
            qty = round(2.0 * (width_mm + height_mm) * length_mm / 1_000_000.0, 3)
            size = [width_mm, height_mm, length_mm]
            shape = "box"
        else:
            pid = "PT-ELEC-CONDUIT"
            qty = length_m
            size = [30.0, 30.0, length_mm]
            shape = "cylinder"
        el = Element(
            id=new_id("ris"),
            category=kind,
            name=name or f"{kind} riser H={length_m:.2f}m",
            level_id=level_id,
            type_id=pid,
            params={
                "origin_mm": [x, y],
                "start_mm": [x, y],
                "end_mm": [x, y],
                "length_mm": length_mm,
                "length_m": length_m,
                "width_mm": width_mm if kind == "duct" else None,
                "height_mm": height_mm if kind == "duct" else None,
                "trade_size": trade_size if kind == "conduit" else None,
                "system": system,
                "part_id": pid,
                "part_qty": qty,
                "size_mm": size,
                "shape": shape,
                "vertical": True,
                "orientation": "vertical",
                "z0_mm": lo,
                "z1_mm": hi,
                "fitting_type": kind,
            },
        )
        model.add_element(el)
        try:
            assign_part(model, el.id, pid, qty=qty)
        except ValidationError:
            pass
        return {"element_id": el.id, "length_m": round(length_m, 3), "vertical": True}

    plan_length_mm = 0.0
    for idx in range(len(pts) - 1):
        a, b = pts[idx], pts[idx + 1]
        plan_length_mm += abs(b[0] - a[0]) + abs(b[1] - a[1])
        run = _place_run(a, b)
        segments.append(run)
        chain.append(str(run["element_id"]))
        if idx < len(pts) - 2:  # elbow at every interior bend
            bx, by = pts[idx + 1]
            fid = _place_elbow(bx, by, z0)
            fitting_ids.append(fid)
            chain.append(fid)

    riser_id: str | None = None
    riser_length_mm = 0.0
    if has_rise and z1 is not None:
        exx, eyy = pts[-1]
        bottom = _place_elbow(exx, eyy, z0)
        fitting_ids.append(bottom)
        chain.append(bottom)
        rr = _place_vertical(exx, eyy, z0, z1)
        riser_id = str(rr["element_id"])
        riser_length_mm = abs(z1 - z0)
        chain.append(riser_id)
        top = _place_elbow(exx, eyy, z1)
        fitting_ids.append(top)
        chain.append(top)

    length_m = (plan_length_mm + riser_length_mm) / 1000.0
    from_ref = from_el or f"xy:{x0:.0f},{y0:.0f}"
    to_ref = to_el or f"xy:{x1:.0f},{y1:.0f}"
    cid = new_id("mepc")
    edge = {
        "id": cid,
        "kind": "mep_autoroute",
        "route_kind": kind,
        "from_id": from_ref,
        "to_id": to_ref,
        "medium": system,
        "nps": nps if kind == "pipe" else trade_size if kind == "conduit" else f"{width_mm}x{height_mm}",
        "material": material if kind == "pipe" else None,
        "length_m": round(length_m, 3),
        "segment_ids": [str(seg["element_id"]) for seg in segments],
        "fitting_ids": fitting_ids,
        "chain": chain,
        "path_mm": [[round(px, 1), round(py, 1)] for px, py in pts],
        "method": method,
        "fallback": fallback,
        "bends": max(0, len(pts) - 2),
        "z0_mm": z0,
        "z1_mm": z1,
        "riser_id": riser_id,
        "level": lvl.name,
        "name": name or f"{kind}:{from_ref[:12]}→{to_ref[:12]}",
    }
    model.meta.setdefault("mep_graph", [])
    model.meta["mep_graph"].append(edge)
    model.meta.setdefault("connections", [])
    model.meta["connections"].append(
        {
            "id": cid,
            "name": edge["name"],
            "from_id": from_ref,
            "from_port": "OUT",
            "to_id": to_ref,
            "to_port": "IN",
            "medium": system,
            "kind": "mep_autoroute",
            "segment_ids": edge["segment_ids"],
        }
    )
    result: dict[str, Any] = {
        "connection_id": cid,
        "kind": kind,
        "method": method,
        "fallback": fallback,
        "length_m": edge["length_m"],
        "path_mm": edge["path_mm"],
        "bends": edge["bends"],
        "segment_ids": edge["segment_ids"],
        "fitting_ids": fitting_ids,
        "riser_id": riser_id,
        "z0_mm": z0,
        "z1_mm": z1,
        "from": {"id": from_el, "xy": [x0, y0]},
        "to": {"id": to_el, "xy": [x1, y1]},
        "edge": edge,
    }
    if fallback:
        result["note"] = "no clear path found — placed orthogonal dogleg without obstacle avoidance"
    return result
