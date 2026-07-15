"""Shared SVG helpers."""

from __future__ import annotations

from xml.sax.saxutils import escape

_COORD_DECIMALS = 3


def fmt(value: float) -> str:
    rounded = round(value, _COORD_DECIMALS)
    if rounded == 0:
        rounded = 0.0
    text = f"{rounded:.{_COORD_DECIMALS}f}".rstrip("0").rstrip(".")
    return text or "0"


def esc(text: str) -> str:
    return escape(text)
