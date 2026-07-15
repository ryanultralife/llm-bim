"""HTML index for browsing a deliverables pack in a browser."""

from __future__ import annotations

import json
from pathlib import Path


def write_pack_index(out_dir: str | Path) -> Path:
    out = Path(out_dir)
    manifest_path = out / "MANIFEST.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    svgs = sorted(out.rglob("*.svg"))
    links = []
    for s in svgs:
        rel = s.relative_to(out).as_posix()
        links.append(f'<li><a href="{rel}" target="_blank">{rel}</a></li>')

    threes = []
    for name in ("model.gltf", "model.ifc", "model.step", "model.llmbim.json", "PLOT_SET.pdf", "boq.json"):
        if (out / name).exists():
            threes.append(f'<li><a href="{name}">{name}</a> ({(out / name).stat().st_size} bytes)</li>')

    data_links = []
    for rel in (
        "materials/fitting_takeoff.json",
        "materials/pipe_takeoff.json",
        "materials/material_summary.json",
        "materials/part_assignments.json",
        "materials/plumbing_schedule.json",
        "materials/MATERIALS_AND_PARTS.json",
        "schedules/plumbing_takeoff.json",
        "clash_report.json",
        "design_rules.json",
    ):
        if (out / rel).is_file():
            data_links.append(f'<li><a href="{rel}">{rel}</a></li>')

    ok = manifest.get("ok", manifest.get("verification", {}).get("ok"))
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{manifest.get("project", "LLM-BIM pack")}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;
background:#0b0f14;color:#e6edf3}}
a{{color:#58a6ff}} .ok{{color:#3fb950}} .bad{{color:#f85149}}
code{{background:#21262d;padding:2px 6px;border-radius:4px}}
</style></head><body>
<h1>{manifest.get("project", "Deliverables pack")}</h1>
<p>Status: <span class="{"ok" if ok else "bad"}">{"OK" if ok else "CHECK VERIFY.json"}</span></p>
<p>{manifest.get("honesty", "")}</p>
<h2>3D / BIM</h2><ul>{"".join(threes)}</ul>
<h2>Materials / plumbing takeoff</h2><ul>{"".join(data_links) or "<li>none — place fittings/parts then re-export</li>"}</ul>
<h2>Drawings (SVG)</h2><ul>{"".join(links) or "<li>none</li>"}</ul>
<h2>Manifest</h2><pre>{json.dumps(manifest.get("verification", {}), indent=2)}</pre>
</body></html>
"""
    path = out / "index.html"
    path.write_text(html, encoding="utf-8")
    return path
