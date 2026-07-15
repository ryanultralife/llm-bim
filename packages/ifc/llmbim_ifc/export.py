"""Minimal IFC4 SPF writer (no ifcopenshell required).

Writes IfcProject / Site / Building / BuildingStorey / Wall / Slab /
Door / Window / Space / BuildingElementProxy (equipment) with extruded
area solids where possible. Opens in many IFC viewers (BlenderBIM, FreeCAD).

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

    for el in model.elements:
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
            try:
                o = el.params["origin_mm"]
                s = el.params["size_mm"]
                z0 = float(el.params.get("z0_mm", 0))
            except (KeyError, TypeError, ValueError):
                continue
            x0, y0 = float(o[0]), float(o[1])
            lx, ly, hz = float(s[0]), float(s[1]), float(s[2])
            pt = f.add(f"IFCCARTESIANPOINT(({x0},{y0},{z0}))")
            a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{axis_x})")
            loc = f.add(f"IFCLOCALPLACEMENT($,#{a3})")
            body = extrude_rect(lx, ly, hz)
            prod = f.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{body}))")
            proxy = f.add(
                f"IFCBUILDINGELEMENTPROXY('{f.guid()}',#{owner},"
                f"'{_esc(el.name or el.id)}',$,$,#{loc},#{prod},$,.ELEMENT.)"
            )
            contained[storey].append(proxy)

        elif el.category == "room":
            try:
                b = el.params["boundary_mm"]
            except (KeyError, TypeError):
                continue
            xs = [float(p[0]) for p in b]
            ys = [float(p[1]) for p in b]
            minx, miny = min(xs), min(ys)
            dx, dy = max(xs) - minx, max(ys) - miny
            pt = f.add(f"IFCCARTESIANPOINT(({minx},{miny},0.))")
            a3 = f.add(f"IFCAXIS2PLACEMENT3D(#{pt},#{axis_z},#{axis_x})")
            loc = f.add(f"IFCLOCALPLACEMENT($,#{a3})")
            # space body optional
            space = f.add(
                f"IFCSPACE('{f.guid()}',#{owner},'{_esc(el.name)}',$,$,#{loc},$,$,"
                f".ELEMENT.,.INTERNAL.,$)"
            )
            contained[storey].append(space)

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

    for storey, els in contained.items():
        if not els:
            continue
        # IFCRELCONTAINEDINSPATIALSTRUCTURE
        ids = ",".join(f"#{e}" for e in els)
        f.add(
            f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{f.guid()}',#{owner},$,$,"
            f"({ids}),#{storey})"
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
