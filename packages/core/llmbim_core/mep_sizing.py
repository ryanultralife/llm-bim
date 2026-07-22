"""Hydraulic pipe sizing + HVAC duct sizing (engineering estimates).

Honesty: everything here is an **engineering estimate — not a stamped
hydraulic design**. Formulas are the standard textbook correlations:

Pipe (water):
  * Velocity: ``v = Q / A`` with the catalog inner diameter
    (copper Type L IDs from ``parts_catalog.COPPER_NPS``; steel uses
    ASME B36.10 Sch 40 inner diameters for the NPS labels in
    ``catalog_systems.STEEL_NPS``).
  * Pressure gradient: Hazen-Williams, SI form
    ``h_f [m/m] = 10.67 * Q^1.852 / (C^1.852 * d^4.87)`` with Q in m3/s and
    d in m, converted to kPa/m via ``rho * g`` (g = 9.80665 m/s2).
    C = 140 for copper, C = 120 for (black) steel.
  * WSFU -> flow: small Hunter's-curve table (predominantly flush-tank
    column, IPC Appendix E style values, approximate) with linear
    interpolation.

Duct (standard air, rho = 1.2 kg/m3, nu = 1.5e-5 m2/s):
  * Equal-friction round diameter from Darcy-Weisbach
    ``dp/L = f * rho * v^2 / (2 * D)`` with the friction factor from the
    Swamee-Jain explicit approximation of Colebrook
    ``f = 0.25 / log10(eps/(3.7 D) + 5.74/Re^0.9)^2`` (laminar fallback
    ``f = 64/Re``), absolute roughness eps = 0.09 mm (galvanized steel,
    ASHRAE "average" category).
  * Rectangular equivalent via the Huebscher equivalent-diameter formula
    ``De = 1.30 * (a*b)^0.625 / (a+b)^0.25`` (equal flow and equal friction),
    aspect ratio limited to 4:1, 50 mm size increments.

Pure module: no I/O; mutations only happen in :func:`size_route` with
``apply=True`` and go through element params / part assignment so existing
takeoffs (``material_lists.pipe_takeoff`` / ``duct_takeoff``) keep working.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from llmbim_core.catalog_systems import STEEL_NPS
from llmbim_core.errors import NotFoundError, ValidationError
from llmbim_core.model import Element, ProjectModel
from llmbim_core.parts_catalog import COPPER_NPS, get_part, resolve_fitting_part_id

HONESTY_NOTE = "engineering estimate — not a stamped hydraulic design"

# --- water / pipe constants ----------------------------------------------------

_G_MS2 = 9.80665
_GPM_TO_LPS = 0.0630902  # 1 US gpm = 0.0630902 L/s

# Hazen-Williams roughness coefficient by material family
_HW_C: dict[str, float] = {"copper": 140.0, "steel": 120.0}

# ASME B36.10 Schedule 40 inner diameters (mm) for the NPS labels carried by
# catalog_systems.STEEL_NPS (which only stores OD). Values: 0.622/0.824/1.049/
# 1.380/1.610/2.067/2.469/3.068/4.026/6.065/7.981 inches converted to mm.
_STEEL_SCH40_ID_MM: dict[str, float] = {
    "1/2": 15.8,
    "3/4": 20.9,
    "1": 26.6,
    "1-1/4": 35.1,
    "1-1/2": 40.9,
    "2": 52.5,
    "2-1/2": 62.7,
    "3": 77.9,
    "4": 102.3,
    "6": 154.1,
    "8": 202.7,
}

# Hunter's curve, predominantly-flush-tank column (WSFU -> US gpm), approximate
# IPC Appendix E style anchor points; linear interpolation between rows and a
# (0, 0) anchor below 1 WSFU (simplification — the published curve starts at 1).
_HUNTER_WSFU_GPM: tuple[tuple[float, float], ...] = (
    (0.0, 0.0),
    (1.0, 3.0),
    (2.0, 5.0),
    (3.0, 6.5),
    (4.0, 8.0),
    (5.0, 9.4),
    (6.0, 10.7),
    (8.0, 12.8),
    (10.0, 14.6),
    (15.0, 17.5),
    (20.0, 20.0),
    (30.0, 23.3),
    (40.0, 26.3),
    (50.0, 29.1),
    (75.0, 35.0),
    (100.0, 43.5),
    (150.0, 52.5),
    (200.0, 65.0),
    (300.0, 85.0),
    (400.0, 105.0),
    (500.0, 125.0),
    (750.0, 170.0),
    (1000.0, 208.0),
)

# --- air / duct constants ------------------------------------------------------

_AIR_RHO = 1.2  # kg/m3 (standard air)
_AIR_NU = 1.5e-5  # m2/s kinematic viscosity
_DUCT_EPS_M = 0.09e-3  # galvanized steel absolute roughness (ASHRAE average)
_DUCT_INCREMENT_MM = 50.0  # commercial rect duct size step
_DUCT_MAX_ASPECT = 4.0


def _material_family(material: str) -> str:
    """Map a material label / material_id to a Hazen-Williams family."""
    m = material.lower().strip()
    if "copper" in m or m in ("cu", "c12200"):
        return "copper"
    if any(k in m for k in ("steel", "black", "a53", "ss3", "stainless", "fire", "fp")):
        return "steel"
    raise ValidationError(
        "Unknown pipe material for hydraulic sizing (use copper or steel)",
        material=material,
        supported=sorted(_HW_C),
    )


def _pipe_table(family: str) -> list[tuple[str, float]]:
    """(nps, id_mm) rows for a material family, sorted by inner diameter."""
    rows: list[tuple[str, float]]
    if family == "copper":
        rows = [(nps, float(geom["id_mm"])) for nps, geom in COPPER_NPS.items()]
    else:
        rows = [
            (nps, _STEEL_SCH40_ID_MM[nps])
            for nps in STEEL_NPS
            if nps in _STEEL_SCH40_ID_MM
        ]
    return sorted(rows, key=lambda r: r[1])


def _pipe_id_mm(nps: str, family: str) -> float:
    for label, id_mm in _pipe_table(family):
        if label == nps:
            return id_mm
    raise ValidationError("NPS not in catalog for material", nps=nps, material=family)


def _velocity_ms(flow_lps: float, id_mm: float) -> float:
    area_m2 = math.pi * (id_mm / 2000.0) ** 2
    return (flow_lps / 1000.0) / area_m2


def _hw_gradient_kpa_m(flow_lps: float, id_mm: float, c: float) -> float:
    """Hazen-Williams head-loss gradient converted to kPa/m."""
    q_m3s = flow_lps / 1000.0
    d_m = id_mm / 1000.0
    hf_m_per_m = 10.67 * math.pow(q_m3s, 1.852) / (math.pow(c, 1.852) * math.pow(d_m, 4.87))
    return hf_m_per_m * 1000.0 * _G_MS2 / 1000.0  # rho*g*hf, Pa/m -> kPa/m


def wsfu_to_lps(wsfu: float) -> float:
    """Convert water supply fixture units to design flow (L/s), Hunter's curve.

    Linear interpolation on the flush-tank anchor table above; above the last
    row (1000 WSFU) the final segment slope is extrapolated. Approximate —
    engineering estimate, not a code calculation.
    """
    if wsfu < 0:
        raise ValidationError("fixture_units must be >= 0", fixture_units=wsfu)
    table = _HUNTER_WSFU_GPM
    if wsfu >= table[-1][0]:
        (x0, y0), (x1, y1) = table[-2], table[-1]
        gpm = y1 + (wsfu - x1) * (y1 - y0) / (x1 - x0)
        return gpm * _GPM_TO_LPS
    gpm = 0.0
    for (x0, y0), (x1, y1) in zip(table, table[1:], strict=False):
        if wsfu <= x1:
            gpm = y0 + (wsfu - x0) * (y1 - y0) / (x1 - x0)
            break
    return gpm * _GPM_TO_LPS


# --- pipe sizing ---------------------------------------------------------------


def size_pipe(
    flow_lps: float | None = None,
    *,
    material: str = "copper",
    max_velocity_ms: float = 2.4,
    fixture_units: float | None = None,
) -> dict[str, Any]:
    """Smallest catalog NPS keeping velocity <= ``max_velocity_ms``.

    Give either ``flow_lps`` directly or ``fixture_units`` (WSFU, converted
    via Hunter's curve). Reports velocity and Hazen-Williams pressure gradient
    (C=140 copper, C=120 steel). Engineering estimate — not a stamped design.
    """
    if fixture_units is not None and flow_lps is not None:
        raise ValidationError(
            "Give flow_lps or fixture_units, not both", flow_lps=flow_lps, fixture_units=fixture_units
        )
    if fixture_units is not None:
        flow_lps = wsfu_to_lps(fixture_units)
    if flow_lps is None or flow_lps <= 0:
        raise ValidationError("flow_lps must be > 0 (or give fixture_units)", flow_lps=flow_lps)
    if max_velocity_ms <= 0:
        raise ValidationError("max_velocity_ms must be > 0", max_velocity_ms=max_velocity_ms)
    family = _material_family(material)
    c = _HW_C[family]
    rejected: list[dict[str, Any]] = []
    for nps, id_mm in _pipe_table(family):
        v = _velocity_ms(flow_lps, id_mm)
        if v <= max_velocity_ms:
            return {
                "ok": True,
                "nps": nps,
                "material": family,
                "id_mm": id_mm,
                "flow_lps": round(flow_lps, 4),
                "fixture_units": fixture_units,
                "velocity_ms": round(v, 3),
                "max_velocity_ms": max_velocity_ms,
                "gradient_kpa_m": round(_hw_gradient_kpa_m(flow_lps, id_mm, c), 4),
                "hw_c": c,
                "method": "velocity limit (Hazen-Williams gradient reported)",
                "rejected": rejected,
                "honesty": HONESTY_NOTE,
            }
        rejected.append({"nps": nps, "velocity_ms": round(v, 3)})
    raise ValidationError(
        "Flow exceeds largest catalog pipe size at this velocity limit",
        flow_lps=flow_lps,
        material=family,
        max_velocity_ms=max_velocity_ms,
        largest_nps=_pipe_table(family)[-1][0],
    )


def check_pipe(
    nps: str,
    flow_lps: float,
    *,
    material: str = "copper",
    max_velocity_ms: float = 2.4,
    max_gradient_kpa_m: float | None = None,
) -> dict[str, Any]:
    """Velocity + Hazen-Williams gradient for a given NPS; ok flags vs limits."""
    if flow_lps <= 0:
        raise ValidationError("flow_lps must be > 0", flow_lps=flow_lps)
    family = _material_family(material)
    id_mm = _pipe_id_mm(nps, family)
    v = _velocity_ms(flow_lps, id_mm)
    grad = _hw_gradient_kpa_m(flow_lps, id_mm, _HW_C[family])
    velocity_ok = v <= max_velocity_ms
    gradient_ok = max_gradient_kpa_m is None or grad <= max_gradient_kpa_m
    return {
        "nps": nps,
        "material": family,
        "id_mm": id_mm,
        "flow_lps": round(flow_lps, 4),
        "velocity_ms": round(v, 3),
        "gradient_kpa_m": round(grad, 4),
        "max_velocity_ms": max_velocity_ms,
        "max_gradient_kpa_m": max_gradient_kpa_m,
        "velocity_ok": velocity_ok,
        "gradient_ok": gradient_ok,
        "ok": velocity_ok and gradient_ok,
        "honesty": HONESTY_NOTE,
    }


# --- duct sizing ---------------------------------------------------------------


def _duct_friction_pa_m(flow_m3s: float, d_m: float) -> float:
    """Round-duct Darcy friction gradient (Pa/m), Swamee-Jain friction factor."""
    area = math.pi * d_m**2 / 4.0
    v = flow_m3s / area
    re = v * d_m / _AIR_NU
    if re < 2300.0:
        f = 64.0 / max(re, 1e-9)
    else:
        f = 0.25 / math.log10(_DUCT_EPS_M / (3.7 * d_m) + 5.74 / re**0.9) ** 2
    return f * _AIR_RHO * v**2 / (2.0 * d_m)


def _solve_round_d_m(flow_m3s: float, friction_pa_m: float) -> float:
    """Diameter where friction equals target (bisection; friction is monotone)."""
    lo, hi = 0.05, 3.0
    if _duct_friction_pa_m(flow_m3s, lo) <= friction_pa_m:
        return lo
    if _duct_friction_pa_m(flow_m3s, hi) > friction_pa_m:
        raise ValidationError(
            "Flow too large for duct sizing bounds", flow_m3h=flow_m3s * 3600.0
        )
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if _duct_friction_pa_m(flow_m3s, mid) > friction_pa_m:
            lo = mid
        else:
            hi = mid
    return hi


def equivalent_diameter_mm(width_mm: float, height_mm: float) -> float:
    """Huebscher equivalent round diameter (equal flow, equal friction)."""
    a, b = float(width_mm), float(height_mm)
    if a <= 0 or b <= 0:
        raise ValidationError("Duct sides must be > 0", width_mm=width_mm, height_mm=height_mm)
    return 1.30 * math.pow(a * b, 0.625) / math.pow(a + b, 0.25)


def _rect_for_round(d_mm: float) -> tuple[float, float]:
    """Smallest-area (w, h) in 50 mm steps, aspect <= 4:1, De(w, h) >= d_mm."""
    best: tuple[float, float, float] | None = None  # (area, w, h)
    h = 100.0
    while h <= 2000.0:
        w = h
        w_max = min(h * _DUCT_MAX_ASPECT, 3000.0)
        while w <= w_max:
            if equivalent_diameter_mm(w, h) >= d_mm:
                area = w * h
                if best is None or area < best[0] or (area == best[0] and w + h < best[1] + best[2]):
                    best = (area, w, h)
                break  # smallest w for this h found
            w += _DUCT_INCREMENT_MM
        h += _DUCT_INCREMENT_MM
    if best is None:
        raise ValidationError("No rectangular duct within 4:1 aspect fits", round_d_mm=d_mm)
    return best[1], best[2]


def size_duct(
    flow_m3h: float,
    *,
    method: str = "equal_friction",
    friction_pa_m: float = 0.8,
    max_velocity_ms: float = 7.5,
    shape: str = "rect",
) -> dict[str, Any]:
    """Equal-friction duct sizing (Darcy + Swamee-Jain), rect via Huebscher.

    Round diameter is solved so the friction gradient equals ``friction_pa_m``
    (then rounded up to 5 mm); if the round-duct velocity would exceed
    ``max_velocity_ms`` the diameter is enlarged (velocity-governed). For
    ``shape="rect"`` the smallest 50 mm-increment w x h with aspect <= 4:1 and
    Huebscher equivalent diameter >= the round size is returned.
    """
    if flow_m3h <= 0:
        raise ValidationError("flow_m3h must be > 0", flow_m3h=flow_m3h)
    if method != "equal_friction":
        raise ValidationError("Only equal_friction is implemented", method=method)
    if shape not in ("rect", "round"):
        raise ValidationError("shape must be rect or round", shape=shape)
    if friction_pa_m <= 0 or max_velocity_ms <= 0:
        raise ValidationError(
            "friction_pa_m and max_velocity_ms must be > 0",
            friction_pa_m=friction_pa_m,
            max_velocity_ms=max_velocity_ms,
        )
    q = flow_m3h / 3600.0
    d_friction = _solve_round_d_m(q, friction_pa_m)
    d_velocity = math.sqrt(4.0 * q / (math.pi * max_velocity_ms))
    governed = "velocity" if d_velocity > d_friction else "friction"
    d_m = max(d_friction, d_velocity)
    round_d_mm = math.ceil(d_m * 1000.0 / 5.0) * 5.0
    d_used = round_d_mm / 1000.0
    v_round = q / (math.pi * d_used**2 / 4.0)
    out: dict[str, Any] = {
        "ok": True,
        "flow_m3h": round(flow_m3h, 3),
        "method": "equal_friction (Darcy-Weisbach, Swamee-Jain friction factor)",
        "shape": shape,
        "round_d_mm": round_d_mm,
        "round_velocity_ms": round(v_round, 3),
        "round_friction_pa_m": round(_duct_friction_pa_m(q, d_used), 4),
        "target_friction_pa_m": friction_pa_m,
        "max_velocity_ms": max_velocity_ms,
        "governed_by": governed,
        "honesty": HONESTY_NOTE,
    }
    if shape == "rect":
        w, h = _rect_for_round(round_d_mm)
        de = equivalent_diameter_mm(w, h)
        v_rect = q / (w / 1000.0 * h / 1000.0)
        out.update(
            {
                "width_mm": w,
                "height_mm": h,
                "aspect": round(w / h, 3),
                "equivalent_d_mm": round(de, 1),
                "velocity_ms": round(v_rect, 3),
                # by Huebscher definition the rect duct has the friction of the
                # equivalent round duct at the same flow
                "friction_pa_m": round(_duct_friction_pa_m(q, de / 1000.0), 4),
            }
        )
    else:
        out["velocity_ms"] = out["round_velocity_ms"]
        out["friction_pa_m"] = out["round_friction_pa_m"]
    return out


def check_duct(
    width_mm: float,
    height_mm: float,
    flow_m3h: float,
    *,
    max_velocity_ms: float = 7.5,
    max_friction_pa_m: float = 1.0,
) -> dict[str, Any]:
    """Velocity + friction gradient for a rect duct; ok flags vs limits."""
    if flow_m3h <= 0:
        raise ValidationError("flow_m3h must be > 0", flow_m3h=flow_m3h)
    q = flow_m3h / 3600.0
    de_mm = equivalent_diameter_mm(width_mm, height_mm)
    v = q / (width_mm / 1000.0 * height_mm / 1000.0)
    friction = _duct_friction_pa_m(q, de_mm / 1000.0)
    velocity_ok = v <= max_velocity_ms
    friction_ok = friction <= max_friction_pa_m
    return {
        "width_mm": float(width_mm),
        "height_mm": float(height_mm),
        "flow_m3h": round(flow_m3h, 3),
        "equivalent_d_mm": round(de_mm, 1),
        "velocity_ms": round(v, 3),
        "friction_pa_m": round(friction, 4),
        "max_velocity_ms": max_velocity_ms,
        "max_friction_pa_m": max_friction_pa_m,
        "velocity_ok": velocity_ok,
        "friction_ok": friction_ok,
        "ok": velocity_ok and friction_ok,
        "honesty": HONESTY_NOTE,
    }


# --- electrical / conduit fill (NEC Chapter 9) --------------------------------

_IN2_TO_MM2 = 645.16

# NEC Chapter 9, Table 5 — THHN/THWN-2 approximate total area per conductor
# (copper), in^2 -> mm^2. Engineering estimate, not a stamped design.
THHN_AREA_MM2: dict[str, float] = {
    "14": 0.0097 * _IN2_TO_MM2,
    "12": 0.0133 * _IN2_TO_MM2,
    "10": 0.0211 * _IN2_TO_MM2,
    "8": 0.0366 * _IN2_TO_MM2,
    "6": 0.0507 * _IN2_TO_MM2,
    "4": 0.0824 * _IN2_TO_MM2,
    "3": 0.0973 * _IN2_TO_MM2,
    "2": 0.1158 * _IN2_TO_MM2,
    "1": 0.1562 * _IN2_TO_MM2,
    "1/0": 0.1855 * _IN2_TO_MM2,
    "2/0": 0.2223 * _IN2_TO_MM2,
    "3/0": 0.2679 * _IN2_TO_MM2,
    "4/0": 0.3237 * _IN2_TO_MM2,
    "250": 0.3970 * _IN2_TO_MM2,
    "300": 0.4608 * _IN2_TO_MM2,
    "350": 0.5242 * _IN2_TO_MM2,
    "400": 0.5863 * _IN2_TO_MM2,
    "500": 0.7073 * _IN2_TO_MM2,
}

# NEC Chapter 9, Table 4 — EMT (Art. 358) internal area at 40% fill (>2 wires),
# in^2 -> mm^2, ordered small -> large.
EMT_FILL_40_MM2: tuple[tuple[str, float], ...] = tuple(
    (t, a * _IN2_TO_MM2)
    for t, a in (
        ("1/2", 0.122),
        ("3/4", 0.213),
        ("1", 0.346),
        ("1-1/4", 0.598),
        ("1-1/2", 0.814),
        ("2", 1.342),
        ("2-1/2", 2.343),
        ("3", 3.538),
        ("3-1/2", 4.618),
        ("4", 5.901),
    )
)

# THHN copper ampacity at 75C (NEC 310.16), (size, amps) small -> large.
_THHN_AMPACITY_75C: tuple[tuple[str, float], ...] = (
    ("14", 20.0),
    ("12", 25.0),
    ("10", 35.0),
    ("8", 50.0),
    ("6", 65.0),
    ("4", 85.0),
    ("3", 100.0),
    ("2", 115.0),
    ("1", 130.0),
    ("1/0", 150.0),
    ("2/0", 175.0),
    ("3/0", 200.0),
    ("4/0", 230.0),
    ("250", 255.0),
    ("300", 285.0),
    ("350", 310.0),
    ("400", 335.0),
    ("500", 380.0),
)

# 240.4(D) small-conductor overcurrent limits (A).
_OCPD_MAX: dict[str, float] = {"14": 15.0, "12": 20.0, "10": 30.0}

# NEC 250.122 copper equipment grounding conductor by OCPD rating (A -> size).
_EGC_250_122: tuple[tuple[float, str], ...] = (
    (15.0, "14"),
    (20.0, "12"),
    (60.0, "10"),
    (100.0, "8"),
    (200.0, "6"),
    (300.0, "4"),
    (400.0, "3"),
    (500.0, "2"),
    (600.0, "1"),
)


def conductor_for_amps(amps: float) -> str:
    """Smallest THHN copper size whose 75C ampacity carries ``amps``, honoring
    the 240.4(D) small-conductor limits. Engineering estimate."""
    if amps <= 0:
        raise ValidationError("amps must be > 0", amps=amps)
    for size, amp in _THHN_AMPACITY_75C:
        rating = min(amp, _OCPD_MAX.get(size, amp))
        if rating >= amps:
            return size
    raise ValidationError(
        "Load exceeds single-conductor table (parallel sets needed)", amps=amps
    )


def egc_for_amps(amps: float) -> str:
    """NEC 250.122 copper equipment grounding conductor size for the OCPD rating."""
    for ocpd, size in _EGC_250_122:
        if amps <= ocpd:
            return size
    return "2"


def size_conduit(
    conductors: Sequence[tuple[str, int]],
    *,
    conduit_type: str = "EMT",
) -> dict[str, Any]:
    """Smallest EMT trade size for ``conductors`` = [(awg, count), ...] at the
    NEC Chapter 9, Table 1 40% fill limit (3+ conductors). Engineering estimate."""
    if conduit_type != "EMT":
        raise ValidationError("Only EMT conduit fill is implemented", conduit_type=conduit_type)
    if not conductors:
        raise ValidationError("conductors required")
    total = 0.0
    detail: list[dict[str, Any]] = []
    for size, count in conductors:
        if size not in THHN_AREA_MM2:
            raise ValidationError(
                "Unknown conductor size", size=size, supported=sorted(THHN_AREA_MM2)
            )
        if count <= 0:
            continue
        total += THHN_AREA_MM2[size] * count
        detail.append(
            {"size": size, "count": count, "area_mm2": round(THHN_AREA_MM2[size], 2)}
        )
    for trade, cap40 in EMT_FILL_40_MM2:
        if total <= cap40:
            return {
                "ok": True,
                "trade_size": trade,
                "conduit_type": conduit_type,
                "conductor_area_mm2": round(total, 2),
                "fill_capacity_mm2": round(cap40, 2),
                "fill_pct": round(total / (cap40 / 0.40) * 100.0, 1),
                "conductors": detail,
                "honesty": HONESTY_NOTE,
            }
    raise ValidationError(
        "Conductors exceed 4in EMT at 40% fill", conductor_area_mm2=round(total, 2)
    )


def feeder_conduit(
    amps: float,
    *,
    phase_conductors: int = 2,
    neutral: bool = True,
    ground: bool = True,
    conduit_type: str = "EMT",
) -> dict[str, Any]:
    """Size a feeder's conductor set (ungrounded + neutral + EGC) and the EMT
    trade size that carries it. Engineering estimate — not a stamped design."""
    hot = conductor_for_amps(amps)
    conductors: list[tuple[str, int]] = [(hot, max(1, phase_conductors))]
    if neutral:
        conductors.append((hot, 1))
    if ground:
        conductors.append((egc_for_amps(amps), 1))
    out = size_conduit(conductors, conduit_type=conduit_type)
    out.update(
        {"amps": amps, "hot_size": hot, "neutral": neutral, "ground": ground}
    )
    return out


# --- route application ---------------------------------------------------------


def _segment_elements(
    model: ProjectModel, ids: Sequence[str], categories: tuple[str, ...]
) -> list[Element]:
    out: list[Element] = []
    for sid in ids:
        try:
            el = model.get_element(str(sid))
        except NotFoundError:
            continue
        if el.category in categories:
            out.append(el)
    return out


def _apply_pipe_size(model: ProjectModel, el: Element, nps: str, flow_lps: float) -> None:
    """Resize a pipe element in place, keeping takeoff keys consistent.

    ``pipe_takeoff`` reads the size from the assigned part's specs (when
    ``part_id``/``type_id`` resolves) or from ``params.nps`` — both are updated.
    """
    raw_mat = str(el.params.get("material_id") or "copper")
    el.params["nps"] = nps
    el.params["flow_lps"] = round(flow_lps, 4)
    el.params["sized_by"] = "mep_sizing"
    pid = resolve_fitting_part_id("pipe", nps, material=raw_mat) or resolve_fitting_part_id(
        "pipe", nps, material=_material_family(raw_mat)
    )
    if not pid:
        return
    from llmbim_core.assignment import assign_part

    length_m = float(el.params.get("length_m") or 0.0)
    el.params.pop("bom", None)  # refresh instance BOM from the new part
    assign_part(model, el.id, pid, qty=length_m or None)
    part = get_part(pid)
    od = float((part.specs or {}).get("od_mm") or 0.0) if part else 0.0
    size = el.params.get("size_mm")
    if od and isinstance(size, list) and len(size) == 3:
        if el.params.get("vertical"):
            el.params["size_mm"] = [od, od, size[2]]
        else:
            el.params["size_mm"] = [size[0], od, od]


def _apply_fitting_size(model: ProjectModel, fid: str, nps: str) -> bool:
    try:
        el = model.get_element(fid)
    except NotFoundError:
        return False
    ftype = str(el.params.get("fitting_type") or "")
    if not ftype or ftype in ("pipe", "duct"):
        return False
    el.params["nps"] = nps
    el.params["sized_by"] = "mep_sizing"
    raw_mat = str(el.params.get("material_id") or "copper")
    pid = resolve_fitting_part_id(ftype, nps, material=raw_mat)
    if pid:
        from llmbim_core.assignment import assign_part

        el.params.pop("bom", None)
        assign_part(model, el.id, pid, qty=1.0)
    return True


def _apply_duct_size(
    model: ProjectModel, el: Element, width_mm: float, height_mm: float, flow_m3h: float
) -> None:
    """Resize a duct element in place; ``duct_takeoff`` reads width_mm/height_mm."""
    el.params["width_mm"] = width_mm
    el.params["height_mm"] = height_mm
    el.params["flow_m3h"] = round(flow_m3h, 3)
    el.params["sized_by"] = "mep_sizing"
    length_mm = float(el.params.get("length_mm") or 0.0)
    if length_mm:
        area_m2 = round(2.0 * (width_mm + height_mm) * length_mm / 1_000_000.0, 3)
        el.params["area_m2"] = area_m2
        el.params["part_qty"] = area_m2
        if el.params.get("vertical"):
            el.params["size_mm"] = [width_mm, height_mm, length_mm]
        else:
            el.params["size_mm"] = [length_mm, width_mm, height_mm]
        if el.type_id:
            from llmbim_core.assignment import assign_part

            try:
                assign_part(model, el.id, el.type_id, qty=area_m2)
            except ValidationError:
                pass


def size_route(
    model: ProjectModel,
    edge_or_ids: Mapping[str, Any] | Sequence[str],
    *,
    flow_lps: float | None = None,
    flow_m3h: float | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Size an MEP run (a ``mep_graph`` edge dict or a list of segment ids).

    Pipes need ``flow_lps`` (L/s), ducts ``flow_m3h`` (m3/h). With
    ``apply=True`` the segment elements (and, for an edge, its fittings) are
    updated in place — ``params.nps`` + part reassignment for pipes,
    ``params.width_mm``/``height_mm`` (+ area/part_qty) for ducts — using the
    same keys the material takeoffs read, plus ``sized_by="mep_sizing"``.
    Engineering estimate — not a stamped hydraulic design.
    """
    edge: dict[str, Any] | None = None
    if isinstance(edge_or_ids, Mapping):
        edge = dict(edge_or_ids)  # summary copy; the live edge is found below
        seg_ids = [str(s) for s in (edge_or_ids.get("segment_ids") or [])]
        kind = str(edge_or_ids.get("route_kind") or "pipe")
    elif isinstance(edge_or_ids, str):
        raise ValidationError("Pass a mep_graph edge dict or a list of segment ids")
    else:
        seg_ids = [str(s) for s in edge_or_ids]
        kind = ""
    if not seg_ids:
        raise ValidationError("Route has no segment ids", edge=bool(edge))
    if not kind:
        cats = {model.get_element(s).category for s in seg_ids}
        kind = "duct" if "duct" in cats else "pipe" if "pipe" in cats else ""
    if kind not in ("pipe", "duct"):
        raise ValidationError("size_route supports pipe and duct runs only", kind=kind or None)

    updated: list[str] = []
    if kind == "pipe":
        if flow_lps is None and flow_m3h is not None:
            flow_lps = flow_m3h / 3.6  # 1 m3/h = 1/3.6 L/s
        if flow_lps is None or flow_lps <= 0:
            raise ValidationError("Pipe run needs flow_lps > 0", flow_lps=flow_lps)
        segments = _segment_elements(model, seg_ids, ("pipe", "plumbing_pipe"))
        if not segments:
            raise ValidationError("No pipe segments found for route", segment_ids=seg_ids)
        material = str(
            (edge or {}).get("material") or segments[0].params.get("material_id") or "copper"
        )
        sizing = size_pipe(flow_lps, material=material)
        nps = str(sizing["nps"])
        if apply:
            for el in segments:
                _apply_pipe_size(model, el, nps, flow_lps)
                updated.append(el.id)
            if edge is not None:
                for fid in [str(f) for f in (edge.get("fitting_ids") or [])]:
                    if _apply_fitting_size(model, fid, nps):
                        updated.append(fid)
    else:
        if flow_m3h is None and flow_lps is not None:
            flow_m3h = flow_lps * 3.6
        if flow_m3h is None or flow_m3h <= 0:
            raise ValidationError("Duct run needs flow_m3h > 0", flow_m3h=flow_m3h)
        segments = _segment_elements(model, seg_ids, ("duct", "hvac"))
        if not segments:
            raise ValidationError("No duct segments found for route", segment_ids=seg_ids)
        sizing = size_duct(flow_m3h)
        if apply:
            for el in segments:
                _apply_duct_size(
                    model, el, float(sizing["width_mm"]), float(sizing["height_mm"]), flow_m3h
                )
                updated.append(el.id)

    if apply and edge is not None:
        # update the live edge stored in model.meta (matched by id)
        for live in model.meta.get("mep_graph") or []:
            if isinstance(live, dict) and live.get("id") == edge.get("id"):
                if kind == "pipe":
                    live["nps"] = sizing["nps"]
                    live["flow_lps"] = round(float(flow_lps or 0.0), 4)
                else:
                    live["nps"] = f"{sizing['width_mm']:.0f}x{sizing['height_mm']:.0f}"
                    live["flow_m3h"] = round(float(flow_m3h or 0.0), 3)
                live["sized_by"] = "mep_sizing"
    return {
        "kind": kind,
        "edge_id": (edge or {}).get("id"),
        "segment_ids": seg_ids,
        "flow_lps": round(flow_lps, 4) if flow_lps is not None else None,
        "flow_m3h": round(flow_m3h, 3) if flow_m3h is not None else None,
        "sizing": sizing,
        "applied": bool(apply),
        "updated_elements": updated,
        "honesty": HONESTY_NOTE,
    }


def _edge_flows(model: ProjectModel, edge: Mapping[str, Any]) -> tuple[float | None, float | None]:
    """(flow_lps, flow_m3h) from the edge itself or its segments' params."""
    fl = edge.get("flow_lps")
    fm = edge.get("flow_m3h")
    if fl is None and fm is None:
        for sid in edge.get("segment_ids") or []:
            try:
                el = model.get_element(str(sid))
            except NotFoundError:
                continue
            if fl is None and el.params.get("flow_lps") is not None:
                fl = el.params["flow_lps"]
            if fm is None and el.params.get("flow_m3h") is not None:
                fm = el.params["flow_m3h"]
    return (
        float(fl) if fl is not None else None,
        float(fm) if fm is not None else None,
    )


def validate_runs(model: ProjectModel) -> list[dict[str, Any]]:
    """Hydraulic check of every ``mep_graph`` edge that carries flow data.

    Edges with ``flow_lps``/``flow_m3h`` (on the edge or its segments' params)
    get velocity/friction numbers and ok/warning status; runs without flow
    data are honestly listed as ``"no flow data"`` instead of being guessed.
    """
    out: list[dict[str, Any]] = []
    for edge in model.meta.get("mep_graph") or []:
        if not isinstance(edge, dict):
            continue
        kind = str(edge.get("route_kind") or "")
        row: dict[str, Any] = {
            "edge_id": edge.get("id"),
            "name": edge.get("name"),
            "kind": kind,
            "honesty": HONESTY_NOTE,
        }
        if kind not in ("pipe", "duct"):
            row["status"] = f"not applicable ({kind or 'unknown kind'})"
            out.append(row)
            continue
        fl, fm = _edge_flows(model, edge)
        seg_ids = [str(s) for s in (edge.get("segment_ids") or [])]
        checks: list[dict[str, Any]] = []
        if kind == "pipe":
            if fl is None and fm is not None:
                fl = fm / 3.6
            if fl is None:
                row["status"] = "no flow data"
                out.append(row)
                continue
            row["flow_lps"] = round(fl, 4)
            for el in _segment_elements(model, seg_ids, ("pipe", "plumbing_pipe")):
                nps = str(el.params.get("nps") or "")
                if not nps:
                    continue
                mat = str(el.params.get("material_id") or "copper")
                try:
                    chk = check_pipe(nps, fl, material=mat)
                except ValidationError:
                    continue
                chk["element_id"] = el.id
                checks.append(chk)
        else:
            if fm is None and fl is not None:
                fm = fl * 3.6
            if fm is None:
                row["status"] = "no flow data"
                out.append(row)
                continue
            row["flow_m3h"] = round(fm, 3)
            for el in _segment_elements(model, seg_ids, ("duct", "hvac")):
                w = float(el.params.get("width_mm") or 0)
                h = float(el.params.get("height_mm") or 0)
                if not (w and h):
                    continue
                chk = check_duct(w, h, fm)
                chk["element_id"] = el.id
                checks.append(chk)
        if not checks:
            row["status"] = "no sized segments"
            out.append(row)
            continue
        worst = max(checks, key=lambda c: float(c["velocity_ms"]))
        row["segments_checked"] = len(checks)
        row["worst"] = worst
        row["velocity_ms"] = worst["velocity_ms"]
        if kind == "pipe":
            row["gradient_kpa_m"] = worst["gradient_kpa_m"]
        else:
            row["friction_pa_m"] = worst["friction_pa_m"]
        row["ok"] = all(bool(c["ok"]) for c in checks)
        row["status"] = "ok" if row["ok"] else "warning"
        out.append(row)
    return out
