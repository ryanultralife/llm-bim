"""Custom SVG providers for INTEC CD sheets (non-model plan geometry).

All diagrams are [ENGINEERING ESTIMATE] schematic — model-projected where
possible, design-basis elsewhere. Coordinates in metres unless noted.
"""

from __future__ import annotations

import html
from typing import Any

import intec_design_basis as basis

# drawing units: mm on sheet (1100×850 title-block area is handled by kernel;
# these views report their own pixel size for fit)


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _mm(m: float) -> float:
    return m * 1000.0


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def _footprint_paths(
    s: dict[str, Any],
    placements: list[dict[str, Any]],
    *,
    ox: float,
    oy: float,
    sc: float,
) -> str:
    """Building + station rectangles in SVG px."""
    parts: list[str] = []
    # main
    parts.append(
        f'<rect x="{ox}" y="{oy - s["bldg_W"] * sc}" width="{s["bldg_L"] * sc}" '
        f'height="{s["bldg_W"] * sc}" fill="none" stroke="#222" stroke-width="2"/>'
    )
    # annex
    ax = ox + s["annex_x0"] * sc
    ay = oy - 0 * sc  # annex is south of y=0
    parts.append(
        f'<rect x="{ax}" y="{oy}" width="{s["annex_L"] * sc}" '
        f'height="{s["annex_D"] * sc}" fill="none" stroke="#555" stroke-width="1.5"/>'
    )
    for pl in placements:
        if pl["id"] in {"STACK"}:
            continue
        x = ox + pl["x"] * sc
        y = oy - (pl["y"] + pl["d"]) * sc
        fill = "#f0c0b0" if pl.get("shielded") else "#c8e6c9"
        if pl["id"] == "CASKBAY":
            fill = "#c8e6c9"
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{pl["w"] * sc:.1f}" '
            f'height="{pl["d"] * sc:.1f}" fill="{fill}" fill-opacity="0.55" '
            f'stroke="#333" stroke-width="0.8"/>'
        )
        cx = x + pl["w"] * sc / 2
        cy = y + pl["d"] * sc / 2
        label = pl["id"]
        fs = max(6, min(10, pl["w"] * sc / len(label) * 1.2))
        parts.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
            f'dominant-baseline="middle" font-size="{fs:.0f}" '
            f'font-family="Segoe UI,Arial,sans-serif" fill="#222">'
            f"{_esc(label)}</text>"
        )
    return "\n".join(parts)


def _wrap_svg(body: str, w: float = 900, h: float = 620, title: str = "") -> str:
    t = (
        f'<text x="20" y="22" font-size="13" font-weight="600" '
        f'font-family="Segoe UI,Arial,sans-serif" fill="#1a237e">{_esc(title)}</text>'
        if title
        else ""
    )
    honesty = (
        f'<text x="20" y="{h - 10}" font-size="8" font-family="Segoe UI,Arial,sans-serif" '
        f'fill="#b71c1c">{_esc(basis.HONESTY[:90])}</text>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">\n'
        f'<rect width="100%" height="100%" fill="#fff"/>\n'
        f"{t}\n{body}\n{honesty}\n</svg>"
    )


def _doc_block(title: str, lines: list[str], *, warn: list[str] | None = None) -> str:
    y = 48
    parts = [
        f'<text x="40" y="{y}" font-size="16" font-weight="700" fill="#1565c0" '
        f'font-family="Segoe UI,Arial,sans-serif">{_esc(title)}</text>'
    ]
    y += 28
    for line in lines:
        # wrap long lines crudely
        chunk = line
        while chunk:
            piece = chunk[:110]
            if len(chunk) > 110:
                sp = piece.rfind(" ")
                if sp > 40:
                    piece = chunk[:sp]
            parts.append(
                f'<text x="40" y="{y}" font-size="11" font-family="Segoe UI,Arial,sans-serif" '
                f'fill="#222">{_esc(piece)}</text>'
            )
            chunk = chunk[len(piece) :].lstrip()
            y += 16
        y += 4
    if warn:
        y += 12
        parts.append(
            f'<text x="40" y="{y}" font-size="13" font-weight="700" fill="#c62828" '
            f'font-family="Segoe UI,Arial,sans-serif">'
            f"ANALYSES NOT YET PERFORMED — DEFERRED TO DS-3</text>"
        )
        y += 22
        for line in warn:
            chunk = line
            while chunk:
                piece = chunk[:100]
                if len(chunk) > 100:
                    sp = piece.rfind(" ")
                    if sp > 40:
                        piece = chunk[:sp]
                parts.append(
                    f'<text x="40" y="{y}" font-size="10" font-family="Segoe UI,Arial,sans-serif" '
                    f'fill="#b71c1c">{_esc(piece)}</text>'
                )
                chunk = chunk[len(piece) :].lstrip()
                y += 14
            y += 4
    return _wrap_svg("\n".join(parts), title="")


# --------------------------------------------------------------------------- #
# public diagram builders                                                      #
# --------------------------------------------------------------------------- #
def zoning_svg() -> str:
    s = basis.build_scalars()
    pl = basis.build_placements()
    sc = 8.0
    ox, oy = 80.0, 80.0 + s["bldg_W"] * sc
    body = [
        '<text x="40" y="36" font-size="14" font-weight="600" fill="#333" '
        'font-family="Segoe UI,Arial,sans-serif">'
        "RADIATION AREA ZONING — overall building (estimate; dose-rate by DS-2)</text>",
        _footprint_paths(s, pl, ox=ox, oy=oy, sc=sc),
        f'<rect x="{ox + 5.5 * sc:.1f}" y="{oy - (2.5 + 19.3) * sc:.1f}" '
        f'width="{36.5 * sc:.1f}" height="{19.3 * sc:.1f}" fill="none" '
        f'stroke="#888" stroke-dasharray="6 4" stroke-width="1.2"/>',
        # legend
        '<rect x="720" y="80" width="22" height="14" fill="#f0c0b0"/>'
        '<text x="750" y="91" font-size="10" font-family="Segoe UI,Arial,sans-serif">'
        "Shielded / R area</text>",
        '<rect x="720" y="104" width="22" height="14" fill="#c8e6c9"/>'
        '<text x="750" y="115" font-size="10" font-family="Segoe UI,Arial,sans-serif">'
        "Occupied / low dose</text>",
    ]
    return _wrap_svg("\n".join(body), w=920, h=640)


def site_plan_svg(*, mode: str = "site") -> str:
    """C-001 site / C-002 grading / C-003 utilities / C-004 duct bank overlays."""
    s = basis.build_scalars()
    pl = basis.build_placements()
    sc = 6.5
    pad = 25.0  # site pad beyond building (m)
    ox = 100.0 + pad * sc
    oy = 70.0 + (s["bldg_W"] + pad) * sc
    site_x = ox - pad * sc
    site_y = oy - (s["bldg_W"] + pad) * sc
    site_w = (s["bldg_L"] + 2 * pad) * sc
    site_h = (s["bldg_W"] + s["annex_D"] + 2 * pad) * sc
    parts = [
        f'<text x="40" y="28" font-size="13" font-weight="600" fill="#333" '
        f'font-family="Segoe UI,Arial,sans-serif">'
        f"SITE PLAN — {mode.upper()} [ENGINEERING ESTIMATE]</text>",
        f'<rect x="{site_x}" y="{site_y}" width="{site_w}" height="{site_h}" '
        f'fill="none" stroke="#999" stroke-dasharray="8 5" stroke-width="1.2"/>',
        _footprint_paths(s, pl, ox=ox, oy=oy, sc=sc),
        # north arrow
        f'<g transform="translate({site_x + site_w - 40},{site_y + 50})">'
        f'<circle r="16" fill="none" stroke="#222"/><line x1="0" y1="10" x2="0" y2="-12" '
        f'stroke="#222"/><polygon points="0,-16 -5,-4 5,-4" fill="#222"/>'
        f'<text y="-22" text-anchor="middle" font-size="10">N</text></g>',
        # scale bar 0..20 m
        f'<g transform="translate(80,{site_y + site_h + 30})">'
        f'<line x1="0" y1="0" x2="{20 * sc}" y2="0" stroke="#222" stroke-width="2"/>'
        f'<line x1="0" y1="-4" x2="0" y2="4" stroke="#222"/>'
        f'<line x1="{20 * sc}" y1="-4" x2="{20 * sc}" y2="4" stroke="#222"/>'
        f'<text x="0" y="16" font-size="9">0</text>'
        f'<text x="{20 * sc}" y="16" text-anchor="end" font-size="9">20 m</text></g>',
    ]
    if mode == "site":
        # cask route
        parts.append(
            f'<line x1="{ox - 10 * sc}" y1="{oy + 5 * sc}" '
            f'x2="{ox + 20 * sc}" y2="{oy + 5 * sc}" stroke="#00bcd4" '
            f'stroke-width="2" stroke-dasharray="6 3" marker-end="url(#arr)"/>'
            f'<text x="{ox - 10 * sc}" y="{oy + 4 * sc}" font-size="9" fill="#00838f">'
            f"cask laydown pad → cask route</text>"
        )
    elif mode == "grading":
        for i, elev in enumerate((1487.9, 1487.6, 1487.3, 1487.0)):
            yy = site_y + site_h * (i + 1) / 5
            parts.append(
                f'<line x1="{site_x}" y1="{yy}" x2="{site_x + site_w}" y2="{yy}" '
                f'stroke="#4caf50" stroke-width="1.2"/>'
                f'<text x="{site_x + site_w + 6}" y="{yy + 3}" font-size="9" '
                f'fill="#2e7d32">{elev}</text>'
            )
        parts.append(
            f'<circle cx="{site_x + 20}" cy="{site_y + site_h - 20}" r="5" '
            f'fill="none" stroke="#0288d1" stroke-width="1.5"/>'
            f'<text x="{site_x + 30}" y="{site_y + site_h - 16}" font-size="9" '
            f'fill="#0277bd">storm sump</text>'
        )
    elif mode == "utilities":
        labels = [
            ("comms / fiber", "#4caf50"),
            ("sanitary", "#e53935"),
            ("process water", "#1e88e5"),
            ("13.8 kV power", "#f9a825"),
        ]
        for i, (lab, col) in enumerate(labels):
            yy = oy - 8 * sc + i * 18
            parts.append(
                f'<line x1="{site_x}" y1="{yy}" x2="{ox}" y2="{yy}" '
                f'stroke="{col}" stroke-width="2.5"/>'
                f'<circle cx="{site_x}" cy="{yy}" r="4" fill="{col}"/>'
                f'<text x="{site_x + 6}" y="{yy - 4}" font-size="9" fill="{col}">'
                f"{_esc(lab)}</text>"
            )
    elif mode == "ductbank":
        # magenta yard / buried runs
        mid_y = oy - s["bldg_W"] * sc / 2
        parts.append(
            f'<line x1="{ox + 5 * sc}" y1="{mid_y}" x2="{ox + 40 * sc}" y2="{mid_y}" '
            f'stroke="#c2185b" stroke-width="3"/>'
        )
        for x in (8, 15, 22, 29, 36):
            parts.append(
                f'<line x1="{ox + x * sc}" y1="{oy + 5 * sc}" '
                f'x2="{ox + x * sc}" y2="{oy - s["bldg_W"] * sc + 5 * sc}" '
                f'stroke="#c2185b" stroke-width="2"/>'
            )
        parts.append(
            f'<text x="{site_x}" y="{mid_y}" font-size="9" fill="#ad1457">'
            f"duct bank / buried feeder</text>"
        )
    notes = {
        "site": "Building footprint PROJECTED from model. Cask pad + haul route are civil design basis.",
        "grading": "Finished contours + storm sump are schematic; survey + SWPPP by DS-2.",
        "utilities": "Incoming services tie to W face; sizing + easements by utility co. / DS-2.",
        "ductbank": "Buried PWR/CWR/DRN services schematic; yard duct bank civil design basis.",
    }
    parts.append(
        f'<text x="40" y="600" font-size="9" fill="#c62828" font-family="Segoe UI,Arial,sans-serif">'
        f"GENERAL NOTES: {_esc(notes.get(mode, ''))}</text>"
    )
    return _wrap_svg("\n".join(parts), w=920, h=640)


def sequence_svg() -> str:
    phases = basis.construction_phases()
    w0, w1 = 0, 40
    left, top = 200.0, 70.0
    bar_h, row_h = 18.0, 36.0
    chart_w = 620.0
    parts = [
        '<text x="40" y="36" font-size="14" font-weight="600" fill="#333" '
        'font-family="Segoe UI,Arial,sans-serif">'
        "CONSTRUCTION SEQUENCE — SP-1..SP-10</text>",
        '<text x="40" y="54" font-size="9" fill="#f9a825" font-family="Segoe UI,Arial,sans-serif">'
        "Construction subtotal ~$59.4M (Class 4-5). SP-5 remote handling is critical path.</text>",
    ]
    for wk in range(0, 41, 4):
        x = left + (wk - w0) / (w1 - w0) * chart_w
        parts.append(
            f'<line x1="{x}" y1="{top - 10}" x2="{x}" y2="{top + len(phases) * row_h}" '
            f'stroke="#eee" stroke-width="1"/>'
            f'<text x="{x}" y="{top - 14}" text-anchor="middle" font-size="9" fill="#888">W{wk}</text>'
        )
    for i, ph in enumerate(phases):
        y = top + i * row_h
        x = left + (ph["w0"] - w0) / (w1 - w0) * chart_w
        bw = (ph["w1"] - ph["w0"]) / (w1 - w0) * chart_w
        col = "#00bcd4" if ph.get("critical") else "#1565c0"
        dash = ' stroke-dasharray="4 2"' if ph.get("critical") else ""
        parts.append(
            f'<text x="40" y="{y + 14}" font-size="10" font-family="Segoe UI,Arial,sans-serif">'
            f'{_esc(ph["id"])} {_esc(ph["name"])}</text>'
            f'<rect x="{x}" y="{y}" width="{bw}" height="{bar_h}" fill="none" '
            f'stroke="{col}" stroke-width="2"{dash}/>'
            f'<text x="{x + bw + 6}" y="{y + 13}" font-size="9" fill="#f9a825">'
            f'${ph["cost_m"]}M'
            f'{" — CRITICAL PATH" if ph.get("critical") else ""}</text>'
        )
    return _wrap_svg("\n".join(parts), w=980, h=520)


def foundation_svg() -> str:
    s = basis.build_scalars()
    sc = 9.0
    ox, oy = 80.0, 80.0 + s["bldg_W"] * sc
    parts = [
        f'<text x="40" y="32" font-size="13" font-weight="600" '
        f'font-family="Segoe UI,Arial,sans-serif">'
        f"FOUNDATION / MAT PLAN — {s['slab_t']} m slab; {s['footing_sq_m']} m sq. footings; "
        f"equipment pads (shaded)</text>",
        f'<rect x="{ox}" y="{oy - s["bldg_W"] * sc}" width="{s["bldg_L"] * sc}" '
        f'height="{s["bldg_W"] * sc}" fill="none" stroke="#222" stroke-width="2"/>',
    ]
    # column grid ~8 m
    xs = list(range(0, int(s["bldg_L"]) + 1, 8))
    if xs[-1] != int(s["bldg_L"]):
        xs.append(int(s["bldg_L"]))
    ys = list(range(0, int(s["bldg_W"]) + 1, 7))
    if ys[-1] != int(s["bldg_W"]):
        ys.append(int(s["bldg_W"]))
    fs = s["footing_sq_m"] * sc * 0.35
    for x in xs:
        for y in ys:
            cx = ox + x * sc
            cy = oy - y * sc
            parts.append(
                f'<rect x="{cx - fs / 2}" y="{cy - fs / 2}" width="{fs}" height="{fs}" '
                f'fill="none" stroke="#1565c0" stroke-width="1.2"/>'
            )
    # equipment pads (ebeam, cells, annex zones)
    for pl in basis.build_placements():
        if pl["kind"] in {"ebeam", "cell", "uncask", "box"} and pl.get("shielded"):
            x = ox + pl["x"] * sc
            y = oy - (pl["y"] + pl["d"]) * sc
            parts.append(
                f'<rect x="{x}" y="{y}" width="{pl["w"] * sc}" height="{pl["d"] * sc}" '
                f'fill="#bbdefb" fill-opacity="0.7" stroke="#1565c0" stroke-width="1"/>'
            )
    parts.append(
        f'<text x="{ox + s["bldg_L"] * sc / 2}" y="{oy + 24}" text-anchor="middle" '
        f'font-size="11">{s["bldg_L"]:.0f} m</text>'
        f'<text x="{ox - 18}" y="{oy - s["bldg_W"] * sc / 2}" text-anchor="middle" '
        f'font-size="11" transform="rotate(-90 {ox - 18} {oy - s["bldg_W"] * sc / 2})">'
        f'{s["bldg_W"]:.0f} m</text>'
    )
    return _wrap_svg("\n".join(parts), w=900, h=560)


def framing_svg(*, roof: bool = False) -> str:
    s = basis.build_scalars()
    sc = 10.0
    ox, oy = 70.0, 60.0 + s["bldg_W"] * sc
    parts = [
        f'<text x="40" y="28" font-size="13" font-weight="600" '
        f'font-family="Segoe UI,Arial,sans-serif">'
        f'{"ROOF" if roof else "GROUND-FLOOR"} FRAMING PLAN — W14 columns / W18 beams'
        f'{"" if not roof else " / W24 crane runways"}</text>',
        f'<rect x="{ox}" y="{oy - s["bldg_W"] * sc}" width="{s["bldg_L"] * sc}" '
        f'height="{s["bldg_W"] * sc}" fill="none" stroke="#999" stroke-width="1"/>',
    ]
    xs = list(range(0, int(s["bldg_L"]) + 1, 8))
    if xs[-1] != s["bldg_L"]:
        xs.append(int(s["bldg_L"]))
    ys = [0, 7, 14, 21, 28, 35]
    ys = [y for y in ys if y <= s["bldg_W"]]
    if ys[-1] != s["bldg_W"]:
        ys.append(s["bldg_W"])
    for y in ys:
        parts.append(
            f'<line x1="{ox}" y1="{oy - y * sc}" x2="{ox + s["bldg_L"] * sc}" '
            f'y2="{oy - y * sc}" stroke="#1565c0" stroke-width="2.5"/>'
        )
    for x in xs:
        for y in ys:
            parts.append(
                f'<rect x="{ox + x * sc - 3}" y="{oy - y * sc - 3}" width="6" height="6" '
                f'fill="#0d47a1"/>'
            )
    if roof:
        # crane runways along tunnel long edges
        for y in (2.5, 2.5 + 19.3):
            parts.append(
                f'<line x1="{ox + 5.5 * sc}" y1="{oy - y * sc}" '
                f'x2="{ox + 42 * sc}" y2="{oy - y * sc}" stroke="#6a1b9a" stroke-width="3"/>'
            )
    # steel table
    parts.append(
        '<g transform="translate(620,80)">'
        '<text font-size="11" font-weight="600">STEEL (this sheet)</text>'
        '<rect y="8" width="160" height="70" fill="none" stroke="#222"/>'
        '<text y="28" x="8" font-size="10">W14x90  · columns</text>'
        '<text y="46" x="8" font-size="10">W18x50  · roof beams</text>'
        '<text y="64" x="8" font-size="10">W24x84  · crane runway</text></g>'
    )
    return _wrap_svg("\n".join(parts), w=900, h=520)


def pfd_svg() -> str:
    steps = [
        ("CASK RECEIPT", "#90caf9"),
        ("UNCASK", "#ef9a9a"),
        ("DECLAD / SHEAR", "#ef9a9a"),
        ("E-BEAM HUB", "#ce93d8"),
        ("SEP CELLS ×6", "#ffcc80"),
        ("DOWN-BLEND", "#ffcc80"),
        ("PRODUCT CASK", "#a5d6a7"),
        ("WASTE PKG", "#bcaaa4"),
    ]
    parts = [
        '<text x="40" y="36" font-size="14" font-weight="600" '
        'font-family="Segoe UI,Arial,sans-serif">'
        "PROCESS FLOW DIAGRAM — receipt → separation → product / waste</text>"
    ]
    x, y = 40.0, 100.0
    for i, (name, col) in enumerate(steps):
        parts.append(
            f'<rect x="{x}" y="{y}" width="100" height="48" rx="4" fill="{col}" '
            f'stroke="#333" stroke-width="1"/>'
            f'<text x="{x + 50}" y="{y + 28}" text-anchor="middle" font-size="9" '
            f'font-family="Segoe UI,Arial,sans-serif">{_esc(name)}</text>'
        )
        if i < len(steps) - 1:
            parts.append(
                f'<line x1="{x + 100}" y1="{y + 24}" x2="{x + 120}" y2="{y + 24}" '
                f'stroke="#333" stroke-width="1.5" marker-end="url(#a)"/>'
            )
        x += 120
        if x > 800:
            x = 40
            y += 90
    parts.append(
        '<text x="40" y="280" font-size="10" fill="#555" font-family="Segoe UI,Arial,sans-serif">'
        "Services: vacuum · CW · process gas · off-gas/HEPA · power · I&amp;C "
        "(see P-002 P&amp;IDs and line list)</text>"
        '<text x="40" y="300" font-size="10" fill="#b71c1c">'
        "SECURITY: vessels are black-box envelopes — no drive enabling detail.</text>"
    )
    return _wrap_svg("\n".join(parts), w=980, h=400)


def one_line_svg() -> str:
    s = basis.build_scalars()
    parts = [
        f'<text x="40" y="36" font-size="14" font-weight="600" '
        f'font-family="Segoe UI,Arial,sans-serif">'
        f"ELECTRICAL ONE-LINE — {s['service_kv']} kV / ~{s['service_mw']} MW "
        f"(coincident estimate)</text>",
        # utility
        f'<rect x="400" y="60" width="120" height="36" fill="none" stroke="#f9a825" stroke-width="2"/>'
        f'<text x="460" y="82" text-anchor="middle" font-size="11">UTILITY {s["service_kv"]} kV</text>',
        '<line x1="460" y1="96" x2="460" y2="130" stroke="#333" stroke-width="2"/>',
        '<rect x="380" y="130" width="160" height="40" fill="none" stroke="#333" stroke-width="2"/>'
        '<text x="460" y="154" text-anchor="middle" font-size="11">MAIN XFMR / SWGR</text>',
        '<line x1="460" y1="170" x2="460" y2="210" stroke="#333" stroke-width="2"/>',
        '<line x1="120" y1="210" x2="800" y2="210" stroke="#333" stroke-width="2"/>',
    ]
    loads = [
        (160, "MCC-PROC", "Separators / e-beam"),
        (320, "MCC-BOP", "HVAC / CW / pumps"),
        (480, "MCC-RH", "Remote handling"),
        (640, "LP/EP", "Lighting / standby"),
        (780, "G-1", "Standby generator"),
    ]
    for x, tag, note in loads:
        parts.append(
            f'<line x1="{x}" y1="210" x2="{x}" y2="250" stroke="#333"/>'
            f'<rect x="{x - 50}" y="250" width="100" height="36" fill="none" stroke="#1565c0"/>'
            f'<text x="{x}" y="272" text-anchor="middle" font-size="10">{_esc(tag)}</text>'
            f'<text x="{x}" y="310" text-anchor="middle" font-size="8" fill="#666">{_esc(note)}</text>'
        )
    parts.append(
        '<text x="40" y="360" font-size="10" fill="#b71c1c">'
        "[ENGINEERING ESTIMATE] — service vs coincident load by DS-2; see E-008.</text>"
    )
    return _wrap_svg("\n".join(parts), w=920, h=420)


def vent_cascade_svg() -> str:
    zones = [
        ("C3 HOT CELLS", "#ef9a9a", "−125 Pa"),
        ("C2 PROCESS", "#ffcc80", "−62 Pa"),
        ("C1 SUPPORT", "#fff59d", "−25 Pa"),
        ("HEPA TRAIN", "#90caf9", "2-stage"),
        ("STACK", "#b0bec5", "elevated"),
    ]
    parts = [
        '<text x="40" y="36" font-size="14" font-weight="600">'
        "CONFINEMENT VENTILATION CASCADE</text>"
    ]
    x = 40.0
    for name, col, note in zones:
        parts.append(
            f'<rect x="{x}" y="100" width="140" height="70" rx="4" fill="{col}" stroke="#333"/>'
            f'<text x="{x + 70}" y="130" text-anchor="middle" font-size="11" font-weight="600">'
            f"{_esc(name)}</text>"
            f'<text x="{x + 70}" y="150" text-anchor="middle" font-size="10">{_esc(note)}</text>'
        )
        if name != "STACK":
            parts.append(
                f'<line x1="{x + 140}" y1="135" x2="{x + 160}" y2="135" stroke="#333" '
                f'stroke-width="2"/>'
            )
        x += 160
    parts.append(
        '<text x="40" y="220" font-size="10" fill="#555">'
        "Cascade dP design basis [ENGINEERING ESTIMATE]; balance calc deferred (DOE-HDBK-1169).</text>"
    )
    return _wrap_svg("\n".join(parts), w=900, h=300)


def material_flow_svg() -> str:
    parts = [
        '<text x="40" y="36" font-size="14" font-weight="600">'
        "CASK &amp; MATERIAL-HANDLING FLOW</text>",
        # main flow
        '<rect x="40" y="80" width="100" height="40" fill="#90caf9" stroke="#333"/>'
        '<text x="90" y="104" text-anchor="middle" font-size="10">CASK IN</text>',
        '<line x1="140" y1="100" x2="180" y2="100" stroke="#333" stroke-width="2"/>',
        '<rect x="180" y="80" width="100" height="40" fill="#ef9a9a" stroke="#333"/>'
        '<text x="230" y="104" text-anchor="middle" font-size="10">UNCASK</text>',
        '<line x1="280" y1="100" x2="320" y2="100" stroke="#333" stroke-width="2"/>',
        '<rect x="320" y="80" width="100" height="40" fill="#ef9a9a" stroke="#333"/>'
        '<text x="370" y="104" text-anchor="middle" font-size="10">DECLAD</text>',
        # fork
        '<line x1="420" y1="100" x2="480" y2="60" stroke="#2e7d32" stroke-width="2"/>',
        '<line x1="420" y1="100" x2="480" y2="140" stroke="#6d4c41" stroke-width="2"/>',
        '<rect x="480" y="40" width="120" height="40" fill="#a5d6a7" stroke="#333"/>'
        '<text x="540" y="64" text-anchor="middle" font-size="10">PRODUCT → CASKING</text>',
        '<rect x="480" y="120" width="120" height="40" fill="#bcaaa4" stroke="#333"/>'
        '<text x="540" y="144" text-anchor="middle" font-size="10">CLAD → WASTE</text>',
        '<text x="40" y="220" font-size="10" fill="#555">'
        "Fissile never recurses through cascade (N-012). Hub inventory ≤20 kg-U basis.</text>",
    ]
    return _wrap_svg("\n".join(parts), w=720, h=280)


def section_cover_svg(discipline: str, title: str) -> str:
    counts = basis.discipline_counts()
    n = counts.get(discipline, 0)
    body = f"""
    <text x="450" y="200" text-anchor="middle" font-size="28" font-weight="700"
          font-family="Segoe UI,Arial,sans-serif" fill="#1a237e">{_esc(title)}</text>
    <text x="450" y="240" text-anchor="middle" font-size="14" fill="#555"
          font-family="Segoe UI,Arial,sans-serif">Discipline { _esc(discipline) } · {n} sheets</text>
    <rect x="250" y="280" width="400" height="80" fill="none" stroke="#90caf9" stroke-width="1.5"/>
    <text x="450" y="315" text-anchor="middle" font-size="12" fill="#1565c0">
      CONSTRUCTION DOCUMENTS — MB-INT-CAD-001</text>
    <text x="450" y="340" text-anchor="middle" font-size="11" fill="#666">
      {_esc(basis.PROJECT_NAME)}</text>
    <text x="450" y="420" text-anchor="middle" font-size="10" fill="#b71c1c">
      {_esc(basis.HONESTY[:100])}</text>
    """
    return _wrap_svg(body, w=900, h=520)


def index_table_svg() -> str:
    counts = basis.discipline_counts()
    labels = {
        "G": "General",
        "C": "Civil / Site",
        "S": "Structural",
        "EQ": "Station Equipment",
        "A": "Architectural",
        "N": "Nuclear / Shielding / Confinement",
        "H": "HVAC / Confinement Ventilation",
        "P": "Process & Piping",
        "E": "Electrical",
        "I": "Instrumentation & Control",
        "F": "Fire Protection",
        "L": "Logistics / Material Handling",
        "LS": "Life Safety",
    }
    parts = [
        '<text x="40" y="36" font-size="14" font-weight="600">'
        "DRAWING INDEX — full register (MB-INT-CAD-001)</text>",
        '<rect x="40" y="50" width="700" height="28" fill="#e3f2fd"/>',
        '<text x="50" y="68" font-size="11" font-weight="600">Disc</text>',
        '<text x="120" y="68" font-size="11" font-weight="600">Discipline</text>',
        '<text x="680" y="68" font-size="11" font-weight="600">Sheets</text>',
    ]
    y = 78
    total = 0
    for disc, label in labels.items():
        n = counts.get(disc, 0)
        total += n
        parts.append(
            f'<line x1="40" y1="{y}" x2="740" y2="{y}" stroke="#eee"/>'
            f'<text x="50" y="{y + 16}" font-size="11">{_esc(disc)}</text>'
            f'<text x="120" y="{y + 16}" font-size="11">{_esc(label)}</text>'
            f'<text x="700" y="{y + 16}" font-size="11" text-anchor="end">{n}</text>'
        )
        y += 24
    parts.append(
        f'<line x1="40" y1="{y}" x2="740" y2="{y}" stroke="#333"/>'
        f'<text x="120" y="{y + 18}" font-size="12" font-weight="600">total</text>'
        f'<text x="700" y="{y + 18}" font-size="12" font-weight="600" text-anchor="end">'
        f"{total}</text>"
    )
    return _wrap_svg("\n".join(parts), w=800, h=y + 60)


def notes_svg() -> str:
    return _doc_block(
        "GENERAL NOTES",
        basis.general_notes()
        + ["", "ABBREVIATIONS", basis.abbreviations()],
        warn=basis.deferred_analyses(),
    )


def code_summary_svg() -> str:
    return _doc_block("CODE SUMMARY & DESIGN BASIS", basis.code_summary())


def doc_text_sheet(title: str, paragraphs: list[str]) -> str:
    return _doc_block(title, paragraphs)


def hall_crop_m() -> tuple[float, float, float, float]:
    """Separator hall crop in mm for A-002 / A-010."""
    # tunnel + cells region
    return (_mm(4.0), _mm(2.0), _mm(42.0), _mm(24.0))


def annex_crop_m() -> tuple[float, float, float, float]:
    return (_mm(0.0), _mm(-12.0), _mm(48.0), _mm(2.0))


def full_crop_m() -> tuple[float, float, float, float]:
    s = basis.build_scalars()
    return (_mm(-2.0), _mm(-s["annex_D"] - 2), _mm(s["bldg_L"] + 8), _mm(s["bldg_W"] + 4))
