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
    print(json.dumps({"out": str(out), "stats": p.stats()}, indent=2))
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

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
