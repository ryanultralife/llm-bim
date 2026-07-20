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


def _wall_join_extensions(
    walls: list[tuple[str, float, float, float, float, float]],
    tol: float = 25.0,
) -> dict[str, tuple[float, float]]:
    """Corner joins: (ext_start, ext_end) per wall id — extend each wall end that
    meets another wall's end by half the *other* wall's thickness, so L/T corners
    close instead of butting with a thickness/2 gap. Mirrors the plan renderer's
    join logic (llmbim_drawings.plan)."""
    ext: dict[str, list[float]] = {wid: [0.0, 0.0] for wid, *_ in walls}
    for i, (id_a, ax0, ay0, ax1, ay1, ath) in enumerate(walls):
        for id_b, bx0, by0, bx1, by1, bth in walls[i + 1 :]:
            for end_a, pa in ((0, (ax0, ay0)), (1, (ax1, ay1))):
                for end_b, pb in ((0, (bx0, by0)), (1, (bx1, by1))):
                    if math.hypot(pa[0] - pb[0], pa[1] - pb[1]) <= tol:
                        ext[id_a][end_a] = max(ext[id_a][end_a], bth / 2.0)
                        ext[id_b][end_b] = max(ext[id_b][end_b], ath / 2.0)
    return {k: (v[0], v[1]) for k, v in ext.items()}


def _export_box_proxy(
    f: _Ifc,
    el,
    owner: int,
    axis_z: int,
    axis_x: int,
    extrude_rect,
    parent_local: int | None = None,
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
    par = f"#{parent_local}" if parent_local is not None else "$"
    loc = f.add(f"IFCLOCALPLACEMENT({par},#{a3})")
    # origin_mm is the plan min-corner (see create_equipment_box); offset the
    # centered profile so the box spans [x0,x0+lx] x [y0,y0+ly] not straddling x0,y0.
    body = extrude_rect(lx, ly, hz, cx=lx / 2.0, cy=ly / 2.0)
    prod = f.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{body}))")
    name, tag = _mep_name_tag(el)
    # Map categories to IFC entity classes for coordination browsers
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
    elif cat == "column" or ftype == "column":
        ent = "IFCCOLUMN"
    elif cat == "beam" or ftype == "beam":
        ent = "IFCBEAM"
    else:
        ent = "IFCBUILDINGELEMENTPROXY"
    if ent == "IFCBUILDINGELEMENTPROXY":
        return f.add(
            f"IFCBUILDINGELEMENTPROXY('{f.guid()}',#{owner},"
            f"'{_esc(name)}','{_esc(tag)}',$,#{loc},#{prod},$,.ELEMENT.)"
        )
    # Column / Beam / FlowFitting / FlowTerminal
    if ent in {"IFCCOLUMN", "IFCBEAM"}:
        # IFC4 added PredefinedType (9th attr) to IfcColumn/IfcBeam
        pdt = ".COLUMN." if ent == "IFCCOLUMN" else ".BEAM."
        return f.add(
            f"{ent}('{f.guid()}',#{owner},"
            f"'{_esc(name)}','{_esc(tag)}',$,#{loc},#{prod},$,{pdt})"
        )
    return f.add(
        f"{ent}('{f.guid()}',#{owner},"
        f"'{_esc(name)}','{_esc(tag)}',$,#{loc},#{prod},$)"
    )


def _mep_name_tag(el) -> tuple[str, str]:
    """Human name + short tag (NPS / section / RISER / system) for IFC browsers."""
    name = el.name or el.id
    nps = el.params.get("nps") or el.params.get("trade_size") or ""
    section = el.params.get("section") or ""
    ftype = el.params.get("fitting_type") or el.category or "MEP"
    tag_parts = [str(ftype).upper()[:12]]
    if section:
        tag_parts.append(str(section).replace(" ", "")[:16])
    if nps:
        tag_parts.append(f"NPS{nps}")
    if el.params.get("vertical") or el.params.get("orientation") == "vertical":
        tag_parts.append("RISER")
    if el.params.get("system"):
        tag_parts.append(str(el.params["system"])[:8])
    if el.params.get("fire_rating"):
        fr = str(el.params["fire_rating"]).replace(" ", "")[:10]
        tag_parts.append(f"FR{fr}")
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
    parent_local: int | None = None,
) -> int | None:
    """Pipe as elongated box; vertical risers extruded in Z. Emits IfcFlowSegment."""
    par = f"#{parent_local}" if parent_local is not None else "$"
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
            # riser centered on its axis (x0,y0); profile default-centered — do NOT
            # pre-offset the point (that double-shifted the section off the axis).
            pt = f.add(f"IFCCARTESIANPOINT(({x0},{y0},{z_base}))")
            a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},$)")
            loc = f.add(f"IFCLOCALPLACEMENT({par},#{a3})")
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
                pt = f.add(f"IFCCARTESIANPOINT(({x0},{y0},{z0}))")
                a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},$)")
                loc = f.add(f"IFCLOCALPLACEMENT({par},#{a3})")
                body = extrude_rect(od, od, max(height, 50.0))
            else:
                ang = math.atan2(y1 - y0, x1 - x0)
                pt = f.add(f"IFCCARTESIANPOINT(({x0},{y0},{z0}))")
                dx_dir = f.add(f"IFCDIRECTION(({math.cos(ang)},{math.sin(ang)},0.))")
                a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{dx_dir})")
                loc = f.add(f"IFCLOCALPLACEMENT({par},#{a3})")
                # run start->end from the placement point, centered on the pipe width
                body = extrude_rect(length, od, od, cx=length / 2.0, cy=0.0)
        elif "origin_mm" in el.params and "size_mm" in el.params:
            o = el.params["origin_mm"]
            sz = el.params["size_mm"]
            x0, y0 = float(o[0]), float(o[1])
            length = max(float(sz[0]), 50.0)
            ang = 0.0
            pt = f.add(f"IFCCARTESIANPOINT(({x0},{y0},{z0}))")
            dx_dir = f.add(f"IFCDIRECTION(({math.cos(ang)},{math.sin(ang)},0.))")
            a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{dx_dir})")
            loc = f.add(f"IFCLOCALPLACEMENT({par},#{a3})")
            body = extrude_rect(length, od, od, cx=length / 2.0, cy=0.0)
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

    # Owner history / app — org declared first so IfcApplication.ApplicationDeveloper
    # (a mandatory attribute) references it instead of being null.
    person = f.add("IFCPERSON($,$,'Agent',$,$,$,$,$)")
    org = f.add("IFCORGANIZATION($,'LLM-BIM',$,$,$)")
    app = f.add(f"IFCAPPLICATION(#{org},'0.1','llm-bim','llm-bim')")
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
    # level_id -> storey IfcLocalPlacement id; elements are placed relative to
    # this so the storey elevation flows through the placement chain (previously
    # every element used parent=$ and z=0, collapsing multi-storey to Z=0).
    storey_local: dict[str, int] = {}
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
        storey_local[lv.id] = loc
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
        default_local = loc
    else:
        default_local = storey_local.get(
            next((lv.id for lv in model.levels), ""), bldg_local
        )

    def place_at(x: float, y: float, z: float, parent_local: int) -> int:
        pt = f.add(f"IFCCARTESIANPOINT(({x},{y},{z}))")
        a2 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{axis_x})")
        return f.add(f"IFCLOCALPLACEMENT(#{parent_local},#{a2})")

    def extrude_rect(
        dx: float, dy: float, height: float, cx: float = 0.0, cy: float = 0.0
    ) -> int:
        """Profile in XY extruded along Z; returns IfcShapeRepresentation.

        The rectangle is centered on its 2D placement point. Callers whose
        element placement sits at a *corner/start* (walls, slabs, doors, boxes)
        pass ``cx``/``cy`` so the profile centers at (cx, cy) and the solid
        spans ``[0, 2*cx] x [-dy/2, dy/2]`` etc., running from the placement
        point instead of straddling it. Point-centered callers (pipes) keep the
        default (cx=cy=0) and remain symmetric about their axis.
        """
        # Rectangle profile
        p2d = f.add(f"IFCCARTESIANPOINT(({cx},{cy}))")
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

    wall_by_id = {el.id: el for el in model.elements if el.category == "wall"}

    # Corner joins: extend wall solids where ends meet so corners close
    wall_geo: list[tuple[str, float, float, float, float, float]] = []
    for wel in wall_by_id.values():
        try:
            ws, we = wel.params["start_mm"], wel.params["end_mm"]
            wth = float(wel.params.get("thickness_mm", 200))
            wall_geo.append(
                (wel.id, float(ws[0]), float(ws[1]), float(we[0]), float(we[1]), wth)
            )
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    joins = _wall_join_extensions(wall_geo)

    # First pass: walls — recorded so hosted openings can void them and place
    # themselves in wall-local coordinates.
    # wall element id -> (ifc wall id, wall IfcLocalPlacement id, thickness)
    ifc_walls: dict[str, tuple[int, int, float]] = {}
    for el in model.elements:
        if el.category != "wall":
            continue
        storey = storey_ids.get(el.level_id or "", default_storey)
        parent_local = storey_local.get(el.level_id or "", default_local)
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
        pt = f.add(f"IFCCARTESIANPOINT(({x0},{y0},0.0))")
        rad = math.radians(ang)
        dx_dir = f.add(f"IFCDIRECTION(({math.cos(rad)},{math.sin(rad)},0.))")
        a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{dx_dir})")
        loc = f.add(f"IFCLOCALPLACEMENT(#{parent_local},#{a3})")
        # corner joins: solid spans [-ext0, length+ext1] in wall-local X so
        # meeting walls close their corners; placement stays at the start point
        # (opening offsets remain measured from the unextended start).
        ext0, ext1 = joins.get(el.id, (0.0, 0.0))
        total = ext0 + length + ext1
        body = extrude_rect(total, th, ht, cx=total / 2.0 - ext0, cy=0.0)
        prod = f.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{body}))")
        wall = f.add(
            f"IFCWALLSTANDARDCASE('{f.guid()}',#{owner},'{_esc(el.name or el.id)}',"
            f"$,$,#{loc},#{prod},$,.STANDARD.)"
        )
        contained[storey].append(wall)
        _attach_csi_pset(f, owner, wall, model, el)
        ifc_walls[el.id] = (wall, loc, th)

    for el in model.elements:
        if el.category in {"room", "wall"}:
            continue  # already exported
        storey = storey_ids.get(el.level_id or "", default_storey)
        # Place elements RELATIVE to their storey's local placement so the storey
        # elevation flows through the chain; element Z is therefore storey-local (0
        # for level datum). Fixes multi-storey collapse to world Z=0.
        parent_local = storey_local.get(el.level_id or "", default_local)
        z_base = 0.0

        if el.category == "slab":
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
            pt = f.add(f"IFCCARTESIANPOINT(({minx},{miny},{z_base - th}))")
            a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{axis_x})")
            loc = f.add(f"IFCLOCALPLACEMENT(#{parent_local},#{a3})")
            # placement at min-corner: offset profile so slab spans [minx,minx+dx]x[miny,miny+dy]
            body = extrude_rect(dx, dy, th, cx=dx / 2.0, cy=dy / 2.0)
            prod = f.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{body}))")
            slab = f.add(
                f"IFCSLAB('{f.guid()}',#{owner},'{_esc(el.name or el.id)}',$,$,#{loc},"
                f"#{prod},$,.FLOOR.)"
            )
            contained[storey].append(slab)

        elif el.category == "equipment":
            eid = _export_box_proxy(f, el, owner, axis_z, axis_x, extrude_rect, parent_local)
            if eid is not None:
                contained[storey].append(eid)
                _link_to_space(el, eid)
                _attach_csi_pset(f, owner, eid, model, el)

        elif el.category == "column" or el.params.get("fitting_type") == "column":
            # IfcColumn envelope (coordination solid)
            eid = _export_box_proxy(f, el, owner, axis_z, axis_x, extrude_rect, parent_local)
            if eid is not None:
                contained[storey].append(eid)
                _attach_csi_pset(f, owner, eid, model, el)

        elif el.category == "beam" or el.params.get("fitting_type") == "beam":
            # Prefer box along start→end for IfcBeam; fallback pipe proxy
            eid = _export_box_proxy(f, el, owner, axis_z, axis_x, extrude_rect, parent_local)
            if eid is None:
                eid = _export_pipe_proxy(f, el, owner, axis_z, extrude_rect, parent_local)
            if eid is not None:
                contained[storey].append(eid)
                _attach_csi_pset(f, owner, eid, model, el)

        elif el.category in {"pipe", "plumbing_pipe", "conduit"}:
            eid = _export_pipe_proxy(f, el, owner, axis_z, extrude_rect, parent_local)
            if eid is not None:
                contained[storey].append(eid)
                _link_to_space(el, eid)
                _attach_csi_pset(f, owner, eid, model, el)

        elif el.category in {"duct", "hvac", "cable_tray"}:
            # rectangular duct / cable tray as FlowSegment envelope
            eid = _export_pipe_proxy(f, el, owner, axis_z, extrude_rect, parent_local)
            if eid is None:
                eid = _export_box_proxy(f, el, owner, axis_z, axis_x, extrude_rect, parent_local)
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
            eid = _export_box_proxy(f, el, owner, axis_z, axis_x, extrude_rect, parent_local)
            if eid is not None:
                contained[storey].append(eid)
                _link_to_space(el, eid)
                _attach_csi_pset(f, owner, eid, model, el)

        elif el.category in {"door", "window"}:
            # Hosted openings: place the door/window in WALL-LOCAL coordinates
            # (x = offset along baseline, y = 0 on centerline, z = sill), punch a
            # real IfcOpeningElement through the host via IfcRelVoidsElement, and
            # fill it with the door/window via IfcRelFillsElement — so importers
            # see hosted openings with actual holes, not free-floating solids.
            kind = "IFCDOOR" if el.category == "door" else "IFCWINDOW"
            try:
                w = float(el.params.get("width_mm", 900))
                h = float(el.params.get("height_mm", 2100 if el.category == "door" else 1200))
                sill = float(el.params.get("sill_mm") or 0)
                off = float(el.params.get("offset_mm") or 0)
                host_ifc = ifc_walls.get(el.host_id or "")
                if host_ifc is not None:
                    host_wall_id, host_loc, th = host_ifc
                    # opening solid: full wall depth (+2mm so the boolean fully
                    # clears both faces), wall-local at (off, 0, sill)
                    op_pt = f.add(f"IFCCARTESIANPOINT(({off},0.,{sill}))")
                    op_a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{op_pt},#{axis_z},#{axis_x})")
                    op_loc = f.add(f"IFCLOCALPLACEMENT(#{host_loc},#{op_a3})")
                    op_body = extrude_rect(w, th + 2.0, h, cx=w / 2.0, cy=0.0)
                    op_prod = f.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{op_body}))")
                    opening = f.add(
                        f"IFCOPENINGELEMENT('{f.guid()}',#{owner},"
                        f"'{_esc((el.name or el.id) + '-OPN')}',$,$,#{op_loc},"
                        f"#{op_prod},$,.OPENING.)"
                    )
                    f.add(
                        f"IFCRELVOIDSELEMENT('{f.guid()}',#{owner},$,$,"
                        f"#{host_wall_id},#{opening})"
                    )
                    # door/window leaf placed relative to the opening (origin)
                    leaf_pt = f.add("IFCCARTESIANPOINT((0.,0.,0.))")
                    leaf_a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{leaf_pt},#{axis_z},#{axis_x})")
                    loc = f.add(f"IFCLOCALPLACEMENT(#{op_loc},#{leaf_a3})")
                    body = extrude_rect(w, max(th, 50.0), h, cx=w / 2.0, cy=0.0)
                else:
                    # hostless fallback: storey-local at origin with sill height
                    th = 100.0
                    pt = f.add(f"IFCCARTESIANPOINT((0.,0.,{z_base + sill}))")
                    a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{axis_x})")
                    loc = f.add(f"IFCLOCALPLACEMENT(#{parent_local},#{a3})")
                    body = extrude_rect(w, max(th, 50.0), h, cx=w / 2.0, cy=0.0)
                    opening = None
                prod = f.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{body}))")
                tag = ""
                if el.type_id:
                    tag = str(el.type_id)[:24]
                if el.params.get("fire_rating"):
                    fr = str(el.params["fire_rating"]).replace(" ", "")[:10]
                    tag = f"{tag}-FR{fr}" if tag else f"FR{fr}"
                tag_attr = f"'{_esc(tag)}'" if tag else "$"
                # IFC4 IfcDoor/IfcWindow have 13 attributes: OverallHeight,
                # OverallWidth, PredefinedType, OperationType/PartitioningType,
                # UserDefined... appended after Tag.
                ent = f.add(
                    f"{kind}('{f.guid()}',#{owner},'{_esc(el.name or el.id)}',"
                    f"$,$,#{loc},#{prod},{tag_attr},{h},{w},.NOTDEFINED.,.NOTDEFINED.,$)"
                )
                if opening is not None:
                    f.add(
                        f"IFCRELFILLSELEMENT('{f.guid()}',#{owner},$,$,"
                        f"#{opening},#{ent})"
                    )
                contained[storey].append(ent)
                _attach_csi_pset(f, owner, ent, model, el)
            except (KeyError, TypeError, ValueError, IndexError):
                continue

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
        "FILE_DESCRIPTION(('ViewDefinition [ReferenceView_V1.2]'),'2;1');",
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
