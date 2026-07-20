"""SCHAD construction-worthy project package — one command.

Builds:
  1. Note-driven CD sheets + details (plans, elevs, sections, MEP, S-details)
  2. Full structural + MEP engineering package (calcs, schedules, CSV)
  3. BOM takeoff (CSI tables)
  4. Specs / open questions / house phase 2
  5. Optional llm-bim 3D model pack (if kernel importable)
  6. PDF plot set of sheets (llm-bim pdf_binder)

Output: output/schad_construction/

  python projects/schad/build_construction_set.py
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import bom_takeoff
import build_notes_cd
import engineering_package
import generate_schad_docs as docs
import schad_design_basis as basis
import schad_structural as struct


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _try_llmbim_model(out: Path) -> dict:
    """Build coordination 3D model into out/model/ if llmbim available."""
    result = {"ok": False, "reason": ""}
    try:
        # Prefer in-repo example if present
        ex = _ROOT / "examples" / "schad_garage.py"
        if not ex.is_file():
            result["reason"] = "examples/schad_garage.py missing"
            return result
        # Run build into model subdir by importing
        sys.path.insert(0, str(_ROOT / "examples"))
        # Load as path
        import importlib.util

        spec = importlib.util.spec_from_file_location("schad_garage", ex)
        if spec is None or spec.loader is None:
            result["reason"] = "cannot load schad_garage"
            return result
        mod = importlib.util.module_from_spec(spec)
        # Ensure SCHAD basis finds projects/schad
        import os

        os.environ.setdefault("SCHAD_ROOT", str(_HERE))
        spec.loader.exec_module(mod)
        model_out = out / "model_3d"
        mod.build_schad(model_out, schad_root=_HERE)
        result["ok"] = True
        result["dir"] = str(model_out.resolve())
        result["viewer"] = str((model_out / "viewer3d.html").resolve())
    except Exception as e:
        result["reason"] = f"{type(e).__name__}: {e}"
    return result


def _try_pdf(sheets_dir: Path, out_pdf: Path) -> dict:
    result = {"ok": False}
    try:
        from llmbim_drawings.pdf_binder import export_pdf_binder

        export_pdf_binder(
            sheets_dir,
            out_pdf,
            pattern="*.svg",
            title="SCHAD 2024-008 Construction Set (Design Development)",
        )
        result["ok"] = True
        result["path"] = str(out_pdf.resolve())
    except Exception as e:
        result["reason"] = f"{type(e).__name__}: {e}"
    return result


def build(out: Path | None = None) -> Path:
    out = Path(out or _ROOT / "output" / "schad_construction")
    if out.exists():
        # clean rebuild of generated dirs only
        for sub in ("sheets", "details", "docs", "engineering", "bom", "model_3d"):
            p = out / sub
            if p.is_dir():
                shutil.rmtree(p)
    out.mkdir(parents=True, exist_ok=True)

    print("=== 1/6 Note-driven CD sheets + details ===")
    notes_tmp = out / "_notes_build"
    build_notes_cd.build(notes_tmp)
    # promote into construction root
    for name in ("sheets", "details", "docs"):
        src = notes_tmp / name
        if src.is_dir():
            if (out / name).exists():
                shutil.rmtree(out / name)
            shutil.copytree(src, out / name)
    for f in ("index.html", "MANIFEST.json", "SCHAD_SSOT_SNAPSHOT.json"):
        if (notes_tmp / f).is_file():
            shutil.copy2(notes_tmp / f, out / f)
    shutil.rmtree(notes_tmp, ignore_errors=True)

    print("=== 2/6 Engineering package ===")
    eng_dir = out / "engineering"
    eng_paths = engineering_package.write_engineering(eng_dir)
    # also classic docs
    for name, gen in (
        ("STRUCTURAL_CALCS.md", docs.structural_doc),
        ("MEP_CALCS.md", docs.mep_doc),
        ("SPECIFICATIONS.md", docs.spec_doc),
    ):
        _write(out / "docs" / name, "\n".join(gen()) + "\n")

    print("=== 3/6 BOM takeoff ===")
    bom_paths = bom_takeoff.write_bom(out / "bom")

    print("=== 4/6 Project data book ===")
    s = basis.build_scalars()
    eng = engineering_package.engineering_json()
    book = {
        "project": {
            "number": "2024-008",
            "name": "SCHAD Garage / ADU / Workshop",
            "address": "3730 Chandler Rd, Quincy, CA 95971",
            "apn": "005-350-001-000",
            "owner": "Joey & Karen Schad",
            "contractor": "Ledger Built LLC",
            "designer": "Ryan Vukich",
            "status": "[DESIGN DEVELOPMENT — engineering complete for review; PE seal pending]",
        },
        "areas_sf": {
            "total": s["area_total"],
            "garage": s["area_garage"],
            "adu": s["area_adu"],
            "workshop": s["area_workshop"],
            "mechbath": 108.0,
        },
        "structural_ok": eng["all_structural_ok"],
        "checks": {
            "beam_dcr": eng["beam"]["DCR"],
            "post_dcr": eng["post"]["DCR"],
            "lateral_dcr": eng["lateral"]["DCR"],
            "strip_q_psf": eng["strip_footing"]["q_psf"],
        },
        "deferred_submittals": [
            "Roof truss fabricator sealed package",
            "Simpson SSW final anchorage / hold-downs (EOR)",
            "Geotechnical report",
            "Site-specific seismic SDS + wind exposure",
            "Title 24 energy forms",
            "Survey + Q-SETBACK zoning confirmation",
        ],
        "open_questions": [
            q for q in basis.open_questions() if q.get("status") not in ("resolved",)
        ],
        "generated": datetime.now(timezone.utc).isoformat(),
        "disclaimer": engineering_package.DISCLAIMER,
    }
    _write(out / "PROJECT_DATA_BOOK.json", json.dumps(book, indent=2, default=str))

    # Construction readiness checklist
    checklist = [
        "# SCHAD Construction Package Readiness Checklist",
        "",
        f"> {engineering_package.DISCLAIMER}",
        "",
        "## Package contents (this build)",
        "",
        "- [x] Architectural plans (floor, ADU, elevs, section)",
        "- [x] Site plan (GIS-derived — survey required)",
        "- [x] Foundation plan + rebar schedule",
        "- [x] Roof framing plan + deferred truss note",
        "- [x] Structural details D01–D12",
        "- [x] Door/window/header/wall type/SSW schedules",
        "- [x] MEP plans E/P/M + calcs",
        "- [x] Structural engineering package (DCRs, connections, rebar)",
        "- [x] MEP engineering package (service, radiant, propane)",
        "- [x] CSI outline specifications",
        "- [x] BOM quantity takeoff",
        "- [x] 3D coordination model (if kernel available)",
        "",
        "## Structural design-support status",
        "",
        f"- Beam DCR: **{eng['beam']['DCR']}** → {'OK' if eng['beam']['ok'] else 'NG'}",
        f"- Post DCR: **{eng['post']['DCR']}** → {'OK' if eng['post']['ok'] else 'NG'}",
        f"- Lateral DCR: **{eng['lateral']['DCR']}** → {'OK' if eng['lateral']['ok'] else 'NG'}",
        f"- All primary checks OK: **{eng['all_structural_ok']}**",
        "",
        "## Required before BUILDING PERMIT / construction",
        "",
        "### Human / PE / AHJ",
        "- [ ] Licensed Structural Engineer review + stamp",
        "- [ ] Geotech report (bearing, frost, seismic site class)",
        "- [ ] Survey + setback confirmation (Q-SETBACK)",
        "- [ ] Truss shop drawings + calcs (deferred)",
        "- [ ] Title 24 energy documentation",
        "- [ ] Owner close Q-WIN / Q-LOC / finishes (HANDOFF-10)",
        "- [ ] Building department intake",
        "",
        "### Field",
        "- [ ] Locate well, septic, propane tank",
        "- [ ] Verify existing utilities / easements",
        "",
        "## How to rebuild",
        "",
        "```",
        "python projects/schad/build_construction_set.py",
        "```",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
    ]
    _write(out / "CONSTRUCTION_READINESS.md", "\n".join(checklist) + "\n")

    print("=== 5/6 llm-bim 3D model (optional) ===")
    model_result = _try_llmbim_model(out)
    print("  model:", model_result)

    print("=== 6/6 PDF plot set ===")
    pdf_result = _try_pdf(out / "sheets", out / "SCHAD_PLOT_SET.pdf")
    print("  pdf:", pdf_result)

    # Master index
    sheet_links = ""
    if (out / "sheets").is_dir():
        for p in sorted((out / "sheets").glob("*.svg")):
            sheet_links += f'<li><a href="sheets/{p.name}">{p.name}</a></li>\n'
    det_links = ""
    if (out / "details").is_dir():
        for p in sorted((out / "details").glob("*.svg")):
            det_links += f'<li><a href="details/{p.name}">{p.name}</a></li>\n'

    index = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>SCHAD 2024-008 Construction Package</title>
<style>
:root {{ --ink:#111; --muted:#555; --bg:#f4f1ea; --card:#fff; --accent:#8b1a1a; }}
body {{ font-family: "Segoe UI", system-ui, sans-serif; margin:0; background:var(--bg); color:var(--ink); }}
header {{ background:#1a1a1a; color:#fff; padding:1.5rem 2rem; }}
header h1 {{ margin:0 0 0.3rem; font-size:1.6rem; }}
header p {{ margin:0; opacity:0.85; }}
main {{ padding:1.5rem 2rem 3rem; max-width:1200px; }}
.badge {{ display:inline-block; background:var(--accent); color:#fff; padding:0.25rem 0.6rem; font-weight:700; font-size:0.85rem; }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-top:1rem; }}
.card {{ background:var(--card); border:1px solid #ddd; padding:1rem 1.2rem; border-radius:4px; }}
.card h2 {{ margin-top:0; font-size:1.1rem; border-bottom:1px solid #eee; padding-bottom:0.4rem; }}
ul {{ margin:0.4rem 0; padding-left:1.2rem; }}
a {{ color:#0b57d0; }}
.ok {{ color:#0a0; font-weight:700; }}
.warn {{ color:var(--accent); font-weight:700; }}
pre {{ background:#f0f0f0; padding:0.8rem; overflow:auto; font-size:0.85rem; }}
@media (max-width:800px) {{ .grid {{ grid-template-columns:1fr; }} }}
</style></head><body>
<header>
  <h1>SCHAD 2024-008 — Construction Package</h1>
  <p>Garage / ADU / Workshop · 3730 Chandler Rd, Quincy CA · Ledger Built LLC</p>
  <p style="margin-top:0.5rem"><span class="badge">DESIGN DEVELOPMENT — PE SEAL PENDING — NOT FOR CONSTRUCTION</span></p>
</header>
<main>
<p>Full project package generated from pure SSOT + engineering modules.
Areas: <strong>{s['area_total']:.0f} SF</strong> total
(garage {s['area_garage']:.0f} · ADU {s['area_adu']:.0f} · workshop {s['area_workshop']:.0f}).</p>

<div class="grid">
  <div class="card">
    <h2>Engineering status</h2>
    <p>Primary structural checks:
      <span class="{'ok' if eng['all_structural_ok'] else 'warn'}">
        {'ALL OK (design-support)' if eng['all_structural_ok'] else 'REVIEW REQUIRED'}
      </span>
    </p>
    <ul>
      <li>Beam DCR {eng['beam']['DCR']}</li>
      <li>Post DCR {eng['post']['DCR']}</li>
      <li>Lateral DCR {eng['lateral']['DCR']}</li>
      <li>Strip q {eng['strip_footing']['q_psf']} psf</li>
    </ul>
    <p><a href="engineering/STRUCTURAL_ENGINEERING.md">Structural Engineering Package</a><br/>
    <a href="engineering/MEP_ENGINEERING.md">MEP Engineering Package</a><br/>
    <a href="engineering/engineering_data.json">engineering_data.json</a></p>
  </div>
  <div class="card">
    <h2>Deliverables</h2>
    <ul>
      <li><a href="CONSTRUCTION_READINESS.md">Construction readiness checklist</a></li>
      <li><a href="docs/SPECIFICATIONS.md">Specifications (CSI)</a></li>
      <li><a href="bom/BOM_TAKEOFF.md">BOM / quantity takeoff</a></li>
      <li><a href="PROJECT_DATA_BOOK.json">Project data book</a></li>
      <li>{"<a href='SCHAD_PLOT_SET.pdf'>PLOT SET PDF</a>" if pdf_result.get("ok") else "PDF: " + pdf_result.get("reason","n/a")}</li>
      <li>{"<a href='model_3d/viewer3d.html'>3D model viewer</a>" if model_result.get("ok") else "3D model: " + model_result.get("reason","n/a")}</li>
    </ul>
  </div>
  <div class="card">
    <h2>Drawing sheets</h2>
    <ul>{sheet_links}</ul>
  </div>
  <div class="card">
    <h2>Details D01–D12</h2>
    <ul>{det_links}</ul>
  </div>
</div>

<div class="card" style="margin-top:1rem">
  <h2>Structural calc summary</h2>
  <pre>{chr(10).join(struct.calc_summary())}</pre>
</div>

<p style="margin-top:1.5rem;color:var(--muted);font-size:0.9rem">
Rebuild: <code>python projects/schad/build_construction_set.py</code> ·
Generated {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
</p>
</main></body></html>
"""
    _write(out / "index.html", index)

    manifest = {
        "ok": True,
        "kind": "schad_construction_package",
        "output_dir": str(out.resolve()),
        "index": str((out / "index.html").resolve()),
        "structural_ok": eng["all_structural_ok"],
        "pdf": pdf_result,
        "model_3d": model_result,
        "engineering": {k: str(v) for k, v in eng_paths.items()},
        "bom": {k: str(v) for k, v in bom_paths.items()},
        "generated": datetime.now(timezone.utc).isoformat(),
        "status": "DESIGN_DEVELOPMENT_PE_PENDING",
    }
    _write(out / "MANIFEST.json", json.dumps(manifest, indent=2))

    print()
    print("SCHAD_CONSTRUCTION_PACKAGE", out.resolve())
    print("OPEN_INDEX", (out / "index.html").resolve())
    if pdf_result.get("ok"):
        print("OPEN_PDF", pdf_result["path"])
    if model_result.get("ok"):
        print("OPEN_3D", model_result.get("viewer"))
    print("STRUCTURAL_OK", eng["all_structural_ok"])
    return out


def main() -> int:
    try:
        build()
    except Exception as e:
        print("ERROR", type(e).__name__, e, file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
