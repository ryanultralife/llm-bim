"""Roof plane commands — gable / shed / low-level plane (WP-SCHAD-S2).

Planes are derived ONCE here and stored in element params so downstream
consumers (glTF mesh, elevations, sections, IFC) never re-derive slope
geometry. All coordinates are millimetres; plane-polygon Z values are
relative to the roof element's *level* elevation (same convention as
``z0_mm`` on other categories).

Every ``category="roof"`` element carries::

    kind             gable | shed | plane
    thickness_mm     roof solid thickness (default 150)
    planes           [{name, polygon_mm ([[x,y,z],...] 3D, convex, plan-CCW),
                       slope (rise/run), downhill_dir [dx,dy],
                       eave_z_mm, ridge_z_mm}, ...]
    ridge_line_mm    gable only — 3D ridge segment [[x,y,z],[x,y,z]]
    valley_lines_mm  gable only — 3D plane-intersection segments against
                     previously created overlapping roofs
    valley_with      element ids of the roofs those valleys were cut against

Honesty: valley lines are *geometric plane intersections* for coordination —
not framing design (no valley rafter sizing, bearing, or flashing detail).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from llmbim_core.commands import Command, DeleteElement
from llmbim_core.errors import ValidationError
from llmbim_core.ids import new_id
from llmbim_core.model import Element, ProjectModel

DEFAULT_ROOF_THICKNESS_MM = 150.0

_MIN_VALLEY_LEN_MM = 50.0


# --- plane math helpers (public: reused by drawings/section renderers) --------


def plane_coeffs(
    polygon_mm: Sequence[Sequence[float]],
) -> tuple[float, float, float] | None:
    """Fit ``z = a*x + b*y + c`` through a 3D roof-plane polygon.

    Uses the first non-degenerate point triple. Returns None for vertical
    or collinear (degenerate) polygons.
    """
    pts = [(float(p[0]), float(p[1]), float(p[2])) for p in polygon_mm]
    n = len(pts)
    if n < 3:
        return None
    x0, y0, z0 = pts[0]
    for i in range(1, n - 1):
        x1, y1, z1 = pts[i]
        x2, y2, z2 = pts[i + 1]
        det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(det) < 1e-6:
            continue
        a = ((z1 - z0) * (y2 - y0) - (z2 - z0) * (y1 - y0)) / det
        b = ((x1 - x0) * (z2 - z0) - (x2 - x0) * (z1 - z0)) / det
        c = z0 - a * x0 - b * y0
        return a, b, c
    return None


def clip_segment_to_polygon(
    p: tuple[float, float],
    q: tuple[float, float],
    polygon: Sequence[Sequence[float]],
) -> tuple[float, float] | None:
    """Cyrus–Beck clip of plan segment p→q against a convex plan polygon.

    ``polygon`` points may be 2D or 3D (extra coords ignored); winding may be
    CW or CCW. Returns the (t0, t1) parameter window of the segment inside
    the polygon (0 ≤ t0 ≤ t1 ≤ 1), or None when fully outside.
    """
    pts = [(float(v[0]), float(v[1])) for v in polygon]
    n = len(pts)
    if n < 3:
        return None
    # orient CCW so "inside" is the left side of each edge
    area2 = sum(
        pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n)
    )
    if area2 < 0:
        pts.reverse()
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for i in range(n):
        ex0, ey0 = pts[i]
        ex1, ey1 = pts[(i + 1) % n]
        # inward normal of CCW edge
        nx, ny = -(ey1 - ey0), ex1 - ex0
        denom = nx * dx + ny * dy
        dist = nx * (p[0] - ex0) + ny * (p[1] - ey0)
        if abs(denom) < 1e-12:
            if dist < -1e-6:
                return None  # parallel and outside this edge
            continue
        t = -dist / denom
        if denom > 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1 + 1e-12:
            return None
    if t1 - t0 < 1e-12:
        return None
    return t0, t1


def _plan_bbox(polygons: Sequence[Sequence[Sequence[float]]]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for poly in polygons:
        for pt in poly:
            xs.append(float(pt[0]))
            ys.append(float(pt[1]))
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), min(ys), max(xs), max(ys)


def valley_segments(
    planes_a: Sequence[dict[str, Any]],
    planes_b: Sequence[dict[str, Any]],
) -> list[list[list[float]]]:
    """Plane-intersection (valley/hip) lines between two roofs' plane sets.

    For every plane pair whose slopes differ, intersects the two plane
    equations (a plan line), clips it to BOTH plane polygons, and returns 3D
    segments ``[[x,y,z],[x,y,z]]``. Geometric coordination only — not framing.
    """
    out: list[list[list[float]]] = []
    for pa in planes_a:
        poly_a = pa.get("polygon_mm") or []
        ca = plane_coeffs(poly_a)
        if ca is None:
            continue
        for pb in planes_b:
            poly_b = pb.get("polygon_mm") or []
            cb = plane_coeffs(poly_b)
            if cb is None:
                continue
            va, vb, vc = ca[0] - cb[0], ca[1] - cb[1], ca[2] - cb[2]
            norm = math.hypot(va, vb)
            if norm < 1e-9:
                continue  # parallel planes — no finite intersection line
            # plan line va*x + vb*y + vc = 0: base point + unit direction
            base_x = -vc * va / (norm * norm)
            base_y = -vc * vb / (norm * norm)
            dx, dy = -vb / norm, va / norm
            bx0, by0, bx1, by1 = _plan_bbox([poly_a, poly_b])
            half = math.hypot(bx1 - bx0, by1 - by0) + 1000.0
            p0 = (base_x - dx * half, base_y - dy * half)
            p1 = (base_x + dx * half, base_y + dy * half)
            win_a = clip_segment_to_polygon(p0, p1, poly_a)
            if win_a is None:
                continue
            win_b = clip_segment_to_polygon(p0, p1, poly_b)
            if win_b is None:
                continue
            t0 = max(win_a[0], win_b[0])
            t1 = min(win_a[1], win_b[1])
            if t1 <= t0:
                continue
            sx0, sy0 = p0[0] + t0 * (p1[0] - p0[0]), p0[1] + t0 * (p1[1] - p0[1])
            sx1, sy1 = p0[0] + t1 * (p1[0] - p0[0]), p0[1] + t1 * (p1[1] - p0[1])
            if math.hypot(sx1 - sx0, sy1 - sy0) < _MIN_VALLEY_LEN_MM:
                continue
            z0 = ca[0] * sx0 + ca[1] * sy0 + ca[2]
            z1 = ca[0] * sx1 + ca[1] * sy1 + ca[2]
            out.append([[sx0, sy0, z0], [sx1, sy1, z1]])
    return out


def _footprint_bbox(
    footprint: Sequence[tuple[float, float]],
) -> tuple[float, float, float, float]:
    if len(footprint) < 3:
        raise ValidationError("Roof footprint needs at least 3 points")
    xs = [float(p[0]) for p in footprint]
    ys = [float(p[1]) for p in footprint]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    if x1 - x0 < 1.0 or y1 - y0 < 1.0:
        raise ValidationError("Roof footprint is degenerate", w_mm=x1 - x0, d_mm=y1 - y0)
    return x0, y0, x1, y1


def _plane(
    name: str,
    polygon: list[tuple[float, float, float]],
    slope: float,
    downhill: tuple[float, float],
    eave_z: float,
    ridge_z: float,
) -> dict[str, Any]:
    return {
        "name": name,
        "polygon_mm": [[float(x), float(y), float(z)] for x, y, z in polygon],
        "slope": float(slope),
        "downhill_dir": [float(downhill[0]), float(downhill[1])],
        "eave_z_mm": float(eave_z),
        "ridge_z_mm": float(ridge_z),
    }


def _collect_valleys(
    model: ProjectModel,
    level_id: str | None,
    new_planes: Sequence[dict[str, Any]],
) -> tuple[list[list[list[float]]], list[str]]:
    """Valleys of the new roof's planes against existing overlapping roofs.

    Only roofs on the same level are considered (plane Z is level-relative).
    """
    bx0, by0, bx1, by1 = _plan_bbox([pl["polygon_mm"] for pl in new_planes])
    valleys: list[list[list[float]]] = []
    against: list[str] = []
    for el in model.elements:
        if el.category != "roof" or el.level_id != level_id:
            continue
        other_planes = el.params.get("planes") or []
        if not other_planes:
            continue
        ox0, oy0, ox1, oy1 = _plan_bbox(
            [pl.get("polygon_mm") or [] for pl in other_planes]
        )
        if ox1 < bx0 or ox0 > bx1 or oy1 < by0 or oy0 > by1:
            continue  # plan bboxes don't overlap — no intersection possible
        segs = valley_segments(new_planes, other_planes)
        if segs:
            valleys.extend(segs)
            against.append(el.id)
    return valleys, against


# --- commands ----------------------------------------------------------------


@dataclass
class CreateGableRoof(Command):
    """Symmetric-pitch gable roof over a rectangular footprint bbox.

    ``pitch`` is rise/run (6:12 → 0.5). ``ridge_offset_mm`` measures from the
    low-coordinate footprint edge perpendicular to ``ridge_axis`` (None →
    centered). Both planes keep ``pitch`` when centered; for an off-center
    ridge the shorter run keeps ``pitch`` and the longer side is flattened so
    the planes still meet at one ridge (stored per-plane ``slope`` is honest).
    Eaves extend ``overhang_mm`` past the footprint on all sides; the roof
    surface continues at slope over the overhang (eave z < plate z).
    """

    level: str
    footprint: list[tuple[float, float]]
    ridge_axis: str = "x"
    ridge_offset_mm: float | None = None
    plate_mm: float = 3000.0
    pitch: float = 0.5
    overhang_mm: float = 450.0
    thickness_mm: float = DEFAULT_ROOF_THICKNESS_MM
    name: str = ""
    op: str = "create_gable_roof"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        lv = model.get_level(self.level)
        if self.pitch <= 0:
            raise ValidationError("pitch must be positive (rise/run)", pitch=self.pitch)
        if self.overhang_mm < 0:
            raise ValidationError("overhang_mm must be non-negative")
        if self.thickness_mm <= 0:
            raise ValidationError("thickness_mm must be positive")
        axis = (self.ridge_axis or "x").lower()
        if axis not in {"x", "y"}:
            raise ValidationError("ridge_axis must be 'x' or 'y'", ridge_axis=self.ridge_axis)
        x0, y0, x1, y1 = _footprint_bbox(self.footprint)
        ov = float(self.overhang_mm)
        plate = float(self.plate_mm)

        span = (y1 - y0) if axis == "x" else (x1 - x0)
        lo = y0 if axis == "x" else x0
        hi = y1 if axis == "x" else x1
        rc = lo + (span / 2.0 if self.ridge_offset_mm is None else float(self.ridge_offset_mm))
        if not (lo < rc < hi):
            raise ValidationError(
                "ridge_offset_mm must fall inside the footprint span",
                ridge_offset_mm=self.ridge_offset_mm,
                span_mm=span,
            )
        run_lo = rc - lo
        run_hi = hi - rc
        rise = self.pitch * min(run_lo, run_hi)
        ridge_z = plate + rise
        slope_lo = rise / run_lo
        slope_hi = rise / run_hi
        eave_lo_z = plate - slope_lo * ov
        eave_hi_z = plate - slope_hi * ov

        if axis == "x":
            plane_lo = _plane(
                "S",
                [
                    (x0 - ov, y0 - ov, eave_lo_z),
                    (x1 + ov, y0 - ov, eave_lo_z),
                    (x1 + ov, rc, ridge_z),
                    (x0 - ov, rc, ridge_z),
                ],
                slope_lo,
                (0.0, -1.0),
                eave_lo_z,
                ridge_z,
            )
            plane_hi = _plane(
                "N",
                [
                    (x0 - ov, rc, ridge_z),
                    (x1 + ov, rc, ridge_z),
                    (x1 + ov, y1 + ov, eave_hi_z),
                    (x0 - ov, y1 + ov, eave_hi_z),
                ],
                slope_hi,
                (0.0, 1.0),
                eave_hi_z,
                ridge_z,
            )
            ridge_line = [[x0 - ov, rc, ridge_z], [x1 + ov, rc, ridge_z]]
        else:
            plane_lo = _plane(
                "W",
                [
                    (x0 - ov, y0 - ov, eave_lo_z),
                    (rc, y0 - ov, ridge_z),
                    (rc, y1 + ov, ridge_z),
                    (x0 - ov, y1 + ov, eave_lo_z),
                ],
                slope_lo,
                (-1.0, 0.0),
                eave_lo_z,
                ridge_z,
            )
            plane_hi = _plane(
                "E",
                [
                    (rc, y0 - ov, ridge_z),
                    (x1 + ov, y0 - ov, eave_hi_z),
                    (x1 + ov, y1 + ov, eave_hi_z),
                    (rc, y1 + ov, ridge_z),
                ],
                slope_hi,
                (1.0, 0.0),
                eave_hi_z,
                ridge_z,
            )
            ridge_line = [[rc, y0 - ov, ridge_z], [rc, y1 + ov, ridge_z]]

        planes = [plane_lo, plane_hi]
        valleys, against = _collect_valleys(model, lv.id, planes)

        eid = self._element_id or new_id("rof")
        params: dict[str, Any] = {
            "kind": "gable",
            "footprint_mm": [[float(p[0]), float(p[1])] for p in self.footprint],
            "ridge_axis": axis,
            "ridge_offset_mm": float(rc - lo),
            "plate_mm": plate,
            "pitch": float(self.pitch),
            "overhang_mm": ov,
            "thickness_mm": float(self.thickness_mm),
            "ridge_z_mm": ridge_z,
            "ridge_line_mm": ridge_line,
            "planes": planes,
            "valley_lines_mm": valleys,
            "valley_with": against,
            "honesty": (
                "Roof planes + valley intersections are geometric coordination, "
                "not framing design"
            ),
        }
        el = Element(
            id=eid,
            category="roof",
            name=self.name or "Roof-Gable",
            level_id=lv.id,
            params=params,
        )
        model.add_element(el)
        self._element_id = el.id
        return {
            "element_id": el.id,
            "category": "roof",
            "kind": "gable",
            "ridge_z_mm": ridge_z,
            "plane_count": len(planes),
            "valley_count": len(valleys),
            "valley_with": against,
        }

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert CreateGableRoof before apply")
        return DeleteElement(element_id=self._element_id)


@dataclass
class CreateShedRoof(Command):
    """Single sloped plane over the footprint bbox, rising toward ``high_side``.

    Slope derives from the two plate heights over the footprint run; eaves
    extend ``overhang_mm`` on all sides, continuing the plane.
    """

    level: str
    footprint: list[tuple[float, float]]
    high_side: str = "N"
    plate_low_mm: float = 3000.0
    plate_high_mm: float = 3600.0
    overhang_mm: float = 450.0
    thickness_mm: float = DEFAULT_ROOF_THICKNESS_MM
    name: str = ""
    op: str = "create_shed_roof"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        lv = model.get_level(self.level)
        side = (self.high_side or "N").upper()
        if side not in {"N", "S", "E", "W"}:
            raise ValidationError("high_side must be N|S|E|W", high_side=self.high_side)
        if self.plate_high_mm < self.plate_low_mm:
            raise ValidationError(
                "plate_high_mm must be >= plate_low_mm",
                plate_low_mm=self.plate_low_mm,
                plate_high_mm=self.plate_high_mm,
            )
        if self.overhang_mm < 0:
            raise ValidationError("overhang_mm must be non-negative")
        if self.thickness_mm <= 0:
            raise ValidationError("thickness_mm must be positive")
        x0, y0, x1, y1 = _footprint_bbox(self.footprint)
        ov = float(self.overhang_mm)
        lo_z = float(self.plate_low_mm)
        hi_z = float(self.plate_high_mm)
        run = (y1 - y0) if side in {"N", "S"} else (x1 - x0)
        slope = (hi_z - lo_z) / run

        def z_at(x: float, y: float) -> float:
            if side == "N":
                return lo_z + slope * (y - y0)
            if side == "S":
                return lo_z + slope * (y1 - y)
            if side == "E":
                return lo_z + slope * (x - x0)
            return lo_z + slope * (x1 - x)

        corners = [
            (x0 - ov, y0 - ov),
            (x1 + ov, y0 - ov),
            (x1 + ov, y1 + ov),
            (x0 - ov, y1 + ov),
        ]
        poly = [(cx, cy, z_at(cx, cy)) for cx, cy in corners]
        downhill = {
            "N": (0.0, -1.0),
            "S": (0.0, 1.0),
            "E": (-1.0, 0.0),
            "W": (1.0, 0.0),
        }[side]
        plane = _plane(
            f"SHED-{side}", poly, slope, downhill, lo_z - slope * ov, hi_z + slope * ov
        )

        eid = self._element_id or new_id("rof")
        params: dict[str, Any] = {
            "kind": "shed",
            "footprint_mm": [[float(p[0]), float(p[1])] for p in self.footprint],
            "high_side": side,
            "plate_low_mm": lo_z,
            "plate_high_mm": hi_z,
            "overhang_mm": ov,
            "thickness_mm": float(self.thickness_mm),
            "slope": float(slope),
            "planes": [plane],
        }
        el = Element(
            id=eid,
            category="roof",
            name=self.name or "Roof-Shed",
            level_id=lv.id,
            params=params,
        )
        model.add_element(el)
        self._element_id = el.id
        return {
            "element_id": el.id,
            "category": "roof",
            "kind": "shed",
            "slope": slope,
            "plane_count": 1,
        }

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert CreateShedRoof before apply")
        return DeleteElement(element_id=self._element_id)


@dataclass
class CreateRoofPlane(Command):
    """Low-level: one roof plane from an explicit convex 3D polygon (mm).

    Z values are relative to the level elevation. The polygon must be planar
    and non-vertical (a plane ``z = f(x, y)`` must exist).
    """

    level: str
    polygon: list[tuple[float, float, float]]
    thickness_mm: float = DEFAULT_ROOF_THICKNESS_MM
    name: str = ""
    op: str = "create_roof_plane"
    _element_id: str | None = None

    def apply(self, model: ProjectModel) -> dict[str, Any]:
        lv = model.get_level(self.level)
        if len(self.polygon) < 3:
            raise ValidationError("Roof plane polygon needs at least 3 points")
        if self.thickness_mm <= 0:
            raise ValidationError("thickness_mm must be positive")
        poly = [(float(p[0]), float(p[1]), float(p[2])) for p in self.polygon]
        coeffs = plane_coeffs(poly)
        if coeffs is None:
            raise ValidationError(
                "Roof plane polygon is vertical or degenerate (needs z = f(x,y))"
            )
        a, b, _c = coeffs
        slope = math.hypot(a, b)
        if slope > 1e-9:
            downhill = (-a / slope, -b / slope)
        else:
            downhill = (0.0, 0.0)
        zs = [p[2] for p in poly]
        plane = _plane("PLANE", poly, slope, downhill, min(zs), max(zs))

        eid = self._element_id or new_id("rof")
        params: dict[str, Any] = {
            "kind": "plane",
            "thickness_mm": float(self.thickness_mm),
            "slope": float(slope),
            "planes": [plane],
        }
        el = Element(
            id=eid,
            category="roof",
            name=self.name or "Roof-Plane",
            level_id=lv.id,
            params=params,
        )
        model.add_element(el)
        self._element_id = el.id
        return {
            "element_id": el.id,
            "category": "roof",
            "kind": "plane",
            "slope": slope,
            "plane_count": 1,
        }

    def invert(self) -> Command:
        if not self._element_id:
            raise ValidationError("Cannot invert CreateRoofPlane before apply")
        return DeleteElement(element_id=self._element_id)
