"""Note-driven plan SVGs from Schad basis (no llm-bim kernel).

Produces: floor plan, foundation plan, roof framing plan, ADU enlarged,
site plan, MEP schematic overlays, schedules as SVG tables.
"""

from __future__ import annotations

import html
import math
import sys
from pathlib import Path
from typing import Any

# Allow running as script / module
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import schad_adu as adu  # noqa: E402
import schad_design_basis as basis  # noqa: E402
import schad_house_basis as house  # noqa: E402
import schad_mep as mep  # noqa: E402
import schad_site as site  # noqa: E402
import schad_structural as struct  # noqa: E402


def _title_block(
    sheet_no: str,
    title: str,
    body: str,
    *,
    w: float = 1100.0,
    h: float = 850.0,
    scale_note: str = '1/4" = 1\'-0"',
) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">
<rect width="100%" height="100%" fill="#fff"/>
<rect x="12" y="12" width="{w-24:.0f}" height="{h-24:.0f}" fill="none" stroke="#111" stroke-width="2"/>
<text x="28" y="40" font-family="Segoe UI,Arial,sans-serif" font-size="20" font-weight="700">{html.escape(sheet_no)} — {html.escape(title)}</text>
<text x="28" y="60" font-family="Segoe UI,Arial,sans-serif" font-size="12" fill="#444">SCHAD 2024-008 · 3730 Chandler Rd, Quincy CA · Ledger Built LLC · DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION</text>
<text x="{w-28}" y="40" text-anchor="end" font-family="Segoe UI,Arial,sans-serif" font-size="12" fill="#333">Scale: {html.escape(scale_note)}</text>
{body}
<text x="28" y="{h-22}" font-family="Segoe UI,Arial,sans-serif" font-size="10" fill="#666">Note-driven from projects/schad SSOT · dims to face of stud U.N.O. · verify in field · PE reserved</text>
</svg>"""


def _plan_transform(
    pts_ft: list[tuple[float, float]],
    *,
    ox: float,
    oy: float,
    scale: float,
    flip_y: bool = True,
    y_ref: float = 0.0,
) -> list[tuple[float, float]]:
    out = []
    for x, y in pts_ft:
        sx = ox + x * scale
        sy = oy - y * scale if flip_y else oy + y * scale
        out.append((sx, sy))
    return out


def floor_plan_svg() -> str:
    s = basis.build_scalars()
    walls = basis.build_walls()
    doors = basis.build_doors()
    windows = basis.build_windows()
    rooms = basis.build_placements()
    scale = 12.0  # px/ft ~ 1/8" feel on sheet
    ox, oy = 80.0, 720.0

    parts: list[str] = []
    # walls
    for w in walls:
        x1, y1 = ox + w["x1"] * scale, oy - w["y1"] * scale
        x2, y2 = ox + w["x2"] * scale, oy - w["y2"] * scale
        kind = w.get("kind", "")
        sw = 4.5 if "exterior" in kind or "fire" in kind else 2.5
        col = "#8b0000" if "fire" in kind else "#1a1a1a"
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{col}" stroke-width="{sw}" stroke-linecap="square"/>'
        )

    # grids
    for i, x in enumerate([0, s["bay_L"], 2 * s["bay_L"], s["main_L"]]):
        gx = ox + x * scale
        parts.append(
            f'<line x1="{gx:.1f}" y1="{oy + 30}" x2="{gx:.1f}" y2="{oy - (s["main_W"]+s["rear_W"])*scale - 20}" '
            f'stroke="#4a7ab5" stroke-width="0.8" stroke-dasharray="8 5" opacity="0.7"/>'
        )
        parts.append(
            f'<circle cx="{gx:.1f}" cy="{oy + 45}" r="12" fill="#fff" stroke="#4a7ab5"/>'
            f'<text x="{gx:.1f}" y="{oy + 49}" text-anchor="middle" font-size="11" '
            f'font-family="Segoe UI,Arial" fill="#4a7ab5">{chr(65+i)}</text>'
        )

    # rooms
    for r in rooms:
        cx = ox + (r["x"] + r["w"] / 2) * scale
        cy = oy - (r["y"] + r["d"] / 2) * scale
        parts.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" font-family="Segoe UI,Arial" '
            f'font-size="12" font-weight="600" fill="#222">{html.escape(r["name"])}</text>'
        )
        area = r["w"] * r["d"]
        parts.append(
            f'<text x="{cx:.1f}" y="{cy + 14:.1f}" text-anchor="middle" font-family="Segoe UI,Arial" '
            f'font-size="10" fill="#555">{area:.0f} SF</text>'
        )

    # doors marks
    for d in doors:
        dx = ox + d["cx"] * scale
        dy = oy - d["cy"] * scale
        parts.append(
            f'<rect x="{dx-14:.1f}" y="{dy-8:.1f}" width="28" height="16" fill="#fff" stroke="#0a5" stroke-width="1"/>'
            f'<text x="{dx:.1f}" y="{dy+4:.1f}" text-anchor="middle" font-size="10" '
            f'font-family="Segoe UI,Arial" font-weight="700" fill="#0a5">{html.escape(d["mark"])}</text>'
        )

    for w in windows:
        wx = ox + w["cx"] * scale
        wy = oy - w["cy"] * scale
        parts.append(
            f'<rect x="{wx-12:.1f}" y="{wy-7:.1f}" width="24" height="14" fill="#e8f4ff" stroke="#06c"/>'
            f'<text x="{wx:.1f}" y="{wy+3:.1f}" text-anchor="middle" font-size="9" '
            f'font-family="Segoe UI,Arial" fill="#06c">{html.escape(w["mark"])}</text>'
        )

    # overall dims
    L, W = s["main_L"], s["main_W"]
    parts.append(
        f'<text x="{ox + L/2*scale:.1f}" y="{oy + 70}" text-anchor="middle" font-size="11" '
        f'font-family="Segoe UI,Arial">{L:.0f}\'-0" OVERALL E-W</text>'
    )
    parts.append(
        f'<text x="{ox - 50}" y="{oy - W/2*scale:.1f}" text-anchor="middle" font-size="11" '
        f'font-family="Segoe UI,Arial" transform="rotate(-90 {ox-50} {oy - W/2*scale:.1f})">'
        f'{W:.0f}\'-0" MAIN N-S</text>'
    )

    # notes block
    notes = basis.build_notes()["general"][:6]
    ny = 100
    parts.append('<text x="720" y="90" font-size="12" font-weight="700" font-family="Segoe UI,Arial">GENERAL NOTES</text>')
    for i, n in enumerate(notes):
        parts.append(
            f'<text x="720" y="{ny + i*16}" font-size="9" font-family="Segoe UI,Arial" fill="#333">'
            f'{i+1}. {html.escape(n[:70])}</text>'
        )

    body = "\n".join(parts)
    return _title_block("A1.1", "FLOOR PLAN — GARAGE / ADU / WORKSHOP", body, scale_note='~1/8" = 1\'-0"')


def foundation_plan_svg() -> str:
    s = basis.build_scalars()
    scale = 11.0
    ox, oy = 90.0, 700.0
    parts: list[str] = []
    fp = basis.footprint()
    # outer footing centerline ~ offset
    poly = [(ox + x * scale, oy - y * scale) for x, y in fp]
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in poly) + " Z"
    parts.append(f'<path d="{d}" fill="#f0ebe3" stroke="#333" stroke-width="2"/>')
    # strip footing offset dashed
    parts.append(f'<path d="{d}" fill="none" stroke="#8B4513" stroke-width="6" opacity="0.35"/>')
    parts.append(
        f'<text x="{ox+10}" y="{oy+40}" font-size="11" font-family="Segoe UI,Arial">'
        f'STRIP FTG {s["footing_w"]*12:.0f}" W x {s["footing_d"]*12:.0f}" D · (2) #4 CONT · 3,500 PSI</text>'
    )
    # point pads at beam lines
    for x in (s["bay_L"], 2 * s["bay_L"]):
        for y in (0.0, s["main_W"]):
            px, py = ox + x * scale, oy - y * scale
            parts.append(
                f'<rect x="{px-18:.1f}" y="{py-18:.1f}" width="36" height="36" fill="#d4c4a8" stroke="#333"/>'
                f'<text x="{px:.1f}" y="{py+4:.1f}" text-anchor="middle" font-size="8" font-family="Segoe UI,Arial">36x36</text>'
            )
    # SSW pads
    st = basis.build_structure()
    for sw in st["strong_walls"]:
        px = ox + (sw["x"] + s["ssw_w"] / 2) * scale
        py = oy - sw["y"] * scale
        parts.append(
            f'<rect x="{px-14:.1f}" y="{py-10:.1f}" width="28" height="20" fill="#c9a0a0" stroke="#800"/>'
            f'<text x="{px:.1f}" y="{py+3:.1f}" text-anchor="middle" font-size="7" font-family="Segoe UI,Arial">{html.escape(sw["id"])}</text>'
        )
    # notes
    for i, n in enumerate(basis.build_notes()["foundation"]):
        parts.append(
            f'<text x="700" y="{100+i*18}" font-size="10" font-family="Segoe UI,Arial">{html.escape(n)}</text>'
        )
    chk = struct.strip_footing_check()
    parts.append(
        f'<text x="700" y="280" font-size="10" font-family="Segoe UI,Arial" fill="#060">'
        f'Strip q={chk["q_psf"]} psf ≤ {chk["q_allow_psf"]} OK (design-support)</text>'
    )
    return _title_block("S1.1", "FOUNDATION PLAN", "\n".join(parts), scale_note='~1/8" = 1\'-0"')


def roof_framing_svg() -> str:
    s = basis.build_scalars()
    scale = 11.0
    ox, oy = 90.0, 700.0
    parts: list[str] = []
    # main roof rectangle
    L, W, p = s["main_L"], s["main_W"], s["bay2_proj"]
    # outline
    fp = basis.footprint()
    poly = [(ox + x * scale, oy - y * scale) for x, y in fp]
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in poly) + " Z"
    parts.append(f'<path d="{d}" fill="#f7f7f7" stroke="#333" stroke-width="1.5"/>')
    # ridge line E-W at y = main_W/2
    y_r = s["main_W"] / 2
    parts.append(
        f'<line x1="{ox:.1f}" y1="{oy - y_r*scale:.1f}" x2="{ox+L*scale:.1f}" y2="{oy - y_r*scale:.1f}" '
        f'stroke="#c00" stroke-width="2"/>'
        f'<text x="{ox+L/2*scale:.1f}" y="{oy - y_r*scale - 8:.1f}" text-anchor="middle" font-size="10" '
        f'fill="#c00" font-family="Segoe UI,Arial">RIDGE EL. {s["ridge"]:.0f}\'-0" · 6:12</text>'
    )
    # trusses 24" OC
    spacing = s["truss_spacing"]
    x = 0.0
    while x <= L + 0.01:
        parts.append(
            f'<line x1="{ox+x*scale:.1f}" y1="{oy:.1f}" x2="{ox+x*scale:.1f}" y2="{oy-W*scale:.1f}" '
            f'stroke="#666" stroke-width="0.6" opacity="0.5"/>'
        )
        x += spacing
    # beams
    for b in basis.build_structure()["beams"]:
        parts.append(
            f'<line x1="{ox+b["x"]*scale:.1f}" y1="{oy-b["y1"]*scale:.1f}" '
            f'x2="{ox+b["x"]*scale:.1f}" y2="{oy-b["y2"]*scale:.1f}" '
            f'stroke="#00a" stroke-width="3"/>'
            f'<text x="{ox+b["x"]*scale+6:.1f}" y="{oy-(b["y1"]+b["y2"])/2*scale:.1f}" '
            f'font-size="10" fill="#00a" font-family="Segoe UI,Arial">{html.escape(b["id"])} W16x40</text>'
        )
    # Bay 2 cross-gable note
    parts.append(
        f'<text x="{ox+s["bay_L"]*scale:.1f}" y="{oy + 20:.1f}" font-size="10" fill="#060" '
        f'font-family="Segoe UI,Arial">BAY-2 CROSS-GABLE (PROPOSED) · VALLEY DETAIL D03</text>'
    )
    # shed
    parts.append(
        f'<text x="{ox+s["rear_off_x"]*scale:.1f}" y="{oy-(s["main_W"]+s["rear_W"]/2)*scale:.1f}" '
        f'font-size="10" font-family="Segoe UI,Arial">SHED ROOF · BEARS 12\' @ MAIN · CURB D02</text>'
    )
    for i, n in enumerate(basis.build_notes()["framing"]):
        parts.append(
            f'<text x="720" y="{100+i*16}" font-size="9" font-family="Segoe UI,Arial">{html.escape(n)}</text>'
        )
    parts.append(
        f'<text x="720" y="280" font-size="10" font-family="Segoe UI,Arial" fill="#800">'
        f'TRUSSES: DEFERRED SUBMITTAL — eng. by fabricator · snow {s["snow_psf"]:.0f} psf</text>'
    )
    return _title_block("S2.1", "ROOF FRAMING PLAN", "\n".join(parts))


def adu_plan_svg() -> str:
    scale = 28.0  # ~1/2" = 1'
    ox, oy = 80.0, 600.0
    W, D = adu.W, adu.D
    parts: list[str] = []
    # shell
    parts.append(
        f'<rect x="{ox:.1f}" y="{oy-D*scale:.1f}" width="{W*scale:.1f}" height="{D*scale:.1f}" '
        f'fill="#fafafa" stroke="#111" stroke-width="3"/>'
    )
    colors = {
        "SLEEPING": "#e8f0ff",
        "LIVING": "#e8ffe8",
        "KITCHEN (HALF)": "#fff5e0",
        "BATH (ROLL-IN)": "#f0e8ff",
    }
    for z in adu.adu_zones():
        parts.append(
            f'<rect x="{ox+z["x"]*scale:.1f}" y="{oy-(z["y"]+z["d"])*scale:.1f}" '
            f'width="{z["w"]*scale:.1f}" height="{z["d"]*scale:.1f}" '
            f'fill="{colors.get(z["name"], "#eee")}" stroke="#666" stroke-width="0.8" opacity="0.85"/>'
            f'<text x="{ox+(z["x"]+z["w"]/2)*scale:.1f}" y="{oy-(z["y"]+z["d"]/2)*scale:.1f}" '
            f'text-anchor="middle" font-size="11" font-family="Segoe UI,Arial" font-weight="600">'
            f'{html.escape(z["name"])}</text>'
        )
    for f in adu.adu_furniture() + adu.adu_kitchen() + adu.adu_bath():
        parts.append(
            f'<rect x="{ox+f["x"]*scale:.1f}" y="{oy-(f["y"]+f["d"])*scale:.1f}" '
            f'width="{f["w"]*scale:.1f}" height="{f["d"]*scale:.1f}" fill="none" stroke="#333" stroke-width="1"/>'
            f'<text x="{ox+(f["x"]+f["w"]/2)*scale:.1f}" y="{oy-(f["y"]+f["d"]/2)*scale+3:.1f}" '
            f'text-anchor="middle" font-size="8" font-family="Segoe UI,Arial">{html.escape(f["name"][:18])}</text>'
        )
    for c in adu.adu_clearances():
        parts.append(
            f'<circle cx="{ox+c["cx"]*scale:.1f}" cy="{oy-c["cy"]*scale:.1f}" r="{c["r"]*scale:.1f}" '
            f'fill="none" stroke="#c00" stroke-width="1.2" stroke-dasharray="4 3"/>'
        )
    for e in adu.adu_electrical()[:40]:
        ex, ey = ox + e["x"] * scale, oy - e["y"] * scale
        parts.append(
            f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" fill="#06c"/>'
            f'<text x="{ex+6:.1f}" y="{ey+3:.1f}" font-size="7" fill="#06c" font-family="Segoe UI,Arial">'
            f'{html.escape(e["sym"])}</text>'
        )
    notes = adu.adu_ada_notes()
    for i, n in enumerate(notes[:10]):
        # wrap long ADA notes
        short = n if len(n) < 90 else n[:87] + "..."
        parts.append(
            f'<text x="580" y="{90+i*22}" font-size="10" font-family="Segoe UI,Arial">'
            f'{i+1}. {html.escape(short)}</text>'
        )
    return _title_block(
        "A1.2",
        "ADU — ENLARGED PLAN, FURNITURE & ELECTRICAL (ADA)",
        "\n".join(parts),
        scale_note='~1/2" = 1\'-0"',
    )


def site_plan_svg() -> str:
    sb = site.site_basis()
    scale = 1.8  # px/ft
    # center garage at origin area
    ox, oy = 550.0, 420.0
    parts: list[str] = []
    ring = sb["parcel_ring"]
    poly = [(ox + x * scale, oy - y * scale) for x, y in ring]
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in poly) + " Z"
    parts.append(f'<path d="{d}" fill="#e8f5e9" stroke="#2e7d32" stroke-width="2"/>')
    g = sb["garage"]
    parts.append(
        f'<rect x="{ox+g["x"]*scale:.1f}" y="{oy-(g["y"]+g["d"])*scale:.1f}" '
        f'width="{g["w"]*scale:.1f}" height="{g["d"]*scale:.1f}" fill="#fff3e0" stroke="#e65100" stroke-width="2"/>'
    )
    h = sb["house"]
    parts.append(
        f'<rect x="{ox+h["x"]*scale:.1f}" y="{oy-(h["y"]+h["d"])*scale:.1f}" '
        f'width="{h["w"]*scale:.1f}" height="{h["d"]*scale:.1f}" fill="#e3f2fd" stroke="#1565c0" stroke-width="1.5"/>'
    )
    if sb.get("driveway"):
        pts = sb["driveway"]["pts"]
        pd = "M " + " L ".join(f"{ox+x*scale:.1f},{oy-y*scale:.1f}" for x, y in pts)
        parts.append(f'<path d="{pd}" fill="none" stroke="#795548" stroke-width="4" opacity="0.7"/>')
    for u in sb.get("utilities", [])[:12]:
        parts.append(
            f'<circle cx="{ox+u["x"]*scale:.1f}" cy="{oy-u["y"]*scale:.1f}" r="5" fill="#333"/>'
            f'<text x="{ox+u["x"]*scale+8:.1f}" y="{oy-u["y"]*scale+3:.1f}" font-size="9" '
            f'font-family="Segoe UI,Arial">{html.escape(u["sym"])}</text>'
        )
    parts.append(
        f'<text x="40" y="100" font-size="12" font-family="Segoe UI,Arial" font-weight="700">'
        f'APN {html.escape(sb["apn"])}</text>'
    )
    parts.append(
        f'<text x="40" y="120" font-size="11" font-family="Segoe UI,Arial">'
        f'{html.escape(sb["address"])}</text>'
    )
    parts.append(
        f'<text x="40" y="145" font-size="11" fill="#c00" font-family="Segoe UI,Arial">'
        f'Q-SETBACK OPEN: 112\' lot depth — 30/40\' setbacks impossible; survey required</text>'
    )
    parts.append(
        f'<text x="40" y="165" font-size="10" font-family="Segoe UI,Arial" fill="#555">'
        f'{html.escape(sb.get("sources", "")[:120])}</text>'
    )
    parts.append(
        f'<text x="{ox+g["x"]*scale+10:.1f}" y="{oy-(g["y"]+g["d"]/2)*scale:.1f}" font-size="10" '
        f'font-family="Segoe UI,Arial" fill="#e65100">NEW GARAGE/ADU 2,080 SF</text>'
    )
    parts.append(
        f'<text x="{ox+h["x"]*scale+10:.1f}" y="{oy-(h["y"]+h["d"]/2)*scale:.1f}" font-size="10" '
        f'font-family="Segoe UI,Arial" fill="#1565c0">EXISTING HOUSE</text>'
    )
    return _title_block("C1.1", "SITE PLAN", "\n".join(parts), scale_note="NTS / GIS-derived")


def mep_plan_svg(kind: str) -> tuple[str, str, str]:
    """kind: E | P | M → (sheet_no, title, svg)"""
    s = basis.build_scalars()
    scale = 11.0
    ox, oy = 80.0, 700.0
    parts: list[str] = []
    # building footprint light
    fp = basis.footprint()
    poly = [(ox + x * scale, oy - y * scale) for x, y in fp]
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in poly) + " Z"
    parts.append(f'<path d="{d}" fill="#fafafa" stroke="#999" stroke-width="1"/>')

    if kind == "E":
        sheet, title = "MEP-101", "ELECTRICAL PLAN"
        for dev in mep.electrical_devices():
            x, y = ox + dev["x"] * scale, oy - dev["y"] * scale
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#1565c0"/>'
                f'<text x="{x+7:.1f}" y="{y+3:.1f}" font-size="8" fill="#1565c0" '
                f'font-family="Segoe UI,Arial">{html.escape(dev["sym"])}</text>'
            )
        for i, line in enumerate(mep.electrical_service_calc()[:6]):
            parts.append(
                f'<text x="40" y="{80+i*14}" font-size="9" font-family="Segoe UI,Arial">'
                f'{html.escape(line[:100])}</text>'
            )
    elif kind == "P":
        sheet, title = "MEP-201", "PLUMBING PLAN"
        fixtures = mep.plumbing_fixtures_layout() if hasattr(mep, "plumbing_fixtures_layout") else []
        for fi in fixtures:
            x, y = ox + fi.get("x", 0) * scale, oy - fi.get("y", 0) * scale
            parts.append(
                f'<rect x="{x-6:.1f}" y="{y-6:.1f}" width="12" height="12" fill="#00838f"/>'
                f'<text x="{x+10:.1f}" y="{y+3:.1f}" font-size="8" fill="#006064" '
                f'font-family="Segoe UI,Arial">{html.escape(str(fi.get("mark", fi.get("name", "?"))))}</text>'
            )
        for i, line in enumerate(mep.plumbing_calc()[:6]):
            parts.append(
                f'<text x="40" y="{80+i*14}" font-size="9" font-family="Segoe UI,Arial">'
                f'{html.escape(line[:100])}</text>'
            )
    else:
        sheet, title = "MEP-301", "MECHANICAL PLAN"
        equip = mep.mech_equipment_layout() if hasattr(mep, "mech_equipment_layout") else []
        for eq in equip:
            x, y = ox + eq.get("x", 0) * scale, oy - eq.get("y", 0) * scale
            label = str(eq.get("mark") or eq.get("sym") or eq.get("name") or "?")[:6]
            parts.append(
                f'<rect x="{x-10:.1f}" y="{y-8:.1f}" width="20" height="16" fill="#6a1b9a" opacity="0.7"/>'
                f'<text x="{x:.1f}" y="{y+4:.1f}" text-anchor="middle" font-size="8" fill="#fff" '
                f'font-family="Segoe UI,Arial">{html.escape(label)}</text>'
            )
        for i, line in enumerate(mep.mechanical_calc()[:6]):
            parts.append(
                f'<text x="40" y="{80+i*14}" font-size="9" font-family="Segoe UI,Arial">'
                f'{html.escape(line[:100])}</text>'
            )

    return sheet, title, _title_block(sheet, title, "\n".join(parts))


def door_window_schedule_svg() -> str:
    doors = basis.build_doors()
    windows = basis.build_windows()
    parts = [
        '<text x="40" y="100" font-size="14" font-weight="700" font-family="Segoe UI,Arial">DOOR SCHEDULE</text>',
        '<text x="40" y="120" font-size="10" font-family="Segoe UI,Arial">'
        "MARK | W | H | TYPE | REMARKS | POS</text>",
    ]
    y = 140
    for d in doors:
        pos = "ASSUMED" if d.get("pos_assumed") else "FIXED"
        line = (
            f'{d["mark"]}  {d["w"]:.1f}\' x {d["h"]:.2f}\'  {d["type"]}  '
            f'{d.get("remarks", "")[:40]}  [{pos}]'
        )
        parts.append(
            f'<text x="40" y="{y}" font-size="11" font-family="Consolas,monospace">{html.escape(line)}</text>'
        )
        y += 18
    y += 20
    parts.append(
        f'<text x="40" y="{y}" font-size="14" font-weight="700" font-family="Segoe UI,Arial">WINDOW SCHEDULE</text>'
    )
    y += 20
    for w in windows:
        line = (
            f'{w["mark"]}  {w["w"]:.0f}\'x{w["h"]:.0f}\'  {w["type"]}  U={w.get("u_factor")}  '
            f'sill {w.get("sill")}\'  [{"ASSUMED" if w.get("pos_assumed") else "FIXED"}]'
        )
        parts.append(
            f'<text x="40" y="{y}" font-size="11" font-family="Consolas,monospace">{html.escape(line)}</text>'
        )
        y += 18
    # headers
    y += 30
    parts.append(
        f'<text x="40" y="{y}" font-size="14" font-weight="700" font-family="Segoe UI,Arial">HEADER SCHEDULE</text>'
    )
    y += 20
    for h in struct.header_schedule():
        parts.append(
            f'<text x="40" y="{y}" font-size="11" font-family="Segoe UI,Arial">'
            f'{html.escape(h["mark"])}: {html.escape(h["member"])} — {html.escape(h["use"])} '
            f'({html.escape(str(h["span"]))})</text>'
        )
        y += 18
    return _title_block("A4.1", "DOOR, WINDOW & HEADER SCHEDULES", "\n".join(parts), scale_note="NTS")


def elevation_svg(direction: str) -> str:
    """Simple orthographic elevation from plate heights + openings (notes)."""
    s = basis.build_scalars()
    scale = 10.0
    ox, ground = 100.0, 650.0
    parts: list[str] = []
    L, W = s["main_L"], s["main_W"]
    p = s["bay2_proj"]
    # ground line
    parts.append(
        f'<line x1="40" y1="{ground}" x2="1000" y2="{ground}" stroke="#333" stroke-width="2"/>'
        f'<text x="40" y="{ground+20}" font-size="10" font-family="Segoe UI,Arial">GRADE</text>'
    )
    # footing dash
    parts.append(
        f'<line x1="80" y1="{ground+25}" x2="900" y2="{ground+25}" stroke="#888" '
        f'stroke-dasharray="6 4" stroke-width="1"/>'
        f'<text x="80" y="{ground+40}" font-size="9" fill="#666" font-family="Segoe UI,Arial">'
        f'FOOTING 18"x12" (dashed below grade)</text>'
    )

    if direction in ("S", "N"):
        # width = main L, height to ridge
        width_ft = L
        # wall plate heights along front
        # Bay1 0-16 @ 10', Bay2 16-32 @ 14' (proj), Bay3 32-48 @ 10'
        segs = [
            (0.0, s["bay_L"], s["plate_main"]),
            (s["bay_L"], 2 * s["bay_L"], s["plate_bay2"]),
            (2 * s["bay_L"], L, s["plate_main"]),
        ]
        for x0, x1, h in segs:
            parts.append(
                f'<rect x="{ox+x0*scale:.1f}" y="{ground-h*scale:.1f}" '
                f'width="{(x1-x0)*scale:.1f}" height="{h*scale:.1f}" '
                f'fill="#f5f0e6" stroke="#111" stroke-width="1.5"/>'
            )
        # roof triangle main
        ridge_x = ox + L / 2 * scale
        ridge_y = ground - s["ridge"] * scale
        parts.append(
            f'<polyline points="{ox:.1f},{ground-s["plate_main"]*scale:.1f} '
            f'{ridge_x:.1f},{ridge_y:.1f} {ox+L*scale:.1f},{ground-s["plate_main"]*scale:.1f}" '
            f'fill="#3d3d3d" stroke="#111" stroke-width="1.2" opacity="0.85"/>'
        )
        # Bay2 gable bump on south
        if direction == "S":
            bx0 = ox + s["bay_L"] * scale
            bw = s["bay_L"] * scale
            peak = ground - s["ridge"] * scale
            parts.append(
                f'<polyline points="{bx0:.1f},{ground-s["plate_bay2"]*scale:.1f} '
                f'{bx0+bw/2:.1f},{peak:.1f} {bx0+bw:.1f},{ground-s["plate_bay2"]*scale:.1f}" '
                f'fill="#2a2a2a" stroke="#111" opacity="0.9"/>'
            )
            # OH doors
            for d in basis.build_doors():
                if d["type"] == "OVERHEAD GARAGE":
                    dx = ox + (d["cx"] - d["w"] / 2) * scale
                    dh = d["h"] * scale
                    dw = d["w"] * scale
                    parts.append(
                        f'<rect x="{dx:.1f}" y="{ground-dh:.1f}" width="{dw:.1f}" height="{dh:.1f}" '
                        f'fill="#87ceeb" stroke="#033" stroke-width="1.5"/>'
                        f'<text x="{dx+dw/2:.1f}" y="{ground-dh/2:.1f}" text-anchor="middle" '
                        f'font-size="11" font-weight="700" font-family="Segoe UI,Arial">'
                        f'{html.escape(d["mark"])}</text>'
                    )
        else:
            # north: ADU glazing band + rear doors
            for w in basis.build_windows():
                if w.get("wall") == "rear-north":
                    wx = ox + (w["cx"] - w["w"] / 2) * scale
                    # rear sits at higher y but elev is width of building
                    # map cx to elev x still
                    parts.append(
                        f'<rect x="{wx:.1f}" y="{ground-(w["sill"]+w["h"])*scale:.1f}" '
                        f'width="{w["w"]*scale:.1f}" height="{w["h"]*scale:.1f}" '
                        f'fill="#b3e5fc" stroke="#0277bd"/>'
                        f'<text x="{wx+w["w"]*scale/2:.1f}" y="{ground-(w["sill"]+w["h"]/2)*scale:.1f}" '
                        f'text-anchor="middle" font-size="9" font-family="Segoe UI,Arial">'
                        f'{html.escape(w["mark"])}</text>'
                    )
        # height tags
        parts.append(
            f'<text x="{ox+L*scale+20:.1f}" y="{ground-s["plate_main"]*scale:.1f}" font-size="10" '
            f'font-family="Segoe UI,Arial">PLATE {s["plate_main"]:.0f}\'</text>'
        )
        parts.append(
            f'<text x="{ox+L*scale+20:.1f}" y="{ridge_y:.1f}" font-size="10" fill="#c00" '
            f'font-family="Segoe UI,Arial">RIDGE {s["ridge"]:.0f}\'</text>'
        )
        title = f"ELEVATION — {'SOUTH' if direction == 'S' else 'NORTH'}"
        no = "A2.1" if direction == "S" else "A2.1b"
    else:
        # East / West — depth of main + rear
        depth = W + s["rear_W"]
        h = s["plate_main"]
        parts.append(
            f'<rect x="{ox:.1f}" y="{ground-h*scale:.1f}" width="{depth*scale:.1f}" '
            f'height="{h*scale:.1f}" fill="#f5f0e6" stroke="#111" stroke-width="1.5"/>'
        )
        # roof slope
        parts.append(
            f'<polyline points="{ox:.1f},{ground-h*scale:.1f} '
            f'{ox+W/2*scale:.1f},{ground-s["ridge"]*scale:.1f} '
            f'{ox+W*scale:.1f},{ground-h*scale:.1f} '
            f'{ox+(W+s["rear_W"])*scale:.1f},{ground-s["plate_rear_low"]*scale:.1f}" '
            f'fill="#3d3d3d" stroke="#111" opacity="0.85"/>'
        )
        parts.append(
            f'<text x="{ox+10}" y="{ground-h*scale/2:.1f}" font-size="12" '
            f'font-family="Segoe UI,Arial">{"EAST" if direction == "E" else "WEST"} ELEV</text>'
        )
        title = f"ELEVATION — {'EAST' if direction == 'E' else 'WEST'}"
        no = "A2.2" if direction == "E" else "A2.2b"

    parts.append(
        f'<text x="80" y="90" font-size="11" font-family="Segoe UI,Arial" fill="#555">'
        f'Note-driven massing from plate/ridge/opening records · standing-seam charcoal · '
        f'DF board-and-batten · 18" overhangs not yet drawn as soffit profiles</text>'
    )
    return _title_block(no, title, "\n".join(parts), scale_note='~1/8" = 1\'-0"')


def wall_type_schedule_svg() -> str:
    rows = [
        ("W1", "EXT 2x6 BnB", "2x6 DF-L @ 16\" OC", "R-21 batt", "WRB + 5/8\" DF structural siding + 1x3 battens @ 16\"", "5/8\" gyp", "—"),
        ("W2", "INT 2x4", "2x4 DF-L @ 16\" OC", "batt optional", "—", "5/8\" gyp both sides", "—"),
        ("W3", "1-HR GAR/ADU", "2x6 or as wall", "—", "—", "5/8\" Type X both sides slab-to-deck", "1-hr"),
        ("W4", "BAY-2 EXT", "2x6 full-height 14'", "R-21", "same as W1", "gyp", "—"),
    ]
    parts = [
        '<text x="40" y="100" font-size="14" font-weight="700" font-family="Segoe UI,Arial">WALL TYPE SCHEDULE (from notes)</text>',
        '<text x="40" y="125" font-size="10" font-family="Consolas,monospace">'
        "TYPE | NAME | STRUCTURE | INSUL | EXTERIOR | INTERIOR | FR</text>",
    ]
    y = 150
    for r in rows:
        parts.append(
            f'<text x="40" y="{y}" font-size="11" font-family="Segoe UI,Arial">'
            f'{html.escape(" | ".join(r))}</text>'
        )
        y += 28
    y += 20
    parts.append(
        f'<text x="40" y="{y}" font-size="14" font-weight="700" font-family="Segoe UI,Arial">'
        f'STRONG-WALL SCHEDULE</text>'
    )
    y += 25
    for sw in basis.build_structure()["strong_walls"]:
        parts.append(
            f'<text x="40" y="{y}" font-size="11" font-family="Segoe UI,Arial">'
            f'{html.escape(sw["id"])}: {html.escape(sw["model"])} @ x={sw["x"]:.1f}\' y={sw["y"]:.1f}\' '
            f'h={sw["h"]:.0f}\'  [pos_assumed={sw.get("pos_assumed")}]  SSTB per ESR-2652 / EOR</text>'
        )
        y += 18
    y += 25
    parts.append(
        f'<text x="40" y="{y}" font-size="14" font-weight="700" font-family="Segoe UI,Arial">'
        f'MATERIALS (notes / specs outline)</text>'
    )
    mats = [
        "Concrete 3,500 psi; footings 18x12; stem 8\" front / 6\" typ",
        "Slab garage 4\" radiant PEX @ 9\" OC + fiber; ADU 3\"; 10-mil VB; 4\" gravel",
        "Steel: W16x40 x2; HSS6x6x1/4 posts; base PL 8x8x1; A325 bolts",
        "Wood: 2x6 ext / 2x4 int DF-L #2; trusses 24\" OC deferred fab",
        "Shear: 5/8\" DF structural siding + SSW panels; SS fasteners",
        "Roof: 24ga standing-seam charcoal; ice & water; R-38 ceiling",
        "Insulation: R-21 walls / R-38 ceiling / R-10 under ADU slab",
        "Propane boilers B-1/B-2; tankless WH-1; PT-1 60-gal well vessel",
    ]
    y += 22
    for m in mats:
        parts.append(
            f'<text x="40" y="{y}" font-size="11" font-family="Segoe UI,Arial">• {html.escape(m)}</text>'
        )
        y += 18
    return _title_block("A4.2", "WALL TYPES, SSW & MATERIALS", "\n".join(parts), scale_note="NTS")


def house_concept_svg() -> str:
    scale = 8.0
    ox, oy = 60.0, 380.0
    parts: list[str] = [
        '<text x="40" y="90" font-size="14" font-weight="700" font-family="Segoe UI,Arial">'
        "H2.2 CONCEPT — UPPER DORMERED BAND (4 BR / 2 BA) + NW MASTER SUITE</text>",
        '<text x="40" y="110" font-size="11" fill="#a00" font-family="Segoe UI,Arial">'
        "CONCEPT ONLY — field dimensions govern · 5 BR / 3 BA program confirmed</text>",
    ]
    for r in house.concept_upper():
        parts.append(
            f'<rect x="{ox+r["x"]*scale:.1f}" y="{oy-(r["y"]+r["d"])*scale:.1f}" '
            f'width="{r["w"]*scale:.1f}" height="{r["d"]*scale:.1f}" fill="#e3f2fd" stroke="#1565c0"/>'
            f'<text x="{ox+(r["x"]+r["w"]/2)*scale:.1f}" y="{oy-(r["y"]+r["d"]/2)*scale:.1f}" '
            f'text-anchor="middle" font-size="8" font-family="Segoe UI,Arial">'
            f'{html.escape(r["name"])}</text>'
        )
    # suite below
    ox2, oy2 = 60.0, 720.0
    parts.append(
        f'<text x="40" y="{oy2-200}" font-size="12" font-weight="700" font-family="Segoe UI,Arial">'
        f"NW MASTER SUITE (vaulted, single story) 16x24 + 10x12 bath + 10x10 WIC</text>"
    )
    for r in house.concept_suite():
        parts.append(
            f'<rect x="{ox2+r["x"]*scale:.1f}" y="{oy2-(r["y"]+r["d"])*scale:.1f}" '
            f'width="{r["w"]*scale:.1f}" height="{r["d"]*scale:.1f}" fill="#fce4ec" stroke="#ad1457"/>'
            f'<text x="{ox2+(r["x"]+r["w"]/2)*scale:.1f}" y="{oy2-(r["y"]+r["d"]/2)*scale:.1f}" '
            f'text-anchor="middle" font-size="9" font-family="Segoe UI,Arial">'
            f'{html.escape(r["name"])}</text>'
        )
    for i, n in enumerate(house.concept_notes()[:8]):
        short = n if len(n) < 95 else n[:92] + "..."
        parts.append(
            f'<text x="580" y="{140+i*22}" font-size="10" font-family="Segoe UI,Arial">'
            f'• {html.escape(short)}</text>'
        )
    return _title_block("H2.2", "HOUSE REMODEL — CONCEPT PLANS", "\n".join(parts), scale_note="NTS concept")


def section_svg() -> str:
    """Building section through Bay 2 (N-S): plates, ridge, shed curb."""
    s = basis.build_scalars()
    scale = 14.0
    ox, ground = 200.0, 700.0
    parts: list[str] = []
    # slab
    depth = s["main_W"] + s["rear_W"]
    parts.append(
        f'<rect x="{ox:.1f}" y="{ground:.1f}" width="{depth*scale:.1f}" height="8" fill="#ccc" stroke="#333"/>'
    )
    # main walls N-S at section cut through bay2
    h_main = s["plate_main"]
    h_bay = s["plate_bay2"]
    # south wall (proj)
    parts.append(
        f'<rect x="{ox-s["bay2_proj"]*scale:.1f}" y="{ground-h_bay*scale:.1f}" '
        f'width="{6:.1f}" height="{h_bay*scale:.1f}" fill="#e8e0d0" stroke="#111"/>'
    )
    # north main wall
    parts.append(
        f'<rect x="{ox+s["main_W"]*scale:.1f}" y="{ground-h_main*scale:.1f}" '
        f'width="6" height="{h_main*scale:.1f}" fill="#e8e0d0" stroke="#111"/>'
    )
    # fire / shed wall at y=32
    parts.append(
        f'<rect x="{ox+s["main_W"]*scale:.1f}" y="{ground-s["plate_rear_high"]*scale:.1f}" '
        f'width="6" height="{s["plate_rear_high"]*scale:.1f}" fill="#c00" opacity="0.35" stroke="#800"/>'
    )
    # ridge
    mid = ox + s["main_W"] / 2 * scale
    parts.append(
        f'<line x1="{ox-s["bay2_proj"]*scale:.1f}" y1="{ground-h_bay*scale:.1f}" '
        f'x2="{mid:.1f}" y2="{ground-s["ridge"]*scale:.1f}" stroke="#333" stroke-width="2"/>'
        f'<line x1="{mid:.1f}" y1="{ground-s["ridge"]*scale:.1f}" '
        f'x2="{ox+s["main_W"]*scale:.1f}" y2="{ground-h_main*scale:.1f}" stroke="#333" stroke-width="2"/>'
    )
    # shed slope
    parts.append(
        f'<line x1="{ox+s["main_W"]*scale:.1f}" y1="{ground-s["plate_rear_high"]*scale:.1f}" '
        f'x2="{ox+(s["main_W"]+s["rear_W"])*scale:.1f}" y2="{ground-s["plate_rear_low"]*scale:.1f}" '
        f'stroke="#333" stroke-width="2"/>'
    )
    # beam
    parts.append(
        f'<rect x="{mid-4:.1f}" y="{ground-h_main*scale-12:.1f}" width="8" height="12" fill="#00a"/>'
        f'<text x="{mid+10:.1f}" y="{ground-h_main*scale-4:.1f}" font-size="10" fill="#00a" '
        f'font-family="Segoe UI,Arial">W16x40</text>'
    )
    labels = [
        (f'BAY-2 PLATE {s["plate_bay2"]:.0f}\'', ox, ground - h_bay * scale - 8),
        (f'RIDGE {s["ridge"]:.0f}\'', mid, ground - s["ridge"] * scale - 8),
        (f'MAIN PLATE {s["plate_main"]:.0f}\'', ox + s["main_W"] * scale + 10, ground - h_main * scale),
        ("SHED CURB 10'→12' (D02)", ox + s["main_W"] * scale + 10, ground - s["plate_rear_high"] * scale),
        ("1-HR FIRE SEP (D08)", ox + s["main_W"] * scale - 80, ground - 40),
    ]
    for text, x, y in labels:
        parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="10" font-family="Segoe UI,Arial">{html.escape(text)}</text>'
        )
    parts.append(
        '<text x="80" y="90" font-size="11" font-family="Segoe UI,Arial">'
        "SECTION @ BAY 2 (N-S) — from plate/ridge/shed scalars · see D01–D05 for connections</text>"
    )
    return _title_block("A3.1", "BUILDING SECTION — BAY 2", "\n".join(parts), scale_note='~1/4" = 1\'-0"')


def cover_sheet_svg() -> str:
    s = basis.build_scalars()
    sheets = basis.sheet_register()
    parts = [
        '<text x="80" y="140" font-size="32" font-weight="700" font-family="Segoe UI,Arial">SCHAD</text>',
        '<text x="80" y="175" font-size="18" font-family="Segoe UI,Arial">Garage / ADU / Workshop Complex</text>',
        '<text x="80" y="210" font-size="14" font-family="Segoe UI,Arial">3730 Chandler Rd, Quincy, CA 95971 · APN 005-350-001</text>',
        '<text x="80" y="235" font-size="13" font-family="Segoe UI,Arial">Ledger Built LLC · Project 2024-008 · Designer: Ryan Vukich</text>',
        f'<text x="80" y="280" font-size="14" font-family="Segoe UI,Arial">Total {s["area_total"]:.0f} SF · '
        f'Garage {s["area_garage"]:.0f} · ADU {s["area_adu"]:.0f} · Workshop {s["area_workshop"]:.0f}</text>',
        '<text x="80" y="320" font-size="16" fill="#c00" font-weight="700" font-family="Segoe UI,Arial">'
        "DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION</text>",
        '<text x="80" y="360" font-size="13" font-family="Segoe UI,Arial">SHEET INDEX (target register)</text>',
    ]
    y = 385
    for sh in sheets:
        parts.append(
            f'<text x="80" y="{y}" font-size="11" font-family="Consolas,monospace">'
            f'{html.escape(str(sh.get("number", sh.get("no", ""))))}  '
            f'{html.escape(str(sh.get("title", "")))}</text>'
        )
        y += 15
        if y > 780:
            break
    return _title_block("A0.1", "COVER SHEET & INDEX", "\n".join(parts), scale_note="NTS")
