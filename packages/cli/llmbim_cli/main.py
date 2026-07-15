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
        kw: dict = {
            "level": "L1",
            "start": start,
            "end": end,
            "thickness_mm": 200,
            "height_mm": 3000,
            "name": name,
        }
        if name == "W-S":
            kw["fire_rating"] = "1-hr"
            kw["type_id"] = "W-EXT-CMU"
        ids[name] = p.create_wall(**kw)
    p.place_door(
        host=ids["W-S"],
        offset_mm=2000,
        width_mm=900,
        height_mm=2100,
        name="Entry",
        type_id="D-HM-36",
        fire_rating="90 min",
    )
    p.place_window(
        host=ids["W-N"],
        offset_mm=3000,
        width_mm=1500,
        height_mm=1200,
        sill_mm=900,
        name="NWin",
        type_id="WIN-VIEW",
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
    phases = getattr(args, "phases", None)
    manifest = p.export_deliverables(
        args.out,
        mode=args.mode,
        plan_level=args.level,
        plan_scale=args.scale,
        phases=phases,
    )
    keys = (
        "project",
        "ok",
        "stats",
        "errors",
        "verification",
        "phase_filter",
        "export_element_count",
        "full_element_count",
    )
    print(json.dumps({k: manifest[k] for k in keys if k in manifest}, indent=2))
    return 0 if manifest.get("ok") else 1


def cmd_verify(args: argparse.Namespace) -> int:
    from llmbim_drawings.deliverables import verify_pack

    v = verify_pack(
        args.path,
        require_parts=args.require_parts,
        require_materials=getattr(args, "require_materials", False),
    )
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


def cmd_schedule(args: argparse.Namespace) -> int:
    """Export or print schedule rows: room|zone|door|csi|connection|pipe|…"""
    from pathlib import Path

    from llmbim import Project
    from llmbim_drawings.schedules import export_schedule_csv, schedule_rows

    p = Project.open(args.path)
    kind = args.kind or "zone"
    rows = schedule_rows(p.model, kind)
    if args.out:
        out = Path(args.out)
        if out.suffix.lower() == ".csv" or not out.suffix:
            if not out.suffix:
                out = out.with_suffix(".csv") if out.name else out / f"{kind}.csv"
            export_schedule_csv(p.model, kind, out)
            print(json.dumps({"kind": kind, "count": len(rows), "wrote": str(out)}, indent=2))
            return 0
        out.write_text(
            __import__("json").dumps(rows, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"kind": kind, "count": len(rows), "wrote": str(out)}, indent=2))
        return 0
    print(
        __import__("json").dumps(
            {"kind": kind, "count": len(rows), "rows": rows[: args.limit]},
            indent=2,
            default=str,
        )
    )
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


def cmd_commit(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    try:
        c = p.commit(args.message, author=args.author or "cli")
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2))
        return 1
    print(json.dumps({"ok": True, **c}, indent=2))
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    print(json.dumps(p.log(limit=args.limit), indent=2))
    return 0


def cmd_status_vcs(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    st = p.status()
    print(json.dumps(st, indent=2))
    return 0 if st.get("clean") else 1


def cmd_checkout(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    r = p.checkout(args.version)
    print(json.dumps(r, indent=2))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    d = p.diff(args.a, args.b)
    print(json.dumps(d, indent=2))
    return 0


def cmd_tag(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    r = p.tag(args.name, args.version)
    print(json.dumps(r, indent=2))
    return 0


def cmd_journal(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    print(json.dumps(p.journal(limit=args.limit), indent=2))
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


def cmd_import_module(args: argparse.Namespace) -> int:
    """Import a project/module into a host as block|native|linked."""
    from llmbim import Project

    host = Project.open(args.host) if args.host else Project.create(args.name or "Host")
    if not host.levels():
        host.add_level(args.level or "L1", 0)
    origin = (0.0, 0.0)
    if args.origin:
        parts = [float(x) for x in args.origin.split(",")]
        origin = (parts[0], parts[1])
    r = host.import_module(
        args.source,
        level=args.level or host.levels()[0].name,
        origin=origin,
        mode=args.mode,
        name=args.module_name,
        rotation_deg=args.rotation or 0,
        kind=args.kind or "fabrication",
    )
    out = Path(args.out) if args.out else Path("output/module_host")
    out.mkdir(parents=True, exist_ok=True)
    host.save(out / "model.llmbim.json")
    if args.pack:
        man = host.export_deliverables(out)
        r["pack_ok"] = man.get("ok")
    print(json.dumps({"result": r, "stats": host.stats(), "out": str(out)}, indent=2, default=str))
    return 0


def cmd_export_module(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    r = p.export_module(args.out, name=args.name, kind=args.kind or "fabrication")
    print(json.dumps(r, indent=2))
    return 0


def cmd_modules(args: argparse.Namespace) -> int:
    from llmbim import Project

    p = Project.open(args.path)
    print(json.dumps(p.modules(), indent=2, default=str))
    return 0


def cmd_materials(args: argparse.Namespace) -> int:
    """List materials catalog or export material lists for a project."""
    if args.path:
        from llmbim import Project

        p = Project.open(args.path)
        if args.out:
            written = p.export_material_lists(args.out)
            print(json.dumps({"out": args.out, "files": written}, indent=2))
            return 0
        print(json.dumps(p.material_lists(), indent=2, default=str))
        return 0
    from llmbim_core.materials import materials_catalog

    print(json.dumps(materials_catalog(), indent=2))
    return 0


def cmd_parts(args: argparse.Namespace) -> int:
    from llmbim_core.parts_catalog import list_parts, parts_catalog

    if args.full:
        print(json.dumps(parts_catalog(), indent=2))
        return 0
    rows = list_parts(
        category=args.category,
        fitting_type=args.fitting_type,
        nps=args.nps,
        material=args.material,
        system=args.system,
    )
    slim = [
        {
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "material": p.primary_material_id,
            "unit_cost": p.unit_cost,
            "nps": (p.specs or {}).get("nps"),
            "fitting_type": (p.specs or {}).get("fitting_type"),
        }
        for p in rows
    ]
    print(json.dumps({"count": len(slim), "parts": slim}, indent=2))
    return 0


def cmd_takeoff(args: argparse.Namespace) -> int:
    """Trade takeoff — copper 90s, fire sprinklers, rebar, steel, CSI, fixtures."""
    from llmbim import Project

    p = Project.open(args.path)
    kind = args.kind
    if kind == "pipe":
        print(json.dumps(p.pipe_takeoff(nps=args.nps, material=args.material), indent=2))
        return 0
    if kind in ("duct", "hvac"):
        print(json.dumps({"duct": p.duct_takeoff()}, indent=2, default=str))
        return 0
    if kind in ("conduit", "electrical"):
        print(json.dumps({"conduit": p.conduit_takeoff()}, indent=2, default=str))
        return 0
    if kind in ("cable_tray", "tray"):
        print(json.dumps({"cable_tray": p.cable_tray_takeoff()}, indent=2, default=str))
        return 0
    if kind == "plumbing":
        print(json.dumps(p.plumbing_schedule(), indent=2))
        return 0
    if kind == "fire":
        print(json.dumps(p.fire_takeoff(), indent=2))
        return 0
    if kind in ("steel", "structural_steel"):
        print(json.dumps(p.steel_takeoff(), indent=2))
        return 0
    if kind == "rebar":
        print(json.dumps(p.rebar_takeoff(), indent=2))
        return 0
    if kind == "csi":
        print(json.dumps(p.csi_takeoff(division=args.division), indent=2))
        return 0
    if kind in ("csi_instances", "instances", "locator"):
        rows = p.csi_instances()
        if args.division:
            rows = [r for r in rows if str(r.get("csi_division") or "").startswith(str(args.division))]
        print(json.dumps({"count": len(rows), "instances": rows}, indent=2, default=str))
        return 0
    if kind in ("trades", "all"):
        print(json.dumps(p.trade_schedule(), indent=2, default=str))
        return 0
    if kind in ("fixture", "fixtures", "process", "framing"):
        print(json.dumps(p.system_takeoff(kind if kind != "fixtures" else "fixture"), indent=2))
        return 0
    rows = p.fitting_takeoff(
        fitting_type=args.fitting_type,
        nps=args.nps,
        material=args.material,
        system=args.system,
    )
    print(json.dumps({"fittings": rows, "count_rows": len(rows)}, indent=2))
    return 0


def _parse_xy(s: str) -> tuple[float, float]:
    parts = [float(x.strip()) for x in s.replace(" ", "").split(",")]
    if len(parts) < 2:
        raise SystemExit("--origin requires x,y mm")
    return parts[0], parts[1]


def _parse_boundary(s: str) -> list[tuple[float, float]]:
    """Parse 'x1,y1;x2,y2;x3,y3' or 'x1,y1 x2,y2 x3,y3' into plan polygon points."""
    raw = (s or "").strip()
    if not raw:
        raise SystemExit("place room requires --boundary or --origin + --end rect")
    seps = ";" if ";" in raw else "|"
    if seps in raw:
        chunks = [c.strip() for c in raw.split(seps) if c.strip()]
    else:
        # space-separated points: "0,0 4000,0 4000,3000"
        chunks = [c.strip() for c in raw.replace("  ", " ").split(" ") if c.strip()]
    pts: list[tuple[float, float]] = []
    for c in chunks:
        pts.append(_parse_xy(c))
    if len(pts) < 3:
        raise SystemExit("room boundary needs ≥3 points (x,y;...)")
    return pts


def cmd_place(args: argparse.Namespace) -> int:
    """Place MEP part/fitting/pipe/riser on an open project and save."""
    from llmbim import Project

    p = Project.open(args.path)
    if not p.levels():
        p.add_level(args.level or "L1", 0)
    level = args.level or p.levels()[0].name
    origin = _parse_xy(args.origin) if args.origin else (0.0, 0.0)
    kind = args.kind
    result: dict = {}
    if kind == "fitting":
        eid = p.place_fitting(
            level=level,
            fitting_type=args.fitting_type or "elbow_90",
            nps=args.nps or "3/4",
            origin=origin,
            material=args.material or "copper",
            name=args.name,
            system=args.system or "CW",
        )
        result = {"element_id": eid, "kind": "fitting"}
    elif kind == "pipe":
        if not args.end:
            raise SystemExit("place pipe requires --end x,y")
        end = _parse_xy(args.end)
        eid = p.place_pipe(
            level=level,
            nps=args.nps or "3/4",
            start=origin,
            end=end,
            material=args.material or "copper",
            name=args.name,
            system=args.system or "CW",
        )
        result = {"element_id": eid, "kind": "pipe"}
    elif kind == "riser":
        kwargs: dict = {
            "level": level,
            "nps": args.nps or "2",
            "origin": origin,
            "material": args.material or "copper",
            "name": args.name,
            "system": args.system or "CW",
        }
        if getattr(args, "to_level", None):
            kwargs["to_level"] = args.to_level
        if args.z0 is not None:
            kwargs["z0_mm"] = float(args.z0)
        if args.z1 is not None:
            kwargs["z1_mm"] = float(args.z1)
        if "to_level" not in kwargs and "z1_mm" not in kwargs:
            kwargs["z0_mm"] = float(args.z0 if args.z0 is not None else 0)
            kwargs["z1_mm"] = float(args.z1 if args.z1 is not None else 3000)
        eid = p.place_riser(**kwargs)
        result = {"element_id": eid, "kind": "riser", **{k: kwargs[k] for k in ("z0_mm", "z1_mm", "to_level") if k in kwargs}}
    elif kind == "part":
        eid = p.place_part(
            level=level,
            kind=args.part_kind or args.fitting_type or "toilet",
            origin=origin,
            name=args.name,
        )
        result = {"element_id": eid, "kind": "part"}
    elif kind == "duct":
        if not args.end:
            raise SystemExit("place duct requires --end x,y")
        end = _parse_xy(args.end)
        eid = p.place_duct(
            level=level,
            start=origin,
            end=end,
            width_mm=float(args.width if args.width is not None else 400),
            height_mm=float(args.height if args.height is not None else 250),
            name=args.name,
            system=args.system or "SA",
            material=args.material or "galv_steel",
        )
        result = {"element_id": eid, "kind": "duct"}
    elif kind == "conduit":
        if not args.end:
            raise SystemExit("place conduit requires --end x,y")
        end = _parse_xy(args.end)
        eid = p.place_conduit(
            level=level,
            start=origin,
            end=end,
            trade_size=args.nps or "3/4",
            name=args.name,
            system=args.system or "P",
            material=args.material or "steel_A36",
        )
        result = {"element_id": eid, "kind": "conduit"}
    elif kind in ("cable_tray", "tray"):
        if not args.end:
            raise SystemExit("place cable_tray requires --end x,y")
        end = _parse_xy(args.end)
        eid = p.place_cable_tray(
            level=level,
            start=origin,
            end=end,
            width_mm=float(args.width if args.width is not None else 300),
            height_mm=float(args.height if args.height is not None else 100),
            name=args.name,
            system=args.system or "PWR",
            material=args.material or "galv_steel",
        )
        result = {"element_id": eid, "kind": "cable_tray"}
    elif kind == "column":
        eid = p.place_column(
            level=level,
            origin=origin,
            section=args.section or args.fitting_type or "W10x33",
            height_mm=float(args.height if args.height is not None else 3000),
            name=args.name,
            material=args.material or "steel_A36",
        )
        result = {"element_id": eid, "kind": "column"}
    elif kind == "beam":
        if not args.end:
            raise SystemExit("place beam requires --end x,y")
        end = _parse_xy(args.end)
        eid = p.place_beam(
            level=level,
            start=origin,
            end=end,
            section=args.section or args.fitting_type or "W12x26",
            name=args.name,
            material=args.material or "steel_A36",
        )
        result = {"element_id": eid, "kind": "beam"}
    elif kind == "wall":
        if not args.end:
            raise SystemExit("place wall requires --end x,y")
        end = _parse_xy(args.end)
        eid = p.create_wall(
            level=level,
            start=origin,
            end=end,
            thickness_mm=float(args.width if args.width is not None else 200),
            height_mm=float(args.height if args.height is not None else 3000),
            name=args.name,
            type_id=getattr(args, "type_id", None) or None,
            fire_rating=getattr(args, "fire_rating", None) or None,
        )
        result = {"element_id": eid, "kind": "wall"}
    elif kind == "door":
        host = getattr(args, "host", None)
        if not host:
            raise SystemExit("place door requires --host <wall_element_id>")
        eid = p.place_door(
            host=host,
            offset_mm=float(getattr(args, "offset", None) if getattr(args, "offset", None) is not None else 1000),
            width_mm=float(args.width if args.width is not None else 900),
            height_mm=float(args.height if args.height is not None else 2100),
            name=args.name,
            type_id=getattr(args, "type_id", None) or None,
            fire_rating=getattr(args, "fire_rating", None) or None,
        )
        result = {"element_id": eid, "kind": "door", "host": host}
    elif kind == "window":
        host = getattr(args, "host", None)
        if not host:
            raise SystemExit("place window requires --host <wall_element_id>")
        eid = p.place_window(
            host=host,
            offset_mm=float(getattr(args, "offset", None) if getattr(args, "offset", None) is not None else 1000),
            width_mm=float(args.width if args.width is not None else 1200),
            height_mm=float(args.height if args.height is not None else 1200),
            sill_mm=float(getattr(args, "sill", None) if getattr(args, "sill", None) is not None else 900),
            name=args.name,
            type_id=getattr(args, "type_id", None) or None,
        )
        result = {"element_id": eid, "kind": "window", "host": host}
    elif kind == "room":
        b_arg = getattr(args, "boundary", None)
        if b_arg:
            boundary = _parse_boundary(b_arg)
        elif args.end:
            # axis-aligned rect from origin (SW) to end (NE)
            x0, y0 = origin
            x1, y1 = _parse_xy(args.end)
            boundary = [
                (min(x0, x1), min(y0, y1)),
                (max(x0, x1), min(y0, y1)),
                (max(x0, x1), max(y0, y1)),
                (min(x0, x1), max(y0, y1)),
            ]
        else:
            raise SystemExit(
                "place room requires --boundary 'x1,y1;x2,y2;...' or --origin + --end for a rectangle"
            )
        eid = p.create_room(
            level=level,
            name=args.name or "Room",
            boundary=boundary,
            height_mm=float(args.height) if args.height is not None else None,
        )
        result = {
            "element_id": eid,
            "kind": "room",
            "name": args.name or "Room",
            "boundary_pts": len(boundary),
        }
    else:
        raise SystemExit(f"Unknown place kind: {kind}")
    # persist back to path
    path = Path(args.path)
    if path.is_dir():
        p.save(path / "model.llmbim.json")
        result["saved"] = str(path / "model.llmbim.json")
    else:
        p.save(path)
        result["saved"] = str(path)
    result["stats"] = p.stats()
    print(json.dumps(result, indent=2, default=str))
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
    p_pack.add_argument(
        "--phases",
        default=None,
        help="Phase filter for exports e.g. new or new,existing (full model still saved)",
    )
    p_pack.set_defaults(func=cmd_pack)

    p_ver = sub.add_parser(
        "verify",
        help="Verify pack: IFC/glTF/STEP, materials, drawing_list, elev/section DXF signals",
    )
    p_ver.add_argument("path", help="Pack directory")
    p_ver.add_argument("--require-parts", action="store_true")
    p_ver.add_argument(
        "--require-materials",
        action="store_true",
        help="Require materials/MATERIALS_AND_PARTS.json takeoff package",
    )
    p_ver.set_defaults(func=cmd_verify)

    p_boq = sub.add_parser("boq", help="Bill of quantities for a project file")
    p_boq.add_argument("path")
    p_boq.add_argument("--out", default=None)
    p_boq.set_defaults(func=cmd_boq)

    p_sch = sub.add_parser(
        "schedule",
        help="Schedule rows: zone|room|door|csi|connection|pipe|duct|conduit|fitting|…",
    )
    p_sch.add_argument("path", help="Project dir or model.llmbim.json")
    p_sch.add_argument(
        "--kind",
        default="zone",
        help="level|zone|room|door|wall|column|beam|pipe|duct|conduit|cable_tray|hvac_device|part|csi|connection",
    )
    p_sch.add_argument("--out", default=None, help="Write .csv or .json file")
    p_sch.add_argument("--limit", type=int, default=50, help="Max rows when printing JSON")
    p_sch.set_defaults(func=cmd_schedule)

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

    # Version control (true model history)
    p_c = sub.add_parser("commit", help="Commit current model as a version")
    p_c.add_argument("path", help="Project dir or model.llmbim.json")
    p_c.add_argument("-m", "--message", required=True)
    p_c.add_argument("--author", default="cli")
    p_c.set_defaults(func=cmd_commit)

    p_log = sub.add_parser("log", help="List model version history")
    p_log.add_argument("path")
    p_log.add_argument("-n", "--limit", type=int, default=20)
    p_log.set_defaults(func=cmd_log)

    p_st = sub.add_parser("status", help="Working tree vs last commit")
    p_st.add_argument("path")
    p_st.set_defaults(func=cmd_status_vcs)

    p_co = sub.add_parser("checkout", help="Restore a committed model version")
    p_co.add_argument("path")
    p_co.add_argument("version")
    p_co.set_defaults(func=cmd_checkout)

    p_df = sub.add_parser("diff", help="Diff versions (default HEAD vs working)")
    p_df.add_argument("path")
    p_df.add_argument("-a", default=None, help="Version A (default HEAD)")
    p_df.add_argument("-b", default=None, help="Version B (default working tree)")
    p_df.set_defaults(func=cmd_diff)

    p_tg = sub.add_parser("tag", help="Tag a version")
    p_tg.add_argument("path")
    p_tg.add_argument("name")
    p_tg.add_argument("--version", default=None)
    p_tg.set_defaults(func=cmd_tag)

    p_jn = sub.add_parser("journal", help="Mutation journal (ops between commits)")
    p_jn.add_argument("path")
    p_jn.add_argument("-n", "--limit", type=int, default=50)
    p_jn.set_defaults(func=cmd_journal)

    p_im = sub.add_parser("import-module", help="Import project as block|native|linked module")
    p_im.add_argument("source", help="Source .llmbim.json or pack/module directory")
    p_im.add_argument("--host", default=None, help="Host project path (create new if omitted)")
    p_im.add_argument("--name", default=None, help="Host project name when creating")
    p_im.add_argument("--module-name", default=None)
    p_im.add_argument("--level", default=None)
    p_im.add_argument("--mode", default="native", choices=["block", "native", "linked"])
    p_im.add_argument("--kind", default="fabrication", help="block|fabrication|machine")
    p_im.add_argument("--origin", default=None, help="x,y mm")
    p_im.add_argument("--rotation", type=float, default=0)
    p_im.add_argument("--out", default=None)
    p_im.add_argument("--pack", action="store_true")
    p_im.set_defaults(func=cmd_import_module)

    p_em = sub.add_parser("export-module", help="Export project as reusable module package")
    p_em.add_argument("path", help="Source project")
    p_em.add_argument("--out", required=True, help="Output .llmbim.json or directory")
    p_em.add_argument("--name", default=None)
    p_em.add_argument("--kind", default="fabrication")
    p_em.set_defaults(func=cmd_export_module)

    p_mod = sub.add_parser("modules", help="List module library + connections on a project")
    p_mod.add_argument("path")
    p_mod.set_defaults(func=cmd_modules)

    p_mat = sub.add_parser("materials", help="Materials catalog or project material lists")
    p_mat.add_argument("path", nargs="?", default=None, help="Project path (omit = catalog only)")
    p_mat.add_argument("--out", default=None, help="Write CSV/JSON lists to directory")
    p_mat.set_defaults(func=cmd_materials)

    p_pts = sub.add_parser("parts", help="Parts catalog (filter plumbing fittings)")
    p_pts.add_argument("--category", default=None)
    p_pts.add_argument("--fitting-type", default=None, help="elbow_90 | tee | pipe | ...")
    p_pts.add_argument("--nps", default=None, help='e.g. 1/2 or 3/4')
    p_pts.add_argument("--material", default=None)
    p_pts.add_argument("--system", default=None)
    p_pts.add_argument("--full", action="store_true")
    p_pts.set_defaults(func=cmd_parts)

    p_tk = sub.add_parser("takeoff", help="Trade takeoff: fittings/fire/steel/rebar/csi/fixtures")
    p_tk.add_argument("path", help="Project dir or model.llmbim.json")
    p_tk.add_argument(
        "--kind",
        default="fittings",
        choices=[
            "fittings",
            "pipe",
            "plumbing",
            "fire",
            "steel",
            "structural_steel",
            "rebar",
            "csi",
            "csi_instances",
            "instances",
            "locator",
            "trades",
            "all",
            "fixture",
            "fixtures",
            "process",
            "framing",
            "duct",
            "hvac",
            "conduit",
            "electrical",
            "cable_tray",
            "tray",
        ],
        help="fittings|pipe|plumbing|fire|steel|rebar|csi|duct|conduit|cable_tray|trades|fixture",
    )
    p_tk.add_argument("--fitting-type", default=None, help="elbow_90 | tee | sprinkler_head | ...")
    p_tk.add_argument("--nps", default=None)
    p_tk.add_argument("--material", default=None, help="copper | fire | process | pvc")
    p_tk.add_argument("--system", default=None, help="plumbing | fire | process")
    p_tk.add_argument("--division", default=None, help="CSI division filter e.g. 21 or 05")
    p_tk.set_defaults(func=cmd_takeoff)

    p_pl = sub.add_parser(
        "place",
        help="Place fitting|pipe|riser|part|wall|door|window|room|MEP|structure on a project and save",
    )
    p_pl.add_argument("path", help="Project dir or model.llmbim.json")
    p_pl.add_argument(
        "--kind",
        required=True,
        choices=[
            "fitting",
            "pipe",
            "riser",
            "part",
            "duct",
            "conduit",
            "cable_tray",
            "tray",
            "column",
            "beam",
            "wall",
            "door",
            "window",
            "room",
        ],
        help="What to place",
    )
    p_pl.add_argument("--width", type=float, default=None, help="Duct/door/window width mm; wall thickness")
    p_pl.add_argument("--height", type=float, default=None, help="Duct/column/door/window/wall/room clear height mm")
    p_pl.add_argument("--level", default=None)
    p_pl.add_argument("--origin", default="0,0", help="x,y mm plan origin / pipe start / wall start / room SW")
    p_pl.add_argument("--end", default=None, help="x,y mm end (pipe/duct/wall/beam/room NE rect)")
    p_pl.add_argument(
        "--boundary",
        default=None,
        help="Room polygon: x1,y1;x2,y2;x3,y3 (mm). Or use --origin + --end for rectangle",
    )
    p_pl.add_argument("--host", default=None, help="Host wall element id (door/window)")
    p_pl.add_argument("--offset", type=float, default=None, help="Offset along host wall mm (door/window)")
    p_pl.add_argument("--sill", type=float, default=None, help="Window sill height mm from floor")
    p_pl.add_argument("--type-id", dest="type_id", default=None, help="Type mark e.g. D-HM-36 / W-2HR")
    p_pl.add_argument("--fire-rating", dest="fire_rating", default=None, help="e.g. 90 min or 2-hr")
    p_pl.add_argument("--nps", default=None, help='Nominal pipe size e.g. 3/4 or 2')
    p_pl.add_argument("--fitting-type", default=None, help="elbow_90 | tee | ...")
    p_pl.add_argument("--section", default=None, help="Steel section for column e.g. W10x33")
    p_pl.add_argument("--part-kind", default=None, help="toilet | sink | ... for kind=part")
    p_pl.add_argument("--material", default=None, help="copper | fire | process | pvc")
    p_pl.add_argument("--system", default=None)
    p_pl.add_argument("--name", default=None)
    p_pl.add_argument("--z0", type=float, default=None, help="Riser base height mm")
    p_pl.add_argument("--z1", type=float, default=None, help="Riser top height mm")
    p_pl.add_argument("--to-level", default=None, help="Multi-storey riser top level e.g. L2")
    p_pl.set_defaults(func=cmd_place)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
