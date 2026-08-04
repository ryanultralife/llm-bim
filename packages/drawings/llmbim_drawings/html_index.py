"""HTML index for browsing a deliverables pack in a browser."""

from __future__ import annotations

import json
from pathlib import Path


def _sheet_title_from_name(stem: str) -> str:
    """Human sheet label from file stem (no path)."""
    # A-101_plan → A-101 · Plan
    if "_" in stem:
        no, rest = stem.split("_", 1)
        return f"{no} · {rest.replace('_', ' ').title()}"
    return stem.replace("_", " ")


def _construction_sheet_cards(out: Path) -> str:
    """Construction sheets as preview cards (sheet no + title), not path lists."""
    index_path = out / "construction" / "SHEET_INDEX.json"
    cards: list[str] = []
    if index_path.is_file():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            for s in data.get("sheets") or []:
                f = s.get("file") or ""
                no = s.get("no") or Path(f).stem
                title = s.get("title") or _sheet_title_from_name(Path(f).stem)
                rel = f"construction/{f}"
                if not (out / "construction" / f).is_file():
                    continue
                disc = s.get("discipline") or ""
                tag = (
                    f'<span style="display:inline-block;background:#1a3a55;'
                    f'color:#9ec9ef;font-size:0.68rem;padding:1px 5px;'
                    f'border-radius:3px;margin-right:4px">{disc}</span>'
                    if disc
                    else ""
                )
                cards.append(
                    f'<a class="sheet-card" href="{rel}" target="_blank">'
                    f'<div class="thumb"><img src="{rel}" alt="{no} · {title}" loading="lazy"/></div>'
                    f'<div class="cap">{tag}<strong>{no}</strong> · {title}</div></a>'
                )
        except Exception:  # noqa: BLE001
            cards = []
    if not cards:
        # fallback: construction/*.svg only (not entire pack path dump)
        for s in sorted((out / "construction").glob("*.svg")) if (out / "construction").is_dir() else []:
            rel = f"construction/{s.name}"
            label = _sheet_title_from_name(s.stem)
            cards.append(
                f'<a class="sheet-card" href="{rel}" target="_blank">'
                f'<div class="thumb"><img src="{rel}" alt="{label}" loading="lazy"/></div>'
                f'<div class="cap">{label}</div></a>'
            )
    if not cards:
        return ""
    return (
        f"<h2>Construction sheets <span style=\"color:#8b949e;font-weight:400\">"
        f"({len(cards)})</span></h2>"
        "<p style=\"color:#8b949e;font-size:0.9rem\">Sheet previews — click to open. "
        "Not a path list.</p>"
        f'<div class="sheet-grid">{"".join(cards)}</div>'
    )


def write_pack_index(out_dir: str | Path) -> Path:
    out = Path(out_dir)
    manifest_path = out / "MANIFEST.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Other SVGs (views, parts) — collapsible; labels without path spam
    other_links: list[str] = []
    for s in sorted(out.rglob("*.svg")):
        rel = s.relative_to(out).as_posix()
        if rel.startswith("construction/") or rel == "hero.svg":
            continue
        label = _sheet_title_from_name(s.stem)
        other_links.append(f'<li><a href="{rel}" target="_blank">{label}</a></li>')

    threes = []
    if (out / "viewer3d.html").exists():
        threes.append(
            '<li><strong><a href="viewer3d.html">viewer3d.html</a></strong> — '
            "3D studio: section cut · cinematic bloom · Imagine sky/floor · layer opacity</li>"
        )
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
        "materials/cable_tray_takeoff.json",
        "materials/MATERIALS_AND_PARTS.json",
        "schedules/plumbing_takeoff.json",
        "schedules/csi.csv",
        "schedules/duct.csv",
        "schedules/conduit.csv",
        "schedules/cable_tray.csv",
        "schedules/column.csv",
        "schedules/beam.csv",
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

    # drawing / sheet index — sheet no + title (linked), never raw path column
    draw_preview = ""
    draw_path = out / "schedules" / "drawing_list.csv"
    sheet_idx = out / "construction" / "SHEET_INDEX.json"
    title_by_file: dict[str, tuple[str, str]] = {}
    if sheet_idx.is_file():
        try:
            for s in (json.loads(sheet_idx.read_text(encoding="utf-8")).get("sheets") or []):
                f = s.get("file") or ""
                title_by_file[f] = (s.get("no") or Path(f).stem, s.get("title") or "")
                title_by_file[Path(f).stem] = title_by_file[f]
        except Exception:  # noqa: BLE001
            pass
    if draw_path.is_file():
        try:
            import csv
            from io import StringIO

            rows = list(csv.DictReader(StringIO(draw_path.read_text(encoding="utf-8"))))
            lines = []
            for r in rows[:40]:
                path = (r.get("path") or "").replace("\\", "/")
                name = r.get("name") or Path(path).stem
                no, title = title_by_file.get(Path(path).name, ("", ""))
                if not no:
                    no, title = title_by_file.get(name, (r.get("sheet_no") or "", ""))
                if not no:
                    no = r.get("sheet_no") or name
                if not title:
                    title = _sheet_title_from_name(name).split(" · ", 1)[-1] if " · " in _sheet_title_from_name(name) else name.replace("_", " ")
                href = path if path else "#"
                kind = r.get("kind") or ""
                fmt = r.get("format") or ""
                lines.append(
                    "<tr>"
                    f"<td><strong>{no}</strong></td>"
                    f"<td><a href=\"{href}\" target=\"_blank\">{title}</a></td>"
                    f"<td>{kind}</td>"
                    f"<td>{fmt}</td>"
                    "</tr>"
                )
            if lines:
                draw_preview = (
                    "<h2>Sheet index</h2>"
                    "<p style=\"color:#8b949e;font-size:0.9rem\">"
                    "Sheet number + title (click opens the drawing). "
                    "Full CSV: "
                    "<a href=\"schedules/drawing_list.csv\">drawing_list.csv</a></p>"
                    "<table><tr><th>Sheet</th><th>Title</th><th>Kind</th>"
                    "<th>Fmt</th></tr>"
                    + "".join(lines)
                    + "</table>"
                )
        except Exception:  # noqa: BLE001
            draw_preview = ""

    construction_gallery = _construction_sheet_cards(out)

    # door schedule sample (type + fire rating) — doors.csv preferred, door.csv legacy
    door_preview = ""
    door_path = out / "schedules" / "doors.csv"
    if not door_path.is_file():
        door_path = out / "schedules" / "door.csv"
    if door_path.is_file():
        try:
            import csv
            from io import StringIO

            rows = list(csv.DictReader(StringIO(door_path.read_text(encoding="utf-8"))))
            lines = []
            for r in rows[:15]:
                lines.append(
                    "<tr>"
                    f"<td>{r.get('name') or r.get('id') or ''}</td>"
                    f"<td>{r.get('type_id') or ''}</td>"
                    f"<td>{r.get('fire_rating') or ''}</td>"
                    f"<td>{r.get('width_mm') or r.get('width') or ''}</td>"
                    f"<td>{r.get('height_mm') or r.get('height') or ''}</td>"
                    f"<td><code>{(r.get('locator') or '')[:40]}</code></td>"
                    "</tr>"
                )
            if lines:
                href = door_path.name
                door_preview = (
                    "<h2>Door schedule (sample)</h2>"
                    "<p>Type marks + fire rating. Full: "
                    f"<a href=\"schedules/{href}\">{href}</a></p>"
                    "<table><tr><th>Name</th><th>Type</th><th>FR</th>"
                    "<th>W</th><th>H</th><th>Locator</th></tr>"
                    + "".join(lines)
                    + "</table>"
                )
        except Exception:  # noqa: BLE001
            door_preview = ""

    # window schedule sample (type + sill) — windows.csv preferred, window.csv legacy
    window_preview = ""
    window_path = out / "schedules" / "windows.csv"
    if not window_path.is_file():
        window_path = out / "schedules" / "window.csv"
    if window_path.is_file():
        try:
            import csv
            from io import StringIO

            rows = list(csv.DictReader(StringIO(window_path.read_text(encoding="utf-8"))))
            lines = []
            for r in rows[:15]:
                lines.append(
                    "<tr>"
                    f"<td>{r.get('name') or r.get('id') or ''}</td>"
                    f"<td>{r.get('type_id') or ''}</td>"
                    f"<td>{r.get('width_mm') or r.get('width') or ''}</td>"
                    f"<td>{r.get('height_mm') or r.get('height') or ''}</td>"
                    f"<td>{r.get('sill_mm') or r.get('sill') or ''}</td>"
                    f"<td><code>{(r.get('locator') or '')[:40]}</code></td>"
                    "</tr>"
                )
            if lines:
                href = window_path.name
                window_preview = (
                    "<h2>Window schedule (sample)</h2>"
                    "<p>Type marks + sill height. Full: "
                    f"<a href=\"schedules/{href}\">{href}</a></p>"
                    "<table><tr><th>Name</th><th>Type</th>"
                    "<th>W</th><th>H</th><th>Sill</th><th>Locator</th></tr>"
                    + "".join(lines)
                    + "</table>"
                )
        except Exception:  # noqa: BLE001
            window_preview = ""

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
<li><strong>Plan SVG</strong> — copper pipes orange; fire black steel dark; process SS gray; PVC yellow; risers = concentric circles; ducts green; conduit purple; cable tray dashed purple; columns X-marks; beams gray; doors/windows green/blue</li>
<li><strong>Openings</strong> — plan/elev/section SVG+DXF show type/FR marks; IFC/glTF/STEP host placement; clash AABB vs MEP</li>
<li><strong>DXF layers</strong> — WALLS, EQUIP, ROOMS, PIPE-CU/FP/SS, DUCT, CONDUIT, CABLE-TRAY, COLUMNS, BEAMS, FITTINGS (risers = CIRCLE)</li>
<li><strong>CSI</strong> — e.g. <code>22 11 16</code> domestic water, <code>21 13 13</code> wet sprinkler, <code>05 12 00</code> structural steel, <code>23 31 00</code> duct, <code>26 05 33</code> conduit</li>
<li><strong>Locator</strong> — <code>L1|RM:Restroom_A|X1200Y3400|Z900|NPS3/4|W10x33|SYS SA|FR2hr|COLUMN|RISER</code> (level · RM: · XY · Z · H · NPS · section · SYS · FR · category)</li>
<li><strong>Honesty</strong> — ENGINEERING ESTIMATE envelopes/takeoff; not PE-sealed CDs</li>
</ul>
"""

    # Hero stills: prefer photoreal product_hero (pitch-grade), then axonometric hero.svg
    hero_html = ""
    product_hero = None
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        cand = out / "renders" / f"product_hero{ext}"
        if cand.is_file():
            product_hero = cand
            break
    if product_hero is not None:
        rel = product_hero.relative_to(out).as_posix()
        hero_html = (
            '<figure style="margin:1.2rem 0">'
            f'<a href="{rel}" target="_blank">'
            f'<img src="{rel}" alt="Product hero still" '
            'style="width:100%;height:auto;display:block;'
            'border:1px solid #30363d;border-radius:8px"></a>'
            '<figcaption style="color:#8b949e;font-size:0.85rem;margin-top:4px">'
            "Product hero still — communication render [ENGINEERING ESTIMATE] · "
            "alongside sheets / 3D / specs · <a href=\"renders/HERO_BRIEF.json\">HERO_BRIEF</a>"
            "</figcaption></figure>"
        )
    elif (out / "hero.svg").is_file():
        hero_html = (
            '<figure style="margin:1.2rem 0">'
            '<a href="hero.svg" target="_blank">'
            '<img src="hero.svg" alt="Shaded axonometric hero render of the model" '
            'style="width:100%;height:auto;display:block;'
            'border:1px solid #30363d;border-radius:8px"></a>'
            '<figcaption style="color:#8b949e;font-size:0.85rem;margin-top:4px">'
            "Presentation axonometric (hero.svg) — [NOT FOR CONSTRUCTION] · "
            "for photoreal product stills see <code>export_hero_pipeline</code> / "
            "<a href=\"renders/HERO_BRIEF.json\">HERO_BRIEF.json</a> when present"
            "</figcaption></figure>"
        )
    # secondary strip: axonometric next to product hero when both exist
    if product_hero is not None and (out / "hero.svg").is_file():
        hero_html += (
            '<p style="color:#8b949e;font-size:0.85rem;margin:0.4rem 0 1rem">'
            'Also: <a href="hero.svg" target="_blank">hero.svg</a> (deterministic 3D axonometric) · '
            '<a href="viewer3d.html">viewer3d.html</a> · '
            '<a href="renders/">renders/</a></p>'
        )

    ok = manifest.get("ok", manifest.get("verification", {}).get("ok"))
    other_block = ""
    if other_links:
        other_block = (
            f"<details style=\"margin:1rem 0\"><summary style=\"cursor:pointer;"
            f"color:#8b949e\">Other drawings / parts "
            f"({len(other_links)}) — expand</summary>"
            f"<ul style=\"font-size:0.88rem\">{''.join(other_links)}</ul></details>"
        )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{manifest.get("project", "LLM-BIM pack")}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;
background:#0b0f14;color:#e6edf3}}
a{{color:#58a6ff}} .ok{{color:#3fb950}} .bad{{color:#f85149}}
code{{background:#21262d;padding:2px 6px;border-radius:4px}}
table{{border-collapse:collapse;width:100%;font-size:0.9rem}}
td,th{{border:1px solid #30363d;padding:6px 8px;text-align:left}}
th{{background:#161b22}}
.sheet-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));
gap:0.65rem;margin:0.75rem 0 1.25rem}}
.sheet-card{{display:flex;flex-direction:column;background:#121821;border:1px solid #30363d;
border-radius:8px;overflow:hidden;text-decoration:none;color:inherit}}
.sheet-card:hover{{border-color:#58a6ff}}
.sheet-card .thumb{{background:#f4f5f7;aspect-ratio:4/3;display:flex;align-items:center;
justify-content:center;overflow:hidden}}
.sheet-card .thumb img{{width:100%;height:100%;object-fit:contain;background:#fff}}
.sheet-card .cap{{padding:0.45rem 0.55rem;font-size:0.78rem;color:#8b949e;line-height:1.3}}
.sheet-card .cap strong{{color:#e6edf3}}
</style></head><body>
<h1>{manifest.get("project", "Deliverables pack")}</h1>
<p>Status: <span class="{"ok" if ok else "bad"}">{"OK" if ok else "CHECK VERIFY.json"}</span></p>
<p>{manifest.get("honesty", "")}</p>
{hero_html}
{"<p><a href='viewer3d.html' style='font-size:1.05rem'>Open 3D Studio</a> — section cut · cinematic bloom · Imagine env · layer opacity</p>" if (out / "viewer3d.html").exists() else ""}
{construction_gallery}
{draw_preview}
<h2>3D / BIM</h2><ul>{"".join(threes)}</ul>
<h2>Materials / takeoff / CSI</h2><ul>{"".join(data_links) or "<li>none — place fittings/parts then re-export</li>"}</ul>
{csi_preview}
{zone_preview}
{conn_preview}
{door_preview}
{window_preview}
{rules_preview}
{legend}
{other_block}
<h2>Manifest</h2><pre>{json.dumps(manifest.get("verification", {}), indent=2)}</pre>
</body></html>
"""
    path = out / "index.html"
    path.write_text(html, encoding="utf-8")
    return path
