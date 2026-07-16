"""Pure-Python STEP AP203 exporter — boxes + cylindrical prisms (n-gon).

Cylinders are emitted as closed shells of planar faces approximating a
right circular cylinder (default 24 sides). Suitable for FreeCAD / CAD
exchange as ENGINEERING ESTIMATE solids.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from llmbim_core.model import Element, ProjectModel


@dataclass
class _StepWriter:
    lines: list[str]
    next_id: int = 1

    def add(self, body: str) -> int:
        i = self.next_id
        self.next_id += 1
        self.lines.append(f"#{i} = {body};")
        return i


def _level_z(model: ProjectModel, level_id: str | None) -> float:
    if not level_id:
        return 0.0
    for lv in model.levels:
        if lv.id == level_id:
            return float(lv.elevation_mm)
    return 0.0


def _box_corners(
    x0: float, y0: float, z0: float, x1: float, y1: float, z1: float
) -> list[tuple[float, float, float]]:
    return [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]


_BOX_FACES = [
    (0, 1, 2, 3),
    (4, 7, 6, 5),
    (0, 4, 5, 1),
    (1, 5, 6, 2),
    (2, 6, 7, 3),
    (3, 7, 4, 0),
]


def _cylinder_corners(
    x0: float,
    y_c: float,
    z0: float,
    length: float,
    radius: float,
    *,
    n: int = 24,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    """Return vertices and face index tuples for a cylinder along +X.

    Bottom ring: indices 0..n-1 at x0
    Top ring: indices n..2n-1 at x0+length
    """
    verts: list[tuple[float, float, float]] = []
    for x in (x0, x0 + length):
        for i in range(n):
            ang = 2 * math.pi * i / n
            y = y_c + radius * math.cos(ang)
            z = z0 + radius + radius * math.sin(ang)  # centerline at z0+radius
            # Actually: store centerline z at z0 + radius so base sits on z0
            verts.append((x, y, z0 + radius + radius * math.sin(ang)))
    # Fix: use proper circle in YZ
    verts = []
    for x in (x0, x0 + length):
        for i in range(n):
            ang = 2 * math.pi * i / n
            y = y_c + radius * math.cos(ang)
            z = (z0 + radius) + radius * math.sin(ang)
            verts.append((x, y, z))

    faces: list[tuple[int, ...]] = []
    # side quads
    for i in range(n):
        j = (i + 1) % n
        # outward: bottom i,j and top i,j
        faces.append((i, j, n + j, n + i))
    # end caps (fan as triangle fans -> quads by taking consecutive)
    # bottom cap at x0: reverse winding
    bottom = tuple(reversed(range(n)))
    top = tuple(range(n, 2 * n))
    # split caps into triangles for planarity
    for i in range(1, n - 1):
        faces.append((0, i + 1, i))  # bottom triangles - wrong for n-gon as non-planar if fan from 0? Actually planar circle
        faces.append((n, n + i, n + i + 1))
    return verts, faces


def _esc(s: str) -> str:
    return s.replace("'", "").replace("\n", " ")[:60]


def _emit_solid(
    w: _StepWriter,
    verts: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    name: str,
    ctx: dict[str, int],
) -> int:
    cart = [w.add(f"CARTESIAN_POINT('',({x:.6f},{y:.6f},{z:.6f}))") for x, y, z in verts]
    origin = w.add("CARTESIAN_POINT('',(0.,0.,0.))")
    axis_z = w.add("DIRECTION('',(0.,0.,1.))")
    axis_x = w.add("DIRECTION('',(1.,0.,0.))")
    axis2 = w.add(f"AXIS2_PLACEMENT_3D('',#{origin},#{axis_z},#{axis_x})")

    face_ids: list[int] = []
    for face in faces:
        if len(face) < 3:
            continue
        pts = ",".join(f"#{cart[i]}" for i in face)
        poly = w.add(f"POLY_LOOP('',({pts}))")
        bound = w.add(f"FACE_OUTER_BOUND('',#{poly},.T.)")
        # plane from first three points
        i0, i1, i2 = face[0], face[1], face[2]
        p0, p1, p2 = verts[i0], verts[i1], verts[i2]
        v1 = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        v2 = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
        nx = v1[1] * v2[2] - v1[2] * v2[1]
        ny = v1[2] * v2[0] - v1[0] * v2[2]
        nz = v1[0] * v2[1] - v1[1] * v2[0]
        nlen = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        nx, ny, nz = nx / nlen, ny / nlen, nz / nlen
        if abs(nz) < 0.9:
            tx, ty, tz = 0.0, 0.0, 1.0
        else:
            tx, ty, tz = 1.0, 0.0, 0.0
        rx = ty * nz - tz * ny
        ry = tz * nx - tx * nz
        rz = tx * ny - ty * nx
        rlen = math.sqrt(rx * rx + ry * ry + rz * rz) or 1.0
        cpt = w.add(f"CARTESIAN_POINT('',({p0[0]:.6f},{p0[1]:.6f},{p0[2]:.6f}))")
        dn = w.add(f"DIRECTION('',({nx:.6f},{ny:.6f},{nz:.6f}))")
        dref = w.add(f"DIRECTION('',({rx/rlen:.6f},{ry/rlen:.6f},{rz/rlen:.6f}))")
        a2p = w.add(f"AXIS2_PLACEMENT_3D('',#{cpt},#{dn},#{dref})")
        plane = w.add(f"PLANE('',#{a2p})")
        face_ids.append(w.add(f"ADVANCED_FACE('',(#{bound}),#{plane},.T.)"))

    shell = w.add("CLOSED_SHELL('',(" + ",".join(f"#{f}" for f in face_ids) + "))")
    solid = w.add(f"MANIFOLD_SOLID_BREP('{_esc(name)}',#{shell})")
    prod = w.add(f"PRODUCT('{_esc(name)}','{_esc(name)}','',(#{ctx['prod_ctx']}))")
    pdf = w.add(f"PRODUCT_DEFINITION_FORMATION('',#{prod},#{ctx['prod_ctx']})")
    pd = w.add(f"PRODUCT_DEFINITION('design','',#{pdf},#{ctx['prod_def_ctx']})")
    pds = w.add(f"PRODUCT_DEFINITION_SHAPE('','',#{pd})")
    w.add(f"ADVANCED_BREP_SHAPE_REPRESENTATION('',(#{solid},#{axis2}),#{ctx['geom_ctx']})")
    abr_id = w.next_id - 1
    w.add(f"SHAPE_DEFINITION_REPRESENTATION(#{pds},#{abr_id})")
    return pd


def _equipment_solid(
    el: Element, model: ProjectModel, *, cyl_sides: int = 24
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]] | None:
    try:
        o = el.params.get("origin_mm")
        s = el.params.get("size_mm") or [100.0, 100.0, 100.0]
        if not o:
            return None
        z0 = float(el.params.get("z0_mm", 0)) + _level_z(model, el.level_id)
        shape = el.params.get("shape", "box")
    except (KeyError, TypeError, ValueError):
        return None
    x0, y0 = float(o[0]) / 1000.0, float(o[1]) / 1000.0
    lx = float(s[0]) / 1000.0 if len(s) > 0 else 0.1
    ly = float(s[1]) / 1000.0 if len(s) > 1 else 0.1
    hz = float(s[2]) / 1000.0 if len(s) > 2 else ly
    z0m = z0 / 1000.0
    if shape == "cylinder" or el.params.get("fitting_type") == "pipe":
        r = max(ly / 2.0, 0.01)
        return _cylinder_corners(x0, y0, z0m, max(lx, 0.05), r, n=cyl_sides)
    corners = _box_corners(x0, y0, z0m, x0 + max(lx, 0.05), y0 + max(ly, 0.05), z0m + max(hz, 0.05))
    return corners, _BOX_FACES


def _pipe_solid(el: Element, model: ProjectModel, *, cyl_sides: int = 16) -> tuple[list, list] | None:
    """Pipe as coordination box: horizontal start→end or vertical riser z0→z1."""
    try:
        od = 0.05
        if el.params.get("size_mm") and len(el.params["size_mm"]) >= 2:
            od = max(float(el.params["size_mm"][1]) / 1000.0, 0.02)
        # vertical riser
        if el.params.get("vertical") or el.params.get("orientation") == "vertical":
            o = el.params.get("origin_mm") or el.params.get("start_mm") or [0, 0]
            x = float(o[0]) / 1000.0
            y = float(o[1]) / 1000.0
            z_lo = (_level_z(model, el.level_id) + float(el.params.get("z0_mm") or 0)) / 1000.0
            z_hi = (_level_z(model, el.level_id) + float(el.params.get("z1_mm") or (float(el.params.get("z0_mm") or 0) + 1000))) / 1000.0
            r = od / 2
            return _box_corners(x - r, y - r, min(z_lo, z_hi), x + r, y + r, max(z_lo, z_hi)), _BOX_FACES
        if "start_mm" in el.params and "end_mm" in el.params:
            s, e = el.params["start_mm"], el.params["end_mm"]
            x0, y0 = float(s[0]) / 1000.0, float(s[1]) / 1000.0
            x1, y1 = float(e[0]) / 1000.0, float(e[1]) / 1000.0
            length = math.hypot(x1 - x0, y1 - y0)
            if length < 1e-6:
                return None
            z0 = (_level_z(model, el.level_id) + float(el.params.get("z0_mm", 0))) / 1000.0
            xmin, xmax = min(x0, x1), max(x0, x1)
            ymin, ymax = min(y0, y1), max(y0, y1)
            if abs(xmax - xmin) < 1e-6:
                xmin -= od / 2
                xmax += od / 2
            else:
                ymin -= od / 2
                ymax += od / 2
            if abs(ymax - ymin) < 1e-6:
                ymin -= od / 2
                ymax += od / 2
            return _box_corners(xmin, ymin, z0, xmax, ymax, z0 + od), _BOX_FACES
        return _equipment_solid(el, model, cyl_sides=cyl_sides)
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def _wall_solid(el: Element, model: ProjectModel) -> tuple[list, list] | None:
    try:
        s = el.params["start_mm"]
        e = el.params["end_mm"]
        th = float(el.params.get("thickness_mm", 200)) / 1000.0
        ht = float(el.params.get("height_mm", 3000)) / 1000.0
    except (KeyError, TypeError, ValueError):
        return None
    x0, y0 = float(s[0]) / 1000.0, float(s[1]) / 1000.0
    x1, y1 = float(e[0]) / 1000.0, float(e[1]) / 1000.0
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return None
    nx, ny = -dy / length, dx / length
    h = th / 2.0
    xs = [x0 + nx * h, x0 - nx * h, x1 + nx * h, x1 - nx * h]
    ys = [y0 + ny * h, y0 - ny * h, y1 + ny * h, y1 - ny * h]
    z0 = _level_z(model, el.level_id) / 1000.0
    corners = _box_corners(min(xs), min(ys), z0, max(xs), max(ys), z0 + ht)
    return corners, _BOX_FACES


def _opening_solid(
    el: Element, model: ProjectModel, wall_by_id: dict
) -> tuple[list, list] | None:
    """Door/window solid along host wall at offset + sill (metres)."""
    try:
        host = wall_by_id.get(el.host_id or "")
        if not host:
            return None
        s = host.params.get("start_mm")
        e = host.params.get("end_mm")
        if not s or not e:
            return None
        hx0, hy0 = float(s[0]) / 1000.0, float(s[1]) / 1000.0
        hx1, hy1 = float(e[0]) / 1000.0, float(e[1]) / 1000.0
        wlen = math.hypot(hx1 - hx0, hy1 - hy0)
        if wlen < 1e-9:
            return None
        off = float(el.params.get("offset_mm") or 0) / 1000.0
        width_o = float(el.params.get("width_mm") or 900) / 1000.0
        oh = float(el.params.get("height_mm") or (2100 if el.category == "door" else 1200)) / 1000.0
        sill = float(el.params.get("sill_mm") or 0) / 1000.0
        th = float(host.params.get("thickness_mm") or 100) / 1000.0
        ux, uy = (hx1 - hx0) / wlen, (hy1 - hy0) / wlen
        ax, ay = hx0 + ux * off, hy0 + uy * off
        bx, by = hx0 + ux * (off + width_o), hy0 + uy * (off + width_o)
        nx, ny = -uy, ux
        h = th / 2.0
        xs = [ax + nx * h, ax - nx * h, bx + nx * h, bx - nx * h]
        ys = [ay + ny * h, ay - ny * h, by + ny * h, by - ny * h]
        z0 = _level_z(model, host.level_id) / 1000.0 + sill
        corners = _box_corners(min(xs), min(ys), z0, max(xs), max(ys), z0 + oh)
        return corners, _BOX_FACES
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def _step_layer(el: Element) -> str:
    """Logical layer / system token for STEP PRODUCT names (CAD tree grouping)."""
    cat = el.category or ""
    ftype = str(el.params.get("fitting_type") or "")
    if cat == "wall":
        return "WALL"
    if cat == "door":
        return "DOOR"
    if cat == "window":
        return "WINDOW"
    if cat == "slab":
        return "SLAB"
    if cat == "equipment":
        return "EQUIP"
    if cat == "conduit" or ftype == "conduit":
        return "CONDUIT"
    if cat == "cable_tray" or ftype == "cable_tray":
        return "CABLE-TRAY"
    if cat == "column" or ftype == "column":
        return "COLUMN"
    if cat == "beam" or ftype == "beam":
        return "BEAM"
    if cat in {"duct", "hvac"} or ftype == "duct":
        return "DUCT"
    if cat in {"pipe", "plumbing_pipe"} or ftype == "pipe":
        mid = str(el.params.get("material_id") or "").lower()
        sys = str(el.params.get("system") or "").lower()
        if "black" in mid or sys in ("fp", "fire", "fire_protection"):
            return "PIPE-FP"
        if "ss316" in mid or sys in ("proc", "process"):
            return "PIPE-SS"
        if "pvc" in mid:
            return "PIPE-PVC"
        return "PIPE-CU"
    if cat in {"fitting", "fittings"}:
        return "FITTING"
    if cat == "wire" or ftype == "wire":
        return "WIRE"
    if cat == "coil" or ftype == "coil":
        return "COIL"
    if cat == "bolt" or ftype == "bolt":
        return "BOLT"
    if cat in {"flange", "joint"} or ftype in {"flange", "joint"}:
        return "FLANGE"
    if cat in {"fixture", "accessory"}:
        return "FIXTURE"
    if cat in {"module_instance", "module_root"}:
        return "MODULE"
    if cat in {"steel", "rebar", "framing"}:
        return "STRUCT"
    return "MEP"


def _step_product_name(el: Element) -> str:
    """PRODUCT id = LAYER:element_name so FreeCAD/etc. group by system."""
    base = (el.name or el.id or "part").replace("'", "").replace('"', "")[:60]
    layer = _step_layer(el)
    nps = el.params.get("nps") or el.params.get("trade_size") or ""
    if nps and (layer.startswith("PIPE") or layer == "CONDUIT"):
        if "NPS" not in base.upper():
            base = f"NPS{nps}_{base}"
    return f"{layer}:{base}"[:80]


def export_step(
    model: ProjectModel,
    path: str | Path,
    *,
    include_walls: bool = True,
    cyl_sides: int = 24,
) -> Path:
    """Write assembly STEP file with LAYER:name product tags for MEP systems."""
    w = _StepWriter(lines=[])
    app_ctx = w.add(
        "APPLICATION_CONTEXT('configuration controlled 3d designs of mechanical parts and assemblies')"
    )
    w.add(
        f"APPLICATION_PROTOCOL_DEFINITION('international standard',"
        f"'config_control_design',1994,#{app_ctx})"
    )
    prod_ctx = w.add(f"PRODUCT_CONTEXT('',#{app_ctx},'mechanical')")
    prod_def_ctx = w.add(
        f"PRODUCT_DEFINITION_CONTEXT('part definition',#{app_ctx},'design')"
    )
    length_unit = w.add("( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT($,.METRE.) )")
    plane_angle = w.add("( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) )")
    solid_angle = w.add("( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() )")
    unc = w.add(
        f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-6),#{length_unit},"
        f"'distance_accuracy_value','confusion accuracy')"
    )
    geom_ctx = w.add(
        f"( GEOMETRIC_REPRESENTATION_CONTEXT(3) "
        f"GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{unc})) "
        f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{length_unit},#{plane_angle},#{solid_angle})) "
        f"REPRESENTATION_CONTEXT('Context #1','3D Context with UNIT and UNCERTAINTY') )"
    )
    ctx = {
        "app_ctx": app_ctx,
        "prod_ctx": prod_ctx,
        "prod_def_ctx": prod_def_ctx,
        "geom_ctx": geom_ctx,
    }

    solids: list[tuple[str, list, list]] = []
    wall_by_id = {el.id: el for el in model.elements if el.category == "wall"}
    proxy_cats = {
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
        "duct",
        "hvac",
        "conduit",
        "cable_tray",
        "column",
        "beam",
        "wire",
        "coil",
        "bolt",
        "fastener",
        "flange",
        "joint",
    }
    for el in model.elements:
        pname = _step_product_name(el)
        if el.category == "equipment":
            solid = _equipment_solid(el, model, cyl_sides=cyl_sides)
            if solid:
                solids.append((pname, solid[0], solid[1]))
        elif el.category == "column":
            solid = _equipment_solid(el, model, cyl_sides=cyl_sides)
            if solid:
                solids.append((pname, solid[0], solid[1]))
        elif el.category in {
            "pipe",
            "plumbing_pipe",
            "conduit",
            "duct",
            "hvac",
            "cable_tray",
            "beam",
            "wire",
        }:
            solid = _pipe_solid(el, model, cyl_sides=max(8, cyl_sides // 2))
            if solid:
                solids.append((pname, solid[0], solid[1]))
        elif el.category in {"coil", "bolt", "flange", "joint", "fastener"}:
            # presentation envelopes via equipment solid path (origin+size)
            solid = _equipment_solid(el, model, cyl_sides=cyl_sides)
            if solid:
                solids.append((pname, solid[0], solid[1]))
        elif el.category in proxy_cats:
            if el.params.get("start_mm") and el.params.get("end_mm"):
                solid = _pipe_solid(el, model)
            else:
                solid = _equipment_solid(el, model, cyl_sides=cyl_sides)
            if solid:
                solids.append((pname, solid[0], solid[1]))
        elif el.category == "wall" and include_walls:
            solid = _wall_solid(el, model)
            if solid:
                solids.append((pname, solid[0], solid[1]))
        elif el.category in {"door", "window"} and include_walls:
            solid = _opening_solid(el, model, wall_by_id)
            if solid:
                solids.append((pname, solid[0], solid[1]))
        elif el.category == "slab":
            try:
                poly = el.params["polygon_mm"]
                th = float(el.params.get("thickness_mm", 200)) / 1000.0
            except (KeyError, TypeError, ValueError):
                continue
            xs = [float(p[0]) / 1000.0 for p in poly]
            ys = [float(p[1]) / 1000.0 for p in poly]
            z0 = _level_z(model, el.level_id) / 1000.0 - th
            corners = _box_corners(min(xs), min(ys), z0, max(xs), max(ys), z0 + th)
            solids.append((pname, corners, _BOX_FACES))

    if not solids:
        c = _box_corners(0, 0, 0, 0.1, 0.1, 0.1)
        solids.append(("MEP:empty", c, _BOX_FACES))

    for name, verts, faces in solids:
        _emit_solid(w, verts, faces, name, ctx)

    header = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('LLM-BIM STEP export'),'2;1');",
        f"FILE_NAME('{_esc(Path(path).name)}','',('llm-bim'),('llm-bim'),",
        "  'llm-bim step_export','llm-bim','');",
        "FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));",
        "ENDSEC;",
        "DATA;",
    ]
    footer = ["ENDSEC;", "END-ISO-10303-21;"]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(header + w.lines + footer) + "\n", encoding="utf-8")
    return p


def export_step_part(el: Element, model: ProjectModel, path: str | Path, **kw) -> Path:
    mini = ProjectModel(name=el.name or el.id, levels=list(model.levels), elements=[el])
    return export_step(mini, path, include_walls=False, **kw)
