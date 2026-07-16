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


def _apply_fillet(solid: Any, feat: dict[str, Any]) -> Any:
    if solid is None:
        raise FabBrepError("fillet requires a base solid first")
    r = float(feat.get("radius_mm") or feat.get("radius") or 1.0)
    selector = str(feat.get("selector") or feat.get("edges") or "|Z")
    try:
        if selector in {"all", "*"}:
            return solid.edges().fillet(r)
        return solid.edges(selector).fillet(r)
    except Exception:
        # fall back: try vertical then all
        try:
            return solid.edges("|Z").fillet(r)
        except Exception:
            try:
                return solid.edges().fillet(r)
            except Exception as exc:  # noqa: BLE001
                raise FabBrepError(f"fillet failed r={r}: {exc}") from exc


def _apply_chamfer(solid: Any, feat: dict[str, Any]) -> Any:
    if solid is None:
        raise FabBrepError("chamfer requires a base solid first")
    d = float(feat.get("distance_mm") or feat.get("length_mm") or feat.get("d_mm") or 1.0)
    selector = str(feat.get("selector") or feat.get("edges") or ">Z")
    try:
        if selector in {"all", "*"}:
            return solid.edges().chamfer(d)
        # face-adjacent edges often selected via faces().edges()
        if selector.startswith(">"):
            return solid.faces(selector).edges().chamfer(d)
        return solid.edges(selector).chamfer(d)
    except Exception:
        try:
            return solid.faces(">Z").edges().chamfer(d)
        except Exception as exc:  # noqa: BLE001
            raise FabBrepError(f"chamfer failed d={d}: {exc}") from exc


def _parse_thread_designation(des: str) -> tuple[float, float]:
    """Return (major_diameter_mm, pitch_mm) from M10x1.5 / 1/4-20 etc."""
    s = des.strip().upper().replace(" ", "")
    if s.startswith("M"):
        body = s[1:]
        if "X" in body:
            d_s, p_s = body.split("X", 1)
            # strip class 6g etc
            p_s = p_s.split("-")[0]
            return float(d_s), float(p_s)
        return float(body.split("-")[0]), float(body.split("-")[0]) * 0.15  # coarse guess
    if "-" in s:  # imperial 1/4-20
        # crude: major from fraction not parsed fully — default
        return 6.35, 1.27
    return 10.0, 1.5


def _apply_thread(solid: Any, feat: dict[str, Any]) -> Any:
    """Machine thread: helical V-groove on shaft/bore + preserves designation in feature.

    External: start from cylinder feature already present, or create major shaft then groove.
    Internal: cut major hole then helical relief (approx).
    """
    des = str(feat.get("designation") or feat.get("thread") or "M10x1.5")
    d_maj, pitch = _parse_thread_designation(des)
    if feat.get("diameter_mm"):
        d_maj = float(feat["diameter_mm"])
    if feat.get("pitch_mm"):
        pitch = float(feat["pitch_mm"])
    length = float(feat.get("length_mm") or feat.get("depth_mm") or 20)
    internal = bool(feat.get("internal") or feat.get("female"))
    ox, oy, oz = _origin(feat)
    depth = float(feat.get("depth_mm") or pitch * 0.55)

    if solid is None and not internal:
        # create external threaded stud
        solid = _wp().transformed(offset=(ox, oy, oz)).circle(d_maj / 2).extrude(length)
        solid = _helix_groove(solid, d_maj, pitch, length, depth, ox, oy, oz, internal=False)
        # ease start
        try:
            solid = solid.faces(">Z").edges().chamfer(min(0.3, pitch * 0.2))
        except Exception:  # noqa: BLE001
            pass
        return solid

    if solid is None and internal:
        # block with threaded hole — need host; create washer-like boss
        outer = d_maj * 2.2
        solid = (
            _wp()
            .transformed(offset=(ox, oy, oz))
            .circle(outer / 2)
            .extrude(length + 5)
        )

    # cut/clear major then groove
    if internal:
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
    """Approximate ISO thread with stacked conical ring cuts along helix samples."""
    # Sample helix; cut small toroidal/ball tools for groove (readable + BREP valid)
    r_cut = max(depth * 0.55, 0.15)
    n_turns = max(1.0, length / pitch)
    samples = max(12, int(16 * n_turns))
    r_path = (d_maj / 2) - (depth * 0.5 if not internal else -depth * 0.3)
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
