"""MCP stdio server — tools mirror registry + high-value façades.

Run: llmbim mcp
Works offline with any MCP client (Claude, Cursor, custom).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP

    HAS_MCP = True
except ImportError:  # pragma: no cover
    HAS_MCP = False
    FastMCP = None  # type: ignore[misc, assignment]

from llmbim import Project
from llmbim_server.store import ProjectStore

store = ProjectStore()


def _tool_result(data: Any) -> str:
    return json.dumps({"ok": True, "result": data}, indent=2, default=str)


def _err(msg: str) -> str:
    return json.dumps({"ok": False, "error": msg})


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
    def project_op(project_id: str, op: str, params_json: str = "{}") -> str:
        """Run any registered op. params_json is a JSON object.
        List ops with ops_catalog()."""
        try:
            params = json.loads(params_json) if params_json else {}
            p = store.get(project_id)
            result = p.op(op, **params)
            store.save(project_id)
            return _tool_result(result)
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

    @mcp.tool()
    def ops_catalog() -> str:
        """Full tool/op catalog for planning (same as llmbim ops --json)."""
        import llmbim_core.registry  # noqa: F401
        from llmbim_core.registry import ops_schema

        return _tool_result(ops_schema())

    @mcp.tool()
    def project_query(project_id: str, q: str) -> str:
        """Query language: category=wall level=L1 param.thickness_mm>200"""
        p = store.get(project_id)
        els = p.query(q)
        return _tool_result(
            [{"id": e.id, "category": e.category, "name": e.name} for e in els[:100]]
        )

    @mcp.tool()
    def project_from_template(template_id: str) -> str:
        """Templates: office_bay | warehouse | hot_cell_bay | lab_bench"""
        p = Project.from_template(template_id)
        pid, _ = store.create(p.name)
        p.model.id = pid
        store._sessions[pid] = p
        store.save(pid)
        return _tool_result({"project_id": pid, "stats": p.stats(), "template": template_id})

    @mcp.tool()
    def project_import(project_id: str, path: str, level: str = "L1") -> str:
        """Import local file: .dxf .ifc .step .csv .json"""
        p = store.get(project_id)
        r = p.import_file(path, level=level)
        store.save(project_id)
        return _tool_result(r)

    @mcp.tool()
    def project_export_pack(project_id: str, out_dir: str = "") -> str:
        """Full deliverables to local folder (default output/<project_name>/).
        Returns absolute path — tell the user where files landed."""
        p = store.get(project_id)
        if out_dir:
            man = p.export_deliverables(out_dir)
            out = out_dir
        else:
            man = p.export_deliverables()  # → output/<slug>/
            out = man.get("output_dir") or ""
        return _tool_result(
            {
                "out": out,
                "ok": man.get("ok"),
                "stats": man.get("stats"),
                "open": f"{out}/index.html" if out else None,
            }
        )

    @mcp.tool()
    def project_commit(project_id: str, message: str, author: str = "agent") -> str:
        """Commit true model version (required after edits — not chat history)."""
        p = store.get(project_id)
        if p._vcs is None:
            from llmbim_core.paths import project_output_dir

            p.bind_vcs(project_output_dir(p.name))
        try:
            c = p.commit(message, author=author)
            store.save(project_id)
            return _tool_result(c)
        except ValueError as e:
            return _err(str(e))

    @mcp.tool()
    def project_log(project_id: str, limit: int = 20) -> str:
        """List committed model versions (newest first)."""
        p = store.get(project_id)
        return _tool_result(p.log(limit=limit))

    @mcp.tool()
    def project_status(project_id: str) -> str:
        """Working tree vs last commit — dirty if uncommitted model changes."""
        p = store.get(project_id)
        return _tool_result(p.status())

    @mcp.tool()
    def project_diff(project_id: str, version_a: str = "", version_b: str = "") -> str:
        """Element-level diff (default HEAD vs working)."""
        p = store.get(project_id)
        return _tool_result(p.diff(version_a or None, version_b or None))

    @mcp.tool()
    def project_checkout(project_id: str, version_id: str) -> str:
        """Restore model to a committed version (discards uncommitted work)."""
        p = store.get(project_id)
        r = p.checkout(version_id)
        store.save(project_id)
        return _tool_result(r)

    @mcp.tool()
    def build_and_export(
        name: str,
        template_id: str = "",
        out_dir: str = "",
    ) -> str:
        """One-shot: create from template (or empty) and export full pack to output/.
        template_id: office_bay|warehouse|hot_cell_bay|lab_bench| (empty=blank)"""
        if template_id:
            p = Project.from_template(template_id)
            if name:
                p.model.name = name
        else:
            p = Project.create(name or "Chat Project")
            p.add_level("L1", 0)
        pid, _ = store.create(p.name)
        p.model.id = pid
        store._sessions[pid] = p
        store.save(pid)
        man = p.export_deliverables(out_dir or None)
        out = man.get("output_dir") or out_dir
        return _tool_result(
            {
                "project_id": pid,
                "out": out,
                "ok": man.get("ok"),
                "stats": p.stats(),
                "open": f"{out}/index.html" if out else None,
            }
        )

    @mcp.tool()
    def project_boq(project_id: str) -> str:
        """Bill of quantities / CSI cost summary"""
        p = store.get(project_id)
        return _tool_result(p.boq()["summary"])

    @mcp.tool()
    def project_clash(project_id: str) -> str:
        """AABB clash report"""
        p = store.get(project_id)
        c = p.clash()
        return _tool_result({"count": len(c), "clashes": c[:40]})

    @mcp.tool()
    def project_rules(project_id: str) -> str:
        """Design/constructability rules"""
        p = store.get(project_id)
        return _tool_result(p.design_rules())

    @mcp.tool()
    def project_stats(project_id: str) -> str:
        p = store.get(project_id)
        return _tool_result(p.stats())

    @mcp.tool()
    def project_takeoff(
        project_id: str,
        kind: str = "plumbing",
        fitting_type: str = "",
        material: str = "",
        system: str = "",
    ) -> str:
        """Trade takeoff. kind: plumbing|fire|steel|rebar|csi|trades|fittings|fixture.
        Answers e.g. how many 90° copper elbows by size."""
        p = store.get(project_id)
        k = (kind or "plumbing").lower()
        if k == "fire":
            return _tool_result(p.fire_takeoff())
        if k in ("steel", "structural_steel"):
            return _tool_result(p.steel_takeoff())
        if k == "rebar":
            return _tool_result(p.rebar_takeoff())
        if k == "csi":
            return _tool_result(p.csi_takeoff())
        if k in ("trades", "all"):
            return _tool_result(p.trade_schedule())
        if k in ("fixture", "fixtures"):
            return _tool_result(p.system_takeoff("fixture"))
        if k == "plumbing":
            return _tool_result(p.plumbing_schedule())
        rows = p.fitting_takeoff(
            fitting_type=fitting_type or None,
            material=material or None,
            system=system or None,
        )
        return _tool_result({"fittings": rows, "count_rows": len(rows)})

    @mcp.tool()
    def place_part(
        project_id: str,
        level: str,
        kind: str = "",
        part_id: str = "",
        section: str = "",
        bar_size: str = "",
        origin_x: float = 0,
        origin_y: float = 0,
        qty: float = 1,
        length_m: float = 0,
        name: str = "",
    ) -> str:
        """Place catalog part: toilet, tp_dispenser, W10x33, rebar #5, sprinkler head, …"""
        p = store.get(project_id)
        eid = p.place_part(
            level=level,
            part_id=part_id or None,
            kind=kind or None,
            section=section or None,
            bar_size=bar_size or None,
            origin=(origin_x, origin_y),
            qty=qty,
            length_m=length_m if length_m else None,
            name=name or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": eid})

    @mcp.tool()
    def place_fitting(
        project_id: str,
        level: str,
        fitting_type: str,
        nps: str,
        origin_x: float = 0,
        origin_y: float = 0,
        material: str = "copper",
        name: str = "",
    ) -> str:
        """Place pipe fitting. material: copper|fire|process|pvc. fitting_type: elbow_90|tee|…"""
        p = store.get(project_id)
        eid = p.place_fitting(
            level=level,
            fitting_type=fitting_type,
            nps=nps,
            origin=(origin_x, origin_y),
            material=material,
            name=name or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": eid})

    @mcp.tool()
    def parts_catalog(
        category: str = "",
        system: str = "",
        fitting_type: str = "",
        nps: str = "",
    ) -> str:
        """List/filter built-in parts catalog (~430 parts)."""
        from llmbim_core.parts_catalog import catalog_summary, list_parts

        if not any([category, system, fitting_type, nps]):
            return _tool_result(catalog_summary())
        rows = list_parts(
            category=category or None,
            system=system or None,
            fitting_type=fitting_type or None,
            nps=nps or None,
        )
        return _tool_result(
            {
                "count": len(rows),
                "parts": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "category": r.category,
                        "csi": r.csi_code,
                        "nps": (r.specs or {}).get("nps"),
                        "fitting_type": (r.specs or {}).get("fitting_type"),
                    }
                    for r in rows[:100]
                ],
            }
        )

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
        unit: str = "mm",
    ) -> str:
        """Create a wall. Coordinates in unit (default mm)."""
        p = store.get(project_id)
        wid = p.create_wall(
            level=level,
            start=(start_x, start_y),
            end=(end_x, end_y),
            thickness_mm=thickness_mm,
            height_mm=height_mm,
            name=name or None,
            unit=unit,
        )
        store.save(project_id)
        return _tool_result({"element_id": wid})

    @mcp.tool()
    def level_add(project_id: str, name: str, elevation_mm: float) -> str:
        p = store.get(project_id)
        lid = p.add_level(name, elevation_mm)
        store.save(project_id)
        return _tool_result({"level_id": lid})

    @mcp.tool()
    def demo_house() -> str:
        """Create standard simple-house demo."""
        pid, p = store.create("Simple House (MCP demo)")
        p.add_level("L1", 0)
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

    def main() -> None:
        mcp.run(transport="stdio")

else:

    def main() -> None:  # pragma: no cover
        print("mcp package not installed. pip install -e '.[mcp,server]'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
