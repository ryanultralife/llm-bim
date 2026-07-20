"""Build a full note-driven Schad CD pack WITHOUT llm-bim kernel geometry.

Uses only projects/schad SSOT (design_basis, details, structural, mep, site,
adu, house). Output: output/schad_notes_cd/

  python projects/schad/build_notes_cd.py
  python -m projects.schad.build_notes_cd
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import generate_schad_docs as docs  # noqa: E402
import schad_design_basis as basis  # noqa: E402
import schad_details as details  # noqa: E402
import schad_house_basis as house  # noqa: E402
import schad_mep as mep  # noqa: E402
import schad_structural as struct  # noqa: E402
import svg_detail  # noqa: E402
import svg_plans  # noqa: E402


def _repo_root() -> Path:
    return _HERE.parents[1]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build(out: Path | None = None) -> Path:
    root = _repo_root()
    out = Path(out or root / "output" / "schad_notes_cd")
    sheets_dir = out / "sheets"
    details_dir = out / "details"
    docs_dir = out / "docs"
    for d in (sheets_dir, details_dir, docs_dir):
        d.mkdir(parents=True, exist_ok=True)

    sheet_files: list[dict] = []

    # --- Cover + plans ---
    plan_builders: list[tuple[str, str, str, Any]] = [
        ("A0.1", "Cover & Index", "A0_1_cover.svg", svg_plans.cover_sheet_svg),
        ("C1.1", "Site Plan", "C1_1_site.svg", svg_plans.site_plan_svg),
        ("A1.1", "Floor Plan", "A1_1_floor_plan.svg", svg_plans.floor_plan_svg),
        ("A1.2", "ADU ADA Plan", "A1_2_adu_ada.svg", svg_plans.adu_plan_svg),
        ("A2.1", "Elevation South", "A2_1_elev_S.svg", lambda: svg_plans.elevation_svg("S")),
        ("A2.1N", "Elevation North", "A2_1_elev_N.svg", lambda: svg_plans.elevation_svg("N")),
        ("A2.2", "Elevation East", "A2_2_elev_E.svg", lambda: svg_plans.elevation_svg("E")),
        ("A2.2W", "Elevation West", "A2_2_elev_W.svg", lambda: svg_plans.elevation_svg("W")),
        ("A3.1", "Building Section Bay 2", "A3_1_section.svg", svg_plans.section_svg),
        ("S1.1", "Foundation Plan", "S1_1_foundation.svg", svg_plans.foundation_plan_svg),
        ("S2.1", "Roof Framing Plan", "S2_1_roof_framing.svg", svg_plans.roof_framing_svg),
        ("A4.1", "Door/Window/Header Schedules", "A4_1_schedules.svg", svg_plans.door_window_schedule_svg),
        ("A4.2", "Wall Types / SSW / Materials", "A4_2_wall_types.svg", svg_plans.wall_type_schedule_svg),
        ("H2.2", "House Concept Plans", "H2_2_concept.svg", svg_plans.house_concept_svg),
    ]
    for no, title, fname, fn in plan_builders:
        svg = fn()
        _write(sheets_dir / fname, svg)
        sheet_files.append({"no": no, "title": title, "file": f"sheets/{fname}"})

    # MEP
    for kind in ("E", "P", "M"):
        no, title, svg = svg_plans.mep_plan_svg(kind)
        fname = f"{no.replace('-', '_')}.svg"
        _write(sheets_dir / fname, svg)
        sheet_files.append({"no": no, "title": title, "file": f"sheets/{fname}"})

    # --- Details D01-D12 individual + 4-up sheets ---
    all_d = details.build_details()
    for d in all_d:
        svg = svg_detail.render_detail_svg(d)
        fname = f"{d['id']}_{d['title'][:40].replace(' ', '_').replace('/', '-')}.svg"
        # sanitize filename
        fname = "".join(c if c.isalnum() or c in "._-" else "_" for c in fname)
        _write(details_dir / fname, svg)

    # 4-up composite S3.1 S3.2 S3.3
    for i, sheet_no in enumerate(("S3.1", "S3.2", "S3.3")):
        chunk = all_d[i * 4 : (i + 1) * 4]
        if not chunk:
            continue
        svg = svg_detail.render_details_sheet(
            chunk, title="STRUCTURAL DETAILS", sheet_no=sheet_no, cols=2, rows=2
        )
        fname = f"{sheet_no.replace('.', '_')}_details.svg"
        _write(sheets_dir / fname, svg)
        sheet_files.append(
            {
                "no": sheet_no,
                "title": f"Structural Details ({', '.join(d['id'] for d in chunk)})",
                "file": f"sheets/{fname}",
            }
        )

    # --- Engineering docs ---
    # write MD into docs_dir (patch generate paths)
    for name, lines_fn in (
        ("STRUCTURAL_CALCS.md", docs.structural_doc),
        ("MEP_CALCS.md", docs.mep_doc),
        ("SPECIFICATIONS.md", docs.spec_doc),
    ):
        _write(docs_dir / name, "\n".join(lines_fn()) + "\n")

    # open questions
    oq = basis.open_questions()
    oq_md = ["# SCHAD Open Questions", ""]
    for q in oq:
        oq_md.append(
            f"- **{q.get('id')}** [{q.get('status')}] — {q.get('q', '')[:200]}"
        )
    _write(docs_dir / "OPEN_QUESTIONS.md", "\n".join(oq_md) + "\n")

    # house concept notes
    h_md = [
        "# Phase 2 House (from notes)",
        "",
        house.remodel_scope().get("directive", ""),
        "",
        "## Concept notes",
    ]
    for n in house.concept_notes():
        h_md.append(f"- {n}")
    h_md += ["", "## Field verify"]
    for v in house.house_field_verify():
        h_md.append(f"- {v}")
    _write(docs_dir / "HOUSE_PHASE2.md", "\n".join(h_md) + "\n")

    # JSON dumps for agents
    data = {
        "project": "2024-008 SCHAD",
        "generated": datetime.now(UTC).isoformat(),
        "source": "projects/schad pure SSOT (no Revit, no llm-bim kernel)",
        "honesty": "[DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION]",
        "scalars": basis.build_scalars(),
        "areas": {
            "total": basis.build_scalars()["area_total"],
            "garage": basis.build_scalars()["area_garage"],
            "adu": basis.build_scalars()["area_adu"],
            "workshop": basis.build_scalars()["area_workshop"],
        },
        "structure_checks": {
            "beam": struct.beam_check(),
            "post": struct.post_check(),
            "strip_ftg": struct.strip_footing_check(),
            "point_ftg": struct.point_footing_check(),
            "lateral": struct.lateral_check(),
            "headers": struct.header_schedule(),
        },
        "mep": {
            "electrical_devices": len(mep.electrical_devices()),
            "plumbing_fixtures": len(mep.plumbing_fixtures_layout()),
            "mech_equipment": len(mep.mech_equipment_layout()),
            "service_calc": mep.electrical_service_calc(),
        },
        "details": [{"id": d["id"], "title": d["title"], "ops": len(d["ops"])} for d in all_d],
        "sheets": sheet_files,
        "open_questions": oq,
    }
    _write(out / "SCHAD_SSOT_SNAPSHOT.json", json.dumps(data, indent=2, default=str))

    # HTML index
    rows = "\n".join(
        f'<tr><td>{s["no"]}</td><td>{s["title"]}</td>'
        f'<td><a href="{s["file"]}">{s["file"]}</a></td></tr>'
        for s in sheet_files
    )
    det_links = "\n".join(
        f'<li><a href="details/{p.name}">{p.name}</a></li>'
        for p in sorted(details_dir.glob("*.svg"))
    )
    index = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>SCHAD Notes CD Pack</title>
<style>
body {{ font-family: Segoe UI, system-ui, sans-serif; margin: 2rem; background: #f6f4ef; color: #111; }}
h1 {{ margin-bottom: 0.2rem; }}
.badge {{ color: #a00; font-weight: 700; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; }}
td, th {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }}
th {{ background: #eee; }}
a {{ color: #0645ad; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
.card {{ background: #fff; padding: 1rem; border: 1px solid #ddd; }}
</style></head><body>
<h1>SCHAD 2024-008 — Note-driven CD pack</h1>
<p class="badge">DESIGN DEVELOPMENT — NOT FOR CONSTRUCTION</p>
<p>Generated from <code>projects/schad</code> pure SSOT — <strong>no Revit, no llm-bim kernel</strong>.</p>
<p>{datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")} · Areas: {data["areas"]}</p>
<div class="grid">
<div class="card">
<h2>Sheets ({len(sheet_files)})</h2>
<table><tr><th>No</th><th>Title</th><th>File</th></tr>
{rows}
</table>
</div>
<div class="card">
<h2>Details D01–D12</h2>
<ul>{det_links}</ul>
<h2>Docs</h2>
<ul>
<li><a href="docs/STRUCTURAL_CALCS.md">STRUCTURAL_CALCS.md</a></li>
<li><a href="docs/MEP_CALCS.md">MEP_CALCS.md</a></li>
<li><a href="docs/SPECIFICATIONS.md">SPECIFICATIONS.md</a></li>
<li><a href="docs/OPEN_QUESTIONS.md">OPEN_QUESTIONS.md</a></li>
<li><a href="docs/HOUSE_PHASE2.md">HOUSE_PHASE2.md</a></li>
<li><a href="SCHAD_SSOT_SNAPSHOT.json">SCHAD_SSOT_SNAPSHOT.json</a></li>
</ul>
<h2>Structural checks (design-support)</h2>
<pre>{chr(10).join(struct.calc_summary())}</pre>
</div>
</div>
</body></html>
"""
    _write(out / "index.html", index)

    # MANIFEST
    manifest = {
        "ok": True,
        "kind": "schad_notes_cd",
        "output_dir": str(out.resolve()),
        "sheets": len(sheet_files),
        "details": len(all_d),
        "index": str((out / "index.html").resolve()),
        "honesty": data["honesty"],
    }
    _write(out / "MANIFEST.json", json.dumps(manifest, indent=2))

    print("SCHAD_NOTES_CD", out.resolve())
    print("OPEN_INDEX", (out / "index.html").resolve())
    print("SHEETS", len(sheet_files), "DETAILS", len(all_d))
    for s in sheet_files:
        print(" ", s["no"], s["title"])
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
