"""Machining / fab drawings with GD&T callouts (SVG, agent-derived)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from llmbim_core.model import ProjectModel

# ASME Y14.5-ish symbol map for SVG text (unicode)
_SYM = {
    "position": "⌖",
    "flatness": "⏥",
    "perpendicularity": "⊥",
    "parallelism": "∥",
    "circularity": "○",
    "cylindricity": "⌭",
    "profile": "⌒",
    "profile_surface": "⌓",
    "runout": "↗",
    "total_runout": "⌰",
    "straightness": "—",
    "angularity": "∠",
    "concentricity": "◎",
    "symmetry": "⌯",
}


def _fcf_text(g: dict[str, Any]) -> str:
    sym = _SYM.get(str(g.get("symbol") or ""), str(g.get("symbol") or "?"))
    dia = "⌀" if g.get("diameter") else ""
    tol = g.get("tolerance")
    dats = "".join(f"|{d}" for d in (g.get("datums") or []))
    return f"|{sym}|{dia}{tol}{dats}|"


def write_gdt_drawing(
    model: ProjectModel,
    element_id: str,
    path: str | Path,
    *,
    width: int = 900,
    height: int = 700,
) -> Path:
    """Emit a single-sheet SVG: title, feature history, GD&T FCFs, size dims."""
    el = model.get_element(element_id)
    if el.category != "fab_part":
        raise ValueError(f"expected fab_part, got {el.category}")
    feats: list[dict[str, Any]] = list(el.params.get("features") or [])
    gdt: list[dict[str, Any]] = list(el.params.get("gdt") or [])
    mat = el.params.get("material_id") or ""
    vol = el.params.get("volume_mm3")

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0b0f14"/>',
        f'<text x="24" y="36" fill="#e6edf3" font-family="Segoe UI,system-ui,sans-serif" '
        f'font-size="20" font-weight="600">{escape(el.name or el.id)} — Fab BREP + GD&amp;T</text>',
        f'<text x="24" y="58" fill="#8b97a8" font-family="Segoe UI,system-ui,sans-serif" '
        f'font-size="12">material={escape(str(mat))} · fidelity=brep_cadquery · '
        f'features={len(feats)} · gdt={len(gdt)}'
        + (f" · V={vol:.1f} mm³" if isinstance(vol, (int, float)) else "")
        + "</text>",
        # border title block
        f'<rect x="20" y="80" width="{width - 40}" height="{height - 100}" fill="none" '
        f'stroke="#30363d" stroke-width="1.5"/>',
        '<text x="36" y="110" fill="#5eb1ff" font-family="Segoe UI,system-ui,sans-serif" '
        'font-size="13" font-weight="600">FEATURE TREE (parametric BREP)</text>',
    ]
    y = 132
    for i, f in enumerate(feats):
        op = f.get("op", "?")
        detail = {k: v for k, v in f.items() if k != "op"}
        txt = f"{i:02d}  {op}  {detail}"
        if len(txt) > 110:
            txt = txt[:107] + "…"
        lines.append(
            f'<text x="36" y="{y}" fill="#c9d1d9" font-family="Consolas,monospace" '
            f'font-size="11">{escape(txt)}</text>'
        )
        y += 16
        if y > height - 220:
            lines.append(
                f'<text x="36" y="{y}" fill="#8b97a8" font-family="Segoe UI,system-ui,sans-serif" '
                f'font-size="11">… {len(feats) - i - 1} more features</text>'
            )
            y += 20
            break

    y = max(y + 20, 200)
    lines.append(
        f'<text x="36" y="{y}" fill="#5eb1ff" font-family="Segoe UI,system-ui,sans-serif" '
        f'font-size="13" font-weight="600">GD&amp;T / TOLERANCES (ASME Y14.5 style callouts)</text>'
    )
    y += 24
    if not gdt:
        lines.append(
            f'<text x="36" y="{y}" fill="#8b97a8" font-family="Segoe UI,system-ui,sans-serif" '
            f'font-size="12">No GD&amp;T yet — use gdt_datum / gdt_fcf / gdt_size</text>'
        )
    for g in gdt:
        kind = g.get("kind")
        if kind == "datum":
            box = (
                f'<rect x="36" y="{y - 14}" width="28" height="28" fill="#1a222d" '
                f'stroke="#e3b341" stroke-width="1.5"/>'
                f'<text x="50" y="{y + 6}" text-anchor="middle" fill="#e3b341" '
                f'font-family="Segoe UI,system-ui,sans-serif" font-size="16" font-weight="700">'
                f'{escape(str(g.get("label") or "?"))}</text>'
                f'<text x="76" y="{y + 6}" fill="#c9d1d9" font-family="Segoe UI,system-ui,sans-serif" '
                f'font-size="12">datum · face={escape(str(g.get("face") or ""))} '
                f'{escape(str(g.get("note") or ""))}</text>'
            )
            lines.append(box)
            y += 36
        elif kind == "fcf":
            fcf = _fcf_text(g)
            lines.append(
                f'<rect x="36" y="{y - 14}" width="{min(420, 24 + 10 * len(fcf))}" height="28" '
                f'fill="#143d2a" stroke="#3dd68c" stroke-width="1.2"/>'
                f'<text x="48" y="{y + 6}" fill="#3dd68c" font-family="Consolas,monospace" '
                f'font-size="13">{escape(fcf)}</text>'
                f'<text x="480" y="{y + 6}" fill="#8b97a8" font-family="Segoe UI,system-ui,sans-serif" '
                f'font-size="11">{escape(str(g.get("applies_to") or g.get("note") or ""))}</text>'
            )
            y += 36
        elif kind == "size":
            tp = g.get("tol_plus")
            tm = g.get("tol_minus")
            dim = (
                f'{g.get("dimension")}  {g.get("nominal")} '
                f'+{tp}/−{tm} {g.get("unit") or "mm"}'
            )
            lines.append(
                f'<text x="36" y="{y + 4}" fill="#e8eef6" font-family="Consolas,monospace" '
                f'font-size="13">{escape(dim)}  {escape(str(g.get("note") or ""))}</text>'
            )
            y += 28
        else:
            lines.append(
                f'<text x="36" y="{y}" fill="#c9d1d9" font-family="Consolas,monospace" '
                f'font-size="11">{escape(str(g))}</text>'
            )
            y += 20

    # honesty footer
    lines.append(
        f'<text x="24" y="{height - 16}" fill="#6e7681" font-family="Segoe UI,system-ui,sans-serif" '
        f'font-size="10">LLM-BIM fab drawing — BREP via CadQuery/OCP · GD&amp;T is model data '
        f"(not PE-stamped inspection plan) · export STEP for CAM</text>"
    )
    lines.append("</svg>")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
