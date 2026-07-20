"""Part / equipment drawing packs (2D GA + STEP companion paths)."""

from __future__ import annotations

import json
from pathlib import Path

from llmbim_core.model import Element, ProjectModel
from llmbim_geometry.step_export import export_step_part

from llmbim_drawings.sheets import title_block_svg
from llmbim_drawings.svg_util import esc, fmt


def _part_views_svg(el: Element, *, scale: float = 0.5) -> str:
    """Orthographic plan + front + side for an equipment box/cylinder."""
    try:
        size = el.params["size_mm"]
        lx, ly, hz = float(size[0]), float(size[1]), float(size[2])
        shape = el.params.get("shape", "box")
    except (KeyError, TypeError, ValueError):
        lx = ly = hz = 100.0
        shape = "box"

    def box(x: float, y: float, w: float, h: float, label: str) -> list[str]:
        return [
            f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" '
            f'fill="#dceaf7" stroke="#0b5cab" stroke-width="1.5"/>',
            f'<text x="{fmt(x + w / 2)}" y="{fmt(y - 8)}" text-anchor="middle" '
            f'font-size="12" font-family="sans-serif">{esc(label)}</text>',
            f'<text x="{fmt(x + w / 2)}" y="{fmt(y + h / 2)}" text-anchor="middle" '
            f'font-size="10" font-family="sans-serif" fill="#333">'
            f"{fmt(w / scale)}×{fmt(h / scale)} mm</text>",
        ]

    def cyl_side(x: float, y: float, length: float, diam: float, label: str) -> list[str]:
        w, h = length * scale, diam * scale
        return [
            f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}" '
            f'rx="{fmt(h/2)}" fill="#dceaf7" stroke="#0b5cab" stroke-width="1.5"/>',
            f'<text x="{fmt(x + w / 2)}" y="{fmt(y - 8)}" text-anchor="middle" '
            f'font-size="12" font-family="sans-serif">{esc(label)}</text>',
            f'<text x="{fmt(x + w / 2)}" y="{fmt(y + h / 2)}" text-anchor="middle" '
            f'font-size="10" font-family="sans-serif" fill="#333">'
            f"Ø{fmt(diam)} × {fmt(length)} mm</text>",
        ]

    if shape == "cylinder":
        # plan: rectangle L×D; front: L×D; side: circle
        pw, ph = lx * scale, ly * scale
        parts = ['<g font-family="sans-serif">']
        parts += box(40, 60, pw, ph, "PLAN")
        parts += cyl_side(40 + pw + 40, 60, lx, ly, "FRONT")
        r = ly * scale / 2
        cx, cy = 40 + pw + 40 + lx * scale + 40 + r, 60 + r
        parts += [
            f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}" fill="#dceaf7" stroke="#0b5cab" stroke-width="1.5"/>',
            f'<text x="{fmt(cx)}" y="{fmt(60 - 8)}" text-anchor="middle" font-size="12">END</text>',
        ]
        max_h = max(ph, ly * scale, 2 * r)
    else:
        pw, ph = lx * scale, ly * scale
        fw, fh = lx * scale, hz * scale
        sw, sh = ly * scale, hz * scale
        parts = ['<g font-family="sans-serif">']
        parts += box(40, 60, pw, ph, "PLAN")
        parts += box(40 + pw + 40, 60, fw, fh, "FRONT")
        parts += box(40 + pw + 40 + fw + 40, 60, sw, sh, "SIDE")
        max_h = max(ph, fh, sh)

    parts.append(
        f'<text x="40" y="40" font-size="14" font-weight="bold">{esc(el.name or el.id)}</text>'
    )
    kind = el.params.get("kind", "equipment")
    parts.append(
        f'<text x="40" y="{fmt(60 + max_h + 40)}" font-size="11">'
        f"kind={esc(str(kind))} shape={esc(str(shape))} · envelope (not Fusion BREP)</text>"
    )
    parts.append("</g>")
    return "\n".join(parts)


def export_part_pack(
    model: ProjectModel,
    out_dir: str | Path,
    *,
    scale: float = 0.4,
) -> dict:
    """For each equipment element: 2D sheet SVG + STEP solid."""
    out = Path(out_dir)
    drawings = out / "drawings"
    step_dir = out / "step"
    drawings.mkdir(parents=True, exist_ok=True)
    step_dir.mkdir(parents=True, exist_ok=True)

    parts_index: list[dict] = []
    equipment = model.query(category="equipment")
    for i, el in enumerate(equipment, start=1):
        sn = f"P-{i:03d}"
        body = _part_views_svg(el, scale=scale)
        sheet = title_block_svg(
            project=model.name,
            sheet_title=f"Part — {el.name or el.id}",
            sheet_no=sn,
            scale_note=f"~{scale} SVG u/mm",
            notes="Envelope geometry for exchange · FAB detail in Fusion STEP if required",
            body=body,
        )
        svg_name = f"{sn}_{(el.name or el.id).replace(' ', '_')[:40]}.svg"
        (drawings / svg_name).write_text(sheet, encoding="utf-8")
        step_name = f"{sn}_{(el.name or el.id).replace(' ', '_')[:40]}.step"
        export_step_part(el, model, step_dir / step_name)
        parts_index.append(
            {
                "sheet": sn,
                "name": el.name,
                "id": el.id,
                "kind": el.params.get("kind"),
                "size_mm": el.params.get("size_mm"),
                "svg": f"drawings/{svg_name}",
                "step": f"step/{step_name}",
            }
        )

    # Assembly GA sheet — all equipment plan footprints
    from llmbim_drawings.plan import render_plan_svg

    level = model.levels[0].name if model.levels else "Bench"
    plan = render_plan_svg(model, level, scale=scale)
    ga = title_block_svg(
        project=model.name,
        sheet_title="Assembly General Arrangement",
        sheet_no="P-000",
        scale_note=f"scale {scale}",
        body=plan,
    )
    (drawings / "P-000_assembly_GA.svg").write_text(ga, encoding="utf-8")

    manifest = {
        "project": model.name,
        "parts": parts_index,
        "assembly_ga": "drawings/P-000_assembly_GA.svg",
    }
    (out / "PARTS_INDEX.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
