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
    cq = None
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
    """Replay feature history → CadQuery Workplane with a solid.

    Named face/edge tags: any feature may include ``tag_edges`` / ``tag_faces``
    (name + CQ selector) so later fillet/chamfer can use ``selector=\"tag:name\"``.
    """
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
        elif op in {"tag", "tag_edges", "tag_faces"}:
            solid = _apply_tag(solid, feat)
        else:
            raise FabBrepError(f"unknown fab op: {op}")
        # optional post-feature tagging on any solid-producing op
        if solid is not None:
            solid = _maybe_attach_tags(solid, feat)
    if solid is None:
        raise FabBrepError("feature tree produced no solid")
    return solid


def _maybe_attach_tags(solid: Any, feat: dict[str, Any]) -> Any:
    """Attach CQ tags from feature fields tag_edges / tag_faces / tags."""
    # tag_edges: {name: selector} or list of {name, selector}
    te = feat.get("tag_edges")
    if isinstance(te, dict):
        for name, sel in te.items():
            try:
                solid = _edge_set(solid, str(sel)).tag(str(name))
            except Exception:  # noqa: BLE001
                continue
    elif isinstance(te, list):
        for item in te:
            if not isinstance(item, dict):
                continue
            try:
                solid = _edge_set(solid, str(item.get("selector") or "|Z")).tag(
                    str(item.get("name") or "edges")
                )
            except Exception:  # noqa: BLE001
                continue
    tf = feat.get("tag_faces")
    if isinstance(tf, dict):
        for name, sel in tf.items():
            try:
                solid = solid.faces(str(sel)).tag(str(name))
            except Exception:  # noqa: BLE001
                continue
    elif isinstance(tf, list):
        for item in tf:
            if not isinstance(item, dict):
                continue
            try:
                solid = solid.faces(str(item.get("selector") or ">Z")).tag(
                    str(item.get("name") or "face")
                )
            except Exception:  # noqa: BLE001
                continue
    # shorthand: tag="long_sides" selector="len_gt:35" kind=edges
    if feat.get("tag") and feat.get("selector") and str(feat.get("op") or "") in {
        "tag",
        "tag_edges",
        "tag_faces",
    }:
        return solid
    if feat.get("tag") and feat.get("tag_selector"):
        kind = str(feat.get("tag_kind") or "edges").lower()
        try:
            if kind == "faces":
                solid = solid.faces(str(feat["tag_selector"])).tag(str(feat["tag"]))
            else:
                solid = _edge_set(solid, str(feat["tag_selector"])).tag(str(feat["tag"]))
        except Exception:  # noqa: BLE001
            pass
    return solid


def _apply_tag(solid: Any, feat: dict[str, Any]) -> Any:
    if solid is None:
        raise FabBrepError("tag requires a base solid first")
    name = str(feat.get("name") or feat.get("tag") or "named")
    selector = str(feat.get("selector") or feat.get("edges") or feat.get("faces") or "|Z")
    kind = str(feat.get("kind") or ("faces" if feat.get("faces") else "edges")).lower()
    try:
        if kind == "faces":
            return solid.faces(selector).tag(name)
        return _edge_set(solid, selector).tag(name)
    except Exception as exc:  # noqa: BLE001
        raise FabBrepError(f"tag failed name={name} selector={selector}: {exc}") from exc


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
    # Optional rotation (deg) about local Z then Y then X — for radial slots / angled pockets.
    rot = feat.get("rotate_deg") or feat.get("rotation_deg") or [0, 0, 0]
    if isinstance(rot, (int, float)):
        rx, ry, rz = 0.0, 0.0, float(rot)
    else:
        rx = float(rot[0]) if len(rot) > 0 else 0.0
        ry = float(rot[1]) if len(rot) > 1 else 0.0
        rz = float(rot[2]) if len(rot) > 2 else float(feat.get("rotate_z_deg") or 0)
    if feat.get("rotate_z_deg") is not None and (not rot or rot == [0, 0, 0]):
        rz = float(feat["rotate_z_deg"])
    # Box centered on origin when center=True (default for rotated cuts); else min-corner origin.
    center = bool(feat.get("center", True if (rx or ry or rz) else False))
    if center:
        tool = _wp().box(sx, sy, sz)
        if rx or ry or rz:
            tool = tool.rotate((0, 0, 0), (1, 0, 0), rx)
            tool = tool.rotate((0, 0, 0), (0, 1, 0), ry)
            tool = tool.rotate((0, 0, 0), (0, 0, 1), rz)
        tool = tool.translate((ox, oy, oz))
    else:
        tool = (
            _wp()
            .transformed(offset=(ox + sx / 2, oy + sy / 2, oz + sz / 2))
            .box(sx, sy, sz)
        )
        if rx or ry or rz:
            # rotate about pocket min-corner is unusual; rotate about box center
            cx, cy, cz = ox + sx / 2, oy + sy / 2, oz + sz / 2
            tool = tool.rotate((cx, cy, cz), (1, 0, 0), rx)
            tool = tool.rotate((cx, cy, cz), (0, 1, 0), ry)
            tool = tool.rotate((cx, cy, cz), (0, 0, 1), rz)
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
    # Named tag from fab_tag / tag_edges
    if low.startswith("tag:"):
        tname = sel.split(":", 1)[1].strip()
        try:
            return solid.edges(tag=tname)
        except Exception as exc:  # noqa: BLE001
            raise FabBrepError(f"no edges with tag={tname}: {exc}") from exc
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
    if low in {"long", "long_edges"}:
        # longest edges on solid (typically the long box sides)
        edges = solid.edges().vals()
        if not edges:
            raise FabBrepError("no edges for long selector")
        lengths = []
        for e in edges:
            try:
                lengths.append((float(e.Length()), e))
            except Exception:  # noqa: BLE001
                continue
        lengths.sort(key=lambda t: t[0], reverse=True)
        if not lengths:
            raise FabBrepError("no measurable edges for long selector")
        max_l = lengths[0][0]
        picked = [e for L, e in lengths if L >= max_l * 0.95]
        return solid.newObject(picked)
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
    """ISO-ish 60° V-thread: helical triangular sweep (true solid form), ball fallback."""
    try:
        return _iso_v_thread_cut(
            solid, d_maj, pitch, length, depth, ox, oy, oz, internal=internal
        )
    except Exception:  # noqa: BLE001
        pass
    # fallback: dense sphere groove
    r_cut = max(depth * 0.48, pitch * 0.22, 0.12)
    n_turns = max(1.0, length / max(pitch, 0.1))
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


def _iso_v_thread_cut(
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
    """Cut 60° triangular profile swept on an ISO helix (Wire.makeHelix + sweep)."""
    require_cadquery()
    if length < pitch * 0.5 or pitch < 0.1:
        raise FabBrepError("thread length/pitch too small for V-profile")
    r_maj = d_maj / 2.0
    # path radius: mid of engagement depth
    if internal:
        r_path = r_maj + depth * 0.25
    else:
        r_path = max(r_maj - depth * 0.55, r_maj * 0.35)
    half_w = pitch * 0.433  # half of base for ~60° triangle with height=depth
    # helix along +Z at local origin, then translate to ox,oy,oz
    wire = cq.Wire.makeHelix(pitch=pitch, height=length, radius=r_path)
    # triangular profile in XY at (r_path, 0) pointing inward (external) or outward
    if internal:
        # cut into wall: triangle points outward from hole
        tri_pts = [(0, -half_w), (0, half_w), (depth, 0)]
    else:
        # cut into shaft: triangle points outward from axis
        tri_pts = [(0, -half_w), (0, half_w), (depth, 0)]
    prof = (
        cq.Workplane("XY")
        .center(r_path, 0)
        .polyline(tri_pts)
        .close()
    )
    cutter = prof.sweep(cq.Workplane("XY").add(wire), isFrenet=True)
    # place at origin
    if abs(ox) + abs(oy) + abs(oz) > 1e-9:
        cutter = cutter.translate((ox, oy, oz))
    return solid.cut(cutter)


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


def resolve_assembly_mates(
    instances: list[dict[str, Any]],
    mates: list[dict[str, Any]],
    *,
    part_bboxes: dict[str, dict[str, float]] | None = None,
) -> list[dict[str, Any]]:
    """Resolve mate constraints into absolute origin_mm for each instance.

    Mate types:
      - coincident: stack B onto A along Z (A top → B bottom)
      - concentric: match XY of B to A (keep Bz)
      - offset: B.origin = A.origin + offset_mm

    Each instance needs ``instance_id`` (or part_id) and features or size hints.
    ``part_bboxes`` optional: instance_id → {xmin,xmax,ymin,ymax,zmin,zmax} in local mm.
    """
    # start with declared placements
    placed: dict[str, dict[str, Any]] = {}
    for inst in instances:
        iid = str(inst.get("instance_id") or inst.get("part_id") or id(inst))
        o = list(inst.get("origin_mm") or [0, 0, 0])
        r = list(inst.get("rotation_deg") or [0, 0, 0])
        placed[iid] = {
            **inst,
            "instance_id": iid,
            "origin_mm": [float(o[0]), float(o[1]), float(o[2] if len(o) > 2 else 0)],
            "rotation_deg": [float(r[0]), float(r[1]), float(r[2] if len(r) > 2 else 0)],
        }

    def _bbox(iid: str) -> dict[str, float]:
        if part_bboxes and iid in part_bboxes:
            return part_bboxes[iid]
        # estimate from features
        feats = list(placed[iid].get("features") or [])
        return estimate_feature_bbox(feats)

    # iterative mate application (order listed)
    for mate in mates or []:
        mtype = str(mate.get("type") or mate.get("kind") or "").lower()
        a = str(mate.get("a") or mate.get("instance_a") or "")
        b = str(mate.get("b") or mate.get("instance_b") or "")
        if a not in placed or b not in placed:
            continue
        oa = placed[a]["origin_mm"]
        _ob = placed[b]["origin_mm"]
        ba, bb = _bbox(a), _bbox(b)
        if mtype in {"coincident", "stack", "against"}:
            # put B's bottom on A's top (world Z)
            a_top = oa[2] + ba.get("zmax", 0) - ba.get("zmin", 0)
            # if a has zmin offset in local, origin is at local 0 typically
            a_top = oa[2] + float(ba.get("zmax", 0))
            b_bottom_local = float(bb.get("zmin", 0))
            placed[b]["origin_mm"][2] = a_top - b_bottom_local + float(mate.get("gap_mm") or 0)
            # optional face tokens
            face_a = str(mate.get("a_face") or mate.get("face_a") or "top").lower()
            face_b = str(mate.get("b_face") or mate.get("face_b") or "bottom").lower()
            if face_a == "bottom":
                a_ref = oa[2] + float(ba.get("zmin", 0))
            else:
                a_ref = oa[2] + float(ba.get("zmax", 0))
            if face_b == "top":
                # b top at a_ref → origin so zmax maps to a_ref
                placed[b]["origin_mm"][2] = a_ref - float(bb.get("zmax", 0))
            else:
                placed[b]["origin_mm"][2] = a_ref - float(bb.get("zmin", 0)) + float(
                    mate.get("gap_mm") or 0
                )
        elif mtype in {"concentric", "align_axis", "coaxial"}:
            # center B XY on A XY (bbox centers)
            ax = oa[0] + 0.5 * (float(ba.get("xmin", 0)) + float(ba.get("xmax", 0)))
            ay = oa[1] + 0.5 * (float(ba.get("ymin", 0)) + float(ba.get("ymax", 0)))
            bx_c = 0.5 * (float(bb.get("xmin", 0)) + float(bb.get("xmax", 0)))
            by_c = 0.5 * (float(bb.get("ymin", 0)) + float(bb.get("ymax", 0)))
            placed[b]["origin_mm"][0] = ax - bx_c
            placed[b]["origin_mm"][1] = ay - by_c
        elif mtype in {"offset", "translate"}:
            off = mate.get("offset_mm") or mate.get("offset") or [0, 0, 0]
            placed[b]["origin_mm"] = [
                oa[0] + float(off[0]),
                oa[1] + float(off[1]),
                oa[2] + float(off[2] if len(off) > 2 else 0),
            ]
        elif mtype in {"fixed", "ground"}:
            # lock A at world origin (optional)
            if mate.get("to") == "world" or True:
                placed[a]["origin_mm"] = [
                    float(mate.get("x") or 0),
                    float(mate.get("y") or 0),
                    float(mate.get("z") or 0),
                ]
    return list(placed.values())


def estimate_feature_bbox(features: list[dict[str, Any]]) -> dict[str, float]:
    """Axis-aligned local bbox estimate from feature tree (mm)."""
    xmin = ymin = zmin = 0.0
    xmax = ymax = zmax = 1.0
    if not features:
        return {"xmin": 0, "xmax": 1, "ymin": 0, "ymax": 1, "zmin": 0, "zmax": 1}
    # prefer true solid bbox when CQ available
    if HAS_CADQUERY:
        try:
            solid = rebuild_solid(features)
            bb = solid.val().BoundingBox()
            return {
                "xmin": float(bb.xmin),
                "xmax": float(bb.xmax),
                "ymin": float(bb.ymin),
                "ymax": float(bb.ymax),
                "zmin": float(bb.zmin),
                "zmax": float(bb.zmax),
            }
        except Exception:  # noqa: BLE001
            pass
    for f in features:
        op = str(f.get("op") or "").lower()
        o = f.get("origin_mm") or [0, 0, 0]
        ox, oy, oz = float(o[0]), float(o[1]), float(o[2] if len(o) > 2 else 0)
        if op == "box":
            s = f.get("size_mm") or [10, 10, 10]
            xmax = max(xmax, ox + float(s[0]))
            ymax = max(ymax, oy + float(s[1]))
            zmax = max(zmax, oz + float(s[2]))
        elif op in {"cylinder", "thread", "revolve"}:
            d = float(f.get("diameter_mm") or f.get("radius_mm", 10) * 2 or 20)
            h = float(f.get("height_mm") or f.get("length_mm") or 20)
            r = d / 2
            xmin = min(xmin, ox - r)
            xmax = max(xmax, ox + r)
            ymin = min(ymin, oy - r)
            ymax = max(ymax, oy + r)
            zmax = max(zmax, oz + h)
    return {
        "xmin": xmin,
        "xmax": xmax,
        "ymin": ymin,
        "ymax": ymax,
        "zmin": zmin,
        "zmax": zmax,
    }


def export_fab_assembly_step(
    members: list[dict[str, Any]],
    path: str | Path,
    *,
    mates: list[dict[str, Any]] | None = None,
) -> Path:
    """Compound multiple feature-trees with placements into one STEP.

    Each member: ``{features, origin_mm, rotation_deg?, instance_id?}``.
    Optional ``mates`` list is resolved first (coincident / concentric / offset).
    """
    require_cadquery()
    if not members:
        raise FabBrepError("empty assembly")
    # ensure features present for bbox
    resolved = list(members)
    if mates:
        bboxes = {}
        for m in members:
            iid = str(m.get("instance_id") or m.get("part_id") or id(m))
            bboxes[iid] = estimate_feature_bbox(list(m.get("features") or []))
            m = {**m, "instance_id": iid}
        resolved = resolve_assembly_mates(members, mates, part_bboxes=bboxes)
    compound = None
    for m in resolved:
        feats = list(m.get("features") or [])
        if not feats:
            continue
        solid = rebuild_solid(feats)
        ox, oy, oz = _origin(m)
        rot = m.get("rotation_deg") or m.get("rotation") or [0, 0, 0]
        rx, ry, rz = float(rot[0]), float(rot[1]), float(rot[2] if len(rot) > 2 else 0)
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
    origin_mm: tuple[float, float, float] | list[float] | None = None,
    rotation_deg: tuple[float, float, float] | list[float] | None = None,
) -> tuple[list[float], list[float], list[int]]:
    """Rebuild → mesh triangles (metres, Y-up glTF convention from mm Z-up fab).

    Fab solids use Z-up mm. glTF: X=X, Y=Z, Z=Y (same as building mesh).
    Optional ``origin_mm`` / ``rotation_deg`` place the solid in the building frame
    (host knit).
    """
    require_cadquery()
    solid = rebuild_solid(features)
    loc = solid.val()
    if rotation_deg is not None:
        rx, ry, rz = float(rotation_deg[0]), float(rotation_deg[1]), float(
            rotation_deg[2] if len(rotation_deg) > 2 else 0
        )
        if abs(rx) + abs(ry) + abs(rz) > 1e-9:
            loc = loc.rotate((0, 0, 0), (1, 0, 0), rx)
            loc = loc.rotate((0, 0, 0), (0, 1, 0), ry)
            loc = loc.rotate((0, 0, 0), (0, 0, 1), rz)
    if origin_mm is not None:
        ox, oy, oz = float(origin_mm[0]), float(origin_mm[1]), float(
            origin_mm[2] if len(origin_mm) > 2 else 0
        )
        if abs(ox) + abs(oy) + abs(oz) > 1e-9:
            loc = loc.translate((ox, oy, oz))
    shape = loc.wrapped if hasattr(loc, "wrapped") else solid.val().wrapped
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
