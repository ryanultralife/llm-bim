"""2D primitives for plan-level geometry."""

from __future__ import annotations

import math
from typing import NamedTuple

from llmbim_core.errors import GeometryDegenerateError


class Vec2(NamedTuple):
    x: float
    y: float


def distance(a: Vec2 | tuple[float, float], b: Vec2 | tuple[float, float]) -> float:
    ax, ay = a
    bx, by = b
    return math.hypot(bx - ax, by - ay)


def wall_length_mm(
    start: tuple[float, float] | Vec2,
    end: tuple[float, float] | Vec2,
    *,
    min_length_mm: float = 1.0,
) -> float:
    length = distance(start, end)
    if length < min_length_mm:
        raise GeometryDegenerateError(
            "Wall length below minimum",
            length_mm=length,
            min_length_mm=min_length_mm,
        )
    return length


def polygon_area_mm2(points: list[tuple[float, float]] | list[list[float]]) -> float:
    """Absolute shoelace area. Raises if degenerate."""
    if len(points) < 3:
        raise GeometryDegenerateError("Polygon needs >= 3 points", n=len(points))
    pts = [(float(p[0]), float(p[1])) for p in points]
    # Close if needed
    if pts[0] != pts[-1]:
        ring = pts + [pts[0]]
    else:
        ring = pts
    acc = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False):
        acc += x1 * y2 - x2 * y1
    area = abs(acc) * 0.5
    if area < 1e-6:
        raise GeometryDegenerateError("Polygon area near zero", area_mm2=area)
    return area


def point_along_segment(
    start: tuple[float, float],
    end: tuple[float, float],
    offset_mm: float,
) -> tuple[float, float]:
    """Point at distance offset_mm from start toward end."""
    length = wall_length_mm(start, end)
    t = offset_mm / length
    return (start[0] + t * (end[0] - start[0]), start[1] + t * (end[1] - start[1]))
