"""Drawing view value object — body content separate from outer <svg>."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DrawingView:
    """Renderable 2D view with size in SVG user units."""

    width: float
    height: float
    body: str  # inner markup only (no <svg> wrapper)
    title: str = ""

    def to_svg(self) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {self.width:.3f} {self.height:.3f}" '
            f'width="{self.width:.3f}" height="{self.height:.3f}">\n'
            f"{self.body}\n</svg>\n"
        )

    def scaled_to_fit(self, max_w: float, max_h: float, pad: float = 10.0) -> tuple[float, str]:
        """Return (scale_factor, transformed body) fitting inside max box."""
        usable_w = max(max_w - 2 * pad, 1.0)
        usable_h = max(max_h - 2 * pad, 1.0)
        if self.width <= 0 or self.height <= 0:
            return 1.0, self.body
        s = min(usable_w / self.width, usable_h / self.height, 1.0)
        body = f'<g transform="translate({pad},{pad}) scale({s})">\n{self.body}\n</g>'
        return s, body
