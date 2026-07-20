"""SCHAD construction engineering package — design-support calculations.

Expands structural + MEP + foundation + connections into stamped-ready
*content* (tables, DCRs, schedules). NOT a PE seal — EOR must review.

Produces markdown + JSON under an out/engineering folder.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import schad_design_basis as basis
import schad_mep as mep
import schad_structural as struct

DISCLAIMER = (
    "DESIGN-SUPPORT ENGINEERING PACKAGE — Prepared for construction "
    "documentation development by Ledger Built LLC / Ryan Vukich. "
    "NOT a substitute for California-licensed Structural Engineer (EOR) "
    "stamp. Values marked (ASSUMED) require confirmation. Geotech, "
    "site-specific seismic (SDS), and truss fabricator calcs are deferred "
    "submittals. NOT FOR CONSTRUCTION until PE-approved."
)


def _ok(flag: bool) -> str:
    return "OK" if flag else "NG — REVISE"


# ---------------------------------------------------------------------------
# Structural engineering depth
# ---------------------------------------------------------------------------
def load_criteria() -> dict[str, Any]:
    s = basis.build_scalars()
    return {
        "code": "2022 CBC / ASCE 7-16 (reference) — confirm AHJ edition",
        "occupancy": "U (garage/workshop) + R-3 (ADU) with 1-hr separation",
        "risk_category": "II",
        "snow_psf": struct.SNOW_PSF,
        "snow_source": "[RB] framing notes — 75 psf ground/roof as published",
        "roof_dl_psf": struct.ROOF_DL_PSF,
        "roof_dl_note": "(ASSUMED) metal + truss + insulation",
        "floor_ll_garage_psf": 50.0,  # CBC residential garage often 50
        "floor_ll_note": "Garage LL 40–50 psf class; use 50 for slab design support",
        "wall_dl_psf": struct.WALL_DL_PSF,
        "wind_V_mph": struct.WIND_V_MPH,
        "wind_note": "(ASSUMED) Exp C — confirm Exposure + topographic",
        "seismic_SDS": struct.SDS,
        "seismic_note": "(ASSUMED) SDC D, SDS=1.0 — replace w/ site-specific",
        "R_system": struct.R_WOOD_SW,
        "R_note": "Light-frame wood shear walls (wood structural panels)",
        "soil_q_allow_psf": struct.SOIL_Q_ALLOW_PSF,
        "soil_note": "CBC 1806.2 presumptive 1500 psf (ASSUMED) — geotech supersedes",
        "frost": "Plumas County frost depth — verify w/ building dept (ASSUMED 18\" min ftg)",
        "area_sf": s["area_total"],
        "ridge_ft": s["ridge"],
        "pitch": "6:12",
    }


def wind_check() -> dict[str, Any]:
    """Simplified MWFRS / components design-support only."""
    V = struct.WIND_V_MPH
    # qz = 0.00256 Kz Kzt Kd V^2 — use Kz~0.85 Exp C 15-20', Kzt=1, Kd=0.85
    qz = 0.00256 * 0.85 * 1.0 * 0.85 * V * V  # psf
    # rough wall C&C GCp ~ ±1.0 → p ~ qz
    p_wall = qz * 1.0
    p_roof = qz * 1.5  # higher for roof corners (order-of-magnitude)
    s = basis.build_scalars()
    # lateral wind force on long wall ~ p * height * length / 1000
    F_k = p_wall * s["plate_main"] * s["main_L"] / 1000.0
    return {
        "method": "Simplified ASCE-style velocity pressure (ASSUMED coefficients)",
        "V_mph": V,
        "qz_psf": round(qz, 1),
        "p_wall_psf": round(p_wall, 1),
        "p_roof_psf": round(p_roof, 1),
        "approx_long_wall_force_k": round(F_k, 1),
        "note": "EOR to run full MWFRS + C&C; SSW + diaphragm design for wind + seismic",
        "ok": True,
    }


def header_checks() -> list[dict[str, Any]]:
    """Order-of-magnitude header checks for OH doors + man doors."""
    # Rough: (2) 1.75x16 LVL for 12' opening, trib ~2' roof+wall
    snow = struct.SNOW_PSF
    trib = 2.0  # ft (ASSUMED header trib)
    span = 12.0
    w = (snow + struct.ROOF_DL_PSF) * trib  # plf
    M = w * span**2 / 8.0 / 1000.0  # k-ft
    # (2) 1.75x16 LVL Fb~2800 psi approx, S ~ 2 * (1.75*16^2/6) = 149 in3
    S = 2 * (1.75 * 16**2 / 6.0)
    Fb = 2800.0  # psi (ASSUMED LVL)
    Mallow = Fb * S / 12.0 / 1000.0  # k-ft
    oh = {
        "mark": "HDR-2",
        "member": "(2) 1.75x16 LVL",
        "span_ft": span,
        "trib_ft": trib,
        "w_plf": round(w),
        "M_kft": round(M, 2),
        "M_allow_kft": round(Mallow, 1),
        "DCR": round(M / Mallow, 2) if Mallow else 99,
        "ok": M <= Mallow,
        "note": "Verify with SSW jack geometry + manufacturer; EOR final",
    }
    # man door 4x8 DF
    span2 = 3.0
    w2 = 50.0  # plf wall above (ASSUMED)
    M2 = w2 * span2**2 / 8.0 / 1000.0
    S2 = 3.5 * 7.25**2 / 6.0  # 4x8 approx
    Mallow2 = 900 * S2 / 12.0 / 1000.0  # Fb~900 #2 DF rough
    man = {
        "mark": "HDR-1",
        "member": "4x8 DF#2",
        "span_ft": span2,
        "w_plf": w2,
        "M_kft": round(M2, 3),
        "M_allow_kft": round(Mallow2, 2),
        "DCR": round(M2 / Mallow2, 2) if Mallow2 else 99,
        "ok": M2 <= Mallow2,
        "note": "Opening <= 4'-0\"; king/jack studs per CRC",
    }
    return [oh, man]


def rebar_schedule() -> list[dict[str, Any]]:
    s = basis.build_scalars()
    # perimeter approx from footprint
    fp = basis.footprint()
    peri = 0.0
    for i in range(len(fp)):
        x1, y1 = fp[i]
        x2, y2 = fp[(i + 1) % len(fp)]
        peri += math.hypot(x2 - x1, y2 - y1)
    # (2) #4 continuous
    bar_lf = peri * 2
    # point pads 4x at bay lines approx (4 posts * 4 bars * 3' each rough)
    pad_lf = 4 * 4 * 3.0
    # SSW pads (3) #4 EW each — 6 pads * 6 lf rough
    ssw_lf = 6 * 6.0
    return [
        {
            "mark": "R1",
            "size": "#4",
            "location": "Strip footing continuous (2) bars",
            "length_lf": round(bar_lf, 0),
            "note": f"Perimeter ~{peri:.0f}' x 2 bars",
        },
        {
            "mark": "R2",
            "size": "#4",
            "location": "Point footings 36x36 — (4) EW bottom each",
            "length_lf": round(pad_lf, 0),
            "note": "4 pads under beam posts",
        },
        {
            "mark": "R3",
            "size": "#4",
            "location": "SSW pads 24x26x18 — (3) EW each",
            "length_lf": round(ssw_lf, 0),
            "note": "6 SSW stations",
        },
        {
            "mark": "R4",
            "size": "WWF or fiber",
            "location": "Garage slab 4\"",
            "length_lf": 0,
            "note": f"Fiber mesh per BOM; alt 6x6-W2.9xW2.9 — area {s['area_garage']:.0f} SF",
        },
    ]


def connection_schedule() -> list[dict[str, Any]]:
    return [
        {
            "id": "C-01",
            "location": "W16x40 to HSS6x6 cap",
            "hardware": "1/2\" cap plate; (4) 3/4\" A325; stiffeners if EOR requires",
            "detail": "D07",
        },
        {
            "id": "C-02",
            "location": "HSS base to point footing",
            "hardware": "Base PL 8x8x1; (4) 3/4\" AB; 1\" non-shrink grout",
            "detail": "D07",
        },
        {
            "id": "C-03",
            "location": "SSW to pad / sill",
            "hardware": "SSTB anchors per ESR-2652; HDU hold-downs per BOM",
            "detail": "D06",
        },
        {
            "id": "C-04",
            "location": "Shed curb to main wall",
            "hardware": "CS16 strap each stud; self-adhered flashing min 6\"",
            "detail": "D02",
        },
        {
            "id": "C-05",
            "location": "Bay-2 plate step shear transfer",
            "hardware": "CS16 strap main dbl plate to bay studs; fire block",
            "detail": "D05",
        },
        {
            "id": "C-06",
            "location": "Valley overlay",
            "hardware": "2x8 valley plates; ice & water; 24ga W-flashing",
            "detail": "D03",
        },
        {
            "id": "C-07",
            "location": "OH door header",
            "hardware": "(2) 1.75x16 LVL; trimmers per SSW; track block per mfr",
            "detail": "D10",
        },
        {
            "id": "C-08",
            "location": "Sill / stem",
            "hardware": "5/8\" AB @ 6'-0\" OC; PT sill; foam sill seal",
            "detail": "D01",
        },
        {
            "id": "C-09",
            "location": "Structural siding nailing",
            "hardware": "Edge nailing schedule per EOR; SS fasteners for battens",
            "detail": "D12",
        },
        {
            "id": "C-10",
            "location": "1-hr garage/ADU penetrations",
            "hardware": "Fire caulk; 20-min self-closing D6",
            "detail": "D08",
        },
    ]


def ssw_schedule() -> list[dict[str, Any]]:
    rows = []
    for sw in basis.build_structure()["strong_walls"]:
        model = sw["model"]
        cap = struct.SSW_ASD_LB.get(model, 0)
        rows.append(
            {
                "id": sw["id"],
                "model": model,
                "x_ft": sw["x"],
                "y_ft": sw["y"],
                "height_ft": sw["h"],
                "asd_capacity_lb": cap,
                "pos_assumed": sw.get("pos_assumed", True),
                "anchors": "SSTB per ESR-2652 — EOR verify embed/edge",
                "hold_down": "HDU series per Simpson / BOM",
            }
        )
    return rows


def structural_engineering_report() -> str:
    lc = load_criteria()
    b, p = struct.beam_check(), struct.post_check()
    sf, pf = struct.strip_footing_check(), struct.point_footing_check()
    lt = struct.lateral_check()
    wind = wind_check()
    headers = header_checks()
    lines = [
        "# SCHAD Structural Engineering Package",
        "",
        f"**Project:** 2024-008 SCHAD Garage/ADU/Workshop",
        f"**Address:** 3730 Chandler Rd, Quincy CA 95971",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"> {DISCLAIMER}",
        "",
        "## 1. Design criteria",
        "",
    ]
    for k, v in lc.items():
        lines.append(f"- **{k}:** {v}")
    lines += [
        "",
        "## 2. Gravity — steel beam (W16x40)",
        "",
        f"- Member: {b['member']}",
        f"- Span: {b['span_ft']} ft · Tributary: {b['trib_ft']} ft",
        f"- Uniform load w = {b['w_plf']} plf (snow+DL+self)",
        f"- Moment M = {b['M_kft']} k-ft vs allow {b['M_allow_kft']} k-ft · **DCR {b['DCR']} → {_ok(b['ok'])}**",
        f"- Deflection (snow): {b['defl_in']}\" vs L/240 = {b['defl_limit_in']}\" · {_ok(b['defl_in'] <= b['defl_limit_in'])}",
        f"- Quantity: 2 beams (bay lines B & C) full depth incl. rear shed band",
        "",
        "## 3. Columns — HSS 6x6x1/4",
        "",
        f"- Axial P = {p['P_k']} k vs allow {p['P_allow_k']} k · **DCR {p['DCR']} → {_ok(p['ok'])}**",
        f"- Quantity: 4 posts (beam ends) · base PL 8x8x1 · 36x36x30 pads",
        "",
        "## 4. Foundations",
        "",
        f"- Strip 18\"x12\": {sf['load_plf']} plf → q = {sf['q_psf']} psf ≤ {sf['q_allow_psf']} · {_ok(sf['ok'])}",
        f"- Record bearing note: {sf['record_plf']} plf · SF_record {sf['SF_record']}",
        f"- Point 36x36: q = {pf['q_psf']} psf ≤ {pf['q_allow_psf']} · {_ok(pf['ok'])}",
        f"- Stem: 8\" front / 6\" typ · AB 5/8\" @ 6'-0\" OC",
        f"- Rebar: see rebar schedule (R1–R4)",
        "",
        "## 5. Lateral (seismic ELF — simplified)",
        "",
        f"- Seismic weight W ≈ {lt['W_k']} k · Cs = {lt['Cs']} · Base shear V = {lt['V_k']} k",
        f"- Front-line demand {lt['v_front_k']} k vs SSW capacity {lt['cap_front_k']} k · **DCR {lt['DCR']} → {_ok(lt['ok'])}**",
        f"- System: Simpson SSW + 5/8\" DF structural siding diaphragm/shear skin",
        f"- **EOR must** complete full ELF/RSA, N-S line, hold-down design, diaphragm nailing",
        "",
        "## 6. Wind (order-of-magnitude)",
        "",
        f"- V = {wind['V_mph']} mph · qz ≈ {wind['qz_psf']} psf · wall p ≈ {wind['p_wall_psf']} psf",
        f"- Approx long-wall force ~ {wind['approx_long_wall_force_k']} k",
        f"- {wind['note']}",
        "",
        "## 7. Headers",
        "",
    ]
    for h in headers:
        lines.append(
            f"- **{h['mark']}** {h['member']}: M={h['M_kft']} / allow {h['M_allow_kft']} "
            f"· DCR {h['DCR']} → {_ok(h['ok'])} — {h['note']}"
        )
    lines += [
        "",
        "## 8. Strong-Wall schedule",
        "",
        "| ID | Model | X | Y | H | ASD (lb) | Anchors |",
        "|----|-------|---|---|---|----------|---------|",
    ]
    for sw in ssw_schedule():
        lines.append(
            f"| {sw['id']} | {sw['model']} | {sw['x_ft']} | {sw['y_ft']} | "
            f"{sw['height_ft']} | {sw['asd_capacity_lb']} | {sw['anchors'][:40]} |"
        )
    lines += [
        "",
        "## 9. Rebar schedule",
        "",
        "| Mark | Size | Location | LF | Note |",
        "|------|------|----------|----|------|",
    ]
    for r in rebar_schedule():
        lines.append(
            f"| {r['mark']} | {r['size']} | {r['location']} | {r['length_lf']} | {r['note']} |"
        )
    lines += [
        "",
        "## 10. Connection schedule",
        "",
        "| ID | Location | Hardware | Detail |",
        "|----|----------|----------|--------|",
    ]
    for c in connection_schedule():
        lines.append(
            f"| {c['id']} | {c['location']} | {c['hardware']} | {c['detail']} |"
        )
    lines += [
        "",
        "## 11. Deferred submittals (required before erection)",
        "",
        "1. **Roof trusses** — fabricator sealed calcs (scissor / modified / shed) @ 75 psf snow",
        "2. **Simpson SSW** final anchorage layout + hold-downs — EOR",
        "3. **Geotechnical** — allowable bearing / frost / seismic site class",
        "4. **Site-specific SDS / wind exposure** — PE",
        "",
        "## 12. Structural notes for S-sheets",
        "",
    ]
    for n in struct.structural_notes():
        lines.append(f"- {n}")
    lines += ["", "---", f"*{DISCLAIMER}*"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# MEP engineering depth
# ---------------------------------------------------------------------------
def propane_load() -> dict[str, Any]:
    # Rough BTU: 2 boilers ~80 MBH each + tankless ~180 MBH peak
    boiler_mbh = 52.0 * 2  # from mech calc order of magnitude
    tankless_mbh = 180.0
    peak = boiler_mbh + tankless_mbh  # coincident peak ASSUMED worst-case
    # 1 CF propane ~ 2500 BTU
    cfh = peak * 1000 / 2500
    return {
        "boilers_mbh_combined": boiler_mbh,
        "tankless_mbh": tankless_mbh,
        "peak_mbh_assumed": peak,
        "approx_cfh": round(cfh, 0),
        "tank": "Existing 250-gal (expandable) [USER]",
        "note": "Verify vaporization rate + regulator/line size for peak; lead/lag boilers reduce coincident demand",
        "ok": True,
    }


def radiant_design() -> dict[str, Any]:
    s = basis.build_scalars()
    gar = 1850.0
    adu = s["area_adu"]
    total = gar + adu
    pex_lf = total / 0.75  # 9" OC
    loops = int(pex_lf // 300) + 1
    loss = total * 25.0  # BTU/h
    return {
        "garage_sf": gar,
        "adu_sf": adu,
        "total_sf": total,
        "pex_spacing_in": 9,
        "pex_size": "1/2\"",
        "pex_lf": round(pex_lf),
        "loops": loops,
        "max_loop_ft": 300,
        "design_loss_btuh": round(loss),
        "design_loss_mbh": round(loss / 1000, 1),
        "source": "Propane boilers B-1/B-2 lead/lag [USER 2026-07-13]",
        "manifold": "Steel w/ flow meters in Mech/Bath",
        "under_slab_R": "R-10 ADU; R-15 edge",
        "note": "Manual-J recommended before final boiler sizing",
    }


def mep_engineering_report() -> str:
    svc = mep.electrical_service_calc()
    plumb = mep.plumbing_calc()
    mech = mep.mechanical_calc()
    prop = propane_load()
    rad = radiant_design()
    panel = basis.electrical_panel()
    lines = [
        "# SCHAD MEP Engineering Package",
        "",
        f"**Project:** 2024-008 SCHAD · Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"> {DISCLAIMER}",
        "",
        "## 1. Electrical service (NEC 220 design-support)",
        "",
    ]
    for s in svc:
        lines.append(f"- {s}")
    lines += [
        "",
        "### Panel A schedule (excerpt from basis)",
        "",
        "| CKT | Description | A |",
        "|-----|-------------|---|",
    ]
    for ckt, desc, amps in panel:
        lines.append(f"| {ckt} | {desc} | {amps} |")
    lines += [
        "",
        f"- Device count (schematic layout): **{len(mep.electrical_devices())}**",
        "- ADU subpanel 100A · EV 50A · Workshop 30A-240V · Service 200A",
        "",
        "## 2. Plumbing (CPC design-support)",
        "",
    ]
    for s in plumb:
        lines.append(f"- {s}")
    lines += [
        "",
        f"- Fixture count (layout): **{len(mep.plumbing_fixtures_layout())}**",
        "- Mech/Bath: WC, lav, dog wash + floor drains",
        "- ADU: KS, LAV, WC, SHR (ADA)",
        "",
        "## 3. Mechanical / hydronic",
        "",
    ]
    for s in mech:
        lines.append(f"- {s}")
    lines += [
        "",
        "### Radiant design summary",
        "",
        f"- Area: garage {rad['garage_sf']} SF + ADU {rad['adu_sf']} SF = {rad['total_sf']} SF",
        f"- PEX: {rad['pex_size']} @ {rad['pex_spacing_in']}\" OC · ~{rad['pex_lf']} LF · {rad['loops']} loops ≤{rad['max_loop_ft']} ft",
        f"- Design loss ~{rad['design_loss_mbh']} MBH @ 25 BTU/SF (ASSUMED)",
        f"- Source: {rad['source']}",
        f"- {rad['note']}",
        "",
        "### Propane",
        "",
        f"- Boilers combined ~{prop['boilers_mbh_combined']} MBH · tankless ~{prop['tankless_mbh']} MBH",
        f"- Peak (conservative coincident) ~{prop['peak_mbh_assumed']} MBH → ~{prop['approx_cfh']} CFH",
        f"- Tank: {prop['tank']}",
        f"- {prop['note']}",
        "",
        "## 4. Equipment schedule (Mech/Bath)",
        "",
        "| Mark | Equipment | Notes |",
        "|------|-----------|-------|",
    ]
    for eq in mep.mech_equipment_layout():
        lines.append(f"| {eq['sym']} | {eq.get('note', '')[:60]} | @ ({eq['x']}, {eq['y']}) |")
    lines += [
        "",
        "## 5. Code references",
        "",
        "- 2023 CEC / NEC 220 service",
        "- 2022 CPC fixtures, DWV, backflow",
        "- 2022 CMC combustion / venting for sealed propane appliances",
        "- Title 24-2022 energy (forms by energy consultant)",
        "",
        "---",
        f"*{DISCLAIMER}*",
    ]
    return "\n".join(lines) + "\n"


def engineering_json() -> dict[str, Any]:
    return {
        "disclaimer": DISCLAIMER,
        "generated": datetime.now(timezone.utc).isoformat(),
        "load_criteria": load_criteria(),
        "beam": struct.beam_check(),
        "post": struct.post_check(),
        "strip_footing": struct.strip_footing_check(),
        "point_footing": struct.point_footing_check(),
        "lateral": struct.lateral_check(),
        "wind": wind_check(),
        "headers": header_checks(),
        "ssw": ssw_schedule(),
        "rebar": rebar_schedule(),
        "connections": connection_schedule(),
        "radiant": radiant_design(),
        "propane": propane_load(),
        "all_structural_ok": all(
            [
                struct.beam_check()["ok"],
                struct.post_check()["ok"],
                struct.strip_footing_check()["ok"],
                struct.point_footing_check()["ok"],
                struct.lateral_check()["ok"],
            ]
        ),
    }


def write_engineering(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    p1 = out_dir / "STRUCTURAL_ENGINEERING.md"
    p1.write_text(structural_engineering_report(), encoding="utf-8")
    paths["structural"] = p1
    p2 = out_dir / "MEP_ENGINEERING.md"
    p2.write_text(mep_engineering_report(), encoding="utf-8")
    paths["mep"] = p2
    data = engineering_json()
    p3 = out_dir / "engineering_data.json"
    p3.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    paths["json"] = p3
    # CSV exports
    import csv

    def write_csv(name: str, rows: list[dict]) -> Path:
        path = out_dir / name
        if not rows:
            path.write_text("", encoding="utf-8")
            return path
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        return path

    paths["ssw_csv"] = write_csv("ssw_schedule.csv", ssw_schedule())
    paths["rebar_csv"] = write_csv("rebar_schedule.csv", rebar_schedule())
    paths["conn_csv"] = write_csv("connection_schedule.csv", connection_schedule())
    paths["header_csv"] = write_csv("header_checks.csv", header_checks())
    return paths
