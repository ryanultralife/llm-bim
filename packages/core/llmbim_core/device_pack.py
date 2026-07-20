"""Device SSOT → BIM: versioned device pack schema + instantiation.

Productizes the Proto-10 pattern (docs/EQUIPMENT_3D_AND_DEVICE_SSOT.md §6):
a machine's single source of truth is a JSON *device pack* — params plus a
component list (kinds, shapes, positions, axes) — and ``build_device()``
instantiates it into any :class:`~llmbim_core.model.ProjectModel` through the
op registry. What ``examples/proto10_separator.py`` hand-rolled per session
lives here as a reusable, testable contract.

Coordinates follow the device frame of §4: mm (or metres, scaled ×1000 like
the primitives importer), x/y in plan, z up. ``build_device`` translates the
whole device to a placement point (``origin_mm``, ``z0_mm``).

Fidelity: envelope geometry and presentation routing — an engineering
estimate, not fab CAD or a stamped design (see ``HONESTY.md``).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self

import pydantic
from pydantic import BaseModel, ConfigDict, Field, model_validator

from llmbim_core.errors import NotFoundError, ValidationError
from llmbim_core.model import ProjectModel
from llmbim_core.registry import dispatch, list_ops

SCHEMA_ID = "llmbim.device_pack/v1"

HONESTY_NOTE = (
    "device instantiation — engineering estimate: envelope geometry and "
    "presentation routing derived from the device SSOT, not fab CAD or a "
    "stamped design"
)

Vec3 = tuple[float, float, float]
AxisName = Literal["x", "y", "z"]
Shape = Literal["box", "cylinder", "tube", "wire_path"]

_AXIS_UNITS: dict[str, Vec3] = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}
_DEFAULT_WIRE_DIAMETER_MM = 6.0


class DeviceComponent(BaseModel):
    """One solid / path of a device.

    Anchor: ``center_mm`` (geometric centre) or ``origin_mm`` — read as the
    centre when the pack's ``origin_mode`` is ``"center"``, as the min corner
    of the axis-aligned extent when ``"min_corner"``. ``wire_path`` components
    carry absolute ``points_mm`` instead (an anchor, if given, offsets them).

    Sizes: box → ``size_mm`` (w, d, h). cylinder/tube → ``od_mm`` /
    ``id_mm`` / ``length_mm``, or ``size_mm`` read as (od, id, length).
    wire_path → ``diameter_mm``.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = ""
    kind: str = "equipment"
    shape: Shape
    origin_mm: Vec3 | None = None
    center_mm: Vec3 | None = None
    size_mm: Vec3 | None = None
    od_mm: float | None = None
    id_mm: float | None = None
    length_mm: float | None = None
    diameter_mm: float | None = None
    axis: AxisName | Vec3 = "x"
    points_mm: list[Vec3] | None = None
    phase: str | None = None
    system: str | None = None
    material_hint: str | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)

    def cyl_dims(self) -> tuple[float, float, float]:
        """(od, id, length) for cylinder/tube; ``size_mm`` read as (od, id, length)."""
        od, inner, length = self.od_mm, self.id_mm, self.length_mm
        if self.size_mm is not None:
            s_od, s_id, s_len = self.size_mm
            od = od if od is not None else s_od
            inner = inner if inner is not None else s_id
            length = length if length is not None else s_len
        return float(od or 0.0), float(inner or 0.0), float(length or 0.0)

    def axis_unit(self) -> Vec3:
        """Normalized axis direction vector."""
        if isinstance(self.axis, str):
            return _AXIS_UNITS[self.axis]
        dx, dy, dz = self.axis
        n = math.sqrt(dx * dx + dy * dy + dz * dz)
        return (dx / n, dy / n, dz / n)

    def axis_letter(self) -> AxisName | None:
        """"x"/"y"/"z" when the axis is (or snaps to) a principal axis."""
        if isinstance(self.axis, str):
            return self.axis
        u = self.axis_unit()
        letters: tuple[AxisName, ...] = ("x", "y", "z")
        for letter in letters:
            ref = _AXIS_UNITS[letter]
            if abs(abs(u[0] * ref[0] + u[1] * ref[1] + u[2] * ref[2]) - 1.0) < 1e-6:
                return letter
        return None

    @model_validator(mode="after")
    def _check(self) -> Self:
        tag = f"component {self.id!r}"
        if self.origin_mm is not None and self.center_mm is not None:
            raise ValueError(f"{tag}: give origin_mm or center_mm, not both")
        if self.shape == "wire_path":
            if not self.points_mm or len(self.points_mm) < 2:
                raise ValueError(f"{tag}: wire_path needs points_mm with >= 2 points")
            return self
        if self.origin_mm is None and self.center_mm is None:
            raise ValueError(f"{tag}: {self.shape} needs origin_mm or center_mm")
        if self.shape == "box":
            if self.size_mm is None:
                raise ValueError(f"{tag}: box needs size_mm (w, d, h)")
            if min(self.size_mm) <= 0:
                raise ValueError(f"{tag}: size_mm values must be > 0")
            return self
        od, inner, length = self.cyl_dims()
        if od <= 0 or length <= 0:
            raise ValueError(
                f"{tag}: {self.shape} needs od_mm and length_mm > 0 "
                f"(or size_mm read as (od, id, length))"
            )
        if inner and inner >= od:
            raise ValueError(f"{tag}: id_mm must be < od_mm")
        if not isinstance(self.axis, str) and math.hypot(*self.axis) < 1e-9:
            raise ValueError(f"{tag}: axis vector must be non-zero")
        return self


class DevicePack(BaseModel):
    """Versioned device SSOT: params + components, in a self-declared unit."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_id: str = Field(default=SCHEMA_ID, alias="schema")
    name: str = Field(min_length=1)
    units: Literal["m", "mm"] = "mm"
    origin_mode: Literal["center", "min_corner"] = "center"
    params: dict[str, Any] = Field(default_factory=dict)
    components: list[DeviceComponent] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        seen: set[str] = set()
        for c in self.components:
            if c.id in seen:
                raise ValueError(f"component {c.id!r}: duplicate component id")
            seen.add(c.id)
        return self

    @property
    def scale(self) -> float:
        """Multiplier to mm — metres scale ×1000, like the primitives importer."""
        return 1000.0 if self.units == "m" else 1.0


def _describe_errors(raw: Any, exc: pydantic.ValidationError) -> list[str]:
    """Human messages naming the offending component id where possible."""
    out: list[str] = []
    for err in exc.errors():
        loc = tuple(err.get("loc") or ())
        msg = str(err.get("msg") or "invalid")
        label: str | None = None
        where = ""
        if len(loc) >= 2 and loc[0] == "components" and isinstance(loc[1], int):
            idx = loc[1]
            label = f"#{idx}"
            if isinstance(raw, Mapping):
                comps = raw.get("components")
                if isinstance(comps, list) and 0 <= idx < len(comps):
                    item = comps[idx]
                    if isinstance(item, Mapping) and item.get("id"):
                        label = str(item["id"])
            where = ".".join(str(x) for x in loc[2:])
        elif loc:
            where = ".".join(str(x) for x in loc)
        prefix = ""
        if label is not None and f"component {label!r}" not in msg:
            prefix = f"component {label!r}: "
        if where and where not in msg:
            prefix += f"{where}: "
        out.append(prefix + msg)
    return out


def load_device_pack(path: str | Path) -> DevicePack:
    """Load + validate a device pack JSON; errors name the offending component."""
    p = Path(path)
    if not p.exists():
        raise NotFoundError(f"device pack not found: {p}", path=str(p))
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"device pack is not valid JSON: {exc}", path=str(p)) from exc
    try:
        return DevicePack.model_validate(raw)
    except pydantic.ValidationError as exc:
        raise ValidationError(
            "invalid device pack: " + "; ".join(_describe_errors(raw, exc)),
            path=str(p),
        ) from exc


def _result_ids(result: Mapping[str, Any]) -> list[str]:
    """Element ids out of an op result, whatever key convention it uses."""
    ids: list[str] = []
    for key in ("element_id", "id"):
        v = result.get(key)
        if isinstance(v, str) and v:
            ids.append(v)
    for key in ("element_ids", "ids", "created_ids"):
        v = result.get(key)
        if isinstance(v, (list, tuple)):
            ids.extend(str(x) for x in v)
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _extents_mm(comp: DeviceComponent, scale: float) -> Vec3:
    """Axis-aligned extent (mm) of the component's solid."""
    if comp.shape == "box":
        assert comp.size_mm is not None  # validated
        return (comp.size_mm[0] * scale, comp.size_mm[1] * scale, comp.size_mm[2] * scale)
    od, _inner, length = comp.cyl_dims()
    od, length = od * scale, length * scale
    ux, uy, uz = comp.axis_unit()
    return (
        abs(ux) * length + (1.0 - abs(ux)) * od,
        abs(uy) * length + (1.0 - abs(uy)) * od,
        abs(uz) * length + (1.0 - abs(uz)) * od,
    )


def _center_mm(comp: DeviceComponent, pack: DevicePack, scale: float) -> Vec3:
    """Component centre in the device frame (mm), honouring origin_mode."""
    if comp.center_mm is not None:
        a = comp.center_mm
        return (a[0] * scale, a[1] * scale, a[2] * scale)
    assert comp.origin_mm is not None  # validated for solid shapes
    a = comp.origin_mm
    ax, ay, az = a[0] * scale, a[1] * scale, a[2] * scale
    if pack.origin_mode == "center":
        return (ax, ay, az)
    ex, ey, ez = _extents_mm(comp, scale)
    return (ax + ex / 2.0, ay + ey / 2.0, az + ez / 2.0)


def _stamp(
    model: ProjectModel,
    ids: list[str],
    pack: DevicePack,
    comp: DeviceComponent,
    scale: float,
) -> None:
    """Record device identity + system/phase metadata on created elements."""
    meta: dict[str, Any] = {
        "device_pack": pack.name,
        "device_component": comp.id,
    }
    if comp.phase:
        meta["phase"] = comp.phase
    if comp.system:
        meta["system"] = comp.system
    if comp.material_hint:
        meta["material_hint"] = comp.material_hint
    if comp.attrs:
        meta["device_attrs"] = dict(comp.attrs)
    if comp.shape in ("cylinder", "tube"):
        meta["axis"] = comp.axis if isinstance(comp.axis, str) else list(comp.axis)
        od, inner, length = comp.cyl_dims()
        meta["od_mm"] = od * scale
        meta["length_mm"] = length * scale
        if inner > 0:
            meta["id_mm"] = inner * scale
    for eid in ids:
        for key, value in meta.items():
            dispatch(model, "set_param", {"id": eid, "key": key, "value": value})


def _build_solid(
    model: ProjectModel,
    comp: DeviceComponent,
    *,
    ops: set[str],
    level: str,
    name: str,
    center: Vec3,
    scale: float,
    warnings: list[str],
) -> tuple[str, list[str]]:
    """Box / cylinder / tube component → (op used, element ids)."""
    cx, cy, cz = center
    if comp.shape == "box":
        ex, ey, ez = _extents_mm(comp, scale)
        r = dispatch(
            model,
            "create_equipment_box",
            {
                "level": level,
                "origin": [cx, cy],
                "size": [ex, ey, ez],
                "name": name,
                "kind": comp.kind,
                "centered": True,
                "z0_mm": cz - ez / 2.0,
                "shape": "box",
            },
        )
        return "create_equipment_box", _result_ids(r)

    od, inner, length = comp.cyl_dims()
    od, inner, length = od * scale, inner * scale, length * scale
    letter = comp.axis_letter()
    use_tube_op = "place_tube" in ops and (comp.shape == "tube" or letter != "x")
    if use_tube_op:
        ux, uy, uz = comp.axis_unit()
        # place_tube's origin is the axis START point: plan XY + z0_mm elevation.
        r = dispatch(
            model,
            "place_tube",
            {
                "level": level,
                "origin": [cx - ux * length / 2.0, cy - uy * length / 2.0],
                "z0_mm": cz - uz * length / 2.0,
                "direction": [ux, uy, uz],
                "length_mm": length,
                "od_mm": od,
                "id_mm": inner if inner > 0 else None,
                "kind": comp.kind,
                "name": name,
                "system": comp.system,
            },
        )
        return "place_tube", _result_ids(r)

    if letter == "x":
        r = dispatch(
            model,
            "create_equipment_box",
            {
                "level": level,
                "origin": [cx, cy],
                "size": [length, od, od],
                "name": name,
                "kind": comp.kind,
                "centered": True,
                "z0_mm": cz - od / 2.0,
                "shape": "cylinder",
            },
        )
        return "create_equipment_box", _result_ids(r)

    # Oriented cylinder/tube without place_tube: honest box envelope fallback.
    ex, ey, ez = _extents_mm(comp, scale)
    axis_repr = comp.axis if isinstance(comp.axis, str) else list(comp.axis)
    warnings.append(
        f"component {comp.id!r}: {comp.shape} along axis {axis_repr!r} — "
        f"place_tube op not available, using box envelope (cylinder primitive runs along +X)"
    )
    r = dispatch(
        model,
        "create_equipment_box",
        {
            "level": level,
            "origin": [cx, cy],
            "size": [ex, ey, ez],
            "name": name,
            "kind": comp.kind,
            "centered": True,
            "z0_mm": cz - ez / 2.0,
            "shape": "box",
        },
    )
    return "create_equipment_box", _result_ids(r)


def _build_wire_path(
    model: ProjectModel,
    comp: DeviceComponent,
    *,
    ops: set[str],
    level: str,
    name: str,
    scale: float,
    ox: float,
    oy: float,
    z0: float,
    warnings: list[str],
) -> tuple[str, list[str]]:
    """wire_path component → (op used, element ids)."""
    assert comp.points_mm is not None  # validated
    off = comp.center_mm or comp.origin_mm or (0.0, 0.0, 0.0)
    pts = [
        [
            ox + (p[0] + off[0]) * scale,
            oy + (p[1] + off[1]) * scale,
            z0 + (p[2] + off[2]) * scale,
        ]
        for p in comp.points_mm
    ]
    dia = float(comp.diameter_mm or comp.od_mm or _DEFAULT_WIRE_DIAMETER_MM) * scale
    if "place_wire_path" in ops:
        r = dispatch(
            model,
            "place_wire_path",
            {
                "level": level,
                "points_mm": pts,
                "diameter_mm": dia,
                "phase": comp.phase,
                "system": comp.system,
                "wire_role": str(comp.attrs.get("role") or comp.kind),
                "name": name,
                "material_id": comp.material_hint,
            },
        )
        return "place_wire_path", _result_ids(r)

    warnings.append(
        f"component {comp.id!r}: place_wire_path op not available — stored as a "
        f"generic polyline element ({len(pts) - 1} segments, reduced render fidelity)"
    )
    r = dispatch(
        model,
        "create_generic",
        {
            "category": "wire_path",
            "level": level,
            "name": name,
            "params": {
                "shape": "polyline",
                "points_mm": pts,
                "diameter_mm": dia,
                "segments": len(pts) - 1,
                "origin_mm": pts[0][:2],
                "z0_mm": pts[0][2],
                "source": "device_pack",
            },
        },
    )
    return "create_generic", _result_ids(r)


def build_device(
    model: ProjectModel,
    pack: DevicePack,
    *,
    level: str,
    origin_mm: tuple[float, float] = (0.0, 0.0),
    z0_mm: float = 0.0,
    name_prefix: str = "",
) -> dict[str, Any]:
    """Instantiate a device pack into ``model`` at a placement point.

    Every mutation goes through the op registry (``create_equipment_box``,
    ``place_tube`` / ``place_wire_path`` when registered, ``create_generic``
    fallbacks otherwise). Names are deterministic: ``name_prefix`` + component
    name (or id). Never fatal per component — failures land in ``skipped``.

    Returns a summary dict: ``created`` records, ``element_ids`` per component,
    ``skipped`` with reasons, ``warnings``, and an honesty note.
    """
    warnings: list[str] = []
    skipped: list[dict[str, str]] = []
    created: list[dict[str, Any]] = []
    element_ids: dict[str, list[str]] = {}

    try:
        model.get_level(level)
    except NotFoundError:
        model.add_level(level, 0)
        warnings.append(f"level {level!r} not found — created at elevation 0")

    ops = {str(o["name"]) for o in list_ops()}
    scale = pack.scale
    ox, oy, z0 = float(origin_mm[0]), float(origin_mm[1]), float(z0_mm)

    for comp in pack.components:
        name = f"{name_prefix}{comp.name or comp.id}"
        try:
            if comp.shape == "wire_path":
                op, ids = _build_wire_path(
                    model,
                    comp,
                    ops=ops,
                    level=level,
                    name=name,
                    scale=scale,
                    ox=ox,
                    oy=oy,
                    z0=z0,
                    warnings=warnings,
                )
            else:
                cx, cy, cz = _center_mm(comp, pack, scale)
                op, ids = _build_solid(
                    model,
                    comp,
                    ops=ops,
                    level=level,
                    name=name,
                    center=(ox + cx, oy + cy, z0 + cz),
                    scale=scale,
                    warnings=warnings,
                )
            _stamp(model, ids, pack, comp, scale)
        except Exception as exc:
            skipped.append({"component_id": comp.id, "reason": f"{type(exc).__name__}: {exc}"})
            continue
        element_ids[comp.id] = ids
        created.append(
            {
                "component_id": comp.id,
                "name": name,
                "shape": comp.shape,
                "kind": comp.kind,
                "op": op,
                "element_ids": ids,
            }
        )

    return {
        "ok": not skipped,
        "device": pack.name,
        "schema": pack.schema_id,
        "level": level,
        "origin_mm": [ox, oy],
        "z0_mm": z0,
        "units": pack.units,
        "scale": scale,
        "components": len(pack.components),
        "created": created,
        "element_ids": element_ids,
        "created_total": sum(len(v) for v in element_ids.values()),
        "skipped": skipped,
        "warnings": warnings,
        "honesty": HONESTY_NOTE,
    }
