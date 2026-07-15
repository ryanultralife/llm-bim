"""CSI MasterFormat-style cost codes for BOQ divisions."""

from __future__ import annotations

from typing import Any

# CSI 2018-ish divisions used in takeoff
CSI_DIVISIONS: dict[str, str] = {
    "00": "Procurement and Contracting",
    "01": "General Requirements",
    "02": "Existing Conditions",
    "03": "Concrete",
    "04": "Masonry",
    "05": "Metals",
    "06": "Wood, Plastics, and Composites",
    "07": "Thermal and Moisture Protection",
    "08": "Openings",
    "09": "Finishes",
    "10": "Specialties",
    "11": "Equipment",
    "12": "Furnishings",
    "13": "Special Construction",
    "14": "Conveying Equipment",
    "21": "Fire Suppression",
    "22": "Plumbing",
    "23": "HVAC",
    "25": "Integrated Automation",
    "26": "Electrical",
    "27": "Communications",
    "28": "Electronic Safety and Security",
    "31": "Earthwork",
    "32": "Exterior Improvements",
    "33": "Utilities",
    "40": "Process Interconnections",
    "41": "Material Processing and Handling Equipment",
    "42": "Process Heating, Cooling, and Drying",
    "43": "Process Gas and Liquid Handling",
    "44": "Pollution and Waste Control Equipment",
    "46": "Water and Wastewater Equipment",
}

# Common section codes for agent lookup
CSI_SECTIONS: dict[str, str] = {
    "03 20 00": "Concrete Reinforcing",
    "03 30 00": "Cast-in-Place Concrete",
    "04 20 00": "Unit Masonry",
    "04 22 00": "Concrete Unit Masonry",
    "05 12 00": "Structural Steel Framing",
    "05 12 23": "Structural Steel for Buildings (bolts)",
    "05 31 00": "Steel Decking",
    "05 50 00": "Metal Fabrications",
    "06 10 00": "Rough Carpentry",
    "06 16 00": "Sheathing",
    "06 60 00": "Plastic Fabrications",
    "07 21 00": "Thermal Insulation",
    "08 11 00": "Metal Doors and Frames",
    "08 11 13": "Hollow Metal Doors and Frames",
    "08 50 00": "Windows",
    "09 21 00": "Plaster and Gypsum Board",
    "09 22 16": "Non-Structural Metal Framing",
    "09 66 00": "Terrazzo Flooring",
    "10 28 13": "Toilet Accessories",
    "10 44 00": "Fire Protection Specialties",
    "11 00 00": "Equipment",
    "11 90 00": "Facility Maintenance Equipment",
    "13 49 00": "Radiation Protection",
    "21 12 00": "Fire-Suppression Standpipes",
    "21 13 13": "Wet-Pipe Sprinkler Systems",
    "22 11 16": "Domestic Water Piping",
    "22 11 19": "Domestic Water Piping Specialties",
    "22 13 00": "Facility Sanitary Sewerage",
    "22 13 16": "Sanitary Waste and Vent Piping",
    "22 33 00": "Electric Domestic Water Heaters",
    "22 34 00": "Fuel-Fired Domestic Water Heaters",
    "22 40 00": "Plumbing Fixtures",
    "22 47 00": "Drinking Fountains and Water Coolers",
    "23 31 00": "HVAC Ducts and Casings",
    "23 36 00": "Air Terminal Units",
    "23 37 00": "Air Outlets and Inlets",
    "23 51 00": "Breechings, Chimneys, and Stacks",
    "26 05 19": "Low-Voltage Electrical Power Conductors",
    "26 05 33": "Raceway and Boxes",
    "26 24 16": "Panelboards",
    "26 27 26": "Wiring Devices",
    "26 51 00": "Interior Lighting",
    "33 11 00": "Water Utility Distribution Piping",
    "40 05 00": "Common Work Results for Process",
    "40 05 13": "Process Piping",
    "43 41 00": "Storage Tanks and Process Vessels",
}

# Map wall type / category → CSI section
CATEGORY_CSI: dict[str, str] = {
    "wall": "04 20 00",
    "slab": "03 30 00",
    "door": "08 11 00",
    "window": "08 50 00",
    "room": "01 22 00",
    "equipment": "11 00 00",
    "note": "01 31 00",
    "grid": "01 32 00",
    "fitting": "22 11 16",
    "pipe": "22 11 16",
    "plumbing_pipe": "22 11 16",
    "fixture": "22 40 00",
    "accessory": "10 28 13",
    "fire_protection": "21 13 13",
    "process_piping": "40 05 13",
    "framing": "06 10 00",
    "structural_steel": "05 12 00",
    "rebar": "03 20 00",
    "hvac": "23 31 00",
    "electrical": "26 05 00",
    "structural": "05 12 00",
    "plumbing": "22 11 16",
    "process": "40 05 00",
    "envelope": "04 20 00",
}

TYPE_CSI: dict[str, str] = {
    "W-EXT-CMU": "04 22 00",
    "W-INT-GYP": "09 21 00",
    "W-SHIELD-CONC": "03 30 00",
    "W-GENERIC-200": "04 20 00",
    "D-HM-36": "08 11 13",
    "D-HM-72": "08 11 13",
    "D-SHIELD-PLUG": "13 49 00",
    "separator_vessel_size_b": "43 41 00",
    "shell": "40 05 00",
    "cartridge": "43 41 00",
    "magnet": "11 90 00",
    "yoke": "05 12 00",
    "flange": "40 05 13",
    "pedestal": "05 50 00",
    "stack": "23 51 00",
    "step_ref": "11 00 00",
    "toilet": "22 40 00",
    "tp_dispenser": "10 28 13",
    "sprinkler_head": "21 13 13",
    "rebar": "03 20 00",
    "wide_flange": "05 12 00",
}


def csi_for_line(row: dict[str, Any]) -> dict[str, str]:
    """Attach CSI code + division to a BOQ line."""
    cat = row.get("category", "")
    type_id = row.get("type_id") or row.get("kind") or ""
    # prefer explicit csi on row or part
    code = (
        row.get("csi_code")
        or TYPE_CSI.get(str(type_id))
        or CATEGORY_CSI.get(cat, "01 00 00")
    )
    # part id lookup
    if code == "01 00 00" or not row.get("csi_code"):
        try:
            from llmbim_core.parts_catalog import get_part

            pid = row.get("part_id") or type_id
            part = get_part(str(pid)) if pid else None
            if part and part.csi_code:
                code = part.csi_code
        except Exception:  # noqa: BLE001
            pass
    div = str(code).split()[0] if code else "01"
    return {
        "csi_code": code,
        "csi_division": div,
        "csi_division_name": CSI_DIVISIONS.get(div, "General"),
        "csi_section_name": CSI_SECTIONS.get(str(code), ""),
    }


def annotate_boq_with_csi(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        rr = dict(r)
        rr.update(csi_for_line(r))
        mats = []
        for m in r.get("materials") or []:
            mats.append(dict(m))
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


def csi_catalog() -> dict[str, Any]:
    return {
        "divisions": CSI_DIVISIONS,
        "sections": CSI_SECTIONS,
        "category_defaults": CATEGORY_CSI,
    }
