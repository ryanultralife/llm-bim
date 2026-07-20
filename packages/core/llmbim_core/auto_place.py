"""Requirements-driven equipment auto-placement (derived coordinates).

Equipment coordinates are DERIVED from engineering requirements — room
assignment, footprints, and clearances — so layout proceeds in parallel with
the design instead of waiting for upstream coordinates. Placement is
deterministic (same inputs → same coordinates: no randomness, stable sort
orders) and every placed element is honestly tagged via ``placement_basis``
so reviewers know the coordinates are derived, not surveyed.

Strategies
----------
perimeter
    Walk the room boundary edges (longest edge first, then clockwise),
    placing each item back-to-wall with its front clearance kept free toward
    the room interior and ``aisle_mm`` between adjacent items along the wall.
    Door swing zones (door width + 300 mm swing margin each side, for doors
    hosted on walls within tolerance of the boundary) and existing equipment
    footprints are skipped.
grid
    Row/column packing in the room interior for free-standing gear, with
    ``aisle_mm`` circulation between rows.

Items that cannot fit are returned in ``unplaced`` with a reason — never
silently dropped, never overlapped.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from llmbim_core.commands import CreateEquipmentBox
from llmbim_core.errors import ValidationError
from llmbim_core.model import Element, ProjectModel

PLACEMENT_BASIS = "derived — requirements-driven auto-placement (verify at design review)"

DOOR_SWING_MARGIN_MM = 300.0
_EDGE_LATERAL_TOL_MM = 250.0  # added to host wall half-thickness for door-on-edge test
_MIN_STEP_MM = 50.0
_MAX_SCAN_ITER = 5000
_SHRINK_MM = 1.0
_TOUCH_TOL_MM = 0.5


@dataclass(frozen=True)
class _Rect:
    """Axis-aligned plan rectangle in mm."""

    x0: float
    y0: float
    x1: float
    y1: float

    def overlaps(self, other: _Rect) -> bool:
        """True when interiors overlap (touching edges do not count)."""
        return (
            min(self.x1, other.x1) - max(self.x0, other.x0) > _TOUCH_TOL_MM
            and min(self.y1, other.y1) - max(self.y0, other.y0) > _TOUCH_TOL_MM
        )


@dataclass(frozen=True)
class _Edge:
    """Directed room boundary edge with unit direction and interior normal."""

    ax: float
    ay: float
    ux: float
    uy: float
    nx: float
    ny: float
    length: float


@dataclass(frozen=True)
class _Item:
    name: str
    kind: str
    w_mm: float
    d_mm: float
    h_mm: float
    clearance_front_mm: float
    against_wall: bool


# --- geometry helpers ---------------------------------------------------------


def _point_in_polygon(x: float, y: float, pts: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y):
            x_cross = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _segment_enters_rect(
    ax: float, ay: float, bx: float, by: float, r: _Rect
) -> bool:
    """True when segment a→b passes through the interior of rect ``r`` (Liang-Barsky)."""
    dx, dy = bx - ax, by - ay
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, ax - r.x0), (dx, r.x1 - ax), (-dy, ay - r.y0), (dy, r.y1 - ay)):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    return False
                t0 = max(t0, t)
            else:
                if t < t0:
                    return False
                t1 = min(t1, t)
    return (t1 - t0) * math.hypot(dx, dy) > 1e-6


def _rect_in_polygon(r: _Rect, pts: list[tuple[float, float]]) -> bool:
    """Rect (shrunk by 1 mm so on-boundary backs count) fully inside polygon."""
    x0, y0 = r.x0 + _SHRINK_MM, r.y0 + _SHRINK_MM
    x1, y1 = r.x1 - _SHRINK_MM, r.y1 - _SHRINK_MM
    if x1 <= x0 or y1 <= y0:
        return _point_in_polygon((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, pts)
    for cx, cy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        if not _point_in_polygon(cx, cy, pts):
            return False
    inner = _Rect(x0, y0, x1, y1)
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if _segment_enters_rect(a[0], a[1], b[0], b[1], inner):
            return False  # concave notch cuts through the rect
    return True


def _clean_boundary(raw: Any) -> list[tuple[float, float]]:
    if not isinstance(raw, (list, tuple)) or len(raw) < 3:
        raise ValidationError("Room has no usable boundary_mm polygon (need ≥3 points)")
    pts: list[tuple[float, float]] = []
    for pt in raw:
        try:
            x, y = float(pt[0]), float(pt[1])
        except (TypeError, ValueError, IndexError) as e:
            raise ValidationError("Room boundary_mm points must be [x, y] mm", point=pt) from e
        if pts and abs(x - pts[-1][0]) < 1e-6 and abs(y - pts[-1][1]) < 1e-6:
            continue
        pts.append((x, y))
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    if len(pts) < 3:
        raise ValidationError("Room boundary_mm degenerates to fewer than 3 points")
    return pts


def _signed_area2(pts: list[tuple[float, float]]) -> float:
    acc = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        acc += x1 * y2 - x2 * y1
    return acc


def _ordered_edges(pts: list[tuple[float, float]]) -> list[_Edge]:
    """Boundary edges in deterministic walk order: longest edge first, then clockwise."""
    edges: list[_Edge] = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length < 1.0:
            continue
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        # pts are normalized clockwise, so the interior is to the right of travel
        edges.append(_Edge(ax=a[0], ay=a[1], ux=ux, uy=uy, nx=uy, ny=-ux, length=length))
    if not edges:
        raise ValidationError("Room boundary has no usable edges")
    start = max(range(len(edges)), key=lambda i: (edges[i].length, -i))
    return edges[start:] + edges[:start]


def _edge_rect(e: _Edge, t: float, w: float, depth: float) -> _Rect:
    p0 = (e.ax + e.ux * t, e.ay + e.uy * t)
    p1 = (e.ax + e.ux * (t + w), e.ay + e.uy * (t + w))
    p2 = (p0[0] + e.nx * depth, p0[1] + e.ny * depth)
    p3 = (p1[0] + e.nx * depth, p1[1] + e.ny * depth)
    xs = (p0[0], p1[0], p2[0], p3[0])
    ys = (p0[1], p1[1], p2[1], p3[1])
    return _Rect(min(xs), min(ys), max(xs), max(ys))


def _proj_end(e: _Edge, r: _Rect) -> float:
    """Furthest extent of rect ``r`` projected onto the edge axis (mm from edge start)."""
    return max(
        (cx - e.ax) * e.ux + (cy - e.ay) * e.uy
        for cx, cy in ((r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1))
    )


# --- model lookups ------------------------------------------------------------


def _find_room(model: ProjectModel, room: str) -> Element:
    rooms = [el for el in model.elements if el.category == "room"]
    for el in rooms:
        if el.id == room:
            return el
    for el in rooms:
        if el.name == room:
            return el
    raise ValidationError(
        "Unknown room — pass a room element id or name",
        room=room,
        known_rooms=[r.name or r.id for r in rooms],
    )


def _level_name(model: ProjectModel, level_id: str | None) -> str:
    for lv in model.levels:
        if lv.id == level_id:
            return lv.name
    if model.levels:
        return model.levels[0].name
    raise ValidationError("Project has no levels — add a level before auto-placing equipment")


def _normalize_items(items: Any, default_clearance_mm: float) -> list[_Item]:
    if not isinstance(items, (list, tuple)) or not items:
        raise ValidationError(
            "items must be a non-empty list of {name, w_mm, d_mm, h_mm, ...} dicts"
        )
    out: list[_Item] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            raise ValidationError("Each item must be a dict", index=i)
        name = str(raw.get("name") or "").strip()
        if not name:
            raise ValidationError("Item requires a name", index=i)
        try:
            w = float(raw["w_mm"])
            d = float(raw["d_mm"])
            h = float(raw["h_mm"])
        except (KeyError, TypeError, ValueError) as e:
            raise ValidationError(
                "Item requires numeric w_mm, d_mm, h_mm footprint", item=name
            ) from e
        if w <= 0 or d <= 0 or h <= 0:
            raise ValidationError("Item w_mm/d_mm/h_mm must be positive", item=name)
        cf = raw.get("clearance_front_mm")
        clearance = float(cf) if cf is not None else float(default_clearance_mm)
        if clearance < 0:
            raise ValidationError("clearance_front_mm must be non-negative", item=name)
        out.append(
            _Item(
                name=name,
                kind=str(raw.get("kind") or "equipment"),
                w_mm=w,
                d_mm=d,
                h_mm=h,
                clearance_front_mm=clearance,
                against_wall=bool(raw.get("against_wall", True)),
            )
        )
    # deterministic order: footprint area descending, then name
    out.sort(key=lambda it: (-(it.w_mm * it.d_mm), it.name))
    return out


def _existing_equipment_rects(model: ProjectModel, level_id: str | None) -> list[_Rect]:
    rects: list[_Rect] = []
    for el in model.elements:
        if el.category != "equipment":
            continue
        if level_id and el.level_id and el.level_id != level_id:
            continue
        poly = el.params.get("polygon_mm")
        if isinstance(poly, list) and len(poly) >= 3:
            try:
                xs = [float(p[0]) for p in poly]
                ys = [float(p[1]) for p in poly]
            except (TypeError, ValueError, IndexError):
                continue
            r = _Rect(min(xs), min(ys), max(xs), max(ys))
        else:
            o = el.params.get("origin_mm")
            s = el.params.get("size_mm")
            if not o or not s:
                continue
            try:
                x0, y0 = float(o[0]), float(o[1])
                lx, ly = float(s[0]), float(s[1])
            except (TypeError, ValueError, IndexError):
                continue
            r = _Rect(x0, y0, x0 + lx, y0 + ly)
        if r.x1 - r.x0 > _TOUCH_TOL_MM and r.y1 - r.y0 > _TOUCH_TOL_MM:
            rects.append(r)
    return rects


def _door_zones(
    model: ProjectModel, level_id: str | None, edges: list[_Edge]
) -> tuple[list[list[tuple[float, float]]], list[_Rect]]:
    """Per-edge blocked intervals + plan swing rectangles for doors on boundary walls.

    A door blocks its opening plus ``door width + 300 mm`` swing margin on each
    side, projected onto any boundary edge the host wall sits on (within
    half-thickness + tolerance). The swing rectangle extends the same span
    into the room interior by ``door width + 300 mm``.
    """
    blocked: list[list[tuple[float, float]]] = [[] for _ in edges]
    swings: list[_Rect] = []
    for door in model.elements:
        if door.category != "door" or not door.host_id:
            continue
        try:
            host = model.get_element(door.host_id)
        except Exception:  # noqa: BLE001 — orphan hosts are simply skipped
            continue
        if host.category != "wall":
            continue
        if level_id and host.level_id and host.level_id != level_id:
            continue
        try:
            s = host.params["start_mm"]
            e = host.params["end_mm"]
            sx, sy = float(s[0]), float(s[1])
            ex, ey = float(e[0]), float(e[1])
            off = float(door.params.get("offset_mm") or 0.0)
            width = float(door.params.get("width_mm") or 900.0)
            th = float(host.params.get("thickness_mm") or 200.0)
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        wall_len = math.hypot(ex - sx, ey - sy)
        if wall_len < 1.0:
            continue
        wux, wuy = (ex - sx) / wall_len, (ey - sy) / wall_len
        p0 = (sx + wux * off, sy + wuy * off)
        p1 = (sx + wux * (off + width), sy + wuy * (off + width))
        tol = th / 2 + _EDGE_LATERAL_TOL_MM
        margin = width + DOOR_SWING_MARGIN_MM
        for i, edge in enumerate(edges):
            d0 = (p0[0] - edge.ax) * edge.uy - (p0[1] - edge.ay) * edge.ux
            d1 = (p1[0] - edge.ax) * edge.uy - (p1[1] - edge.ay) * edge.ux
            if max(abs(d0), abs(d1)) > tol:
                continue
            t0 = (p0[0] - edge.ax) * edge.ux + (p0[1] - edge.ay) * edge.uy
            t1 = (p1[0] - edge.ax) * edge.ux + (p1[1] - edge.ay) * edge.uy
            lo, hi = min(t0, t1), max(t0, t1)
            if hi < 0 or lo > edge.length:
                continue
            blocked[i].append((lo - margin, hi + margin))
            swing = _edge_rect(edge, lo - margin, (hi - lo) + 2 * margin, margin)
            swings.append(swing)
    return blocked, swings


# --- placement engine ---------------------------------------------------------


@dataclass
class _Placer:
    model: ProjectModel
    room: Element
    level_name: str
    polygon: list[tuple[float, float]]
    strategy: str
    aisle_mm: float
    swings: list[_Rect] = field(default_factory=list)
    existing: list[_Rect] = field(default_factory=list)
    placed_fp: list[_Rect] = field(default_factory=list)
    placed_res: list[_Rect] = field(default_factory=list)
    placed: list[dict[str, Any]] = field(default_factory=list)
    unplaced: list[dict[str, Any]] = field(default_factory=list)

    def blocking(self, fp: _Rect, res: _Rect) -> list[_Rect]:
        """Obstacles conflicting with a candidate footprint + front-clearance zone.

        The candidate's reserved zone (footprint + clearance) must not overlap
        any footprint; the candidate's footprint must not overlap any other
        item's reserved zone or a door swing. Clearance zones may share space
        (aisles are shared circulation).
        """
        hits = [ob for ob in self.existing if res.overlaps(ob)]
        hits += [ob for ob in self.placed_fp if res.overlaps(ob)]
        hits += [ob for ob in self.placed_res if fp.overlaps(ob)]
        hits += [ob for ob in self.swings if fp.overlaps(ob)]
        return hits

    def commit(
        self, item: _Item, fp: _Rect, res: _Rect, rotation_deg: float, via: str
    ) -> None:
        result = CreateEquipmentBox(
            level=self.level_name,
            origin=(fp.x0, fp.y0),
            size=(fp.x1 - fp.x0, fp.y1 - fp.y0, item.h_mm),
            name=item.name,
            kind=item.kind,
        ).apply(self.model)
        eid = str(result["element_id"])
        el = self.model.get_element(eid)
        el.params["placement_basis"] = PLACEMENT_BASIS
        el.params["clearance_front_mm"] = item.clearance_front_mm
        el.params["room"] = self.room.name or self.room.id
        el.params["room_id"] = self.room.id
        el.params["placement_strategy"] = self.strategy
        el.params["rotation_deg"] = rotation_deg
        el.params["clear_zone_mm"] = [res.x0, res.y0, res.x1, res.y1]
        self.placed_fp.append(fp)
        self.placed_res.append(res)
        self.placed.append(
            {
                "id": eid,
                "name": item.name,
                "origin_mm": [fp.x0, fp.y0],
                "size_mm": [fp.x1 - fp.x0, fp.y1 - fp.y0, item.h_mm],
                "rotation_deg": rotation_deg,
                "footprint_mm": [fp.x0, fp.y0, fp.x1, fp.y1],
                "reserved_mm": [res.x0, res.y0, res.x1, res.y1],
                "clearance_front_mm": item.clearance_front_mm,
                "via": via,
            }
        )

    def reject(self, item: _Item, reason: str) -> None:
        self.unplaced.append(
            {
                "name": item.name,
                "w_mm": item.w_mm,
                "d_mm": item.d_mm,
                "clearance_front_mm": item.clearance_front_mm,
                "reason": reason,
            }
        )

    # -- perimeter -------------------------------------------------------------

    def scan_edge(
        self,
        edge: _Edge,
        cursor: float,
        item: _Item,
        blocked: list[tuple[float, float]],
    ) -> tuple[_Rect, _Rect, float] | None:
        w, d, c = item.w_mm, item.d_mm, item.clearance_front_mm
        t = cursor
        for _ in range(_MAX_SCAN_ITER):
            if t + w > edge.length + 1e-6:
                return None
            door_hits = [iv for iv in blocked if iv[0] < t + w and iv[1] > t]
            if door_hits:
                t = max(t + _MIN_STEP_MM, min(iv[1] for iv in door_hits))
                continue
            fp = _edge_rect(edge, t, w, d)
            res = _edge_rect(edge, t, w, d + c)
            if not _rect_in_polygon(fp, self.polygon) or not _rect_in_polygon(res, self.polygon):
                t += _MIN_STEP_MM
                continue
            hits = self.blocking(fp, res)
            if hits:
                t = max(t + _MIN_STEP_MM, min(_proj_end(edge, ob) for ob in hits))
                continue
            return fp, res, t
        return None

    def place_perimeter(
        self,
        items: list[_Item],
        edges: list[_Edge],
        blocked: list[list[tuple[float, float]]],
    ) -> None:
        cursors = [0.0 for _ in edges]
        for item in items:
            found: tuple[int, _Rect, _Rect, float] | None = None
            for ei, edge in enumerate(edges):
                hit = self.scan_edge(edge, cursors[ei], item, blocked[ei])
                if hit is not None:
                    found = (ei, hit[0], hit[1], hit[2])
                    break
            if found is None:
                self.reject(
                    item,
                    "no boundary segment fits "
                    f"{item.w_mm:.0f}x{item.d_mm:.0f} mm back-to-wall with "
                    f"{item.clearance_front_mm:.0f} mm front clearance "
                    "(room size, door swings, and existing equipment considered)",
                )
                continue
            ei, fp, res, t = found
            edge = edges[ei]
            rotation = round(math.degrees(math.atan2(edge.ny, edge.nx)), 3) % 360.0
            self.commit(item, fp, res, rotation, via=f"perimeter:edge{ei}")
            cursors[ei] = t + item.w_mm + self.aisle_mm

    # -- grid ------------------------------------------------------------------

    def place_grid(self, items: list[_Item], margin_mm: float) -> None:
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        gx0, gx1 = min(xs) + margin_mm, max(xs) - margin_mm
        gy0, gy1 = min(ys) + margin_mm, max(ys) - margin_mm
        x, y = gx0, gy0
        row_depth = 0.0
        for item in items:
            w, d, c = item.w_mm, item.d_mm, item.clearance_front_mm
            if w > gx1 - gx0 or d + c > gy1 - gy0:
                self.reject(
                    item,
                    f"footprint {w:.0f}x{d:.0f} mm + {c:.0f} mm clearance exceeds "
                    "the room interior (after wall margin)",
                )
                continue
            reason = "no unobstructed interior space left (rows exhausted)"
            done = False
            for _ in range(_MAX_SCAN_ITER):
                if x + w > gx1 + 1e-6:
                    y += (row_depth if row_depth > 0 else self.aisle_mm) + self.aisle_mm
                    x = gx0
                    row_depth = 0.0
                    continue
                if y + d + c > gy1 + 1e-6:
                    reason = "no interior row left with enough depth for footprint + clearance"
                    break
                fp = _Rect(x, y, x + w, y + d)
                res = _Rect(x, y, x + w, y + d + c)
                if not _rect_in_polygon(fp, self.polygon) or not _rect_in_polygon(
                    res, self.polygon
                ):
                    x += _MIN_STEP_MM
                    continue
                hits = self.blocking(fp, res)
                if hits:
                    x = max(x + _MIN_STEP_MM, min(ob.x1 for ob in hits))
                    continue
                self.commit(item, fp, res, 90.0, via="grid")
                x = fp.x1 + self.aisle_mm
                row_depth = max(row_depth, d + c)
                done = True
                break
            if not done:
                self.reject(item, reason)


# --- public API ---------------------------------------------------------------


def auto_place_equipment(
    model: ProjectModel,
    *,
    room: str,
    items: list[dict[str, Any]],
    clearance_mm: float = 900.0,
    aisle_mm: float = 1200.0,
    strategy: str = "perimeter",
) -> dict[str, Any]:
    """Derive equipment coordinates from requirements and place real elements.

    room: room element id or name. items: [{name, w_mm, d_mm, h_mm, kind?,
    clearance_front_mm?, against_wall?}]. Every placed item becomes a real
    equipment element (command bus) tagged with ``placement_basis``; items
    that cannot fit are returned in ``unplaced`` with a reason.
    """
    if float(clearance_mm) < 0 or float(aisle_mm) < 0:
        raise ValidationError("clearance_mm and aisle_mm must be non-negative")
    strat = str(strategy or "perimeter").lower()
    if strat not in {"perimeter", "grid"}:
        raise ValidationError("strategy must be 'perimeter' or 'grid'", strategy=strategy)
    room_el = _find_room(model, str(room))
    pts = _clean_boundary(room_el.params.get("boundary_mm"))
    if _signed_area2(pts) > 0:
        pts = list(reversed(pts))  # normalize clockwise
    norm_items = _normalize_items(items, float(clearance_mm))
    level_name = _level_name(model, room_el.level_id)
    edges = _ordered_edges(pts)
    blocked, swings = _door_zones(model, room_el.level_id, edges)

    placer = _Placer(
        model=model,
        room=room_el,
        level_name=level_name,
        polygon=pts,
        strategy=strat,
        aisle_mm=float(aisle_mm),
        swings=swings,
        existing=_existing_equipment_rects(model, room_el.level_id),
    )
    if strat == "perimeter":
        wall_items = [it for it in norm_items if it.against_wall]
        free_items = [it for it in norm_items if not it.against_wall]
        placer.place_perimeter(wall_items, edges, blocked)
        if free_items:
            placer.place_grid(free_items, float(clearance_mm))
    else:
        placer.place_grid(norm_items, float(clearance_mm))

    return {
        "room": room_el.name or room_el.id,
        "room_id": room_el.id,
        "level": level_name,
        "strategy": strat,
        "placement_basis": PLACEMENT_BASIS,
        "placed": placer.placed,
        "unplaced": placer.unplaced,
        "placed_count": len(placer.placed),
        "unplaced_count": len(placer.unplaced),
        "ok": not placer.unplaced,
    }


def auto_place_by_needs(
    model: ProjectModel, *, assignments: list[dict[str, Any]]
) -> dict[str, Any]:
    """Run :func:`auto_place_equipment` per room and aggregate the results.

    assignments: [{room, items, strategy?, clearance_mm?, aisle_mm?}].
    """
    if not isinstance(assignments, (list, tuple)) or not assignments:
        raise ValidationError(
            "assignments must be a non-empty list of {room, items, ...} dicts"
        )
    results: list[dict[str, Any]] = []
    for i, a in enumerate(assignments):
        if not isinstance(a, dict):
            raise ValidationError("Each assignment must be a dict", index=i)
        if not a.get("room") or a.get("items") is None:
            raise ValidationError("Assignment requires room and items", index=i)
        results.append(
            auto_place_equipment(
                model,
                room=str(a["room"]),
                items=a["items"],
                clearance_mm=float(a.get("clearance_mm", 900.0)),
                aisle_mm=float(a.get("aisle_mm", 1200.0)),
                strategy=str(a.get("strategy", "perimeter")),
            )
        )
    placed_total = sum(len(r["placed"]) for r in results)
    unplaced_total = sum(len(r["unplaced"]) for r in results)
    return {
        "rooms": len(results),
        "placed_count": placed_total,
        "unplaced_count": unplaced_total,
        "placement_basis": PLACEMENT_BASIS,
        "results": results,
        "ok": unplaced_total == 0,
    }
