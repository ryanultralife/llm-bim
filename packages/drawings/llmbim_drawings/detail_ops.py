"""Detail ops DSL renderer — data-driven 2D construction details.

A detail is a list of ops drawn in DETAIL-LOCAL FEET (x right, y up), the
vocabulary used by ``projects/schad/schad_details.py``:

    ('l', x1, y1, x2, y2[, weight])   solid line (weight: "heavy"|"light")
    ('d', x1, y1, x2, y2[, weight])   dashed line
    ('r', x, y, w, h)                 rectangle (x, y = lower-left)
    ('c', cx, cy, r)                  circle
    ('h', x, y, w, h)                 hatched region (45-degree hatch)
    ('t', x, y, w, 'text')            wrapped label (w = wrap width,
                                      1.0 ~ 60 characters per line)
    ('dim', x1, y1, x2, y2[, offset[, 'text']])
                                      dimension: extension lines + ticks +
                                      feet-inches text (offset in feet,
                                      perpendicular to the measured line)

``render_detail_ops`` converts one op list into a :class:`DrawingView`
(y flipped to screen space, ``scale`` px per foot). ``render_detail_sheet``
composes up to four detail dicts ``{id, title, scale, ops}`` 4-up via
``compose_sheet`` with drafting labels (``D01 — TITLE — 3/4" = 1'-0"``).
The data itself stays in the project modules — this is the renderer only.
"""

from __future__ import annotations

import math
import textwrap
from collections.abc import Mapping, Sequence
from typing import Any

from llmbim_core.errors import ValidationError

from llmbim_drawings.layout import compose_sheet
from llmbim_drawings.svg_util import esc, fmt
from llmbim_drawings.view import DrawingView

SUPPORTED_OPS = ("l", "d", "r", "c", "h", "t", "dim")

_FONT = 8.0  # label font size (SVG units, screen space)
_CHAR_W = 0.6  # average character width as a fraction of font size
_LINE_H = _FONT * 1.3  # wrapped-label line height
_MARGIN = 8.0  # canvas margin around geometry (SVG units)
_HATCH_STEP = 6.0  # 45-degree hatch spacing (SVG units)
_WRAP_CHARS_PER_UNIT = 60  # 't' wrap width 1.0 ft ~ 60 characters
_STROKES = {"heavy": 2.2, "normal": 1.2, "light": 0.7}


def format_feet_inches(value_ft: float) -> str:
    """Architectural feet-inches text: 3.5 -> ``3'-6"``, 0.53125 -> ``0'-6 3/8"``."""
    sign = "-" if value_ft < 0 else ""
    total_16ths = round(abs(value_ft) * 12.0 * 16.0)
    feet, rem = divmod(total_16ths, 12 * 16)
    inches, frac16 = divmod(rem, 16)
    if frac16:
        g = math.gcd(frac16, 16)
        text = f'{sign}{feet}\'-{inches} {frac16 // g}/{16 // g}"'
    else:
        text = f"{sign}{feet}'-{inches}\""
    return text


def scale_note_from_ratio(ratio: float) -> str:
    """Detail scale ratio -> drafting note: 16 -> ``3/4" = 1'-0"``, 8 -> ``1 1/2" = 1'-0"``."""
    if ratio <= 0:
        return "NTS"
    six = round((12.0 / ratio) * 16.0)
    whole, frac16 = divmod(six, 16)
    if frac16:
        g = math.gcd(frac16, 16)
        frac = f"{frac16 // g}/{16 // g}"
        num = f"{whole} {frac}" if whole else frac
    else:
        num = str(whole)
    return f'{num}" = 1\'-0"'


def _bad(message: str, **details: Any) -> ValidationError:
    return ValidationError(
        f"{message}; supported detail ops: {', '.join(SUPPORTED_OPS)}",
        supported_ops=list(SUPPORTED_OPS),
        **details,
    )


def _nums(code: str, args: Sequence[Any], n: int) -> list[float]:
    if len(args) < n:
        raise _bad(f"detail op {code!r} expects at least {n} numeric args, got {len(args)}",
                   op=code)
    out: list[float] = []
    for v in args[:n]:
        try:
            out.append(float(v))
        except (TypeError, ValueError) as exc:
            raise _bad(f"detail op {code!r} has non-numeric arg {v!r}", op=code) from exc
    return out


def _parse_op(op: Any) -> tuple[str, list[float], list[Any]]:
    """(code, numeric args, extras) with validation against SUPPORTED_OPS."""
    if not isinstance(op, (list, tuple)) or not op:
        raise _bad(f"detail op must be a non-empty tuple/list, got {op!r}")
    code = str(op[0])
    args = list(op[1:])
    if code in {"l", "d"}:
        nums = _nums(code, args, 4)
        weight = str(args[4]) if len(args) > 4 and args[4] else "normal"
        if weight not in _STROKES:
            raise _bad(f"detail op {code!r} weight must be heavy|light, got {weight!r}", op=code)
        return code, nums, [weight]
    if code in {"r", "h"}:
        return code, _nums(code, args, 4), []
    if code == "c":
        return code, _nums(code, args, 3), []
    if code == "t":
        if len(args) < 4:
            raise _bad(f"detail op 't' expects (x, y, wrap_w, text), got {len(args)} args",
                       op=code)
        return code, _nums(code, args, 3), [str(args[3])]
    if code == "dim":
        nums = _nums(code, args, 4)
        offset = float(args[4]) if len(args) > 4 and args[4] is not None else 0.6
        text = str(args[5]) if len(args) > 5 and args[5] else ""
        return code, nums, [offset, text]
    raise _bad(f"unknown detail op {code!r}", op=code)


def _wrap_label(text: str, wrap_w: float) -> list[str]:
    chars = max(10, round(abs(wrap_w) * _WRAP_CHARS_PER_UNIT))
    return textwrap.wrap(text, width=chars) or [""]


def _dim_geometry(
    nums: list[float], offset: float
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float], float]:
    """((dim p1), (dim p2), (text anchor), length_ft) in feet space (y up)."""
    x1, y1, x2, y2 = nums
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= 0:
        raise _bad("detail op 'dim' has zero length", op="dim")
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    nx, ny = -uy, ux  # left-hand normal in y-up feet space
    a = (x1 + nx * offset, y1 + ny * offset)
    b = (x2 + nx * offset, y2 + ny * offset)
    toff = offset + (0.22 if offset >= 0 else -0.22)
    mid = ((x1 + x2) / 2 + nx * toff, (y1 + y2) / 2 + ny * toff)
    return a, b, mid, length


def render_detail_ops(
    ops: Sequence[Any], *, scale: float = 24.0, title: str = ""
) -> DrawingView:
    """Render one detail op list (local feet, y up) to a ``DrawingView``.

    ``scale``: SVG units per foot. Text renders in screen space (fixed font);
    geometry is scaled and y-flipped. Unknown op codes raise
    :class:`ValidationError` listing the supported vocabulary.
    """
    if scale <= 0:
        raise ValidationError("detail scale must be > 0", scale=scale)
    parsed = [_parse_op(op) for op in ops]
    if not parsed:
        raise _bad("detail needs at least one op")

    # pass 1 — bounds in feet (text/dim extents estimated in feet via scale)
    pts: list[tuple[float, float]] = []
    for code, nums, extras in parsed:
        if code in {"l", "d"}:
            pts += [(nums[0], nums[1]), (nums[2], nums[3])]
        elif code in {"r", "h"}:
            x, y, w, h = nums
            pts += [(x, y), (x + w, y + h)]
        elif code == "c":
            cx, cy, r = nums
            pts += [(cx - r, cy - r), (cx + r, cy + r)]
        elif code == "t":
            x, y, wrap_w = nums
            lines = _wrap_label(str(extras[0]), wrap_w)
            block_w = max(len(ln) for ln in lines) * _FONT * _CHAR_W / scale
            block_h = len(lines) * _LINE_H / scale
            pts += [(x, y + _FONT / scale), (x + block_w, y - block_h)]
        elif code == "dim":
            a, b, mid, _length = _dim_geometry(nums, float(extras[0]))
            pts += [(nums[0], nums[1]), (nums[2], nums[3]), a, b,
                    (mid[0], mid[1] + _FONT / scale), (mid[0], mid[1] - _FONT / scale)]
    minx = min(p[0] for p in pts)
    maxx = max(p[0] for p in pts)
    miny = min(p[1] for p in pts)
    maxy = max(p[1] for p in pts)

    def sx(x: float) -> float:
        return (x - minx) * scale + _MARGIN

    def sy(y: float) -> float:
        return (maxy - y) * scale + _MARGIN

    width = max((maxx - minx) * scale, 1.0) + 2 * _MARGIN
    height = max((maxy - miny) * scale, 1.0) + 2 * _MARGIN

    # pass 2 — render
    parts: list[str] = [
        '<g class="detail-ops" stroke="#111" fill="none" stroke-linecap="square">'
    ]
    for code, nums, extras in parsed:
        if code in {"l", "d"}:
            x1, y1, x2, y2 = nums
            sw = _STROKES[str(extras[0])]
            dash = ' stroke-dasharray="6 4"' if code == "d" else ""
            parts.append(
                f'  <line x1="{fmt(sx(x1))}" y1="{fmt(sy(y1))}" x2="{fmt(sx(x2))}" '
                f'y2="{fmt(sy(y2))}" stroke-width="{fmt(sw)}"{dash}/>'
            )
        elif code == "r":
            x, y, w, h = nums
            parts.append(
                f'  <rect x="{fmt(sx(x))}" y="{fmt(sy(y + h))}" width="{fmt(w * scale)}" '
                f'height="{fmt(h * scale)}" stroke-width="1.2"/>'
            )
        elif code == "c":
            cx, cy, r = nums
            parts.append(
                f'  <circle cx="{fmt(sx(cx))}" cy="{fmt(sy(cy))}" r="{fmt(max(r * scale, 0.8))}" '
                f'stroke-width="1"/>'
            )
        elif code == "h":
            parts.append(_hatch_rect(*nums, sx=sx, sy=sy, scale=scale))
        elif code == "t":
            x, y, _wrap_w = nums
            lines = _wrap_label(str(extras[0]), _wrap_w)
            tx = fmt(sx(x))
            spans = "".join(
                f'<tspan x="{tx}" dy="{fmt(0 if i == 0 else _LINE_H)}">{esc(ln)}</tspan>'
                for i, ln in enumerate(lines)
            )
            parts.append(
                f'  <text x="{tx}" y="{fmt(sy(y))}" font-family="sans-serif" '
                f'font-size="{fmt(_FONT)}" fill="#111" stroke="none">{spans}</text>'
            )
        elif code == "dim":
            parts.append(_dim_svg(nums, float(extras[0]), str(extras[1]), sx=sx, sy=sy))
    parts.append("</g>")
    return DrawingView(width=width, height=height, body="\n".join(parts), title=title)


def _hatch_rect(
    x: float, y: float, w: float, h: float, *, sx: Any, sy: Any, scale: float
) -> str:
    """45-degree hatch lines clipped analytically to the rect (no clipPath ids)."""
    x0, y0 = sx(x), sy(y + h)  # screen top-left
    pw, ph = abs(w) * scale, abs(h) * scale
    lines: list[str] = ['  <g class="hatch" stroke="#666" stroke-width="0.6">']
    o = _HATCH_STEP
    while o < pw + ph:
        # diagonal from bottom/right boundary up-left to left/top boundary
        if o <= pw:
            ax, ay = x0 + o, y0 + ph
        else:
            ax, ay = x0 + pw, y0 + ph - (o - pw)
        if o <= ph:
            bx, by = x0, y0 + ph - o
        else:
            bx, by = x0 + o - ph, y0
        lines.append(
            f'    <line x1="{fmt(ax)}" y1="{fmt(ay)}" x2="{fmt(bx)}" y2="{fmt(by)}"/>'
        )
        o += _HATCH_STEP
    lines.append("  </g>")
    return "\n".join(lines)


def _dim_svg(
    nums: list[float], offset: float, text_override: str, *, sx: Any, sy: Any
) -> str:
    """Dimension: extension lines, dim line with 45-degree ticks, ft-in text."""
    x1, y1, x2, y2 = nums
    a, b, mid, length = _dim_geometry(nums, offset)
    text = text_override or format_feet_inches(length)
    pax, pay, pbx, pby = sx(a[0]), sy(a[1]), sx(b[0]), sy(b[1])
    # screen-space direction along dim line + normal for extension overshoot
    dx, dy = pbx - pax, pby - pay
    dlen = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dlen, dy / dlen
    parts = ['  <g class="dim" stroke="#333" stroke-width="0.8" fill="none">']
    for (px, py), (qx, qy) in (((x1, y1), a), ((x2, y2), b)):
        ex, ey = sx(qx) - sx(px), sy(qy) - sy(py)
        elen = math.hypot(ex, ey) or 1.0
        ox, oy = ex / elen * 4.0, ey / elen * 4.0  # 4 px overshoot past dim line
        parts.append(
            f'    <line x1="{fmt(sx(px))}" y1="{fmt(sy(py))}" '
            f'x2="{fmt(sx(qx) + ox)}" y2="{fmt(sy(qy) + oy)}"/>'
        )
    parts.append(f'    <line x1="{fmt(pax)}" y1="{fmt(pay)}" x2="{fmt(pbx)}" y2="{fmt(pby)}"/>')
    for px, py in ((pax, pay), (pbx, pby)):  # architectural 45-degree ticks
        parts.append(
            f'    <line x1="{fmt(px - 3)}" y1="{fmt(py + 3)}" '
            f'x2="{fmt(px + 3)}" y2="{fmt(py - 3)}" stroke-width="1.2"/>'
        )
    ang = math.degrees(math.atan2(uy, ux))
    if ang > 90.0 or ang <= -90.0:
        ang += 180.0 if ang <= -90.0 else -180.0
    tx, ty = sx(mid[0]), sy(mid[1])
    parts.append(
        f'    <text x="{fmt(tx)}" y="{fmt(ty)}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="{fmt(_FONT)}" fill="#111" stroke="none" '
        f'transform="rotate({fmt(ang)} {fmt(tx)} {fmt(ty)})">{esc(text)}</text>'
    )
    parts.append("  </g>")
    return "\n".join(parts)


def render_detail_sheet(
    details: Sequence[Mapping[str, Any]],
    *,
    width: float = 880.0,
    height: float = 760.0,
    scale: float = 24.0,
    gutter: float = 16.0,
) -> DrawingView:
    """Compose up to four detail dicts ``{id, title, scale, ops}`` 4-up.

    Each cell carries the drafting label ``<ID> — <TITLE>`` plus a scale note
    derived from the detail's ``scale`` ratio (16 -> ``3/4" = 1'-0"``).
    """
    if not details:
        raise _bad("render_detail_sheet needs at least one detail")
    if len(details) > 4:
        raise ValidationError(
            "render_detail_sheet composes at most 4 details per sheet",
            got=len(details),
        )
    cells: list[tuple[DrawingView, str, str]] = []
    for i, det in enumerate(details, start=1):
        ops = det.get("ops")
        if not isinstance(ops, (list, tuple)) or not ops:
            raise _bad(f"detail {det.get('id') or i} has no ops list")
        det_id = str(det.get("id") or f"D{i:02d}")
        det_title = str(det.get("title") or "")
        label = f"{det_id} — {det_title}" if det_title else det_id
        note = scale_note_from_ratio(float(det.get("scale") or 0))
        view = render_detail_ops(ops, scale=scale, title=label)
        cells.append((view, label, note))
    return compose_sheet(cells, width=width, height=height, gutter=gutter)
