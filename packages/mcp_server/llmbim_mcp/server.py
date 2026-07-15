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
        """Query: category=door fire_rating=90_min | column section=W10x33 | room~Mech csi~23_31 | vertical=true"""
        p = store.get(project_id)
        els = p.query(q)
        rows = []
        try:
            from llmbim_core.csi import csi_for_element
        except Exception:  # noqa: BLE001
            csi_for_element = None  # type: ignore[assignment]
        for e in els[:100]:
            row = {
                "id": e.id,
                "category": e.category,
                "name": e.name,
                "nps": e.params.get("nps") or e.params.get("trade_size"),
                "trade_size": e.params.get("trade_size") or e.params.get("nps"),
                "section": e.params.get("section"),
                "system": e.params.get("system"),
                "fitting_type": e.params.get("fitting_type"),
                "vertical": e.params.get("vertical"),
                "part_id": e.params.get("part_id") or e.type_id,
                "type_id": e.type_id,
                "fire_rating": e.params.get("fire_rating"),
                "phase": e.params.get("phase", "new"),
                "length_m": e.params.get("length_m"),
                "height_mm": e.params.get("height_mm"),
            }
            if csi_for_element is not None:
                try:
                    info = csi_for_element(p.model, e)
                    row["csi_code"] = info.get("csi_code")
                    row["locator"] = info.get("locator")
                    row["room"] = info.get("room")
                    row["level"] = info.get("level")
                except Exception:  # noqa: BLE001
                    pass
            rows.append(row)
        return _tool_result({"count": len(els), "returned": len(rows), "elements": rows})

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
    def project_export_pack(
        project_id: str,
        out_dir: str = "",
        phases: str = "",
    ) -> str:
        """Full deliverables to local folder (default output/<project_name>/).

        phases: optional filter e.g. 'new' or 'new,existing' — IFC/BOQ/views
        use filtered elements; full model still saved as model.llmbim.json.
        Returns absolute path — tell the user where files landed."""
        p = store.get(project_id)
        phase_arg = phases.strip() or None
        kwargs: dict = {}
        if phase_arg:
            kwargs["phases"] = phase_arg
        if out_dir:
            man = p.export_deliverables(out_dir, **kwargs)
            out = out_dir
        else:
            man = p.export_deliverables(**kwargs)  # → output/<slug>/
            out = man.get("output_dir") or ""
        return _tool_result(
            {
                "out": out,
                "ok": man.get("ok"),
                "stats": man.get("stats"),
                "export_stats": man.get("export_stats"),
                "phase_filter": man.get("phase_filter"),
                "export_element_count": man.get("export_element_count"),
                "full_element_count": man.get("full_element_count"),
                "open": f"{out}/index.html" if out else None,
            }
        )

    @mcp.tool()
    def project_verify_pack(
        pack_dir: str,
        require_materials: bool = True,
        require_parts: bool = False,
    ) -> str:
        """Verify a deliverables pack directory for vision completeness.

        Checks model.ifc/gltf/step, materials package, drawing_list, levels,
        plan/elev/section DXF, design_rules. Returns ok + signal flags."""
        from llmbim_drawings.deliverables import verify_pack

        v = verify_pack(
            pack_dir,
            require_parts=require_parts,
            require_materials=require_materials,
        )
        return _tool_result(v)

    @mcp.tool()
    def set_phase(project_id: str, element_id: str, phase: str = "new") -> str:
        """Set element phase: new | existing | demo | temp (for pack phase filters)."""
        p = store.get(project_id)
        p.set_phase(element_id, phase)
        store.save(project_id)
        return _tool_result({"element_id": element_id, "phase": phase})

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
        phases: str = "",
    ) -> str:
        """One-shot: create from template (or empty) and export full pack to output/.
        template_id: office_bay|warehouse|hot_cell_bay|lab_bench| (empty=blank)
        phases: optional e.g. new or new,existing"""
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
        kwargs: dict = {}
        if phases.strip():
            kwargs["phases"] = phases.strip()
        man = p.export_deliverables(out_dir or None, **kwargs)
        out = man.get("output_dir") or out_dir
        return _tool_result(
            {
                "project_id": pid,
                "out": out,
                "ok": man.get("ok"),
                "stats": p.stats(),
                "phase_filter": man.get("phase_filter"),
                "open": f"{out}/index.html" if out else None,
            }
        )

    @mcp.tool()
    def project_schedule(project_id: str, kind: str = "zone", limit: int = 100) -> str:
        """Schedule rows. kind: level|zone|room|door|wall|column|beam|pipe|duct|conduit|cable_tray|hvac_device|csi|connection|fitting|part."""
        from llmbim_drawings.schedules import schedule_rows

        p = store.get(project_id)
        rows = schedule_rows(p.model, kind)
        return _tool_result({"kind": kind, "count": len(rows), "rows": rows[: max(1, min(limit, 500))]})

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
        """Trade takeoff. kind: plumbing|fire|steel|rebar|csi|duct|hvac|conduit|cable_tray|electrical|trades|fittings|fixture.
        Steel includes place_column/place_beam lengths. Duct/conduit/tray are dedicated takeoffs."""
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
        if k in ("csi_instances", "locator", "locators"):
            return _tool_result({"count": len(p.csi_instances()), "instances": p.csi_instances()[:200]})
        if k in ("trades", "all"):
            return _tool_result(p.trade_schedule())
        if k in ("fixture", "fixtures"):
            return _tool_result(p.system_takeoff("fixture"))
        if k == "plumbing":
            return _tool_result(p.plumbing_schedule())
        if k in ("duct", "hvac"):
            return _tool_result({"duct": p.duct_takeoff()})
        if k in ("conduit",):
            return _tool_result({"conduit": p.conduit_takeoff()})
        if k in ("cable_tray", "tray"):
            return _tool_result({"cable_tray": p.cable_tray_takeoff()})
        if k == "electrical":
            return _tool_result(
                {
                    "conduit": p.conduit_takeoff(),
                    "cable_tray": p.cable_tray_takeoff(),
                    "devices": p.system_takeoff("electrical"),
                }
            )
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
    def place_pipe(
        project_id: str,
        level: str,
        nps: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        material: str = "copper",
        system: str = "CW",
        z0_mm: float = 0,
        name: str = "",
    ) -> str:
        """Horizontal pipe run start→end. material: copper|fire|process|pvc."""
        p = store.get(project_id)
        eid = p.place_pipe(
            level=level,
            nps=nps,
            start=(start_x, start_y),
            end=(end_x, end_y),
            material=material,
            system=system,
            z0_mm=z0_mm,
            name=name or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": eid})

    @mcp.tool()
    def place_riser(
        project_id: str,
        level: str,
        nps: str,
        origin_x: float,
        origin_y: float,
        z0_mm: float = 0,
        z1_mm: float = 3000,
        material: str = "copper",
        system: str = "CW",
        name: str = "",
        to_level: str = "",
    ) -> str:
        """Vertical pipe riser at plan XY. to_level e.g. L2 spans storeys (z1 from elev delta)."""
        p = store.get(project_id)
        kwargs: dict = {
            "level": level,
            "nps": nps,
            "origin": (origin_x, origin_y),
            "material": material,
            "system": system,
            "name": name or None,
        }
        if to_level:
            kwargs["to_level"] = to_level
            if z0_mm:
                kwargs["z0_mm"] = z0_mm
            # only pass z1 if user changed from default while using to_level offset
        else:
            kwargs["z0_mm"] = z0_mm
            kwargs["z1_mm"] = z1_mm
        eid = p.place_riser(**kwargs)
        store.save(project_id)
        return _tool_result({"element_id": eid})

    @mcp.tool()
    def place_duct(
        project_id: str,
        level: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        width_mm: float = 400,
        height_mm: float = 250,
        system: str = "SA",
        z0_mm: float = 2700,
        name: str = "",
    ) -> str:
        """Rectangular HVAC duct (CSI 23 31 00)."""
        p = store.get(project_id)
        eid = p.place_duct(
            level=level,
            start=(start_x, start_y),
            end=(end_x, end_y),
            width_mm=width_mm,
            height_mm=height_mm,
            system=system,
            z0_mm=z0_mm,
            name=name or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": eid})

    @mcp.tool()
    def place_conduit(
        project_id: str,
        level: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        trade_size: str = "3/4",
        system: str = "P",
        z0_mm: float = 2800,
        name: str = "",
    ) -> str:
        """Electrical conduit run (CSI 26 05 33). trade_size e.g. 3/4, 1, 2."""
        p = store.get(project_id)
        eid = p.place_conduit(
            level=level,
            start=(start_x, start_y),
            end=(end_x, end_y),
            trade_size=trade_size,
            system=system,
            z0_mm=z0_mm,
            name=name or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": eid})

    @mcp.tool()
    def place_cable_tray(
        project_id: str,
        level: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        width_mm: float = 300,
        height_mm: float = 100,
        system: str = "PWR",
        z0_mm: float = 2900,
        name: str = "",
    ) -> str:
        """Cable tray run (CSI 26 05 36)."""
        p = store.get(project_id)
        eid = p.place_cable_tray(
            level=level,
            start=(start_x, start_y),
            end=(end_x, end_y),
            width_mm=width_mm,
            height_mm=height_mm,
            system=system,
            z0_mm=z0_mm,
            name=name or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": eid})

    @mcp.tool()
    def place_column(
        project_id: str,
        level: str,
        origin_x: float = 0,
        origin_y: float = 0,
        section: str = "W10x33",
        height_mm: float = 3000,
        name: str = "",
    ) -> str:
        """Structural steel column (CSI 05 12 00). section e.g. W10x33."""
        p = store.get(project_id)
        eid = p.place_column(
            level=level,
            origin=(origin_x, origin_y),
            section=section,
            height_mm=height_mm,
            name=name or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": eid})

    @mcp.tool()
    def place_beam(
        project_id: str,
        level: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        section: str = "W12x26",
        z0_mm: float = 0,
        name: str = "",
    ) -> str:
        """Structural steel beam start→end (CSI 05 12 00)."""
        p = store.get(project_id)
        eid = p.place_beam(
            level=level,
            start=(start_x, start_y),
            end=(end_x, end_y),
            section=section,
            z0_mm=z0_mm if z0_mm else None,
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
    def import_module(
        project_id: str,
        source_path: str,
        level: str = "L1",
        mode: str = "native",
        origin_x: float = 0,
        origin_y: float = 0,
        rotation_deg: float = 0,
        kind: str = "fabrication",
        name: str = "",
    ) -> str:
        """Import another project/module into host.
        mode: native (editable) | block (CAD instance) | linked (re-syncable).
        kind: fabrication | machine | block."""
        p = store.get(project_id)
        if not p.levels():
            p.add_level(level, 0)
        r = p.import_module(
            source_path,
            level=level,
            origin=(origin_x, origin_y),
            mode=mode,
            name=name or None,
            rotation_deg=rotation_deg,
            kind=kind,
        )
        store.save(project_id)
        return _tool_result(r)

    @mcp.tool()
    def export_module(
        project_id: str,
        out_path: str,
        name: str = "",
        kind: str = "fabrication",
    ) -> str:
        """Export current project as reusable module package (dir or .llmbim.json)."""
        p = store.get(project_id)
        r = p.export_module(out_path, name=name or None, kind=kind)
        return _tool_result(r)

    @mcp.tool()
    def define_port(
        project_id: str,
        element_id: str,
        port_name: str,
        role: str = "process",
        medium: str = "",
        position_x: float = 0,
        position_y: float = 0,
    ) -> str:
        """Define connection port on equipment/module (FEED, PWR, DRAIN, …)."""
        p = store.get(project_id)
        r = p.define_port(
            element_id,
            port_name,
            role=role,
            medium=medium,
            position=(position_x, position_y) if (position_x or position_y) else None,
        )
        store.save(project_id)
        return _tool_result(r)

    @mcp.tool()
    def connect_ports(
        project_id: str,
        from_id: str,
        from_port: str,
        to_id: str,
        to_port: str,
        medium: str = "process",
        name: str = "",
    ) -> str:
        """Connect two ports (machine ↔ host header, module ↔ module)."""
        p = store.get(project_id)
        r = p.connect(from_id, from_port, to_id, to_port, medium=medium, name=name)
        store.save(project_id)
        return _tool_result(r)

    @mcp.tool()
    def list_modules(project_id: str) -> str:
        """Module library definitions, instances, and connections on a project."""
        p = store.get(project_id)
        return _tool_result(p.modules())

    @mcp.tool()
    def explode_block(project_id: str, instance_id: str) -> str:
        """Explode a block module_instance into native host elements."""
        p = store.get(project_id)
        r = p.explode_block(instance_id)
        store.save(project_id)
        return _tool_result(r)

    @mcp.tool()
    def csi_instances(project_id: str) -> str:
        """Per-element MasterFormat CSI code + level/XY/Z locator to find items."""
        p = store.get(project_id)
        rows = p.csi_instances()
        return _tool_result({"count": len(rows), "instances": rows[:200]})

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
        type_id: str = "",
        fire_rating: str = "",
    ) -> str:
        """Create a wall. Coordinates in unit (default mm). fire_rating e.g. 1-hr, 2-hr."""
        p = store.get(project_id)
        wid = p.create_wall(
            level=level,
            start=(start_x, start_y),
            end=(end_x, end_y),
            thickness_mm=thickness_mm,
            height_mm=height_mm,
            name=name or None,
            unit=unit,
            type_id=type_id or None,
            fire_rating=fire_rating or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": wid})

    @mcp.tool()
    def place_door(
        project_id: str,
        host: str,
        offset_mm: float = 1000,
        width_mm: float = 900,
        height_mm: float = 2100,
        type_id: str = "",
        fire_rating: str = "",
        name: str = "",
    ) -> str:
        """Place door on host wall (offset along wall baseline from start). FR e.g. 90 min."""
        p = store.get(project_id)
        did = p.place_door(
            host=host,
            offset_mm=offset_mm,
            width_mm=width_mm,
            height_mm=height_mm,
            type_id=type_id or None,
            fire_rating=fire_rating or None,
            name=name or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": did})

    @mcp.tool()
    def place_window(
        project_id: str,
        host: str,
        offset_mm: float = 1000,
        width_mm: float = 1200,
        height_mm: float = 1200,
        sill_mm: float = 900,
        type_id: str = "",
        name: str = "",
    ) -> str:
        """Place window on host wall. sill_mm is height from level floor to sill."""
        p = store.get(project_id)
        wid = p.place_window(
            host=host,
            offset_mm=offset_mm,
            width_mm=width_mm,
            height_mm=height_mm,
            sill_mm=sill_mm,
            type_id=type_id or None,
            name=name or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": wid})

    @mcp.tool()
    def room_create(
        project_id: str,
        level: str,
        name: str,
        boundary_json: str,
        height_mm: float = 0,
    ) -> str:
        """Create room space. boundary_json is [[x,y],...] mm plan polygon (≥3 pts)."""
        import json as _json

        p = store.get(project_id)
        boundary = _json.loads(boundary_json)
        rid = p.create_room(
            level=level,
            name=name,
            boundary=[(float(pt[0]), float(pt[1])) for pt in boundary],
            height_mm=height_mm if height_mm else None,
        )
        store.save(project_id)
        return _tool_result({"element_id": rid, "name": name})

    @mcp.tool()
    def level_add(project_id: str, name: str, elevation_mm: float) -> str:
        p = store.get(project_id)
        lid = p.add_level(name, elevation_mm)
        store.save(project_id)
        return _tool_result({"level_id": lid})

    @mcp.tool()
    def demo_house() -> str:
        """Create standard simple-house demo with entry door + window."""
        pid, p = store.create("Simple House (MCP demo)")
        p.add_level("L1", 0)
        walls: dict[str, str] = {}
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
            walls[name] = p.create_wall(**kw)
        p.place_door(
            host=walls["W-S"],
            offset_mm=2000,
            width_mm=900,
            height_mm=2100,
            name="Entry",
            type_id="D-HM-36",
            fire_rating="90 min",
        )
        p.place_window(
            host=walls["W-S"],
            offset_mm=5000,
            width_mm=1200,
            height_mm=900,
            sill_mm=900,
            name="Front window",
            type_id="WIN-VIEW",
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
