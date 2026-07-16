"""Fab-grade BREP via CadQuery / OpenCascade (OCP).

Feature trees are LLM-authored parametric history. Rebuild → true BREP STEP
with fillets, holes, threads (helix), and tessellation for glTF review.

Optional dependency: ``cadquery`` (pulls cadquery-ocp). Import fails soft so
unit tests without the extra still collect (fab tests skip).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

_CQ_ERR: str | None = None
try:
    import cadquery as cq  # type: ignore
    from OCP.BRep import BRep_Tool  # type: ignore
    from OCP.BRepMesh import BRepMesh_IncrementalMesh  # type: ignore
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED  # type: ignore
    from OCP.TopExp import TopExp_Explorer  # type: ignore
    from OCP.TopLoc import TopLoc_Location  # type: ignore
    from OCP.TopoDS import TopoDS  # type: ignore

    HAS_CADQUERY = True
except Exception as exc:  # noqa: BLE001
    cq = None  # type: ignore
    HAS_CADQUERY = False
    _CQ_ERR = str(exc)


class FabBrepError(RuntimeError):
    """CadQuery/OCP rebuild or export failed."""


def require_cadquery() -> None:
    if not HAS_CADQUERY:
        raise FabBrepError(
            "CadQuery/OCP not available. Install: pip install 'llmbim[fab]' "
            f"or cadquery>=2.8 ({_CQ_ERR})"
        )


def _wp() -> Any:
    require_cadquery()
    return cq.Workplane("XY")


def rebuild_solid(features: list[dict[str, Any]]) -> Any:
    """Replay feature history → CadQuery Workplane with a solid."""
    require_cadquery()
    if not features:
        raise FabBrepError("empty feature tree")

    solid: Any = None
    for feat in features:
        op = str(feat.get("op") or "").lower()
        if op in {"box", "rect_prism"}:
            solid = _apply_box(solid, feat)
        elif op in {"cylinder", "cyl"}:
            solid = _apply_cylinder(solid, feat)
        elif op in {"hole", "drill"}:
            solid = _apply_hole(solid, feat)
        elif op in {"fillet", "ease", "round"}:
            solid = _apply_fillet(solid, feat)
        elif op in {"chamfer", "break_edge"}:
            solid = _apply_chamfer(solid, feat)
        elif op in {"thread", "machine_thread"}:
            solid = _apply_thread(solid, feat)
        elif op in {"cut_box", "pocket"}:
            solid = _apply_cut_box(solid, feat)
        elif op in {"union_box"}:
            solid = _apply_union_box(solid, feat)
        elif op in {"extrude_circle"}:
            solid = _apply_extrude_circle(solid, feat)
        elif op in {"revolve", "lathe"}:
            solid = _apply_revolve(solid, feat)
        elif op in {"hole_pattern", "pattern_holes"}:
            solid = _apply_hole_pattern(solid, feat)
        elif op in {"mirror"}:
            solid = _apply_mirror(solid, feat)
        else:
            raise FabBrepError(f"unknown fab op: {op}")
    if solid is None:
        raise FabBrepError("feature tree produced no solid")
    return solid


def _origin(feat: dict[str, Any]) -> tuple[float, float, float]:
    o = feat.get("origin_mm") or feat.get("origin") or [0, 0, 0]
    return float(o[0]), float(o[1]), float(o[2] if len(o) > 2 else 0)


def _apply_box(solid: Any, feat: dict[str, Any]) -> Any:
    size = feat.get("size_mm") or feat.get("size") or [50, 50, 20]
    sx, sy, sz = float(size[0]), float(size[1]), float(size[2])
    ox, oy, oz = _origin(feat)
    part = (
        _wp()
        .transformed(offset=(ox + sx / 2, oy + sy / 2, oz + sz / 2))
        .box(sx, sy, sz)
    )
    if solid is None:
        return part
    return solid.union(part)


def _apply_cylinder(solid: Any, feat: dict[str, Any]) -> Any:
    d = float(feat.get("diameter_mm") or feat.get("d_mm") or 20)
    h = float(feat.get("height_mm") or feat.get("length_mm") or 40)
    ox, oy, oz = _origin(feat)
    axis = str(feat.get("axis") or "z").lower()
    if axis == "x":
        part = (
            _wp()
            .transformed(offset=(ox, oy, oz), rotate=(0, 90, 0))
            .circle(d / 2)
            .extrude(h)
        )
    elif axis == "y":
        part = (
            _wp()
            .transformed(offset=(ox, oy, oz), rotate=(90, 0, 0))
            .circle(d / 2)
            .extrude(h)
        )
    else:
        part = _wp().transformed(offset=(ox, oy, oz)).circle(d / 2).extrude(h)
    if solid is None:
        return part
    return solid.union(part)


def _apply_extrude_circle(solid: Any, feat: dict[str, Any]) -> Any:
    return _apply_cylinder(solid, feat)


def _apply_hole(solid: Any, feat: dict[str, Any]) -> Any:
    if solid is None:
        raise FabBrepError("hole requires a base solid first")
    d = float(feat.get("diameter_mm") or feat.get("d_mm") or 6)
    depth = feat.get("depth_mm")
    ox, oy, oz = _origin(feat)
    # Position on top face plane relative to solid center is hard; use absolute cut cylinder
    h = float(depth) if depth is not None else 1e4
    dir_z = str(feat.get("direction") or "down").lower()
    if dir_z in {"up", "+z", "z+"}:
        tool = _wp().transformed(offset=(ox, oy, oz)).circle(d / 2).extrude(h)
    else:
        tool = _wp().transformed(offset=(ox, oy, oz)).circle(d / 2).extrude(-h)
    return solid.cut(tool)


def _apply_cut_box(solid: Any, feat: dict[str, Any]) -> Any:
    if solid is None:
        raise FabBrepError("cut_box requires a base solid first")
    size = feat.get("size_mm") or feat.get("size") or [10, 10, 10]
    sx, sy, sz = float(size[0]), float(size[1]), float(size[2])
    ox, oy, oz = _origin(feat)
    tool = (
        _wp()
        .transformed(offset=(ox + sx / 2, oy + sy / 2, oz + sz / 2))
        .box(sx, sy, sz)
    )
    return solid.cut(tool)


def _apply_union_box(solid: Any, feat: dict[str, Any]) -> Any:
    return _apply_box(solid, feat)


def _edge_set(solid: Any, selector: str) -> Any:
    """Rich edge selection for fillet/chamfer.

    Selectors:
      all | * | vertical | |Z | |X | |Y
      top_loop | bottom_loop  (faces >Z / <Z edges)
      >Z | <Z | >X | <X | >Y | <Y  (face then edges)
      index:0,2,5   (nth edges among all)
      len_lt:N / len_gt:N  (edge length mm)
    """
    sel = (selector or "|Z").strip()
    low = sel.lower()
    if low in {"all", "*"}:
        return solid.edges()
    if low in {"vertical", "|z"}:
        return solid.edges("|Z")
    if low in {"|x", "along_x"}:
        return solid.edges("|X")
    if low in {"|y", "along_y"}:
        return solid.edges("|Y")
    if low in {"top_loop", "top"}:
        return solid.faces(">Z").edges()
    if low in {"bottom_loop", "bottom"}:
        return solid.faces("<Z").edges()
    if sel.startswith(">") or sel.startswith("<"):
        # face selector then its edges
        return solid.faces(sel).edges()
    if low.startswith("index:"):
        raw = low.split(":", 1)[1]
        want = {int(x) for x in raw.split(",") if x.strip().isdigit()}
        edges = solid.edges().vals()
        picked = [e for i, e in enumerate(edges) if i in want]
        if not picked:
            raise FabBrepError(f"no edges matched index selector {sel}")
        return solid.newObject(picked)
    if low.startswith("len_lt:") or low.startswith("len_gt:"):
        thr = float(low.split(":", 1)[1])
        edges = solid.edges().vals()
        picked = []
        for e in edges:
            try:
                L = float(e.Length())
            except Exception:  # noqa: BLE001
                continue
            if low.startswith("len_lt:") and L < thr:
                picked.append(e)
            elif low.startswith("len_gt:") and L > thr:
                picked.append(e)
        if not picked:
            raise FabBrepError(f"no edges matched length selector {sel}")
        return solid.newObject(picked)
    # default: CadQuery string selector on edges
    return solid.edges(sel)


def _apply_fillet(solid: Any, feat: dict[str, Any]) -> Any:
    if solid is None:
        raise FabBrepError("fillet requires a base solid first")
    r = float(feat.get("radius_mm") or feat.get("radius") or 1.0)
    selector = str(feat.get("selector") or feat.get("edges") or "|Z")
    try:
        return _edge_set(solid, selector).fillet(r)
    except Exception:
        for fb in ("|Z", "top_loop", "all"):
            try:
                return _edge_set(solid, fb).fillet(r)
            except Exception:  # noqa: BLE001
                continue
        raise FabBrepError(f"fillet failed r={r} selector={selector}") from None


def _apply_chamfer(solid: Any, feat: dict[str, Any]) -> Any:
    if solid is None:
        raise FabBrepError("chamfer requires a base solid first")
    d = float(feat.get("distance_mm") or feat.get("length_mm") or feat.get("d_mm") or 1.0)
    selector = str(feat.get("selector") or feat.get("edges") or "top_loop")
    try:
        return _edge_set(solid, selector).chamfer(d)
    except Exception:
        for fb in ("top_loop", ">Z", "all"):
            try:
                return _edge_set(solid, fb).chamfer(d)
            except Exception:  # noqa: BLE001
                continue
        raise FabBrepError(f"chamfer failed d={d} selector={selector}") from None


def _apply_revolve(solid: Any, feat: dict[str, Any]) -> Any:
    """Revolve a rectangle profile about Z (lathe-style boss/shaft)."""
    # profile: outer radius, inner radius (0 = solid), height
    r_out = float(feat.get("radius_mm") or feat.get("outer_radius_mm") or 20)
    r_in = float(feat.get("inner_radius_mm") or 0)
    h = float(feat.get("height_mm") or 30)
    ox, oy, oz = _origin(feat)
    # sketch on XZ, revolve about Z
    pts = [(r_in, 0), (r_out, 0), (r_out, h), (r_in, h)]
    part = (
        cq.Workplane("XZ")
        .transformed(offset=(ox, oy, oz))
        .polyline(pts)
        .close()
        .revolve(360)
    )
    if solid is None:
        return part
    return solid.union(part)


def _apply_hole_pattern(solid: Any, feat: dict[str, Any]) -> Any:
    """Rectangular hole pattern (bolt circle via count_x/count_y + spacing)."""
    if solid is None:
        raise FabBrepError("hole_pattern requires a base solid first")
    d = float(feat.get("diameter_mm") or 6)
    depth = float(feat.get("depth_mm") or 1e4)
    ox, oy, oz = _origin(feat)
    nx = max(1, int(feat.get("count_x") or feat.get("nx") or 2))
    ny = max(1, int(feat.get("count_y") or feat.get("ny") or 1))
    sx = float(feat.get("spacing_x_mm") or feat.get("pitch_x_mm") or 20)
    sy = float(feat.get("spacing_y_mm") or feat.get("pitch_y_mm") or 20)
    for ix in range(nx):
        for iy in range(ny):
            x = ox + ix * sx
            y = oy + iy * sy
            tool = _wp().transformed(offset=(x, y, oz)).circle(d / 2).extrude(-abs(depth))
            solid = solid.cut(tool)
    return solid


def _apply_mirror(solid: Any, feat: dict[str, Any]) -> Any:
    if solid is None:
        raise FabBrepError("mirror requires a base solid first")
    plane = str(feat.get("plane") or "YZ").upper()
    # CadQuery mirror
    try:
        return solid.mirror(mirrorPlane=plane, basePointVector=(0, 0, 0))
    except Exception as exc:  # noqa: BLE001
        raise FabBrepError(f"mirror failed plane={plane}: {exc}") from exc


def _parse_thread_designation(des: str) -> tuple[float, float, str]:
    """Return (major_diameter_mm, pitch_mm, series) from M10x1.5 / 1/4-20 etc."""
    s = des.strip().upper().replace(" ", "")
    if s.startswith("M"):
        body = s[1:]
        if "X" in body:
            d_s, p_s = body.split("X", 1)
            p_s = p_s.split("-")[0]
            return float(d_s), float(p_s), "metric"
        d = float(body.split("-")[0])
        # ISO coarse defaults (subset)
        coarse = {
            3: 0.5, 4: 0.7, 5: 0.8, 6: 1.0, 8: 1.25, 10: 1.5, 12: 1.75, 16: 2.0, 20: 2.5, 24: 3.0,
        }
        return d, float(coarse.get(int(round(d)), d * 0.15)), "metric"
    if "-" in s:  # imperial 1/4-20
        # TPI after dash
        try:
            left, right = s.split("-", 1)
            tpi = float(right.split("-")[0])
            pitch = 25.4 / tpi
            # crude major for common fractions
            frac_map = {"1/4": 6.35, "5/16": 7.938, "3/8": 9.525, "1/2": 12.7}
            d = frac_map.get(left, 6.35)
            return d, pitch, "inch"
        except Exception:  # noqa: BLE001
            return 6.35, 1.27, "inch"
    return 10.0, 1.5, "metric"


def _apply_thread(solid: Any, feat: dict[str, Any]) -> Any:
    """ISO-ish machine thread: major/minor cylinders + dense helical V-groove.

    Depth ≈ 0.54127 × pitch (basic ISO 68-1 external engagement depth).
    """
    des = str(feat.get("designation") or feat.get("thread") or "M10x1.5")
    d_maj, pitch, _series = _parse_thread_designation(des)
    if feat.get("diameter_mm"):
        d_maj = float(feat["diameter_mm"])
    if feat.get("pitch_mm"):
        pitch = float(feat["pitch_mm"])
    length = float(feat.get("length_mm") or feat.get("depth_mm") or 20)
    internal = bool(feat.get("internal") or feat.get("female"))
    ox, oy, oz = _origin(feat)
    # ISO basic engagement depth
    h_iso = 0.54127 * pitch
    depth = float(feat.get("depth_mm") or h_iso)

    if solid is None and not internal:
        solid = _wp().transformed(offset=(ox, oy, oz)).circle(d_maj / 2).extrude(length)
        solid = _helix_groove(solid, d_maj, pitch, length, depth, ox, oy, oz, internal=False)
        try:
            solid = solid.faces(">Z").edges().chamfer(min(0.25, pitch * 0.15))
            solid = solid.faces("<Z").edges().chamfer(min(0.2, pitch * 0.12))
        except Exception:  # noqa: BLE001
            pass
        return solid

    if solid is None and internal:
        outer = d_maj * 2.2
        solid = (
            _wp()
            .transformed(offset=(ox, oy, oz))
            .circle(outer / 2)
            .extrude(length + 5)
        )

    if internal:
        # minor clearance ≈ major for tap drill is smaller; use major for hole then groove
        tool = _wp().transformed(offset=(ox, oy, oz)).circle(d_maj / 2).extrude(length + 0.1)
        solid = solid.cut(tool)
        solid = _helix_groove(solid, d_maj, pitch, length, depth, ox, oy, oz, internal=True)
    else:
        solid = _helix_groove(solid, d_maj, pitch, length, depth, ox, oy, oz, internal=False)
    return solid


def _helix_groove(
    solid: Any,
    d_maj: float,
    pitch: float,
    length: float,
    depth: float,
    ox: float,
    oy: float,
    oz: float,
    *,
    internal: bool,
) -> Any:
    """Helical V-groove via dense sphere cuts (ISO depth) — valid BREP, readable thread."""
    r_cut = max(depth * 0.48, pitch * 0.22, 0.12)
    n_turns = max(1.0, length / max(pitch, 0.1))
    # denser sampling for cleaner thread form
    samples = max(24, int(28 * n_turns))
    if internal:
        r_path = (d_maj / 2) + depth * 0.35
    else:
        r_path = (d_maj / 2) - depth * 0.55
    for i in range(samples):
        t = i / max(samples - 1, 1)
        ang = 2 * math.pi * n_turns * t
        z = oz + length * t
        x = ox + r_path * math.cos(ang)
        y = oy + r_path * math.sin(ang)
        ball = _wp().transformed(offset=(x, y, z)).sphere(r_cut)
        try:
            solid = solid.cut(ball)
        except Exception:  # noqa: BLE001
            continue
    return solid


def export_fab_step(features: list[dict[str, Any]], path: str | Path) -> Path:
    """Rebuild feature tree and write true OpenCascade STEP (MANIFOLD BREP)."""
    require_cadquery()
    solid = rebuild_solid(features)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(solid, str(out))
    return out


def export_fab_ortho_svgs(
    features: list[dict[str, Any]],
    *,
    width: float = 320,
    height: float = 240,
) -> dict[str, str]:
    """Three orthographic SVG projections (top / front / right) via CadQuery HLR SVG."""
    require_cadquery()
    solid = rebuild_solid(features)
    shape = solid.val()
    views = {
        "top": (0, 0, 1),
        "front": (0, -1, 0),
        "right": (1, 0, 0),
    }
    out: dict[str, str] = {}
    for name, pdir in views.items():
        opts = {
            "width": width,
            "height": height,
            "marginLeft": 20,
            "marginTop": 20,
            "showAxes": False,
            "projectionDir": pdir,
            "strokeWidth": 0.35,
            "strokeColor": (0.1, 0.12, 0.15),
            "hiddenColor": (0.55, 0.55, 0.58),
            "showHidden": True,
        }
        out[name] = cq.exporters.getSVG(shape, opts=opts)
    return out


def export_fab_assembly_step(
    members: list[dict[str, Any]],
    path: str | Path,
) -> Path:
    """Compound multiple feature-trees with placements into one STEP.

    Each member: ``{features: [...], origin_mm: [x,y,z], rotation_deg?: [rx,ry,rz]}``
    """
    require_cadquery()
    if not members:
        raise FabBrepError("empty assembly")
    compound = None
    for m in members:
        feats = list(m.get("features") or [])
        if not feats:
            continue
        solid = rebuild_solid(feats)
        ox, oy, oz = _origin(m)
        rot = m.get("rotation_deg") or m.get("rotation") or [0, 0, 0]
        rx, ry, rz = float(rot[0]), float(rot[1]), float(rot[2] if len(rot) > 2 else 0)
        # translate / rotate
        loc = solid.val()
        if abs(rx) + abs(ry) + abs(rz) > 1e-9:
            loc = loc.rotate((0, 0, 0), (1, 0, 0), rx)
            loc = loc.rotate((0, 0, 0), (0, 1, 0), ry)
            loc = loc.rotate((0, 0, 0), (0, 0, 1), rz)
        if abs(ox) + abs(oy) + abs(oz) > 1e-9:
            loc = loc.translate((ox, oy, oz))
        piece = cq.Workplane("XY").newObject([loc])
        compound = piece if compound is None else compound.union(piece)
    if compound is None:
        raise FabBrepError("assembly produced no solids")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(compound, str(out))
    return out


def tessellate_features(
    features: list[dict[str, Any]],
    *,
    linear_deflection: float = 0.25,
) -> tuple[list[float], list[float], list[int]]:
    """Rebuild → mesh triangles (metres, Y-up glTF convention from mm Z-up fab).

    Fab solids use Z-up mm. glTF: X=X, Y=Z, Z=Y (same as building mesh).
    """
    require_cadquery()
    solid = rebuild_solid(features)
    shape = solid.val().wrapped
    BRepMesh_IncrementalMesh(shape, float(linear_deflection), False, 0.5, True)

    pos: list[float] = []
    nrm: list[float] = []
    idx: list[int] = []
    base = 0
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face_s(exp.Current())
        loc = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, loc)
        if triangulation is not None:
            trsf = loc.Transformation()
            nodes = triangulation.NbNodes()
            ntris = triangulation.NbTriangles()
            for i in range(1, nodes + 1):
                p = triangulation.Node(i)
                p.Transform(trsf)
                # mm Z-up → m Y-up glTF
                pos.extend([p.X() / 1000.0, p.Z() / 1000.0, p.Y() / 1000.0])
                nrm.extend([0.0, 1.0, 0.0])
            reversed_face = face.Orientation() == TopAbs_REVERSED
            for i in range(1, ntris + 1):
                tri = triangulation.Triangle(i)
                a, b, c = tri.Get()
                if reversed_face:
                    idx.extend([base + a - 1, base + c - 1, base + b - 1])
                else:
                    idx.extend([base + a - 1, base + b - 1, base + c - 1])
            base += nodes
        exp.Next()

    # recompute normals from faces
    if pos and idx:
        nrm = [0.0] * len(pos)
        for i in range(0, len(idx), 3):
            ia, ib, ic = idx[i] * 3, idx[i + 1] * 3, idx[i + 2] * 3
            ax, ay, az = pos[ia], pos[ia + 1], pos[ia + 2]
            bx, by, bz = pos[ib], pos[ib + 1], pos[ib + 2]
            cx, cy, cz = pos[ic], pos[ic + 1], pos[ic + 2]
            ux, uy, uz = bx - ax, by - ay, bz - az
            vx, vy, vz = cx - ax, cy - ay, cz - az
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            nx, ny, nz = nx / ln, ny / ln, nz / ln
            for off in (ia, ib, ic):
                nrm[off] += nx
                nrm[off + 1] += ny
                nrm[off + 2] += nz
        for i in range(0, len(nrm), 3):
            ln = math.sqrt(nrm[i] ** 2 + nrm[i + 1] ** 2 + nrm[i + 2] ** 2) or 1.0
            nrm[i] /= ln
            nrm[i + 1] /= ln
            nrm[i + 2] /= ln
    return pos, nrm, idx


def solid_volume_mm3(features: list[dict[str, Any]]) -> float:
    require_cadquery()
    return float(rebuild_solid(features).val().Volume())
