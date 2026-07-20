"""Construction BOM / quantity takeoff from Schad basis (bid-ready tables).

Design-support quantities — not a sealed estimate. Unit costs optional/blank
for contractor pricing.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import schad_design_basis as basis


def _perimeter_ft() -> float:
    fp = basis.footprint()
    peri = 0.0
    for i in range(len(fp)):
        x1, y1 = fp[i]
        x2, y2 = fp[(i + 1) % len(fp)]
        peri += math.hypot(x2 - x1, y2 - y1)
    return peri


def _wall_areas() -> dict[str, float]:
    """Approx wall SF by kind (length * height)."""
    areas: dict[str, float] = {}
    for w in basis.build_walls():
        L = math.hypot(w["x2"] - w["x1"], w["y2"] - w["y1"])
        a = L * w["height"]
        k = w.get("kind", "other")
        areas[k] = areas.get(k, 0.0) + a
    return areas


def bom_lines() -> list[dict[str, Any]]:
    s = basis.build_scalars()
    peri = _perimeter_ft()
    wa = _wall_areas()
    ext_sf = sum(v for k, v in wa.items() if "exterior" in k or "fire" in k)
    int_sf = sum(v for k, v in wa.items() if "interior" in k)
    lines: list[dict[str, Any]] = []

    def add(div: str, item: str, qty: float, unit: str, note: str = "", csi: str = ""):
        lines.append(
            {
                "csi": csi,
                "division": div,
                "item": item,
                "qty": round(qty, 1) if isinstance(qty, float) else qty,
                "unit": unit,
                "note": note,
            }
        )

    # 03 Concrete
    ftg_cy = peri * (s["footing_w"] * s["footing_d"]) / 27.0
    slab_g = s["area_garage"] * s["slab_garage_t"] / 27.0
    slab_a = s["area_adu"] * s["slab_adu_t"] / 27.0
    add("03", "Strip footing concrete", ftg_cy, "CY", "18x12 continuous", "03 30 00")
    add("03", "Point footing 36x36x30", 4, "EA", "Under HSS posts", "03 30 00")
    add("03", "SSW pad 24x26x18", 6, "EA", "Under Strong-Walls", "03 30 00")
    add("03", "Stem wall concrete", peri * 0.5 * 0.67 / 27.0, "CY", "approx 6-8\" x 8\"", "03 30 00")
    add("03", "Garage slab 4\"", slab_g, "CY", f"{s['area_garage']:.0f} SF", "03 30 00")
    add("03", "ADU slab 3\"", slab_a, "CY", f"{s['area_adu']:.0f} SF", "03 30 00")
    add("03", "Vapor barrier 10-mil", s["area_total"] * 1.1, "SF", "+10% waste", "03 30 00")
    add("03", "Gravel base 4\"", s["area_total"] * 0.33 / 27.0, "CY", "under slabs", "31 20 00")
    add("03", "Rebar #4 continuous (2)", peri * 2, "LF", "strip ftg", "03 20 00")
    add("03", "Fiber mesh / WWF", s["area_garage"], "SF", "garage slab", "03 20 00")

    # 05 Metals
    beam_lf = 2 * (s["main_W"] + s["rear_W"])  # full depth per basis beams
    add("05", "W16x40 beam A992", beam_lf, "LF", "2 beams", "05 12 00")
    add("05", "HSS 6x6x1/4 column", 4 * s["plate_main"], "LF", "4 posts @ ~plate height", "05 12 00")
    add("05", "Base plate 8x8x1", 4, "EA", "with (4) 3/4 AB", "05 12 00")
    add("05", "Cap plate 1/2\"", 4, "EA", "beam bearing", "05 12 00")
    add("05", "Simpson SSW24x9", 4, "EA", "Bays 1 & 3", "05 12 00")
    add("05", "Simpson SSW24x12", 2, "EA", "Bay 2", "05 12 00")
    add("05", "HDU hold-downs", 12, "EA", "ASSUMED 2 per SSW — EOR", "05 12 00")
    add("05", "Anchor bolts 5/8\"", peri / 6.0, "EA", "@ 6'-0\" OC perimeter", "05 50 00")

    # 06 Wood
    stud_ext = ext_sf / (s["plate_main"] * (16 / 12))  # rough stud count
    add("06", "2x6 DF-L studs @ 16\" OC", max(stud_ext, 1), "EA", "ext walls approx", "06 10 00")
    add("06", "2x4 DF-L studs @ 16\" OC", max(int_sf / (s["plate_main"] * 1.33), 1), "EA", "int partitions", "06 10 00")
    add("06", "PT sill plate", peri, "LF", "ext", "06 10 00")
    add("06", "Double top plate", peri * 1.2, "LF", "ext+int", "06 10 00")
    add("06", "LVL 1.75x16 header", 3 * 12, "LF", "3 OH door openings", "06 17 00")
    add("06", "4x8 DF header", 4 * 4, "LF", "man doors/windows", "06 10 00")
    add("06", "Roof trusses 24\" OC", s["main_L"] / 2.0 + 1, "EA", "DEFERRED FAB SUBMITTAL", "06 17 53")
    add("06", "5/8\" DF structural siding", ext_sf * 1.1, "SF", "shear layer +10%", "06 16 00")
    add("06", "1x3 battens @ 16\" OC", ext_sf / (16 / 12) * 1.1, "LF", "board-and-batten", "06 20 00")

    # 07 Thermal / moisture
    add("07", "R-21 batt wall insulation", ext_sf, "SF", "cavity", "07 21 00")
    add("07", "R-38 ceiling insulation", s["area_total"], "SF", "", "07 21 00")
    add("07", "R-10 under-slab (ADU)", s["area_adu"], "SF", "", "07 21 00")
    add("07", "R-15 slab edge", peri, "LF", "", "07 21 00")
    add("07", "WRB housewrap", ext_sf * 1.1, "SF", "", "07 25 00")
    add("07", "Standing-seam 24ga metal roof", s["area_total"] * 1.15, "SF", "charcoal + waste", "07 41 13")
    add("07", "Ice & water shield", s["area_total"] * 0.4, "SF", "eaves/valleys min", "07 30 00")
    add("07", "1x6 T&G pine soffit", peri * 1.5, "SF", "18\" eaves/rakes approx", "07 46 00")

    # 08 Openings
    add("08", "OH door 12x9 insulated glass", 2, "EA", "D1, D3", "08 36 00")
    add("08", "OH door 12x12 insulated glass", 1, "EA", "D2", "08 36 00")
    add("08", "Entry door 3-0 solid core ADA", 1, "EA", "D4 ADU", "08 11 00")
    add("08", "Entry door 3-0 solid core", 1, "EA", "D5 workshop", "08 11 00")
    add("08", "HM door 2-6", 1, "EA", "D6 fire sep 20-min", "08 11 00")
    add("08", "Vinyl casement 4x4 U≤0.30", 4, "EA", "W1-W4 (Q-WIN)", "08 52 00")

    # 09 Finishes
    add("09", "5/8\" Type X gyp 1-hr sep", s["rear_L"] * s["plate_rear_high"] * 2, "SF", "both sides fire wall", "09 29 00")
    add("09", "5/8\" gyp ADU interior", s["area_adu"] * 3.5, "SF", "walls+ceiling approx", "09 29 00")

    # 22 / 23 / 26
    rad = 1850 + s["area_adu"]
    add("22", "1/2\" PEX radiant", rad / 0.75, "LF", "9\" OC", "22 07 00")
    add("22", "Radiant manifold loops", int(rad / 0.75 // 300) + 1, "EA", "", "22 07 00")
    add("22", "Plumbing fixtures package", len(basis.plumbing_fixtures()), "LOT", "ADU+mech", "22 40 00")
    add("23", "Propane boiler sealed comb.", 2, "EA", "B-1/B-2", "23 52 00")
    add("23", "Tankless propane WH + buffer", 1, "EA", "WH-1", "22 34 00")
    add("23", "Well pressure vessel 60-gal", 1, "EA", "PT-1", "22 12 00")
    add("26", "200A service equipment", 1, "LOT", "Panel A", "26 24 00")
    add("26", "100A ADU subpanel", 1, "EA", "", "26 24 00")
    add("26", "EV NEMA 14-50 circuit", 1, "EA", "", "26 05 00")
    add("26", "LED high-bay / lighting package", 1, "LOT", "garage+soffit", "26 51 00")

    return lines


def write_bom(out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = bom_lines()
    csv_path = out_dir / "BOM_TAKEOFF.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["csi", "division", "item", "qty", "unit", "note"])
        w.writeheader()
        w.writerows(lines)
    json_path = out_dir / "BOM_TAKEOFF.json"
    json_path.write_text(json.dumps(lines, indent=2), encoding="utf-8")
    # markdown
    md = [
        "# SCHAD Bill of Materials / Quantity Takeoff",
        "",
        "> Design-support takeoff from basis geometry. Not a sealed estimate. "
        "Contractor to verify. Waste factors partial.",
        "",
        "| CSI | Div | Item | Qty | Unit | Note |",
        "|-----|-----|------|-----|------|------|",
    ]
    for L in lines:
        md.append(
            f"| {L['csi']} | {L['division']} | {L['item']} | {L['qty']} | {L['unit']} | {L['note']} |"
        )
    md_path = out_dir / "BOM_TAKEOFF.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return {"csv": csv_path, "json": json_path, "md": md_path}
