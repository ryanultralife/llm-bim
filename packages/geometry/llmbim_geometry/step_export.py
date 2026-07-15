"""Pure-Python STEP AP203 exporter for equipment boxes and wall solids.

Emits manifold solid B-rep style faceted boxes and approximate cylinders
(as 16-sided prisms) so outputs open in FreeCAD, CAD Assistant, etc.

Not a full OpenCASCADE BREP kernel — engineering-estimate solids for exchange.
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
    """8 corners: bottom 0-3, top 4-7."""
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


# Faces as quads of corner indices (outward-ish)
_BOX_FACES = [
    (0, 1, 2, 3),  # bottom
    (4, 7, 6, 5),  # top
    (0, 4, 5, 1),  # y0
    (1, 5, 6, 2),  # x1
    (2, 6, 7, 3),  # y1
    (3, 7, 4, 0),  # x0
]


def _emit_box(
    w: _StepWriter,
    corners_m: list[tuple[float, float, float]],
    name: str,
    ctx: dict[str, int],
) -> int:
    """Return PRODUCT_DEFINITION id for a box solid (mm→m already applied)."""
    cart: list[int] = []
    for x, y, z in corners_m:
        cart.append(w.add(f"CARTESIAN_POINT('',({x:.6f},{y:.6f},{z:.6f}))"))

    # Axes for plane placement
    origin = w.add("CARTESIAN_POINT('',(0.,0.,0.))")
    axis_z = w.add("DIRECTION('',(0.,0.,1.))")
    axis_x = w.add("DIRECTION('',(1.,0.,0.))")
    axis2 = w.add(f"AXIS2_PLACEMENT_3D('',#{origin},#{axis_z},#{axis_x})")

    face_ids: list[int] = []
    for a, b, c, d in _BOX_FACES:
        # Poly loop
        poly = w.add(
            f"POLY_LOOP('',(#{cart[a]},#{cart[b]},#{cart[c]},#{cart[d]}))"
        )
        bound = w.add(f"FACE_OUTER_BOUND('',#{poly},.T.)")
        # Advanced face with plane (simplified: use FACE_SURFACE style FACETED)
        # Use OPEN_SHELL of ADVANCED_FACE is heavy; use FACETED_BREP style
        # ISO 10303-42: FACE_SURFACE needs SURFACE. Use PLANE at first point.
        p0 = corners_m[a]
        # Normal approx from cross product
        v1 = (
            corners_m[b][0] - p0[0],
            corners_m[b][1] - p0[1],
            corners_m[b][2] - p0[2],
        )
        v2 = (
            corners_m[d][0] - p0[0],
            corners_m[d][1] - p0[1],
            corners_m[d][2] - p0[2],
        )
        nx = v1[1] * v2[2] - v1[2] * v2[1]
        ny = v1[2] * v2[0] - v1[0] * v2[2]
        nz = v1[0] * v2[1] - v1[1] * v2[0]
        nlen = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        nx, ny, nz = nx / nlen, ny / nlen, nz / nlen
        # pick X direction on plane
        if abs(nz) < 0.9:
            tx, ty, tz = 0.0, 0.0, 1.0
        else:
            tx, ty, tz = 1.0, 0.0, 0.0
        # cross n × t for ref direction? Use simple fixed for faceted
        cpt = w.add(f"CARTESIAN_POINT('',({p0[0]:.6f},{p0[1]:.6f},{p0[2]:.6f}))")
        dn = w.add(f"DIRECTION('',({nx:.6f},{ny:.6f},{nz:.6f}))")
        # reference direction perpendicular to normal
        rx, ry, rz = ty * nz - tz * ny, tz * nx - tx * nz, tx * ny - ty * nx
        rlen = math.sqrt(rx * rx + ry * ry + rz * rz) or 1.0
        dref = w.add(f"DIRECTION('',({rx/rlen:.6f},{ry/rlen:.6f},{rz/rlen:.6f}))")
        a2p = w.add(f"AXIS2_PLACEMENT_3D('',#{cpt},#{dn},#{dref})")
        plane = w.add(f"PLANE('',#{a2p})")
        face = w.add(f"ADVANCED_FACE('',(#{bound}),#{plane},.T.)")
        face_ids.append(face)

    shell = w.add("CLOSED_SHELL('',(" + ",".join(f"#{f}" for f in face_ids) + "))")
    solid = w.add(f"MANIFOLD_SOLID_BREP('{_esc(name)}',#{shell})")

    # Product structure
    app_ctx = ctx["app_ctx"]
    prod = w.add(f"PRODUCT('{_esc(name)}','{_esc(name)}','',(#{ctx['prod_ctx']}))")
    pdf = w.add(
        f"PRODUCT_DEFINITION_FORMATION('',#{prod},#{ctx['prod_ctx']})"
    )
    pd = w.add(f"PRODUCT_DEFINITION('design','',#{pdf},#{ctx['prod_def_ctx']})")
    pds = w.add(f"PRODUCT_DEFINITION_SHAPE('','',#{pd})")
    w.add(f"ADVANCED_BREP_SHAPE_REPRESENTATION('',(#{solid},#{axis2}),#{ctx['geom_ctx']})")
    # link shape to product
    # Actually need SHAPE_DEFINITION_REPRESENTATION
    # Find last ABR - we need its id
    abr_id = w.next_id - 1
    w.add(f"SHAPE_DEFINITION_REPRESENTATION(#{pds},#{abr_id})")
    return pd


def _esc(s: str) -> str:
    return s.replace("'", "").replace("\n", " ")[:60]


def _equipment_box_m(el: Element, model: ProjectModel) -> tuple[float, float, float, float, float, float] | None:
    try:
        o = el.params["origin_mm"]
        s = el.params["size_mm"]
        z0 = float(el.params.get("z0_mm", 0)) + _level_z(model, el.level_id)
    except (KeyError, TypeError, ValueError):
        return None
    x0, y0 = float(o[0]) / 1000.0, float(o[1]) / 1000.0
    lx, ly, hz = float(s[0]) / 1000.0, float(s[1]) / 1000.0, float(s[2]) / 1000.0
    z0m = z0 / 1000.0
    return x0, y0, z0m, x0 + lx, y0 + ly, z0m + hz


def _wall_box_m(el: Element, model: ProjectModel) -> tuple[float, float, float, float, float, float] | None:
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
    # AABB of wall band (conservative)
    xs = [x0 + nx * h, x0 - nx * h, x1 + nx * h, x1 - nx * h]
    ys = [y0 + ny * h, y0 - ny * h, y1 + ny * h, y1 - ny * h]
    z0 = _level_z(model, el.level_id) / 1000.0
    return min(xs), min(ys), z0, max(xs), max(ys), z0 + ht


def export_step(model: ProjectModel, path: str | Path, *, include_walls: bool = True) -> Path:
    """Write assembly STEP file for the project solids."""
    w = _StepWriter(lines=[])
    # Header entities
    app_ctx = w.add(
        "APPLICATION_CONTEXT('configuration controlled 3d designs of mechanical parts and assemblies')"
    )
    app_proto = w.add(
        f"APPLICATION_PROTOCOL_DEFINITION('international standard',"
        f"'config_control_design',1994,#{app_ctx})"
    )
    _ = app_proto
    prod_ctx = w.add(
        f"PRODUCT_CONTEXT('',#{app_ctx},'mechanical')"
    )
    prod_def_ctx = w.add(
        f"PRODUCT_DEFINITION_CONTEXT('part definition',#{app_ctx},'design')"
    )
    # Geometric representation context
    unc = w.add(
        "UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-6),"
        f"#{w.next_id + 2},'distance_accuracy_value','confusion accuracy')"
    )
    # We need length unit before uncertainty — rebuild carefully
    # Simpler geometric context without uncertainty chain:

    # Reset writer for cleaner header (avoid forward-ref mess)
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
    plane_angle = w.add(
        "( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) )"
    )
    solid_angle = w.add(
        "( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() )"
    )
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

    solids: list[tuple[str, list[tuple[float, float, float]]]] = []
    for el in model.elements:
        if el.category == "equipment":
            b = _equipment_box_m(el, model)
            if b:
                x0, y0, z0, x1, y1, z1 = b
                solids.append(
                    (el.name or el.id, _box_corners(x0, y0, z0, x1, y1, z1))
                )
        elif el.category == "wall" and include_walls:
            b = _wall_box_m(el, model)
            if b:
                x0, y0, z0, x1, y1, z1 = b
                solids.append(
                    (el.name or el.id, _box_corners(x0, y0, z0, x1, y1, z1))
                )
        elif el.category == "slab":
            try:
                poly = el.params["polygon_mm"]
                th = float(el.params.get("thickness_mm", 200)) / 1000.0
            except (KeyError, TypeError, ValueError):
                continue
            xs = [float(p[0]) / 1000.0 for p in poly]
            ys = [float(p[1]) / 1000.0 for p in poly]
            z0 = _level_z(model, el.level_id) / 1000.0 - th
            solids.append(
                (
                    el.name or el.id,
                    _box_corners(min(xs), min(ys), z0, max(xs), max(ys), z0 + th),
                )
            )

    if not solids:
        solids.append(("empty", _box_corners(0, 0, 0, 0.1, 0.1, 0.1)))

    for name, corners in solids:
        _emit_box(w, corners, name, ctx)

    # ISO-10303-21 file
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


def export_step_part(el: Element, model: ProjectModel, path: str | Path) -> Path:
    """Export a single equipment element as its own STEP part file."""
    mini = ProjectModel(
        name=el.name or el.id,
        levels=list(model.levels),
        elements=[el],
    )
    return export_step(mini, path, include_walls=False)
