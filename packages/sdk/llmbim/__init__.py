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
    Version control (commit/log/checkout/diff) tracks *true model states*,
    not chat history.
    """

    def __init__(
        self,
        model: ProjectModel,
        log: TransactionLog | None = None,
        *,
        vcs_dir: str | Path | None = None,
        author: str = "agent",
    ) -> None:
        self._model = model
        self._log = log or TransactionLog()
        self._vcs = None
        self._author = author
        if vcs_dir is not None:
            self.bind_vcs(vcs_dir)

    @classmethod
    def create(
        cls,
        name: str = "Untitled",
        units: str = "mm",
        *,
        vcs: bool = True,
        author: str = "agent",
    ) -> Project:
        if units != "mm":
            # still allow via units module on walls; project store unit is mm
            pass
        p = cls(ProjectModel(name=name, units="mm"), author=author)
        if vcs:
            from llmbim_core.paths import project_output_dir
            from llmbim_core.versioning import init_vcs

            d = project_output_dir(name)
            p._vcs = init_vcs(d, p._model, message="initial commit")
            p._author = author
        return p

    @classmethod
    def open(cls, path: str | Path, *, author: str = "agent") -> Project:
        path = Path(path)
        # open file or project directory
        if path.is_dir():
            model_path = path / "model.llmbim.json"
            proj = cls(ProjectModel.open(model_path), author=author)
            proj.bind_vcs(path)
            return proj
        model = ProjectModel.open(path)
        proj = cls(model, author=author)
        # if sibling .llmbim exists, bind
        if (path.parent / ".llmbim").is_dir():
            proj.bind_vcs(path.parent)
        return proj

    def bind_vcs(self, project_dir: str | Path) -> None:
        """Attach version control to a directory (creates .llmbim/)."""
        from llmbim_core.versioning import ModelVCS

        self._vcs = ModelVCS(project_dir)
        # ensure working copy exists
        if not self._vcs.model_path.exists():
            self._model.save(self._vcs.model_path)

    @property
    def vcs_dir(self) -> Path | None:
        return self._vcs.project_dir if self._vcs else None

    def save(self, path: str | Path | None = None) -> None:
        if path is not None:
            self._model.save(path)
        elif self._vcs is not None:
            self._model.save(self._vcs.model_path)
        else:
            raise ValueError("No path: pass path= or bind_vcs / create(vcs=True)")

    @property
    def name(self) -> str:
        return self._model.name

    @property
    def model(self) -> ProjectModel:
        """Low-level model (prefer high-level methods in agent code)."""
        return self._model

    def execute(self, command: Any) -> dict[str, Any]:
        """Apply a low-level command (advanced agents / tests). Logs to VCS journal."""
        result = self._log.execute(self._model, command)
        if self._vcs is not None:
            op = getattr(command, "op", type(command).__name__)
            summary = result.get("result") if isinstance(result, dict) else {}
            if not isinstance(summary, dict):
                summary = {"result": summary}
            self._vcs.append_journal(str(op), summary, author=self._author)
        return result

    # --- version control ------------------------------------------------------

    def commit(self, message: str, *, author: str | None = None, allow_empty: bool = False) -> dict[str, Any]:
        """Create a true model version (full snapshot + parent + hash). Required after chat edits."""
        if self._vcs is None:
            from llmbim_core.paths import project_output_dir
            from llmbim_core.versioning import init_vcs

            self._vcs = init_vcs(project_output_dir(self.name), self._model, message="initial commit")
        return self._vcs.commit(
            self._model,
            message,
            author=author or self._author,
            allow_empty=allow_empty,
        )

    def log(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if self._vcs is None:
            return []
        return self._vcs.log(limit=limit)

    def history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Alias for log() — committed model versions."""
        return self.log(limit=limit)

    def status(self) -> dict[str, Any]:
        if self._vcs is None:
            return {"clean": True, "head": None, "message": "VCS not bound"}
        return self._vcs.status(self._model)

    def checkout(self, version_id: str) -> dict[str, Any]:
        """Restore model to a committed version. Discards uncommitted working changes."""
        if self._vcs is None:
            raise RuntimeError("VCS not bound — open a project dir or create(vcs=True)")
        self._model = self._vcs.checkout(version_id, author=self._author)
        self._log = TransactionLog()  # reset undo stack after checkout
        return {"version_id": version_id, "stats": self._model.stats(), "head": self._vcs.head()}

    def diff(self, version_a: str | None = None, version_b: str | None = None) -> dict[str, Any]:
        """Diff versions (default: HEAD vs working tree)."""
        if self._vcs is None:
            return {"summary": {}, "note": "VCS not bound"}
        return self._vcs.diff(version_a, version_b, model=self._model)

    def tag(self, name: str, version_id: str | None = None) -> dict[str, Any]:
        if self._vcs is None:
            raise RuntimeError("VCS not bound")
        return self._vcs.tag(name, version_id)

    def journal(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Append-only mutation journal (finer than commits)."""
        if self._vcs is None:
            return []
        entries = self._vcs.read_journal()
        return entries[-limit:]

    def add_level(self, name: str, elevation_mm: float) -> str:
        result = self._log.execute(self._model, AddLevel(name=name, elevation_mm=elevation_mm))
        return str(result["result"]["level_id"])

    def add_grid(
        self,
        axis: str,
        positions_mm: list[float],
        name: str | None = None,
        labels: list[str] | None = None,
    ) -> str:
        """Add structural grid. axis U → 1,2,3…; V → A,B,C… (or pass labels)."""
        result = self._log.execute(
            self._model,
            AddGrid(
                axis=axis,
                positions_mm=positions_mm,
                name=name or "",
                labels=labels,
            ),
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
        fire_rating: str | None = None,
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
                fire_rating=fire_rating or "",
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
        type_id: str | None = None,
        fire_rating: str | None = None,
    ) -> str:
        result = self._log.execute(
            self._model,
            PlaceDoor(
                host=host,
                offset_mm=offset_mm,
                width_mm=width_mm,
                height_mm=height_mm,
                name=name or "",
                type_id=type_id or "",
                fire_rating=fire_rating or "",
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
        type_id: str | None = None,
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
                type_id=type_id or "",
            ),
        )
        return str(result["result"]["element_id"])

    def create_room(
        self,
        *,
        level: str,
        name: str,
        boundary: list[tuple[float, float]],
        height_mm: float | None = None,
        ceiling_height_mm: float | None = None,
    ) -> str:
        """Create room space. Optional clear height (ceiling_height_mm alias)."""
        result = self._log.execute(
            self._model,
            CreateRoom(
                level=level,
                name=name,
                boundary=boundary,
                height_mm=height_mm,
                ceiling_height_mm=ceiling_height_mm,
            ),
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

    def export_elevation_dxf(self, direction: str, path: str | Path) -> None:
        """Elevation DXF (X=plan axis, Y=Z elev mm) for CAD handoff."""
        from llmbim_drawings.dxf_export import export_elevation_dxf

        export_elevation_dxf(self._model, direction, path)

    def export_section_dxf(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        path: str | Path,
    ) -> None:
        """Section DXF along plan cut p0→p1 (X=distance along cut, Y=Z elev)."""
        from llmbim_drawings.dxf_export import export_section_dxf

        export_section_dxf(self._model, p0, p1, path)

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

    def materials_catalog(self) -> dict[str, Any]:
        from llmbim_core.materials import materials_catalog

        return materials_catalog()

    def parts_catalog(
        self,
        *,
        category: str | None = None,
        fitting_type: str | None = None,
        nps: str | None = None,
        material: str | None = None,
    ) -> list[dict[str, Any]]:
        from llmbim_core.parts_catalog import list_parts

        return [
            p.model_dump()
            for p in list_parts(
                category=category,
                fitting_type=fitting_type,
                nps=nps,
                material=material,
            )
        ]

    def assign_material(self, element_id: str, material_id: str, *, role: str = "primary") -> dict[str, Any]:
        from llmbim_core.assign_commands import AssignMaterial

        return self.execute(AssignMaterial(element_id=element_id, material_id=material_id, role=role))

    def assign_part(
        self,
        element_id: str,
        part_id: str,
        *,
        qty: float | None = None,
        apply_geometry: bool = False,
    ) -> dict[str, Any]:
        from llmbim_core.assign_commands import AssignPart

        return self.execute(
            AssignPart(element_id=element_id, part_id=part_id, qty=qty, apply_geometry=apply_geometry)
        )

    def auto_assign(self) -> dict[str, Any]:
        """Assign materials/parts from wall types and equipment kind."""
        return self.op("auto_assign")

    def place_fitting(
        self,
        *,
        level: str,
        fitting_type: str,
        nps: str,
        origin: tuple[float, float] = (0.0, 0.0),
        name: str | None = None,
        material: str = "copper",
        qty: float = 1.0,
        system: str = "CW",
    ) -> str:
        """Place fitting. material: copper | fire | process | pvc."""
        r = self.op(
            "place_fitting",
            level=level,
            fitting_type=fitting_type,
            nps=nps,
            origin=list(origin),
            name=name,
            material=material,
            qty=qty,
            system=system,
        )
        return str(r["element_id"])

    def place_pipe(
        self,
        *,
        level: str,
        nps: str,
        start: tuple[float, float],
        end: tuple[float, float],
        name: str | None = None,
        material: str = "copper",
        system: str = "CW",
        z0_mm: float = 0.0,
    ) -> str:
        """Place pipe. material: copper | fire (black steel) | process (SS316) | pvc."""
        r = self.op(
            "place_pipe",
            level=level,
            nps=nps,
            start=list(start),
            end=list(end),
            name=name,
            material=material,
            system=system,
            z0_mm=z0_mm,
        )
        return str(r["element_id"])

    def place_riser(
        self,
        *,
        level: str,
        nps: str,
        origin: tuple[float, float],
        z0_mm: float | None = None,
        z1_mm: float | None = None,
        name: str | None = None,
        material: str = "copper",
        system: str = "CW",
        to_level: str | None = None,
    ) -> str:
        """Vertical pipe riser at plan XY. Use to_level='L2' for multi-storey span."""
        kwargs: dict[str, Any] = {
            "level": level,
            "nps": nps,
            "origin": list(origin),
            "name": name,
            "material": material,
            "system": system,
        }
        if z0_mm is not None:
            kwargs["z0_mm"] = z0_mm
        if z1_mm is not None:
            kwargs["z1_mm"] = z1_mm
        if to_level:
            kwargs["to_level"] = to_level
        r = self.op("place_riser", **kwargs)
        return str(r["element_id"])

    def place_part(
        self,
        *,
        level: str,
        part_id: str | None = None,
        origin: tuple[float, float] = (0.0, 0.0),
        name: str | None = None,
        qty: float = 1.0,
        length_m: float | None = None,
        kind: str | None = None,
        section: str | None = None,
        bar_size: str | None = None,
    ) -> str:
        """Place any catalog part: toilet, tp_dispenser, W10x33, rebar #5, …"""
        r = self.op(
            "place_part",
            level=level,
            part_id=part_id,
            origin=list(origin),
            name=name,
            qty=qty,
            length_m=length_m,
            kind=kind,
            section=section,
            bar_size=bar_size,
        )
        return str(r["element_id"])

    def place_duct(
        self,
        *,
        level: str,
        start: tuple[float, float],
        end: tuple[float, float],
        width_mm: float = 400.0,
        height_mm: float = 250.0,
        name: str | None = None,
        system: str = "SA",
        z0_mm: float = 2700.0,
        material: str = "galv_steel",
    ) -> str:
        """Rectangular HVAC duct (CSI 23 31 00). Takeoff includes length_m + area_m2."""
        r = self.op(
            "place_duct",
            level=level,
            start=list(start),
            end=list(end),
            width_mm=width_mm,
            height_mm=height_mm,
            name=name,
            system=system,
            z0_mm=z0_mm,
            material=material,
        )
        return str(r["element_id"])

    def place_column(
        self,
        *,
        level: str,
        origin: tuple[float, float] = (0.0, 0.0),
        section: str = "W10x33",
        height_mm: float = 3000.0,
        name: str | None = None,
        material: str = "steel_A36",
        rotation_deg: float = 0.0,
    ) -> str:
        """Structural steel column (vertical). CSI 05 12 00."""
        r = self.op(
            "place_column",
            level=level,
            origin=list(origin),
            section=section,
            height_mm=height_mm,
            name=name,
            material=material,
            rotation_deg=rotation_deg,
        )
        return str(r["element_id"])

    def place_beam(
        self,
        *,
        level: str,
        start: tuple[float, float],
        end: tuple[float, float],
        section: str = "W12x26",
        name: str | None = None,
        material: str = "steel_A36",
        z0_mm: float | None = None,
    ) -> str:
        """Structural steel beam along plan start→end. CSI 05 12 00."""
        r = self.op(
            "place_beam",
            level=level,
            start=list(start),
            end=list(end),
            section=section,
            name=name,
            material=material,
            z0_mm=z0_mm,
        )
        return str(r["element_id"])

    def place_cable_tray(
        self,
        *,
        level: str,
        start: tuple[float, float],
        end: tuple[float, float],
        width_mm: float = 300.0,
        height_mm: float = 100.0,
        name: str | None = None,
        system: str = "PWR",
        z0_mm: float = 2900.0,
        material: str = "galv_steel",
    ) -> str:
        """Place cable tray run. CSI 26 05 36."""
        r = self.op(
            "place_cable_tray",
            level=level,
            start=list(start),
            end=list(end),
            width_mm=width_mm,
            height_mm=height_mm,
            name=name,
            system=system,
            z0_mm=z0_mm,
            material=material,
        )
        return str(r["element_id"])

    def place_conduit(
        self,
        *,
        level: str,
        start: tuple[float, float],
        end: tuple[float, float],
        trade_size: str = "3/4",
        name: str | None = None,
        system: str = "P",
        z0_mm: float = 2800.0,
        material: str = "steel_A36",
    ) -> str:
        """Electrical conduit run (CSI 26 05 33). trade_size e.g. 3/4, 1, 2."""
        r = self.op(
            "place_conduit",
            level=level,
            start=list(start),
            end=list(end),
            trade_size=trade_size,
            name=name,
            system=system,
            z0_mm=z0_mm,
            material=material,
        )
        return str(r["element_id"])

    def place_wire(
        self,
        *,
        level: str,
        start: tuple[float, float],
        end: tuple[float, float],
        diameter_mm: float = 6.0,
        name: str | None = None,
        material: str = "copper",
        system: str = "PWR",
        z0_mm: float = 2900.0,
    ) -> str:
        """Thin wire/conductor run (CSI 26 05 19) — renders as fine cylinder."""
        r = self.op(
            "place_wire",
            level=level,
            start=list(start),
            end=list(end),
            diameter_mm=diameter_mm,
            name=name,
            material=material,
            system=system,
            z0_mm=z0_mm,
        )
        return str(r["element_id"])

    def place_coil(
        self,
        *,
        level: str,
        origin: tuple[float, float] = (0.0, 0.0),
        coil_radius_mm: float = 80.0,
        tube_radius_mm: float = 8.0,
        turns: float = 6.0,
        pitch_mm: float = 24.0,
        name: str | None = None,
        material: str = "copper",
        system: str = "PROC",
        z0_mm: float = 1000.0,
        orientation: str = "vertical",
    ) -> str:
        """Helical coil / wound conductor (CSI 23 82 16)."""
        r = self.op(
            "place_coil",
            level=level,
            origin=list(origin),
            coil_radius_mm=coil_radius_mm,
            tube_radius_mm=tube_radius_mm,
            turns=turns,
            pitch_mm=pitch_mm,
            name=name,
            material=material,
            system=system,
            z0_mm=z0_mm,
            orientation=orientation,
        )
        return str(r["element_id"])

    def place_bolt(
        self,
        *,
        level: str,
        origin: tuple[float, float] = (0.0, 0.0),
        shank_d_mm: float = 20.0,
        shank_len_mm: float = 60.0,
        grade: str = "A325",
        name: str | None = None,
        z0_mm: float = 0.0,
        orientation: str = "vertical",
    ) -> str:
        """Structural bolt hex head + shank (CSI 05 12 23)."""
        r = self.op(
            "place_bolt",
            level=level,
            origin=list(origin),
            shank_d_mm=shank_d_mm,
            shank_len_mm=shank_len_mm,
            grade=grade,
            name=name,
            z0_mm=z0_mm,
            orientation=orientation,
        )
        return str(r["element_id"])

    def place_flange(
        self,
        *,
        level: str,
        origin: tuple[float, float] = (0.0, 0.0),
        od_mm: float = 150.0,
        thickness_mm: float = 18.0,
        name: str | None = None,
        material: str = "steel_A36",
        system: str = "PROC",
        z0_mm: float = 1000.0,
    ) -> str:
        """Joined flange / ring section at a joint (CSI 40 05 13)."""
        r = self.op(
            "place_flange",
            level=level,
            origin=list(origin),
            od_mm=od_mm,
            thickness_mm=thickness_mm,
            name=name,
            material=material,
            system=system,
            z0_mm=z0_mm,
        )
        return str(r["element_id"])

    def fitting_takeoff(
        self,
        *,
        fitting_type: str | None = None,
        nps: str | None = None,
        material: str | None = None,
        system: str | None = None,
    ) -> list[dict[str, Any]]:
        """Count fittings by type/size/system — copper 90°, fire 90°, process tees, …"""
        from llmbim_core.material_lists import fitting_takeoff

        return fitting_takeoff(
            self._model,
            fitting_type=fitting_type,
            nps=nps,
            material=material,
            system=system,
        )

    def system_takeoff(self, system: str | None = None) -> list[dict[str, Any]]:
        from llmbim_core.material_lists import system_takeoff

        return system_takeoff(self._model, system)

    def csi_takeoff(self, *, division: str | None = None) -> list[dict[str, Any]]:
        from llmbim_core.material_lists import csi_takeoff

        return csi_takeoff(self._model, division=division)

    def csi_instances(self) -> list[dict[str, Any]]:
        """Per-element MasterFormat CSI + level/XY/Z/height locator to find items."""
        from llmbim_core.csi import csi_instance_schedule

        return csi_instance_schedule(self._model)

    def fire_takeoff(self) -> dict[str, Any]:
        from llmbim_core.material_lists import fire_takeoff

        return fire_takeoff(self._model)

    def steel_takeoff(self) -> list[dict[str, Any]]:
        from llmbim_core.material_lists import steel_takeoff

        return steel_takeoff(self._model)

    def schedule(self, kind: str = "zone") -> list[dict[str, Any]]:
        """Schedule rows: level|zone|column|beam|duct|conduit|cable_tray|csi|…"""
        from llmbim_drawings.schedules import schedule_rows

        return schedule_rows(self._model, kind)

    def rebar_takeoff(self) -> list[dict[str, Any]]:
        from llmbim_core.material_lists import rebar_takeoff

        return rebar_takeoff(self._model)

    def trade_schedule(self) -> dict[str, Any]:
        from llmbim_core.material_lists import full_trade_schedule

        return full_trade_schedule(self._model)

    def pipe_takeoff(
        self,
        *,
        nps: str | None = None,
        material: str | None = None,
    ) -> list[dict[str, Any]]:
        from llmbim_core.material_lists import pipe_takeoff

        return pipe_takeoff(self._model, nps=nps, material=material)

    def duct_takeoff(self) -> list[dict[str, Any]]:
        """HVAC duct runs: length_m + area_m2 by size."""
        from llmbim_core.material_lists import duct_takeoff

        return duct_takeoff(self._model)

    def conduit_takeoff(self) -> list[dict[str, Any]]:
        """Electrical conduit length by trade size (m)."""
        from llmbim_core.material_lists import conduit_takeoff

        return conduit_takeoff(self._model)

    def cable_tray_takeoff(self) -> list[dict[str, Any]]:
        """Cable tray runs: length_m + area_m2 by width."""
        from llmbim_core.material_lists import cable_tray_takeoff

        return cable_tray_takeoff(self._model)

    def plumbing_schedule(self) -> dict[str, Any]:
        """Full plumbing takeoff: fittings by type/size + pipe lengths."""
        from llmbim_core.material_lists import plumbing_schedule

        return plumbing_schedule(self._model)

    def material_lists(self) -> dict[str, Any]:
        """In-memory material/part assignment + BOM + fitting takeoff."""
        from llmbim_core.material_lists import (
            exploded_material_bom,
            fitting_takeoff,
            material_assignment_list,
            material_summary,
            part_assignment_list,
            part_summary,
            pipe_takeoff,
            plumbing_schedule,
        )

        exploded = exploded_material_bom(self._model)
        return {
            "material_assignments": material_assignment_list(self._model),
            "part_assignments": part_assignment_list(self._model),
            "material_summary": material_summary(exploded),
            "fitting_takeoff": fitting_takeoff(self._model),
            "pipe_takeoff": pipe_takeoff(self._model),
            "part_summary": part_summary(self._model),
            "plumbing": plumbing_schedule(self._model),
        }

    def export_material_lists(self, out_dir: str | Path | None = None) -> dict[str, str]:
        from llmbim_core.material_lists import export_lists
        from llmbim_core.paths import project_output_dir

        dest = Path(out_dir) if out_dir else project_output_dir(self.name) / "materials"
        return export_lists(self._model, dest)

    @classmethod
    def from_template(cls, template_id: str, name: str | None = None, **kwargs: Any) -> Project:
        from llmbim_templates import apply_template

        p = cls.create(name or template_id, vcs=True)
        apply_template(template_id, p, **kwargs)
        # template mutates after initial commit — leave dirty for agent to commit
        return p

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

        result = dispatch(self._model, op_name, params)
        if self._vcs is not None:
            self._vcs.append_journal(op_name, {"params": params, "result": result}, author=self._author)
        return result

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

    def export_viewer_3d(self, out_dir: str | Path, *, embed: bool = True) -> Path | None:
        """Write model.gltf (if missing) + viewer3d.html orbit review with layer opacity toggles."""
        from llmbim_drawings.viewer3d import write_viewer_3d
        from llmbim_geometry.mesh import export_gltf_walls

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        gltf = out / "model.gltf"
        if not gltf.is_file():
            export_gltf_walls(self._model, gltf)
        return write_viewer_3d(out, embed=embed)

    def validate(self) -> list[dict[str, Any]]:
        from llmbim_core.validate import validate_model

        return [i.to_dict() for i in validate_model(self._model)]

    def export_ifc(self, path: str | Path) -> None:
        from llmbim_ifc import export_ifc

        export_ifc(self._model, path)

    def export_step(self, path: str | Path, *, include_walls: bool = True) -> None:
        from llmbim_geometry.step_export import export_step

        export_step(self._model, path, include_walls=include_walls)

    # --- Fab BREP + GD&T (CadQuery / OpenCascade) ---------------------------------

    def create_fab_part(
        self,
        *,
        name: str = "FabPart",
        material: str = "steel_A36",
        level: str | None = None,
        origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> str:
        """Create fab-grade BREP part (feature tree + GD&T). Requires cadquery extra."""
        r = self.op(
            "create_fab_part",
            name=name,
            material=material,
            level=level,
            origin_mm=list(origin),
        )
        return str(r["element_id"])

    def fab_box(
        self,
        element_id: str,
        size_mm: tuple[float, float, float],
        origin_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> dict[str, Any]:
        return self.op(
            "fab_box", element_id=element_id, size_mm=list(size_mm), origin_mm=list(origin_mm)
        )

    def fab_cylinder(
        self,
        element_id: str,
        *,
        diameter_mm: float,
        height_mm: float,
        origin_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
        axis: str = "z",
    ) -> dict[str, Any]:
        return self.op(
            "fab_cylinder",
            element_id=element_id,
            diameter_mm=diameter_mm,
            height_mm=height_mm,
            origin_mm=list(origin_mm),
            axis=axis,
        )

    def fab_hole(
        self,
        element_id: str,
        *,
        diameter_mm: float,
        origin_mm: tuple[float, float, float],
        depth_mm: float | None = None,
        direction: str = "down",
    ) -> dict[str, Any]:
        kw: dict[str, Any] = {
            "element_id": element_id,
            "diameter_mm": diameter_mm,
            "origin_mm": list(origin_mm),
            "direction": direction,
        }
        if depth_mm is not None:
            kw["depth_mm"] = depth_mm
        return self.op("fab_hole", **kw)

    def fab_cut_box(
        self,
        element_id: str,
        size_mm: tuple[float, float, float],
        origin_mm: tuple[float, float, float],
        *,
        rotate_z_deg: float = 0.0,
        rotate_deg: tuple[float, float, float] | None = None,
        center: bool | None = None,
    ) -> dict[str, Any]:
        """Boolean pocket cut; use ``rotate_z_deg`` for radial slots on a tube."""
        kw: dict[str, Any] = {
            "element_id": element_id,
            "size_mm": list(size_mm),
            "origin_mm": list(origin_mm),
            "rotate_z_deg": rotate_z_deg,
        }
        if rotate_deg is not None:
            kw["rotate_deg"] = list(rotate_deg)
        if center is not None:
            kw["center"] = center
        return self.op("fab_cut_box", **kw)

    def fab_fillet(
        self, element_id: str, *, radius_mm: float, selector: str = "|Z"
    ) -> dict[str, Any]:
        """Ease edges (fillet) on fab BREP."""
        return self.op(
            "fab_fillet", element_id=element_id, radius_mm=radius_mm, selector=selector
        )

    def fab_chamfer(
        self, element_id: str, *, distance_mm: float, selector: str = ">Z"
    ) -> dict[str, Any]:
        return self.op(
            "fab_chamfer", element_id=element_id, distance_mm=distance_mm, selector=selector
        )

    def fab_thread(
        self,
        element_id: str,
        *,
        designation: str = "M10x1.5",
        length_mm: float = 20.0,
        origin_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
        internal: bool = False,
    ) -> dict[str, Any]:
        """Machine thread (ISO metric designation e.g. M10x1.5)."""
        return self.op(
            "fab_thread",
            element_id=element_id,
            designation=designation,
            length_mm=length_mm,
            origin_mm=list(origin_mm),
            internal=internal,
        )

    def gdt_datum(
        self, element_id: str, *, label: str = "A", face: str = "bottom", note: str = ""
    ) -> dict[str, Any]:
        return self.op("gdt_datum", element_id=element_id, label=label, face=face, note=note)

    def gdt_fcf(
        self,
        element_id: str,
        *,
        symbol: str,
        tolerance: float,
        datums: list[str] | None = None,
        diameter: bool = False,
        applies_to: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        """GD&T feature control frame (position, flatness, perpendicularity, …)."""
        return self.op(
            "gdt_fcf",
            element_id=element_id,
            symbol=symbol,
            tolerance=tolerance,
            datums=datums or [],
            diameter=diameter,
            applies_to=applies_to,
            note=note,
        )

    def gdt_size(
        self,
        element_id: str,
        *,
        dimension: str,
        nominal: float,
        tol_plus: float,
        tol_minus: float | None = None,
        unit: str = "mm",
    ) -> dict[str, Any]:
        return self.op(
            "gdt_size",
            element_id=element_id,
            dimension=dimension,
            nominal=nominal,
            tol_plus=tol_plus,
            tol_minus=tol_minus,
            unit=unit,
        )

    def export_fab_step(self, element_id: str, path: str | Path) -> dict[str, Any]:
        """Export fab_part as true OpenCascade STEP BREP."""
        return self.op("export_fab_step", element_id=element_id, path=str(path))

    def validate_fab(self, element_id: str) -> dict[str, Any]:
        return self.op("validate_fab", element_id=element_id)

    def export_gdt_drawing(self, element_id: str, path: str | Path) -> Path:
        """Write machining SVG with ortho BREP views + feature list + GD&T callouts."""
        from llmbim_drawings.gdt_drawing import write_gdt_drawing

        return write_gdt_drawing(self._model, element_id, path)

    def fab_revolve(
        self,
        element_id: str,
        *,
        radius_mm: float,
        height_mm: float,
        inner_radius_mm: float = 0.0,
        origin_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> dict[str, Any]:
        """Lathe revolve (disk/tube) about Z."""
        return self.op(
            "fab_revolve",
            element_id=element_id,
            radius_mm=radius_mm,
            height_mm=height_mm,
            inner_radius_mm=inner_radius_mm,
            origin_mm=list(origin_mm),
        )

    def fab_hole_pattern(
        self,
        element_id: str,
        *,
        diameter_mm: float,
        origin_mm: tuple[float, float, float],
        count_x: int = 2,
        count_y: int = 1,
        spacing_x_mm: float = 20.0,
        spacing_y_mm: float = 20.0,
        depth_mm: float | None = None,
    ) -> dict[str, Any]:
        kw: dict[str, Any] = {
            "element_id": element_id,
            "diameter_mm": diameter_mm,
            "origin_mm": list(origin_mm),
            "count_x": count_x,
            "count_y": count_y,
            "spacing_x_mm": spacing_x_mm,
            "spacing_y_mm": spacing_y_mm,
        }
        if depth_mm is not None:
            kw["depth_mm"] = depth_mm
        return self.op("fab_hole_pattern", **kw)

    def create_fab_assembly(self, *, name: str = "FabAssembly", level: str | None = None) -> str:
        r = self.op("create_fab_assembly", name=name, level=level)
        return str(r["element_id"])

    def export_fab_assembly_step(self, assembly_id: str, path: str | Path) -> dict[str, Any]:
        return self.op("export_fab_assembly_step", assembly_id=assembly_id, path=str(path))

    def export_fab_ortho(self, element_id: str, out_dir: str | Path) -> dict[str, Any]:
        """Write top/front/right SVG orthographics for a fab_part."""
        return self.op("export_fab_ortho", element_id=element_id, out_dir=str(out_dir))

    def fab_tag(
        self,
        element_id: str,
        *,
        name: str,
        selector: str,
        kind: str = "edges",
    ) -> dict[str, Any]:
        """Name edges/faces; later fillet with selector='tag:name'."""
        return self.op(
            "fab_tag", element_id=element_id, name=name, selector=selector, kind=kind
        )

    def fab_mate(
        self,
        assembly_id: str,
        *,
        mate_type: str,
        a: str,
        b: str,
        a_face: str = "top",
        b_face: str = "bottom",
        gap_mm: float = 0.0,
        offset_mm: tuple[float, float, float] | None = None,
    ) -> dict[str, Any]:
        """Mate assembly instances: coincident | concentric | offset."""
        kw: dict[str, Any] = {
            "assembly_id": assembly_id,
            "mate_type": mate_type,
            "a": a,
            "b": b,
            "a_face": a_face,
            "b_face": b_face,
            "gap_mm": gap_mm,
        }
        if offset_mm is not None:
            kw["offset_mm"] = list(offset_mm)
        return self.op("fab_mate", **kw)

    def fab_assembly_add(
        self,
        assembly_id: str,
        part_id: str,
        *,
        origin_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
        rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        return self.op(
            "fab_assembly_add",
            assembly_id=assembly_id,
            part_id=part_id,
            origin_mm=list(origin_mm),
            rotation_deg=list(rotation_deg),
            instance_id=instance_id,
        )

    def fab_host_to_building(
        self,
        element_id: str,
        *,
        level: str | None = None,
        origin_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
        z0_mm: float | None = None,
        host_id: str | None = None,
        rotation_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> dict[str, Any]:
        """Place fab BREP into the building (level/host) for glTF + model.step envelope."""
        kw: dict[str, Any] = {
            "element_id": element_id,
            "level": level,
            "origin_mm": list(origin_mm),
            "host_id": host_id,
            "rotation_deg": list(rotation_deg),
        }
        if z0_mm is not None:
            kw["z0_mm"] = z0_mm
        return self.op("fab_host_to_building", **kw)

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
        phases: str | list[str] | None = None,
    ) -> dict[str, Any]:
        """Full pack: JSON + IFC + glTF + STEP + construction and/or part sheets.

        If ``out_dir`` is omitted, writes to ``output/<project_slug>/`` in the repo.
        ``phases``: e.g. ``\"new\"`` or ``[\"new\",\"existing\"]`` — filters exports
        (full model still saved as model.llmbim.json).
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
            phases=phases,
        )
        result["output_dir"] = str(dest.resolve())
        return result

    def verify_pack(
        self,
        out_dir: str | Path | None = None,
        *,
        require_materials: bool = True,
        require_parts: bool = False,
    ) -> dict[str, Any]:
        """Verify a deliverables pack (vision completeness signals).

        If ``out_dir`` is omitted, uses ``output/<project_slug>/``.
        """
        from llmbim_core.paths import project_output_dir
        from llmbim_drawings.deliverables import verify_pack

        dest = Path(out_dir) if out_dir else project_output_dir(self.name)
        return verify_pack(
            dest,
            require_materials=require_materials,
            require_parts=require_parts,
        )

    def save_local(self, name: str | None = None) -> Path:
        """Save project JSON under output/<slug>/model.llmbim.json."""
        from llmbim_core.paths import project_output_dir

        d = project_output_dir(name or self.name)
        path = d / "model.llmbim.json"
        self.save(path)
        return path

    # --- modules / blocks / machines -----------------------------------------

    def import_module(
        self,
        source: str | Path | ProjectModel,
        *,
        level: str,
        origin: tuple[float, float] = (0.0, 0.0),
        mode: str = "native",
        name: str | None = None,
        rotation_deg: float = 0.0,
        z0_mm: float = 0.0,
        kind: str = "fabrication",
    ) -> dict[str, Any]:
        """Import another project as block | native (exploded) | linked module/machine.

        - ``block``: single instance + definition in library (CAD-like block)
        - ``native``: copy all elements into host (editable fabrication)
        - ``linked``: block that can re-sync from source path
        """
        from llmbim_core.modules import import_module

        result = import_module(
            self._model,
            source,
            level=level,
            origin=origin,
            mode=mode,  # type: ignore[arg-type]
            name=name,
            rotation_deg=rotation_deg,
            z0_mm=z0_mm,
            kind=kind,
        )
        if self._vcs is not None:
            self._vcs.append_journal(
                "import_module",
                {"mode": mode, "name": name, "result": result},
                author=self._author,
            )
        return result

    def export_module(
        self,
        path: str | Path,
        *,
        name: str | None = None,
        element_ids: list[str] | None = None,
        kind: str = "fabrication",
    ) -> dict[str, Any]:
        """Save this project (or selection) as a reusable module package."""
        from llmbim_core.modules import export_as_module

        return export_as_module(
            self._model,
            path,
            name=name or self.name,
            element_ids=element_ids,
            kind=kind,
        )

    def explode_block(self, instance_id: str) -> dict[str, Any]:
        """Turn a block instance into native host elements."""
        from llmbim_core.modules import explode_block

        result = explode_block(self._model, instance_id)
        if self._vcs is not None:
            self._vcs.append_journal("explode_block", result, author=self._author)
        return result

    def define_port(
        self,
        element_id: str,
        name: str,
        *,
        role: str = "process",
        medium: str = "",
        position: tuple[float, float] | None = None,
        direction: str = "",
    ) -> dict[str, Any]:
        """Define a connection port on equipment/module (process, power, drain, …)."""
        from llmbim_core.modules import define_port

        return define_port(
            self._model,
            element_id,
            name,
            role=role,
            medium=medium,
            position_mm=list(position) if position else None,
            direction=direction,
        )

    def connect(
        self,
        from_id: str,
        from_port: str,
        to_id: str,
        to_port: str,
        *,
        medium: str = "process",
        name: str = "",
    ) -> dict[str, Any]:
        """Connect two ports (machine ↔ host, module ↔ module)."""
        from llmbim_core.modules import connect

        result = connect(
            self._model,
            from_id,
            from_port,
            to_id,
            to_port,
            medium=medium,
            name=name,
        )
        if self._vcs is not None:
            self._vcs.append_journal("connect", result, author=self._author)
        return result

    def modules(self) -> dict[str, Any]:
        from llmbim_core.modules import list_connections, list_modules

        data = list_modules(self._model)
        data["connections"] = list_connections(self._model)
        return data

    def resync_module(self, instance_id: str) -> dict[str, Any]:
        """Re-load a linked block definition from its source path."""
        from llmbim_core.modules import resync_linked_module

        return resync_linked_module(self._model, instance_id)


__all__ = ["Project", "Element", "Level", "ProjectModel", "__version__"]
