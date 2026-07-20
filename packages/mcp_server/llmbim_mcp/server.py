"""MCP stdio server — tools mirror registry + high-value façades.

Run: llmbim mcp
Works offline with any MCP client (Claude, Cursor, custom).
"""

from __future__ import annotations

import json
import sys
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
    def set_type(project_id: str, element_id: str, type_id: str) -> str:
        """Set type mark e.g. W-EXT-CMU, D-HM-36 (walls may sync thickness from catalog)."""
        p = store.get(project_id)
        p.set_type(element_id, type_id)
        store.save(project_id)
        el = p.model.get_element(element_id)
        return _tool_result(
            {
                "element_id": element_id,
                "type_id": type_id,
                "category": el.category,
                "thickness_mm": el.params.get("thickness_mm"),
            }
        )

    @mcp.tool()
    def element_delete(
        project_id: str,
        element_id: str,
        cascade: bool = True,
    ) -> str:
        """Delete element. cascade=True also removes hosted doors/windows on walls."""
        p = store.get(project_id)
        p.delete_element(element_id, cascade=cascade)
        store.save(project_id)
        return _tool_result({"deleted": element_id, "cascade": cascade})

    @mcp.tool()
    def shell_create(
        project_id: str,
        level: str,
        x: float = 0,
        y: float = 0,
        width_mm: float = 10000,
        depth_mm: float = 8000,
        height_mm: float = 3000,
        thickness_mm: float = 200,
        name_prefix: str = "W",
    ) -> str:
        """Create four walls of a rectangular shell (S/E/N/W). Returns wall element ids."""
        p = store.get(project_id)
        ids = p.create_rect_shell(
            level=level,
            x=x,
            y=y,
            w=width_mm,
            d=depth_mm,
            height_mm=height_mm,
            thickness_mm=thickness_mm,
            name_prefix=name_prefix,
        )
        store.save(project_id)
        return _tool_result({"wall_ids": ids, "count": len(ids), "prefix": name_prefix})

    @mcp.tool()
    def roof_gable_create(
        project_id: str,
        level: str,
        footprint_json: str,
        ridge_axis: str = "x",
        ridge_offset_mm: float | None = None,
        plate_mm: float = 3000.0,
        pitch: float = 0.5,
        overhang_mm: float = 450.0,
        thickness_mm: float = 150.0,
        name: str = "",
    ) -> str:
        """Gable roof over footprint bbox (footprint_json: [[x,y],...] mm).

        pitch is rise/run (6:12 → 0.5); plate_mm = top of plate above level;
        overhang extends the eaves. Valley lines vs overlapping roofs are
        computed and stored on the new element (geometric coordination)."""
        try:
            p = store.get(project_id)
            footprint = json.loads(footprint_json)
            eid = p.create_gable_roof(
                level=level,
                footprint=[(float(q[0]), float(q[1])) for q in footprint],
                ridge_axis=ridge_axis,
                ridge_offset_mm=ridge_offset_mm,
                plate_mm=plate_mm,
                pitch=pitch,
                overhang_mm=overhang_mm,
                thickness_mm=thickness_mm,
                name=name,
            )
            store.save(project_id)
            el = p.model.get_element(eid)
            return _tool_result(
                {
                    "element_id": eid,
                    "ridge_z_mm": el.params.get("ridge_z_mm"),
                    "plane_count": len(el.params.get("planes") or []),
                    "valley_count": len(el.params.get("valley_lines_mm") or []),
                }
            )
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

    @mcp.tool()
    def roof_shed_create(
        project_id: str,
        level: str,
        footprint_json: str,
        high_side: str = "N",
        plate_low_mm: float = 3000.0,
        plate_high_mm: float = 3600.0,
        overhang_mm: float = 450.0,
        thickness_mm: float = 150.0,
        name: str = "",
    ) -> str:
        """Single-plane shed roof over footprint bbox rising toward high_side N|S|E|W."""
        try:
            p = store.get(project_id)
            footprint = json.loads(footprint_json)
            eid = p.create_shed_roof(
                level=level,
                footprint=[(float(q[0]), float(q[1])) for q in footprint],
                high_side=high_side,
                plate_low_mm=plate_low_mm,
                plate_high_mm=plate_high_mm,
                overhang_mm=overhang_mm,
                thickness_mm=thickness_mm,
                name=name,
            )
            store.save(project_id)
            el = p.model.get_element(eid)
            return _tool_result(
                {
                    "element_id": eid,
                    "slope": el.params.get("slope"),
                    "plane_count": len(el.params.get("planes") or []),
                }
            )
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

    @mcp.tool()
    def roof_plane_create(
        project_id: str,
        level: str,
        polygon_json: str,
        thickness_mm: float = 150.0,
        name: str = "",
    ) -> str:
        """Low-level roof plane from a convex 3D polygon_json [[x,y,z],...] (mm, z above level)."""
        try:
            p = store.get(project_id)
            polygon = json.loads(polygon_json)
            eid = p.create_roof_plane(
                level=level,
                polygon=[(float(q[0]), float(q[1]), float(q[2])) for q in polygon],
                thickness_mm=thickness_mm,
                name=name,
            )
            store.save(project_id)
            el = p.model.get_element(eid)
            return _tool_result(
                {
                    "element_id": eid,
                    "slope": el.params.get("slope"),
                    "plane_count": len(el.params.get("planes") or []),
                }
            )
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

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
    def place_tube(
        project_id: str,
        level: str,
        origin_x: float = 0,
        origin_y: float = 0,
        z0_mm: float = 0,
        direction: str = "x",
        length_mm: float = 100,
        od_mm: float = 50,
        id_mm: float = 0,
        kind: str = "port",
        system: str = "",
        name: str = "",
    ) -> str:
        """Oriented tube/port from origin+z0 along direction. direction: x|y|z (± ok)
        or JSON vector e.g. "[0,0.7,0.7]". id_mm>0 makes a hollow stub (KF port)."""
        try:
            p = store.get(project_id)
            d: str | list[float] = direction
            ds = direction.strip()
            if ds.startswith("["):
                d = [float(v) for v in json.loads(ds)]
            eid = p.place_tube(
                level=level,
                origin=(origin_x, origin_y),
                z0_mm=z0_mm,
                direction=d,
                length_mm=length_mm,
                od_mm=od_mm,
                id_mm=id_mm if id_mm > 0 else None,
                kind=kind or "port",
                system=system or None,
                name=name or None,
            )
            store.save(project_id)
            return _tool_result({"element_id": eid})
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

    @mcp.tool()
    def place_wire_path(
        project_id: str,
        level: str,
        points_json: str,
        diameter_mm: float = 6,
        phase: str = "",
        system: str = "",
        wire_role: str = "coil",
        name: str = "",
    ) -> str:
        """ONE 3D wire/hose polyline element. points_json = [[x,y,z],...] mm
        (z above level). phase A|B|C colors it wire_phase_a/b/c in the viewer."""
        try:
            p = store.get(project_id)
            pts = json.loads(points_json)
            eid = p.place_wire_path(
                level=level,
                points_mm=[[float(v) for v in pt] for pt in pts],
                diameter_mm=diameter_mm,
                phase=phase or None,
                system=system or None,
                wire_role=wire_role or "coil",
                name=name or None,
            )
            store.save(project_id)
            return _tool_result({"element_id": eid})
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

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
    def mep_autoroute(
        project_id: str,
        level: str,
        start: str,
        end: str,
        kind: str = "pipe",
        nps: str = "2",
        material: str = "copper",
        system: str = "CW",
        z0_mm: str = "",
        z1_mm: str = "",
        clearance_mm: float = 150,
        grid_mm: float = 250,
        width_mm: float = 400,
        height_mm: float = 250,
        trade_size: str = "3/4",
        name: str = "",
    ) -> str:
        """Obstacle-avoiding orthogonal MEP route around walls/equipment.
        start/end: element id or "x,y" mm. kind: pipe|duct|conduit.
        Elbows placed at bends; z1_mm adds a vertical riser at the end.
        Falls back to plain dogleg when no clear path (result.fallback)."""

        def _ep(v: str) -> str | list[float]:
            if "," in v:
                a, b = v.split(",", 1)
                try:
                    return [float(a), float(b)]
                except ValueError:
                    return v
            return v

        try:
            p = store.get(project_id)
            r = p.mep_autoroute(
                level=level,
                start=_ep(start),
                end=_ep(end),
                kind=kind,
                nps=nps,
                material=material,
                system=system,
                z0_mm=float(z0_mm) if z0_mm.strip() else None,
                z1_mm=float(z1_mm) if z1_mm.strip() else None,
                clearance_mm=clearance_mm,
                grid_mm=grid_mm,
                width_mm=width_mm,
                height_mm=height_mm,
                trade_size=trade_size,
                name=name,
            )
            store.save(project_id)
            return _tool_result(r)
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

    @mcp.tool()
    def mep_tap(
        project_id: str,
        target: str,
        source: str = "",
        system: str = "",
        kind: str = "pipe",
        nps: str = "",
        material: str = "",
        clearance_mm: float = 150,
        grid_mm: float = 250,
        name: str = "",
    ) -> str:
        """Tap a branch off an existing pipe/duct/conduit run.
        target: element id or "x,y" mm. Splits the nearest run (or `source` id,
        filtered by `system` if given) at the tap point, inserts a catalog tee,
        and autoroutes tee→target. nps overrides the branch size (reducing tee)."""

        def _ep(v: str) -> str | list[float]:
            if "," in v:
                a, b = v.split(",", 1)
                try:
                    return [float(a), float(b)]
                except ValueError:
                    return v
            return v

        try:
            p = store.get(project_id)
            r = p.mep_tap(
                target=_ep(target),
                source=source or None,
                system=system or None,
                kind=kind,
                nps=nps or None,
                material=material or None,
                clearance_mm=clearance_mm,
                grid_mm=grid_mm,
                name=name,
            )
            store.save(project_id)
            return _tool_result(r)
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

    @mcp.tool()
    def mep_trunk_branch(
        project_id: str,
        level: str,
        trunk_start: str,
        trunk_end: str,
        targets: str,
        kind: str = "pipe",
        nps: str = "2",
        branch_nps: str = "",
        material: str = "copper",
        system: str = "CW",
        z0_mm: str = "",
        clearance_mm: float = 150,
        grid_mm: float = 250,
        width_mm: float = 400,
        height_mm: float = 250,
        trade_size: str = "3/4",
        name: str = "",
    ) -> str:
        """Autoroute a trunk run, then tee-tap a branch to each target.
        trunk_start/trunk_end: element id or "x,y" mm. targets: ";"-separated
        list of element ids or "x,y" points. branch_nps sizes the branches
        smaller than the trunk (reducing tees)."""

        def _ep(v: str) -> str | list[float]:
            if "," in v:
                a, b = v.split(",", 1)
                try:
                    return [float(a), float(b)]
                except ValueError:
                    return v
            return v

        try:
            p = store.get(project_id)
            r = p.mep_trunk_branch(
                level=level,
                trunk_start=_ep(trunk_start),
                trunk_end=_ep(trunk_end),
                targets=[_ep(t.strip()) for t in targets.split(";") if t.strip()],
                kind=kind,
                nps=nps,
                branch_nps=branch_nps or None,
                material=material,
                system=system,
                z0_mm=float(z0_mm) if z0_mm.strip() else None,
                clearance_mm=clearance_mm,
                grid_mm=grid_mm,
                width_mm=width_mm,
                height_mm=height_mm,
                trade_size=trade_size,
                name=name,
            )
            store.save(project_id)
            return _tool_result(r)
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

    @mcp.tool()
    def mep_size_pipe(
        project_id: str,
        flow_lps: str = "",
        fixture_units: str = "",
        material: str = "copper",
        max_velocity_ms: float = 2.4,
    ) -> str:
        """Size a pipe NPS from flow (L/s) or WSFU fixture units.
        Velocity + Hazen-Williams gradient. Engineering estimate, not stamped design."""
        try:
            p = store.get(project_id)
            r = p.size_pipe(
                float(flow_lps) if flow_lps.strip() else None,
                material=material,
                max_velocity_ms=max_velocity_ms,
                fixture_units=float(fixture_units) if fixture_units.strip() else None,
            )
            return _tool_result(r)
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

    @mcp.tool()
    def mep_size_duct(
        project_id: str,
        flow_m3h: float,
        friction_pa_m: float = 0.8,
        max_velocity_ms: float = 7.5,
        shape: str = "rect",
    ) -> str:
        """Equal-friction duct sizing: round diameter + rect equivalent (estimate)."""
        try:
            p = store.get(project_id)
            r = p.size_duct(
                flow_m3h,
                friction_pa_m=friction_pa_m,
                max_velocity_ms=max_velocity_ms,
                shape=shape,
            )
            return _tool_result(r)
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

    @mcp.tool()
    def mep_size_route(
        project_id: str,
        segment_ids: str,
        flow_lps: str = "",
        flow_m3h: str = "",
        apply: bool = False,
    ) -> str:
        """Size an existing routed run (segment_ids comma-separated).
        apply=true updates element sizes takeoff-consistently (estimate)."""
        try:
            p = store.get(project_id)
            ids = [s.strip() for s in segment_ids.split(",") if s.strip()]
            r = p.size_route(
                ids,
                flow_lps=float(flow_lps) if flow_lps.strip() else None,
                flow_m3h=float(flow_m3h) if flow_m3h.strip() else None,
                apply=apply,
            )
            if apply:
                store.save(project_id)
            return _tool_result(r)
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

    @mcp.tool()
    def mep_validate_runs(project_id: str) -> str:
        """Velocity/friction report for every routed run with flow data (estimate)."""
        try:
            p = store.get(project_id)
            return _tool_result({"runs": p.validate_runs()})
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

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
    def create_fab_part(
        project_id: str,
        name: str = "FabPart",
        material: str = "steel_A36",
        level: str = "",
    ) -> str:
        """Create fab-grade BREP part (feature tree + GD&T). Requires cadquery."""
        p = store.get(project_id)
        eid = p.create_fab_part(name=name, material=material, level=level or None)
        store.save(project_id)
        return _tool_result({"element_id": eid})

    @mcp.tool()
    def fab_feature(
        project_id: str,
        element_id: str,
        op: str,
        size_x: float = 50,
        size_y: float = 50,
        size_z: float = 20,
        origin_x: float = 0,
        origin_y: float = 0,
        origin_z: float = 0,
        diameter_mm: float = 10,
        radius_mm: float = 2,
        selector: str = "|Z",
        designation: str = "M10x1.5",
        length_mm: float = 20,
        internal: bool = False,
        count_x: int = 2,
        count_y: int = 1,
        spacing_x_mm: float = 20,
        spacing_y_mm: float = 20,
    ) -> str:
        """Add fab BREP feature. op: box|cylinder|hole|fillet|chamfer|thread|revolve|hole_pattern|cut_box."""
        p = store.get(project_id)
        o = (origin_x, origin_y, origin_z)
        op_l = op.lower()
        if op_l == "box":
            r = p.fab_box(element_id, size_mm=(size_x, size_y, size_z), origin_mm=o)
        elif op_l == "cylinder":
            r = p.fab_cylinder(
                element_id, diameter_mm=diameter_mm, height_mm=length_mm or size_z, origin_mm=o
            )
        elif op_l == "hole":
            r = p.fab_hole(
                element_id, diameter_mm=diameter_mm, origin_mm=o, depth_mm=length_mm or size_z
            )
        elif op_l == "fillet":
            r = p.fab_fillet(element_id, radius_mm=radius_mm, selector=selector)
        elif op_l == "chamfer":
            r = p.fab_chamfer(element_id, distance_mm=radius_mm, selector=selector)
        elif op_l == "thread":
            r = p.fab_thread(
                element_id,
                designation=designation,
                length_mm=length_mm,
                origin_mm=o,
                internal=internal,
            )
        elif op_l == "revolve":
            r = p.fab_revolve(
                element_id, radius_mm=diameter_mm / 2 or radius_mm, height_mm=length_mm, origin_mm=o
            )
        elif op_l in {"hole_pattern", "pattern"}:
            r = p.fab_hole_pattern(
                element_id,
                diameter_mm=diameter_mm,
                origin_mm=o,
                count_x=count_x,
                count_y=count_y,
                spacing_x_mm=spacing_x_mm,
                spacing_y_mm=spacing_y_mm,
                depth_mm=length_mm or size_z,
            )
        elif op_l in {"cut_box", "pocket"}:
            r = p.op(
                "fab_cut_box",
                element_id=element_id,
                size_mm=[size_x, size_y, size_z],
                origin_mm=list(o),
            )
        else:
            return _tool_result({"ok": False, "error": f"unknown fab op {op}"})
        store.save(project_id)
        return _tool_result(r)

    @mcp.tool()
    def fab_gdt(
        project_id: str,
        element_id: str,
        kind: str = "datum",
        label: str = "A",
        symbol: str = "position",
        tolerance: float = 0.1,
        datums: str = "",
        diameter: bool = False,
        nominal: float = 0,
        tol_plus: float = 0.1,
        dimension: str = "size",
    ) -> str:
        """GD&T on fab_part. kind: datum | fcf | size. datums pipe-separated e.g. A|B."""
        p = store.get(project_id)
        if kind == "datum":
            r = p.gdt_datum(element_id, label=label)
        elif kind == "fcf":
            dlist = [d.strip() for d in datums.split("|") if d.strip()] if datums else []
            r = p.gdt_fcf(
                element_id,
                symbol=symbol,
                tolerance=tolerance,
                datums=dlist,
                diameter=diameter,
            )
        else:
            r = p.gdt_size(
                element_id, dimension=dimension, nominal=nominal, tol_plus=tol_plus
            )
        store.save(project_id)
        return _tool_result(r)

    @mcp.tool()
    def export_fab(
        project_id: str,
        element_id: str,
        out_dir: str,
        kind: str = "step",
    ) -> str:
        """Export fab_part. kind: step | gdt | ortho | all."""
        from pathlib import Path

        p = store.get(project_id)
        dest = Path(out_dir)
        dest.mkdir(parents=True, exist_ok=True)
        out: dict = {}
        if kind in {"step", "all"}:
            out["step"] = p.export_fab_step(element_id, dest / f"{element_id}.step")
        if kind in {"gdt", "all"}:
            path = p.export_gdt_drawing(element_id, dest / f"{element_id}_gdt.svg")
            out["gdt"] = str(path)
        if kind in {"ortho", "all"}:
            out["ortho"] = p.export_fab_ortho(element_id, dest / "views")
        store.save(project_id)
        return _tool_result(out)

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
    def slab_create(
        project_id: str,
        level: str,
        polygon_json: str,
        thickness_mm: float = 200,
        name: str = "",
    ) -> str:
        """Create floor slab. polygon_json is [[x,y],...] mm plan polygon (≥3 pts)."""
        import json as _json

        p = store.get(project_id)
        poly = _json.loads(polygon_json)
        sid = p.create_slab(
            level=level,
            polygon=[(float(pt[0]), float(pt[1])) for pt in poly],
            thickness_mm=thickness_mm,
            name=name or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": sid, "thickness_mm": thickness_mm})

    @mcp.tool()
    def equipment_create(
        project_id: str,
        level: str,
        origin_x: float = 0,
        origin_y: float = 0,
        size_x: float = 1000,
        size_y: float = 1000,
        size_z: float = 1000,
        name: str = "",
        kind: str = "equipment",
        shape: str = "box",
        z0_mm: float = 0,
        centered: bool = False,
    ) -> str:
        """Place equipment envelope (box or cylinder). size is Lx,Ly,Hz mm; cylinder Ly=diameter."""
        p = store.get(project_id)
        eid = p.create_equipment_box(
            level=level,
            origin=(origin_x, origin_y),
            size=(size_x, size_y, size_z),
            name=name or None,
            kind=kind or "equipment",
            shape=shape or "box",
            z0_mm=z0_mm,
            centered=centered,
        )
        store.save(project_id)
        return _tool_result({"element_id": eid, "kind": kind, "shape": shape})

    @mcp.tool()
    def auto_place(
        project_id: str,
        room: str,
        items_json: str,
        clearance_mm: float = 900,
        aisle_mm: float = 1200,
        strategy: str = "perimeter",
    ) -> str:
        """Requirements-driven equipment auto-placement — coordinates DERIVED from
        room assignment, footprints, and clearances (deterministic; placed elements
        tagged placement_basis for design review). room: room element id or name.
        items_json: JSON list of {name, w_mm, d_mm, h_mm, kind?, clearance_front_mm?,
        against_wall?}. strategy: perimeter (back-to-wall, skips door swings and
        existing equipment) | grid (interior rows with aisle circulation). Items
        that cannot fit are returned in result.unplaced with a reason."""
        import json as _json

        try:
            p = store.get(project_id)
            items = _json.loads(items_json)
            r = p.auto_place(
                room=room,
                items=items,
                clearance_mm=clearance_mm,
                aisle_mm=aisle_mm,
                strategy=strategy,
            )
            store.save(project_id)
            return _tool_result(r)
        except Exception as e:  # noqa: BLE001
            return _err(str(e))

    @mcp.tool()
    def level_add(project_id: str, name: str, elevation_mm: float) -> str:
        p = store.get(project_id)
        lid = p.add_level(name, elevation_mm)
        store.save(project_id)
        return _tool_result({"level_id": lid})

    @mcp.tool()
    def grid_add(
        project_id: str,
        axis: str = "U",
        positions_json: str = "[0,6000,12000]",
        name: str = "",
        labels_json: str = "",
    ) -> str:
        """Add structural grid. axis U=const X (1,2,3), V=const Y (A,B,C). positions_json mm list."""
        import json as _json

        p = store.get(project_id)
        positions = _json.loads(positions_json)
        labels = _json.loads(labels_json) if labels_json.strip() else None
        gid = p.add_grid(
            axis=axis,
            positions_mm=[float(x) for x in positions],
            name=name or None,
            labels=[str(x) for x in labels] if labels else None,
        )
        store.save(project_id)
        return _tool_result({"element_id": gid, "axis": axis.upper(), "count": len(positions)})

    @mcp.tool()
    def note_create(
        project_id: str,
        level: str,
        text: str,
        x: float = 0,
        y: float = 0,
        name: str = "",
    ) -> str:
        """Place plan text note at (x,y) mm — appears on plan SVG notes layer."""
        p = store.get(project_id)
        nid = p.create_note(
            level=level,
            text=text,
            position=(x, y),
            name=name or None,
        )
        store.save(project_id)
        return _tool_result({"element_id": nid, "text": text[:80]})

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
