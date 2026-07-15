"""Multi-page PDF plot binder from SVG construction/part sheets.

Pure-Python PDF 1.4: draws extracted SVG primitives (line, rect, polygon,
circle, text) so plot sets open without Cairo/ReportLab.
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET


def _pdf_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _parse_svg_drawing(svg_path: Path) -> tuple[float, float, list[str]]:
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

    # Scale SVG units to fit A4 landscape points (842 x 595)
    page_w, page_h = 842.0, 595.0
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

    def walk(el: ET.Element, xform: tuple[float, float] = (0.0, 0.0)) -> None:
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        # crude translate from transform="translate(a,b)"
        tx, ty = xform
        tr = el.get("transform") or ""
        m = re.search(r"translate\(([^,]+),?\s*([^)]*)\)", tr)
        if m:
            tx += float(m.group(1))
            ty += float(m.group(2) or 0)

        stroke = el.get("stroke")
        fill = el.get("fill")
        # default black stroke for lines
        if tag == "line":
            x1 = float(el.get("x1", 0)) + tx
            y1 = float(el.get("y1", 0)) + ty
            x2 = float(el.get("x2", 0)) + tx
            y2 = float(el.get("y2", 0)) + ty
            ops.append("0 0 0 RG")
            ops.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")
        elif tag == "rect":
            x = float(el.get("x", 0)) + tx
            y = float(el.get("y", 0)) + ty
            w = float(el.get("width", 0))
            h = float(el.get("height", 0))
            if fill and fill not in ("none",):
                ops.append("0.9 0.9 0.95 rg")
                ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
            ops.append("0 0 0 RG")
            ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re S")
        elif tag == "polygon":
            pts = el.get("points", "").strip()
            pairs = []
            for tok in re.split(r"[\s,]+", pts):
                if tok:
                    pairs.append(float(tok))
            if len(pairs) >= 4:
                ops.append("0.8 0.8 0.85 rg")
                ops.append("0 0 0 RG")
                ops.append(f"{pairs[0]+tx:.2f} {pairs[1]+ty:.2f} m")
                for i in range(2, len(pairs), 2):
                    ops.append(f"{pairs[i]+tx:.2f} {pairs[i+1]+ty:.2f} l")
                ops.append("h B")
        elif tag == "circle":
            cx = float(el.get("cx", 0)) + tx
            cy = float(el.get("cy", 0)) + ty
            r = float(el.get("r", 0))
            # approximate circle with 4 bezier-ish lines (octagon)
            ops.append("0 0 0 RG")
            n = 16
            for i in range(n):
                a0 = 2 * 3.14159265 * i / n
                a1 = 2 * 3.14159265 * (i + 1) / n
                x0 = cx + r * __import__("math").cos(a0)
                y0 = cy + r * __import__("math").sin(a0)
                x1 = cx + r * __import__("math").cos(a1)
                y1 = cy + r * __import__("math").sin(a1)
                if i == 0:
                    ops.append(f"{x0:.2f} {y0:.2f} m")
                ops.append(f"{x1:.2f} {y1:.2f} l")
            ops.append("h S")
        elif tag == "text":
            x = float(el.get("x", 0)) + tx
            y = float(el.get("y", 0)) + ty
            content = (el.text or "").strip()
            if content:
                # PDF text unflipped: temporarily invert
                ops.append("q")
                ops.append(f"1 0 0 -1 0 {2*y:.2f} cm")  # local flip for text
                ops.append("BT /F1 9 Tf")
                ops.append(f"0 0 0 rg")
                ops.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm")
                ops.append(f"({_pdf_escape(content[:80])}) Tj")
                ops.append("ET")
                ops.append("Q")

        for child in el:
            walk(child, (tx, ty))

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


def export_pdf_binder(
    sheet_dir: str | Path,
    path: str | Path,
    *,
    pattern: str = "*.svg",
    title: str = "LLM-BIM Plot Set",
) -> Path:
    """Build multi-page PDF from SVG sheets in a directory (sorted)."""
    d = Path(sheet_dir)
    sheets = sorted(d.glob(pattern))
    if not sheets:
        # also search one level
        sheets = sorted(d.rglob(pattern))
        # prefer construction/ or drawings/
        pref = [s for s in sheets if "construction" in str(s) or "drawings" in str(s)]
        sheets = pref or sheets

    pages: list[tuple[float, float, list[str]]] = []
    # cover
    cover_ops = [
        "BT /F1 24 Tf 50 500 Td (LLM-BIM Plot Binder) Tj ET",
        f"BT /F1 14 Tf 50 460 Td ({_pdf_escape(title)[:60]}) Tj ET",
        "BT /F1 10 Tf 50 430 Td (ENGINEERING ESTIMATE - agent-derived plot set) Tj ET",
    ]
    y = 400
    for i, s in enumerate(sheets[:40], start=1):
        cover_ops.append(
            f"BT /F1 10 Tf 50 {y} Td ({i:02d}  {_pdf_escape(s.name)[:50]}) Tj ET"
        )
        y -= 14
    pages.append((842.0, 595.0, cover_ops))

    for s in sheets[:40]:
        try:
            pages.append(_parse_svg_drawing(s))
        except Exception:
            pages.append(
                (
                    842.0,
                    595.0,
                    [f"BT /F1 12 Tf 50 400 Td (Failed to render { _pdf_escape(s.name) }) Tj ET"],
                )
            )

    pdf = _build_pdf(pages)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(pdf)
    return p
