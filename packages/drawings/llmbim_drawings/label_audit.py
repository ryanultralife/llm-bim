"""Measured SVG label audit — T7 ratchet, T8 contents.

Overlap is AABB intersection ≥ 35 % of the smaller box. Width from
matplotlib TextPath when available, else 0.55 em. Rotated text uses the
axis-aligned bounds of the rotated rectangle. Never skip a label here:
this is the guard, not the placer.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

EM = 0.55
MIN_OVERLAP = 0.35
TEXT_RE = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)
ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')
TAG_RE = re.compile(r"<[^>]+>")
ROT_RE = re.compile(
    r"rotate\(\s*([-\d.]+)(?:\s*[,\s]\s*([-\d.]+)\s*[,\s]\s*([-\d.]+))?\s*\)"
)


def _num(v: str, d: float = 0.0) -> float:
    try:
        return float(re.sub(r"[^0-9.eE+-]", "", v) or d)
    except ValueError:
        return d


def _advance(s: str, fs: float) -> float:
    try:
        from matplotlib.font_manager import FontProperties
        from matplotlib.textpath import TextPath

        tp = TextPath((0, 0), s, size=fs, prop=FontProperties(family="sans-serif"))
        ext = tp.get_extents()
        return float(ext.width) or (len(s) * fs * EM)
    except Exception:
        return len(s) * fs * EM


def _rotate_aabb(
    x0: float, y0: float, x1: float, y1: float, ang: float, cx: float, cy: float
) -> tuple[float, float, float, float]:
    rad = math.radians(ang)
    c, s = math.cos(rad), math.sin(rad)
    xs, ys = [], []
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        dx, dy = x - cx, y - cy
        xs.append(cx + dx * c - dy * s)
        ys.append(cy + dx * s + dy * c)
    return min(xs), min(ys), max(xs), max(ys)


def boxes(svg_text: str) -> list[tuple[float, float, float, float, str, float]]:
    out: list[tuple[float, float, float, float, str, float]] = []
    for attrs, body in TEXT_RE.findall(svg_text):
        a = dict(ATTR_RE.findall(attrs))
        s = TAG_RE.sub("", body)
        s = re.sub(r"\s+", " ", s).strip()
        if not s:
            continue
        fs = _num(a.get("font-size", "8"), 8.0) or 8.0
        x, y = _num(a.get("x", "0")), _num(a.get("y", "0"))
        w = _advance(s, fs)
        anchor = a.get("text-anchor", "start")
        if anchor == "middle":
            x -= w / 2
        elif anchor == "end":
            x -= w
        x0, y0, x1, y1 = x, y - fs * 0.8, x + w, y + fs * 0.2
        tr = a.get("transform") or ""
        m = ROT_RE.search(tr)
        if m:
            ang = float(m.group(1))
            cx = float(m.group(2)) if m.group(2) else x + w / 2
            cy = float(m.group(3)) if m.group(3) else y
            x0, y0, x1, y1 = _rotate_aabb(x0, y0, x1, y1, ang, cx, cy)
        out.append((x0, y0, x1, y1, s, fs))
    return out


def overlap_pairs(
    bs: list[tuple[float, float, float, float, str, float]],
) -> list[tuple[float, str, str]]:
    hits: list[tuple[float, str, str]] = []
    n = len(bs)
    for i in range(n):
        ax0, ay0, ax1, ay1, at, _afs = bs[i]
        for j in range(i + 1, n):
            bx0, by0, bx1, by1, bt, _bfs = bs[j]
            ox = min(ax1, bx1) - max(ax0, bx0)
            oy = min(ay1, by1) - max(ay0, by0)
            if ox <= 0 or oy <= 0:
                continue
            inter = ox * oy
            small = min((ax1 - ax0) * (ay1 - ay0), (bx1 - bx0) * (by1 - by0))
            if small > 0 and inter / small >= MIN_OVERLAP:
                hits.append((round(inter / small, 2), at[:80], bt[:80]))
    return hits


def audit_construction_svgs(
    out: Path, sheets: list[dict[str, Any]]
) -> dict[str, Any]:
    """T7 audit + T8 contents. Does not drop labels; reports them."""
    per: list[dict[str, Any]] = []
    total_pairs = 0
    total_labels = 0
    by_file = {str(s.get("file") or ""): s for s in sheets}
    # T7a: every SVG on disk, not only the emitter's register (A-1xx_plan family).
    disk = sorted(p.name for p in out.glob("*.svg"))
    for fname in disk:
        spec = by_file.get(fname) or {
            "no": Path(fname).stem, "file": fname, "title": "",
        }
        path = out / fname
        text = path.read_text(encoding="utf-8", errors="replace")
        bs = boxes(text)
        hits = overlap_pairs(bs)
        labels = [b[4] for b in bs]
        total_pairs += len(hits)
        total_labels += len(labels)
        per.append(
            {
                "no": spec.get("no"),
                "file": fname,
                "title": spec.get("title"),
                "n_labels": len(labels),
                "overlap_pairs": len(hits),
                "labels": labels,
                "element_ids": list(spec.get("element_ids") or []),
                "samples": hits[:5],
            }
        )
    return {
        "n_sheets": len(per),
        "n_labels": total_labels,
        "overlap_pairs": total_pairs,
        "ok": total_pairs == 0,
        "sheets": per,
    }
