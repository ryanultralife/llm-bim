"""Product layout + mesh-match renders from the pack model.

Rule (EQUIPMENT_3D / MineClean): never hybrid STEP+bay in one PNG.

1. **Mesh product stills** (primary) — closed roof + ghost walls from
   ``model.gltf`` via :func:`llmbim_geometry.render_hero.export_mesh_product_views`
   (presentation path restored 2026-08-05 after regression).

2. **Layout schematic** — equipment + process CLs from ``model.llmbim.json``.

Usage:
  from llmbim_drawings.product_views import export_product_views
  export_product_views(pack_dir, out_subdir="renders")
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def _equip_items(model: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten equipment elements to labeled AABBs (mm). Skip micro / pure tubes."""
    items: list[dict[str, Any]] = []
    for el in model.get("elements") or []:
        if el.get("category") != "equipment":
            continue
        p = el.get("params") or {}
        # place_tube ports drawn as process segments, not boxes
        if p.get("geom") == "place_tube" or p.get("fitting_type") == "tube":
            continue
        size = p.get("size_mm") or [0, 0, 0]
        origin = p.get("origin_mm") or [0, 0]
        if len(size) < 3:
            continue
        w, d, h = float(size[0]), float(size[1]), float(size[2])
        if w < 1 or d < 1 or h < 1:
            continue
        ox, oy = float(origin[0]), float(origin[1])
        z0 = float(p.get("z0_mm") or 0.0)
        # create_equipment_box centered=True stores origin as center for MineClean
        # Heuristic: if shape cylinder and size[0] is length along X, origin is often center.
        centered = bool(p.get("centered", True))
        if centered:
            cx, cy = ox, oy
        else:
            cx, cy = ox + w / 2, oy + d / 2
        tag = (
            p.get("equipment_tag")
            or p.get("equipment")
            or p.get("mark")
            or el.get("name")
            or "EQ"
        )
        tag = str(tag).split()[0][:16]
        name = str(p.get("equipment_name") or p.get("label") or el.get("name") or tag)
        items.append(
            {
                "tag": tag,
                "name": name[:40],
                "cx": cx,
                "cy": cy,
                "sx": w,
                "sy": d,
                "sz": h,
                "z0": z0,
                "kind": str(p.get("kind") or "equipment"),
            }
        )
    return items


def _nps_od_mm(nps: str | None) -> float:
    """Approx OD (mm) from NPS string for schematic stroke weight."""
    if not nps:
        return 40.0
    s = str(nps).strip().lower().replace("″", "").replace('"', "")
    table = {
        "1/2": 21.3,
        "0.5": 21.3,
        "3/4": 26.7,
        "1": 33.4,
        "1-1/2": 48.3,
        "1.5": 48.3,
        "2": 60.3,
        "3": 88.9,
        "4": 114.3,
        "6": 168.3,
    }
    return float(table.get(s, 40.0))


def _process_segments(model: dict[str, Any]) -> list[dict[str, Any]]:
    """Pipes, risers, place_tube stubs, wire_paths as 3D polylines (mm)."""
    segs: list[dict[str, Any]] = []
    for el in model.get("elements") or []:
        cat = el.get("category")
        p = el.get("params") or {}
        system = str(p.get("system") or "PROC")
        name = str(el.get("name") or "")

        if cat == "pipe":
            a = p.get("start_mm") or p.get("origin_mm") or [0, 0]
            b = p.get("end_mm") or a
            z0 = float(p.get("z0_mm") or 0.0)
            # riser: same XY, height in size_mm[2] or z1
            ax, ay = float(a[0]), float(a[1])
            bx, by = float(b[0]), float(b[1])
            od = float(p.get("od_mm") or _nps_od_mm(p.get("nps")))
            if abs(ax - bx) < 1e-6 and abs(ay - by) < 1e-6:
                # vertical riser
                z1 = z0
                if p.get("z1_mm") is not None:
                    z1 = float(p["z1_mm"])
                else:
                    sz = p.get("size_mm") or [0, 0, 0]
                    # size often [od, od, height] or length along Z
                    z1 = z0 + abs(float(sz[2] if len(sz) > 2 else sz[0] or 200))
                pts = [[ax, ay, z0], [ax, ay, z1]]
            else:
                pts = [[ax, ay, z0], [bx, by, z0]]
            segs.append(
                {
                    "kind": "pipe",
                    "system": system,
                    "name": name,
                    "points": pts,
                    "od_mm": od,
                    "tag": str(p.get("mark") or name)[:12],
                }
            )
            continue

        if cat == "wire_path" or p.get("geom") == "place_wire_path":
            pts_raw = p.get("points_mm") or []
            pts = []
            for pt in pts_raw:
                if len(pt) >= 3:
                    pts.append([float(pt[0]), float(pt[1]), float(pt[2])])
            if len(pts) >= 2:
                segs.append(
                    {
                        "kind": "wire",
                        "system": system,
                        "name": name,
                        "points": pts,
                        "od_mm": float(p.get("diameter_mm") or 12.0),
                        "tag": str(p.get("phase") or p.get("wire_role") or name)[:10],
                        "phase": p.get("phase"),
                        "wire_role": p.get("wire_role"),
                    }
                )
            continue

        if p.get("geom") == "place_tube" or p.get("fitting_type") == "tube":
            ox = float((p.get("origin_mm") or [0, 0])[0])
            oy = float((p.get("origin_mm") or [0, 0])[1])
            z0 = float(p.get("z0_mm") or 0.0)
            L = float(p.get("length_mm") or (p.get("size_mm") or [100])[0] or 100)
            dvec = p.get("axis_dir") or p.get("direction")
            if isinstance(dvec, str):
                axis_map = {
                    "x": (1, 0, 0),
                    "-x": (-1, 0, 0),
                    "y": (0, 1, 0),
                    "-y": (0, -1, 0),
                    "z": (0, 0, 1),
                    "-z": (0, 0, -1),
                }
                dx, dy, dz = axis_map.get(dvec.lower(), (1, 0, 0))
            elif isinstance(dvec, (list, tuple)) and len(dvec) >= 3:
                dx, dy, dz = float(dvec[0]), float(dvec[1]), float(dvec[2])
                n = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
                dx, dy, dz = dx / n, dy / n, dz / n
            else:
                # size_mm is [L, od, od] along +X when no axis
                dx, dy, dz = 1.0, 0.0, 0.0
            segs.append(
                {
                    "kind": "tube",
                    "system": system,
                    "name": name,
                    "points": [[ox, oy, z0], [ox + dx * L, oy + dy * L, z0 + dz * L]],
                    "od_mm": float(p.get("od_mm") or p.get("diameter_mm") or 50),
                    "tag": "TUBE",
                }
            )
            continue

        if cat == "fitting":
            o = p.get("origin_mm") or [0, 0]
            z0 = float(p.get("z0_mm") or 0.0)
            segs.append(
                {
                    "kind": "fitting",
                    "system": system,
                    "name": name,
                    "points": [[float(o[0]), float(o[1]), z0]],
                    "od_mm": float(_nps_od_mm(p.get("nps"))),
                    "tag": str(name)[:10],
                }
            )
    return segs


def _group_by_tag(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge parts of same equipment tag into readable envelopes."""
    if not items:
        return []
    ox0 = min(p["cx"] - p["sx"] / 2 for p in items)
    ox1 = max(p["cx"] + p["sx"] / 2 for p in items)
    oy0 = min(p["cy"] - p["sy"] / 2 for p in items)
    oy1 = max(p["cy"] + p["sy"] / 2 for p in items)
    span_x = max(ox1 - ox0, 1.0)
    span_y = max(oy1 - oy0, 1.0)

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items:
        buckets[it["tag"]].append(it)

    groups: list[dict[str, Any]] = []

    def _add(tag: str, name: str, parts: list[dict[str, Any]]) -> None:
        xs0 = [p["cx"] - p["sx"] / 2 for p in parts]
        xs1 = [p["cx"] + p["sx"] / 2 for p in parts]
        ys0 = [p["cy"] - p["sy"] / 2 for p in parts]
        ys1 = [p["cy"] + p["sy"] / 2 for p in parts]
        zs0 = [p["z0"] for p in parts]
        zs1 = [p["z0"] + p["sz"] for p in parts]
        x0, x1 = min(xs0), max(xs1)
        y0, y1 = min(ys0), max(ys1)
        z0, z1 = min(zs0), max(zs1)
        sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
        if sx * sy < 0.05e6:
            return
        if sx > 0.85 * span_x and sy > 0.55 * span_y:
            mid = [
                p
                for p in parts
                if p["sx"] < 0.5 * span_x
                and p["sy"] < 0.7 * span_y
                and p["sx"] * p["sy"] > 0.08e6
            ]
            for p in mid[:12]:
                groups.append(
                    {
                        "tag": tag,
                        "name": p["name"],
                        "cx": p["cx"],
                        "cy": p["cy"],
                        "sx": p["sx"],
                        "sy": p["sy"],
                        "sz": p["sz"],
                        "z0": p["z0"],
                        "n_parts": 1,
                    }
                )
            return
        groups.append(
            {
                "tag": tag,
                "name": name,
                "cx": 0.5 * (x0 + x1),
                "cy": 0.5 * (y0 + y1),
                "sx": sx,
                "sy": sy,
                "sz": sz,
                "z0": z0,
                "n_parts": len(parts),
            }
        )

    for tag, parts in buckets.items():
        _add(tag, parts[0]["name"], parts)

    groups.sort(key=lambda g: g["sx"] * g["sy"] * g["sz"], reverse=True)
    return groups


_COLORS = [
    "#3d8fb5",
    "#d4893a",
    "#5f8f6a",
    "#5b6fad",
    "#4a9e6a",
    "#2f8a9c",
    "#b03a3a",
    "#8b7355",
    "#6b7db5",
    "#9a6bb5",
]

_SYS_COLOR = {
    "PROC": "#c45c26",
    "CW": "#2a7fd4",
    "RMF": "#c02828",
    "RMF_A": "#c02828",
    "RMF_B": "#2d9a45",
    "RMF_C": "#3458c8",
    "SIG": "#c9b22a",
    "PWR": "#b8860b",
    "SAMPLE": "#8b5cf6",
    "GAS": "#0d9488",
}


def _color(i: int) -> str:
    return _COLORS[i % len(_COLORS)]


def _seg_color(seg: dict[str, Any]) -> str:
    sys = str(seg.get("system") or "PROC")
    if sys in _SYS_COLOR:
        return _SYS_COLOR[sys]
    if seg.get("kind") == "wire":
        ph = str(seg.get("phase") or "").upper()
        if ph == "A":
            return _SYS_COLOR["RMF_A"]
        if ph == "B":
            return _SYS_COLOR["RMF_B"]
        if ph == "C":
            return _SYS_COLOR["RMF_C"]
        role = str(seg.get("wire_role") or "")
        if role in ("hose", "lead", "signal"):
            return _SYS_COLOR["SIG"]
    return _SYS_COLOR.get("PROC", "#c45c26")


def _iso(x: float, y: float, z: float) -> tuple[float, float]:
    c30 = math.cos(math.radians(30))
    s30 = math.sin(math.radians(30))
    return (x - y) * c30, z + (x + y) * s30


def _iso_box(ax, cx, cy, sx, sy, z0, sz, cols, edge="#222", lw=0.6, zorder=3):
    import matplotlib.pyplot as plt

    x0, x1 = cx - sx / 2, cx + sx / 2
    y0, y1 = cy - sy / 2, cy + sy / 2
    z1 = z0 + sz
    bot = [_iso(x0, y0, z0), _iso(x1, y0, z0), _iso(x1, y1, z0), _iso(x0, y1, z0)]
    top = [_iso(x0, y0, z1), _iso(x1, y0, z1), _iso(x1, y1, z1), _iso(x0, y1, z1)]
    faces = [
        ([top[0], top[1], top[2], top[3]], cols[0]),
        ([bot[0], bot[1], top[1], top[0]], cols[1]),
        ([bot[1], bot[2], top[2], top[1]], cols[2]),
    ]
    for pts, col in faces:
        ax.add_patch(
            plt.Polygon(
                pts,
                closed=True,
                facecolor=col,
                edgecolor=edge,
                lw=lw,
                alpha=0.88,
                zorder=zorder,
            )
        )
    return _iso(cx, cy, z1 + 40)


def _shade(hex_c: str, f: float) -> str:
    h = hex_c.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def ch(c: int) -> int:
        return max(0, min(255, int(c * f)))

    return f"#{ch(r):02x}{ch(g):02x}{ch(b):02x}"


def _draw_seg_iso(ax, seg: dict[str, Any], zorder: int = 15) -> None:
    pts = seg["points"]
    if len(pts) < 2:
        if pts:
            u, v = _iso(pts[0][0], pts[0][1], pts[0][2])
            ax.plot(u, v, "o", color=_seg_color(seg), markersize=4, zorder=zorder)
        return
    xs, ys = [], []
    for x, y, z in pts:
        u, v = _iso(x, y, z)
        xs.append(u)
        ys.append(v)
    lw = max(1.2, min(6.0, float(seg.get("od_mm") or 40) / 18.0))
    ax.plot(
        xs,
        ys,
        color=_seg_color(seg),
        lw=lw,
        solid_capstyle="round",
        solid_joinstyle="round",
        alpha=0.95,
        zorder=zorder,
    )


def _draw_seg_plan(ax, seg: dict[str, Any], zorder: int = 12) -> None:
    pts = seg["points"]
    if len(pts) < 2:
        if pts:
            ax.plot(pts[0][0], pts[0][1], "o", color=_seg_color(seg), markersize=5, zorder=zorder)
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    lw = max(1.0, min(5.5, float(seg.get("od_mm") or 40) / 20.0))
    ax.plot(
        xs,
        ys,
        color=_seg_color(seg),
        lw=lw,
        solid_capstyle="round",
        solid_joinstyle="round",
        alpha=0.95,
        zorder=zorder,
    )


def _draw_seg_elev(ax, seg: dict[str, Any], axis: str = "x", zorder: int = 12) -> None:
    """Elevation: horizontal = plan X (or Y), vertical = Z."""
    pts = seg["points"]
    if len(pts) < 2:
        if pts:
            h = pts[0][0] if axis == "x" else pts[0][1]
            ax.plot(h, pts[0][2], "o", color=_seg_color(seg), markersize=4, zorder=zorder)
        return
    hs = [p[0] if axis == "x" else p[1] for p in pts]
    zs = [p[2] for p in pts]
    lw = max(1.0, min(5.5, float(seg.get("od_mm") or 40) / 20.0))
    ax.plot(
        hs,
        zs,
        color=_seg_color(seg),
        lw=lw,
        solid_capstyle="round",
        solid_joinstyle="round",
        alpha=0.95,
        zorder=zorder,
    )


def _export_layout_views(
    model: dict[str, Any],
    out: Path,
    *,
    title_prefix: str,
    max_labels: int,
) -> list[Path]:
    """Labeled equipment envelopes + process polylines (schematic)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Rectangle

    items = _equip_items(model)
    groups = _group_by_tag(items)
    segs = _process_segments(model)
    if not groups and not segs:
        return []

    paths: list[Path] = []

    # bounds from both equipment and process
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for g in groups:
        xs += [g["cx"] - g["sx"] / 2, g["cx"] + g["sx"] / 2]
        ys += [g["cy"] - g["sy"] / 2, g["cy"] + g["sy"] / 2]
        zs += [g["z0"], g["z0"] + g["sz"]]
    for s in segs:
        for pt in s["points"]:
            xs.append(pt[0])
            ys.append(pt[1])
            zs.append(pt[2])
    if not xs:
        return []
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    z1 = max(zs)
    pad = 0.06 * max(x1 - x0, y1 - y0, 1000)

    n_pipe = sum(1 for s in segs if s["kind"] == "pipe")
    n_wire = sum(1 for s in segs if s["kind"] == "wire")
    n_tube = sum(1 for s in segs if s["kind"] == "tube")
    foot = (
        f"layout + process · equip={len(groups)} pipe={n_pipe} tube={n_tube} "
        f"wire={n_wire} · no hybrid STEP · [ENGINEERING ESTIMATE]"
    )

    # ── L1 iso layout ─────────────────────────────────────────────────────
    fig = plt.figure(figsize=(14, 8), dpi=150)
    ax = fig.add_axes([0.02, 0.06, 0.96, 0.88])
    _iso_box(
        ax,
        0.5 * (x0 + x1),
        0.5 * (y0 + y1),
        (x1 - x0) * 1.05,
        (y1 - y0) * 1.05,
        0,
        max(80.0, min((g["z0"] for g in groups), default=80) or 80),
        ["#a8aeb4", "#8a9096", "#959ba1"],
        zorder=1,
    )
    for i, g in enumerate(groups[:40]):
        col = _color(i)
        u, v = _iso_box(
            ax,
            g["cx"],
            g["cy"],
            g["sx"],
            g["sy"],
            g["z0"],
            g["sz"],
            [_shade(col, 1.12), col, _shade(col, 0.78)],
            zorder=3 + (i % 5),
        )
        if i < max_labels:
            ax.text(
                u,
                v,
                g["tag"],
                ha="center",
                va="bottom",
                fontsize=7.5,
                fontweight="bold",
                color="#111",
                zorder=20,
            )
    for s in segs:
        _draw_seg_iso(ax, s, zorder=16)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.autoscale()
    ax.set_title(
        f"{title_prefix} — layout iso (equipment + piping)",
        fontsize=13,
        pad=6,
    )
    fig.text(0.02, 0.015, foot, fontsize=7.5, color="#555")
    p = out / "L1_layout_iso.png"
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    paths.append(p)

    # ── L2 plan ───────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(14, 7), dpi=150)
    ax = fig.add_axes([0.04, 0.08, 0.92, 0.84])
    ax.add_patch(
        Rectangle(
            (x0 - pad, y0 - pad),
            (x1 - x0) + 2 * pad,
            (y1 - y0) + 2 * pad,
            facecolor="#e8eaed",
            edgecolor="#222",
            lw=1.5,
            zorder=1,
        )
    )
    for i, g in enumerate(groups[:50]):
        col = _color(i)
        ax.add_patch(
            FancyBboxPatch(
                (g["cx"] - g["sx"] / 2, g["cy"] - g["sy"] / 2),
                g["sx"],
                g["sy"],
                boxstyle="round,pad=4,rounding_size=20",
                facecolor=col,
                edgecolor="#111",
                lw=0.8,
                alpha=0.85,
                zorder=3,
            )
        )
        if i < max_labels and g["sx"] * g["sy"] > 0.2e6:
            ax.text(
                g["cx"],
                g["cy"],
                g["tag"],
                ha="center",
                va="center",
                fontsize=8,
                fontweight="bold",
                color="#fff",
                zorder=5,
            )
    for s in segs:
        _draw_seg_plan(ax, s)
    # legend
    legend_y = y1 + pad * 0.55
    ax.plot([x0, x0 + 400], [legend_y, legend_y], color=_SYS_COLOR["PROC"], lw=3)
    ax.text(x0 + 420, legend_y, "PROC", va="center", fontsize=8, color="#333")
    ax.plot([x0 + 700, x0 + 1100], [legend_y, legend_y], color=_SYS_COLOR["CW"], lw=3)
    ax.text(x0 + 1120, legend_y, "CW", va="center", fontsize=8, color="#333")
    ax.plot([x0 + 1300, x0 + 1700], [legend_y, legend_y], color=_SYS_COLOR["SIG"], lw=3)
    ax.text(x0 + 1720, legend_y, "SIG/hose", va="center", fontsize=8, color="#333")

    ax.set_xlim(x0 - pad * 1.5, x1 + pad * 1.5)
    ax.set_ylim(y0 - pad * 1.5, y1 + pad * 1.8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        f"{title_prefix} — layout plan (equipment + piping)",
        fontsize=13,
        pad=6,
    )
    fig.text(0.02, 0.02, foot, fontsize=7.5, color="#555")
    p = out / "L2_layout_plan.png"
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    paths.append(p)

    # ── L3 elev X–Z ───────────────────────────────────────────────────────
    fig = plt.figure(figsize=(14, 6), dpi=150)
    ax = fig.add_axes([0.04, 0.10, 0.92, 0.82])
    ax.axhline(0, color="#666", lw=1.2, zorder=0)
    for i, g in enumerate(groups[:50]):
        col = _color(i)
        ax.add_patch(
            Rectangle(
                (g["cx"] - g["sx"] / 2, g["z0"]),
                g["sx"],
                g["sz"],
                facecolor=col,
                edgecolor="#111",
                lw=0.8,
                alpha=0.88,
                zorder=3,
            )
        )
        if i < max_labels and g["sx"] > 200:
            ax.text(
                g["cx"],
                g["z0"] + g["sz"] / 2,
                g["tag"],
                ha="center",
                va="center",
                fontsize=7.5,
                fontweight="bold",
                color="#fff",
                zorder=5,
            )
    for s in segs:
        _draw_seg_elev(ax, s, axis="x")
    ax.set_xlim(x0 - pad, x1 + pad)
    ax.set_ylim(-pad * 0.3, z1 + pad * 0.5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"{title_prefix} — layout elev X–Z (+ piping)", fontsize=13, pad=6)
    fig.text(0.02, 0.02, foot, fontsize=7.5, color="#555")
    p = out / "L3_layout_elev.png"
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    paths.append(p)

    (out / "PRODUCT_VIEWS.json").write_text(
        json.dumps(
            {
                "rule": "layout AABB + process polylines; mesh match is primary product still",
                "groups": len(groups),
                "parts": len(items),
                "process_segments": len(segs),
                "pipe": n_pipe,
                "tube": n_tube,
                "wire": n_wire,
                "layout_files": [p.name for p in paths],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return paths


def export_product_views(
    pack_dir: str | Path,
    *,
    out_subdir: str = "renders",
    title_prefix: str = "llm-bim product",
    max_labels: int = 24,
    mesh_match: bool = True,
    layout: bool = True,
) -> list[Path]:
    """Write engineering stills under pack_dir/out_subdir.

    Default: **ENG_*** plan/elev/iso from full model.gltf (same as 3D viewer +
    sheets), plus optional L1–L3 labeled layout. Pitch JPGs are never SSOT.
    """
    pack = Path(pack_dir)
    out = pack / out_subdir
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    if mesh_match and (pack / "model.gltf").is_file():
        try:
            from llmbim_geometry.render_hero import export_mesh_product_views

            paths.extend(
                export_mesh_product_views(
                    pack,
                    out_subdir=out_subdir,
                    title_prefix=str(title_prefix)[:48],
                )
            )
        except Exception as exc:  # noqa: BLE001
            (out / "MESH_VIEWS_ERROR.txt").write_text(str(exc), encoding="utf-8")

    if layout:
        mj = pack / "model.llmbim.json"
        if mj.is_file():
            model = json.loads(mj.read_text(encoding="utf-8"))
            paths.extend(
                _export_layout_views(
                    model,
                    out,
                    title_prefix=str(title_prefix)[:48],
                    max_labels=max_labels,
                )
            )

    # Keep legacy R1/R2/R3 names pointing at mesh match when present
    # (export_mesh_product_views already writes those names)

    return paths
