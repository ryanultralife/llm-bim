"""Minimal IFC4 SPF writer (no ifcopenshell required).

Writes IfcProject / Site / Building / BuildingStorey / Wall / Slab /
Door / Window / Space / IfcFlowSegment (pipes+risers) / IfcFlowFitting /
IfcFlowTerminal (fixtures) / BuildingElementProxy (equipment, modules)
with extruded area solids where possible.
Opens in many IFC viewers (BlenderBIM, FreeCAD).

Engineering-estimate geometry — not a certified MVD delivery.
"""

from __future__ import annotations

import math
import uuid
from pathlib import Path

from llmbim_core.model import ProjectModel


class _Ifc:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.n = 1

    def add(self, entity: str) -> int:
        i = self.n
        self.n += 1
        self.lines.append(f"#{i}={entity};")
        return i

    def guid(self) -> str:
        # IFC compressed GUID is complex; use 22-char base64-ish placeholder
        # Many parsers accept UUID-like; use IfcGloballyUniqueId 22 chars
        raw = uuid.uuid4().hex + uuid.uuid4().hex
        alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"
        num = int(raw[:32], 16)
        out = []
        for _ in range(22):
            out.append(alphabet[num % 64])
            num //= 64
        return "".join(reversed(out))


def _esc(s: str) -> str:
    return (s or "").replace("'", "''")[:80]


def _export_box_proxy(
    f: _Ifc,
    el,
    owner: int,
    axis_z: int,
    axis_x: int,
    extrude_rect,
) -> int | None:
    """IfcBuildingElementProxy from origin_mm + size_mm (equipment, fittings, modules)."""
    try:
        o = el.params.get("origin_mm")
        s = el.params.get("size_mm")
        if not o or not s:
            # fittings may only have origin — default small cube
            if not o:
                return None
            s = [100.0, 100.0, 100.0]
        z0 = float(el.params.get("z0_mm", 0))
        x0, y0 = float(o[0]), float(o[1])
        lx, ly, hz = float(s[0]), float(s[1]), float(s[2] if len(s) > 2 else s[1])
        if lx < 1:
            lx = 50.0
        if ly < 1:
            ly = 50.0
        if hz < 1:
            hz = 50.0
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    pt = f.add(f"IFCCARTESIANPOINT(({x0},{y0},{z0}))")
    a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{axis_x})")
    loc = f.add(f"IFCLOCALPLACEMENT($,#{a3})")
    body = extrude_rect(lx, ly, hz)
    prod = f.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{body}))")
    name, tag = _mep_name_tag(el)
    # fittings / fixtures → FlowFitting / FlowTerminal when category matches
    cat = (el.category or "").lower()
    ftype = str(el.params.get("fitting_type") or "").lower()
    if cat in {"fitting", "fittings"} or ftype in {
        "elbow_90",
        "elbow_45",
        "tee",
        "coupling",
        "reducer",
        "cap",
        "union",
        "ball_valve",
        "check_valve",
    }:
        ent = "IFCFLOWFITTING"
    elif cat in {"fixture", "accessory"} or ftype in {"toilet", "sink", "urinal", "lavatory"}:
        ent = "IFCFLOWTERMINAL"
    else:
        ent = "IFCBUILDINGELEMENTPROXY"
    if ent == "IFCBUILDINGELEMENTPROXY":
        return f.add(
            f"IFCBUILDINGELEMENTPROXY('{f.guid()}',#{owner},"
            f"'{_esc(name)}','{_esc(tag)}',$,#{loc},#{prod},$,.ELEMENT.)"
        )
    return f.add(
        f"{ent}('{f.guid()}',#{owner},"
        f"'{_esc(name)}','{_esc(tag)}',$,#{loc},#{prod},$)"
    )


def _mep_name_tag(el) -> tuple[str, str]:
    """Human name + short tag (NPS / RISER / system) for IFC browsers."""
    name = el.name or el.id
    nps = el.params.get("nps") or ""
    ftype = el.params.get("fitting_type") or el.category or "MEP"
    tag_parts = [str(ftype).upper()[:12]]
    if nps:
        tag_parts.append(f"NPS{nps}")
    if el.params.get("vertical") or el.params.get("orientation") == "vertical":
        tag_parts.append("RISER")
    if el.params.get("system"):
        tag_parts.append(str(el.params["system"])[:8])
    return str(name), "-".join(tag_parts)[:40]


def _attach_csi_pset(f: _Ifc, owner: int, product_id: int, model: ProjectModel, el) -> None:
    """Attach Pset_CSIMasterFormat with CSI code + locator for IFC browsers."""
    try:
        from llmbim_core.csi import csi_for_element

        info = csi_for_element(model, el)
    except Exception:  # noqa: BLE001
        info = {}
    code = info.get("csi_code") or el.params.get("csi_code") or ""
    if not code:
        return
    locator = info.get("locator") or info.get("csi_instance") or ""
    room = info.get("room") or ""
    section = info.get("csi_section_name") or ""
    props: list[int] = []
    props.append(
        f.add(f"IFCPROPERTYSINGLEVALUE('CSI_Code',$,IFCLABEL('{_esc(str(code))}'),$)")
    )
    if section:
        props.append(
            f.add(
                f"IFCPROPERTYSINGLEVALUE('CSI_Section',$,IFCLABEL('{_esc(str(section))}'),$)"
            )
        )
    if locator:
        props.append(
            f.add(
                f"IFCPROPERTYSINGLEVALUE('Locator',$,IFCLABEL('{_esc(str(locator))}'),$)"
            )
        )
    if room:
        props.append(
            f.add(f"IFCPROPERTYSINGLEVALUE('Room',$,IFCLABEL('{_esc(str(room))}'),$)")
        )
    ids = ",".join(f"#{p}" for p in props)
    pset = f.add(
        f"IFCPROPERTYSET('{f.guid()}',#{owner},'Pset_CSIMasterFormat',$,({ids}))"
    )
    f.add(
        f"IFCRELDEFINESBYPROPERTIES('{f.guid()}',#{owner},$,$,(#{product_id}),#{pset})"
    )


def _export_pipe_proxy(
    f: _Ifc,
    el,
    owner: int,
    axis_z: int,
    extrude_rect,
) -> int | None:
    """Pipe as elongated box; vertical risers extruded in Z. Emits IfcFlowSegment."""
    try:
        vertical = bool(el.params.get("vertical") or el.params.get("orientation") == "vertical")
        od = 50.0
        if el.params.get("size_mm") and len(el.params["size_mm"]) >= 2:
            od = max(float(el.params["size_mm"][0]), float(el.params["size_mm"][1]), 20.0)
        z0 = float(el.params.get("z0_mm", 0))

        if vertical:
            o = el.params.get("origin_mm") or el.params.get("start_mm")
            if not o:
                return None
            x0, y0 = float(o[0]), float(o[1])
            z1 = float(el.params.get("z1_mm") or (z0 + float(el.params.get("length_mm") or 1000)))
            height = abs(z1 - z0)
            if height < 1:
                height = float(el.params.get("length_mm") or 1000)
            z_base = min(z0, z1)
            pt = f.add(f"IFCCARTESIANPOINT(({x0 - od / 2},{y0 - od / 2},{z_base}))")
            a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},$)")
            loc = f.add(f"IFCLOCALPLACEMENT($,#{a3})")
            body = extrude_rect(od, od, height)
        elif "start_mm" in el.params and "end_mm" in el.params:
            s = el.params["start_mm"]
            e = el.params["end_mm"]
            x0, y0 = float(s[0]), float(s[1])
            x1, y1 = float(e[0]), float(e[1])
            length = math.hypot(x1 - x0, y1 - y0)
            if length < 1:
                o = el.params.get("origin_mm") or s
                x0, y0 = float(o[0]), float(o[1])
                height = float(
                    el.params.get("length_mm")
                    or (el.params.get("size_mm") or [0, 0, 500])[-1]
                    or 500
                )
                pt = f.add(f"IFCCARTESIANPOINT(({x0 - od / 2},{y0 - od / 2},{z0}))")
                a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},$)")
                loc = f.add(f"IFCLOCALPLACEMENT($,#{a3})")
                body = extrude_rect(od, od, max(height, 50.0))
            else:
                ang = math.atan2(y1 - y0, x1 - x0)
                pt = f.add(f"IFCCARTESIANPOINT(({x0},{y0},{z0}))")
                dx_dir = f.add(f"IFCDIRECTION(({math.cos(ang)},{math.sin(ang)},0.))")
                a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{dx_dir})")
                loc = f.add(f"IFCLOCALPLACEMENT($,#{a3})")
                body = extrude_rect(length, od, od)
        elif "origin_mm" in el.params and "size_mm" in el.params:
            o = el.params["origin_mm"]
            sz = el.params["size_mm"]
            x0, y0 = float(o[0]), float(o[1])
            length = max(float(sz[0]), 50.0)
            ang = 0.0
            pt = f.add(f"IFCCARTESIANPOINT(({x0},{y0},{z0}))")
            dx_dir = f.add(f"IFCDIRECTION(({math.cos(ang)},{math.sin(ang)},0.))")
            a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{dx_dir})")
            loc = f.add(f"IFCLOCALPLACEMENT($,#{a3})")
            body = extrude_rect(length, od, od)
        else:
            return None
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    prod = f.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{body}))")
    name, tag = _mep_name_tag(el)
    return f.add(
        f"IFCFLOWSEGMENT('{f.guid()}',#{owner},"
        f"'{_esc(name)}','{_esc(tag)}',$,#{loc},#{prod},$)"
    )


def export_ifc(model: ProjectModel, path: str | Path) -> Path:
    """Write IFC4 file from project model."""
    f = _Ifc()

    # Owner history / app
    app = f.add(
        "IFCAPPLICATION($,'llm-bim','llm-bim','0.1')"
    )
    person = f.add("IFCPERSON($,$,'Agent',$,$,$,$,$)")
    org = f.add("IFCORGANIZATION($,'LLM-BIM',$,$,$)")
    po = f.add(f"IFCPERSONANDORGANIZATION(#{person},#{org},$)")
    owner = f.add(
        f"IFCOWNERHISTORY(#{po},#{app},$,.ADDED.,$,#{po},#{app},0)"
    )

    # Units (mm)
    length = f.add("IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.)")
    area = f.add("IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.)")
    vol = f.add("IFCSIUNIT(*,.VOLUMEUNIT.,$,.CUBIC_METRE.)")
    units = f.add(f"IFCUNITASSIGNMENT((#{length},#{area},#{vol}))")

    # Geometric context
    origin = f.add("IFCCARTESIANPOINT((0.,0.,0.))")
    axis_z = f.add("IFCDIRECTION((0.,0.,1.))")
    axis_x = f.add("IFCDIRECTION((1.,0.,0.))")
    world = f.add(f"IFCAXIS2PLACEMENT3D(#{origin},#{axis_z},#{axis_x})")
    ctx3d = f.add(
        f"IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#{world},$)"
    )
    ctx_body = f.add(
        f"IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,#{ctx3d},$,"
        f".MODEL_VIEW.,$)"
    )

    project = f.add(
        f"IFCPROJECT('{f.guid()}',#{owner},'{_esc(model.name)}',$,$,$,$,(#{ctx3d}),#{units})"
    )
    site_local = f.add(f"IFCLOCALPLACEMENT($,#{world})")
    site = f.add(
        f"IFCSITE('{f.guid()}',#{owner},'Site',$,$,#{site_local},$,$,.ELEMENT.,$,"
        f"$,$,$,$)"
    )
    bldg_local = f.add(f"IFCLOCALPLACEMENT(#{site_local},#{world})")
    building = f.add(
        f"IFCBUILDING('{f.guid()}',#{owner},'{_esc(model.name)}',$,$,"
        f"#{bldg_local},$,$,.ELEMENT.,$,$,$)"
    )

    # Aggregate
    f.add(f"IFCRELAGGREGATES('{f.guid()}',#{owner},$,$,#{project},(#{site}))")
    f.add(f"IFCRELAGGREGATES('{f.guid()}',#{owner},$,$,#{site},(#{building}))")

    storey_ids: dict[str, int] = {}
    for lv in sorted(model.levels, key=lambda x: x.elevation_mm):
        elev = float(lv.elevation_mm)
        pt = f.add(f"IFCCARTESIANPOINT((0.,0.,{elev}))")
        a2 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{axis_x})")
        loc = f.add(f"IFCLOCALPLACEMENT(#{bldg_local},#{a2})")
        sid = f.add(
            f"IFCBUILDINGSTOREY('{f.guid()}',#{owner},'{_esc(lv.name)}',$,$,"
            f"#{loc},$,$,.ELEMENT.,{elev})"
        )
        storey_ids[lv.id] = sid
        f.add(
            f"IFCRELAGGREGATES('{f.guid()}',#{owner},$,$,#{building},(#{sid}))"
        )

    if not storey_ids and model.levels:
        pass
    default_storey = next(iter(storey_ids.values()), None)
    if default_storey is None:
        pt = f.add("IFCCARTESIANPOINT((0.,0.,0.))")
        a2 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{axis_x})")
        loc = f.add(f"IFCLOCALPLACEMENT(#{bldg_local},#{a2})")
        default_storey = f.add(
            f"IFCBUILDINGSTOREY('{f.guid()}',#{owner},'Default',$,$,#{loc},$,$,.ELEMENT.,0.)"
        )
        f.add(
            f"IFCRELAGGREGATES('{f.guid()}',#{owner},$,$,#{building},(#{default_storey}))"
        )

    def place_at(x: float, y: float, z: float, parent_local: int) -> int:
        pt = f.add(f"IFCCARTESIANPOINT(({x},{y},{z}))")
        a2 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{axis_x})")
        return f.add(f"IFCLOCALPLACEMENT(#{parent_local},#{a2})")

    def extrude_rect(
        dx: float, dy: float, height: float
    ) -> int:
        """Profile in XY extruded along Z; returns IfcShapeRepresentation."""
        # Rectangle profile
        p2d = f.add("IFCCARTESIANPOINT((0.,0.))")
        d2 = f.add("IFCDIRECTION((1.,0.))")
        a2d = f.add(f"IFCAXIS2PLACEMENT2D(#{p2d},#{d2})")
        profile = f.add(
            f"IFCRECTANGLEPROFILEDEF(.AREA.,$,#{a2d},{dx},{dy})"
        )
        # Position for solid
        p0 = f.add("IFCCARTESIANPOINT((0.,0.,0.))")
        a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{p0},#{axis_z},#{axis_x})")
        direc = f.add("IFCDIRECTION((0.,0.,1.))")
        solid = f.add(
            f"IFCEXTRUDEDAREASOLID(#{profile},#{a3},#{direc},{height})"
        )
        return f.add(
            f"IFCSHAPEREPRESENTATION(#{ctx_body},'Body','SweptSolid',(#{solid}))"
        )

    contained: dict[int, list[int]] = {s: [] for s in storey_ids.values()}
    if default_storey not in contained:
        contained[default_storey] = []
    # IfcSpace id → MEP/product ids inside that room (coordination linkage)
    space_members: dict[int, list[int]] = {}
    # room element name → IfcSpace entity id
    space_by_name: dict[str, int] = {}

    def _room_for_el(el) -> str | None:
        try:
            from llmbim_core.csi import element_position_mm, room_containing

            x, y, _z = element_position_mm(el)
            if x is None or y is None:
                return None
            return room_containing(model, x, y, el.level_id)
        except Exception:  # noqa: BLE001
            return None

    def _link_to_space(el, ifc_eid: int | None) -> None:
        if ifc_eid is None:
            return
        room = _room_for_el(el)
        if not room:
            return
        sid = space_by_name.get(str(room))
        if sid is None:
            return
        space_members.setdefault(sid, []).append(ifc_eid)

    # Pass 1: rooms → IfcSpace (so MEP can link by name)
    for el in model.elements:
        if el.category != "room":
            continue
        storey = storey_ids.get(el.level_id or "", default_storey)
        try:
            b = el.params.get("boundary_mm") or el.params.get("boundary") or []
            if len(b) < 3:
                continue
            xs = [float(p[0]) for p in b]
            ys = [float(p[1]) for p in b]
            minx, miny = min(xs), min(ys)
            dx, dy = max(xs) - minx, max(ys) - miny
        except (TypeError, ValueError, IndexError):
            continue
        pt = f.add(f"IFCCARTESIANPOINT(({minx},{miny},0.))")
        a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{axis_x})")
        loc = f.add(f"IFCLOCALPLACEMENT($,#{a3})")
        rname = el.name or el.id
        desc = f"RM:{_esc(rname)}"
        h = el.params.get("height_mm") or el.params.get("ceiling_height_mm")
        if h is not None:
            desc += f"|H{float(h):.0f}"
        space = f.add(
            f"IFCSPACE('{f.guid()}',#{owner},'{_esc(rname)}','{desc}',$,#{loc},$,$,"
            f".ELEMENT.,.INTERNAL.,$)"
        )
        contained[storey].append(space)
        space_by_name[str(rname)] = space
        space_members.setdefault(space, [])

    for el in model.elements:
        if el.category == "room":
            continue  # already exported
        storey = storey_ids.get(el.level_id or "", default_storey)
        # Get storey local placement id — re-parse from entity is hard; use building local offset
        # Simpler: place relative to storey with elevation already in storey
        z_base = 0.0

        if el.category == "wall":
            try:
                s = el.params["start_mm"]
                e = el.params["end_mm"]
                th = float(el.params.get("thickness_mm", 200))
                ht = float(el.params.get("height_mm", 3000))
            except (KeyError, TypeError, ValueError):
                continue
            x0, y0 = float(s[0]), float(s[1])
            x1, y1 = float(e[0]), float(e[1])
            length = math.hypot(x1 - x0, y1 - y0)
            if length < 1:
                continue
            ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
            # placement at start, rotate Z
            pt = f.add(f"IFCCARTESIANPOINT(({x0},{y0},{z_base}))")
            # rotation around Z
            rad = math.radians(ang)
            dx_dir = f.add(f"IFCDIRECTION(({math.cos(rad)},{math.sin(rad)},0.))")
            a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{dx_dir})")
            # parent is storey — we need storey placement; use relative $
            loc = f.add(f"IFCLOCALPLACEMENT($,#{a3})")
            body = extrude_rect(length, th, ht)
            prod = f.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{body}))")
            wall = f.add(
                f"IFCWALLSTANDARDCASE('{f.guid()}',#{owner},'{_esc(el.name or el.id)}',"
                f"$,$,#{loc},#{prod},$)"
            )
            contained[storey].append(wall)
            _attach_csi_pset(f, owner, wall, model, el)

        elif el.category == "slab":
            try:
                poly = el.params["polygon_mm"]
                th = float(el.params.get("thickness_mm", 200))
            except (KeyError, TypeError, ValueError):
                continue
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) for p in poly]
            minx, miny = min(xs), min(ys)
            dx, dy = max(xs) - minx, max(ys) - miny
            if dx < 1 or dy < 1:
                continue
            pt = f.add(f"IFCCARTESIANPOINT(({minx},{miny},{-th}))")
            a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{axis_x})")
            loc = f.add(f"IFCLOCALPLACEMENT($,#{a3})")
            body = extrude_rect(dx, dy, th)
            prod = f.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{body}))")
            slab = f.add(
                f"IFCSLAB('{f.guid()}',#{owner},'{_esc(el.name or el.id)}',$,$,#{loc},"
                f"#{prod},$,.FLOOR.)"
            )
            contained[storey].append(slab)

        elif el.category == "equipment":
            eid = _export_box_proxy(f, el, owner, axis_z, axis_x, extrude_rect)
            if eid is not None:
                contained[storey].append(eid)
                _link_to_space(el, eid)
                _attach_csi_pset(f, owner, eid, model, el)

        elif el.category in {"pipe", "plumbing_pipe", "conduit"}:
            eid = _export_pipe_proxy(f, el, owner, axis_z, extrude_rect)
            if eid is not None:
                contained[storey].append(eid)
                _link_to_space(el, eid)
                _attach_csi_pset(f, owner, eid, model, el)

        elif el.category in {"duct", "hvac", "cable_tray"}:
            # rectangular duct / cable tray as FlowSegment envelope
            eid = _export_pipe_proxy(f, el, owner, axis_z, extrude_rect)
            if eid is None:
                eid = _export_box_proxy(f, el, owner, axis_z, axis_x, extrude_rect)
            if eid is not None:
                contained[storey].append(eid)
                _link_to_space(el, eid)
                _attach_csi_pset(f, owner, eid, model, el)

        elif el.category in {
            "fitting",
            "fittings",
            "fixture",
            "accessory",
            "module_instance",
            "module_root",
            "steel",
            "rebar",
            "framing",
            "fire_protection",
            "process_piping",
            "conduit",
        }:
            # MEP/catalog parts + module envelopes as coordination proxies
            eid = _export_box_proxy(f, el, owner, axis_z, axis_x, extrude_rect)
            if eid is not None:
                contained[storey].append(eid)
                _link_to_space(el, eid)
                _attach_csi_pset(f, owner, eid, model, el)

        elif el.category in {"door", "window"}:
            # Place as opening proxy at host offset — simplified box at origin
            kind = "IFCDOOR" if el.category == "door" else "IFCWINDOW"
            w = float(el.params.get("width_mm", 900))
            h = float(el.params.get("height_mm", 2100))
            pt = f.add("IFCCARTESIANPOINT((0.,0.,0.))")
            a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{axis_x})")
            loc = f.add(f"IFCLOCALPLACEMENT($,#{a3})")
            body = extrude_rect(w, 100.0, h)
            prod = f.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{body}))")
            ent = f.add(
                f"{kind}('{f.guid()}',#{owner},'{_esc(el.name or el.id)}',$,$,"
                f"#{loc},#{prod},$,$)"
            )
            contained[storey].append(ent)
            _attach_csi_pset(f, owner, ent, model, el)

    for storey, els in contained.items():
        if not els:
            continue
        # IFCRELCONTAINEDINSPATIALSTRUCTURE — storey contains walls/spaces/MEP
        ids = ",".join(f"#{e}" for e in els)
        f.add(
            f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{f.guid()}',#{owner},$,$,"
            f"({ids}),#{storey})"
        )

    # Space membership: MEP products contained in IfcSpace (room linkage for agents)
    for space_id, members in space_members.items():
        if not members:
            continue
        ids = ",".join(f"#{e}" for e in members)
        f.add(
            f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{f.guid()}',#{owner},"
            f"'SpaceContents',$,({ids}),#{space_id})"
        )

    header = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');",
        f"FILE_NAME('{_esc(Path(path).name)}','',('llm-bim'),('llm-bim'),",
        "  'llm-bim','llm-bim','');",
        "FILE_SCHEMA(('IFC4'));",
        "ENDSEC;",
        "DATA;",
    ]
    footer = ["ENDSEC;", "END-ISO-10303-21;"]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(header + f.lines + footer) + "\n", encoding="utf-8")
    return p
