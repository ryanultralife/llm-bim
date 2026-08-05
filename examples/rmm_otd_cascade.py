#!/usr/bin/env python3
"""RMM-OTD nested Halbach nest — full llm-bim pack (STEP + 2D + 3D + HTML).

USER LOCK (2026-08-05):
  · Nested CF rotors (inner / middle / outer) — NO magnetic gears, NO CVT gear train
  · Magnetic coupling ONLY between outer↔middle and middle↔inner
  · Halbach arrays sintered / embedded in the carbon-fiber rotors
  · Outer rotor driven AND harvested by stator coils
  · Stator coils live in the exterior shell = vacuum barrier

Source SSOT (Eigen):
  cad/design_basis/rmm_otd_basis.json
  docs/tier4_drawings/rmm_otd/  (nest GA)
  docs/renders/rmm_otd/
  cad/fusion/ step + params

Build:
  set EIGEN_ROOT=...\\Eigen
  python examples/rmm_otd_cascade.py

Outputs:
  examples/output/rmm_otd/
    model.step · model.gltf · model.ifc · gallery.html · viewer3d.html
"""
from __future__ import annotations

import json
import math
import shutil
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "output" / "rmm_otd"

_sib = ROOT.parent / "Eigen"
EIGEN = Path(__import__("os").environ["EIGEN_ROOT"]) if __import__("os").environ.get("EIGEN_ROOT") else (
    _sib if _sib.is_dir() else Path.home() / "Eigen"
)

from llmbim import Project  # noqa: E402

MM = 1000.0


def _load_basis() -> dict:
    candidates = [
        EIGEN / "cad" / "design_basis" / "rmm_otd_basis.json",
        EIGEN / "cad" / "fusion" / "rmm_otd_fusion_params.json",
    ]
    for p in candidates:
        if p.is_file() and p.name.endswith("basis.json"):
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"rmm_otd_basis.json not under {EIGEN}")


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
    z0: float,
    height: float,
    part: str,
    equipment: str = "MB-RMM-OTD",
) -> str:
    return p.create_equipment_box(
        level="Module",
        origin=(0.0, 0.0),
        size=(od, od, height),
        name=name,
        kind=kind,
        shape="cylinder",
        orientation="z",
        centered=True,
        z0_mm=z0,
        id_mm=id_mm,
        equipment=equipment,
        part=part,
    )


def build(out_dir: Path | None = None) -> tuple[Project, Path]:
    out = Path(out_dir) if out_dir else OUT
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    B = _load_basis()
    des = B["design"]
    shells = sorted(B["shells"], key=lambda s: s["r_outer_m"])  # inner → outer
    perf = B.get("performance_est", {})
    det = B.get("cad_detail", {})
    locks = B.get("locks", {})

    L = float(des["length_m"]) * MM
    wall = float(des.get("wall_m", 0.06)) * MM
    # Stand pad under module
    stand_h = 100.0
    z_rotor = stand_h + 40.0  # air gap above pad

    # Housing = vacuum vessel = stator shell (outside outer rotor)
    r_out_max = max(s["r_outer_m"] for s in shells) * MM
    # Prefer fusion params if present
    fp = EIGEN / "cad" / "fusion" / "rmm_otd_fusion_params.json"
    housing_ri = r_out_max + 0.5 * wall
    housing_ro = housing_ri + wall
    if fp.is_file():
        try:
            P = json.loads(fp.read_text(encoding="utf-8")).get("params", {})
            if "housing_ri" in P:
                housing_ri = float(P["housing_ri"])
                housing_ro = float(P["housing_ro"])
                L = float(P.get("rotor_len", L))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    overhang = 40.0
    vessel_h = L + 2 * overhang
    z_vessel = z_rotor - overhang

    p = Project.create("MB-RMM-OTD Nested Halbach Nest", vcs=False)
    p.add_level("Module", 0)

    # --- Stand ---
    pad = max(housing_ro * 2 + 200, 1400.0)
    p.create_equipment_box(
        level="Module",
        origin=(0.0, 0.0),
        size=(pad, pad, stand_h),
        name="Stand pad",
        kind="pedestal",
        centered=True,
        z0_mm=0.0,
        equipment="MB-RMM-OTD",
        part="stand",
    )

    # --- Three nested CF rotors (Halbach integral — shown as CF wall tubes) ---
    roles = {
        0: ("Inner CF Halbach rotor", "rotor_inner", "inner_coupled"),
        1: ("Middle CF Halbach rotor", "rotor_middle", "middle_coupled"),
        2: ("Outer CF Halbach rotor (driven/harvested)", "rotor_outer", "outer_stator"),
    }
    for i, s in enumerate(shells):
        ri = float(s["r_inner_m"]) * MM
        ro = float(s["r_outer_m"]) * MM
        name, part, _ = roles.get(i, (f"Rotor {i}", f"rotor_{i}", "rotor"))
        # Full length nest (equal L)
        _tube(
            p,
            name=name,
            kind="rotor",
            od=ro * 2,
            id_mm=ri * 2,
            z0=z_rotor,
            height=L,
            part=part,
        )
        # Halbach rim band (outer portion of wall) — visual of sintered array
        # rim occupies outer ~f_v of wall radial span
        f_v = float(det.get("magnet_rim", {}).get("f_v_nominal", 0.1))
        t_wall = ro - ri
        r_mag_outer = ro - 5.0  # overwrap class
        r_mag_inner = max(ri + 2.0, r_mag_outer - max(t_wall * (0.25 + f_v), 8.0))
        if r_mag_outer > r_mag_inner + 1.0:
            _tube(
                p,
                name=f"Halbach rim (sintered) — shell {i}",
                kind="magnet",
                od=r_mag_outer * 2,
                id_mm=r_mag_inner * 2,
                z0=z_rotor + 20.0,
                height=L - 40.0,
                part=f"halbach_{part}",
            )

    # --- Vacuum vessel / exterior shell = stator host ---
    _tube(
        p,
        name="Exterior shell (vacuum barrier + stator host)",
        kind="vessel",
        od=housing_ro * 2,
        id_mm=housing_ri * 2,
        z0=z_vessel,
        height=vessel_h,
        part="vacuum_vessel_stator_shell",
    )

    # --- Stator coils in the shell wall (drive + harvest outer rotor only) ---
    coil_h = L * 0.85
    coil_z0 = z_rotor + (L - coil_h) / 2
    n_seg = int(det.get("stator", {}).get("n_segments", 6))
    _tube(
        p,
        name=f"Stator coils in vacuum shell ({n_seg} seg) — drive & harvest outer",
        kind="stator",
        od=housing_ro * 2 - 4.0,
        id_mm=housing_ri * 2 + 8.0,
        z0=coil_z0,
        height=coil_h,
        part="stator_coils_shell",
    )

    # --- End caps / vacuum heads ---
    cap_thk = 40.0
    cap_od = housing_ro * 2 + 20.0
    for name, z0, part in (
        ("Bottom vacuum head", z_vessel - cap_thk, "head_bottom"),
        ("Top vacuum head", z_vessel + vessel_h, "head_top"),
    ):
        _tube(
            p,
            name=name,
            kind="cap",
            od=cap_od,
            id_mm=None,
            z0=z0,
            height=cap_thk,
            part=part,
        )

    # --- Magnetic coupling air-gap annotations as thin free-span (visual only) ---
    # Gaps between shells — empty space, no gear bodies
    for i in range(len(shells) - 1):
        r_out_inner = float(shells[i]["r_outer_m"]) * MM
        r_in_outer = float(shells[i + 1]["r_inner_m"]) * MM
        gap = r_in_outer - r_out_inner
        # label slab ring at mid height for plan readability only
        if gap > 1.0:
            mid_r = 0.5 * (r_out_inner + r_in_outer)
            p.create_slab(
                level="Module",
                polygon=_circle(0, 0, mid_r, n=32),
                thickness_mm=1.0,
                name=f"Magnetic coupling gap {i}↔{i+1} (~{gap:.0f} mm radial)",
            )

    # Outer rotor OD silhouette
    p.create_slab(
        level="Module",
        polygon=_circle(0, 0, r_out_max, n=48),
        thickness_mm=2.0,
        name="Outer rotor OD plan silhouette",
    )
    p.create_slab(
        level="Module",
        polygon=_circle(0, 0, housing_ro, n=48),
        thickness_mm=2.0,
        name="Vacuum vessel OD plan silhouette",
    )

    clear = housing_ro * 2 + 500
    p.create_room(
        level="Module",
        name="RMM-OTD nested module envelope",
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
        p.commit("RMM-OTD nested Halbach nest — magnetic couple only, stator=vessel")
    except ValueError as exc:
        print(f"  [commit] {exc}")

    manifest = p.export_deliverables(
        out,
        mode="part",
        plan_level="Module",
        plan_scale=0.18,
        set_type="construction",
    )

    _stage_assets(out)
    _hero(out)
    def _cards(paths: list[Path], prefix: str) -> str:
        bits = []
        for pth in paths:
            rel = f"{prefix}/{pth.name}"
            bits.append(
                f'<figure class="card"><a href="{rel}" target="_blank">'
                f'<img src="{rel}" alt="{pth.stem}" loading="lazy"/></a>'
                f"<figcaption>{pth.stem}</figcaption></figure>"
            )
        return "\n".join(bits) or "<p class='meta'>None</p>"

    def _imgs(folder: Path) -> list[Path]:
        if not folder.is_dir():
            return []
        files: list[Path] = []
        for pat in ("*.png", "*.jpg", "*.jpeg"):
            files.extend(folder.glob(pat))
        return sorted(files, key=lambda x: x.name.lower())

    hero = out / "renders" / "product_hero.jpg"
    if not hero.is_file():
        for c in ("hero.jpg", "cutaway.jpg", "section.jpg", "MB-RMM-OTD-GA-001.png"):
            if (out / "renders" / c).is_file():
                hero = out / "renders" / c
                break
            if (out / "sheets" / c).is_file():
                hero = out / "sheets" / c
                break
    sheet_pngs = [x for x in _imgs(out / "sheets") if x.suffix.lower() == ".png"]
    render_pngs = _imgs(out / "renders")
    gallery = out / "gallery.html"
    gallery.write_text(
        _gallery_html_clean(
            out, hero, sheet_pngs, render_pngs, shells, housing_ri, housing_ro, L,
            locks, perf,
            (out / "model.step").is_file(),
            (out / "model.gltf").is_file(),
            (out / "viewer3d.html").is_file(),
            _cards,
        ),
        encoding="utf-8",
    )
    _enhance_index(out, perf)

    meta = {
        "project": "MB-RMM-OTD Nested Halbach Nest",
        "honesty": "ENGINEERING ESTIMATE",
        "architecture_lock": "docs/RMM_OTD_ARCHITECTURE_LOCK.md",
        "locks_user": {
            "nested_rotors": True,
            "magnetic_coupling_only": True,
            "no_gears": True,
            "no_cvt_gears": True,
            "halbach_in_cf_rotors": True,
            "outer_driven_and_harvested_by_shell_stator": True,
            "shell_is_vacuum_barrier": True,
        },
        "basis": str(EIGEN / "cad" / "design_basis" / "rmm_otd_basis.json"),
        "shells_mm": [
            {
                "index": i,
                "ri": float(s["r_inner_m"]) * MM,
                "ro": float(s["r_outer_m"]) * MM,
                "L": L,
                "role": s.get("role"),
                "mass_kg": s.get("mass_kg"),
            }
            for i, s in enumerate(shells)
        ],
        "vessel_mm": {"ri": housing_ri, "ro": housing_ro, "L": vessel_h},
        "performance_est": perf,
        "stats": p.stats(),
        "deliverables": manifest,
        "gallery": str(gallery),
    }
    (out / "rmm_otd_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (out / "docs").mkdir(exist_ok=True)
    shutil.copy2(
        EIGEN / "cad" / "design_basis" / "rmm_otd_basis.json",
        out / "docs" / "rmm_otd_basis.json",
    )
    lock = EIGEN / "docs" / "RMM_OTD_ARCHITECTURE_LOCK.md"
    if lock.is_file():
        shutil.copy2(lock, out / "docs" / lock.name)

    return p, out


def _stage_assets(out: Path) -> None:
    sheets = out / "sheets"
    renders = out / "renders"
    for d in (sheets, renders):
        d.mkdir(exist_ok=True)

    # Nest GA (tier4) — correct architecture drawings
    nest_ga = EIGEN / "docs" / "tier4_drawings" / "rmm_otd"
    if nest_ga.is_dir():
        for f in nest_ga.iterdir():
            if f.is_file() and f.suffix.lower() in {".png", ".dxf", ".pdf"}:
                shutil.copy2(f, sheets / f.name)

    # Product renders (nest heroes — not geared cascade stills as authority)
    for src in (
        EIGEN / "docs" / "renders" / "rmm_otd",
    ):
        if src.is_dir():
            for f in src.iterdir():
                if f.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                    shutil.copy2(f, renders / f.name)

    # Optional: only nest-relevant OpenSCAD stills if named nested_*
    osc = EIGEN / "cad" / "openscad" / "renders"
    if osc.is_dir():
        for f in osc.iterdir():
            if f.suffix.lower() not in {".png", ".jpg"}:
                continue
            n = f.name.lower()
            # Prefer nested / exclude cascade gear marketing as primary
            if n.startswith("nested") or "section" in n or "m60" in n:
                shutil.copy2(f, renders / f.name)

    for name in (
        "rmm_otd_fusion_params.json",
        "rmm_otd_fusion_massprops.json",
    ):
        s = EIGEN / "cad" / "fusion" / name
        if s.is_file():
            shutil.copy2(s, out / name)


def _hero(out: Path) -> None:
    try:
        from llmbim_drawings.hero_product import export_hero_pipeline, stage_hero_render

        export_hero_pipeline(
            out,
            product_id="rmm_otd",
            kind="device",
            title="RMM-OTD nested Halbach mechanical battery",
            use_library=True,
        )
        for cand in (
            out / "renders" / "hero.jpg",
            out / "renders" / "cutaway.jpg",
            out / "renders" / "section.jpg",
            out / "renders" / "MB-RMM-OTD-GA-001.png",
            out / "sheets" / "MB-RMM-OTD-GA-001.png",
        ):
            if cand.is_file():
                stage_hero_render(out, cand)
                break
    except Exception as exc:  # noqa: BLE001
        print(f"  [hero] {exc}")


def _gallery_html_clean(
    out, hero, sheet_pngs, render_pngs, shells, housing_ri, housing_ro, L,
    locks, perf, has_step, has_gltf, has_viewer, cards_fn,
) -> str:
    def fv(key, nd=2):
        v = perf.get(key)
        if isinstance(v, (int, float)):
            return f"{v:.{nd}f}"
        return "—"

    shell_rows = "".join(
        f"<tr><td>{i}</td><td>{s.get('role','')}</td>"
        f"<td>{s['r_inner_m']*1000:.0f}</td><td>{s['r_outer_m']*1000:.0f}</td>"
        f"<td>{float(s.get('mass_kg',0)):.1f}</td></tr>"
        for i, s in enumerate(shells)
    )
    lock_lis = "".join(f"<li><code>{k}</code> — {v}</li>" for k, v in locks.items())
    hero_src = hero.relative_to(out).as_posix() if hero.is_file() else ""
    iframe = (
        "<iframe class='viewer' src='viewer3d.html' title='3D'></iframe>"
        if has_viewer else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>MB-RMM-OTD Nested Halbach Nest</title>
<style>
:root {{ --bg:#0b0d10; --panel:#141a22; --text:#e8eef6; --muted:#8b9bb0;
  --accent:#3d9cf0; --warn:#e0a84a; --ok:#5dce8a; --border:#243041; --bad:#e07070; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Segoe UI,system-ui,sans-serif; background:var(--bg); color:var(--text); }}
header {{ padding:1.5rem 2rem; border-bottom:1px solid var(--border);
  background:linear-gradient(180deg,#121820,var(--bg)); }}
h1 {{ margin:0 0 .4rem; font-size:1.55rem; }}
.badge {{ display:inline-block; padding:.15rem .55rem; border-radius:999px;
  background:#3a2a12; color:var(--warn); font-size:.8rem; font-weight:600; margin:.15rem .25rem .15rem 0; }}
.badge.ok {{ background:#14301f; color:var(--ok); }}
.badge.no {{ background:#3a1515; color:var(--bad); }}
.meta {{ color:var(--muted); max-width:75ch; }}
nav {{ display:flex; flex-wrap:wrap; gap:.55rem; padding:1rem 2rem; position:sticky; top:0;
  background:rgba(11,13,16,.94); border-bottom:1px solid var(--border); z-index:5; }}
nav a {{ color:var(--accent); text-decoration:none; padding:.35rem .7rem;
  border:1px solid var(--border); border-radius:8px; font-size:.9rem; }}
section {{ padding:1.4rem 2rem; border-bottom:1px solid var(--border); }}
h2 {{ margin:0 0 .9rem; font-size:1.15rem; color:#c5d4e8; }}
.hero {{ width:100%; max-height:70vh; object-fit:contain; background:#000;
  border:1px solid var(--border); border-radius:12px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:1rem; }}
.card {{ margin:0; background:var(--panel); border:1px solid var(--border); border-radius:10px; overflow:hidden; }}
.card img {{ width:100%; height:180px; object-fit:contain; background:#0a0a0a; display:block; }}
.card figcaption {{ padding:.45rem .6rem; font-size:.78rem; color:var(--muted); }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:.75rem; }}
.stat {{ background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:.8rem 1rem; }}
.stat b {{ display:block; font-size:1.2rem; color:var(--ok); }}
.stat span {{ color:var(--muted); font-size:.8rem; }}
table {{ border-collapse:collapse; width:100%; max-width:720px; font-size:.92rem; }}
th,td {{ border:1px solid var(--border); padding:.4rem .55rem; text-align:left; }}
th {{ background:var(--panel); color:var(--muted); }}
iframe.viewer {{ width:100%; height:70vh; border:1px solid var(--border); border-radius:12px; background:#000; }}
ul.locks {{ color:var(--muted); }}
code {{ color:#9ecbff; }} a {{ color:var(--accent); }}
</style></head><body>
<header>
  <h1>MB-RMM-OTD — Nested Halbach Nest</h1>
  <span class="badge">ENGINEERING ESTIMATE</span>
  <span class="badge ok">NESTED ROTORS</span>
  <span class="badge ok">MAGNETIC COUPLE ONLY</span>
  <span class="badge no">NO GEARS</span>
  <span class="badge ok">STATOR = VACUUM SHELL</span>
  <p class="meta">
    Three coaxial CF rotors with <strong>Halbach arrays sintered into the rotors</strong>.
    <strong>Magnetic coupling only</strong> between outer↔middle↔inner (no contact, no gears).
    <strong>Outer rotor</strong> is driven and harvested by <strong>stator coils in the exterior shell</strong>,
    which is also the <strong>vacuum barrier</strong>.
  </p>
</header>
<nav>
  <a href="#hero">Hero</a><a href="#arch">Architecture</a><a href="#stats">Numbers</a>
  <a href="#3d">3D</a><a href="#sheets">2D</a><a href="#renders">Renders</a>
  <a href="viewer3d.html" target="_blank">viewer3d</a>
  <a href="model.step">STEP</a><a href="index.html">index</a>
</nav>
<section id="hero"><h2>Product hero</h2>
<img class="hero" src="{hero_src}" alt="RMM-OTD hero"/></section>
<section id="arch"><h2>Architecture (user lock)</h2>
<ul class="locks">
<li>Nested rotors only (inner / middle / outer)</li>
<li>Magnetic coupling only between shells — <strong>no gears, no CVT gear train</strong></li>
<li>Halbach arrays sintered into CF rotor walls</li>
<li>Outer rotor driven <em>and</em> harvested by shell stator coils</li>
<li>Exterior shell = vacuum barrier = stator host</li>
</ul>
<h3>Design locks</h3><ul class="locks">{lock_lis or "<li>See rmm_otd_basis.json</li>"}</ul>
<h3>Shells (mm)</h3>
<table><tr><th>#</th><th>Role</th><th>r_i</th><th>r_o</th><th>mass kg</th></tr>
{shell_rows}</table>
<p class="meta">Vessel/stator shell: ID {housing_ri*2:.0f} mm · OD {housing_ro*2:.0f} mm · rotor L {L:.0f} mm</p>
</section>
<section id="stats"><h2>Performance EST</h2>
<div class="stats">
<div class="stat"><b>{fv('E_kWh')}</b><span>kWh</span></div>
<div class="stat"><b>{fv('mass_kg',0)}</b><span>kg rotors</span></div>
<div class="stat"><b>{fv('tip_speed_m_s',0)}</b><span>m/s tip</span></div>
<div class="stat"><b>{fv('stress_SF')}</b><span>hoop SF</span></div>
<div class="stat"><b>{fv('B_combined_est_T',2)}</b><span>T combined EST</span></div>
</div></section>
<section id="3d"><h2>3D nest envelopes</h2>
<p class="meta">STEP {'yes' if has_step else 'no'} · glTF {'yes' if has_gltf else 'no'} ·
<a href="viewer3d.html" target="_blank">viewer3d.html</a>
{' · <a href="model.step">model.step</a>' if has_step else ''}
{' · <a href="model.gltf">model.gltf</a>' if has_gltf else ''}</p>
{iframe}
<p class="meta">Empty radial gaps = magnetic coupling. No gear solids. Stator band is in the vacuum shell wall around the outer rotor only.</p>
</section>
<section id="sheets"><h2>2D nest drawings ({len(sheet_pngs)})</h2>
<div class="grid">{cards_fn(sheet_pngs, "sheets")}</div></section>
<section id="renders"><h2>Renders ({len(render_pngs)})</h2>
<div class="grid">{cards_fn(render_pngs, "renders")}</div></section>
</body></html>
"""


def _enhance_index(out: Path, perf: dict) -> None:
    idx = out / "index.html"
    e = perf.get("E_kWh", "—")
    banner = (
        f'<div style="padding:12px 16px;background:#1a2330;border-bottom:1px solid #345;'
        f'font-family:system-ui,sans-serif;color:#e8eef6">'
        f'<strong>RMM-OTD nested nest (NO GEARS)</strong> — '
        f'<a style="color:#6cb6ff" href="gallery.html">gallery.html</a> · '
        f'<a style="color:#6cb6ff" href="viewer3d.html">3D</a> · '
        f'E≈{e} kWh · outer driven/harvested by shell stator · '
        f'<span style="color:#e0a84a">ENGINEERING ESTIMATE</span></div>'
    )
    if idx.is_file():
        text = idx.read_text(encoding="utf-8", errors="replace")
        if "gallery.html" not in text or "NO GEARS" not in text:
            if "<body>" in text:
                text = text.replace("<body>", "<body>\n" + banner, 1)
            else:
                text = banner + text
            idx.write_text(text, encoding="utf-8")
    else:
        idx.write_text(
            f"<!DOCTYPE html><html><body>{banner}"
            f"<p><a href='gallery.html'>gallery</a></p></body></html>",
            encoding="utf-8",
        )


def main() -> None:
    print("=== RMM-OTD nested Halbach nest (no gears) ===")
    print(f"  Eigen: {EIGEN}")
    p, out = build(OUT)
    print(json.dumps({"out": str(out), "stats": p.stats()}, indent=2))
    gal = out / "gallery.html"
    print(f"\nOpen: {gal}")
    try:
        webbrowser.open(gal.resolve().as_uri())
    except Exception as exc:  # noqa: BLE001
        print(f"  browser: {exc}")


if __name__ == "__main__":
    main()
