#!/usr/bin/env python3
"""Publish full MineClean apparatus studio (machines + piping + hardware)."""
from __future__ import annotations
import csv, json, shutil, sys
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import os as _os
_E = _os.environ.get("EIGEN_ROOT")
if _E:
    EIGEN = Path(_E).expanduser().resolve()
elif (ROOT.parent / "Eigen").is_dir():
    EIGEN = ROOT.parent / "Eigen"
else:
    EIGEN = Path.home() / "Eigen"
OUT = ROOT / "examples" / "output" / "mineclean_studio"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EIGEN / "scripts"))

def copytree(src, dst):
    if not src.exists(): return
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src, dst)

def _sync_product_hero_stills() -> list[str]:
    """Stage pitch-grade field-skid hero via shared hero_product pipeline."""
    renders = OUT / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    landed: list[str] = []
    try:
        from llmbim_drawings.hero_product import export_hero_pipeline

        man = export_hero_pipeline(
            OUT,
            product_id="mineclean",
            kind="skid",
            title="MineClean field skid",
            use_library=True,
        )
        if man.get("product_hero"):
            landed.append(str(man["product_hero"]))
        landed.append("HERO_BRIEF.json")
        landed.append("HERO_MANIFEST.json")
    except Exception as e:  # noqa: BLE001
        print(f"  [render] hero_pipeline: {e}")
    # Extra context stills from docs library
    src_docs = ROOT / "docs" / "renders" / "mineclean"
    for name in ("ghost.jpg", "ctx_amd.jpg", "field_skid_hero.jpg"):
        s = src_docs / name
        if s.is_file():
            d = renders / name
            try:
                shutil.copy2(s, d)
                landed.append(name)
            except OSError as e:
                print(f"  [render] {name}: {e}")
    return sorted(set(landed))


def main():
    print("=== Full apparatus studio ===")
    OUT.mkdir(parents=True, exist_ok=True)
    from examples.mineclean_full_apparatus import build, OUT as FA
    p = build()
    for item in FA.iterdir():
        d = OUT / item.name
        if item.is_dir(): copytree(item, d)
        else: shutil.copy2(item, d)

    product_stills = _sync_product_hero_stills()
    print(f"  product stills: {product_stills}")

    sheets = OUT / "sheets"; sheets.mkdir(exist_ok=True)
    for folder in ("drawings_sset", "part_sheets"):
        src = EIGEN / "docs" / "mineclean" / folder
        if src.exists():
            for f in src.glob("MB-MCLEAN*"):
                shutil.copy2(f, sheets / f.name)
    docs = OUT / "docs"; docs.mkdir(exist_ok=True)
    for name in [
        "MB-MCLEAN-BOM-001.md", "MB-MCLEAN-BOM-HARDWARE-001.md",
        "MB-MCLEAN-MACHINES-001.md", "MB-MCLEAN-LAYERS-001.md",
        "MB-MCLEAN-AWI-001_Assembly.md", "MB-MCLEAN-FAB-001_Product_Package.md",
        "MB-MCLEAN_Model_Set.md",
    ]:
        s = EIGEN / "docs" / "mineclean" / name
        if s.exists(): shutil.copy2(s, docs / name)
    for j in ("mineclean_basis.json", "mineclean_layers.json", "mineclean_machines.json"):
        s = EIGEN / "cad" / "design_basis" / j
        if s.exists(): shutil.copy2(s, OUT / j)
    (OUT / "schedules").mkdir(exist_ok=True)
    for c in ("mineclean_bom.csv", "mineclean_hardware_bom.csv"):
        s = EIGEN / "cad" / "fusion" / c
        if s.exists(): shutil.copy2(s, OUT / "schedules" / c)
    fab = EIGEN / "output" / "mineclean_fab_machines"
    if fab.exists(): copytree(fab, OUT / "fab")

    from mineclean_machines import MACHINES, PIPE_NETWORK, summary, aggregate_hardware
    from mineclean_design_basis import MCLEAN as S
    from mineclean_layers import leaf_count, ZONES, LAYERS
    sm = summary()
    counts = leaf_count()
    hw = aggregate_hardware()

    s_png = sorted(sheets.glob("MB-MCLEAN-S*.png"))
    d_png = sorted(sheets.glob("MB-MCLEAN-D*.png"))
    def cards(ps):
        return "\n".join(
            f'<a class="card" href="sheets/{p.name}" target="_blank"><img src="sheets/{p.name}" loading="lazy"/><span>{p.stem.replace("MB-MCLEAN-","")}</span></a>'
            for p in ps)

    mrows = ""
    for mid, m in MACHINES.items():
        nh = sum(h.get("qty",0) for h in m.get("hardware",[]))
        mrows += f"<tr><td><code>{mid}</code></td><td>{m['name']}</td><td>{m['layer_zone']}</td><td>{len(m['parts'])}</td><td>{nh}</td><td>{len(m.get('nozzles',[]))}</td><td>{len(m.get('pipe',[]))}</td></tr>"

    hrows = ""
    for h in hw[:80]:
        t = h.get("torque_Nm"); ts = f"{t:.0f}" if t else "—"
        hrows += f"<tr><td><code>{h['pn']}</code></td><td>{h['desc']}</td><td>{h['qty']}</td><td>{h.get('matl','')}</td><td>{ts}</td></tr>"

    prows = ""
    for seg in PIPE_NETWORK:
        prows += f"<tr><td><code>{seg['tag']}</code></td><td>{seg['nps']}</td><td>{seg['length_mm']:.0f}</td><td>{seg['system']}</td></tr>"

    step_files = sorted((OUT/"fab"/"fab").glob("*.step")) if (OUT/"fab"/"fab").exists() else []
    steps = "".join(f"<li><a href='fab/fab/{f.name}'>{f.name}</a></li>" for f in step_files[:40])
    views = "".join(f"<li><a href='views/{f.name}' target=_blank>{f.name}</a></li>" for f in sorted((OUT/"views").glob("*.svg"))) if (OUT/"views").exists() else ""

    html = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>MB-MCLEAN Full Apparatus — Machines + Piping + Hardware</title>
<style>
:root{{--bg:#0b0f14;--panel:#12181f;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--link:#58a6ff;--ok:#3fb950;--amber:#d29922;--card:#161b22}}
*{{box-sizing:border-box}}body{{font-family:system-ui,sans-serif;margin:0;background:var(--bg);color:var(--text);line-height:1.45}}
header{{padding:1.3rem 1.5rem;border-bottom:1px solid var(--border)}}
h1{{margin:.25rem 0;font-size:1.45rem}}.badge{{display:inline-block;padding:.1rem .45rem;border-radius:999px;background:#1f2937;color:var(--amber);font-size:.7rem;margin-right:.3rem;border:1px solid #3d4450}}
.badge.ok{{color:var(--ok)}}
nav{{display:flex;flex-wrap:wrap;gap:.4rem;padding:.65rem 1.5rem;border-bottom:1px solid var(--border);position:sticky;top:0;background:rgba(11,15,20,.95);z-index:20}}
nav a{{color:var(--link);text-decoration:none;font-size:.82rem;padding:.28rem .55rem;border:1px solid var(--border);border-radius:6px;background:var(--card)}}
main{{max-width:1280px;margin:0 auto;padding:1.1rem 1.4rem 3.5rem}}
section{{margin:1.8rem 0}}h2{{font-size:1.12rem;border-bottom:1px solid var(--border);padding-bottom:.3rem}}
a{{color:var(--link)}}.hero{{display:grid;grid-template-columns:1.1fr .9fr;gap:1rem}}
@media(max-width:900px){{.hero{{grid-template-columns:1fr}}}}
.hero img{{width:100%;border:1px solid var(--border);border-radius:10px;background:#000}}
.panel{{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:1rem}}
.cta{{display:inline-block;margin:.3rem .2rem;padding:.55rem .9rem;background:#1f6feb;color:#fff!important;text-decoration:none;border-radius:8px;font-weight:600}}
.cta.sec{{background:#21262d;border:1px solid var(--border)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:.7rem}}
.card{{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden;text-decoration:none;color:var(--text)}}
.card img{{width:100%;aspect-ratio:13/9;object-fit:cover;object-position:top}}
.card span{{padding:.45rem .55rem;font-size:.78rem;color:var(--muted)}}
table{{border-collapse:collapse;width:100%;font-size:.8rem}}th,td{{border:1px solid var(--border);padding:4px 6px;text-align:left}}th{{background:#161b22}}
code{{background:#21262d;padding:1px 4px;border-radius:4px}}.muted{{color:var(--muted);font-size:.86rem}}
.kpi{{display:flex;flex-wrap:wrap;gap:.45rem}}.kpi div{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:.45rem .7rem;min-width:100px}}
.kpi b{{display:block;font-size:1.02rem}}.kpi span{{font-size:.7rem;color:var(--muted)}}
.scroll{{max-height:420px;overflow:auto;border:1px solid var(--border);border-radius:8px}}
footer{{margin-top:2rem;padding-top:.8rem;border-top:1px solid var(--border);color:var(--muted);font-size:.78rem}}
ul.cols{{columns:2}}
</style></head><body>
<header>
<span class="badge ok">FULL APPARATUS</span>
<span class="badge">15 MACHINES</span>
<span class="badge">23 PIPE SEGS</span>
<span class="badge">3439 HARDWARE PCS</span>
<span class="badge">ENGINEERING ESTIMATE</span>
<h1>MB-MCLEAN — Full Manufacturable Apparatus</h1>
<p class="muted">Every block developed as a real machine · complete process piping · nuts, bolts, gaskets, washers</p>
</header>
<nav>
<a href="#hero">3D</a><a href="#machines">Machines</a><a href="#pipe">Piping</a>
<a href="#hardware">Hardware</a><a href="#s-sheets">S sheets</a><a href="#d-sheets">D sheets</a>
<a href="#step">STEP</a><a href="viewer3d.html"><b>3D Studio ↗</b></a>
</nav>
<main>
<section id="hero" class="hero">
<div>
{"<a href='renders/product_hero.jpg' target='_blank'><img src='renders/product_hero.jpg' alt='MB-MCLEAN field skid product hero'/></a>" if (OUT / "renders" / "product_hero.jpg").exists() else "<a href='hero.svg' target='_blank'><img src='hero.svg' alt='hero'/></a>"}
<p class="muted">Field-skid product still · full apparatus with process (PROC) + cooling (CW) · place_tube / place_wire_path densified</p>
<a class="cta" href="viewer3d.html">Open 3D Studio</a>
<a class="cta sec" href="PLOT_SET.pdf">PLOT_SET.pdf</a>
<a class="cta sec" href="fab/fab/ASM_mineclean_full_apparatus.step">Full ASM STEP</a>
<a class="cta sec" href="docs/MB-MCLEAN-MACHINES-001.md">Machines doc</a>
{"<a class='cta sec' href='renders/ghost_product.jpg'>Ghost still</a>" if (OUT / "renders" / "ghost_product.jpg").exists() else ""}
{"<a class='cta sec' href='renders/ctx_amd.jpg'>AMD context</a>" if (OUT / "renders" / "ctx_amd.jpg").exists() else ""}
</div>
<div class="panel">
<h3>Apparatus counts</h3>
<div class="kpi">
<div><b>{sm["n_machines"]}</b><span>machines</span></div>
<div><b>{sm["n_pipe_segments"]}</b><span>pipe segments</span></div>
<div><b>{sm["pipe_length_m"]} m</b><span>pipe CL length</span></div>
<div><b>{sm["n_part_lines"]}</b><span>equipment P/Ns</span></div>
<div><b>{sm["n_hardware_lines"]}</b><span>hardware lines</span></div>
<div><b>{sm["hardware_pieces"]}</b><span>nuts/bolts/etc</span></div>
<div><b>{p.stats().get("elements","?")}</b><span>3D elements</span></div>
<div><b>{counts["layers"]}</b><span>mfg layers</span></div>
</div>
<p class="muted">Chamber Ø{S["chamber_ID"]:.0f}×{S["chamber_L"]:.0f} · Skid {S["skid_W"]:.0f}×{S["skid_L"]:.0f} · {S["design_flow_m3_h"]:.0f} m³/h · ~{S["total_power_kW"]:.0f} kW</p>
<ul>
<li><a href="docs/MB-MCLEAN-BOM-HARDWARE-001.md">Full hardware BOM</a></li>
<li><a href="schedules/mineclean_hardware_bom.csv">Hardware CSV</a></li>
<li><a href="mineclean_machines.json">machines JSON SSOT</a></li>
</ul>
</div>
</section>

<section id="machines">
<h2>15 developed machine blocks</h2>
<div class="scroll"><table>
<tr><th>ID</th><th>Name</th><th>Zone</th><th>Parts</th><th>HW pcs</th><th>Nozzles</th><th>Pipe</th></tr>
{mrows}
</table></div>
<p class="muted">Each machine has nozzles, part list, and complete stud/nut/washer/gasket kits — see <a href="docs/MB-MCLEAN-MACHINES-001.md">MACHINES-001</a></p>
</section>

<section id="pipe">
<h2>Process + cooling pipe network ({sm["n_pipe_segments"]} segments · {sm["pipe_length_m"]} m)</h2>
<div class="scroll"><table><tr><th>Tag</th><th>NPS</th><th>L mm</th><th>System</th></tr>{prows}</table></div>
<p class="muted">PROC 3-in PTFE-lined main train · 1.5-in sludge · 1-in CW · 1/2-in samples · elbows/tees/flanges in M-PIPING</p>
</section>

<section id="hardware">
<h2>Nuts &amp; bolts rollup (top 80 of {sm["n_hardware_lines"]} lines)</h2>
<div class="scroll"><table><tr><th>P/N</th><th>Description</th><th>Qty</th><th>Matl</th><th>N·m</th></tr>{hrows}</table></div>
<p class="muted">Includes every 3-in flange kit (4 studs + 8 nuts + 8 washers + gasket per joint), cap M16 sets, saddle M20, collector M6+PTFE, etc.</p>
</section>

<section id="s-sheets">
<h2>S1–S8 fab sheets</h2>
<div class="grid">{cards(s_png)}</div>
</section>
<section id="d-sheets">
<h2>D1–D9 detail sheets</h2>
<div class="grid">{cards(d_png)}</div>
</section>

<section>
<h2>llm-bim views</h2>
<ul class="cols">{views or "<li class=muted>—</li>"}</ul>
</section>

<section id="step">
<h2>STEP solids ({len(step_files)})</h2>
<ul class="cols">{steps}</ul>
</section>

<section>
<h2>Honesty</h2>
<div class="panel">
<p>Manufacturable apparatus definition: real machines, full piping CL network, bolt-level hardware. <strong>Not</strong> field-proven cleanup. All quantities [ENGINEERING ESTIMATE] for RFQ.</p>
</div>
</section>
<footer>Mechanical Battery LLC · MB-MCLEAN full apparatus studio · {OUT.as_posix()}</footer>
</main></body></html>'''
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print(f"[OK] studio → {OUT}")
    print(f"     machines={sm['n_machines']} pipe={sm['n_pipe_segments']} hw={sm['hardware_pieces']}")

if __name__ == "__main__":
    main()
