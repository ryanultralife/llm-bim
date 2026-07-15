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
        "materials/csi_takeoff.json",
        "materials/csi_instances.json",
        "materials/connections.json",
        "materials/steel_takeoff.json",
        "materials/rebar_takeoff.json",
        "materials/trade_schedule.json",
        "materials/duct_takeoff.json",
        "materials/conduit_takeoff.json",
        "materials/MATERIALS_AND_PARTS.json",
        "schedules/plumbing_takeoff.json",
        "schedules/csi.csv",
        "schedules/duct.csv",
        "schedules/conduit.csv",
        "schedules/zone_areas.csv",
        "schedules/levels.csv",
        "schedules/drawing_list.csv",
        "schedules/connections.csv",
        "clash_report.json",
        "design_rules.json",
    ):
        if (out / rel).is_file():
            data_links.append(f'<li><a href="{rel}">{rel}</a></li>')

    # connection graph sample (enriched rows from connection_schedule)
    conn_preview = ""
    conn_path = out / "materials" / "connections.json"
    if not conn_path.is_file():
        conn_path = out / "schedules" / "connections.csv"
    if conn_path.is_file():
        try:
            if conn_path.suffix.lower() == ".json":
                cdata = json.loads(conn_path.read_text(encoding="utf-8"))
                rows = cdata if isinstance(cdata, list) else cdata.get("connections") or []
            else:
                import csv
                from io import StringIO

                rows = list(csv.DictReader(StringIO(conn_path.read_text(encoding="utf-8"))))
            lines = []
            for r in rows[:12]:
                loc = r.get("locator") or ""
                if not loc:
                    fn = r.get("from_name") or r.get("from_id") or ""
                    tn = r.get("to_name") or r.get("to_id") or ""
                    fp = r.get("from_port") or ""
                    tp = r.get("to_port") or ""
                    loc = f"{fn}.{fp} → {tn}.{tp}"
                med = r.get("medium") or ""
                name = r.get("name") or ""
                lines.append(
                    f"<tr><td>{name}</td><td><code>{loc}</code></td><td>{med}</td></tr>"
                )
            if lines:
                conn_preview = (
                    "<h2>Module connections (sample)</h2>"
                    "<p>Port graph for machines/host. Full list: "
                    "<a href=\"materials/connections.json\">connections.json</a> · "
                    "<a href=\"schedules/connections.csv\">schedules/connections.csv</a></p>"
                    "<table><tr><th>Name</th><th>Locator</th><th>Medium</th></tr>"
                    + "".join(lines)
                    + "</table>"
                )
        except Exception:  # noqa: BLE001
            conn_preview = ""

    # short CSI sample for agents scanning the pack
    csi_preview = ""
    csi_path = out / "materials" / "csi_instances.json"
    if csi_path.is_file():
        try:
            rows = json.loads(csi_path.read_text(encoding="utf-8"))
            sample = rows[:12] if isinstance(rows, list) else []
            lines = []
            for r in sample:
                code = r.get("csi_code") or ""
                loc = r.get("locator") or r.get("csi_instance") or ""
                name = r.get("element_name") or r.get("part_id") or r.get("element_id") or ""
                room = r.get("room") or ""
                lines.append(
                    f"<tr><td><code>{code}</code></td><td>{name}</td>"
                    f"<td>{room}</td><td><code>{loc}</code></td></tr>"
                )
            if lines:
                csi_preview = (
                    "<h2>CSI locators (sample)</h2>"
                    "<p>MasterFormat section + level|RM:room|XY|Z|NPS|RISER to find items. Full list: "
                    "<a href=\"materials/csi_instances.json\">csi_instances.json</a> · "
                    "<a href=\"schedules/csi.csv\">schedules/csi.csv</a></p>"
                    "<table><tr><th>CSI</th><th>Name</th><th>Room</th><th>Locator</th></tr>"
                    + "".join(lines)
                    + "</table>"
                )
        except Exception:  # noqa: BLE001
            csi_preview = ""

    # zone / area schedule sample
    zone_preview = ""
    zone_path = out / "schedules" / "zone_areas.csv"
    if zone_path.is_file():
        try:
            import csv
            from io import StringIO

            rows = list(csv.DictReader(StringIO(zone_path.read_text(encoding="utf-8"))))
            lines = []
            for r in rows[:12]:
                lines.append(
                    "<tr>"
                    f"<td>{r.get('name') or ''}</td>"
                    f"<td>{r.get('level') or ''}</td>"
                    f"<td>{r.get('area_m2') or ''}</td>"
                    f"<td>{r.get('height_mm') or ''}</td>"
                    f"<td>{r.get('volume_m3') or ''}</td>"
                    "</tr>"
                )
            if lines:
                zone_preview = (
                    "<h2>Zone / area schedule (sample)</h2>"
                    "<p>Room areas + clear height. Full: "
                    "<a href=\"schedules/zone_areas.csv\">zone_areas.csv</a></p>"
                    "<table><tr><th>Name</th><th>Level</th><th>Area m²</th>"
                    "<th>Height mm</th><th>Vol m³</th></tr>"
                    + "".join(lines)
                    + "</table>"
                )
        except Exception:  # noqa: BLE001
            zone_preview = ""

    # drawing / sheet index sample
    draw_preview = ""
    draw_path = out / "schedules" / "drawing_list.csv"
    if draw_path.is_file():
        try:
            import csv
            from io import StringIO

            rows = list(csv.DictReader(StringIO(draw_path.read_text(encoding="utf-8"))))
            lines = []
            for r in rows[:20]:
                lines.append(
                    "<tr>"
                    f"<td>{r.get('sheet_no') or ''}</td>"
                    f"<td>{r.get('name') or ''}</td>"
                    f"<td>{r.get('kind') or ''}</td>"
                    f"<td><a href=\"{r.get('path') or '#'}\">{r.get('path') or ''}</a></td>"
                    f"<td>{r.get('format') or ''}</td>"
                    "</tr>"
                )
            if lines:
                draw_preview = (
                    "<h2>Drawing list (sample)</h2>"
                    "<p>Sheet inventory. Full: "
                    "<a href=\"schedules/drawing_list.csv\">drawing_list.csv</a></p>"
                    "<table><tr><th>#</th><th>Name</th><th>Kind</th>"
                    "<th>Path</th><th>Fmt</th></tr>"
                    + "".join(lines)
                    + "</table>"
                )
        except Exception:  # noqa: BLE001
            draw_preview = ""

    # design rules findings sample
    rules_preview = ""
    rules_path = out / "design_rules.json"
    if rules_path.is_file():
        try:
            rdata = json.loads(rules_path.read_text(encoding="utf-8"))
            findings = rdata.get("findings") or []
            summary = rdata.get("summary") or {}
            lines = []
            for f in findings[:15]:
                lines.append(
                    "<tr>"
                    f"<td>{f.get('severity') or ''}</td>"
                    f"<td><code>{f.get('rule') or ''}</code></td>"
                    f"<td>{f.get('domain') or ''}</td>"
                    f"<td>{(f.get('message') or '')[:80]}</td>"
                    "</tr>"
                )
            if lines or summary:
                tot = summary.get("total", len(findings))
                rules_preview = (
                    "<h2>Design rules (sample)</h2>"
                    f"<p>Findings: {tot} "
                    f"(err {summary.get('error', 0)} / warn {summary.get('warning', 0)} / "
                    f"info {summary.get('info', 0)}). Full: "
                    "<a href=\"design_rules.json\">design_rules.json</a></p>"
                )
                if lines:
                    rules_preview += (
                        "<table><tr><th>Sev</th><th>Rule</th><th>Domain</th>"
                        "<th>Message</th></tr>"
                        + "".join(lines)
                        + "</table>"
                    )
        except Exception:  # noqa: BLE001
            rules_preview = ""

    legend = """
<h2>MEP / layers legend</h2>
<ul>
<li><strong>Plan SVG</strong> — copper pipes orange; fire black steel dark; process SS gray; PVC yellow; risers = concentric circles; ducts green; conduit purple; cable tray dashed purple; columns X-marks; beams gray</li>
<li><strong>DXF layers</strong> — WALLS, EQUIP, ROOMS, PIPE-CU/FP/SS, DUCT, CONDUIT, CABLE-TRAY, COLUMNS, BEAMS, FITTINGS (risers = CIRCLE)</li>
<li><strong>CSI</strong> — e.g. <code>22 11 16</code> domestic water, <code>21 13 13</code> wet sprinkler, <code>05 12 00</code> structural steel, <code>23 31 00</code> duct, <code>26 05 33</code> conduit</li>
<li><strong>Locator</strong> — <code>L1|RM:Restroom_A|X1200Y3400|Z900|NPS3/4|W10x33|SYS SA|FR2hr|COLUMN|RISER</code> (level · RM: · XY · Z · H · NPS · section · SYS · FR · category)</li>
<li><strong>Honesty</strong> — ENGINEERING ESTIMATE envelopes/takeoff; not PE-sealed CDs</li>
</ul>
"""

    ok = manifest.get("ok", manifest.get("verification", {}).get("ok"))
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{manifest.get("project", "LLM-BIM pack")}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;
background:#0b0f14;color:#e6edf3}}
a{{color:#58a6ff}} .ok{{color:#3fb950}} .bad{{color:#f85149}}
code{{background:#21262d;padding:2px 6px;border-radius:4px}}
table{{border-collapse:collapse;width:100%;font-size:0.9rem}}
td,th{{border:1px solid #30363d;padding:6px 8px;text-align:left}}
th{{background:#161b22}}
</style></head><body>
<h1>{manifest.get("project", "Deliverables pack")}</h1>
<p>Status: <span class="{"ok" if ok else "bad"}">{"OK" if ok else "CHECK VERIFY.json"}</span></p>
<p>{manifest.get("honesty", "")}</p>
<h2>3D / BIM</h2><ul>{"".join(threes)}</ul>
<h2>Materials / takeoff / CSI</h2><ul>{"".join(data_links) or "<li>none — place fittings/parts then re-export</li>"}</ul>
{csi_preview}
{zone_preview}
{conn_preview}
{draw_preview}
{rules_preview}
{legend}
<h2>Drawings (SVG)</h2><ul>{"".join(links) or "<li>none</li>"}</ul>
<h2>Manifest</h2><pre>{json.dumps(manifest.get("verification", {}), indent=2)}</pre>
</body></html>
"""
    path = out / "index.html"
    path.write_text(html, encoding="utf-8")
    return path
