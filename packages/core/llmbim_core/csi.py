"""CSI MasterFormat-style cost codes for BOQ divisions."""

from __future__ import annotations

from typing import Any

# Simplified CSI 2018-ish divisions relevant to BIM takeoff
CSI_DIVISIONS: dict[str, str] = {
    "01": "General Requirements",
    "02": "Existing Conditions",
    "03": "Concrete",
    "04": "Masonry",
    "05": "Metals",
    "06": "Wood, Plastics, and Composites",
    "07": "Thermal and Moisture Protection",
    "08": "Openings",
    "09": "Finishes",
    "11": "Equipment",
    "13": "Special Construction",
    "21": "Fire Suppression",
    "22": "Plumbing",
    "23": "HVAC",
    "26": "Electrical",
    "31": "Earthwork",
    "32": "Exterior Improvements",
    "40": "Process Interconnections",
    "43": "Process Gas and Liquid Handling",
    "44": "Pollution and Waste Control Equipment",
    "46": "Water and Wastewater Equipment",
}

# Map wall type / category → CSI section
CATEGORY_CSI: dict[str, str] = {
    "wall": "04 20 00",
    "slab": "03 30 00",
    "door": "08 11 00",
    "window": "08 50 00",
    "room": "01 22 00",  # unit prices / measurement
    "equipment": "11 00 00",
    "note": "01 31 00",
    "grid": "01 32 00",
    "fitting": "22 11 16",
    "pipe": "22 11 16",
    "plumbing_pipe": "22 11 16",
}

TYPE_CSI: dict[str, str] = {
    "W-EXT-CMU": "04 22 00",
    "W-INT-GYP": "09 21 00",
    "W-SHIELD-CONC": "03 30 00",
    "W-GENERIC-200": "04 20 00",
    "D-HM-36": "08 11 13",
    "D-HM-72": "08 11 13",
    "D-SHIELD-PLUG": "13 49 00",  # radiation protection
    "separator_vessel_size_b": "43 41 00",
    "shell": "40 05 00",
    "cartridge": "43 41 00",
    "magnet": "11 90 00",
    "yoke": "05 12 00",
    "flange": "40 05 13",
    "pedestal": "05 50 00",
    "stack": "23 51 00",
    "step_ref": "11 00 00",
}


def csi_for_line(row: dict[str, Any]) -> dict[str, str]:
    """Attach CSI code + division to a BOQ line."""
    cat = row.get("category", "")
    type_id = row.get("type_id") or row.get("kind") or ""
    code = TYPE_CSI.get(str(type_id)) or CATEGORY_CSI.get(cat, "01 00 00")
    div = code.split()[0] if code else "01"
    return {
        "csi_code": code,
        "csi_division": div,
        "csi_division_name": CSI_DIVISIONS.get(div, "General"),
    }


def annotate_boq_with_csi(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        rr = dict(r)
        rr.update(csi_for_line(r))
        # also tag materials if present
        mats = []
        for m in r.get("materials") or []:
            mm = dict(m)
            mats.append(mm)
        rr["materials"] = mats
        out.append(rr)
    return out


def boq_by_csi_division(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Roll up estimated cost by CSI division."""
    by: dict[str, dict[str, Any]] = {}
    for r in rows:
        if "csi_division" not in r:
            r = {**r, **csi_for_line(r)}
        div = r["csi_division"]
        bucket = by.setdefault(
            div,
            {
                "division": div,
                "name": r.get("csi_division_name", ""),
                "est_cost": 0.0,
                "lines": 0,
            },
        )
        bucket["est_cost"] += float(r.get("est_cost") or 0)
        bucket["lines"] += 1
    for b in by.values():
        b["est_cost"] = round(b["est_cost"], 2)
    return dict(sorted(by.items()))
