"""One-shot deliverables pack: BIM + 3D + 2D + STEP + sheets + verification."""

from __future__ import annotations

import hashlib
import json
import traceback
from pathlib import Path
from typing import Any

from llmbim_core.model import ProjectModel
from llmbim_drawings.construction import export_construction_set
from llmbim_drawings.parts import export_part_pack
from llmbim_drawings.plan import write_plan_svg
from llmbim_drawings.schedules import export_schedule_csv
from llmbim_drawings.section import write_elevation_svg, write_section_svg
from llmbim_geometry.mesh import export_gltf_walls
from llmbim_geometry.step_export import export_step
from llmbim_ifc.export import export_ifc


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _try(label: str, errors: list[dict], fn) -> Any:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        errors.append(
            {
                "step": label,
                "error": str(exc),
                "trace": traceback.format_exc()[-1500:],
            }
        )
        return None


def verify_pack(
    out_dir: str | Path,
    *,
    require_parts: bool = False,
    require_materials: bool = False,
) -> dict[str, Any]:
    """Check a deliverables directory for required artifacts.

    ``require_materials`` enforces vision pack completeness: materials takeoff
    package under ``materials/`` (assignments, fitting/pipe/CSI lists).
    """
    out = Path(out_dir)
    # Core 3D/BIM artifacts (MANIFEST is written after verify during pack export)
    required = [
        "model.llmbim.json",
        "model.ifc",
        "model.gltf",
        "model.step",
    ]
    missing = [r for r in required if not (out / r).is_file()]
    checks: dict[str, Any] = {"missing": missing, "files": {}}
    for r in required + ["MANIFEST.json", "boq.json", "clash_report.json", "design_rules.json"]:
        p = out / r
        if p.is_file():
            size = p.stat().st_size
            checks["files"][r] = {"size": size, "ok": size > 20}
    # content probes
    if (out / "model.ifc").is_file():
        t = (out / "model.ifc").read_text(encoding="utf-8", errors="replace")
        checks["ifc_has_project"] = "IFCPROJECT" in t
    if (out / "model.step").is_file():
        t = (out / "model.step").read_text(encoding="utf-8", errors="replace")
        checks["step_has_brep"] = "MANIFOLD_SOLID_BREP" in t
    if (out / "construction").is_dir():
        checks["construction_sheets"] = len(list((out / "construction").glob("*.svg")))
    if (out / "parts").is_dir():
        checks["part_steps"] = len(list((out / "parts" / "step").glob("*.step"))) if (out / "parts" / "step").exists() else 0
    if require_parts and checks.get("part_steps", 0) < 1:
        missing.append("parts/step/*.step")

    # Materials / multi-trade takeoff package (vision: full pack includes lists)
    mat_pkg = out / "materials" / "MATERIALS_AND_PARTS.json"
    mat_dir = out / "materials"
    if mat_dir.is_dir():
        checks["materials_json_count"] = len(list(mat_dir.glob("*.json")))
        checks["materials_csv_count"] = len(list(mat_dir.glob("*.csv")))
    if mat_pkg.is_file():
        size = mat_pkg.stat().st_size
        checks["files"]["materials/MATERIALS_AND_PARTS.json"] = {"size": size, "ok": size > 20}
        checks["has_materials_package"] = True
        # probe expected takeoff keys when package present
        try:
            import json as _json

            payload = _json.loads(mat_pkg.read_text(encoding="utf-8"))
            checks["materials_has_fitting_takeoff"] = "fitting_takeoff" in payload
            checks["materials_has_csi"] = "csi" in payload or "csi_takeoff" in [
                p.name for p in mat_dir.glob("csi*.json")
            ]
        except Exception:  # noqa: BLE001
            checks["materials_package_parse_ok"] = False
    else:
        checks["has_materials_package"] = False
        if require_materials:
            missing.append("materials/MATERIALS_AND_PARTS.json")

    # plumbing schedule sidecar (optional soft signal)
    plumb = out / "schedules" / "plumbing_takeoff.json"
    if plumb.is_file():
        checks["files"]["schedules/plumbing_takeoff.json"] = {
            "size": plumb.stat().st_size,
            "ok": plumb.stat().st_size > 2,
        }

    checks["ok"] = not missing and all(v.get("ok", True) for v in checks["files"].values())
    if (out / "model.ifc").is_file() and not checks.get("ifc_has_project"):
        checks["ok"] = False
    if (out / "model.step").is_file() and not checks.get("step_has_brep"):
        checks["ok"] = False
    if require_materials and not checks.get("has_materials_package"):
        checks["ok"] = False
    return checks


def export_deliverables(
    model: ProjectModel,
    out_dir: str | Path,
    *,
    mode: str = "auto",
    plan_level: str | None = None,
    plan_scale: float | None = None,
    phases: str | list[str] | None = None,
) -> dict[str, Any]:
    """Write a full output pack with per-step error isolation.

    ``phases``: optional filter e.g. ``\"new\"`` or ``[\"new\",\"existing\"]``.
    Full unfiltered model is always saved as ``model.llmbim.json``; IFC/glTF/SVG/
    BOQ/clash use the phase-filtered view when ``phases`` is set.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    errors: list[dict] = []

    # Source of truth: always full model
    full_model = model
    work = model.filter_by_phase(phases) if phases else model
    phase_filter = None
    if phases:
        if isinstance(phases, str):
            phase_filter = [p.strip() for p in phases.split(",") if p.strip()]
        else:
            phase_filter = [str(p) for p in phases]

    has_walls = any(el.category == "wall" for el in work.elements)
    has_equip = any(el.category == "equipment" for el in work.elements)
    if mode == "auto":
        mode = "facility" if has_walls else "part"

    level = plan_level or (work.levels[0].name if work.levels else "L1")
    if plan_scale is None:
        plan_scale = 0.01 if has_walls else 0.4

    model_path = out / "model.llmbim.json"
    _try("save_model", errors, lambda: full_model.save(model_path))
    if phase_filter:
        filtered_path = out / "model_phase_filtered.llmbim.json"
        _try("save_phase_filtered", errors, lambda: work.save(filtered_path))

    # Expand CAD-like blocks for solid/mesh export (host model stays with instances)
    export_model = work
    if any(el.category == "module_instance" for el in work.elements):
        try:
            from llmbim_core.modules import expand_block_for_export

            export_model = expand_block_for_export(work)
        except Exception as exc:  # noqa: BLE001
            errors.append({"step": "expand_blocks", "error": str(exc)})
            export_model = work

    ifc_path = out / "model.ifc"
    _try("export_ifc", errors, lambda: export_ifc(export_model, ifc_path))

    gltf_path = out / "model.gltf"
    _try("export_gltf", errors, lambda: export_gltf_walls(export_model, gltf_path))

    step_path = out / "model.step"
    _try(
        "export_step",
        errors,
        lambda: export_step(export_model, step_path, include_walls=has_walls),
    )

    views = out / "views"
    views.mkdir(exist_ok=True)
    _try(
        "plan_view",
        errors,
        lambda: write_plan_svg(work, level, views / f"plan_{level}.svg", scale=plan_scale),
    )
    _try(
        "elev_S",
        errors,
        lambda: write_elevation_svg(work, "S", views / "elev_S.svg", scale=plan_scale),
    )
    _try(
        "elev_E",
        errors,
        lambda: write_elevation_svg(work, "E", views / "elev_E.svg", scale=plan_scale),
    )
    # section mid
    def _section() -> None:
        xs = []
        ys = []
        for el in work.elements:
            if el.category == "wall" and "start_mm" in el.params:
                xs += [float(el.params["start_mm"][0]), float(el.params["end_mm"][0])]
                ys += [float(el.params["start_mm"][1]), float(el.params["end_mm"][1])]
        if not xs:
            xs, ys = [0.0, 1000.0], [-1000.0, 1000.0]
        mid = (min(xs) + max(xs)) / 2
        write_section_svg(
            work,
            (mid, min(ys) - 1000),
            (mid, max(ys) + 1000),
            views / "section.svg",
            scale=plan_scale,
        )

    _try("section", errors, _section)

    schedules = out / "schedules"
    schedules.mkdir(exist_ok=True)
    for kind in (
        "room",
        "door",
        "window",
        "wall",
        "equipment",
        "fitting",
        "pipe",
        "part",
        "material",
        "csi",
    ):
        _try(
            f"schedule_{kind}",
            errors,
            lambda k=kind: export_schedule_csv(work, k, schedules / f"{k}.csv"),
        )

    # Materials / parts / plumbing takeoff package
    from llmbim_core.material_lists import export_lists, plumbing_schedule

    mat_dir = out / "materials"
    mat_written = _try("material_lists", errors, lambda: export_lists(work, mat_dir))
    plumb = _try("plumbing_schedule", errors, lambda: plumbing_schedule(work))
    if plumb is not None:
        (out / "schedules" / "plumbing_takeoff.json").write_text(
            json.dumps(plumb, indent=2) + "\n", encoding="utf-8"
        )

    result: dict[str, Any] = {
        "mode": mode,
        "model": model_path.name if model_path.exists() else None,
        "ifc": ifc_path.name if ifc_path.exists() else None,
        "gltf": gltf_path.name if gltf_path.exists() else None,
        "step": step_path.name if step_path.exists() else None,
        "views": "views/",
        "schedules": "schedules/",
        "phase_filter": phase_filter,
        "export_element_count": len(work.elements),
        "full_element_count": len(full_model.elements),
    }
    if mat_written:
        result["materials"] = "materials/"
    if plumb is not None:
        result["plumbing_takeoff"] = "schedules/plumbing_takeoff.json"

    # Builder / designer intelligence
    from llmbim_core.clash import find_clashes
    from llmbim_core.quantities import export_boq_csv, export_boq_json
    from llmbim_core.rules import rules_summary, run_design_rules
    from llmbim_drawings.dxf_export import export_plan_dxf

    _try("boq_json", errors, lambda: export_boq_json(work, out / "boq.json"))
    _try("boq_csv", errors, lambda: export_boq_csv(work, out / "boq.csv"))
    clashes = _try("clash", errors, lambda: find_clashes(work)) or []
    (out / "clash_report.json").write_text(
        json.dumps({"count": len(clashes), "clashes": clashes}, indent=2) + "\n",
        encoding="utf-8",
    )
    findings = _try("rules", errors, lambda: run_design_rules(work)) or []
    (out / "design_rules.json").write_text(
        json.dumps({"summary": rules_summary(findings), "findings": findings}, indent=2) + "\n",
        encoding="utf-8",
    )
    _try(
        "dxf",
        errors,
        lambda: export_plan_dxf(work, level, out / "views" / f"plan_{level}.dxf"),
    )
    result["boq"] = "boq.json"
    result["clash_report"] = "clash_report.json"
    result["design_rules"] = "design_rules.json"
    result["dxf"] = f"views/plan_{level}.dxf"

    # Bundle locked Fusion STEP references
    from llmbim_geometry.step_import import pack_step_references

    refs = _try("step_refs", errors, lambda: pack_step_references(work, out)) or []
    if refs:
        result["step_refs"] = "step_refs/"

    if mode in {"facility", "both"} or has_walls:
        cd = _try(
            "construction_set",
            errors,
            lambda: export_construction_set(
                work, out / "construction", plan_level=level, plan_scale=plan_scale
            ),
        )
        if cd:
            result["construction"] = cd

    if mode in {"part", "both"} or has_equip:
        scale_parts = 0.15 if has_walls else max(plan_scale, 0.2)
        parts = _try(
            "part_pack",
            errors,
            lambda: export_part_pack(work, out / "parts", scale=scale_parts),
        )
        if parts:
            result["parts"] = parts

    # PDF after sheets exist
    from llmbim_drawings.pdf_binder import export_pdf_binder

    def _pdf() -> None:
        cand = out / "construction"
        if not cand.is_dir() or not list(cand.glob("*.svg")):
            cand = out / "parts" / "drawings"
        if cand.is_dir() and list(cand.glob("*.svg")):
            export_pdf_binder(cand, out / "PLOT_SET.pdf", title=work.name)

    _try("pdf_binder", errors, _pdf)
    if (out / "PLOT_SET.pdf").is_file():
        result["plot_set_pdf"] = "PLOT_SET.pdf"

    # checksums
    checksums: dict[str, str] = {}
    for p in out.rglob("*"):
        if p.is_file() and p.suffix.lower() in {
            ".json",
            ".ifc",
            ".gltf",
            ".step",
            ".svg",
            ".csv",
        }:
            try:
                checksums[str(p.relative_to(out)).replace("\\", "/")] = _sha256(p)
            except OSError:
                pass

    # Modern packs always write materials/; require it for vision pack completeness
    has_part_assign = any(el.params.get("part_id") for el in work.elements)
    verification = verify_pack(
        out,
        require_parts=has_equip,
        require_materials=True,  # export_lists always runs above
    )
    if has_part_assign and not verification.get("has_materials_package"):
        verification["ok"] = False
        verification.setdefault("missing", []).append("materials/MATERIALS_AND_PARTS.json")
    try:
        from llmbim_drawings.html_index import write_pack_index

        write_pack_index(out)
        result["index_html"] = "index.html"
    except Exception as exc:  # noqa: BLE001
        errors.append({"step": "html_index", "error": str(exc)})

    try:
        from llmbim_drawings.zip_pack import zip_pack

        zpath = zip_pack(out)
        result["zip"] = zpath.name
    except Exception as exc:  # noqa: BLE001
        errors.append({"step": "zip_pack", "error": str(exc)})

    manifest = {
        "project": full_model.name,
        "honesty": "ENGINEERING ESTIMATE — LLM-BIM agent deliverables pack",
        "outputs": result,
        "stats": full_model.stats(),
        "export_stats": work.stats(),
        "phase_filter": phase_filter,
        "export_element_count": len(work.elements),
        "full_element_count": len(full_model.elements),
        "errors": errors,
        "verification": verification,
        "checksums_sha256": checksums,
        "ok": verification.get("ok", False) and len(errors) == 0,
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out / "VERIFY.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    if errors:
        (out / "ERRORS.json").write_text(json.dumps(errors, indent=2) + "\n", encoding="utf-8")
    return manifest
