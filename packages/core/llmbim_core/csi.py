"""CSI MasterFormat cost codes + instance location locators.

``csi_code`` is a real MasterFormat-style section number (e.g. ``22 11 16``).
``csi_locator`` / position fields let agents *find* the item in the model
(level, plan XY, height/Z) without inventing fake PE seals.
"""

from __future__ import annotations

from typing import Any

from llmbim_core.model import Element, ProjectModel

# CSI MasterFormat 2016/2018-ish divisions
CSI_DIVISIONS: dict[str, str] = {
    "00": "Procurement and Contracting Requirements",
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
    "23": "Heating, Ventilating, and Air Conditioning (HVAC)",
    "25": "Integrated Automation",
    "26": "Electrical",
    "27": "Communications",
    "28": "Electronic Safety and Security",
    "31": "Earthwork",
    "32": "Exterior Improvements",
    "33": "Utilities",
    "40": "Process Interconnections",
    "41": "Material Processing and Handling Equipment",
    "42": "Process Heating, Cooling, and Drying Equipment",
    "43": "Process Gas and Liquid Handling, Purification and Storage Equipment",
    "44": "Pollution and Waste Control Equipment",
    "46": "Water and Wastewater Equipment",
}

# Section titles — keys are canonical "NN NN NN" MasterFormat numbers
CSI_SECTIONS: dict[str, str] = {
    "01 22 00": "Unit Prices",
    "01 31 00": "Project Management and Coordination",
    "01 32 00": "Construction Progress Documentation",
    "03 20 00": "Concrete Reinforcing",
    "03 21 00": "Reinforcing Steel",
    "03 30 00": "Cast-in-Place Concrete",
    "04 20 00": "Unit Masonry",
    "04 22 00": "Concrete Unit Masonry",
    "05 12 00": "Structural Steel Framing",
    "05 12 23": "Structural Steel for Buildings",
    "05 31 00": "Steel Decking",
    "05 50 00": "Metal Fabrications",
    "05 52 00": "Metal Railings",
    "06 10 00": "Rough Carpentry",
    "06 16 00": "Sheathing",
    "06 60 00": "Plastic Fabrications",
    "07 21 00": "Thermal Insulation",
    "08 11 00": "Metal Doors and Frames",
    "08 11 13": "Hollow Metal Doors and Frames",
    "08 50 00": "Windows",
    "09 21 00": "Plaster and Gypsum Board Assemblies",
    "09 22 16": "Non-Structural Metal Framing",
    "09 29 00": "Gypsum Board",
    "09 66 00": "Terrazzo Flooring",
    "10 28 13": "Toilet Accessories",
    "10 28 19": "Toilet, Bath, and Laundry Accessories",
    "10 44 00": "Fire Protection Specialties",
    "10 44 16": "Fire Extinguishers",
    "11 00 00": "Equipment",
    "11 90 00": "Facility Maintenance and Operation Equipment",
    "13 49 00": "Radiation Protection",
    "21 05 00": "Common Work Results for Fire Suppression",
    "21 12 00": "Fire-Suppression Standpipes",
    "21 13 00": "Fire-Suppression Sprinkler Systems",
    "21 13 13": "Wet-Pipe Sprinkler Systems",
    "21 13 16": "Dry-Pipe Sprinkler Systems",
    "22 05 00": "Common Work Results for Plumbing",
    "22 05 19": "Meters and Gages for Plumbing Piping",
    "22 05 23": "General-Duty Valves for Plumbing Piping",
    "22 11 16": "Domestic Water Piping",
    "22 11 19": "Domestic Water Piping Specialties",
    "22 13 00": "Facility Sanitary Sewerage",
    "22 13 16": "Sanitary Waste and Vent Piping",
    "22 13 19": "Sanitary Waste Piping Specialties",
    "22 14 00": "Facility Storm Drainage",
    "22 33 00": "Electric Domestic Water Heaters",
    "22 34 00": "Fuel-Fired Domestic Water Heaters",
    "22 40 00": "Plumbing Fixtures",
    "22 41 00": "Residential Plumbing Fixtures",
    "22 42 00": "Commercial Plumbing Fixtures",
    "22 42 13": "Commercial Water Closets",
    "22 42 16": "Commercial Lavatories and Sinks",
    "22 42 19": "Commercial Urinals",
    "22 47 00": "Drinking Fountains and Water Coolers",
    "23 05 00": "Common Work Results for HVAC",
    "23 31 00": "HVAC Ducts and Casings",
    "23 33 00": "Air Duct Accessories",
    "23 36 00": "Air Terminal Units",
    "23 37 00": "Air Outlets and Inlets",
    "23 51 00": "Breechings, Chimneys, and Stacks",
    "26 05 00": "Common Work Results for Electrical",
    "26 05 19": "Low-Voltage Electrical Power Conductors and Cables",
    "26 05 33": "Raceway and Boxes for Electrical Systems",
    "26 05 36": "Cable Trays for Electrical Systems",
    "26 24 16": "Panelboards",
    "26 27 26": "Wiring Devices",
    "26 51 00": "Interior Lighting",
    "33 11 00": "Water Utility Distribution Piping",
    "40 05 00": "Common Work Results for Process Interconnections",
    "40 05 13": "Process Piping",
    "40 05 23": "Process Valves",
    "40 05 33": "Process Pipe Hangers and Supports",
    "43 41 00": "Storage Tanks and Process Vessels",
}

# Map wall type / category → CSI section
CATEGORY_CSI: dict[str, str] = {
    "wall": "04 20 00",
    "slab": "03 30 00",
    "door": "08 11 13",
    "window": "08 50 00",
    "room": "01 22 00",
    "equipment": "11 00 00",
    "note": "01 31 00",
    "grid": "01 32 00",
    "fitting": "22 11 16",
    "pipe": "22 11 16",
    "plumbing_pipe": "22 11 16",
    "fixture": "22 42 00",
    "accessory": "10 28 13",
    "fire_protection": "21 13 13",
    "process_piping": "40 05 13",
    "framing": "06 10 00",
    "structural_steel": "05 12 00",
    "rebar": "03 21 00",
    "hvac": "23 31 00",
    "duct": "23 31 00",
    "conduit": "26 05 33",
    "cable_tray": "26 05 36",
    "column": "05 12 00",
    "beam": "05 12 00",
    "electrical": "26 05 00",
    "structural": "05 12 00",
    "plumbing": "22 11 16",
    "process": "40 05 00",
    "envelope": "04 20 00",
    "module_instance": "11 00 00",
    "module_root": "11 00 00",
    "steel": "05 12 00",
    "wire": "26 05 19",
    "coil": "23 82 16",
    "bolt": "05 12 23",
    "fastener": "05 12 23",
    "flange": "40 05 13",
    "joint": "40 05 13",
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
    "toilet": "22 42 13",
    "urinal": "22 42 19",
    "lavatory": "22 42 16",
    "sink": "22 42 16",
    "tp_dispenser": "10 28 13",
    "soap_dispenser": "10 28 13",
    "grab_bar": "10 28 13",
    "hand_dryer": "10 28 13",
    "sprinkler_head": "21 13 13",
    "rebar": "03 21 00",
    "wide_flange": "05 12 00",
    "hss": "05 12 00",
    "bolt": "05 12 23",
    "wire": "26 05 19",
    "coil": "23 82 16",
    "joint": "40 05 13",
    "elbow_90": "22 11 16",
    "elbow_45": "22 11 16",
    "tee": "22 11 16",
    "ball_valve": "22 05 23",
    "gate_valve": "22 05 23",
    "pipe": "22 11 16",
    "toilet_hose": "22 11 19",
    "flush_valve": "22 11 19",
    "floor_drain": "22 13 19",
    "header": "40 05 13",
    "skid": "43 41 00",
    "separator_skid": "43 41 00",
}

# Finer article-level tags (not always published as MF numbers — used as csi_detail)
# Prefer real section first; detail disambiguates within section for takeoff
FITTING_CSI: dict[str, str] = {
    "elbow_90": "22 11 16",
    "elbow_45": "22 11 16",
    "tee": "22 11 16",
    "coupling": "22 11 16",
    "cap": "22 11 16",
    "union": "22 11 16",
    "reducer": "22 11 16",
    "ball_valve": "22 05 23",
    "gate_valve": "22 05 23",
    "check_valve": "22 05 23",
    "grooved_coupling": "21 13 13",
    "sprinkler_head": "21 13 13",
    "flange": "40 05 13",
    "pipe": "22 11 16",
    "toilet": "22 42 13",
    "urinal": "22 42 19",
    "lavatory": "22 42 16",
    "tp_dispenser": "10 28 13",
    "toilet_hose": "22 11 19",
    "wide_flange": "05 12 00",
    "rebar": "03 21 00",
    "wwf": "03 21 00",
    "vav": "23 36 00",
    "diffuser": "23 37 00",
    "grille": "23 37 00",
    "fire_damper": "23 33 00",
    "smoke_damper": "23 33 00",
    "duct": "23 31 00",
    "flex_duct": "23 31 00",
    "cable_tray": "26 05 36",
    "column": "05 12 00",
    "beam": "05 12 00",
    "panel": "26 24 16",
    "luminaire": "26 51 00",
    "receptacle": "26 27 26",
    "switch": "26 27 26",
    "conduit": "26 05 33",
}

MATERIAL_CSI_OVERRIDE: dict[str, str] = {
    "copper_C12200": "22 11 16",
    "copper_fitting": "22 11 16",
    "black_steel": "21 13 13",
    "ss316L": "40 05 13",
    "pvc_sch40": "22 13 16",
    "rebar_G60": "03 21 00",
    "steel_A992": "05 12 00",
    "steel_A36": "05 12 00",
}


def normalize_csi_code(code: str) -> str:
    """Normalize to 'NN NN NN' (or longer) spacing."""
    if not code:
        return "01 00 00"
    parts = str(code).replace("-", " ").replace(".", " ").split()
    # keep numeric groups
    nums = [p for p in parts if p.isdigit() or (len(p) <= 3 and p.isalnum())]
    if len(nums) >= 3:
        return f"{nums[0]:>02} {nums[1]:>02} {nums[2]:>02}" + (
            (" " + " ".join(nums[3:])) if len(nums) > 3 else ""
        )
    if len(nums) == 1 and len(nums[0]) == 6 and nums[0].isdigit():
        n = nums[0]
        return f"{n[0:2]} {n[2:4]} {n[4:6]}"
    return str(code).strip()


def resolve_csi_code(
    *,
    csi_code: str | None = None,
    category: str = "",
    type_id: str = "",
    part_id: str = "",
    fitting_type: str = "",
    material_id: str = "",
    system: str = "",
) -> str:
    """Pick the best MasterFormat section for an item."""
    if csi_code:
        return normalize_csi_code(csi_code)
    if part_id:
        try:
            from llmbim_core.parts_catalog import get_part

            part = get_part(str(part_id))
            if part and part.csi_code:
                return normalize_csi_code(part.csi_code)
            if part and (part.specs or {}).get("csi_code"):
                return normalize_csi_code(str(part.specs["csi_code"]))
            if part and (part.specs or {}).get("fitting_type"):
                ft = str(part.specs["fitting_type"])
                if ft in FITTING_CSI:
                    return FITTING_CSI[ft]
        except Exception:  # noqa: BLE001
            pass
    if fitting_type and fitting_type in FITTING_CSI:
        code = FITTING_CSI[fitting_type]
        # fire system overrides plumbing fitting defaults
        if system in ("fire", "fire_protection") and fitting_type != "sprinkler_head":
            if fitting_type in ("elbow_90", "elbow_45", "tee", "coupling", "pipe", "reducer", "cap"):
                code = "21 13 13"
        if system in ("process", "process_piping"):
            if fitting_type in ("elbow_90", "elbow_45", "tee", "pipe", "flange", "ball_valve", "gate_valve"):
                code = "40 05 13" if fitting_type != "ball_valve" else "40 05 23"
        return code
    if type_id and str(type_id) in TYPE_CSI:
        return TYPE_CSI[str(type_id)]
    if material_id and material_id in MATERIAL_CSI_OVERRIDE:
        return MATERIAL_CSI_OVERRIDE[material_id]
    if system == "fire":
        return "21 13 13"
    if system == "process":
        return "40 05 13"
    if category in CATEGORY_CSI:
        return CATEGORY_CSI[category]
    return "01 00 00"


def element_position_mm(el: Element) -> tuple[float | None, float | None, float | None]:
    """Plan X,Y and Z (height of item base) in mm."""
    p = el.params
    z = None
    if p.get("z0_mm") is not None:
        z = float(p["z0_mm"])
    if "origin_mm" in p and isinstance(p["origin_mm"], (list, tuple)):
        x, y = float(p["origin_mm"][0]), float(p["origin_mm"][1])
        return x, y, z if z is not None else 0.0
    if "start_mm" in p and "end_mm" in p:
        s, e = p["start_mm"], p["end_mm"]
        x = (float(s[0]) + float(e[0])) / 2
        y = (float(s[1]) + float(e[1])) / 2
        return x, y, z if z is not None else 0.0
    if "position_mm" in p:
        return float(p["position_mm"][0]), float(p["position_mm"][1]), z if z is not None else 0.0
    if "polygon_mm" in p and p["polygon_mm"]:
        xs = [float(pt[0]) for pt in p["polygon_mm"]]
        ys = [float(pt[1]) for pt in p["polygon_mm"]]
        return sum(xs) / len(xs), sum(ys) / len(ys), z if z is not None else 0.0
    return None, None, z


def element_height_mm(el: Element) -> float | None:
    p = el.params
    if p.get("height_mm") is not None:
        return float(p["height_mm"])
    if p.get("size_mm") and len(p["size_mm"]) >= 3:
        return float(p["size_mm"][2])
    if p.get("size_mm") and len(p["size_mm"]) >= 2 and p.get("fitting_type") == "pipe":
        return float(p["size_mm"][1])  # OD as vertical extent for horizontal pipe
    return None


def _point_in_polygon(x: float, y: float, poly: list[Any]) -> bool:
    """Ray casting; poly is list of [x,y] or (x,y)."""
    if len(poly) < 3:
        return False
    inside = False
    n = len(poly)
    try:
        j = n - 1
        for i in range(n):
            xi, yi = float(poly[i][0]), float(poly[i][1])
            xj, yj = float(poly[j][0]), float(poly[j][1])
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-30) + xi):
                inside = not inside
            j = i
    except (TypeError, ValueError, IndexError):
        return False
    return inside


def room_containing(model: ProjectModel, x: float, y: float, level_id: str | None = None) -> str | None:
    """Return name of first room whose boundary contains (x,y) on the level."""
    for el in model.elements:
        if el.category != "room":
            continue
        if level_id and el.level_id and el.level_id != level_id:
            continue
        boundary = el.params.get("boundary_mm") or el.params.get("boundary") or []
        if _point_in_polygon(x, y, boundary):
            return el.name or el.id
    return None


def location_for_element(model: ProjectModel, el: Element) -> dict[str, Any]:
    """Level + room + plan + height so agents can locate the instance."""
    level_name = ""
    level_elev = 0.0
    if el.level_id:
        for lv in model.levels:
            if lv.id == el.level_id:
                level_name = lv.name
                level_elev = float(lv.elevation_mm)
                break
    x, y, z = element_position_mm(el)
    h = element_height_mm(el)
    z_abs = None
    if z is not None:
        z_abs = level_elev + float(z)
    nps = el.params.get("nps") or el.params.get("trade_size") or ""
    section = el.params.get("section") or el.params.get("bar_size") or ""
    fire_rating = el.params.get("fire_rating") or ""
    system = el.params.get("system") or ""
    trade_size = el.params.get("trade_size") or ""
    room = None
    if x is not None and y is not None:
        room = room_containing(model, x, y, el.level_id)
    parts = []
    if level_name:
        parts.append(level_name)
    if room:
        # sanitize for locator token
        parts.append("RM:" + str(room).replace(" ", "_")[:40])
    if x is not None and y is not None:
        parts.append(f"X{x:.0f}Y{y:.0f}")
    if z is not None:
        parts.append(f"Z{z:.0f}")
    if z_abs is not None:
        parts.append(f"Zabs{z_abs:.0f}")
    if h is not None:
        parts.append(f"H{h:.0f}")
    if nps:
        # conduits often use trade_size; pipes use nps — both as NPS token for agents
        parts.append(f"NPS{nps}")
    if trade_size and str(trade_size) != str(nps):
        parts.append(f"TS{trade_size}")
    if section:
        parts.append(str(section).replace(" ", ""))
    if system:
        parts.append(f"SYS{str(system)[:12]}")
    if fire_rating:
        fr = str(fire_rating).replace(" ", "").replace("-", "")
        parts.append(f"FR{fr[:12]}")
    if el.params.get("vertical"):
        parts.append("RISER")
    if el.category in {"column", "beam", "duct", "conduit", "cable_tray"}:
        parts.append(str(el.category).upper().replace("_", "")[:10])
    locator = "|".join(parts) if parts else el.id
    return {
        "level": level_name or None,
        "room": room,
        "level_elevation_mm": level_elev,
        "x_mm": round(x, 1) if x is not None else None,
        "y_mm": round(y, 1) if y is not None else None,
        "z_mm": round(z, 1) if z is not None else None,
        "z_absolute_mm": round(z_abs, 1) if z_abs is not None else None,
        "height_mm": round(h, 1) if h is not None else None,
        "nps": nps or None,
        "trade_size": trade_size or None,
        "section_mark": section or None,
        "fire_rating": fire_rating or None,
        "system": system or None,
        "locator": locator,
    }


def csi_for_element(model: ProjectModel, el: Element) -> dict[str, Any]:
    """Full CSI identity + location for one model element."""
    pid = el.params.get("part_id") or el.type_id or ""
    ftype = el.params.get("fitting_type") or ""
    mat = el.params.get("material_id") or ""
    system = el.params.get("system") or ""
    code = resolve_csi_code(
        csi_code=el.params.get("csi_code"),
        category=el.category,
        type_id=str(el.type_id or el.params.get("kind") or ""),
        part_id=str(pid),
        fitting_type=str(ftype),
        material_id=str(mat),
        system=str(system),
    )
    # fire black steel / process from material — only for pipe/fitting MEP, not panels/steel/equip
    pipe_fit_types = {
        "pipe",
        "elbow_90",
        "elbow_45",
        "tee",
        "coupling",
        "reducer",
        "cap",
        "union",
        "ball_valve",
        "gate_valve",
        "check_valve",
        "flange",
        "sprinkler_head",
    }
    if str(mat) in MATERIAL_CSI_OVERRIDE and not el.params.get("csi_code"):
        if el.category in {"pipe", "fitting", "fittings", "plumbing_pipe"} or ftype in pipe_fit_types:
            # do not override if part already resolved a specific catalog CSI
            part_had_csi = False
            if pid:
                try:
                    from llmbim_core.parts_catalog import get_part

                    part = get_part(str(pid))
                    if part and (part.csi_code or (part.specs or {}).get("csi_code")):
                        part_had_csi = True
                except Exception:  # noqa: BLE001
                    pass
            if not part_had_csi:
                code = MATERIAL_CSI_OVERRIDE[str(mat)]
                if system == "fire" or str(mat) == "black_steel":
                    code = "21 13 13"
                if system == "process" or str(mat) == "ss316L":
                    code = "40 05 13" if ftype != "ball_valve" else "40 05 23"

    div = code.split()[0] if code else "01"
    loc = location_for_element(model, el)
    # Instance mark: CSI + locator so codes uniquely find items
    csi_instance = f"{code} @{loc['locator']}"
    return {
        "csi_code": code,
        "csi_number": code,  # alias agents may search
        "csi_division": div,
        "csi_division_name": CSI_DIVISIONS.get(div, "General"),
        "csi_section_name": CSI_SECTIONS.get(code, CSI_SECTIONS.get(normalize_csi_code(code), "")),
        "csi_instance": csi_instance,
        "element_id": el.id,
        "element_name": el.name,
        "category": el.category,
        "part_id": pid or None,
        "fitting_type": ftype or None,
        **loc,
    }


def csi_for_line(row: dict[str, Any], model: ProjectModel | None = None) -> dict[str, Any]:
    """Attach CSI code + division (+ optional location) to a BOQ/takeoff line."""
    cat = row.get("category", "")
    type_id = row.get("type_id") or row.get("kind") or ""
    code = resolve_csi_code(
        csi_code=row.get("csi_code"),
        category=str(cat),
        type_id=str(type_id),
        part_id=str(row.get("part_id") or type_id or ""),
        fitting_type=str(row.get("fitting_type") or ""),
        material_id=str(row.get("material_id") or ""),
        system=str(row.get("system") or ""),
    )
    div = str(code).split()[0] if code else "01"
    out: dict[str, Any] = {
        "csi_code": code,
        "csi_number": code,
        "csi_division": div,
        "csi_division_name": CSI_DIVISIONS.get(div, "General"),
        "csi_section_name": CSI_SECTIONS.get(code, ""),
    }
    # if we have element id + model, attach locator
    eid = row.get("id") or row.get("element_id")
    if model is not None and eid:
        try:
            el = model.get_element(str(eid))
            loc = location_for_element(model, el)
            out.update({k: loc[k] for k in loc})
            out["csi_instance"] = f"{code} @{loc['locator']}"
        except Exception:  # noqa: BLE001
            pass
    return out


def annotate_boq_with_csi(
    rows: list[dict[str, Any]],
    model: ProjectModel | None = None,
) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        rr = dict(r)
        rr.update(csi_for_line(r, model=model))
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


def csi_instance_schedule(model: ProjectModel) -> list[dict[str, Any]]:
    """One row per element with real CSI number + XYZ/level locator."""
    rows = []
    for el in model.elements:
        if el.category in {"note", "grid", "room"}:
            continue
        row = csi_for_element(model, el)
        # attach qty for takeoff
        qty = el.params.get("part_qty")
        if el.params.get("length_m") is not None:
            qty = el.params["length_m"]
        row["qty"] = qty if qty is not None else 1
        row["unit"] = "m" if el.params.get("length_m") is not None or el.category == "pipe" else "ea"
        rows.append(row)
    return sorted(rows, key=lambda r: (r.get("csi_code") or "", r.get("locator") or ""))


def csi_catalog() -> dict[str, Any]:
    return {
        "divisions": CSI_DIVISIONS,
        "sections": CSI_SECTIONS,
        "category_defaults": CATEGORY_CSI,
        "type_defaults": TYPE_CSI,
        "fitting_defaults": FITTING_CSI,
        "note": "csi_code is MasterFormat section; csi_instance / locator add level+XY+Z to find the item",
    }
