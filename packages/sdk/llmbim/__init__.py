"""Public LLM-BIM SDK — the surface agents should import."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llmbim_core.annotations import CreateNote, SetElementPhase, SetElementType
from llmbim_core.commands import (
    AddGrid,
    AddLevel,
    CreateEquipmentBox,
    CreateRoom,
    CreateSlab,
    CreateWall,
    DeleteElement,
    PlaceDoor,
    PlaceWindow,
    TransactionLog,
)
from llmbim_core.model import Element, Level, ProjectModel

__version__ = "0.1.0a0"


class Project:
    """Agent-facing project facade.

    All mutations go through the command bus so undo/redo stays consistent.
    """

    def __init__(self, model: ProjectModel, log: TransactionLog | None = None) -> None:
        self._model = model
        self._log = log or TransactionLog()

    @classmethod
    def create(cls, name: str = "Untitled", units: str = "mm") -> Project:
        if units != "mm":
            raise ValueError("MVP only supports units='mm'")
        return cls(ProjectModel(name=name, units=units))

    @classmethod
    def open(cls, path: str | Path) -> Project:
        return cls(ProjectModel.open(path))

    def save(self, path: str | Path) -> None:
        self._model.save(path)

    @property
    def name(self) -> str:
        return self._model.name

    @property
    def model(self) -> ProjectModel:
        """Low-level model (prefer high-level methods in agent code)."""
        return self._model

    def execute(self, command: Any) -> dict[str, Any]:
        """Apply a low-level command (advanced agents / tests)."""
        return self._log.execute(self._model, command)

    def add_level(self, name: str, elevation_mm: float) -> str:
        result = self._log.execute(self._model, AddLevel(name=name, elevation_mm=elevation_mm))
        return str(result["result"]["level_id"])

    def add_grid(self, axis: str, positions_mm: list[float], name: str | None = None) -> str:
        result = self._log.execute(
            self._model,
            AddGrid(axis=axis, positions_mm=positions_mm, name=name or ""),
        )
        return str(result["result"]["element_id"])

    def create_wall(
        self,
        *,
        level: str,
        start: tuple[float, float],
        end: tuple[float, float],
        thickness_mm: float | None = None,
        height_mm: float | None = None,
        name: str | None = None,
        unit: str | None = None,
        thickness: float | None = None,
        height: float | None = None,
        type_id: str | None = None,
    ) -> str:
        from llmbim_core.units import parse_length, point_to_mm

        u = unit or self._model.units or "mm"
        s = point_to_mm(start, u)
        e = point_to_mm(end, u)
        th = parse_length(thickness_mm if thickness_mm is not None else (thickness if thickness is not None else 200), u)
        ht = parse_length(height_mm if height_mm is not None else (height if height is not None else 3000), u)
        result = self._log.execute(
            self._model,
            CreateWall(
                level=level,
                start=s,
                end=e,
                thickness_mm=th,
                height_mm=ht,
                name=name or "",
            ),
        )
        eid = str(result["result"]["element_id"])
        if type_id:
            self.set_type(eid, type_id)
        return eid

    def create_slab(
        self,
        *,
        level: str,
        polygon: list[tuple[float, float]],
        thickness_mm: float,
        name: str | None = None,
    ) -> str:
        result = self._log.execute(
            self._model,
            CreateSlab(
                level=level,
                polygon=polygon,
                thickness_mm=thickness_mm,
                name=name or "",
            ),
        )
        return str(result["result"]["element_id"])

    def place_door(
        self,
        *,
        host: str,
        offset_mm: float,
        width_mm: float,
        height_mm: float,
        name: str | None = None,
    ) -> str:
        result = self._log.execute(
            self._model,
            PlaceDoor(
                host=host,
                offset_mm=offset_mm,
                width_mm=width_mm,
                height_mm=height_mm,
                name=name or "",
            ),
        )
        return str(result["result"]["element_id"])

    def place_window(
        self,
        *,
        host: str,
        offset_mm: float,
        width_mm: float,
        height_mm: float,
        sill_mm: float,
        name: str | None = None,
    ) -> str:
        result = self._log.execute(
            self._model,
            PlaceWindow(
                host=host,
                offset_mm=offset_mm,
                width_mm=width_mm,
                height_mm=height_mm,
                sill_mm=sill_mm,
                name=name or "",
            ),
        )
        return str(result["result"]["element_id"])

    def create_room(
        self,
        *,
        level: str,
        name: str,
        boundary: list[tuple[float, float]],
    ) -> str:
        result = self._log.execute(
            self._model,
            CreateRoom(level=level, name=name, boundary=boundary),
        )
        return str(result["result"]["element_id"])

    def create_equipment_box(
        self,
        *,
        level: str,
        origin: tuple[float, float],
        size: tuple[float, float, float],
        name: str | None = None,
        kind: str = "equipment",
        centered: bool = False,
        z0_mm: float = 0.0,
        shape: str = "box",
    ) -> str:
        """Place equipment envelope: shape ``box`` or ``cylinder`` (along +X)."""
        result = self._log.execute(
            self._model,
            CreateEquipmentBox(
                level=level,
                origin=origin,
                size=size,
                name=name or "",
                kind=kind,
                centered=centered,
                z0_mm=z0_mm,
                shape=shape,
            ),
        )
        return str(result["result"]["element_id"])

    def create_rect_shell(
        self,
        *,
        level: str,
        x: float,
        y: float,
        w: float,
        d: float,
        height_mm: float,
        thickness_mm: float = 300,
        name_prefix: str = "W",
    ) -> list[str]:
        """Four walls forming a rectangular room/building footprint (mm)."""
        corners = [
            ((x, y), (x + w, y), f"{name_prefix}-S"),
            ((x + w, y), (x + w, y + d), f"{name_prefix}-E"),
            ((x + w, y + d), (x, y + d), f"{name_prefix}-N"),
            ((x, y + d), (x, y), f"{name_prefix}-W"),
        ]
        ids: list[str] = []
        for start, end, nm in corners:
            ids.append(
                self.create_wall(
                    level=level,
                    start=start,
                    end=end,
                    thickness_mm=thickness_mm,
                    height_mm=height_mm,
                    name=nm,
                )
            )
        return ids

    def delete_element(self, element_id: str, *, cascade: bool = True) -> None:
        self._log.execute(self._model, DeleteElement(element_id=element_id, cascade=cascade))

    def create_note(
        self, *, level: str, text: str, position: tuple[float, float], name: str | None = None
    ) -> str:
        result = self._log.execute(
            self._model,
            CreateNote(level=level, text=text, position=position, name=name or ""),
        )
        return str(result["result"]["element_id"])

    def set_type(self, element_id: str, type_id: str) -> None:
        self._log.execute(self._model, SetElementType(element_id=element_id, type_id=type_id))

    def set_phase(self, element_id: str, phase: str) -> None:
        self._log.execute(self._model, SetElementPhase(element_id=element_id, phase=phase))

    def boq(self) -> dict[str, Any]:
        from llmbim_core.quantities import boq_summary, compute_boq

        rows = compute_boq(self._model)
        return {"summary": boq_summary(rows), "lines": rows}

    def export_boq(self, path: str | Path, *, fmt: str = "json") -> None:
        from llmbim_core.quantities import export_boq_csv, export_boq_json

        if fmt == "csv":
            export_boq_csv(self._model, path)
        else:
            export_boq_json(self._model, path)

    def clash(self) -> list[dict[str, Any]]:
        from llmbim_core.clash import find_clashes

        return find_clashes(self._model)

    def design_rules(self) -> dict[str, Any]:
        from llmbim_core.rules import rules_summary, run_design_rules

        findings = run_design_rules(self._model)
        return {"summary": rules_summary(findings), "findings": findings}

    def export_dxf(self, level: str, path: str | Path) -> None:
        from llmbim_drawings.dxf_export import export_plan_dxf

        export_plan_dxf(self._model, level, path)

    def export_pdf_binder(self, sheet_dir: str | Path, path: str | Path, **kw: Any) -> None:
        from llmbim_drawings.pdf_binder import export_pdf_binder

        export_pdf_binder(sheet_dir, path, title=self.name, **kw)

    def import_step(
        self,
        step_path: str | Path,
        *,
        level: str,
        name: str | None = None,
        kind: str = "step_ref",
        copy_into: str | Path | None = None,
    ) -> str:
        """Import Fusion/CAD STEP as locked equipment envelope + file reference."""
        from llmbim_geometry.step_import import import_step_as_equipment

        el = import_step_as_equipment(
            self._model,
            step_path,
            level=level,
            name=name,
            kind=kind,
            copy_into=copy_into,
        )
        return el.id

    def catalog(self) -> dict[str, Any]:
        from llmbim_core.types_catalog import catalog_dict

        return catalog_dict()

    @classmethod
    def from_template(cls, template_id: str, name: str | None = None, **kwargs: Any) -> Project:
        from llmbim_templates import apply_template

        p = cls.create(name or template_id)
        return apply_template(template_id, p, **kwargs)

    def undo(self) -> dict[str, Any]:
        return self._log.undo(self._model)

    def redo(self) -> dict[str, Any]:
        return self._log.redo(self._model)

    def query(self, q: str | None = None, **filters: str) -> list[Element]:
        """Query by kwargs or query language string: ``category=wall level=L1``."""
        if q:
            from llmbim_core.query_lang import run_query

            return run_query(self._model, q)
        return self._model.query(**filters)  # type: ignore[arg-type]

    def stats(self) -> dict[str, int]:
        return self._model.stats()

    def op(self, op_name: str, **params: Any) -> dict[str, Any]:
        """Dispatch a registered operation by name (extensible agent surface)."""
        from llmbim_core.registry import dispatch

        return dispatch(self._model, op_name, params)

    def ops(self) -> list[dict[str, Any]]:
        from llmbim_core.registry import list_ops

        return list_ops()

    def repair(self) -> dict[str, Any]:
        from llmbim_core.repair import repair_model

        return repair_model(self._model)

    def create_generic(
        self,
        category: str,
        *,
        level: str | None = None,
        name: str = "",
        params: dict[str, Any] | None = None,
        **kw: Any,
    ) -> str:
        """Create any category of element (open vocabulary for unknown domains)."""
        r = self.op(
            "create_generic",
            category=category,
            level=level,
            name=name,
            params={**(params or {}), **{k: v for k, v in kw.items() if k != "name"}},
        )
        # flatten kw into params for convenience
        if kw:
            el = self.model.get_element(str(r["id"]))
            el.params.update(kw)
        return str(r["id"])

    def import_file(self, path: str | Path, **kwargs: Any) -> dict[str, Any]:
        """Auto-import by extension: .json/.csv/.dxf/.ifc/.step/.llmbim.json."""
        from llmbim_core.io_import import auto_import

        return auto_import(self._model, path, **kwargs)

    def run_script(self, source: str | Path, *, outfile: str | Path | None = None) -> dict[str, Any]:
        from llmbim_core.script_runner import run_script

        result = run_script(source, project=self, outfile=outfile)
        return {k: v for k, v in result.items() if k != "project"}

    def bulk(self, ops: list[dict[str, Any]]) -> dict[str, Any]:
        """Apply a list of {op, ...} mutations/queries."""
        import json
        import tempfile
        from pathlib import Path as P

        from llmbim_core.io_import import import_json_batch

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(ops, f)
            tmp = f.name
        try:
            return import_json_batch(self._model, tmp)
        finally:
            P(tmp).unlink(missing_ok=True)

    def create_assembly(
        self,
        name: str,
        element_ids: list[str] | None = None,
        *,
        kind: str = "group",
    ) -> str:
        r = self.op(
            "create_assembly",
            name=name,
            element_ids=element_ids or [],
            kind=kind,
        )
        return str(r["assembly_id"])

    def assemblies(self) -> list[dict[str, Any]]:
        return self.op("list_assemblies").get("assemblies", [])

    def design_option(
        self,
        name: str,
        element_ids: list[str] | None = None,
        *,
        clone: bool = True,
    ) -> dict[str, Any]:
        """Create a design option (optional clone of elements)."""
        return self.op(
            "design_option",
            name=name,
            element_ids=element_ids or [],
            clone=clone,
        )

    def levels(self) -> list[Level]:
        return list(self._model.levels)

    def export_plan(self, level: str, path: str | Path, **opts: Any) -> None:
        from llmbim_drawings import export_plan_svg

        export_plan_svg(self._model, level, path, **opts)

    def export_section(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        path: str | Path,
        **opts: Any,
    ) -> None:
        from llmbim_drawings import export_section_svg

        export_section_svg(self._model, p0, p1, path, **opts)

    def export_elevation(self, direction: str, path: str | Path, **opts: Any) -> None:
        from llmbim_drawings import export_elevation_svg

        export_elevation_svg(self._model, direction, path, **opts)

    def export_gltf(self, path: str | Path) -> None:
        from llmbim_geometry.mesh import export_gltf_walls

        export_gltf_walls(self._model, path)

    def validate(self) -> list[dict[str, Any]]:
        from llmbim_core.validate import validate_model

        return [i.to_dict() for i in validate_model(self._model)]

    def export_ifc(self, path: str | Path) -> None:
        from llmbim_ifc import export_ifc

        export_ifc(self._model, path)

    def export_step(self, path: str | Path, *, include_walls: bool = True) -> None:
        from llmbim_geometry.step_export import export_step

        export_step(self._model, path, include_walls=include_walls)

    def export_construction_set(
        self, out_dir: str | Path, *, plan_level: str | None = None, plan_scale: float = 0.02
    ) -> dict[str, Any]:
        from llmbim_drawings.construction import export_construction_set

        return export_construction_set(
            self._model, out_dir, plan_level=plan_level, plan_scale=plan_scale
        )

    def export_part_pack(self, out_dir: str | Path, *, scale: float = 0.4) -> dict[str, Any]:
        from llmbim_drawings.parts import export_part_pack

        return export_part_pack(self._model, out_dir, scale=scale)

    def export_deliverables(
        self,
        out_dir: str | Path | None = None,
        *,
        mode: str = "auto",
        plan_level: str | None = None,
        plan_scale: float | None = None,
    ) -> dict[str, Any]:
        """Full pack: JSON + IFC + glTF + STEP + construction and/or part sheets.

        If ``out_dir`` is omitted, writes to ``output/<project_slug>/`` in the repo.
        """
        from llmbim_core.paths import project_output_dir
        from llmbim_drawings.deliverables import export_deliverables

        dest = Path(out_dir) if out_dir else project_output_dir(self.name)
        result = export_deliverables(
            self._model,
            dest,
            mode=mode,
            plan_level=plan_level,
            plan_scale=plan_scale,
        )
        result["output_dir"] = str(dest.resolve())
        return result

    def save_local(self, name: str | None = None) -> Path:
        """Save project JSON under output/<slug>/model.llmbim.json."""
        from llmbim_core.paths import project_output_dir

        d = project_output_dir(name or self.name)
        path = d / "model.llmbim.json"
        self.save(path)
        return path


__all__ = ["Project", "Element", "Level", "ProjectModel", "__version__"]
