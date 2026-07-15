"""Unit conversion — accept anything common, store mm."""

from __future__ import annotations

from typing import Any

# factors TO millimetres
_TO_MM: dict[str, float] = {
    "mm": 1.0,
    "millimeter": 1.0,
    "millimetre": 1.0,
    "cm": 10.0,
    "centimeter": 10.0,
    "m": 1000.0,
    "meter": 1000.0,
    "metre": 1000.0,
    "km": 1_000_000.0,
    "in": 25.4,
    "inch": 25.4,
    "inches": 25.4,
    "ft": 304.8,
    "foot": 304.8,
    "feet": 304.8,
    "yd": 914.4,
    "yard": 914.4,
    "mil": 0.0254,
}


def normalize_unit(unit: str | None) -> str:
    if not unit:
        return "mm"
    u = unit.strip().lower().replace(" ", "")
    aliases = {"\"": "in", "'": "ft", "′": "ft", "″": "in"}
    u = aliases.get(u, u)
    if u not in _TO_MM:
        raise ValueError(f"Unknown unit {unit!r}. Supported: {sorted(set(_TO_MM))}")
    return u


def to_mm(value: float, unit: str | None = "mm") -> float:
    u = normalize_unit(unit)
    return float(value) * _TO_MM[u]


def from_mm(value_mm: float, unit: str | None = "mm") -> float:
    u = normalize_unit(unit)
    return float(value_mm) / _TO_MM[u]


def parse_length(value: Any, default_unit: str = "mm") -> float:
    """Parse number or string like '3.5m', '12ft', '100 mm' → mm."""
    if isinstance(value, (int, float)):
        return to_mm(float(value), default_unit)
    s = str(value).strip().lower().replace(",", "")
    # split number and unit
    num = ""
    unit = ""
    for i, ch in enumerate(s):
        if ch.isdigit() or ch in ".-+e":
            num += ch
        else:
            unit = s[i:].strip()
            break
    if not num:
        raise ValueError(f"Cannot parse length: {value!r}")
    return to_mm(float(num), unit or default_unit)


def point_to_mm(pt: Any, unit: str | None = "mm") -> tuple[float, float]:
    if isinstance(pt, dict):
        x = pt.get("x", pt.get(0))
        y = pt.get("y", pt.get(1))
        return to_mm(float(x), unit), to_mm(float(y), unit)
    return to_mm(float(pt[0]), unit), to_mm(float(pt[1]), unit)
