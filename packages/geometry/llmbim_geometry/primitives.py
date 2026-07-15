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
