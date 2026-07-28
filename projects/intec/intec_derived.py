"""INTEC derived systems content — frozen Eigen engines → sheet text/SVG.

Source snapshot: ``data/eigen_systems_snapshot.json`` produced from
``Eigen/scripts/intec_facility_systems.py``, ``intec_bid_basis.py``,
``intec_module_basis.py`` (freeze 2026-07-22).

llm-bim does NOT import Eigen at runtime — the JSON is the pack SSOT so
CI/agents work without Eigen on disk. Re-freeze when engines change:

  cd Eigen && PYTHONPATH=scripts python -c \"... dump to projects/intec/data/\"

Honesty: [ENGINEERING ESTIMATE] — every figure is design-basis class.
"""

from __future__ import annotations

import html
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parent / "data" / "eigen_systems_snapshot.json"


def _esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


@lru_cache(maxsize=1)
def load_snapshot() -> dict[str, Any]:
    if not _DATA.is_file():
        raise FileNotFoundError(
            f"missing {_DATA} — freeze Eigen engines into this path"
        )
    return json.loads(_DATA.read_text(encoding="utf-8"))


def snapshot_meta() -> dict[str, str]:
    s = load_snapshot()
    return {
        "source": str(s.get("source", "")),
        "honesty": str(s.get("honesty", "")),
        "path": str(_DATA),
    }


# --------------------------------------------------------------------------- #
# table → SVG                                                                  #
# --------------------------------------------------------------------------- #
def table_svg(
    title: str,
    headers: list[str],
    rows: list[list[Any]],
    *,
    col_w: list[float] | None = None,
    note: str = "",
    max_rows: int = 40,
) -> str:
    """Simple ruled table sheet body."""
    n = len(headers)
    widths = col_w or [max(80.0, 820.0 / n)] * n
    total_w = sum(widths)
    x0, y0 = 30.0, 50.0
    row_h = 16.0
    header_h = 20.0
    shown = rows[:max_rows]
    h = y0 + header_h + row_h * len(shown) + 50
    w = max(900.0, x0 * 2 + total_w)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="0 0 {w:.0f} {h:.0f}">',
        f'<rect width="100%" height="100%" fill="#fff"/>',
        f'<text x="{x0}" y="28" font-size="13" font-weight="700" '
        f'font-family="Segoe UI,Arial,sans-serif" fill="#1a237e">{_esc(title)}</text>',
        f'<rect x="{x0}" y="{y0}" width="{total_w}" height="{header_h}" fill="#e3f2fd"/>',
    ]
    x = x0
    for i, hdr in enumerate(headers):
        parts.append(
            f'<text x="{x + 4}" y="{y0 + 14}" font-size="9" font-weight="600" '
            f'font-family="Segoe UI,Arial,sans-serif">{_esc(hdr)}</text>'
        )
        x += widths[i]
    y = y0 + header_h
    for ri, row in enumerate(shown):
        if ri % 2 == 1:
            parts.append(
                f'<rect x="{x0}" y="{y}" width="{total_w}" height="{row_h}" fill="#fafafa"/>'
            )
        x = x0
        for i, cell in enumerate(row):
            txt = str(cell)
            if len(txt) > 55:
                txt = txt[:52] + "…"
            parts.append(
                f'<text x="{x + 4}" y="{y + 12}" font-size="8" '
                f'font-family="Segoe UI,Arial,sans-serif">{_esc(txt)}</text>'
            )
            x += widths[i]
        y += row_h
    # grid
    parts.append(
        f'<rect x="{x0}" y="{y0}" width="{total_w}" height="{header_h + row_h * len(shown)}" '
        f'fill="none" stroke="#90a4ae" stroke-width="0.8"/>'
    )
    x = x0
    for ww in widths[:-1]:
        x += ww
        parts.append(
            f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y0 + header_h + row_h * len(shown)}" '
            f'stroke="#cfd8dc" stroke-width="0.5"/>'
        )
    foot = note or "[ENGINEERING ESTIMATE] — design-basis; PE seal reserved (DS-2)."
    if len(rows) > max_rows:
        foot = f"showing {max_rows}/{len(rows)} rows · " + foot
    parts.append(
        f'<text x="{x0}" y="{h - 14}" font-size="8" fill="#b71c1c" '
        f'font-family="Segoe UI,Arial,sans-serif">{_esc(foot)}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def bullets_svg(title: str, lines: list[str], *, warn: str = "") -> str:
    y = 48.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="700" viewBox="0 0 900 700">',
        f'<rect width="100%" height="100%" fill="#fff"/>',
        f'<text x="40" y="30" font-size="14" font-weight="700" fill="#1a237e" '
        f'font-family="Segoe UI,Arial,sans-serif">{_esc(title)}</text>',
    ]
    for line in lines:
        chunk = str(line)
        while chunk:
            piece = chunk[:105]
            if len(chunk) > 105:
                sp = piece.rfind(" ")
                if sp > 40:
                    piece = chunk[:sp]
            parts.append(
                f'<text x="40" y="{y}" font-size="10" font-family="Segoe UI,Arial,sans-serif">'
                f"{_esc(piece)}</text>"
            )
            chunk = chunk[len(piece) :].lstrip()
            y += 14
        y += 4
        if y > 640:
            break
    if warn:
        parts.append(
            f'<text x="40" y="680" font-size="8" fill="#b71c1c">{_esc(warn)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# sheet content providers (used by build_llmbim register)                      #
# --------------------------------------------------------------------------- #
def g006_calc_index() -> str:
    s = load_snapshot()
    el = s["electrical"]
    hv = s["hvac"]
    rows = [
        ["E / service", f"{el['service_design_mw']} MW design / {el['coincident_mw']} MW coincident", "E-001 / E-008"],
        ["E / lighting", f"{el['lighting_kw']} kW lumen-method", "E-007"],
        ["E / standby G-1", f"{el['gen_kw']} kW diesel + ATS", "E-001"],
        ["H / exhaust", f"{hv['exhaust_m3h']} m³/h ({hv['exhaust_cfm']} cfm)", "H-002 / H-005"],
        ["H / HEPA", f"{hv['hepa_stages']}-stage · {hv['hepa_banks']} banks", "H-003"],
        ["H / exhaust fan", f"{hv['exhaust_fan_kw']} kW", "H-004"],
        ["P / fixtures", f"{len(s['plumbing']['fixtures'])} fixture types", "P-008"],
        ["F / water demand", f"{s['fire']['water_demand_gpm']} gpm NFPA 13 bound", "F-001"],
        ["I / CAM", f"n={s['rad_monitoring']['cam']['n']}", "I-003 / I-005"],
        ["I / ARM", f"n={s['rad_monitoring']['arm']['n']}", "I-003"],
        ["I / CAAS", f"n={s['rad_monitoring']['caas']['n']} · {s['rad_monitoring']['caas']['voting']}", "I-005"],
        ["I / I/O total", f"{s['controls']['io_total']} pts · {s['controls']['remote_racks']} racks", "I-001"],
        ["LS / occupancy", f"{s['egress']['occupant_load']} support-side", "LS-001"],
        ["C / ops commit", f"{s['site']['ops_acres_commit']} ac + PIDAS", "C-005"],
    ]
    return table_svg(
        "G-006 ENGINEERING CALCULATIONS INDEX (derived)",
        ["System", "Key result", "Sheet"],
        rows,
        col_w=[160, 420, 120],
        note="Drivers in eigen_systems_snapshot.json · " + str(s.get("honesty", "")),
    )


def g007_equip_index() -> str:
    s = load_snapshot()
    rows: list[list[Any]] = []
    for eq in s.get("hvac_equipment", [])[:25]:
        if isinstance(eq, dict):
            rows.append([
                eq.get("tag") or eq.get("id") or "—",
                eq.get("what") or eq.get("name") or "—",
                eq.get("capacity") or eq.get("size") or "—",
                eq.get("driver", "")[:50],
            ])
    eq_mod = s.get("module_equipment") or {}
    if isinstance(eq_mod, dict):
        for k, v in list(eq_mod.items())[:20]:
            if isinstance(v, dict):
                rows.append([k, v.get("what") or v.get("name") or "—",
                             v.get("qty") or v.get("n") or "—", "module_basis.EQUIPMENT"])
            elif isinstance(v, list):
                rows.append([k, f"{len(v)} items", "—", "module_basis.EQUIPMENT"])
    if not rows:
        rows = [["(see module EQUIPMENT + hvac_equipment in snapshot)", "—", "—", "—"]]
    return table_svg(
        "G-007 EQUIPMENT SPECIFICATIONS INDEX (basis-of-design)",
        ["Tag", "Description", "Capacity / qty", "Driver"],
        rows,
        col_w=[100, 280, 160, 200],
    )


def g010_bid_quantities() -> str:
    s = load_snapshot()
    rows = []
    for item in s.get("bid_quantities") or []:
        if isinstance(item, (list, tuple)) and len(item) >= 4:
            rows.append([item[0], item[1], item[2], item[3]])
        elif isinstance(item, dict):
            rows.append([
                item.get("name") or item.get("item"),
                item.get("qty") or item.get("value"),
                item.get("unit"),
                item.get("basis") or item.get("driver"),
            ])
    return table_svg(
        "G-010 BID QUANTITIES — model takeoff (derived)",
        ["Item", "Qty", "Unit", "Basis sheet"],
        rows,
        col_w=[260, 80, 60, 340],
        note="BUDGETARY pricing basis · NOT a bought-out estimate · rebar = density ALLOWANCE",
    )


def g011_scope() -> str:
    s = load_snapshot()
    lines: list[str] = ["SCOPE MATRIX — GC vs OWNER furnish/install", ""]
    scope = s.get("bid_scope") or []
    if isinstance(scope, list):
        for row in scope[:40]:
            if isinstance(row, (list, tuple)):
                lines.append(" · ".join(str(x) for x in row))
            elif isinstance(row, dict):
                lines.append(
                    f"{row.get('system', row.get('item', '?'))}: "
                    f"GC={row.get('gc', '—')} · OWNER={row.get('owner', '—')}"
                )
            else:
                lines.append(str(row))
    elif isinstance(scope, dict):
        for k, v in scope.items():
            lines.append(f"{k}: {v}")
    lines += ["", "ASSUMPTIONS"]
    for a in (s.get("bid_assumptions") or [])[:15]:
        lines.append(f"• {a if not isinstance(a, (list, tuple)) else ' — '.join(map(str, a))}")
    lines += ["", "ALLOWANCES"]
    for a in (s.get("bid_allowances") or [])[:12]:
        lines.append(f"• {a if not isinstance(a, (list, tuple)) else ' — '.join(map(str, a))}")
    lines += ["", "EXCLUSIONS"]
    for a in (s.get("bid_exclusions") or [])[:12]:
        lines.append(f"• {a if not isinstance(a, (list, tuple)) else ' — '.join(map(str, a))}")
    return bullets_svg("G-011 SCOPE MATRIX + BID CLARIFICATIONS", lines)


def g012_crosswalk() -> str:
    s = load_snapshot()
    cw = s.get("room_crosswalk")
    rows: list[list[Any]] = []
    if isinstance(cw, list):
        for r in cw:
            if isinstance(r, (list, tuple)):
                rows.append(list(r)[:4])
            elif isinstance(r, dict):
                rows.append([
                    r.get("as_modeled") or r.get("plan") or r.get("id"),
                    r.get("program") or r.get("systems"),
                    r.get("note") or r.get("governs") or "as-modeled",
                    r.get("driver") or "",
                ])
    if not rows:
        # fallback from placements vs support rooms
        from intec_design_basis import build_placements

        prog = {r["room"]: r["name"] for r in s.get("support_rooms") or []}
        for pl in build_placements():
            rows.append([
                pl["id"],
                pl["name"],
                prog.get(pl["id"], "(process / as-modeled)"),
                "as-modeled governs",
            ])
    return table_svg(
        "G-012 ROOM CROSSWALK — as-modeled vs program basis",
        ["As-modeled", "Name / program", "Notes", "Driver"],
        rows,
        col_w=[120, 220, 220, 160],
    )


def h004_hvac_equip() -> str:
    s = load_snapshot()
    rows = []
    for eq in s.get("hvac_equipment") or []:
        if isinstance(eq, dict):
            rows.append([
                eq.get("tag") or eq.get("id") or "—",
                eq.get("what") or eq.get("type") or "—",
                eq.get("capacity") or eq.get("m3h") or eq.get("cfm") or "—",
                eq.get("where") or eq.get("location") or "—",
                str(eq.get("driver", ""))[:40],
            ])
    if not rows:
        hv = s["hvac"]
        rows = [
            ["EF-1/2", "Exhaust fans 2x50%", f"{hv['exhaust_fan_kw']} kW", "MECH", hv.get("fans", "")],
            ["HEPA", f"{hv['hepa_stages']}-stage BIBO", f"{hv['hepa_banks']} banks", "filter room", "ASME AG-1"],
            ["AHU-1", "Support AHU", f"{hv.get('ahu_m3h', '—')} m³/h", "MECH", "R1 supply"],
        ]
    return table_svg(
        "H-004 HVAC EQUIPMENT SCHEDULE (derived)",
        ["Tag", "Equipment", "Capacity", "Location", "Driver"],
        rows,
        col_w=[80, 200, 140, 100, 200],
    )


def h005_airflow() -> str:
    s = load_snapshot()
    rows = []
    for r in (s["hvac"].get("rooms") or [])[:35]:
        rows.append([
            r.get("room"),
            r.get("zone"),
            r.get("atmosphere"),
            r.get("dp_Pa"),
            r.get("m3h"),
            r.get("cfm"),
            str(r.get("class", ""))[:40],
        ])
    return table_svg(
        "H-005 AIRFLOW SCHEDULE + CONFINEMENT CASCADE (derived)",
        ["Room", "Zone", "Atm", "dP Pa", "m³/h", "cfm", "Class"],
        rows,
        col_w=[90, 50, 80, 60, 60, 55, 280],
        note=f"cascade {s['hvac'].get('cascade')} · exhaust {s['hvac']['exhaust_m3h']} m³/h",
    )


def e006_panels() -> str:
    s = load_snapshot()
    rows = []
    for card in s.get("panel_circuits") or []:
        if not isinstance(card, dict):
            continue
        for c in (card.get("ckts") or [])[:12]:
            rows.append([
                card.get("panel"),
                card.get("v"),
                c.get("desc"),
                c.get("va"),
                c.get("brk"),
                c.get("note", ""),
            ])
        rows.append([card.get("panel"), "—", f"(connected {card.get('conn_kw')} kW)", "—", card.get("main"), card.get("driver", "")[:30]])
    return table_svg(
        "E-006 PANEL & CIRCUIT SCHEDULES — NEC panel cards (derived)",
        ["Panel", "Voltage", "Circuit", "VA", "Breaker", "Note"],
        rows,
        col_w=[80, 120, 220, 60, 90, 160],
        max_rows=45,
    )


def e007_lighting() -> str:
    s = load_snapshot()
    rows = [
        [
            r.get("room"),
            r.get("lux"),
            r.get("fixture"),
            r.get("n_fixtures"),
            r.get("kw"),
            r.get("circuits"),
            str(r.get("driver", ""))[:45],
        ]
        for r in s.get("lighting") or []
    ]
    return table_svg(
        "E-007 LIGHTING PLAN + FIXTURE SCHEDULE (derived)",
        ["Room", "lux", "Fixture", "N", "kW", "Ckts", "Driver"],
        rows,
        col_w=[100, 50, 70, 40, 50, 45, 320],
    )


def f003_fire() -> str:
    s = load_snapshot()
    rows = [
        [
            r.get("room"),
            str(r.get("suppression", ""))[:50],
            r.get("detection"),
            r.get("rating"),
            str(r.get("why", ""))[:40],
        ]
        for r in (s["fire"].get("rooms") or [])
    ]
    return table_svg(
        "F-003 FIRE SUPPRESSION SELECTION PER ROOM (derived)",
        ["Room", "Suppression", "Detection", "Rating", "Why"],
        rows,
        col_w=[90, 260, 120, 60, 220],
        note=f"water demand {s['fire'].get('water_demand_gpm')} gpm · {s['fire'].get('driver', '')[:60]}",
    )


def p008_plumbing() -> str:
    s = load_snapshot()
    rows = [
        [f.get("tag"), f.get("what"), f.get("n"), f.get("where"), str(f.get("driver", ""))[:45]]
        for f in (s["plumbing"].get("fixtures") or [])
    ]
    return table_svg(
        "P-008 PLUMBING FIXTURES + EMERGENCY FIXTURES (derived)",
        ["Tag", "Description", "N", "Where", "Driver"],
        rows,
        col_w=[70, 260, 40, 160, 240],
        note=f"main {s['plumbing'].get('domestic_main')} · sanitary {s['plumbing'].get('sanitary_main')}",
    )


def p009_plumbing_conn() -> str:
    s = load_snapshot()
    rows = []
    for c in s.get("plumbing_connections") or []:
        if isinstance(c, dict):
            rows.append([
                c.get("tag") or c.get("fixture") or "—",
                c.get("service") or c.get("system") or "—",
                c.get("size") or c.get("nps") or "—",
                c.get("where") or c.get("room") or "—",
                str(c.get("driver", c.get("note", "")))[:40],
            ])
    if not rows:
        pl = s["plumbing"]
        rows = [
            ["domestic main", "CW", pl.get("domestic_main"), "riser", "wsfu"],
            ["sanitary main", "SAN", pl.get("sanitary_main"), "riser", "dfu"],
            ["WH-1", "DHW", pl.get("water_heater"), "MECH", "decon showers"],
        ]
    return table_svg(
        "P-009 PLUMBING RISER + FIXTURE CONNECTION SCHEDULE",
        ["Tag", "Service", "Size", "Location", "Note"],
        rows,
        col_w=[100, 80, 160, 120, 260],
    )


def i005_rad_io() -> str:
    s = load_snapshot()
    rm = s["rad_monitoring"]
    ctl = s["controls"]
    rows = [
        ["CAM", rm["cam"]["n"], rm["cam"]["where"][:50], rm["cam"]["driver"][:40]],
        ["ARM", rm["arm"]["n"], rm["arm"]["where"][:50], rm["arm"]["driver"][:40]],
        ["CAAS", rm["caas"]["n"], rm["caas"].get("voting", ""), rm["caas"]["driver"][:40]],
        ["Portal", rm["portal"]["n"], rm["portal"]["where"][:50], rm["portal"]["driver"][:40]],
        ["Hand/foot", rm["hand_foot"]["n"], rm["hand_foot"]["where"], rm["hand_foot"]["driver"][:40]],
        ["Stack CEMS", rm["stack"]["n"], rm["stack"]["where"], rm["stack"]["driver"][:40]],
        ["I/O process", ctl["io_process"], "—", "station census"],
        ["I/O HVAC", ctl["io_hvac"], "—", "dampers/dp/flow"],
        ["I/O rad", ctl["io_rad"], "—", "monitor points ×2"],
        ["I/O total", ctl["io_total"], f"{ctl['remote_racks']} racks", ctl["driver"][:40]],
    ]
    return table_svg(
        "I-005 RAD MONITORING + CAAS + CONTROL I/O (derived)",
        ["Item", "N / pts", "Where / arch", "Driver"],
        rows,
        col_w=[100, 80, 320, 240],
    )


def s015_modules() -> str:
    s = load_snapshot()
    rows = []
    for m in s.get("module_modules") or []:
        if isinstance(m, (list, tuple)):
            rows.append(list(m)[:5])
        elif isinstance(m, dict):
            rows.append([
                m.get("id") or m.get("tag"),
                m.get("name") or m.get("what"),
                m.get("mass_t") or m.get("lift_t"),
                m.get("station") or m.get("where"),
                m.get("note") or "",
            ])
    conns = s.get("module_connections") or []
    if conns and not rows:
        for c in conns:
            if isinstance(c, (list, tuple)):
                rows.append([c[0], c[1] if len(c) > 1 else "", "", "", c[2] if len(c) > 2 else ""])
    return table_svg(
        "S-015 MODULE CONSTRUCTION + CONNECTIONS",
        ["ID", "Name / connection", "Mass t", "Station", "Notes"],
        rows or [["SPM", "Separator skid", "—", "CELL-*", "see module_basis"]],
        col_w=[80, 240, 70, 100, 280],
        note="K1–K10 connection keynotes in snapshot module_connections",
    )


def s016_station_matrix() -> str:
    s = load_snapshot()
    rows = []
    for sid, st in (s.get("module_stations") or {}).items():
        if not isinstance(st, dict):
            continue
        rows.append([
            sid,
            st.get("name", ""),
            f"T{st.get('tier', '?')}",
            str(st.get("constr", ""))[:40],
            str(st.get("anchor", ""))[:30],
            str(st.get("conns", ""))[:35],
        ])
    return table_svg(
        "S-016 STATION CONSTRUCTION MATRIX — every box",
        ["ID", "Name", "Tier", "Construction", "Anchorage", "Connections"],
        rows,
        col_w=[80, 160, 40, 220, 150, 180],
        max_rows=30,
    )


def ls001_egress() -> str:
    s = load_snapshot()
    eg = s["egress"]
    lines = [
        f"Occupant load (support): {eg['occupant_load']}",
        f"Process block: {eg['process_block']}",
        f"Support exits: {eg['exits_support']} · width {eg['exit_width_mm']} mm",
        f"Travel limit: {eg['travel_limit_m']} m · ok={eg['travel_ok']}",
        f"Muster: {eg['muster']}",
        f"Notes: {eg['notes']}",
        f"Driver: {eg['driver']}",
    ]
    return bullets_svg("LS-001 EGRESS + OCCUPANT LOADS (derived)", lines)


def l001_logistics() -> str:
    s = load_snapshot()
    lg = s["logistics"]
    lines = []
    for section in ("receiving", "shipping", "storage", "moving", "charging"):
        block = lg.get(section) or {}
        lines.append(section.upper())
        if isinstance(block, dict):
            for k, v in block.items():
                lines.append(f"  {k}: {v}")
        lines.append("")
    return bullets_svg("L-001 RECEIVE / SHIP / STORE / MOVE / CHARGE (derived)", lines)


def c005_ops_site() -> str:
    s = load_snapshot()
    site = s["site"]
    lines = [
        f"Ops acres commit: {site.get('ops_acres_commit')}",
        f"Compressed acres: {site.get('compressed_acres')}",
        f"Ops envelope m: {site.get('ops_envelope_m')}",
        f"PA fence m: {site.get('pa_fence_m')} · PIDAS corridor {site.get('pidas_corridor_m')} m",
        f"Fence perimeter: {site.get('fence_perimeter_m')} m",
        f"Parking stalls: {site.get('parking_stalls')} — {site.get('parking_note')}",
        "Gates:",
        *[f"  • {g}" for g in (site.get("gates") or [])],
        "Yard equipment:",
        *[f"  • {y}" for y in (site.get("yard") or [])],
        f"Driver: {site.get('driver')}",
    ]
    return bullets_svg("C-005 OPS SITE PLAN — 2-ACRE COMMIT (derived)", lines)


def a011_room_req() -> str:
    s = load_snapshot()
    rows = []
    for r in s.get("support_rooms") or []:
        rows.append([
            r.get("room"),
            r.get("name"),
            r.get("area_m2"),
            r.get("zone"),
            str(r.get("driver", ""))[:50],
        ])
    # also list process rooms from fire/hvac as zone source
    seen = {r[0] for r in rows}
    for r in (s["hvac"].get("rooms") or []):
        if r.get("room") not in seen:
            rows.append([
                r.get("room"),
                r.get("atmosphere"),
                "—",
                r.get("zone"),
                r.get("class", "")[:50],
            ])
    return table_svg(
        "A-011 ROOM REQUIREMENTS & FINISH SCHEDULE (derived)",
        ["Room", "Name / atm", "Area m²", "Zone", "Driver"],
        rows,
        col_w=[90, 200, 70, 50, 320],
        max_rows=40,
    )


def a012_doors() -> str:
    s = load_snapshot()
    dw = s.get("doors_windows") or {}
    rows = []
    for d in dw.get("doors") or []:
        rows.append([
            d.get("mark"),
            d.get("what"),
            d.get("n"),
            d.get("rating"),
            str(d.get("hw", ""))[:35],
            str(d.get("driver", ""))[:35],
        ])
    for w in dw.get("windows") or []:
        rows.append([
            w.get("mark"),
            w.get("what"),
            w.get("n"),
            "—",
            w.get("where", ""),
            str(w.get("driver", ""))[:35],
        ])
    return table_svg(
        "A-012 SUPPORT PROGRAM + DOOR & WINDOW SCHEDULE (derived)",
        ["Mark", "Description", "N", "Rating", "HW / where", "Driver"],
        rows,
        col_w=[60, 240, 40, 100, 180, 200],
    )


def a013_door_leaves() -> str:
    s = load_snapshot()
    rows = []
    for d in s.get("door_instances") or []:
        if isinstance(d, dict):
            rows.append([
                d.get("mark") or d.get("id"),
                d.get("type") or d.get("what"),
                d.get("w_mm") or d.get("width"),
                d.get("h_mm") or d.get("height"),
                d.get("rating") or d.get("fire"),
                d.get("hw_set") or d.get("hardware") or "—",
                d.get("room") or d.get("from_to") or "—",
            ])
    if not rows:
        return a012_doors()
    return table_svg(
        "A-013 DOOR LEAF SCHEDULE + HARDWARE SETS (derived)",
        ["Mark", "Type", "W", "H", "Rating", "HW set", "Location"],
        rows,
        col_w=[70, 180, 50, 50, 80, 120, 160],
        max_rows=40,
    )


def k_connections_doc() -> str:
    s = load_snapshot()
    lines = ["CONNECTION KEYNOTES K1–K10 (module_basis)", ""]
    for c in s.get("module_connections") or []:
        if isinstance(c, (list, tuple)) and len(c) >= 3:
            lines.append(f"{c[0]} — {c[1]}")
            lines.append(f"    {c[2]}")
            lines.append("")
    return bullets_svg("MODULE CONNECTION KEYNOTES", lines)
