"""AABB clash detection for coordination (builders + designers)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from llmbim_core.model import Element, ProjectModel


@dataclass
class AABB:
    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float

    def intersects(self, other: AABB, tol: float = 1.0) -> bool:
        return not (
            self.xmax < other.xmin - tol
            or self.xmin > other.xmax + tol
            or self.ymax < other.ymin - tol
            or self.ymin > other.ymax + tol
            or self.zmax < other.zmin - tol
            or self.zmin > other.zmax + tol
        )

    def volume(self) -> float:
        return max(0.0, self.xmax - self.xmin) * max(0.0, self.ymax - self.ymin) * max(
            0.0, self.zmax - self.zmin
        )


def _level_z(model: ProjectModel, level_id: str | None) -> float:
    if not level_id:
        return 0.0
    for lv in model.levels:
        if lv.id == level_id:
            return float(lv.elevation_mm)
    return 0.0


def element_aabb(el: Element, model: ProjectModel) -> AABB | None:
    z0 = _level_z(model, el.level_id)
    if el.category == "wall":
        try:
            s = el.params["start_mm"]
            e = el.params["end_mm"]
            th = float(el.params.get("thickness_mm", 200))
            ht = float(el.params.get("height_mm", 3000))
        except (KeyError, TypeError, ValueError):
            return None
        xs = [float(s[0]), float(e[0])]
        ys = [float(s[1]), float(e[1])]
        # expand by half thickness roughly
        pad = th / 2
        return AABB(min(xs) - pad, min(ys) - pad, z0, max(xs) + pad, max(ys) + pad, z0 + ht)
    if el.category == "equipment" or el.category == "column" or el.params.get("fitting_type") == "column":
        try:
            o = el.params["origin_mm"]
            s = el.params["size_mm"]
            z_off = float(el.params.get("z0_mm", 0))
            shape = el.params.get("shape", "box")
        except (KeyError, TypeError, ValueError):
            return None
        x0, y0 = float(o[0]), float(o[1])
        lx, ly, hz = float(s[0]), float(s[1]), float(s[2])
        if el.category == "column" or el.params.get("fitting_type") == "column":
            # origin is column center
            half_x, half_y = lx / 2, ly / 2
            ht = float(el.params.get("height_mm") or hz or 3000)
            return AABB(
                x0 - half_x,
                y0 - half_y,
                z0 + z_off,
                x0 + half_x,
                y0 + half_y,
                z0 + z_off + ht,
            )
        if shape == "cylinder":
            r = ly / 2
            return AABB(x0, y0 - r, z0 + z_off, x0 + lx, y0 + r, z0 + z_off + ly)
        return AABB(x0, y0, z0 + z_off, x0 + lx, y0 + ly, z0 + z_off + hz)
    if el.category == "slab":
        try:
            poly = el.params["polygon_mm"]
            th = float(el.params.get("thickness_mm", 200))
        except (KeyError, TypeError, ValueError):
            return None
        xs = [float(p[0]) for p in poly]
        ys = [float(p[1]) for p in poly]
        return AABB(min(xs), min(ys), z0 - th, max(xs), max(ys), z0)
    if (
        el.category
        in {"pipe", "plumbing_pipe", "conduit", "duct", "hvac", "cable_tray", "beam"}
        or el.params.get("fitting_type")
        in {"pipe", "conduit", "duct", "cable_tray", "beam"}
    ):
        try:
            is_duct = el.category in {"duct", "hvac"} or el.params.get("fitting_type") == "duct"
            is_tray = el.category == "cable_tray" or el.params.get("fitting_type") == "cable_tray"
            is_beam = el.category == "beam" or el.params.get("fitting_type") == "beam"
            od = 50.0
            if el.params.get("size_mm") and len(el.params["size_mm"]) >= 2:
                od = max(float(el.params["size_mm"][1]), 20.0)
            if is_duct or is_tray:
                od = float(el.params.get("width_mm") or od)
            if is_beam:
                od = float(el.params.get("width_mm") or el.params.get("depth_mm") or od or 150)
            z_off = float(el.params.get("z0_mm", 0))
            elev_h = od
            if is_duct or is_tray:
                elev_h = float(el.params.get("height_mm") or (100 if is_tray else 250))
            if is_beam:
                elev_h = float(el.params.get("height_mm") or el.params.get("depth_mm") or 300)
            # vertical riser
            if el.params.get("vertical") or el.params.get("orientation") == "vertical":
                o = el.params.get("origin_mm") or el.params.get("start_mm") or [0, 0]
                x, y = float(o[0]), float(o[1])
                z_lo = z0 + float(el.params.get("z0_mm") or 0)
                z_hi = z0 + float(el.params.get("z1_mm") or (z_lo + 1000))
                r = od / 2
                return AABB(x - r, y - r, min(z_lo, z_hi), x + r, y + r, max(z_lo, z_hi))
            if "start_mm" in el.params and "end_mm" in el.params:
                s, e = el.params["start_mm"], el.params["end_mm"]
                xs = [float(s[0]), float(e[0])]
                ys = [float(s[1]), float(e[1])]
                pad = od / 2
                return AABB(
                    min(xs) - pad,
                    min(ys) - pad,
                    z0 + z_off,
                    max(xs) + pad,
                    max(ys) + pad,
                    z0 + z_off + elev_h,
                )
            if "origin_mm" in el.params and "size_mm" in el.params:
                o, s = el.params["origin_mm"], el.params["size_mm"]
                x0, y0 = float(o[0]), float(o[1])
                lx, ly = float(s[0]), float(s[1])
                return AABB(x0, y0 - ly / 2, z0 + z_off, x0 + lx, y0 + ly / 2, z0 + z_off + ly)
        except (KeyError, TypeError, ValueError, IndexError):
            return None
    if el.category in {
        "fitting",
        "fittings",
        "fixture",
        "accessory",
        "module_instance",
        "module_root",
        "equipment",
    } or el.params.get("origin_mm"):
        try:
            o = el.params.get("origin_mm")
            if not o:
                return None
            s = el.params.get("size_mm") or [100.0, 100.0, 100.0]
            z_off = float(el.params.get("z0_mm", 0))
            x0, y0 = float(o[0]), float(o[1])
            lx = float(s[0]) if len(s) > 0 else 100.0
            ly = float(s[1]) if len(s) > 1 else 100.0
            hz = float(s[2]) if len(s) > 2 else ly
            # fittings often centered on origin
            return AABB(
                x0 - lx / 2,
                y0 - ly / 2,
                z0 + z_off,
                x0 + lx / 2,
                y0 + ly / 2,
                z0 + z_off + max(hz, 50.0),
            )
        except (KeyError, TypeError, ValueError, IndexError):
            return None
    return None


def find_clashes(
    model: ProjectModel,
    *,
    categories: tuple[str, ...] = (
        "wall",
        "equipment",
        "slab",
        "pipe",
        "plumbing_pipe",
        "fitting",
        "fixture",
        "module_instance",
        "module_root",
        "duct",
        "hvac",
        "conduit",
        "cable_tray",
        "column",
        "beam",
    ),
    ignore_same_host: bool = True,
) -> list[dict[str, Any]]:
    """Pairwise AABB clashes among selected categories (includes MEP + structure)."""
    items: list[tuple[Element, AABB]] = []
    for el in model.elements:
        if el.category not in categories:
            continue
        box = element_aabb(el, model)
        if box and box.volume() > 0:
            items.append((el, box))

    mep = {
        "pipe",
        "plumbing_pipe",
        "fitting",
        "fittings",
        "fixture",
        "duct",
        "hvac",
        "conduit",
        "cable_tray",
        "column",
        "beam",
    }
    clashes: list[dict[str, Any]] = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, ba = items[i]
            b, bb = items[j]
            if a.category == "slab" and b.category == "wall":
                continue  # walls sit on slabs — skip slab/wall
            if b.category == "slab" and a.category == "wall":
                continue
            if a.category == "slab" and b.category == "slab":
                continue
            # skip fittings sitting on their own pipes (same import module parent)
            if a.parent_id and a.parent_id == b.parent_id and a.parent_id:
                if a.category in mep and b.category in mep:
                    continue
            if ignore_same_host and a.host_id and a.host_id == b.id:
                continue
            if ignore_same_host and b.host_id and b.host_id == a.id:
                continue
            if ba.intersects(bb):
                cats = {a.category, b.category}
                sev = "warning"
                if cats & mep and cats & {"wall", "equipment"}:
                    sev = "error"
                elif cats <= mep:
                    sev = "warning"  # pipe-pipe / pipe-fitting
                elif cats == {"wall", "equipment"}:
                    sev = "warning"
                else:
                    sev = "error"
                clashes.append(
                    {
                        "a_id": a.id,
                        "a_name": a.name,
                        "a_category": a.category,
                        "b_id": b.id,
                        "b_name": b.name,
                        "b_category": b.category,
                        "severity": sev,
                        "message": f"AABB overlap: {a.name or a.id} × {b.name or b.id}",
                    }
                )
    return clashes
