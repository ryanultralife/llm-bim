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
    pad: float = 0.0  # screen-space margin revealed on all sides (for dimension bands)

    def to_svg(self) -> str:
        # A negative-origin viewBox reveals `pad` units around the [0,width]x[0,height]
        # content box without moving any geometry, so dimension lines/text and grid
        # bubbles that extend just outside the model extents stay on-canvas.
        p = self.pad
        vb_w = self.width + 2 * p
        vb_h = self.height + 2 * p
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{-p:.3f} {-p:.3f} {vb_w:.3f} {vb_h:.3f}" '
            f'width="{vb_w:.3f}" height="{vb_h:.3f}">\n'
            f"{self.body}\n</svg>\n"
        )

    def scaled_to_fit(self, max_w: float, max_h: float, pad: float = 10.0) -> tuple[float, str]:
        """Return (scale_factor, transformed body) fitting inside max box.

        Accounts for ``self.pad``: the body's content spans ``[-pad, width+pad]``
        (dimension bands / grid bubbles reach outside the geometry box), so the
        fit uses the padded extent and the translate shifts the content's real
        top-left ``(-pad, -pad)`` to ``(pad, pad)`` — otherwise those annotations
        clip off the sheet frame.
        """
        p = self.pad
        content_w = self.width + 2 * p
        content_h = self.height + 2 * p
        usable_w = max(max_w - 2 * pad, 1.0)
        usable_h = max(max_h - 2 * pad, 1.0)
        if content_w <= 0 or content_h <= 0:
            return 1.0, self.body
        s = min(usable_w / content_w, usable_h / content_h, 1.0)
        tx = pad + p * s
        ty = pad + p * s
        body = f'<g transform="translate({tx:.3f},{ty:.3f}) scale({s})">\n{self.body}\n</g>'
        return s, body
