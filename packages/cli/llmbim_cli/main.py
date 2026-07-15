"""``llmbim`` console script."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def cmd_version(_: argparse.Namespace) -> int:
    from llmbim import __version__

    print(__version__)
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from llmbim import Project
    from llmbim_drawings import export_elevation_svg, export_plan_svg, export_section_svg
    from llmbim_drawings.schedules import export_schedule_csv

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    p = Project.create("Simple House")
    p.add_level("L1", 0)
    p.add_level("L2", 3000)
    footprint = [(0, 0), (10000, 0), (10000, 8000), (0, 8000)]
    p.create_slab(level="L1", polygon=footprint, thickness_mm=200, name="Slab")
    ids = {}
    for start, end, name in [
        ((0, 0), (10000, 0), "W-S"),
        ((10000, 0), (10000, 8000), "W-E"),
        ((10000, 8000), (0, 8000), "W-N"),
        ((0, 8000), (0, 0), "W-W"),
    ]:
        ids[name] = p.create_wall(
            level="L1", start=start, end=end, thickness_mm=200, height_mm=3000, name=name
        )
    p.place_door(host=ids["W-S"], offset_mm=2000, width_mm=900, height_mm=2100, name="Entry")
    p.place_window(
        host=ids["W-N"], offset_mm=3000, width_mm=1500, height_mm=1200, sill_mm=900, name="NWin"
    )
    p.create_room(level="L1", name="Living", boundary=footprint)
    p.save(out / "simple_house.llmbim.json")
    export_plan_svg(p.model, "L1", out / "plan_L1.svg")
    export_section_svg(p.model, (5000, -1000), (5000, 9000), out / "section.svg")
    export_elevation_svg(p.model, "S", out / "elev_S.svg")
    export_schedule_csv(p.model, "door", out / "doors.csv")
    export_schedule_csv(p.model, "room", out / "rooms.csv")
    p.export_gltf(out / "model.gltf")
    issues = p.validate()
    print(
        json.dumps(
            {"out": str(out), "stats": p.stats(), "validation": issues},
            indent=2,
        )
    )
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    host = args.host or os.environ.get("HOST", "0.0.0.0")
    port = int(args.port or os.environ.get("PORT", "8000"))
    print(f"LLM-BIM API on http://{host}:{port}  (docs at /docs)", file=sys.stderr)
    uvicorn.run(
        "llmbim_server.app:app",
        host=host,
        port=port,
        reload=args.reload,
    )
    return 0


def cmd_mcp(_: argparse.Namespace) -> int:
    from llmbim_mcp.server import main as mcp_main

    mcp_main()
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    issues = p.validate()
    errors = [i for i in issues if i.get("severity") == "error"]
    print(json.dumps({"path": args.path, "ok": not errors, "issues": issues}, indent=2))
    return 1 if errors else 0


def cmd_pack(args: argparse.Namespace) -> int:
    """Export full deliverables pack from a .llmbim.json file."""
    from llmbim import Project

    p = Project.open(args.path)
    manifest = p.export_deliverables(
        args.out,
        mode=args.mode,
        plan_level=args.level,
        plan_scale=args.scale,
    )
    print(json.dumps({k: manifest[k] for k in ("project", "ok", "stats", "errors", "verification") if k in manifest}, indent=2))
    return 0 if manifest.get("ok") else 1


def cmd_verify(args: argparse.Namespace) -> int:
    from llmbim_drawings.deliverables import verify_pack

    v = verify_pack(args.path, require_parts=args.require_parts)
    print(json.dumps(v, indent=2))
    return 0 if v.get("ok") else 1


def cmd_boq(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    data = p.boq()
    if args.out:
        p.export_boq(args.out, fmt="csv" if args.out.endswith(".csv") else "json")
    print(json.dumps(data["summary"], indent=2))
    return 0


def cmd_clash(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    c = p.clash()
    print(json.dumps({"count": len(c), "clashes": c[:50]}, indent=2))
    return 1 if any(x.get("severity") == "error" for x in c) else 0


def cmd_rules(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    r = p.design_rules()
    print(json.dumps(r["summary"], indent=2))
    if args.verbose:
        print(json.dumps(r["findings"][:40], indent=2))
    return 1 if r["summary"].get("error", 0) else 0


def cmd_import_step(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.project) if args.project else Project.create("STEP Import")
    if not args.project:
        p.add_level(args.level, 0)
    eid = p.import_step(args.step, level=args.level, name=args.name, copy_into=args.copy_into)
    out = Path(args.out or "examples/output/step_import")
    p.save(out / "model.llmbim.json")
    man = p.export_deliverables(out, mode="part")
    print(json.dumps({"equipment_id": eid, "out": str(out), "ok": man.get("ok")}, indent=2))
    return 0 if man.get("ok") else 1


def cmd_import(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.project) if args.project else Project.create(Path(args.path).stem)
    if not p.levels():
        p.add_level(args.level or "L1", 0)
    result = p.import_file(args.path, level=args.level or (p.levels()[0].name if p.levels() else "L1"))
    out = Path(args.out or "examples/output/import")
    out.mkdir(parents=True, exist_ok=True)
    p.save(out / "model.llmbim.json")
    if args.pack:
        man = p.export_deliverables(out)
        result["pack_ok"] = man.get("ok")
    print(json.dumps({"result": result, "stats": p.stats(), "out": str(out)}, indent=2, default=str))
    return 0


def cmd_script(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.create(args.name or "Script")
    r = p.run_script(args.path, outfile=args.save)
    print(json.dumps({k: r[k] for k in r if k != "project"}, indent=2))
    if args.pack and r.get("ok"):
        out = Path(args.pack)
        man = p.export_deliverables(out)
        print(json.dumps({"pack_ok": man.get("ok"), "out": str(out)}, indent=2))
    return 0 if r.get("ok") else 1


def cmd_query(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    els = p.query(args.q)
    print(json.dumps([{"id": e.id, "category": e.category, "name": e.name} for e in els], indent=2))
    return 0


def cmd_op(args: argparse.Namespace) -> int:
    from llmbim import Project
    import json as _json

    p = Project.open(args.path) if args.path else Project.create("op")
    params = _json.loads(args.params) if args.params else {}
    r = p.op(args.name, **params)
    if args.save:
        p.save(args.save)
    print(_json.dumps(r, indent=2, default=str))
    return 0


def cmd_ops(args: argparse.Namespace) -> int:
    """List ops or write JSON schema for any LLM tool-caller."""
    # Import registry side effects
    import llmbim_core.registry as reg  # noqa: F401
    from llmbim_core.registry import list_ops, ops_schema, write_ops_schema

    if args.schema:
        out = args.schema if args.schema != True and args.schema is not True else None
        # --schema alone → default path
        path = args.out or "skills/llm-bim/ops.schema.json"
        if isinstance(args.schema, str) and args.schema not in ("", "true"):
            path = args.schema
        written = write_ops_schema(path)
        print(json.dumps({"wrote": written, "tools": len(ops_schema()["tools"])}, indent=2))
        return 0
    data = ops_schema() if args.json else list_ops()
    print(json.dumps(data, indent=2))
    return 0


def cmd_pdf(args: argparse.Namespace) -> int:
    from llmbim_drawings.pdf_binder import export_pdf_binder

    p = export_pdf_binder(args.sheets, args.out, title=args.title or "LLM-BIM Plot Set")
    print(json.dumps({"pdf": str(p), "size": p.stat().st_size}, indent=2))
    return 0


def cmd_template(args: argparse.Namespace) -> int:
    from llmbim import Project
    from llmbim_core.paths import project_output_dir
    from llmbim_templates import list_templates

    if args.list:
        print(json.dumps(list_templates(), indent=2))
        return 0
    p = Project.from_template(args.name)
    out = Path(args.out) if args.out else project_output_dir(args.name)
    man = p.export_deliverables(out)
    print(
        json.dumps(
            {
                "template": args.name,
                "out": str(Path(man.get("output_dir", out)).resolve()),
                "ok": man.get("ok"),
                "stats": p.stats(),
                "open": str(Path(man.get("output_dir", out)) / "index.html"),
            },
            indent=2,
        )
    )
    return 0 if man.get("ok") else 1


def cmd_case(args: argparse.Namespace) -> int:
    """Build named real-world test cases (INTEC site, Proto10 separator)."""
    from llmbim_core.paths import project_output_dir

    root = Path(__file__).resolve().parents[3]  # repo root when installed editable
    if not (root / "examples").exists():
        root = Path.cwd()
    if args.name == "intec":
        from examples.intec_site import build_intec

        out = Path(args.out) if args.out else project_output_dir("intec")
        p = build_intec(out)
    elif args.name == "proto10":
        from examples.proto10_separator import build_proto10

        out = Path(args.out) if args.out else project_output_dir("proto10")
        p = build_proto10(out)
    else:
        print(f"Unknown case: {args.name}. Use intec | proto10", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "case": args.name,
                "out": str(out.resolve()),
                "stats": p.stats(),
                "open": str(out / "index.html"),
            },
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llmbim", description="LLM-native BIM CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ver = sub.add_parser("version", help="Print version")
    p_ver.set_defaults(func=cmd_version)

    p_demo = sub.add_parser("demo", help="Build demo house + drawings to a folder")
    p_demo.add_argument("--out", default="examples/output", help="Output directory")
    p_demo.set_defaults(func=cmd_demo)

    p_serve = sub.add_parser("serve", help="Start HTTP agent API")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", default=None)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    p_mcp = sub.add_parser("mcp", help="Start MCP stdio server")
    p_mcp.set_defaults(func=cmd_mcp)

    p_val = sub.add_parser("validate", help="Validate a .llmbim.json project file")
    p_val.add_argument("path", help="Path to project JSON")
    p_val.set_defaults(func=cmd_validate)

    p_case = sub.add_parser("case", help="Build real test cases: intec | proto10")
    p_case.add_argument("name", choices=["intec", "proto10"])
    p_case.add_argument("--out", default=None, help="Output directory")
    p_case.set_defaults(func=cmd_case)

    p_pack = sub.add_parser("pack", help="Full deliverables pack from .llmbim.json")
    p_pack.add_argument("path", help="Input project JSON")
    p_pack.add_argument("--out", required=True, help="Output directory")
    p_pack.add_argument("--mode", default="auto", choices=["auto", "facility", "part", "both"])
    p_pack.add_argument("--level", default=None)
    p_pack.add_argument("--scale", type=float, default=None)
    p_pack.set_defaults(func=cmd_pack)

    p_ver = sub.add_parser("verify", help="Verify a deliverables pack directory")
    p_ver.add_argument("path", help="Pack directory")
    p_ver.add_argument("--require-parts", action="store_true")
    p_ver.set_defaults(func=cmd_verify)

    p_boq = sub.add_parser("boq", help="Bill of quantities for a project file")
    p_boq.add_argument("path")
    p_boq.add_argument("--out", default=None)
    p_boq.set_defaults(func=cmd_boq)

    p_clash = sub.add_parser("clash", help="AABB clash report")
    p_clash.add_argument("path")
    p_clash.set_defaults(func=cmd_clash)

    p_rules = sub.add_parser("rules", help="Design/constructability rules")
    p_rules.add_argument("path")
    p_rules.add_argument("-v", "--verbose", action="store_true")
    p_rules.set_defaults(func=cmd_rules)

    p_tpl = sub.add_parser("template", help="Start from a design template")
    p_tpl.add_argument("name", nargs="?", default=None)
    p_tpl.add_argument("--list", action="store_true")
    p_tpl.add_argument("--out", default=None)
    p_tpl.set_defaults(func=cmd_template)

    p_imp = sub.add_parser("import-step", help="Import Fusion STEP as locked equipment")
    p_imp.add_argument("step", help="Path to .step/.stp file")
    p_imp.add_argument("--project", default=None, help="Existing .llmbim.json")
    p_imp.add_argument("--level", default="L1")
    p_imp.add_argument("--name", default=None)
    p_imp.add_argument("--copy-into", default=None)
    p_imp.add_argument("--out", default=None)
    p_imp.set_defaults(func=cmd_import_step)

    p_pdf = sub.add_parser("pdf", help="Build multi-page PDF from SVG sheet folder")
    p_pdf.add_argument("sheets", help="Directory of SVG sheets")
    p_pdf.add_argument("--out", required=True)
    p_pdf.add_argument("--title", default=None)
    p_pdf.set_defaults(func=cmd_pdf)

    p_imp2 = sub.add_parser("import", help="Import any supported file into a project")
    p_imp2.add_argument("path")
    p_imp2.add_argument("--project", default=None)
    p_imp2.add_argument("--level", default=None)
    p_imp2.add_argument("--out", default=None)
    p_imp2.add_argument("--pack", action="store_true")
    p_imp2.set_defaults(func=cmd_import)

    p_scr = sub.add_parser("script", help="Run a trusted Python build script")
    p_scr.add_argument("path")
    p_scr.add_argument("--name", default=None)
    p_scr.add_argument("--save", default=None)
    p_scr.add_argument("--pack", default=None)
    p_scr.set_defaults(func=cmd_script)

    p_q = sub.add_parser("query", help="Query language: category=wall level=L1")
    p_q.add_argument("path")
    p_q.add_argument("q")
    p_q.set_defaults(func=cmd_query)

    p_op = sub.add_parser("op", help="Dispatch registered op")
    p_op.add_argument("name")
    p_op.add_argument("--path", default=None)
    p_op.add_argument("--params", default=None, help="JSON object")
    p_op.add_argument("--save", default=None)
    p_op.set_defaults(func=cmd_op)

    p_ops = sub.add_parser("ops", help="List ops or emit JSON schema for LLM tools")
    p_ops.add_argument("--json", action="store_true", help="Full schema JSON")
    p_ops.add_argument(
        "--schema",
        nargs="?",
        const=True,
        default=None,
        help="Write schema file (default skills/llm-bim/ops.schema.json)",
    )
    p_ops.add_argument("--out", default=None, help="Schema output path")
    p_ops.set_defaults(func=cmd_ops)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
