"""Simple query language for agents.

Examples:
  category=wall
  category=door level=L1
  name~Entry
  type_id=W-SHIELD-CONC
  phase=existing
  kind=shell
  param.thickness_mm>200
  room=Restroom_A
  room~Restroom
  csi=22 11 16
  csi~22 11
  vertical=true
  nps=3/4
"""

from __future__ import annotations

import re
from typing import Any

from llmbim_core.model import Element, ProjectModel


def parse_query(q: str) -> list[tuple[str, str, Any]]:
    """Parse space-separated filters into (field, op, value)."""
    tokens = re.findall(r'(\S+?)(=~|~=|>=|<=|!=|=|>|<|~)(\S+)', q.strip())
    if not tokens and q.strip():
        # bare category shortcut
        return [("category", "=", q.strip())]
    out = []
    for field, op, val in tokens:
        raw = val.strip("\"'")
        # keep CSI-like tokens (22_11_16) as strings — int("22_11") is valid Python but wrong
        if "_" in raw or "/" in raw or (field in ("csi", "csi_code", "csi_number", "nps", "room", "space")):
            val_c: Any = raw
        else:
            try:
                if "." in raw:
                    val_c = float(raw)
                else:
                    val_c = int(raw)
            except ValueError:
                val_c = raw
        out.append((field, op, val_c))
    return out


def _csi_code_for(el: Element, model: ProjectModel) -> str | None:
    try:
        from llmbim_core.csi import csi_for_element

        return str(csi_for_element(model, el).get("csi_code") or "")
    except Exception:  # noqa: BLE001
        return el.params.get("csi_code")


def _room_for(el: Element, model: ProjectModel) -> str | None:
    try:
        from llmbim_core.csi import element_position_mm, room_containing

        x, y, _z = element_position_mm(el)
        if x is None or y is None:
            return None
        return room_containing(model, x, y, el.level_id)
    except Exception:  # noqa: BLE001
        return None


def match_element(el: Element, filters: list[tuple[str, str, Any]], model: ProjectModel) -> bool:
    for field, op, val in filters:
        if field.startswith("param."):
            key = field[6:]
            left = el.params.get(key)
        elif field == "level":
            # name or id
            if el.level_id is None:
                left = None
            else:
                try:
                    left = model.get_level(el.level_id).name
                except Exception:
                    left = el.level_id
            if left != val and el.level_id != val:
                # also try compare
                if op == "=" and str(left) != str(val) and str(el.level_id) != str(val):
                    return False
                if op == "=":
                    continue
        elif field == "kind":
            left = el.params.get("kind")
        elif field == "phase":
            left = el.params.get("phase", "new")
        elif field == "category":
            left = el.category
        elif field == "name":
            left = el.name
        elif field == "type_id":
            left = el.type_id
        elif field == "id":
            left = el.id
        elif field == "host_id":
            left = el.host_id
        elif field in ("room", "space"):
            left = _room_for(el, model)
        elif field in ("csi", "csi_code", "csi_number"):
            # allow csi=22_11_16 or csi=22+11+16 from token parser
            left = _csi_code_for(el, model)
            if left:
                left = str(left).replace("_", " ").replace("+", " ")
            if isinstance(val, str):
                val = val.replace("_", " ").replace("+", " ")
        elif field in ("nps", "system", "material_id", "fitting_type", "part_id"):
            left = el.params.get(field)
        elif field in ("vertical", "riser"):
            left = bool(el.params.get("vertical") or el.params.get("orientation") == "vertical")
            if isinstance(val, str):
                val = val.lower() in ("1", "true", "yes", "riser", "vertical")
            else:
                val = bool(val)
        else:
            left = getattr(el, field, el.params.get(field))

        if field == "level" and op == "=":
            if str(left) == str(val) or str(el.level_id) == str(val):
                continue
            return False

        if op in ("~", "=~", "~="):
            if left is None or str(val).lower() not in str(left).lower():
                return False
        elif op == "=":
            if field in ("vertical", "riser"):
                if bool(left) != bool(val):
                    return False
            elif left is None:
                if val not in (None, "", "None"):
                    return False
            elif isinstance(val, str) and isinstance(left, (str, int, float)):
                if str(left).lower() != str(val).lower():
                    return False
            elif str(left) != str(val):
                return False
        elif op == "!=":
            if str(left) == str(val):
                return False
        elif op in (">", ">=", "<", "<="):
            try:
                lv, rv = float(left), float(val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return False
            if op == ">" and not (lv > rv):
                return False
            if op == ">=" and not (lv >= rv):
                return False
            if op == "<" and not (lv < rv):
                return False
            if op == "<=" and not (lv <= rv):
                return False
    return True


def run_query(model: ProjectModel, q: str) -> list[Element]:
    filters = parse_query(q)
    if not filters:
        return list(model.elements)
    return [el for el in model.elements if match_element(el, filters, model)]
