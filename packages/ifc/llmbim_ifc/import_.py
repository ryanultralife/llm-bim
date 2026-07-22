"""IFC4 SPF importer (round-trips files written by ``llmbim_ifc.export``).

Hand-rolled STEP Physical File parser — no ifcopenshell required. Reads the
entity patterns our own writer emits (storey-relative IfcLocalPlacement
chains, IfcWallStandardCase with a centered IfcRectangleProfileDef, hosted
openings via IfcRelVoidsElement/IfcRelFillsElement, box proxies, flow
segments, spaces) and rebuilds native model elements with world-mm geometry.

Corner joins: the writer inflates a wall profile's XDim by ext0/ext1 (half the
meeting wall's thickness at each joined end) while keeping the placement point
at the TRUE wall start; the profile center cx encodes the start extension
exactly (ext0 = XDim/2 - cx), so it is always undone. The end extension ext1
is not stored; it is recovered by snapping the wall axis against the other
walls (end-to-start joins and non-parallel end-to-end joins resolve exactly).
Where no partner geometry matches, the extended length is kept and the wall is
flagged ``ifc_length_approx`` (error <= half the thickest meeting wall).

Rooms: IfcSpace carries no boundary geometry in our SPF (min-corner placement
+ name/height in Description only), so imported rooms get an exact min corner
but a placeholder 1000x1000mm extent, flagged ``ifc_extent_approx``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llmbim_core.ids import new_id
from llmbim_core.model import Element, ProjectModel

_ENTITY_RE = re.compile(r"#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*)\);\s*$")
_REF_RE = re.compile(r"#(\d+)")

# The writer joins wall ends that meet within 25mm; +1mm slack for float text.
_JOIN_TOL_MM = 26.0

# Entity types converted into model elements.
_HANDLED = {
    "IFCBUILDINGSTOREY",
    "IFCWALL",
    "IFCWALLSTANDARDCASE",
    "IFCSLAB",
    "IFCDOOR",
    "IFCWINDOW",
    "IFCSPACE",
    "IFCFLOWSEGMENT",
    "IFCPIPESEGMENT",
    "IFCDUCTSEGMENT",
    "IFCCABLECARRIERSEGMENT",
    "IFCBUILDINGELEMENTPROXY",
    "IFCCOLUMN",
    "IFCBEAM",
    "IFCFLOWFITTING",
    "IFCFLOWTERMINAL",
}
# Support/bookkeeping entities that are consumed indirectly (not "skipped").
_SUPPORT = {
    "IFCCARTESIANPOINT",
    "IFCDIRECTION",
    "IFCAXIS2PLACEMENT2D",
    "IFCAXIS2PLACEMENT3D",
    "IFCLOCALPLACEMENT",
    "IFCRECTANGLEPROFILEDEF",
    "IFCEXTRUDEDAREASOLID",
    "IFCSHAPEREPRESENTATION",
    "IFCPRODUCTDEFINITIONSHAPE",
    "IFCGEOMETRICREPRESENTATIONCONTEXT",
    "IFCGEOMETRICREPRESENTATIONSUBCONTEXT",
    "IFCSIUNIT",
    "IFCUNITASSIGNMENT",
    "IFCPROJECT",
    "IFCSITE",
    "IFCBUILDING",
    "IFCPERSON",
    "IFCORGANIZATION",
    "IFCAPPLICATION",
    "IFCPERSONANDORGANIZATION",
    "IFCOWNERHISTORY",
    "IFCRELAGGREGATES",
    "IFCRELCONTAINEDINSPATIALSTRUCTURE",
    "IFCRELVOIDSELEMENT",
    "IFCRELFILLSELEMENT",
    "IFCRELDEFINESBYPROPERTIES",
    "IFCPROPERTYSET",
    "IFCPROPERTYSINGLEVALUE",
    "IFCOPENINGELEMENT",
    "IFCMATERIAL",
    "IFCRELASSOCIATESMATERIAL",
    "IFCSYSTEM",
    "IFCRELASSIGNSTOGROUP",
    "IFCRELSERVICESBUILDINGS",
}


def _split_args(body: str) -> list[str]:
    """Top-level comma split, aware of nesting and of ``'...'`` strings."""
    out: list[str] = []
    depth = 0
    in_str = False
    cur = ""
    for ch in body:
        if ch == "'":
            in_str = not in_str
            cur += ch
            continue
        if not in_str:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            if ch == "," and depth == 0:
                out.append(cur)
                cur = ""
                continue
        cur += ch
    out.append(cur)
    return out


def _ref(token: str) -> int | None:
    token = token.strip()
    if token.startswith("#"):
        try:
            return int(token[1:])
        except ValueError:
            return None
    return None


def _unstr(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and token.startswith("'") and token.endswith("'"):
        return token[1:-1].replace("''", "'")
    return ""


def _num(token: str) -> float | None:
    try:
        return float(token.strip())
    except ValueError:
        return None


@dataclass
class _RawWall:
    ent: int
    name: str
    sx: float
    sy: float
    dx: float  # unit direction
    dy: float
    th: float
    height: float
    l_raw: float  # XDim - ext0 (true length + unresolved ext1)
    ext0: float
    length: float = 0.0
    resolved: bool = True


class _Spf:
    """Indexed STEP file: entity args, placement chains, extruded profiles."""

    def __init__(self, ent: dict[int, tuple[str, str]]) -> None:
        self.ent = ent
        self._args: dict[int, list[str]] = {}
        self._plc: dict[int, tuple[float, float, float, float]] = {}

    def typ(self, i: int | None) -> str:
        if i is None or i not in self.ent:
            return ""
        return self.ent[i][0]

    def args(self, i: int) -> list[str]:
        if i not in self._args:
            self._args[i] = _split_args(self.ent[i][1])
        return self._args[i]

    def coords(self, i: int | None) -> tuple[float, ...]:
        """Numbers of an IfcCartesianPoint / IfcDirection."""
        if i is None or self.typ(i) not in {"IFCCARTESIANPOINT", "IFCDIRECTION"}:
            return ()
        inner = self.args(i)[0].strip().strip("()")
        vals: list[float] = []
        for tok in inner.split(","):
            v = _num(tok)
            if v is None:
                return ()
            vals.append(v)
        return tuple(vals)

    def _axis_local(self, a3: int | None) -> tuple[float, float, float, float]:
        """(x, y, z, z-rotation rad) of an IfcAxis2Placement3D."""
        lx = ly = lz = 0.0
        ang = 0.0
        if a3 is not None and self.typ(a3) == "IFCAXIS2PLACEMENT3D":
            pa = self.args(a3)
            c = self.coords(_ref(pa[0]))
            if len(c) >= 2:
                lx, ly = c[0], c[1]
                lz = c[2] if len(c) > 2 else 0.0
            if len(pa) > 2:
                d = self.coords(_ref(pa[2]))
                if len(d) >= 2 and (abs(d[0]) > 1e-12 or abs(d[1]) > 1e-12):
                    ang = math.atan2(d[1], d[0])
        return lx, ly, lz, ang

    def placement(self, loc: int | None) -> tuple[float, float, float, float]:
        """World (x, y, z, rotation rad) of an IfcLocalPlacement chain.

        Only Z-axis rotations are composed — the only kind our writer emits.
        """
        if loc is None or self.typ(loc) != "IFCLOCALPLACEMENT":
            return 0.0, 0.0, 0.0, 0.0
        if loc in self._plc:
            return self._plc[loc]
        a = self.args(loc)
        parent = _ref(a[0])
        lx, ly, lz, ang = self._axis_local(_ref(a[1]))
        if parent is None:
            res = (lx, ly, lz, ang)
        else:
            px, py, pz, pang = self.placement(parent)
            ca, sa = math.cos(pang), math.sin(pang)
            res = (px + ca * lx - sa * ly, py + sa * lx + ca * ly, pz + lz, pang + ang)
        self._plc[loc] = res
        return res

    def local_point(self, loc: int | None) -> tuple[float, float, float]:
        """Placement point WITHOUT parent composition (e.g. opening-in-wall)."""
        if loc is None or self.typ(loc) != "IFCLOCALPLACEMENT":
            return 0.0, 0.0, 0.0
        lx, ly, lz, _ang = self._axis_local(_ref(self.args(loc)[1]))
        return lx, ly, lz

    def profile(self, prod: int | None) -> tuple[float, float, float, float, float] | None:
        """(xdim, ydim, depth, cx, cy) from ProductDefinitionShape →
        ShapeRepresentation → ExtrudedAreaSolid → RectangleProfileDef."""
        if prod is None or self.typ(prod) != "IFCPRODUCTDEFINITIONSHAPE":
            return None
        pa = self.args(prod)
        if len(pa) < 3:
            return None
        for rep_ref in _REF_RE.findall(pa[2]):
            rep = int(rep_ref)
            if self.typ(rep) != "IFCSHAPEREPRESENTATION":
                continue
            ra = self.args(rep)
            if len(ra) < 4:
                continue
            for item_ref in _REF_RE.findall(ra[3]):
                item = int(item_ref)
                if self.typ(item) != "IFCEXTRUDEDAREASOLID":
                    continue
                ea = self.args(item)
                if len(ea) < 4:
                    continue
                depth = _num(ea[3])
                pr = _ref(ea[0])
                if depth is None or pr is None or self.typ(pr) != "IFCRECTANGLEPROFILEDEF":
                    continue
                fa = self.args(pr)
                if len(fa) < 5:
                    continue
                xdim, ydim = _num(fa[3]), _num(fa[4])
                if xdim is None or ydim is None:
                    continue
                cx = cy = 0.0
                a2d = _ref(fa[2])
                if a2d is not None and self.typ(a2d) == "IFCAXIS2PLACEMENT2D":
                    c = self.coords(_ref(self.args(a2d)[0]))
                    if len(c) >= 2:
                        cx, cy = c[0], c[1]
                return xdim, ydim, depth, cx, cy
        return None


def _length_scale(spf: _Spf) -> float:
    """mm per file unit: 1.0 for MILLI METRE files (ours), 1000.0 for metres."""
    for i, (typ, body) in spf.ent.items():
        if typ == "IFCSIUNIT" and ".LENGTHUNIT." in body:
            _ = i
            return 1.0 if ".MILLI." in body else 1000.0
    return 1.0


def _resolve_wall_ends(walls: list[_RawWall]) -> None:
    """Undo the end-side corner-join extension ext1 where partner walls allow.

    Two exactly-resolvable cases (mirrors ``export._wall_join_extensions``):
    end-to-start — another wall's TRUE start (placement point) lies on this
    wall's axis where ``l_raw == p + partner_th/2``; end-to-end — the two wall
    axes intersect and BOTH raw lengths overshoot the intersection by half the
    other wall's thickness. Otherwise the (possibly extended) length stands.
    """
    tol = _JOIN_TOL_MM
    for a in walls:
        best: tuple[float, float] | None = None  # (error, true length)
        for b in walls:
            if b is a:
                continue
            vx, vy = b.sx - a.sx, b.sy - a.sy
            # end-to-start: b's start is exact; project onto a's axis
            p = vx * a.dx + vy * a.dy
            perp = abs(vx * a.dy - vy * a.dx)
            if perp <= tol and p > tol:
                err = abs(a.l_raw - (p + b.th / 2.0))
                if err <= tol and (best is None or err < best[0]):
                    best = (err, p)
            # end-to-end: intersect the two wall axes
            denom = a.dx * b.dy - a.dy * b.dx
            if abs(denom) > 1e-9:
                t = (vx * b.dy - vy * b.dx) / denom
                u = (vx * a.dy - vy * a.dx) / denom
                if t > tol and u > tol:
                    err_a = abs(a.l_raw - (t + b.th / 2.0))
                    err_b = abs(b.l_raw - (u + a.th / 2.0))
                    err = max(err_a, err_b)
                    if err <= tol and (best is None or err < best[0]):
                        best = (err, t)
        if best is not None:
            a.length = best[1]
            a.resolved = True
        else:
            a.length = a.l_raw
            # ext0 > 0 proves this wall participates in joins; its far end may
            # then also be extended without a resolvable partner signature.
            a.resolved = a.ext0 <= 1e-6


def _split_leaf_tag(tag: str) -> tuple[str, str]:
    """Writer door/window Tag → (type_id, fire_rating)."""
    if not tag:
        return "", ""
    m = re.search(r"(?:^|-)FR([^-]+)$", tag)
    if m:
        base = tag[: m.start()]
        return base, m.group(1)
    return tag, ""


def _parse_mep_tag(tag: str) -> dict[str, Any]:
    """Writer MEP Tag (FTYPE[-SECTION][-NPSx][-RISER][-SYSTEM][-FRx])."""
    out: dict[str, Any] = {}
    rest: list[str] = []
    for i, tok in enumerate(tag.split("-") if tag else []):
        if i == 0:
            out["ftype"] = tok.lower()
        elif tok.upper().startswith("NPS") and len(tok) > 3:
            out["nps"] = tok[3:]
        elif tok.upper() == "RISER":
            out["vertical"] = True
        elif tok.upper().startswith("FR") and len(tok) > 2:
            out["fire_rating"] = tok[2:]
        elif tok:
            rest.append(tok)
    if rest:
        out["system"] = rest[-1]
    return out


_PROXY_CATEGORY = {
    "IFCBUILDINGELEMENTPROXY": ("equipment", "eqp"),
    "IFCCOLUMN": ("column", "col"),
    "IFCBEAM": ("beam", "bem"),
    "IFCFLOWFITTING": ("fitting", "fit"),
    "IFCFLOWTERMINAL": ("fixture", "fix"),
}

_SEGMENT_CATEGORY = {"duct", "hvac", "cable_tray", "conduit", "plumbing_pipe"}


def import_ifc(model: ProjectModel, path: str | Path) -> dict[str, Any]:
    """Import an IFC4 SPF file into ``model`` with real geometry recovery.

    Returns a summary dict: created counts per category, skipped entity type
    counts, warnings, and the created element ids.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    if "ISO-10303-21" not in text:
        raise ValueError(f"Not a STEP/IFC SPF file: {path}")
    ent: dict[int, tuple[str, str]] = {}
    for line in text.splitlines():
        m = _ENTITY_RE.match(line.strip())
        if m:
            ent[int(m.group(1))] = (m.group(2), m.group(3))
    if not ent:
        raise ValueError(f"No IFC entities found in {path}")

    spf = _Spf(ent)
    scale = _length_scale(spf)
    warnings: list[str] = []
    created_ids: list[str] = []
    counts: dict[str, int] = {}

    def _count(key: str) -> None:
        counts[key] = counts.get(key, 0) + 1

    # --- levels from storeys -------------------------------------------------
    storey_level: dict[int, str] = {}  # storey entity -> Level.id
    levels_created = 0
    storeys: list[tuple[int, str, float]] = []
    for i, (typ, _body) in ent.items():
        if typ != "IFCBUILDINGSTOREY":
            continue
        a = spf.args(i)
        name = _unstr(a[2]) if len(a) > 2 else ""
        elev = _num(a[-1]) if a else None
        if elev is None:  # $ elevation — fall back to the placement chain Z
            elev = spf.placement(_ref(a[5]) if len(a) > 5 else None)[2]
        storeys.append((i, name, float(elev) * scale))
    for n, (sid, name, elev_mm) in enumerate(sorted(storeys, key=lambda s: s[2])):
        name = name or f"Storey-{n + 1}"
        existing = next((lv for lv in model.levels if lv.name == name), None)
        if existing is not None:
            storey_level[sid] = existing.id
            continue
        lv = model.add_level(name, elev_mm)
        storey_level[sid] = lv.id
        levels_created += 1
    if not model.levels:
        model.add_level("L1", 0)
        levels_created += 1
    level_elev = {lv.id: lv.elevation_mm for lv in model.levels}
    default_level_id = model.levels[0].id

    # --- spatial containment (product entity -> storey entity) --------------
    container: dict[int, int] = {}
    for i, (typ, _body) in ent.items():
        if typ != "IFCRELCONTAINEDINSPATIALSTRUCTURE":
            continue
        a = spf.args(i)
        if len(a) < 6:
            continue
        target = _ref(a[5])
        if target is not None and spf.typ(target) == "IFCBUILDINGSTOREY":
            for r in _REF_RE.findall(a[4]):
                container[int(r)] = target

    def level_of(eid: int) -> str:
        sid = container.get(eid)
        if sid is not None and sid in storey_level:
            return storey_level[sid]
        return default_level_id

    # --- opening relationships ----------------------------------------------
    voids: dict[int, int] = {}  # opening entity -> host wall entity
    fills: dict[int, int] = {}  # door/window entity -> opening entity
    for i, (typ, _body) in ent.items():
        if typ == "IFCRELVOIDSELEMENT":
            a = spf.args(i)
            host, opening = (_ref(a[4]), _ref(a[5])) if len(a) > 5 else (None, None)
            if host is not None and opening is not None:
                voids[opening] = host
        elif typ == "IFCRELFILLSELEMENT":
            a = spf.args(i)
            opening, leaf = (_ref(a[4]), _ref(a[5])) if len(a) > 5 else (None, None)
            if opening is not None and leaf is not None:
                fills[leaf] = opening

    # --- walls ---------------------------------------------------------------
    raw_walls: list[_RawWall] = []
    for i, (typ, _body) in ent.items():
        if typ not in {"IFCWALL", "IFCWALLSTANDARDCASE"}:
            continue
        a = spf.args(i)
        if len(a) < 7:
            warnings.append(f"wall #{i}: too few attributes; skipped")
            continue
        pr = spf.profile(_ref(a[6]))
        if pr is None:
            warnings.append(f"wall #{i} ({_unstr(a[2])}): no rectangle profile; skipped")
            continue
        wx, wy, _wz, ang = spf.placement(_ref(a[5]))
        xdim, ydim, depth, cx, _cy = pr
        xdim, ydim, depth, cx = xdim * scale, ydim * scale, depth * scale, cx * scale
        ext0 = max(0.0, xdim / 2.0 - cx)
        raw_walls.append(
            _RawWall(
                ent=i,
                name=_unstr(a[2]),
                sx=wx * scale,
                sy=wy * scale,
                dx=math.cos(ang),
                dy=math.sin(ang),
                th=ydim,
                height=depth,
                l_raw=xdim - ext0,
                ext0=ext0,
            )
        )
    _resolve_wall_ends(raw_walls)

    wall_elem_by_ent: dict[int, Element] = {}
    for w in raw_walls:
        params: dict[str, Any] = {
            "start_mm": [w.sx, w.sy],
            "end_mm": [w.sx + w.dx * w.length, w.sy + w.dy * w.length],
            "thickness_mm": w.th,
            "height_mm": w.height,
            "length_mm": w.length,
            "source": "ifc",
        }
        if not w.resolved:
            params["ifc_length_approx"] = True
            warnings.append(
                f"wall '{w.name or w.ent}': end-side corner-join extension not "
                f"resolvable; length kept at {w.length:.0f}mm (may be extended)"
            )
        el = Element(
            id=new_id("wal"),
            category="wall",
            name=w.name,
            level_id=level_of(w.ent),
            params=params,
        )
        model.add_element(el)
        wall_elem_by_ent[w.ent] = el
        created_ids.append(el.id)
        _count("walls")

    # --- doors / windows (hosted via voids + fills) --------------------------
    for i, (typ, _body) in ent.items():
        if typ not in {"IFCDOOR", "IFCWINDOW"}:
            continue
        a = spf.args(i)
        if len(a) < 10:
            warnings.append(f"{typ.lower()} #{i}: too few attributes; skipped")
            continue
        height = _num(a[8])
        width = _num(a[9])
        if height is None or width is None:
            warnings.append(f"{typ.lower()} #{i}: no overall width/height; skipped")
            continue
        width, height = width * scale, height * scale
        offset = 0.0
        sill = 0.0
        host_el: Element | None = None
        opening = fills.get(i)
        if opening is not None:
            host_el = wall_elem_by_ent.get(voids.get(opening, -1))
            op_args = spf.args(opening)
            if len(op_args) > 5:
                ox, _oy, oz = spf.local_point(_ref(op_args[5]))
                offset, sill = ox * scale, oz * scale
        if host_el is None:
            warnings.append(f"{typ.lower()} #{i} ({_unstr(a[2])}): host wall not found; unhosted")
        is_door = typ == "IFCDOOR"
        type_id, fire_rating = _split_leaf_tag(_unstr(a[7]))
        params = {
            "offset_mm": offset,
            "width_mm": width,
            "height_mm": height,
            "source": "ifc",
        }
        if not is_door or sill > 1e-6:
            params["sill_mm"] = sill
        if type_id:
            params["type_id"] = type_id
        if fire_rating:
            params["fire_rating"] = fire_rating
        el = Element(
            id=new_id("dor" if is_door else "wnd"),
            category="door" if is_door else "window",
            name=_unstr(a[2]),
            level_id=host_el.level_id if host_el is not None else level_of(i),
            host_id=host_el.id if host_el is not None else None,
            type_id=type_id or None,
            params=params,
        )
        model.add_element(el)
        created_ids.append(el.id)
        _count("doors" if is_door else "windows")

    # --- slabs (rectangular extrusion -> bbox polygon) -----------------------
    for i, (typ, _body) in ent.items():
        if typ != "IFCSLAB":
            continue
        a = spf.args(i)
        if len(a) < 7:
            continue
        pr = spf.profile(_ref(a[6]))
        if pr is None:
            warnings.append(f"slab #{i}: no rectangle profile; skipped")
            continue
        sx, sy, _sz, _ang = spf.placement(_ref(a[5]))
        dx, dy, depth = pr[0] * scale, pr[1] * scale, pr[2] * scale
        x0, y0 = sx * scale, sy * scale
        el = Element(
            id=new_id("slb"),
            category="slab",
            name=_unstr(a[2]),
            level_id=level_of(i),
            params={
                "polygon_mm": [[x0, y0], [x0 + dx, y0], [x0 + dx, y0 + dy], [x0, y0 + dy]],
                "thickness_mm": depth,
                "area_mm2": dx * dy,
                "source": "ifc",
            },
        )
        model.add_element(el)
        created_ids.append(el.id)
        _count("slabs")

    # --- box proxies: equipment / columns / beams / fittings / fixtures ------
    for i, (typ, _body) in ent.items():
        if typ not in _PROXY_CATEGORY:
            continue
        category, prefix = _PROXY_CATEGORY[typ]
        a = spf.args(i)
        if len(a) < 7:
            continue
        pr = spf.profile(_ref(a[6]))
        if pr is None:
            warnings.append(f"{typ.lower()} #{i}: no rectangle profile; skipped")
            continue
        px, py, pz, _ang = spf.placement(_ref(a[5]))
        lx, ly, hz = pr[0] * scale, pr[1] * scale, pr[2] * scale
        x0, y0 = px * scale, py * scale
        lvl = level_of(i)
        z0 = pz * scale - level_elev.get(lvl, 0.0)
        params = {
            "kind": category,
            "shape": "box",
            "origin_mm": [x0, y0],
            "size_mm": [lx, ly, hz],
            "z0_mm": z0,
            "polygon_mm": [[x0, y0], [x0 + lx, y0], [x0 + lx, y0 + ly], [x0, y0 + ly]],
            "source": "ifc",
        }
        tag = _unstr(a[3])
        if tag:
            params["ifc_tag"] = tag
        el = Element(
            id=new_id(prefix),
            category=category,
            name=_unstr(a[2]),
            level_id=lvl,
            params=params,
        )
        model.add_element(el)
        created_ids.append(el.id)
        _count("equipment" if category == "equipment" else category)

    # --- flow segments: horizontal pipe runs + vertical risers ---------------
    # Accept the abstract IfcFlowSegment and the concrete IFC4 subtypes
    # (IfcPipeSegment/IfcDuctSegment/IfcCableCarrierSegment) — all share the
    # first 7 attributes (…, Placement, Representation) the parser reads.
    _flow_seg_types = {
        "IFCFLOWSEGMENT",
        "IFCPIPESEGMENT",
        "IFCDUCTSEGMENT",
        "IFCCABLECARRIERSEGMENT",
    }
    for i, (typ, _body) in ent.items():
        if typ not in _flow_seg_types:
            continue
        a = spf.args(i)
        if len(a) < 7:
            continue
        pr = spf.profile(_ref(a[6]))
        if pr is None:
            warnings.append(f"flowsegment #{i}: no rectangle profile; skipped")
            continue
        px, py, pz, ang = spf.placement(_ref(a[5]))
        xdim, ydim, depth, cx, _cy = (v * scale for v in pr)
        x0, y0 = px * scale, py * scale
        lvl = level_of(i)
        z_local = pz * scale - level_elev.get(lvl, 0.0)
        tag_info = _parse_mep_tag(_unstr(a[3]))
        category = str(tag_info.get("ftype") or "pipe")
        if category not in _SEGMENT_CATEGORY:
            category = "pipe"
        # Risers use a default-centered square profile extruded in Z (cx == 0);
        # horizontal runs center the profile at cx == length/2 along the axis.
        vertical = bool(tag_info.get("vertical")) or (
            abs(cx) <= 1e-6 and abs(xdim - ydim) <= 1e-6
        )
        params = {
            "shape": "cylinder",
            "fitting_type": "pipe",
            "source": "ifc",
        }
        if vertical:
            params.update(
                {
                    "origin_mm": [x0, y0],
                    "start_mm": [x0, y0],
                    "end_mm": [x0, y0],
                    "vertical": True,
                    "z0_mm": z_local,
                    "z1_mm": z_local + depth,
                    "length_mm": depth,
                    "length_m": depth / 1000.0,
                    "size_mm": [xdim, ydim, depth],
                }
            )
        else:
            ex, ey = x0 + math.cos(ang) * xdim, y0 + math.sin(ang) * xdim
            params.update(
                {
                    "origin_mm": [x0, y0],
                    "start_mm": [x0, y0],
                    "end_mm": [ex, ey],
                    "z0_mm": z_local,
                    "length_mm": xdim,
                    "length_m": xdim / 1000.0,
                    "size_mm": [xdim, ydim, depth],
                }
            )
        for key in ("nps", "system", "fire_rating"):
            if key in tag_info:
                params[key] = tag_info[key]
        el = Element(
            id=new_id("pip"),
            category=category,
            name=_unstr(a[2]),
            level_id=lvl,
            params=params,
        )
        model.add_element(el)
        created_ids.append(el.id)
        _count("pipes")

    # --- rooms from spaces (min corner exact; extent is a placeholder) -------
    room_warned = False
    for i, (typ, _body) in ent.items():
        if typ != "IFCSPACE":
            continue
        a = spf.args(i)
        if len(a) < 6:
            continue
        px, py, _pz, _ang = spf.placement(_ref(a[5]))
        x0, y0 = px * scale, py * scale
        name = _unstr(a[2])
        desc = _unstr(a[3])
        room_h: float | None = None
        if desc.startswith("RM:"):
            body_txt = desc[3:]
            if "|H" in body_txt:
                nm, _sep, h_txt = body_txt.partition("|H")
                name = name or nm
                room_h = _num(h_txt)
            else:
                name = name or body_txt
        dx = dy = 1000.0
        params = {
            "boundary_mm": [[x0, y0], [x0 + dx, y0], [x0 + dx, y0 + dy], [x0, y0 + dy]],
            "area_mm2": dx * dy,
            "source": "ifc",
            "ifc_extent_approx": True,
        }
        if room_h is not None:
            params["height_mm"] = room_h
            params["ceiling_height_mm"] = room_h
        if not room_warned:
            warnings.append(
                "IfcSpace carries no boundary geometry; room min-corner is exact "
                "but extents are 1000x1000mm placeholders (ifc_extent_approx)"
            )
            room_warned = True
        el = Element(
            id=new_id("rom"),
            category="room",
            name=name,
            level_id=level_of(i),
            params=params,
        )
        model.add_element(el)
        created_ids.append(el.id)
        _count("rooms")

    # --- unknown entity census ----------------------------------------------
    skipped: dict[str, int] = {}
    for _i, (typ, _body) in ent.items():
        if typ not in _HANDLED and typ not in _SUPPORT:
            skipped[typ] = skipped.get(typ, 0) + 1

    return {
        "ok": True,
        "levels": levels_created,
        "created": counts,
        "element_ids": created_ids,
        "skipped": skipped,
        "warnings": warnings,
        "unit_scale": scale,
    }
