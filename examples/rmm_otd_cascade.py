#!/usr/bin/env python3
"""RMM-OTD Rev C cascade — full llm-bim pack (STEP + 2D + 3D + HTML).

Source SSOT (Eigen):
  cad/rmm_otd_dims.json  (geometry master)
  docs/rmm_otd_drawings/  (2D MB-OTD sheets)
  docs/renders/rmm_otd/   (product heroes)
  cad/openscad/renders/  (cascade OpenSCAD stills)
  docs/rmm_otd_studio/step_refs/*.stl  (optional high-fidelity meshes)

Build:
  python examples/rmm_otd_cascade.py
  python examples/open_packs.py rmm_otd   # open HTML

Outputs:
  examples/output/rmm_otd/
    model.step · model.gltf · model.ifc · model.llmbim.json
    index.html · gallery.html · viewer3d.html
    views/ · sheets/ · fab/ · renders/ · parts/
"""
from __future__ import annotations

import json
import math
import shutil
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "output" / "rmm_otd"

# Eigen SSOT discovery
_sib = ROOT.parent / "Eigen"
EIGEN = Path(__import__("os").environ["EIGEN_ROOT"]) if __import__("os").environ.get("EIGEN_ROOT") else (
    _sib if _sib.is_dir() else Path.home() / "Eigen"
)

from llmbim import Project  # noqa: E402


def _load_dims() -> dict:
    candidates = [
        EIGEN / "cad" / "rmm_otd_dims.json",
        EIGEN / "docs" / "rmm_otd_studio" / "docs" / "rmm_otd_dims.json",
        ROOT / "examples" / "output" / "rmm_otd_studio" / "docs" / "rmm_otd_dims.json",
    ]
    for p in candidates:
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError("cad/rmm_otd_dims.json not found — set EIGEN_ROOT or open Eigen sibling")


def _circle(cx: float, cy: float, r: float, n: int = 48) -> list[tuple[float, float]]:
    return [
        (cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def _tube(
    p: Project,
    *,
    name: str,
    kind: str,
    od: float,
    id_mm: float | None,
    z_bot: float,
    z_top: float,
    equipment: str = "MB-OTD",
    part: str = "",
) -> str:
    h = abs(z_top - z_bot)
    return p.create_equipment_box(
        level="Module",
        origin=(0.0, 0.0),
        size=(od, od, h),
        name=name,
        kind=kind,
        shape="cylinder",
        orientation="z",
        centered=True,
        z0_mm=min(z_bot, z_top),
        id_mm=id_mm,
        equipment=equipment,
        part=part or name,
    )


def build(out_dir: Path | None = None) -> tuple[Project, Path]:
    out = Path(out_dir) if out_dir else OUT
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    d = _load_dims()
    # Shift master Z so stand sits near z=0
    z_floor = float(d["col_z0"]) - 80.0  # pad under column

    def Z(z: float) -> float:
        return float(z) - z_floor

    p = Project.create("MB-OTD RMM-OTD Cascade Module", vcs=False)
    p.add_level("Module", 0)

    # --- Stand / containment pad ---
    cont_od = float(d["cont_ri"] + d["cont_sand"] + d["cont_t"]) * 2
    p.create_equipment_box(
        level="Module",
        origin=(0.0, 0.0),
        size=(cont_od + 200, cont_od + 200, 80.0),
        name="Stand pad",
        kind="pedestal",
        centered=True,
        z0_mm=0.0,
        equipment="MB-OTD",
        part="stand",
    )

    # --- Central column ---
    _tube(
        p,
        name="Central column",
        kind="shaft",
        od=float(d["col_r"]) * 2,
        id_mm=None,
        z_bot=Z(d["col_z0"]),
        z_top=Z(d["col_z1"]),
        part="column",
    )

    # --- Three CF rotors (hollow) ---
    for label, ro, ri, za, zb, part in (
        ("Outer CF rotor", d["Ro1"], d["Ri1"], d["z1a"], d["z1b"], "rotor_outer"),
        ("Middle CF rotor", d["Ro2"], d["Ri2"], d["z2a"], d["z2b"], "rotor_middle"),
        ("Inner CF rotor", d["Ro3"], d["Ri3"], d["z3a"], d["z3b"], "rotor_inner"),
    ):
        _tube(
            p,
            name=label,
            kind="rotor",
            od=float(ro) * 2,
            id_mm=float(ri) * 2,
            z_bot=Z(za),
            z_top=Z(zb),
            part=part,
        )

    # --- Drive stator band (outermost) ---
    _tube(
        p,
        name="Drive stator band",
        kind="stator",
        od=float(d["drive_r2"]) * 2,
        id_mm=float(d["drive_r1"]) * 2,
        z_bot=Z(d["drive_z0"]),
        z_top=Z(d["drive_z1"]),
        part="drive_stator",
    )

    # --- Main vessel wall ---
    _tube(
        p,
        name="Main vessel wall",
        kind="vessel",
        od=float(d["vM_ro"]) * 2,
        id_mm=float(d["vM_ri"]) * 2,
        z_bot=Z(d["zM0"]),
        z_top=Z(d["zM1"]),
        part="vessel_main",
    )

    # --- End caps ---
    for name, r, zc, part in (
        ("Bottom end cap", d["capB_r"], d["zCapB"], "cap_bottom"),
        ("Top end cap", d["capT_r"], d["zSp1"], "cap_top"),
    ):
        _tube(
            p,
            name=name,
            kind="cap",
            od=float(r) * 2,
            id_mm=float(d["col_r"]) * 2 + 10,
            z_bot=Z(zc),
            z_top=Z(zc) + float(d["cap_t"]),
            part=part,
        )

    # --- Gear stage A modulators (annulus) ---
    _tube(
        p,
        name="Gear A modulator",
        kind="modulator",
        od=float(d["gA_mod_r2"]) * 2,
        id_mm=float(d["gA_mod_r1"]) * 2,
        z_bot=Z(d["zA0"]),
        z_top=Z(d["zA1"]),
        part="gearA_mod",
    )
    _tube(
        p,
        name="Gear B modulator",
        kind="modulator",
        od=float(d["gB_mod_r2"]) * 2,
        id_mm=float(d["gB_mod_r1"]) * 2,
        z_bot=Z(d["zB0"]),
        z_top=Z(d["zB1"]),
        part="gearB_mod",
    )

    # --- CVT stack ---
    for name, r1, r2, part in (
        ("CVT flywheel rim", d["cvt_fly_r1"], d["cvt_fly_r2"], "cvt_fly"),
        ("CVT isolation can", d["cvt_can_r1"], d["cvt_can_r2"], "cvt_can"),
        ("CVT follower", d["cvt_out_r1"], d["cvt_out_r2"], "cvt_out"),
        ("CVT control ring", d["cvt_ctrl_r1"], d["cvt_ctrl_r2"], "cvt_ctrl"),
        ("CVT stator", d["cvt_stat_r1"], d["cvt_stat_r2"], "cvt_stat"),
        ("CVT housing", d["cvt_house_r1"], d["cvt_house_r2"], "cvt_house"),
    ):
        _tube(
            p,
            name=name,
            kind="cvt",
            od=float(r2) * 2,
            id_mm=float(r1) * 2,
            z_bot=Z(d["zC0"]),
            z_top=Z(d["zC1"]),
            part=part,
        )

    # --- Containment sleeve (ghost) ---
    _tube(
        p,
        name="Containment sleeve",
        kind="containment",
        od=float(d["cont_ri"] + d["cont_sand"] + d["cont_t"]) * 2,
        id_mm=float(d["cont_ri"]) * 2,
        z_bot=Z(d["zCapB"]) - 20,
        z_top=Z(d["zSp1"]) + float(d["cap_t"]) + 40,
        part="containment",
    )

    # Plan silhouette
    p.create_slab(
        level="Module",
        polygon=_circle(0, 0, float(d["vM_ro"]), n=48),
        thickness_mm=2.0,
        name="Vessel OD plan silhouette",
    )
    clear = float(d["cont_ri"] + d["cont_sand"] + d["cont_t"]) * 2 + 400
    p.create_room(
        level="Module",
        name="RMM-OTD module envelope",
        boundary=[
            (-clear / 2, -clear / 2),
            (clear / 2, -clear / 2),
            (clear / 2, clear / 2),
            (-clear / 2, clear / 2),
        ],
    )

    try:
        p.auto_assign()
    except Exception as exc:  # noqa: BLE001
        print(f"  [auto_assign] {exc}")
    try:
        p.commit("RMM-OTD Rev C cascade BIM envelopes from geometry master")
    except ValueError as exc:
        # vcs may already have auto-committed; continue
        print(f"  [commit] {exc}")

    # Full llm-bim pack: glTF + STEP + IFC + 2D views + parts
    manifest = p.export_deliverables(
        out,
        mode="part",
        plan_level="Module",
        plan_scale=0.15,
        set_type="construction",
    )

    # --- Stage Eigen 2D sheets + fab + OpenSCAD stills + product hero ---
    _stage_eigen_assets(out, d)

    # Hero pipeline (library rmm_otd)
    try:
        from llmbim_drawings.hero_product import export_hero_pipeline, stage_hero_render

        export_hero_pipeline(
            out,
            product_id="rmm_otd",
            kind="device",
            title="RMM-OTD mechanical battery cascade",
            use_library=True,
        )
        # Prefer cascade section as product hero if library thin
        for cand in (
            EIGEN / "cad" / "openscad" / "renders" / "cascade_section.png",
            EIGEN / "docs" / "renders" / "rmm_otd" / "hero.jpg",
            EIGEN / "docs" / "renders" / "rmm_otd" / "cutaway.jpg",
            out / "renders" / "cascade_section.png",
        ):
            if cand.is_file():
                stage_hero_render(out, cand)
                break
    except Exception as exc:  # noqa: BLE001
        print(f"  [hero] {exc}")

    # Rich gallery HTML (user-facing)
    gallery = _write_gallery_html(out, d, manifest)
    _enhance_index(out, d)

    meta = {
        "project": "MB-OTD RMM-OTD Cascade",
        "honesty": "ENGINEERING ESTIMATE — llm-bim envelopes + Eigen master dims",
        "architecture": "Rev C cascade (staged lock)",
        "eigen_master": str(EIGEN / "cad" / "rmm_otd_dims.json"),
        "performance_est": {
            "E_kWh": d.get("E_kwh"),
            "E_use_kWh": d.get("E_use"),
            "m_rotors_kg": d.get("m_rotors"),
            "wh_kg": d.get("wh_kg"),
            "v_tip_m_s": d.get("v_tip"),
            "SF": d.get("SF"),
        },
        "stats": p.stats(),
        "validation": p.validate(),
        "deliverables": manifest,
        "gallery": str(gallery),
        "viewer3d": str(out / "viewer3d.html"),
        "index": str(out / "index.html"),
    }
    (out / "rmm_otd_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (out / "docs").mkdir(exist_ok=True)
    shutil.copy2(EIGEN / "cad" / "rmm_otd_dims.json", out / "docs" / "rmm_otd_dims.json")
    for name in ("RMM_OTD_ARCHITECTURE_LOCK.md", "RMM_OTD_Design_Maturity_Report.md"):
        src = EIGEN / "docs" / name
        if src.is_file():
            shutil.copy2(src, out / "docs" / name)

    return p, out


def _stage_eigen_assets(out: Path, d: dict) -> None:
    sheets = out / "sheets"
    fab = out / "fab"
    renders = out / "renders"
    mesh = out / "meshes"
    for d_ in (sheets, fab, renders, mesh):
        d_.mkdir(exist_ok=True)

    # 2D drawing package
    src_dwg = EIGEN / "docs" / "rmm_otd_drawings"
    if src_dwg.is_dir():
        for f in src_dwg.iterdir():
            if not f.is_file():
                continue
            if f.name.startswith("MB-OTD-FAB"):
                shutil.copy2(f, fab / f.name)
            elif f.suffix.lower() in {".png", ".dxf", ".pdf", ".md"}:
                shutil.copy2(f, sheets / f.name)

    # Product + OpenSCAD renders
    for src in (
        EIGEN / "docs" / "renders" / "rmm_otd",
        EIGEN / "cad" / "openscad" / "renders",
    ):
        if src.is_dir():
            for f in src.iterdir():
                if f.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                    shutil.copy2(f, renders / f.name)

    # High-fidelity STLs (cascade components)
    stl_src = EIGEN / "docs" / "rmm_otd_studio" / "step_refs"
    if stl_src.is_dir():
        for f in stl_src.glob("*.stl"):
            shutil.copy2(f, mesh / f.name)

    # Cascade fusion params for traceability
    params = EIGEN / "cad" / "fusion" / "rmm_otd_cascade_fusion_params.json"
    if params.is_file():
        shutil.copy2(params, out / "rmm_otd_cascade_fusion_params.json")
    basis = EIGEN / "cad" / "design_basis" / "rmm_otd_cascade_basis.json"
    if basis.is_file():
        shutil.copy2(basis, out / "rmm_otd_cascade_basis.json")


def _write_gallery_html(out: Path, d: dict, manifest: dict) -> Path:
    """Single-page gallery: hero + 2D sheets + 3D links + performance."""
    def imgs(folder: Path, glob: str = "*") -> list[Path]:
        if not folder.is_dir():
            return []
        files = []
        for pat in ("*.png", "*.jpg", "*.jpeg"):
            files.extend(folder.glob(pat))
        return sorted(files, key=lambda p: p.name.lower())

    hero = out / "renders" / "product_hero.jpg"
    if not hero.is_file():
        for c in ("cascade_section.png", "hero.jpg", "cutaway.jpg", "section.jpg"):
            if (out / "renders" / c).is_file():
                hero = out / "renders" / c
                break

    sheet_pngs = [p for p in imgs(out / "sheets") if p.suffix.lower() == ".png"]
    fab_pngs = [p for p in imgs(out / "fab") if p.suffix.lower() == ".png"]
    render_pngs = imgs(out / "renders")

    def cards(paths: list[Path], rel_prefix: str) -> str:
        bits = []
        for p in paths:
            rel = f"{rel_prefix}/{p.name}".replace("\\", "/")
            bits.append(
                f'<figure class="card"><a href="{rel}" target="_blank">'
                f'<img src="{rel}" alt="{p.stem}" loading="lazy"/>'
                f"</a><figcaption>{p.stem}</figcaption></figure>"
            )
        return "\n".join(bits) if bits else "<p class='muted'>No images found.</p>"

    has_step = (out / "model.step").is_file()
    has_gltf = (out / "model.gltf").is_file()
    has_viewer = (out / "viewer3d.html").is_file()
    mesh_list = sorted((out / "meshes").glob("*.stl")) if (out / "meshes").is_dir() else []

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MB-OTD RMM-OTD — Gallery</title>
<style>
  :root {{
    --bg: #0b0d10; --panel: #141a22; --text: #e8eef6; --muted: #8b9bb0;
    --accent: #3d9cf0; --warn: #e0a84a; --ok: #5dce8a; --border: #243041;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.45;
  }}
  header {{
    padding: 1.5rem 2rem; border-bottom: 1px solid var(--border);
    background: linear-gradient(180deg, #121820, var(--bg));
  }}
  h1 {{ margin: 0 0 0.35rem; font-size: 1.6rem; }}
  .badge {{
    display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px;
    background: #3a2a12; color: var(--warn); font-size: 0.8rem; font-weight: 600;
  }}
  .meta {{ color: var(--muted); font-size: 0.95rem; max-width: 70ch; }}
  nav {{
    display: flex; flex-wrap: wrap; gap: 0.6rem; padding: 1rem 2rem;
    border-bottom: 1px solid var(--border); position: sticky; top: 0;
    background: rgba(11,13,16,0.92); backdrop-filter: blur(8px); z-index: 5;
  }}
  nav a {{
    color: var(--accent); text-decoration: none; padding: 0.35rem 0.7rem;
    border: 1px solid var(--border); border-radius: 8px; font-size: 0.9rem;
  }}
  nav a:hover {{ background: var(--panel); }}
  section {{ padding: 1.5rem 2rem; border-bottom: 1px solid var(--border); }}
  h2 {{ margin: 0 0 1rem; font-size: 1.2rem; color: #c5d4e8; }}
  .hero {{
    width: 100%; max-height: 70vh; object-fit: contain; background: #000;
    border: 1px solid var(--border); border-radius: 12px;
  }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 1rem;
  }}
  .card {{
    margin: 0; background: var(--panel); border: 1px solid var(--border);
    border-radius: 10px; overflow: hidden;
  }}
  .card img {{ width: 100%; height: 180px; object-fit: contain; background: #0a0a0a; display: block; }}
  .card figcaption {{
    padding: 0.45rem 0.6rem; font-size: 0.78rem; color: var(--muted);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .stats {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 0.75rem;
  }}
  .stat {{
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 0.8rem 1rem;
  }}
  .stat b {{ display: block; font-size: 1.25rem; color: var(--ok); }}
  .stat span {{ color: var(--muted); font-size: 0.8rem; }}
  .files {{ columns: 2; font-size: 0.9rem; }}
  .files a {{ color: var(--accent); }}
  .muted {{ color: var(--muted); }}
  iframe.viewer {{
    width: 100%; height: 70vh; border: 1px solid var(--border); border-radius: 12px;
    background: #000;
  }}
</style>
</head>
<body>
<header>
  <h1>MB-OTD — RMM-OTD Cascade Module</h1>
  <div class="badge">ENGINEERING ESTIMATE</div>
  <p class="meta">
    Rev C production CAD master · geometry from Eigen <code>rmm_otd_dims.json</code> ·
    llm-bim envelopes (cylinders) + Eigen 2D package + OpenSCAD stills.
    Not fab-release; not [DEMONSTRATED].
  </p>
</header>

<nav>
  <a href="#hero">Hero</a>
  <a href="#stats">Numbers</a>
  <a href="#3d">3D viewer</a>
  <a href="#sheets">2D sheets</a>
  <a href="#fab">FAB sheets</a>
  <a href="#renders">Renders</a>
  <a href="#files">Files</a>
  <a href="viewer3d.html" target="_blank">Open viewer3d</a>
  <a href="index.html">Pack index</a>
</nav>

<section id="hero">
  <h2>Product hero</h2>
  <img class="hero" src="{hero.relative_to(out).as_posix() if hero.is_file() else ''}" alt="RMM-OTD hero"/>
</section>

<section id="stats">
  <h2>Performance (engine-pinned EST)</h2>
  <div class="stats">
    <div class="stat"><b>{d.get('E_kwh', '—')}</b><span>kWh stored</span></div>
    <div class="stat"><b>{d.get('E_use', '—')}</b><span>kWh usable</span></div>
    <div class="stat"><b>{d.get('wh_kg', '—')}</b><span>Wh/kg rotors</span></div>
    <div class="stat"><b>{d.get('v_tip', '—')}</b><span>m/s tip</span></div>
    <div class="stat"><b>{d.get('SF', '—')}</b><span>stress SF</span></div>
    <div class="stat"><b>{d.get('m_rotors', '—')}</b><span>kg rotors</span></div>
  </div>
</section>

<section id="3d">
  <h2>3D model</h2>
  <p class="muted">
    STEP: {'yes' if has_step else 'no'} ·
    glTF: {'yes' if has_gltf else 'no'} ·
    meshes: {len(mesh_list)} STL ·
    <a href="viewer3d.html" target="_blank">viewer3d.html</a>
    {' · <a href="model.step">model.step</a>' if has_step else ''}
    {' · <a href="model.gltf">model.gltf</a>' if has_gltf else ''}
  </p>
  {"<iframe class='viewer' src='viewer3d.html' title='3D viewer'></iframe>" if has_viewer else "<p class='muted'>viewer3d.html not generated</p>"}
</section>

<section id="sheets">
  <h2>2D design sheets ({len(sheet_pngs)})</h2>
  <div class="grid">
    {cards(sheet_pngs, "sheets")}
  </div>
</section>

<section id="fab">
  <h2>FAB sheets ({len(fab_pngs)})</h2>
  <div class="grid">
    {cards(fab_pngs, "fab")}
  </div>
</section>

<section id="renders">
  <h2>Renders / OpenSCAD stills ({len(render_pngs)})</h2>
  <div class="grid">
    {cards(render_pngs, "renders")}
  </div>
</section>

<section id="files">
  <h2>Pack files</h2>
  <div class="files">
    <ul>
      <li><a href="model.step">model.step</a></li>
      <li><a href="model.gltf">model.gltf</a></li>
      <li><a href="model.ifc">model.ifc</a></li>
      <li><a href="model.llmbim.json">model.llmbim.json</a></li>
      <li><a href="MANIFEST.json">MANIFEST.json</a></li>
      <li><a href="rmm_otd_meta.json">rmm_otd_meta.json</a></li>
      <li><a href="boq.json">boq.json</a> (if present)</li>
      <li><a href="docs/rmm_otd_dims.json">geometry master</a></li>
    </ul>
  </div>
  <p class="muted">Built with llm-bim <code>export_deliverables</code> + Eigen SSOT.</p>
</section>
</body>
</html>
"""
    path = out / "gallery.html"
    path.write_text(html, encoding="utf-8")
    return path


def _enhance_index(out: Path, d: dict) -> None:
    idx = out / "index.html"
    banner = (
        f'<div style="padding:12px 16px;background:#1a2330;border-bottom:1px solid #345;'
        f'font-family:system-ui,sans-serif">'
        f'<strong style="color:#e8eef6">RMM-OTD gallery:</strong> '
        f'<a style="color:#6cb6ff" href="gallery.html">Open gallery.html</a> · '
        f'<a style="color:#6cb6ff" href="viewer3d.html">3D viewer</a> · '
        f'E≈{d.get("E_kwh")} kWh · SF={d.get("SF")} · '
        f'<span style="color:#e0a84a">ENGINEERING ESTIMATE</span></div>'
    )
    if idx.is_file():
        text = idx.read_text(encoding="utf-8", errors="replace")
        if "gallery.html" not in text:
            if "<body>" in text:
                text = text.replace("<body>", "<body>\n" + banner, 1)
            else:
                text = banner + text
            idx.write_text(text, encoding="utf-8")
    else:
        idx.write_text(
            f"<!DOCTYPE html><html><head><meta charset='utf-8'/>"
            f"<title>MB-OTD</title></head><body>{banner}"
            f"<p><a href='gallery.html'>gallery</a></p></body></html>",
            encoding="utf-8",
        )


def main() -> None:
    print("=== RMM-OTD llm-bim cascade pack ===")
    print(f"  Eigen: {EIGEN}")
    p, out = build(OUT)
    print(json.dumps({"out": str(out), "stats": p.stats()}, indent=2))
    gallery = out / "gallery.html"
    print(f"\nOpen: {gallery}")
    try:
        webbrowser.open(gallery.resolve().as_uri())
    except Exception as exc:  # noqa: BLE001
        print(f"  (browser open failed: {exc})")


if __name__ == "__main__":
    main()
