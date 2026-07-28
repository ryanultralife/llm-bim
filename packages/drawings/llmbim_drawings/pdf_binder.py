"""Multi-page PDF plot binder from SVG construction/part sheets.

Pure-Python PDF 1.4: draws extracted SVG primitives (line, rect, polygon,
circle, text) so plot sets open without Cairo/ReportLab.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

# Typographic characters the drawing engine emits that a WinAnsi PDF font
# cannot show — fold to ASCII so they don't render as "?" mojibake.
_UNI_ASCII = {
    "—": "-", "–": "-", "‒": "-", "−": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "′": "'", "″": '"',
    "·": ".", "•": "*", "…": "...",
    "→": "->", "←": "<-", "⇒": "=>",
    "×": "x", "÷": "/", "°": "deg",
    "²": "2", "³": "3", "½": "1/2", "¼": "1/4",
    "¾": "3/4", "⅓": "1/3", "⅔": "2/3",
    "≤": "<=", "≥": ">=", "≈": "~", "±": "+/-",
    "ℓ": "L", "µ": "u", "μ": "u",
    " ": " ", " ": " ", " ": " ", " ": " ",
}


def _pdf_escape(s: str) -> str:
    for u, a in _UNI_ASCII.items():
        if u in s:
            s = s.replace(u, a)
    # anything still non-Latin-1 would corrupt the stream — drop to '?'
    s = s.encode("cp1252", "replace").decode("cp1252")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _num(value: str | None, base: float = 0.0) -> float:
    """Parse an SVG length. Handles ``100%`` (of ``base``) and unit suffixes
    (``10px``, ``2.5pt``) that a bare ``float()`` chokes on — a single such
    attribute used to fail the whole sheet ("Failed to render")."""
    if value is None:
        return 0.0
    v = str(value).strip()
    if not v:
        return 0.0
    if v.endswith("%"):
        try:
            return float(v[:-1]) * base / 100.0
        except ValueError:
            return 0.0
    m = re.match(r"^\s*(-?\d*\.?\d+)", v)
    return float(m.group(1)) if m else 0.0


_PATH_TOK = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")


def _path_construct(
    d: str, mapx: Callable[[float], float], mapy: Callable[[float], float]
) -> list[str]:
    """Translate an SVG path ``d`` into PDF path-construction ops (m/l/c/h).

    Handles M/L/H/V/C/S/Q/Z (abs + rel); the drawing engine emits paths for
    footings, stems, slab outlines and revision clouds. Without this the whole
    <path> element was dropped from the PDF, so foundation/framing plans (and
    any path-based custom sheet) rendered blank. Arcs (A) are skipped.
    """
    # each token is ("c", command_letter) or ("n", number)
    items: list[tuple[str, Any]] = []
    for c, n in _PATH_TOK.findall(d or ""):
        if c:
            items.append(("c", c))
        elif n:
            items.append(("n", float(n)))
    ops: list[str] = []
    i = 0
    cx = cy = sx0 = sy0 = 0.0
    px = py = 0.0  # last control reflection point
    cmd = ""
    started = False

    def take(k: int) -> list[float]:
        nonlocal i
        out: list[float] = []
        while len(out) < k and i < len(items) and items[i][0] == "n":
            out.append(float(items[i][1]))
            i += 1
        return out

    n_items = len(items)
    while i < n_items:
        if items[i][0] == "c":
            cmd = str(items[i][1])
            i += 1
        rel = cmd.islower()
        C = cmd.upper()
        if C == "M":
            v = take(2)
            if len(v) < 2:
                break
            cx, cy = (cx + v[0], cy + v[1]) if rel else (v[0], v[1])
            sx0, sy0 = cx, cy
            ops.append(f"{mapx(cx):.2f} {mapy(cy):.2f} m")
            started = True
            cmd = "l" if rel else "L"       # subsequent pairs are lineto
        elif C == "L":
            v = take(2)
            if len(v) < 2:
                break
            cx, cy = (cx + v[0], cy + v[1]) if rel else (v[0], v[1])
            ops.append(f"{mapx(cx):.2f} {mapy(cy):.2f} l")
        elif C == "H":
            v = take(1)
            if not v:
                break
            cx = cx + v[0] if rel else v[0]
            ops.append(f"{mapx(cx):.2f} {mapy(cy):.2f} l")
        elif C == "V":
            v = take(1)
            if not v:
                break
            cy = cy + v[0] if rel else v[0]
            ops.append(f"{mapx(cx):.2f} {mapy(cy):.2f} l")
        elif C in ("C", "S", "Q"):
            k = 6 if C == "C" else 4
            v = take(k)
            if len(v) < k:
                break
            pts = []
            for j in range(0, k, 2):
                ax = cx + v[j] if rel else v[j]
                ay = cy + v[j + 1] if rel else v[j + 1]
                pts.append((ax, ay))
            if C == "C":
                (c1x, c1y), (c2x, c2y), (ex, ey) = pts
            elif C == "Q":  # quadratic → cubic
                (qx, qy), (ex, ey) = pts
                c1x, c1y = cx + 2 / 3 * (qx - cx), cy + 2 / 3 * (qy - cy)
                c2x, c2y = ex + 2 / 3 * (qx - ex), ey + 2 / 3 * (qy - ey)
            else:  # S: smooth cubic, reflect prev control
                (c2x, c2y), (ex, ey) = pts
                c1x, c1y = 2 * cx - px, 2 * cy - py
            ops.append(
                f"{mapx(c1x):.2f} {mapy(c1y):.2f} {mapx(c2x):.2f} "
                f"{mapy(c2y):.2f} {mapx(ex):.2f} {mapy(ey):.2f} c"
            )
            px, py = c2x, c2y
            cx, cy = ex, ey
        elif C == "Z":
            ops.append("h")
            cx, cy = sx0, sy0
        elif C == "A":
            # Elliptical arc → polyline (door swings, bubbles). Residual #3.
            v = take(7)
            if len(v) < 7:
                break
            import math as _math

            rx, ry = abs(v[0]) or 1e-6, abs(v[1]) or 1e-6
            x_rot = _math.radians(v[2])
            large = int(v[3]) != 0
            sweep = int(v[4]) != 0
            ex = cx + v[5] if rel else v[5]
            ey = cy + v[6] if rel else v[6]
            # Endpoint-parameterized arc approximation (W3C SVG impl notes simplified)
            dx = (cx - ex) / 2.0
            dy = (cy - ey) / 2.0
            cos_phi, sin_phi = _math.cos(x_rot), _math.sin(x_rot)
            x1p = cos_phi * dx + sin_phi * dy
            y1p = -sin_phi * dx + cos_phi * dy
            rx = max(rx, abs(x1p))
            ry = max(ry, abs(y1p))
            sq = max(
                0.0,
                (rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p)
                / max(rx * rx * y1p * y1p + ry * ry * x1p * x1p, 1e-12),
            )
            coef = _math.sqrt(sq)
            if large == sweep:
                coef = -coef
            cxp = coef * (rx * y1p / ry)
            cyp = coef * (-ry * x1p / rx)
            cx_arc = cos_phi * cxp - sin_phi * cyp + (cx + ex) / 2.0
            cy_arc = sin_phi * cxp + cos_phi * cyp + (cy + ey) / 2.0

            def _angle(ux: float, uy: float, vx: float, vy: float) -> float:
                n = _math.hypot(ux, uy) * _math.hypot(vx, vy)
                if n < 1e-12:
                    return 0.0
                c = max(-1.0, min(1.0, (ux * vx + uy * vy) / n))
                ang = _math.acos(c)
                if ux * vy - uy * vx < 0:
                    ang = -ang
                return ang

            th1 = _angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
            dth = _angle(
                (x1p - cxp) / rx,
                (y1p - cyp) / ry,
                (-x1p - cxp) / rx,
                (-y1p - cyp) / ry,
            )
            if not sweep and dth > 0:
                dth -= 2 * _math.pi
            elif sweep and dth < 0:
                dth += 2 * _math.pi
            n_seg = max(4, int(abs(dth) / ( _math.pi / 8)) + 1)
            for k in range(1, n_seg + 1):
                th = th1 + dth * k / n_seg
                cos_th, sin_th = _math.cos(th), _math.sin(th)
                xx = cos_phi * rx * cos_th - sin_phi * ry * sin_th + cx_arc
                yy = sin_phi * rx * cos_th + cos_phi * ry * sin_th + cy_arc
                ops.append(f"{mapx(xx):.2f} {mapy(yy):.2f} l")
            cx, cy = ex, ey
        else:
            i += 1
    return ops if started else []


# Page sizes in PDF points (1 pt = 1/72"). Landscape (width x height).
_PAGE_A4_LAND = (842.0, 595.0)       # metric default
_PAGE_ANSI_B_LAND = (1224.0, 792.0)  # 17" x 11" — imperial construction sets
_PAGE_ARCH_D_LAND = (2592.0, 1728.0)  # 36" x 24"


def _hex_rgb(color: str | None) -> tuple[float, float, float] | None:
    """Parse #rgb / #rrggbb (and named none-skips) to 0–1 RGB."""
    if not color:
        return None
    c = color.strip().lower()
    if c in ("none", "transparent"):
        return None
    if c.startswith("rgb"):
        m = re.search(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", c)
        if m:
            return int(m.group(1)) / 255.0, int(m.group(2)) / 255.0, int(m.group(3)) / 255.0
        return None
    if c.startswith("#"):
        h = c[1:]
        if len(h) == 3:
            r, g, b = int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16)
            return r / 255.0, g / 255.0, b / 255.0
        if len(h) == 6:
            return int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
    named = {
        "black": (0.0, 0.0, 0.0),
        "white": (1.0, 1.0, 1.0),
        "red": (1.0, 0.0, 0.0),
        "gray": (0.5, 0.5, 0.5),
        "grey": (0.5, 0.5, 0.5),
    }
    return named.get(c)


def _pdf_color_ops(color: str | None, *, stroke: bool) -> list[str]:
    rgb = _hex_rgb(color)
    if rgb is None:
        rgb = (0.0, 0.0, 0.0) if stroke else (0.85, 0.85, 0.9)
    op = "RG" if stroke else "rg"
    return [f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} {op}"]


def _stroke_style_ops(el: ET.Element, sx: float) -> list[str]:
    """stroke-width → PDF ``w``; stroke-dasharray → ``d`` (residual #3)."""
    out: list[str] = []
    sw = el.get("stroke-width")
    if sw is not None and str(sw).strip() not in ("", "none"):
        # Keep a visible minimum so hairlines don't vanish when scaled down
        w = max(0.25, _num(sw) * sx)
        out.append(f"{w:.2f} w")
    dash = el.get("stroke-dasharray")
    if dash and dash not in ("none",):
        dl = [f"{_num(t) * sx:.2f}" for t in re.split(r"[\s,]+", dash) if t]
        if dl:
            out.append(f"[{' '.join(dl)}] 0 d")
    else:
        out.append("[] 0 d")  # solid (reset after prior dashed siblings)
    return out


def _parse_svg_drawing(
    svg_path: Path,
    *,
    page_w: float = 842.0,
    page_h: float = 595.0,
) -> tuple[float, float, list[str]]:
    """Return (width, height, PDF content stream operators)."""
    text = svg_path.read_text(encoding="utf-8", errors="replace")
    # viewBox
    vb = re.search(r'viewBox="([^"]+)"', text)
    if vb:
        parts = [float(x) for x in vb.group(1).replace(",", " ").split()]
        if len(parts) == 4:
            _vx, _vy, vw, vh = parts
        else:
            vw, vh = 1100.0, 850.0
    else:
        vw, vh = 1100.0, 850.0

    margin = 36.0
    usable_w, usable_h = page_w - 2 * margin, page_h - 2 * margin
    s = min(usable_w / max(vw, 1), usable_h / max(vh, 1))
    # PDF y-up: flip
    ops: list[str] = []
    ops.append("q")
    ops.append(f"1 0 0 1 {margin} {margin} cm")
    ops.append(f"{s} 0 0 {s} 0 0 cm")
    # flip Y around view height
    ops.append(f"1 0 0 -1 0 {vh} cm")

    try:
        # strip default ns for easier find
        text_ns = re.sub(r'\sxmlns="[^"]+"', "", text, count=1)
        root = ET.fromstring(text_ns)
    except ET.ParseError:
        ops.append("Q")
        return page_w, page_h, ops

    def walk(el: ET.Element, xform: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)) -> None:
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        # Compose transform="translate(a,b) scale(s)". Previously only translate
        # was honored, so any view scaled to fit a sheet (scale(s<1)) drew at full
        # size and overflowed the page. Track (tx,ty,sx,sy) and map local (x,y) to
        # page as X = tx + x*sx, Y = ty + y*sy.
        tx, ty, sx, sy = xform
        tr = el.get("transform") or ""
        mt = re.search(r"translate\(([^,]+),?\s*([^)]*)\)", tr)
        if mt:
            tx += float(mt.group(1)) * sx
            ty += float(mt.group(2) or 0) * sy
        msx = re.search(r"scale\(([^,)]+),?\s*([^)]*)\)", tr)
        if msx:
            s1 = float(msx.group(1))
            s2 = float(msx.group(2)) if msx.group(2) else s1
            sx *= s1
            sy *= s2

        def mapx(v: float) -> float:
            return tx + v * sx

        def mapy(v: float) -> float:
            return ty + v * sy

        fill = el.get("fill")
        stroke = el.get("stroke")
        # default black stroke for lines
        if tag == "line":
            x1 = mapx(_num(el.get("x1"), vw))
            y1 = mapy(_num(el.get("y1"), vh))
            x2 = mapx(_num(el.get("x2"), vw))
            y2 = mapy(_num(el.get("y2"), vh))
            ops.append("q")
            ops.extend(_stroke_style_ops(el, sx))
            ops.extend(_pdf_color_ops(stroke or "#000", stroke=True))
            ops.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")
            ops.append("Q")
        elif tag == "rect":
            x = mapx(_num(el.get("x"), vw))
            y = mapy(_num(el.get("y"), vh))
            w = _num(el.get("width"), vw) * sx
            h = _num(el.get("height"), vh) * sy
            has_fill = bool(fill and fill not in ("none",))
            has_stroke = stroke is None or stroke not in ("none",)
            ops.append("q")
            ops.extend(_stroke_style_ops(el, sx))
            if has_fill:
                ops.extend(_pdf_color_ops(fill, stroke=False))
                ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
            if has_stroke:
                ops.extend(_pdf_color_ops(stroke or "#000", stroke=True))
                ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re S")
            ops.append("Q")
        elif tag == "polygon":
            pts = el.get("points", "").strip()
            pairs = []
            for tok in re.split(r"[\s,]+", pts):
                if tok:
                    try:
                        pairs.append(float(tok))
                    except ValueError:
                        pass
            if len(pairs) >= 4:
                has_fill = bool(fill and fill not in ("none",))
                has_stroke = stroke is None or stroke not in ("none",)
                ops.append("q")
                ops.extend(_stroke_style_ops(el, sx))
                if has_fill:
                    ops.extend(_pdf_color_ops(fill, stroke=False))
                else:
                    ops.append("1 1 1 rg")
                ops.extend(_pdf_color_ops(stroke or "#000", stroke=True))
                ops.append(f"{mapx(pairs[0]):.2f} {mapy(pairs[1]):.2f} m")
                for i in range(2, len(pairs), 2):
                    ops.append(f"{mapx(pairs[i]):.2f} {mapy(pairs[i+1]):.2f} l")
                paint = "h B" if has_fill else "h S"
                ops.append(paint)
                ops.append("Q")
        elif tag == "circle":
            import math as _math

            cx = mapx(_num(el.get("cx"), vw))
            cy = mapy(_num(el.get("cy"), vh))
            r = _num(el.get("r"), vw) * sx
            has_fill = bool(fill and fill not in ("none",))
            ops.append("q")
            ops.extend(_stroke_style_ops(el, sx))
            if has_fill:
                ops.extend(_pdf_color_ops(fill, stroke=False))
            ops.extend(_pdf_color_ops(stroke or "#000", stroke=True))
            n = 16
            for i in range(n):
                a0 = 2 * _math.pi * i / n
                a1 = 2 * _math.pi * (i + 1) / n
                x0 = cx + r * _math.cos(a0)
                y0 = cy + r * _math.sin(a0)
                x1 = cx + r * _math.cos(a1)
                y1 = cy + r * _math.sin(a1)
                if i == 0:
                    ops.append(f"{x0:.2f} {y0:.2f} m")
                ops.append(f"{x1:.2f} {y1:.2f} l")
            ops.append("h B" if has_fill else "h S")
            ops.append("Q")
        elif tag == "path":
            pops = _path_construct(el.get("d") or "", mapx, mapy)
            if pops:
                has_fill = bool(fill and fill not in ("none",))
                has_stroke = bool(stroke and stroke not in ("none",))
                if not has_fill and not has_stroke:
                    has_stroke = True   # default: outline
                ops.append("q")
                ops.extend(_stroke_style_ops(el, sx))
                if has_fill:
                    ops.extend(_pdf_color_ops(fill, stroke=False))
                if has_stroke:
                    ops.extend(_pdf_color_ops(stroke or "#000", stroke=True))
                ops.extend(pops)
                paint = "B" if (has_fill and has_stroke) else ("f" if has_fill else "S")
                ops.append(paint)
                ops.append("Q")
        elif tag == "text":
            x = mapx(_num(el.get("x"), vw))
            y = mapy(_num(el.get("y"), vh))
            content = (el.text or "").strip()[:80]
            if content:
                # Honor the SVG font-size (was fixed 9, so titles and fine
                # print all came out the same size), clamped to a sane range.
                _fsa = el.get("font-size")
                fs = max(3.5, min(28.0, (_num(_fsa) if _fsa else 9.0) * sx))
                # Honor text-anchor: the binder used to left-anchor everything,
                # so centered dimensions were shifted right and right-aligned
                # datum labels ran past the drawing edge.
                anchor = el.get("text-anchor", "start")
                tw = len(content) * fs * 0.5   # Helvetica avg advance ~0.5 em
                if anchor == "middle":
                    x -= tw / 2.0
                elif anchor == "end":
                    x -= tw
                # PDF text unflipped: temporarily invert
                ops.append("q")
                ops.append(f"1 0 0 -1 0 {2*y:.2f} cm")  # local flip for text
                ops.append(f"BT /F1 {fs:.1f} Tf")
                ops.extend(_pdf_color_ops(fill or stroke or "#000", stroke=False))
                ops.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm")
                ops.append(f"({_pdf_escape(content)}) Tj")
                ops.append("ET")
                ops.append("Q")

        for child in el:
            walk(child, (tx, ty, sx, sy))

    walk(root)
    ops.append("Q")
    return page_w, page_h, ops


def _build_pdf(pages: list[tuple[float, float, list[str]]]) -> bytes:
    """Assemble PDF bytes from page content operators."""
    objects: list[bytes] = []

    def add_obj(data: bytes) -> int:
        objects.append(data)
        return len(objects)

    # 1: catalog
    # 2: pages
    # 3: font
    font_id = 3
    add_obj(b"<< /Type /Catalog /Pages 2 0 R >>")
    # placeholder for pages
    add_obj(b"<< /Type /Pages /Kids [] /Count 0 >>")
    add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids: list[int] = []
    for w, h, ops in pages:
        stream = "\n".join(ops).encode("latin-1", errors="replace")
        # uncompressed for simplicity
        content = (
            f"<< /Length {len(stream)} >>\nstream\n".encode()
            + stream
            + b"\nendstream"
        )
        cid = add_obj(content)
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] "
            f"/Contents {cid} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        ).encode()
        page_ids.append(add_obj(page))

    # fix pages object
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()

    # write xref
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode()
        out += obj
        out += b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects)+1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)


def _order_sheets_from_index(
    d: Path, sheets: list[Path]
) -> tuple[list[Path], list[tuple[str, str]]]:
    """Order SVG files by SHEET_INDEX.json; return (paths, cover labels).

    Cover labels are ``(sheet_no, title)`` for human-readable rows
    (residual #10). Falls back to filename-only labels when index missing.
    """
    import json

    by_name = {s.name: s for s in sheets}
    idx_path = d / "SHEET_INDEX.json"
    if not idx_path.is_file() and d.name != "construction":
        # pack root → construction/SHEET_INDEX.json
        alt = d / "construction" / "SHEET_INDEX.json"
        if alt.is_file():
            idx_path = alt
            d = alt.parent
            by_name = {s.name: s for s in d.glob("*.svg")}
    ordered: list[Path] = []
    labels: list[tuple[str, str]] = []
    if idx_path.is_file():
        try:
            data = json.loads(idx_path.read_text(encoding="utf-8"))
            for row in data.get("sheets") or []:
                fname = str(row.get("file") or "")
                no = str(row.get("no") or "")
                title = str(row.get("title") or fname)
                path = by_name.get(fname) or (d / fname if fname else None)
                if path and Path(path).is_file():
                    ordered.append(Path(path))
                    labels.append((no or Path(path).stem, title))
        except Exception:  # noqa: BLE001
            ordered = []
            labels = []
    if not ordered:
        ordered = sorted(sheets)
        labels = [(s.stem, s.name) for s in ordered]
    else:
        # append any SVGs not listed in the index (extras) after the register
        seen = {p.resolve() for p in ordered}
        for s in sorted(sheets):
            if s.resolve() not in seen:
                ordered.append(s)
                labels.append((s.stem, s.name))
    return ordered, labels


def _detect_page_size(
    sheet_dir: Path,
    *,
    page_size: str | None,
    units: str | None,
) -> tuple[float, float, str]:
    """Pick MediaBox. Imperial construction packs → ANSI B landscape (residual #5)."""
    if page_size:
        key = page_size.strip().lower().replace(" ", "_")
        mapping = {
            "a4": _PAGE_A4_LAND,
            "a4_landscape": _PAGE_A4_LAND,
            "ansi_b": _PAGE_ANSI_B_LAND,
            "ansi-b": _PAGE_ANSI_B_LAND,
            "b": _PAGE_ANSI_B_LAND,
            "arch_d": _PAGE_ARCH_D_LAND,
            "arch-d": _PAGE_ARCH_D_LAND,
            "d": _PAGE_ARCH_D_LAND,
        }
        if key in mapping:
            w, h = mapping[key]
            return w, h, key
    u = (units or "").lower()
    if u in {"imperial", "us", "ft"}:
        return (*_PAGE_ANSI_B_LAND, "ansi_b")
    # sniff SHEET_INDEX / a sample sheet for imperial scale notes
    idx = sheet_dir / "SHEET_INDEX.json"
    sample = ""
    if idx.is_file():
        sample = idx.read_text(encoding="utf-8", errors="replace")[:4000]
    if not sample:
        for svg in list(sheet_dir.glob("*.svg"))[:3]:
            sample += svg.read_text(encoding="utf-8", errors="replace")[:1500]
    if "1/4" in sample or "1'-0" in sample or "imperial" in sample.lower() or "ft" in sample:
        return (*_PAGE_ANSI_B_LAND, "ansi_b")
    return (*_PAGE_A4_LAND, "a4")


def export_pdf_binder(
    sheet_dir: str | Path,
    path: str | Path,
    *,
    pattern: str = "*.svg",
    title: str = "LLM-BIM Plot Set",
    page_size: str | None = None,
    units: str | None = None,
) -> Path:
    """Build multi-page PDF from SVG sheets in a directory.

    Order: ``SHEET_INDEX.json`` when present (residual #10), else sorted glob.
    Cover rows use ``NO — TITLE`` not raw filenames.
    Page size: A4 landscape (metric) or ANSI B landscape (imperial) (residual #5).
    Stroke widths, dashes on ``<line>``, per-element fills, and path arcs are
    honored (residual #3).
    """
    d = Path(sheet_dir)
    sheets = sorted(d.glob(pattern))
    if not sheets:
        # also search one level
        sheets = sorted(d.rglob(pattern))
        # prefer construction/ or drawings/
        pref = [s for s in sheets if "construction" in str(s) or "drawings" in str(s)]
        sheets = pref or sheets

    sheets, labels = _order_sheets_from_index(d, sheets)
    page_w, page_h, size_name = _detect_page_size(d, page_size=page_size, units=units)

    pages: list[tuple[float, float, list[str]]] = []
    # cover — title y scaled to page height
    title_y = page_h - 80
    cover_ops = [
        f"BT /F1 24 Tf 50 {title_y:.0f} Td (LLM-BIM Plot Binder) Tj ET",
        f"BT /F1 14 Tf 50 {title_y - 40:.0f} Td ({_pdf_escape(title)[:60]}) Tj ET",
        f"BT /F1 10 Tf 50 {title_y - 70:.0f} Td "
        f"(ENGINEERING ESTIMATE - agent-derived plot set | page {size_name}) Tj ET",
    ]
    y = title_y - 100
    for i, (s, (no, sheet_title)) in enumerate(
        zip(sheets[:40], labels[:40], strict=False), start=1
    ):
        row = f"{i:02d}  {no} - {sheet_title}"
        # drop if label was already the filename
        if no == s.stem and sheet_title == s.name:
            row = f"{i:02d}  {s.name}"
        cover_ops.append(
            f"BT /F1 10 Tf 50 {y:.0f} Td ({_pdf_escape(row)[:70]}) Tj ET"
        )
        y -= 14
        if y < 40:
            break
    pages.append((page_w, page_h, cover_ops))

    for s in sheets[:40]:
        try:
            pages.append(_parse_svg_drawing(s, page_w=page_w, page_h=page_h))
        except Exception:
            pages.append(
                (
                    page_w,
                    page_h,
                    [
                        f"BT /F1 12 Tf 50 400 Td "
                        f"(Failed to render {_pdf_escape(s.name)}) Tj ET"
                    ],
                )
            )

    pdf = _build_pdf(pages)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(pdf)
    return p
