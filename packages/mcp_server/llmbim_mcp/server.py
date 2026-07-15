"""MCP stdio server — tools for Claude/Grok desktop clients.

Run: python -m llmbim_mcp.server
Or:  llmbim mcp
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Prefer official MCP SDK when installed; fall back to minimal JSON-RPC loop.
try:
    from mcp.server.fastmcp import FastMCP

    HAS_MCP = True
except ImportError:  # pragma: no cover
    HAS_MCP = False
    FastMCP = None  # type: ignore[misc, assignment]

from llmbim import Project
from llmbim_drawings import export_plan_svg
from llmbim_server.store import ProjectStore

store = ProjectStore()


def _tool_result(data: Any) -> str:
    return json.dumps({"ok": True, "result": data}, indent=2)


if HAS_MCP:
    mcp = FastMCP("llm-bim")

    @mcp.tool()
    def project_create(name: str = "Untitled") -> str:
        """Create a new BIM project. Returns project_id."""
        pid, p = store.create(name)
        return _tool_result({"project_id": pid, "name": p.name})

    @mcp.tool()
    def project_list() -> str:
        """List projects in the local store."""
        return _tool_result(store.list_projects())

    @mcp.tool()
    def level_add(project_id: str, name: str, elevation_mm: float) -> str:
        p = store.get(project_id)
        lid = p.add_level(name, elevation_mm)
        store.save(project_id)
        return _tool_result({"level_id": lid})

    @mcp.tool()
    def wall_create(
        project_id: str,
        level: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        thickness_mm: float = 200,
        height_mm: float = 3000,
        name: str = "",
    ) -> str:
        p = store.get(project_id)
        wid = p.create_wall(
            level=level,
            start=(start_x, start_y),
            end=(end_x, end_y),
            thickness_mm=thickness_mm,
            height_mm=height_mm,
            name=name or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": wid})

    @mcp.tool()
    def slab_create(
        project_id: str,
        level: str,
        polygon_json: str,
        thickness_mm: float = 200,
        name: str = "",
    ) -> str:
        """polygon_json: JSON list of [x,y] pairs in mm."""
        poly = [tuple(pt) for pt in json.loads(polygon_json)]
        p = store.get(project_id)
        sid = p.create_slab(level=level, polygon=poly, thickness_mm=thickness_mm, name=name or None)
        store.save(project_id)
        return _tool_result({"element_id": sid})

    @mcp.tool()
    def door_place(
        project_id: str,
        host: str,
        offset_mm: float,
        width_mm: float = 900,
        height_mm: float = 2100,
        name: str = "",
    ) -> str:
        p = store.get(project_id)
        did = p.place_door(
            host=host, offset_mm=offset_mm, width_mm=width_mm, height_mm=height_mm, name=name or None
        )
        store.save(project_id)
        return _tool_result({"element_id": did})

    @mcp.tool()
    def project_stats(project_id: str) -> str:
        p = store.get(project_id)
        return _tool_result(p.stats())

    @mcp.tool()
    def export_plan(project_id: str, level: str = "L1", path: str = "") -> str:
        p = store.get(project_id)
        out = Path(path) if path else store.artifacts_dir(project_id) / f"plan_{level}.svg"
        export_plan_svg(p.model, level, out)
        return _tool_result({"path": str(out)})

    @mcp.tool()
    def demo_house() -> str:
        """Create the standard simple-house demo project."""
        pid, p = store.create("Simple House (MCP demo)")
        p.add_level("L1", 0)
        footprint = [(0, 0), (10000, 0), (10000, 8000), (0, 8000)]
        p.create_slab(level="L1", polygon=footprint, thickness_mm=200)
        for start, end, name in [
            ((0, 0), (10000, 0), "W-S"),
            ((10000, 0), (10000, 8000), "W-E"),
            ((10000, 8000), (0, 8000), "W-N"),
            ((0, 8000), (0, 0), "W-W"),
        ]:
            p.create_wall(
                level="L1", start=start, end=end, thickness_mm=200, height_mm=3000, name=name
            )
        store.save(pid)
        return _tool_result({"project_id": pid, "stats": p.stats()})

    @mcp.tool()
    def project_boq(project_id: str) -> str:
        """Bill of quantities / cost estimate summary."""
        p = store.get(project_id)
        return _tool_result(p.boq()["summary"])

    @mcp.tool()
    def project_clash(project_id: str) -> str:
        """AABB clash detection report."""
        p = store.get(project_id)
        c = p.clash()
        return _tool_result({"count": len(c), "clashes": c[:30]})

    @mcp.tool()
    def project_rules(project_id: str) -> str:
        """Design and constructability rules."""
        p = store.get(project_id)
        return _tool_result(p.design_rules())

    @mcp.tool()
    def template_create(template_id: str) -> str:
        """Create project from template: office_bay|warehouse|hot_cell_bay|lab_bench."""
        from llmbim import Project

        p = Project.from_template(template_id)
        pid, _ = store.create(p.name)
        p.model.id = pid
        store._sessions[pid] = p
        store.save(pid)
        return _tool_result({"project_id": pid, "stats": p.stats(), "template": template_id})

    @mcp.tool()
    def export_pack(project_id: str, out_dir: str = "") -> str:
        """Full deliverables pack (IFC/STEP/glTF/drawings/BOQ)."""
        p = store.get(project_id)
        out = out_dir or str(store.artifacts_dir(project_id) / "pack")
        man = p.export_deliverables(out)
        return _tool_result({"out": out, "ok": man.get("ok"), "stats": man.get("stats")})

    def main() -> None:
        mcp.run(transport="stdio")

else:

    def main() -> None:  # pragma: no cover
        print(
            "mcp package not installed. Run: pip install -e '.[server]'",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
